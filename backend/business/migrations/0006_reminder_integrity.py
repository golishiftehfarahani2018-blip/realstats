from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('business','0005_officesettings_response_hours_remindersent'),('crm','0008_remove_notification_crm_safe_notification_code_and_more')]
 operations=[migrations.RunSQL('''
 ALTER TABLE business_remindersent ADD CONSTRAINT biz_reminder_office FOREIGN KEY(office_id,organization_id) REFERENCES core_office(id,organization_id);
 ALTER TABLE business_remindersent ADD CONSTRAINT biz_reminder_recipient FOREIGN KEY(recipient_id,office_id,organization_id) REFERENCES core_membership(id,office_id,organization_id);
 CREATE TRIGGER biz_reminder_append_only BEFORE UPDATE OR DELETE ON business_remindersent FOR EACH ROW EXECUTE FUNCTION estate_reject_audit_mutation();
 CREATE FUNCTION business_revision_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF OLD.state <> 'submitted' OR NEW.author_id IS DISTINCT FROM OLD.author_id OR NEW.offering_id IS DISTINCT FROM OLD.offering_id OR NEW.changes IS DISTINCT FROM OLD.changes OR NEW.base_version IS DISTINCT FROM OLD.base_version OR NEW.office_id IS DISTINCT FROM OLD.office_id OR NEW.organization_id IS DISTINCT FROM OLD.organization_id THEN RAISE EXCEPTION 'Revision content is immutable'; END IF; RETURN NEW; END; $$;
 CREATE TRIGGER biz_revision_immutable BEFORE UPDATE ON business_offeringrevision FOR EACH ROW EXECUTE FUNCTION business_revision_immutable();
 ''')]
