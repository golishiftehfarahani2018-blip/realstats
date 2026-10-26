from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, NotFound, APIException
from .models import Offering, Property, Person, AuditEvent, Membership, PriceHistory


class Conflict(APIException):
    status_code = 409
    default_detail = "نسخه تغییر کرده است؛ اطلاعات را دوباره بارگذاری کنید."


def manager(m):
    if not m or not m.active or m.role != "manager":
        raise PermissionDenied("دسترسی مدیر لازم است.")


def audit(m, action, record=None, outcome="allowed"):
    AuditEvent.objects.create(
        organization_id=m.organization_id,
        office_id=m.office_id,
        actor=m,
        action=action,
        record_id=record,
        outcome=outcome,
    )


def visible(m):
    qs = Offering.objects.select_related("property", "introducer").filter(
        office_id=m.office_id, organization_id=m.organization_id
    )
    if m.role == "manager":
        return qs
    cond = Q(introducer=m) | Q(status="approved")
    if m.role == "senior":
        cond |= Q(status__in=["submitted", "revision"])
    return qs.filter(cond)


def get_offering(m, pk, lock=False):
    qs = visible(m)
    if lock:
        qs = qs.select_for_update(of=("self",))
    try:
        return qs.get(pk=pk)
    except Offering.DoesNotExist:
        raise NotFound()


def private_allowed(m, o):
    return m.role == "manager" or o.introducer_id == m.id


def private_details(m, pk):
    o = get_offering(m, pk)
    allowed = private_allowed(m, o)
    audit(m, "contact.view", o.id, "allowed" if allowed else "denied")
    if not allowed:
        raise PermissionDenied("دسترسی به اطلاعات خصوصی مجاز نیست.")
    return {
        "owner_version": o.owner.version,
        "owner_name": o.owner.name,
        "owner_phone": o.owner.phone,
        "exact_address": o.property.exact_address,
    }


def summary(o, m):
    return {
        "id": str(o.id),
        "property_id": str(o.property_id),
        "kind": o.property.kind,
        "details": o.property.details,
        "district": o.property.district,
        "area": str(o.property.area),
        "transaction": o.transaction,
        "price_toman": str(o.price_toman),
        "negotiable_price": o.negotiable_price,
        "deposit_toman": str(o.deposit_toman),
        "rent_toman": str(o.rent_toman),
        "currency": "IRT",
        "status": o.status,
        "review_reason": o.review_reason
        if private_allowed(m, o) or m.role == "senior"
        else "",
        "version": o.version,
        "created_at": o.created_at.isoformat(),
        "can_edit": (private_allowed(m, o) and o.status in ["draft", "revision"]),
        "can_view_private": private_allowed(m, o),
        "can_review": (
            m.role in ["manager", "senior"]
            and o.introducer_id != m.id
            and o.status == "submitted"
        ),
    }


def price_history(m, o):
    PriceHistory.objects.create(
        organization_id=m.organization_id,
        office_id=m.office_id,
        offering=o,
        actor=m,
        offering_version=o.version,
        price_toman=o.price_toman,
        deposit_toman=o.deposit_toman,
        rent_toman=o.rent_toman,
    )


@transaction.atomic
def create_offering(m, d):
    scope = {"organization_id": m.organization_id, "office_id": m.office_id}
    p = Property.objects.create(
        **scope, details=d.get("details",{}), **{k: d[k] for k in ["kind", "district", "area", "exact_address"]}
    )
    from crm.people import resolve_person

    person = resolve_person(m, d["owner_name"], d["owner_phone"], "owner")
    o = Offering.objects.create(
        **scope,
        property=p,
        negotiable_price=d.get("negotiable_price",False),
        owner=person,
        introducer=m,
        assignee=m,
        **{
            k: d[k]
            for k in ["transaction", "price_toman", "deposit_toman", "rent_toman"]
        },
    )
    price_history(m, o)
    audit(m, "offering.create", o.id)
    return o


@transaction.atomic
def change_offering(m, pk, d, action):
    o = get_offering(m, pk, True)
    if o.version != d["version"]:
        raise Conflict()
    if action in ["edit", "submit"]:
        if not (o.introducer_id == m.id or m.role == "manager") or o.status not in [
            "draft",
            "revision",
        ]:
            raise PermissionDenied()
        if action == "submit":
            o.status = "submitted"
            o.review_reason = ""
        else:
            for k in ["transaction", "price_toman", "deposit_toman", "rent_toman", "negotiable_price"]:
                if k in d:
                    setattr(o, k, d[k])
            for k in ["kind", "district", "area", "exact_address", "details"]:
                if k in d:
                    setattr(o.property, k, {**o.property.details,**d[k]} if k=="details" else d[k])
            o.property.save()
            if "owner_phone" in d and d["owner_phone"] != o.owner.phone:
                raise Conflict(
                    "تغییر شماره شخص نیازمند فرایند اصلاح هویت است؛ شخص جدید ثبت نکنید."
                )
            if "owner_name" in d:
                person = Person.objects.select_for_update().get(pk=o.owner_id)
                if person.name != d["owner_name"]:
                    if d.get("owner_version") != person.version:
                        raise Conflict(
                            "مشخصات شخص تغییر کرده است؛ اطلاعات خصوصی را دوباره دریافت کنید."
                        )
                    person.name = d["owner_name"]
                    person.version += 1
                    person.save(update_fields=["name", "version"])
                    audit(m, "person.rename", person.id)
    elif action == "review":
        if m.role not in ["manager", "senior"] or o.introducer_id == m.id:
            raise PermissionDenied("خودتأییدی مجاز نیست.")
        if o.status != "submitted":
            raise Conflict()
        o.status = d["decision"]
        o.review_reason = d.get("reason", "")
        o.reviewed_by = m
    o.version += 1
    o.save()
    if action == "edit" and any(
        k in d for k in ["price_toman", "deposit_toman", "rent_toman"]
    ):
        price_history(m, o)
    audit(m, "offering." + action, o.id)
    return o


@transaction.atomic
def deactivate(m, pk, active):
    manager(m)
    try:
        target = Membership.objects.select_for_update().get(
            pk=pk,
            office_id=m.office_id,
            organization_id=m.organization_id,
            role="advisor",
        )
    except Membership.DoesNotExist:
        raise NotFound()
    target.active = active
    if not active:
        target.auth_epoch += 1
    target.save(update_fields=["active", "auth_epoch"])
    audit(m, "membership.activate" if active else "membership.deactivate", target.id)
    return target
