from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from core.models import Membership, Offering
from core import services as core
from core.services import Conflict, audit
from .models import (
    Demand,
    Cooperation,
    Visit,
    FollowUp,
    Notification,
    AssignmentEvent,
    OfferingAssignmentEvent,
    CooperationHistory,
    VisitHistory,
)
from .people import scope, resolve_person, person_for, add_relation
from .serializers import (
    DemandInput,
    DemandEditInput,
    AssignInput,
    CooperationInput,
    CooperationDecision,
    VisitInput,
    VisitEditInput,
    FollowUpInput,
)
from .matching import evaluate

from .constants import NOTIFICATION_LABELS as EVENT_LABELS


def validate(cls, data):
    value = cls(data=data)
    value.is_valid(raise_exception=True)
    return value.validated_data


def active_actor(m):
    if (
        not m
        or not Membership.objects.filter(
            pk=m.id, active=True, user__is_active=True, office__active=True, **scope(m)
        ).exists()
    ):
        raise PermissionDenied()


def fetch(qs, pk, lock=False):
    if lock:
        qs = qs.select_for_update(of=("self",))
    try:
        return qs.get(pk=pk)
    except qs.model.DoesNotExist:
        raise NotFound()


def version(record, expected):
    if record.version != expected:
        raise Conflict()


def demands(m):
    return Demand.objects.filter(**scope(m))


def demand_for(m, pk, lock=False):
    return fetch(demands(m), pk, lock)


def demand_contact_allowed(m, d):
    return m.role == "manager" or d.introducer_id == m.id


def demand_operator(m, d):
    return demand_contact_allowed(m, d) or d.assignee_id == m.id


def demand_summary(m, d):
    return {
        "id": str(d.id),
        "kind": d.kind,
        "transaction": d.transaction,
        "districts": d.districts,
        "area_min": str(d.area_min),
        "area_max": str(d.area_max),
        **{
            f: str(getattr(d, f))
            for f in [
                "budget_min_toman",
                "budget_max_toman",
                "deposit_max_toman",
                "rent_max_toman",
            ]
        },
        "currency": "IRT",
        "status": d.status,
        "version": d.version,
        "can_edit": demand_contact_allowed(m, d),
        "can_operate": demand_operator(m, d),
        "can_view_private": demand_contact_allowed(m, d),
        "introducer_id": str(d.introducer_id),
        "assignee_id": str(d.assignee_id),
        "created_at": d.created_at.isoformat(),
    }


@transaction.atomic
def create_demand(m, data):
    active_actor(m)
    d = validate(DemandInput, data)
    if "person_id" in d:
        person = person_for(m, d.pop("person_id"))
        add_relation(m, person, "applicant")
    else:
        person = resolve_person(m, d.pop("name"), d.pop("phone"), "applicant")
    demand = Demand.objects.create(
        **scope(m), person=person, introducer=m, assignee=m, **d
    )
    audit(m, "demand.create", demand.id)
    return demand


@transaction.atomic
def edit_demand(m, pk, data):
    active_actor(m)
    d = validate(DemandEditInput, data)
    record = demand_for(m, pk, True)
    if not demand_contact_allowed(m, record):
        raise PermissionDenied()
    version(record, d.pop("version"))
    for key, value in d.items():
        setattr(record, key, value)
    record.version += 1
    record.save()
    audit(m, "demand.edit", record.id)
    return record


def demand_contact(m, pk):
    record = demand_for(m, pk)
    allowed = demand_contact_allowed(m, record)
    audit(m, "demand.contact.view", record.id, "allowed" if allowed else "denied")
    if not allowed:
        raise PermissionDenied()
    return {"name": record.person.name, "phone": record.person.phone}


def notify(m, recipients, event, record_type, record_id):
    # Only controlled codes/UUIDs; never phone, address, customer name, note or arbitrary payload.
    for recipient in Membership.objects.filter(
        id__in=set(recipients), active=True, **scope(m)
    ):
        Notification.objects.create(
            **scope(m),
            recipient=recipient,
            event_code=event,
            record_type=record_type,
            record_id=record_id,
        )


