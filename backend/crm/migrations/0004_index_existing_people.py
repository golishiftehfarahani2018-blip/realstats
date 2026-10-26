"""Retain legacy identities; index a canonical row without merging historical referrals."""

import hashlib
import hmac
from django.conf import settings
from django.db import migrations

TRANSLATE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩كي", "01234567890123456789کی")


def forward(apps, schema_editor):
    Person = apps.get_model("core", "Person")
    Offering = apps.get_model("core", "Offering")
    Index = apps.get_model("crm", "PhoneIndex")
    Relation = apps.get_model("crm", "PersonRelation")
    alias = schema_editor.connection.alias
    for p in Person.objects.using(alias).order_by("created_at", "id").iterator():
        normalized = p.phone.translate(TRANSLATE).strip()
        digest = hmac.new(
            settings.FIELD_ENCRYPTION_KEY.encode(),
            ("estate-phone-index-v1:" + normalized).encode(),
            hashlib.sha256,
        ).hexdigest()
        Index.objects.using(alias).get_or_create(
            office_id=p.office_id,
            organization_id=p.organization_id,
            digest=digest,
            defaults={"person_id": p.id},
        )
    for o in Offering.objects.using(alias).iterator():
        Relation.objects.using(alias).get_or_create(
            office_id=o.office_id,
            organization_id=o.organization_id,
            person_id=o.owner_id,
            membership_id=o.introducer_id,
            relation="owner",
        )


class Migration(migrations.Migration):
    dependencies = [("crm", "0003_scope_and_history")]
    operations = [migrations.RunPython(forward)]
