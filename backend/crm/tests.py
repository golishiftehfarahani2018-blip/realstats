import secrets
from datetime import timedelta
from django.test import TestCase
from django.db import transaction, DatabaseError, IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient
from core.models import User, Organization, Office, Membership, AuditEvent
from core import services as core
from . import services as s
from .people import resolve_person
from .models import (
    Demand,
    Cooperation,
    Visit,
    Notification,
    AssignmentEvent,
    OfferingAssignmentEvent,
    PersonRelation,
    PhoneIndex,
)


class CRMFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = secrets.token_urlsafe(20)
        cls.org = Organization.objects.create(name="Fictional CRM")
        cls.office = Office.objects.create(
            organization=cls.org, name="Fictional office"
        )
        cls.otheroffice = Office.objects.create(
            organization=cls.org, name="Second office"
        )
        otherorg = Organization.objects.create(name="Other customer")
        cls.thirdoffice = Office.objects.create(
            organization=otherorg, name="Third office"
        )
        cls.members = []
        for name, role, office in [
            ("crm_manager", "manager", cls.office),
            ("crm_first", "advisor", cls.office),
            ("crm_second", "advisor", cls.office),
            ("crm_third", "advisor", cls.office),
            ("crm_senior", "senior", cls.office),
            ("crm_other", "manager", cls.otheroffice),
            ("crm_external", "manager", cls.thirdoffice),
        ]:
            u = User.objects.create_user(username=name, password=cls.password)
            cls.members.append(
                Membership.objects.create(
                    user=u, role=role, organization=office.organization, office=office
                )
            )
        (
            cls.manager,
            cls.supplier,
            cls.requester,
            cls.stranger,
            cls.senior,
            cls.other,
            cls.external,
        ) = cls.members

    def client_for(self, m):
        c = APIClient(enforce_csrf_checks=True)
        token = c.get("/api/v1/auth/csrf").json()["csrfToken"]
        r = c.post(
            "/api/v1/auth/login",
            {"username": m.user.username, "password": self.password},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(r.status_code, 200, r.content)
        c.credentials(HTTP_X_CSRFTOKEN=r.json()["csrfToken"])
        return c

    def demand_data(self, **extra):
        return {
            "name": "SECRET_CUSTOMER",
            "phone": "09911112222",
            "kind": "apartment",
            "transaction": "sale",
            "districts": ["کیان"],
            "area_min": "80",
            "area_max": "120",
            "budget_min_toman": 100,
            "budget_max_toman": 200,
            **extra,
        }

    def offering(self, m=None):
        m = m or self.supplier
        o = core.create_offering(
            m,
            {
                "kind": "apartment",
                "district": "کیان",
                "area": "90",
                "exact_address": "SECRET_ADDRESS",
                "owner_name": "SECRET_OWNER",
                "owner_phone": "09123456789",
                "transaction": "sale",
                "price_toman": 150,
                "deposit_toman": 0,
                "rent_toman": 0,
            },
        )
        o = core.change_offering(m, o.id, {"version": 1}, "submit")
        reviewer = self.manager if m.office_id == self.office.id else m
        if reviewer.id == m.id:
            # Only needed for cross-office isolation fixture: alternate historical advisor.
            u = User.objects.create_user(
                username="fixture_" + secrets.token_hex(4), password=self.password
            )
            reviewer = Membership.objects.create(
                user=u, role="senior", office=m.office, organization=m.organization
            )
        return core.change_offering(
            reviewer, o.id, {"version": 2, "decision": "approved"}, "review"
        )

    def pair(self):
        d = s.create_demand(self.requester, self.demand_data())
        o = self.offering()
        c, _ = s.request_cooperation(
            self.requester, {"demand_id": str(d.id), "offering_id": str(o.id)}
        )
        return d, o, c

    def accepted(self):
        d, o, c = self.pair()
        c = s.decide_cooperation(
            self.supplier, c.id, {"version": 1, "decision": "accepted"}
        )
        return d, o, c

    def test_full_customer_match_cooperation_visit_followup_flow(self):
        a = self.client_for(self.supplier)
        b = self.client_for(self.requester)
        o = self.offering()
        r = b.post("/api/v1/demands", self.demand_data(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        r = b.get(f"/api/v1/demands/{d['id']}/matches")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["results"][0]["score"], 100)
        r = b.post(
            "/api/v1/cooperations",
            {"demand_id": d["id"], "offering_id": str(o.id)},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        c = r.json()
        r = a.patch(
            "/api/v1/cooperations/" + c["id"],
            {"version": 1, "decision": "accepted"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        r = a.post(
            "/api/v1/visits",
            {
                "cooperation_id": c["id"],
                "cooperation_version": 2,
                "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        v = r.json()
        self.assertEqual(
            a.patch(
                "/api/v1/visits/" + v["id"],
                {"version": 1, "action": "complete", "outcome_code": "interested"},
                format="json",
            ).status_code,
            200,
        )
        r = b.post(
            "/api/v1/followups",
            {
                "cooperation_id": c["id"],
                "kind": "task",
                "body": "SECRET_PRIVATE_NOTE 09911112222",
                "due_at": (timezone.now() + timedelta(hours=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        f = r.json()
        self.assertEqual(
            b.patch(
                "/api/v1/followups/" + f["id"], {"version": 1}, format="json"
            ).status_code,
            200,
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.supplier, event_code="cooperation.requested"
            ).exists()
        )
        self.assertEqual(a.get(f"/api/v1/demands/{d['id']}/private").status_code, 403)
        self.assertEqual(b.get(f"/api/v1/offerings/{o.id}/private").status_code, 403)

    def test_duplicate_phone_never_leaks_another_advisors_identity(self):
        person = resolve_person(
            self.supplier, "SECRET_CUSTOMER", "09911112222", "applicant"
        )
        r = self.client_for(self.requester).post(
            "/api/v1/people", {"name": "other", "phone": "09911112222"}, format="json"
        )
        self.assertEqual(r.status_code, 409, r.content)
        for secret in ["SECRET_CUSTOMER", str(person.id), "09911112222"]:
            self.assertNotIn(secret, r.content.decode())
        self.assertEqual(PhoneIndex.objects.count(), 1)

    def test_same_person_can_be_owner_and_applicant(self):
        o = self.offering()
        c = self.client_for(self.supplier)
        d = self.demand_data(person_id=str(o.owner_id))
        del d["name"]
        del d["phone"]
        r = c.post("/api/v1/demands", d, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(
            set(
                PersonRelation.objects.filter(
                    person_id=o.owner_id, membership=self.supplier
                ).values_list("relation", flat=True)
            ),
            {"owner", "applicant"},
        )

    def test_customer_contact_and_private_identifiers(self):
        d = s.create_demand(self.requester, self.demand_data())
        for m in [self.supplier, self.stranger, self.senior]:
            c = self.client_for(m)
            self.assertEqual(c.get(f"/api/v1/demands/{d.id}/private").status_code, 403)
            self.assertEqual(
                c.get(f"/api/v1/people/{d.person_id}/private").status_code, 404
            )
            for path in ["/demands", "/demands?q=09911112222", "/people"]:
                r = c.get("/api/v1" + path)
                for secret in ["09911112222", "SECRET_CUSTOMER", "phone", "digest"]:
                    self.assertNotIn(secret, r.content.decode())
        for m in [self.requester, self.manager]:
            self.assertEqual(
                self.client_for(m).get(f"/api/v1/demands/{d.id}/private").status_code,
                200,
            )
        self.assertEqual(
            AuditEvent.objects.filter(
                action="demand.contact.view", outcome="allowed"
            ).count(),
            2,
        )

    def test_matching_excludes_drafts_and_other_offices(self):
        d = s.create_demand(self.requester, self.demand_data())
        self.offering()
        self.offering(self.other)
        r = self.client_for(self.requester).get(f"/api/v1/demands/{d.id}/matches")
        self.assertEqual(r.json()["count"], 1)
        for secret in ["SECRET_OWNER", "SECRET_ADDRESS", "09123456789", "09911112222"]:
            self.assertNotIn(secret, r.content.decode())

    def test_cross_office_and_customer_isolation(self):
        d, o, c = self.pair()
        for m in [self.other, self.external]:
            client = self.client_for(m)
            for path in [
                f"/demands/{d.id}",
                f"/demands/{d.id}/private",
                f"/demands/{d.id}/matches",
                f"/cooperations/{c.id}",
            ]:
                self.assertEqual(client.get("/api/v1" + path).status_code, 404)
            self.assertEqual(client.get("/api/v1/demands").json()["count"], 0)

    def test_forged_identity_and_unauthorized_cooperation(self):
        d, o, c = self.pair()
        x = self.client_for(self.stranger)
        for field in ["office", "organization", "introducer", "assignee", "role"]:
            self.assertEqual(
                x.post(
                    "/api/v1/demands",
                    self.demand_data(**{field: "forged"}),
                    format="json",
                ).status_code,
                400,
            )
        self.assertEqual(
            x.post(
                "/api/v1/cooperations",
                {"demand_id": str(d.id), "offering_id": str(o.id)},
                format="json",
            ).status_code,
            403,
        )
        self.assertEqual(x.get("/api/v1/cooperations/" + str(c.id)).status_code, 404)
        self.assertEqual(
            self.client_for(self.requester)
            .patch(
                "/api/v1/cooperations/" + str(c.id),
                {"version": 1, "decision": "accepted"},
                format="json",
            )
            .status_code,
            403,
        )

    def test_cooperation_repeats_are_idempotent(self):
        d, o, c = self.pair()
        count = Notification.objects.count()
        again, created = s.request_cooperation(
            self.requester, {"demand_id": str(d.id), "offering_id": str(o.id)}
        )
        self.assertFalse(created)
        self.assertEqual(again.id, c.id)
        self.assertEqual(Notification.objects.count(), count)

    def test_rejection_requires_reason_and_reopening_preserves_record(self):
        d, o, c = self.pair()
        a = self.client_for(self.supplier)
        self.assertEqual(
            a.patch(
                f"/api/v1/cooperations/{c.id}",
                {"version": 1, "decision": "rejected"},
                format="json",
            ).status_code,
            400,
        )
        s.decide_cooperation(
            self.supplier,
            c.id,
            {"version": 1, "decision": "rejected", "reason_code": "not_available"},
        )
        reopened = s.decide_cooperation(
            self.requester,
            c.id,
            {"version": 2, "decision": "reopen", "reason_code": "needs_update"},
        )
        self.assertEqual(reopened.id, c.id)
        self.assertEqual(reopened.version, 3)

    def test_assignment_preserves_introducers_and_does_not_grant_contact(self):
        d, o, c = self.pair()
        s.assign_target(
            self.manager,
            {
                "version": d.version,
                "assignee_id": str(self.stranger.id),
                "reason": "جایگزین",
            },
            demand_id=d.id,
        )
        s.assign_target(
            self.manager,
            {
                "version": o.version,
                "assignee_id": str(self.stranger.id),
                "reason": "جایگزین",
            },
            offering_id=o.id,
        )
        d.refresh_from_db()
        o.refresh_from_db()
        self.assertEqual(d.introducer_id, self.requester.id)
        self.assertEqual(o.introducer_id, self.supplier.id)
        x = self.client_for(self.stranger)
        self.assertEqual(x.get(f"/api/v1/demands/{d.id}/private").status_code, 403)
        self.assertEqual(x.get(f"/api/v1/offerings/{o.id}/private").status_code, 403)
        self.assertEqual(AssignmentEvent.objects.count(), 1)
        self.assertEqual(OfferingAssignmentEvent.objects.count(), 1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            AssignmentEvent.objects.all().update(reason="changed")

    def test_reassignment_rejects_another_office(self):
        d = s.create_demand(self.requester, self.demand_data())
        r = self.client_for(self.manager).post(
            f"/api/v1/demands/{d.id}/assign",
            {"version": 1, "assignee_id": str(self.other.id), "reason": "test"},
            format="json",
        )
        self.assertEqual(r.status_code, 404)

    def test_visit_requires_acceptance_supplier_and_current_version(self):
        d, o, c = self.pair()
        payload = {
            "cooperation_id": str(c.id),
            "cooperation_version": 1,
            "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat(),
        }
        a = self.client_for(self.supplier)
        b = self.client_for(self.requester)
        self.assertEqual(
            a.post("/api/v1/visits", payload, format="json").status_code, 409
        )
        c = s.decide_cooperation(
            self.supplier, c.id, {"version": 1, "decision": "accepted"}
        )
        payload["cooperation_version"] = 2
        self.assertEqual(
            b.post("/api/v1/visits", payload, format="json").status_code, 403
        )
        r = a.post("/api/v1/visits", payload, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(
            a.post("/api/v1/visits", payload, format="json").status_code, 409
        )
        self.assertEqual(Visit.objects.count(), 1)
        self.assertEqual(
            a.patch(
                "/api/v1/visits/" + r.json()["id"],
                {"version": 2, "action": "cancel", "outcome_code": "other"},
                format="json",
            ).status_code,
            409,
        )

    def test_followup_text_is_private_to_author_and_manager(self):
        d, o, c = self.pair()
        f = s.create_followup(
            self.requester,
            {
                "cooperation_id": str(c.id),
                "kind": "note",
                "body": "SECRET_NOTE 09911112222",
            },
        )
        a = self.client_for(self.supplier)
        b = self.client_for(self.requester)
        self.assertEqual(a.get(f"/api/v1/followups/{f.id}/private").status_code, 404)
        self.assertEqual(
            b.get(f"/api/v1/followups/{f.id}/private").json()["body"],
            "SECRET_NOTE 09911112222",
        )
        self.assertNotIn("SECRET_NOTE", b.get("/api/v1/followups").content.decode())
        self.assertEqual(
            self.client_for(self.manager)
            .get(f"/api/v1/followups/{f.id}/private")
            .status_code,
            200,
        )

    def test_notifications_are_recipient_scoped_and_have_no_private_payload(self):
        d, o, c = self.pair()
        a = self.client_for(self.supplier)
        b = self.client_for(self.requester)
        n = Notification.objects.filter(recipient=self.supplier).first()
        self.assertEqual(
            b.patch(f"/api/v1/notifications/{n.id}", {}, format="json").status_code, 404
        )
        self.assertEqual(
            a.patch(f"/api/v1/notifications/{n.id}", {}, format="json").status_code, 200
        )
        self.assertEqual(
            a.patch(f"/api/v1/notifications/{n.id}", {}, format="json").status_code, 200
        )
        response = a.get("/api/v1/notifications").content.decode()
        for secret in [
            "SECRET_CUSTOMER",
            "09911112222",
            "SECRET_OWNER",
            "09123456789",
            "SECRET_ADDRESS",
        ]:
            self.assertNotIn(secret, response)

    def test_database_rejects_cross_office_links_and_historical_rewrite(self):
        d, o, c = self.pair()
        with self.assertRaises(DatabaseError), transaction.atomic():
            Demand.objects.filter(pk=d.id).update(introducer=self.stranger)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Demand.objects.filter(pk=d.id).update(assignee=self.other)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Cooperation.objects.filter(pk=c.id).update(supplier=self.stranger)
        p = resolve_person(self.other, "شخص دیگر", "09933334444", "applicant")
        with self.assertRaises(IntegrityError), transaction.atomic():
            PersonRelation.objects.create(
                person=p,
                membership=self.requester,
                relation="applicant",
                office=self.office,
                organization=self.org,
            )

    def test_version_conflict_and_csrf(self):
        d = s.create_demand(self.requester, self.demand_data())
        b = self.client_for(self.requester)
        payload = self.demand_data(version=1, status="open")
        del payload["name"]
        del payload["phone"]
        self.assertEqual(
            b.patch(f"/api/v1/demands/{d.id}", payload, format="json").status_code, 200
        )
        self.assertEqual(
            b.patch(f"/api/v1/demands/{d.id}", payload, format="json").status_code, 409
        )
        b.credentials()
        self.assertEqual(
            b.post("/api/v1/demands", self.demand_data(), format="json").status_code,
            403,
        )

    def test_disabled_account_cannot_access_phase_two(self):
        b = self.client_for(self.requester)
        core.deactivate(self.manager, self.requester.id, False)
        for path in [
            "/demands",
            "/people",
            "/cooperations",
            "/visits",
            "/followups",
            "/notifications",
        ]:
            self.assertEqual(b.get("/api/v1" + path).status_code, 403)

    def test_due_followups_are_real_queries_not_sending_reminders(self):
        d, o, c = self.pair()
        s.create_followup(
            self.requester,
            {
                "cooperation_id": str(c.id),
                "kind": "task",
                "body": "سررسید",
                "due_at": (timezone.now() - timedelta(hours=1)).isoformat(),
            },
        )
        response = self.client_for(self.requester).get("/api/v1/followups?due=1").json()
        self.assertEqual(response["count"], 1)
        self.assertTrue(response["results"][0]["overdue"])

    def test_visit_and_cooperation_history_are_append_only(self):
        from .models import CooperationHistory, VisitHistory

        d, o, c = self.accepted()
        v = s.create_visit(
            self.supplier,
            {
                "cooperation_id": str(c.id),
                "cooperation_version": c.version,
                "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat(),
            },
        )
        old = v.scheduled_at
        s.change_visit(
            self.supplier,
            v.id,
            {
                "version": 1,
                "action": "reschedule",
                "scheduled_at": (timezone.now() + timedelta(days=2)).isoformat(),
                "outcome_code": "schedule_conflict",
            },
        )
        history = s.workflow_history(self.requester, v.id, "visit")
        self.assertEqual(len(history), 2)
        self.assertEqual(parse_datetime(history[0]["scheduled_at"]), old)
        self.assertEqual(CooperationHistory.objects.filter(cooperation=c).count(), 2)
        with self.assertRaises(DatabaseError), transaction.atomic():
            VisitHistory.objects.filter(visit=v).delete()

    def test_shared_person_name_uses_a_separate_version(self):
        o = core.create_offering(
            self.supplier,
            {
                "kind": "apartment",
                "district": "نمونه",
                "area": 90,
                "exact_address": "نشانی",
                "owner_name": "نام اولیه",
                "owner_phone": "09123456789",
                "transaction": "sale",
                "price_toman": 10,
                "deposit_toman": 0,
                "rent_toman": 0,
            },
        )
        other = core.create_offering(
            self.supplier,
            {
                "kind": "land",
                "district": "نمونه",
                "area": 100,
                "exact_address": "نشانی دیگر",
                "owner_name": "نام اولیه",
                "owner_phone": "09123456789",
                "transaction": "sale",
                "price_toman": 20,
                "deposit_toman": 0,
                "rent_toman": 0,
            },
        )
        self.assertEqual(o.owner_id, other.owner_id)
        core.change_offering(
            self.supplier,
            o.id,
            {"version": 1, "owner_version": 1, "owner_name": "نام اصلاح‌شده"},
            "edit",
        )
        from core.services import Conflict

        with self.assertRaises(Conflict):
            core.change_offering(
                self.supplier,
                other.id,
                {"version": 1, "owner_version": 1, "owner_name": "تغییر کهنه"},
                "edit",
            )
        self.assertEqual(
            core.private_details(self.supplier, other.id)["owner_version"], 2
        )

    def test_existing_person_uuid_does_not_grant_customer_contact(self):
        person = resolve_person(self.supplier, "شخص خصوصی", "09911112222", "applicant")
        data = self.demand_data(person_id=str(person.id))
        del data["name"]
        del data["phone"]
        response = self.client_for(self.requester).post(
            "/api/v1/demands", data, format="json"
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            PersonRelation.objects.filter(
                person=person, membership=self.requester
            ).exists()
        )
        self.assertEqual(Demand.objects.count(), 0)

    def test_followup_body_is_encrypted_in_postgresql(self):
        from django.db import connection

        d, o, c = self.pair()
        f = s.create_followup(
            self.requester,
            {
                "cooperation_id": str(c.id),
                "kind": "note",
                "body": "SECRET_NOTE 09911112222",
            },
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT body FROM crm_followup WHERE id=%s", [f.id])
            value = cursor.fetchone()[0]
        self.assertNotIn("SECRET_NOTE", value)
        self.assertNotIn("09911112222", value)

    def test_closed_demand_prevents_new_matching_and_scheduling(self):
        d, o, c = self.accepted()
        data = self.demand_data(version=1, status="closed")
        del data["name"]
        del data["phone"]
        s.edit_demand(self.requester, d.id, data)
        b = self.client_for(self.requester)
        a = self.client_for(self.supplier)
        self.assertEqual(b.get(f"/api/v1/demands/{d.id}/matches").status_code, 409)
        self.assertEqual(
            a.post(
                "/api/v1/visits",
                {
                    "cooperation_id": str(c.id),
                    "cooperation_version": 2,
                    "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat(),
                },
                format="json",
            ).status_code,
            409,
        )
