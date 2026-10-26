from django.db import migrations
SQL=[]
for table in ['deal','agreement','ledger','agreementvote','offeringrevision','publication']:
    SQL.append(f'ALTER TABLE business_{table} ADD CONSTRAINT biz_{table}_scope UNIQUE (id, office_id, organization_id);')
    SQL.append(f'ALTER TABLE business_{table} ADD CONSTRAINT biz_{table}_office FOREIGN KEY (office_id,organization_id) REFERENCES core_office(id,organization_id);')
for table,field,target in [
 ('deal','offering','core_offering'),('agreement','deal','business_deal'),
 ('ledger','deal','business_deal'),('ledger','agreement','business_agreement'),('ledger','actor','core_membership'),('ledger','beneficiary','core_membership'),
 ('agreementvote','agreement','business_agreement'),('agreementvote','actor','core_membership'),('agreementvote','beneficiary','core_membership'),
 ('offeringrevision','offering','core_offering'),('offeringrevision','author','core_membership'),('offeringrevision','reviewer','core_membership'),
 ('publication','offering','core_offering'),('publication','consent_by','core_membership')]:
 SQL.append(f'ALTER TABLE business_{table} ADD CONSTRAINT biz_{table}_{field}_fk FOREIGN KEY ({field}_id,office_id,organization_id) REFERENCES {target}(id,office_id,organization_id);')
for table in ['agreement','ledger','agreementvote']:
 SQL.append(f'CREATE TRIGGER biz_{table}_append_only BEFORE UPDATE OR DELETE ON business_{table} FOR EACH ROW EXECUTE FUNCTION estate_reject_audit_mutation();')
SQL.append('''CREATE FUNCTION business_ledger_agreement() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM business_agreement WHERE id=NEW.agreement_id AND deal_id=NEW.deal_id) THEN RAISE EXCEPTION 'Agreement belongs to another deal'; END IF;
 IF NEW.reversal_of_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM business_ledger WHERE id=NEW.reversal_of_id AND deal_id=NEW.deal_id AND kind IN ('receipt','payout') AND amount=-NEW.amount AND distributable=-NEW.distributable AND beneficiary_id IS NOT DISTINCT FROM NEW.beneficiary_id) THEN RAISE EXCEPTION 'Invalid reversal'; END IF;
 RETURN NEW; END; $$;
 CREATE TRIGGER biz_ledger_agreement BEFORE INSERT ON business_ledger FOR EACH ROW EXECUTE FUNCTION business_ledger_agreement();
 ALTER TABLE business_ledger ADD CONSTRAINT biz_ledger_kind CHECK(kind IN ('receipt','payout','receipt_back','payout_back'));
 ALTER TABLE business_ledger ADD CONSTRAINT biz_ledger_sign CHECK((kind IN ('receipt','payout') AND amount>0 AND distributable>=0) OR (kind IN ('receipt_back','payout_back') AND amount<0 AND distributable<=0));
 CREATE FUNCTION business_customer_scope() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM business_customer c JOIN business_publication p ON p.office_id=c.office_id WHERE c.id=NEW.customer_id AND p.id=NEW.publication_id) THEN RAISE EXCEPTION 'Customer office mismatch'; END IF;
 RETURN NEW; END; $$;
 CREATE TRIGGER biz_request_scope BEFORE INSERT OR UPDATE ON business_customerrequest FOR EACH ROW EXECUTE FUNCTION business_customer_scope();
 CREATE TRIGGER biz_favorite_scope BEFORE INSERT OR UPDATE ON business_favorite FOR EACH ROW EXECUTE FUNCTION business_customer_scope();
 ALTER TABLE business_offeringrevision ADD CONSTRAINT biz_revision_state CHECK(state IN ('submitted','approved','rejected'));
 ALTER TABLE business_deal ADD CONSTRAINT biz_deal_state CHECK(state IN ('open','cancelled'));
 ALTER TABLE business_agreementvote ADD CONSTRAINT biz_vote_decision CHECK(decision IN ('accepted','disputed','resolved'));
 ALTER TABLE business_customerrequest ADD CONSTRAINT biz_request_state CHECK(status IN ('received','contacted','closed'));
''')
class Migration(migrations.Migration):
 dependencies=[('business','0001_initial')]
 operations=[migrations.RunSQL('\n'.join(SQL))]
