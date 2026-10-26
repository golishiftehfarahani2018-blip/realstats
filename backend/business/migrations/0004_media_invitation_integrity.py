from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('business','0003_invitation_publicimage')]
 operations=[migrations.RunSQL('''
 ALTER TABLE business_publicimage ADD CONSTRAINT biz_photo_office FOREIGN KEY(office_id,organization_id) REFERENCES core_office(id,organization_id);
 ALTER TABLE business_publicimage ADD CONSTRAINT biz_photo_publication FOREIGN KEY(publication_id,office_id,organization_id) REFERENCES business_publication(id,office_id,organization_id);
 ALTER TABLE business_publicimage ADD CONSTRAINT biz_photo_reviewer FOREIGN KEY(reviewer_id,office_id,organization_id) REFERENCES core_membership(id,office_id,organization_id);
 ALTER TABLE business_invitation ADD CONSTRAINT biz_invite_office FOREIGN KEY(office_id,organization_id) REFERENCES core_office(id,organization_id);
 ALTER TABLE business_invitation ADD CONSTRAINT biz_invite_creator FOREIGN KEY(creator_id,office_id,organization_id) REFERENCES core_membership(id,office_id,organization_id);
 ''')]