def assign_target(m, data, *, demand_id=None, offering_id=None):
    with transaction.atomic():
        active_actor(m)
        core.manager(m)
        d = validate(AssignInput, data)
        record = (
            demand_for(m, demand_id, True)
            if demand_id
            else core.get_offering(m, offering_id, True)
        )
        version(record, d["version"])
        target = fetch(
            Membership.objects.filter(
                active=True,
                user__is_active=True,
                role__in=["advisor", "senior", "manager"],
                **scope(m),
            ),
            d["assignee_id"],
        )
        if record.assignee_id == target.id:
            return record
        event_cls = AssignmentEvent if demand_id else OfferingAssignmentEvent
        event_cls.objects.create(
            **scope(m),
            **({"demand": record} if demand_id else {"offering": record}),
            previous=record.assignee,
            assignee=target,
            actor=m,
            reason=d["reason"],
        )
        record.assignee = target
        record.version += 1
        record.save()
        kind = "demand" if demand_id else "offering"
        audit(m, kind + ".assign", record.id)
        notify(m, [target.id], kind + ".assigned", kind, record.id)
        return record


def matches(m, pk):
    d = demand_for(m, pk)
    if d.status != "open":
        raise Conflict("تقاضا بسته است.")
    result = []
    for o in (
        Offering.objects.select_related("property", "introducer")
        .filter(status="approved", **scope(m))
        .order_by("id")[:1000]
    ):
        result.append({"offering": core.summary(o, m), **evaluate(d, o)})
    result.sort(key=lambda x: (not x["eligible"], -x["score"], x["offering"]["id"]))
    return result


def cooperations(m):
    qs = Cooperation.objects.select_related("demand", "offering").filter(**scope(m))
    if m.role != "manager":
        qs = qs.filter(
            Q(requested_by=m)
            | Q(supplier=m)
            | Q(demand__introducer=m)
            | Q(demand__assignee=m)
            | Q(offering__assignee=m)
        )
    return qs


def cooperation_for(m, pk, lock=False):
    return fetch(cooperations(m), pk, lock)


def lock_working_records(m, c):
    # Lock current operational records before checking active state/assignee.
    # Closing a demand and scheduling a visit then have an explicit serial order.
    c.demand = demand_for(m, c.demand_id, True)
    c.offering = core.get_offering(m, c.offering_id, True)


def supplier_operator(m, c):
    return m.role == "manager" or m.id in [c.supplier_id, c.offering.assignee_id]


def recipients(c):
    return [
        c.requested_by_id,
        c.supplier_id,
        c.demand.introducer_id,
        c.demand.assignee_id,
        c.offering.assignee_id,
    ]


def cooperation_summary(m, c):
    return {
        "id": str(c.id),
        "demand_id": str(c.demand_id),
        "offering_id": str(c.offering_id),
        "status": c.status,
        "reason_code": c.reason_code,
        "version": c.version,
        "can_decide": (m.role == "manager" or m.id == c.supplier_id)
        and c.status == "requested",
        "can_schedule": supplier_operator(m, c) and c.status == "accepted",
        "can_close": c.status in ["requested", "accepted"],
        "can_reopen": (
            m.role == "manager"
            or m.id in [c.requested_by_id, c.demand.introducer_id, c.demand.assignee_id]
        )
        and c.status in ["rejected", "closed"],
        "created_at": c.created_at.isoformat(),
    }


@transaction.atomic
def request_cooperation(m, data):
    active_actor(m)
    d = validate(CooperationInput, data)
    demand = demand_for(m, d["demand_id"], True)
    if not demand_operator(m, demand):
        raise PermissionDenied()
    offering = core.get_offering(m, d["offering_id"], True)
    if demand.status != "open" or offering.status != "approved":
        raise Conflict("تقاضای باز و عرضه تأییدشده لازم است.")
    try:
        with transaction.atomic():
            c, created = Cooperation.objects.get_or_create(
                demand=demand,
                offering=offering,
                defaults={
                    **scope(m),
                    "requested_by": m,
                    "supplier": offering.introducer,
                },
            )
    except IntegrityError:
        raise Conflict()
    if created:
        CooperationHistory.objects.create(
            **scope(m),
            cooperation=c,
            actor=m,
            version=c.version,
            status=c.status,
            reason_code=c.reason_code,
        )
        audit(m, "cooperation.request", c.id)
        notify(m, recipients(c), "cooperation.requested", "cooperation", c.id)
    return c, created


