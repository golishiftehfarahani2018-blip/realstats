from django.db import migrations

SCOPED = [
    "membership",
    "person",
    "property",
    "offering",
    "publiclisting",
    "privatedocument",
    "auditevent",
]
SQL = []
for table in ["person", "offering"]:
    SQL.append(
        f"ALTER TABLE core_{table} ADD CONSTRAINT {table}_scope_unique UNIQUE (id, office_id, organization_id);"
    )
for table in SCOPED:
    SQL.append(
        f"ALTER TABLE core_{table} ADD CONSTRAINT {table}_office_org_fk FOREIGN KEY (office_id, organization_id) REFERENCES core_office (id, organization_id);"
    )
for field, target in [
    ("property", "property"),
    ("owner", "person"),
    ("introducer", "membership"),
    ("assignee", "membership"),
    ("reviewed_by", "membership"),
]:
    SQL.append(
        f"ALTER TABLE core_offering ADD CONSTRAINT offering_{field}_scope_fk FOREIGN KEY ({field}_id, office_id, organization_id) REFERENCES core_{target} (id, office_id, organization_id);"
    )
for table in ["publiclisting", "privatedocument"]:
    SQL.append(
        f"ALTER TABLE core_{table} ADD CONSTRAINT {table}_offering_scope_fk FOREIGN KEY (offering_id, office_id, organization_id) REFERENCES core_offering (id, office_id, organization_id);"
    )
SQL.append(
    "ALTER TABLE core_auditevent ADD CONSTRAINT audit_actor_scope_fk FOREIGN KEY (actor_id, office_id, organization_id) REFERENCES core_membership (id, office_id, organization_id);"
)
SQL.append("""CREATE FUNCTION estate_reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Audit events are append-only'; END; $$;
CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON core_auditevent FOR EACH ROW EXECUTE FUNCTION estate_reject_audit_mutation();
CREATE FUNCTION estate_immutable_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.introducer_id IS DISTINCT FROM OLD.introducer_id OR NEW.office_id IS DISTINCT FROM OLD.office_id OR NEW.organization_id IS DISTINCT FROM OLD.organization_id OR NEW.property_id IS DISTINCT FROM OLD.property_id OR NEW.owner_id IS DISTINCT FROM OLD.owner_id THEN
 RAISE EXCEPTION 'Offering identity and historical introducer are immutable'; END IF; RETURN NEW; END; $$;
CREATE TRIGGER offering_identity BEFORE UPDATE ON core_offering FOR EACH ROW EXECUTE FUNCTION estate_immutable_identity();""")


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunSQL("\n".join(SQL))]
