from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0004_alter_property_area_pricehistory")]
    operations = [
        migrations.RunSQL("""
    ALTER TABLE core_pricehistory ADD CONSTRAINT price_office_org_fk FOREIGN KEY (office_id, organization_id) REFERENCES core_office (id, organization_id);
    ALTER TABLE core_pricehistory ADD CONSTRAINT price_offering_scope_fk FOREIGN KEY (offering_id, office_id, organization_id) REFERENCES core_offering (id, office_id, organization_id);
    ALTER TABLE core_pricehistory ADD CONSTRAINT price_actor_scope_fk FOREIGN KEY (actor_id, office_id, organization_id) REFERENCES core_membership (id, office_id, organization_id);
    ALTER TABLE core_pricehistory ADD CONSTRAINT price_version_unique UNIQUE (offering_id, offering_version);
    CREATE TRIGGER price_append_only BEFORE UPDATE OR DELETE ON core_pricehistory FOR EACH ROW EXECUTE FUNCTION estate_reject_audit_mutation();
    """)
    ]