@transaction.atomic
def decide_cooperation(m, pk, data):
    active_actor(m)
    d = validate(CooperationDecision, data)
    c = cooperation_for(m, pk, True)
    version(c, d["version"])
    lock_working_records(m, c)
    decision = d["decision"]
    if decision in ["accepted", "rejected"]:
        if not (m.role == "manager" or m.id == c.supplier_id):
            raise PermissionDenied()
        if c.status != "requested":
            raise Conflict()
    elif decision == "closed":
        if c.status not in ["requested", "accepted"]:
            raise Conflict()
        if Visit.objects.filter(cooperation=c, status="scheduled").exists():
            raise Conflict("ابتدا بازدید برنامه‌ریزی‌شده را تعیین تکلیف کنید.")
    elif decision == "reopen":
        if not (
            m.role == "manager"
            or m.id in [c.requested_by_id, c.demand.introducer_id, c.demand.assignee_id]
        ):
            raise PermissionDenied()
        if c.status not in ["rejected", "closed"]:
            raise Conflict()
    if decision in ["accepted", "reopen"] and (
        c.demand.status != "open" or c.offering.status != "approved"
    ):
        raise Conflict("پرونده فعال نیست.")
    c.status = "requested" if decision == "reopen" else decision
    c.reason_code = d.get("reason_code", "")
    c.version += 1
    c.save()
    CooperationHistory.objects.create(
        **scope(m),
        cooperation=c,
        actor=m,
        version=c.version,
        status=c.status,
        reason_code=c.reason_code,
    )
    audit(m, "cooperation." + decision, c.id)
    notify(m, recipients(c), "cooperation." + decision, "cooperation", c.id)
    return c


def visits(m):
    return Visit.objects.select_related(
        "cooperation__demand", "cooperation__offering"
    ).filter(cooperation_id__in=cooperations(m).values("id"), **scope(m))


def visit_summary(m, v):
    return {
        "id": str(v.id),
        "cooperation_id": str(v.cooperation_id),
        "scheduled_at": v.scheduled_at.isoformat(),
        "status": v.status,
        "outcome_code": v.outcome_code,
        "version": v.version,
        "can_change": supplier_operator(m, v.cooperation) and v.status == "scheduled",
    }


@transaction.atomic
def create_visit(m, data):
    active_actor(m)
    d = validate(VisitInput, data)
    c = cooperation_for(m, d["cooperation_id"], True)
    version(c, d["cooperation_version"])
    lock_working_records(m, c)
    if not supplier_operator(m, c):
        raise PermissionDenied()
    if (
        c.status != "accepted"
        or c.demand.status != "open"
        or c.offering.status != "approved"
    ):
        raise Conflict("همکاری پذیرفته و پرونده فعال لازم است.")
    if Visit.objects.filter(cooperation=c, status="scheduled").exists():
        raise Conflict("این همکاری بازدید برنامه‌ریزی‌شده دارد.")
    visit = Visit.objects.create(
        **scope(m), cooperation=c, scheduled_at=d["scheduled_at"]
    )
    c.version += 1
    c.save()
    VisitHistory.objects.create(
        **scope(m),
        visit=visit,
        actor=m,
        version=visit.version,
        scheduled_at=visit.scheduled_at,
        status=visit.status,
        outcome_code=visit.outcome_code,
    )
    audit(m, "visit.schedule", visit.id)
    notify(m, recipients(c), "visit.scheduled", "visit", visit.id)
    return visit


