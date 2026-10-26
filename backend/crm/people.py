"""Private people and per-office keyed phone index; never expose a duplicate's identity."""

import hashlib
import hmac
from django.conf import settings
from django.db import transaction, IntegrityError
from rest_framework.exceptions import NotFound, PermissionDenied
from core.models import Person
from core.services import Conflict, audit
from core.serializers import normalize
from .models import PersonRelation, PhoneIndex


def phone_digest(phone):
    return hmac.new(
        settings.FIELD_ENCRYPTION_KEY.encode(),
        ("estate-phone-index-v1:" + normalize(phone)).encode(),
        hashlib.sha256,
    ).hexdigest()


def scope(m):
    return {"office_id": m.office_id, "organization_id": m.organization_id}


def people_visible(m):
    qs = Person.objects.filter(**scope(m))
    if m.role != "manager":
        qs = qs.filter(personrelation__membership=m)
    return qs.distinct()


def person_for(m, pk):
    try:
        return people_visible(m).get(pk=pk)
    except Person.DoesNotExist:
        raise NotFound()


def add_relation(m, p, relation):
    if p.office_id != m.office_id or p.organization_id != m.organization_id:
        raise PermissionDenied()
    PersonRelation.objects.get_or_create(
        **scope(m), person=p, membership=m, relation=relation
    )


@transaction.atomic
def resolve_person(m, name, phone, relation):
    digest = phone_digest(phone)
    index = PhoneIndex.objects.filter(**scope(m), digest=digest).first()
    if index:
        if not people_visible(m).filter(pk=index.person_id).exists():
            raise Conflict("این شخص قبلاً ثبت شده؛ درخواست بررسی را به مدیر بدهید.")
        p = index.person
        add_relation(m, p, relation)
        return p
    try:
        with transaction.atomic():
            p = Person.objects.create(
                **scope(m), name=normalize(name), phone=normalize(phone)
            )
            PhoneIndex.objects.create(**scope(m), digest=digest, person=p)
            add_relation(m, p, relation)
            audit(m, "person.create", p.id)
            return p
    except IntegrityError:
        # Unique scoped digest handles concurrent submissions. No other person's ID is returned.
        raise Conflict("این شخص قبلاً ثبت شده؛ درخواست بررسی را به مدیر بدهید.")


def contact(m, pk):
    p = person_for(m, pk)
    audit(m, "customer.contact.view", p.id)
    return {"name": p.name, "phone": p.phone}


def person_summary(m, p):
    relations = PersonRelation.objects.filter(person=p, **scope(m))
    if m.role != "manager":
        relations = relations.filter(membership=m)
    return {
        "id": str(p.id),
        "label": "شخص " + str(p.id)[:8],
        "relations": sorted(set(relations.values_list("relation", flat=True))),
    }
