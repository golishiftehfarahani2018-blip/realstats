from django.db import migrations

SQL = []
for table, field, target in [
    ("cooperationhistory", "cooperation", "crm_cooperation"),
    ("visithistory", "visit", "crm_visit"),
]:
    SQL.append(f"""ALTER TABLE crm_{table} ADD CONSTRAINT crm_{table}_office_scope FOREIGN KEY (office_id,organization_id) REFERENCES core_office(id,organization_id);
 ALTER TABLE crm_{table} ADD CONSTRAINT crm_{table}_actor_scope FOREIGN KEY (actor_id,office_id,organization_id) REFERENCES core_membership(id,office_id,organization_id);
 ALTER TABLE crm_{table} ADD CONSTRAINT crm_{table}_record_scope FOREIGN KEY ({field}_id,office_id,organization_id) REFERENCES {target}(id,office_id,organization_id);
 CREATE TRIGGER crm_{table}_append_only BEFORE UPDATE OR DELETE ON crm_{table} FOR EACH ROW EXECUTE FUNCTION estate_reject_audit_mutation();""")


class Migration(migrations.Migration):
    dependencies = [("crm", "0005_cooperationhistory_visithistory")]
    operations = [migrations.RunSQL("\n".join(SQL))]
