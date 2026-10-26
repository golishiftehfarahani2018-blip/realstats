import secrets
from django.test import TestCase
from django.db import connection, transaction, IntegrityError, DatabaseError
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from .models import (
    Organization,
    Office,
    Membership,
    Offering,
    AuditEvent,
    PriceHistory,
)
from . import services as s
from .serializers import OfferingInput


class SecurityFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = secrets.token_urlsafe(20)
        cls.org = Organization.objects.create(name="Fictional")
        cls.office = Office.objects.create(organization=cls.org, name="Sample")
        cls.otheroffice = Office.objects.create(organization=cls.org, name="Other")
        cls.otherorg = Organization.objects.create(name="Second")
        cls.thirdoffice = Office.objects.create(organization=cls.otherorg, name="Third")
        cls.members = []
        for username, role, office in [
            ("manager", "manager", cls.office),
            ("first", "advisor", cls.office),
            ("second", "advisor", cls.office),
            ("senior", "senior", cls.office),
            ("other", "manager", cls.otheroffice),
            ("third", "manager", cls.thirdoffice),
        ]:
            user = get_user_model().objects.create_user(
                username=username, password=cls.password
            )
            cls.members.append(
                Membership.objects.create(
                    user=user,
                    role=role,
                    office=office,
                    organization=office.organization,
                )
            )
        cls.manager, cls.first, cls.second, cls.senior, cls.other, cls.third = (
            cls.members
        )

    def payload(self):
        return {
            "kind": "apartment",
            "district": "محله نمونه",
            "area": 90,
            "exact_address": "SECRET_ADDRESS_771",
            "owner_name": "PRIVATE_OWNER",
            "owner_phone": "09123456789",
            "transaction": "sale",
            "price_toman": 5000000000,
            "deposit_toman": 0,
            "rent_toman": 0,
        }

    def client_for(self, m, csrf=False):
        c = APIClient(enforce_csrf_checks=csrf)
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

    def create(self, m=None):
        return s.create_offering(m or self.first, self.payload())

    def approve(self, o):
        o = s.change_offering(self.first, o.id, {"version": o.version}, "submit")
        return s.change_offering(
            self.manager, o.id, {"version": o.version, "decision": "approved"}, "review"
        )

    def test_real_postgresql(self):
        self.assertEqual(connection.vendor, "postgresql")

    def test_full_flow_and_contact_audit(self):
        m = self.client_for(self.manager, True)
        r = m.post(
            "/api/v1/advisors",
            {
                "username": "newadvisor",
                "first_name": "مشاور جدید",
                "password": secrets.token_urlsafe(20),
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        a = self.client_for(self.first, True)
        b = self.client_for(self.second, True)
        r = a.post("/api/v1/offerings", self.payload(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        o = r.json()
        url = "/api/v1/offerings/" + o["id"]
        self.assertEqual(b.get(url).status_code, 404)
        r = a.post(url + "/submit", {"version": 1}, format="json")
        self.assertEqual(r.status_code, 200)
        r = m.post(
            url + "/review",
            {"version": 2, "decision": "revision", "reason": "قیمت را بررسی کنید"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        r = a.patch(url, {"version": 3, "price_toman": "۵۲۰۰۰۰۰۰۰۰"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            a.post(url + "/submit", {"version": 4}, format="json").status_code, 200
        )
        self.assertEqual(
            m.post(
                url + "/review", {"version": 5, "decision": "approved"}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(b.get(url).status_code, 200)
        self.assertEqual(b.get(url + "/private").status_code, 403)
        self.assertEqual(a.get(url + "/private").json()["owner_phone"], "09123456789")
        self.assertEqual(m.get(url + "/private").status_code, 200)
        self.assertEqual(
            AuditEvent.objects.filter(action="contact.view", outcome="allowed").count(),
            2,
        )
        self.assertTrue(
            AuditEvent.objects.filter(action="contact.view", outcome="denied").exists()
        )

    def test_identifier_swapping_and_no_leak(self):
        o = self.approve(self.create())
        b = self.client_for(self.second)
        for suffix in [
            "",
            "?q=09123456789",
            "?q=PRIVATE_OWNER",
            "?q=SECRET_ADDRESS_771",
            "?q=نمونه",
        ]:
            r = b.get("/api/v1/offerings" + suffix)
            self.assertEqual(r.status_code, 200)
            for secret in [
                "09123456789",
                "SECRET_ADDRESS_771",
                "PRIVATE_OWNER",
                "owner_phone",
                "exact_address",
                "storage_key",
            ]:
                self.assertNotIn(secret, r.content.decode())
        self.assertEqual(b.get(f"/api/v1/offerings/{o.id}/private").status_code, 403)
        self.assertEqual(b.get(f"/api/v1/offerings/{o.id}/documents").status_code, 403)

    def test_draft_and_unauthorized_review(self):
        o = self.create()
        b = self.client_for(self.second)
        self.assertEqual(b.get(f"/api/v1/offerings/{o.id}").status_code, 404)
        self.assertEqual(b.get("/api/v1/offerings").json(), [])
        s.change_offering(self.first, o.id, {"version": 1}, "submit")
        self.assertEqual(
            self.client_for(self.first)
            .post(
                f"/api/v1/offerings/{o.id}/review",
                {"version": 2, "decision": "approved"},
                format="json",
            )
            .status_code,
            403,
        )
        self.assertEqual(
            b.post(
                f"/api/v1/offerings/{o.id}/review",
                {"version": 2, "decision": "approved"},
                format="json",
            ).status_code,
            404,
        )

    def test_senior_review_does_not_grant_contact(self):
        o = self.create()
        c = self.client_for(self.senior)
        self.assertEqual(c.get(f"/api/v1/offerings/{o.id}").status_code, 404)
        s.change_offering(self.first, o.id, {"version": 1}, "submit")
        self.assertEqual(c.get(f"/api/v1/offerings/{o.id}").status_code, 200)
        self.assertEqual(c.get(f"/api/v1/offerings/{o.id}/private").status_code, 403)
        self.assertEqual(
            c.post(
                f"/api/v1/offerings/{o.id}/review",
                {"version": 2, "decision": "approved"},
                format="json",
            ).status_code,
            200,
        )

    def test_office_and_organization_isolation(self):
        o = self.approve(self.create())
        for m in [self.other, self.third]:
            c = self.client_for(m)
            self.assertEqual(c.get("/api/v1/offerings").json(), [])
            for suffix in ["", "/private", "/documents"]:
                self.assertEqual(
                    c.get(f"/api/v1/offerings/{o.id}" + suffix).status_code, 404
                )
        cross = self.create(self.other)
        self.assertEqual(
            self.client_for(self.manager)
            .get(f"/api/v1/offerings/{cross.id}")
            .status_code,
            404,
        )

    def test_forged_office_role_and_introducer(self):
        c = self.client_for(self.first)
        for key, value in [
            ("office", str(self.otheroffice.id)),
            ("organization", str(self.otherorg.id)),
            ("introducer", str(self.second.id)),
            ("role", "manager"),
            ("status", "approved"),
            ("assignee", str(self.second.id)),
        ]:
            d = self.payload()
            d[key] = value
            self.assertEqual(
                c.post("/api/v1/offerings", d, format="json").status_code, 400
            )
        self.assertEqual(Offering.objects.count(), 0)
        self.assertEqual(
            c.post("/api/v1/advisors", {"role": "manager"}, format="json").status_code,
            403,
        )

    def test_deactivation_blocks_existing_session(self):
        c = self.client_for(self.first)
        self.assertEqual(c.get("/api/v1/me").status_code, 200)
        r = self.client_for(self.manager).patch(
            f"/api/v1/advisors/{self.first.id}", {"active": False}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(c.get("/api/v1/me").status_code, 403)
        self.assertEqual(
            c.post("/api/v1/offerings", self.payload(), format="json").status_code, 403
        )

    def test_reactivation_never_revives_old_session(self):
        c = self.client_for(self.first)
        s.deactivate(self.manager, self.first.id, False)
        s.deactivate(self.manager, self.first.id, True)
        self.assertEqual(c.get("/api/v1/me").status_code, 403)
        self.assertEqual(self.client_for(self.first).get("/api/v1/me").status_code, 200)

    def test_account_deactivation_blocks_session(self):
        c = self.client_for(self.first)
        self.first.user.is_active = False
        self.first.user.save()
        self.assertEqual(c.get("/api/v1/offerings").status_code, 403)

    def test_version_conflict(self):
        o = self.create()
        c = self.client_for(self.first)
        url = f"/api/v1/offerings/{o.id}"
        self.assertEqual(
            c.patch(url, {"version": 1, "price_toman": 12}, format="json").status_code,
            200,
        )
        self.assertEqual(
            c.patch(url, {"version": 1, "price_toman": 99}, format="json").status_code,
            409,
        )
        o.refresh_from_db()
        self.assertEqual(o.price_toman, 12)

    def test_price_history_and_private_revision(self):
        o = self.create()
        c = self.client_for(self.first)
        r = c.patch(
            f"/api/v1/offerings/{o.id}",
            {
                "version": 1,
                "price_toman": "۱۲۳۴",
                "area": "۹۰.۲۵",
                "exact_address": "نشانی اصلاح‌شده",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["area"], "90.25")
        self.assertEqual(PriceHistory.objects.filter(offering=o).count(), 2)
        self.assertEqual(
            c.get(f"/api/v1/offerings/{o.id}/private").json()["exact_address"],
            "نشانی اصلاح‌شده",
        )

    def test_csrf_required_including_login(self):
        c = APIClient(enforce_csrf_checks=True)
        self.assertEqual(
            c.post(
                "/api/v1/auth/login",
                {"username": "first", "password": self.password},
                format="json",
            ).status_code,
            403,
        )
        c = self.client_for(self.first, True)
        c.credentials()
        self.assertEqual(
            c.post("/api/v1/offerings", self.payload(), format="json").status_code, 403
        )

    def test_database_scope_constraints_and_immutable_referral(self):
        o = self.create()
        for changes in [
            {"assignee": self.other},
            {"introducer": self.second},
            {"office": self.otheroffice},
        ]:
            with self.assertRaises(DatabaseError), transaction.atomic():
                Offering.objects.filter(pk=o.id).update(**changes)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Membership.objects.create(
                user=self.second.user,
                organization=self.otherorg,
                office=self.office,
                role="advisor",
            )

    def test_audit_append_only(self):
        o = self.create()
        event = AuditEvent.objects.get(action="offering.create", record_id=o.id)
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuditEvent.objects.filter(pk=event.id).update(action="changed")
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuditEvent.objects.filter(pk=event.id).delete()
        c = self.client_for(self.manager)
        self.assertEqual(c.delete("/api/v1/audit").status_code, 405)

    def test_encrypted_storage(self):
        o = self.create()
        with connection.cursor() as cur:
            cur.execute("SELECT phone FROM core_person WHERE id=%s", [o.owner_id])
            encrypted = cur.fetchone()[0]
        self.assertNotIn("09123456789", encrypted)
        self.assertEqual(o.owner.phone, "09123456789")

    def test_integer_money_and_normalization(self):
        for value in [1.1, "1.0", True, -1]:
            d = self.payload()
            d["price_toman"] = value
            self.assertFalse(OfferingInput(data=d).is_valid())
        d = self.payload()
        d.update(district="كيان", price_toman="۱۲۳۴", owner_phone="٠٩١٢٣٤٥٦٧٨٩")
        ser = OfferingInput(data=d)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data["district"], "کیان")

    def test_assignee_is_not_introducer(self):
        o = self.approve(self.create())
        Offering.objects.filter(pk=o.id).update(assignee=self.second)
        self.assertEqual(
            self.client_for(self.second)
            .get(f"/api/v1/offerings/{o.id}/private")
            .status_code,
            403,
        )
        o.refresh_from_db()
        self.assertEqual(o.introducer_id, self.first.id)

    def test_private_responses_never_cached(self):
        o = self.create()
        r = self.client_for(self.first).get(f"/api/v1/offerings/{o.id}/private")
        self.assertIn("no-store", r["Cache-Control"])
        self.assertIn("Cookie", r["Vary"])

    def test_inventory_pages_filter_before_count_and_preserve_privacy(self):
        for _ in range(3):
            self.approve(self.create())
        self.create()  # Another advisor must neither see nor count this draft.
        c = self.client_for(self.second)
        url = '/api/v1/offerings?paginated=1&limit=2&kind=apartment&transaction=sale&area_min=۸۰&price_max=6000000000'
        first = c.get(url)
        self.assertEqual(first.status_code, 200)
        data = first.json()
        self.assertEqual(data['count'], 3)
        self.assertTrue(data['has_more'])
        self.assertEqual(len(data['results']), 2)
        last = c.get(url+'&offset=2').json()
        self.assertFalse(last['has_more'])
        self.assertEqual(len(last['results']), 1)
        self.assertTrue(set(x['id'] for x in data['results']).isdisjoint(x['id'] for x in last['results']))
        for secret in ['SECRET_ADDRESS_771', 'PRIVATE_OWNER', '09123456789']:
            self.assertNotIn(secret, str(data))
        self.assertEqual(c.get('/api/v1/offerings?paginated=1&status=draft').json()['count'], 0)
        self.assertEqual(c.get(url+'&q=ناشناخته').json()['count'], 0)

    def test_inventory_filter_validation(self):
        c = self.client_for(self.manager)
        for query in ['limit=101', 'offset=-1', 'area_min=100&area_max=10',
                      'price_min=1', 'transaction=sale&rent_max=100',
                      'transaction=sale&price_min=12.5', 'owner_phone=09123456789',
                      'kind=unknown', 'paginated=no']:
            with self.subTest(query=query):
                self.assertEqual(c.get('/api/v1/offerings?'+query).status_code, 400)

    def test_inventory_count_is_scoped_to_office(self):
        self.approve(self.create())
        result = self.client_for(self.other).get('/api/v1/offerings?paginated=1').json()
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['results'], [])