@transaction.atomic
def change_visit(m, pk, data):
    active_actor(m)
    d = validate(VisitEditInput, data)
    initial = fetch(visits(m), pk)
    c = cooperation_for(m, initial.cooperation_id, True)
    lock_working_records(m, c)
    v = fetch(visits(m), pk, True)
    version(v, d["version"])
    if not supplier_operator(m, c):
        raise PermissionDenied()
    if v.status != "scheduled":
        raise Conflict()
    action = d["action"]
    if action == "reschedule":
        if (
            c.status != "accepted"
            or c.demand.status != "open"
            or c.offering.status != "approved"
        ):
            raise Conflict()
        v.scheduled_at = d["scheduled_at"]
    elif action == "complete":
        v.status = "completed"
    else:
        v.status = "cancelled"
    v.outcome_code = d.get("outcome_code", "")
    v.version += 1
    v.save()
    c.version += 1
    c.save()
    VisitHistory.objects.create(
        **scope(m),
        visit=v,
        actor=m,
        version=v.version,
        scheduled_at=v.scheduled_at,
        status=v.status,
        outcome_code=v.outcome_code,
    )
    audit(m, "visit." + action, v.id)
    notify(m, recipients(c), "visit." + action, "visit", v.id)
    return v


def followups(m):
    qs = FollowUp.objects.filter(**scope(m))
    return qs if m.role == "manager" else qs.filter(author=m)


def followup_summary(f):
    return {
        "id": str(f.id),
        "cooperation_id": str(f.cooperation_id),
        "kind": f.kind,
        "due_at": f.due_at.isoformat() if f.due_at else None,
        "completed_at": f.completed_at.isoformat() if f.completed_at else None,
        "overdue": bool(f.due_at and not f.completed_at and f.due_at < timezone.now()),
        "version": f.version,
    }


@transaction.atomic
def create_followup(m, data):
    active_actor(m)
    d = validate(FollowUpInput, data)
    c = cooperation_for(m, d.pop("cooperation_id"))
    f = FollowUp.objects.create(**scope(m), cooperation=c, author=m, **d)
    audit(m, "followup.create", f.id)
    notify(m, [m.id], "followup.created", "followup", f.id)
    return f


@transaction.atomic
def complete_followup(m, pk, expected):
    active_actor(m)
    f = fetch(followups(m), pk, True)
    version(f, expected)
    if f.completed_at:
        raise Conflict()
    f.completed_at = timezone.now()
    f.version += 1
    f.save()
    audit(m, "followup.complete", f.id)
    return f


def followup_private(m, pk):
    f = fetch(followups(m), pk)
    audit(m, "followup.view", f.id)
    return {"body": f.body}


def notifications(m):
    return Notification.objects.filter(recipient=m, **scope(m))


def notification_summary(n):
    return {
        "id": str(n.id),
        "event_code": n.event_code,
        "label": EVENT_LABELS.get(n.event_code, "رویداد جدید"),
        "record_type": n.record_type,
        "record_id": str(n.record_id),
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "created_at": n.created_at.isoformat(),
    }


@transaction.atomic
def read_notification(m, pk):
    active_actor(m)
    n = fetch(notifications(m), pk, True)
    if not n.read_at:
        n.read_at = timezone.now()
        n.save(update_fields=["read_at"])
    return n


def assignment_history(m, pk, kind):
    core.manager(m)
    record = demand_for(m, pk) if kind == "demand" else core.get_offering(m, pk)
    cls = AssignmentEvent if kind == "demand" else OfferingAssignmentEvent
    audit(m, kind + ".assignment.history", record.id)
    return [
        {
            "id": str(e.id),
            "previous_id": str(e.previous_id),
            "assignee_id": str(e.assignee_id),
            "actor_id": str(e.actor_id),
            "created_at": e.created_at.isoformat(),
            "reason": e.reason,
        }
        for e in cls.objects.filter(**scope(m), **{kind: record}).order_by(
            "-created_at", "id"
        )[:100]
    ]


def workflow_history(m, pk, kind):
    record = cooperation_for(m, pk) if kind == "cooperation" else fetch(visits(m), pk)
    cls = CooperationHistory if kind == "cooperation" else VisitHistory
    result = []
    for event in cls.objects.filter(**scope(m), **{kind: record}).order_by("version"):
        row = {
            "id": str(event.id),
            "version": event.version,
            "actor_id": str(event.actor_id),
            "status": event.status,
            "created_at": event.created_at.isoformat(),
        }
        if kind == "cooperation":
            row["reason_code"] = event.reason_code
        else:
            row.update(
                scheduled_at=event.scheduled_at.isoformat(),
                outcome_code=event.outcome_code,
            )
        result.append(row)
    return result
