from django.db import migrations

SQL = []
TABLES = [
    "personrelation",
    "phoneindex",
    "demand",
    "assignmentevent",
    "offeringassignmentevent",
    "cooperation",
    "visit",
    "followup",
    "notification",
]
TARGETS = {
    "personrelation": [("person", "core_person"), ("membership", "core_membership")],
    "phoneindex": [("person", "core_person")],
    "demand": [
        ("person", "core_person"),
        ("introducer", "core_membership"),
        ("assignee", "core_membership"),
    ],
    "assignmentevent": [
        ("demand", "crm_demand"),
        ("previous", "core_membership"),
        ("assignee", "core_membership"),
        ("actor", "core_membership"),
    ],
    "offeringassignmentevent": [
        ("offering", "core_offering"),
        ("previous", "core_membership"),
        ("assignee", "core_membership"),
        ("actor", "core_membership"),
    ],
    "cooperation": [
        ("demand", "crm_demand"),
        ("offering", "core_offering"),
        ("requested_by", "core_membership"),
        ("supplier", "core_membership"),
    ],
    "visit": [("cooperation", "crm_cooperation")],
    "followup": [("cooperation", "crm_cooperation"), ("author", "core_membership")],
    "notification": [("recipient", "core_membership")],
}
for table in TABLES:
    SQL.append(
        f"ALTER TABLE crm_{table} ADD CONSTRAINT crm_{table}_scope_fk FOREIGN KEY (office_id,organization_id) REFERENCES core_office(id,organization_id);"
    )
    for field, target in TARGETS[table]:
        SQL.append(
            f"ALTER TABLE crm_{table} ADD CONSTRAINT crm_{table}_{field}_scope_fk FOREIGN KEY ({field}_id,office_id,organization_id) REFERENCES {target}(id,office_id,organization_id);"
        )
for table in ["assignmentevent", "offeringassignmentevent"]:
    SQL.append(
        f"CREATE TRIGGER crm_{table}_append_only BEFORE UPDATE OR DELETE ON crm_{table} FOR EACH ROW EXECUTE FUNCTION estate_reject_audit_mutation();"
    )
for table, fields in [
    ("demand", ["person_id", "introducer_id", "office_id", "organization_id"]),
    (
        "cooperation",
        [
            "demand_id",
            "offering_id",
            "requested_by_id",
            "supplier_id",
            "office_id",
            "organization_id",
        ],
    ),
    ("visit", ["cooperation_id", "office_id", "organization_id"]),
    ("followup", ["cooperation_id", "author_id", "office_id", "organization_id"]),
]:
    checks = " OR ".join(f"NEW.{f} IS DISTINCT FROM OLD.{f}" for f in fields)
    SQL.append(f"""CREATE FUNCTION crm_{table}_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF {checks} THEN RAISE EXCEPTION 'Historical identity is immutable'; END IF; RETURN NEW; END; $$;
 CREATE TRIGGER crm_{table}_identity BEFORE UPDATE ON crm_{table} FOR EACH ROW EXECUTE FUNCTION crm_{table}_identity_guard();""")
SQL.append("""CREATE FUNCTION crm_supplier_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM core_offering WHERE id=NEW.offering_id AND introducer_id=NEW.supplier_id AND office_id=NEW.office_id AND organization_id=NEW.organization_id) THEN RAISE EXCEPTION 'Supplier must be historical offering introducer'; END IF; RETURN NEW; END; $$;
 CREATE TRIGGER crm_supplier_guard BEFORE INSERT ON crm_cooperation FOR EACH ROW EXECUTE FUNCTION crm_supplier_guard();
 ALTER TABLE crm_demand ADD CONSTRAINT crm_districts_array CHECK (jsonb_typeof(districts)='array' AND jsonb_array_length(districts)<=30);
""")


class Migration(migrations.Migration):
    dependencies = [("crm", "0002_offeringassignmentevent")]
    operations = [migrations.RunSQL("\n".join(SQL))]
