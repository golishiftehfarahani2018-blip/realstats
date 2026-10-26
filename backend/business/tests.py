import secrets
import uuid
from django.test import TestCase, SimpleTestCase
from django.db import transaction, DatabaseError, IntegrityError
from rest_framework.test import APIClient
from core.tests import SecurityFlowTests
from core.models import Offering, Membership, Office
from . import finance
from .models import Agreement, Ledger, Publication, CustomerRequest, Customer, AgreementVote


class Rules(SimpleTestCase):
    def test_rounding_stable_and_exact(self):
        self.assertEqual(finance.allocate(101,{'office':5000,'a':3000,'b':2000}),{'office':51,'a':30,'b':20})
        self.assertEqual(finance.allocate(1,{'b':1,'a':1}),{'a':1,'b':0})
        self.assertEqual(finance.allocate(0,{'office':0}),{'office':0})
        for total in range(120):
            self.assertEqual(sum(finance.allocate(total,{'a':3,'b':5,'c':7}).values()),total)

    def test_negotiable_price_is_not_a_confirmed_budget_match(self):
        from types import SimpleNamespace as S
        from crm.matching import evaluate
        demand=S(kind='apartment',transaction='sale',area_min=80,area_max=100,budget_min_toman=0,budget_max_toman=100,districts=[])
        offering=S(property=S(kind='apartment',area=90,district='نمونه'),transaction='sale',price_toman=0,negotiable_price=True)
        result=evaluate(demand,offering)
        self.assertFalse(result['eligible'])
        self.assertFalse(next(x for x in result['reasons'] if x['criterion']=='budget')['matched'])


class BusinessFlow(TestCase):
    @classmethod
    def setUpTestData(cls):SecurityFlowTests.setUpTestData.__func__(cls)
    payload=SecurityFlowTests.payload
    create=SecurityFlowTests.create
    approve=SecurityFlowTests.approve
    client_for=SecurityFlowTests.client_for

    def setup_deal(self):
        self.o=self.approve(self.create())
        self.deal=finance.create(self.manager,{'offering':self.o.id,'amount':1000})
        self.d={'version':1,'fee':101,'deductions':[],'mode':'percent','shares':[{'beneficiary':'office','value':5000},{'beneficiary':str(self.first.id),'value':3000},{'beneficiary':str(self.second.id),'value':2000}],'reason':'توافق آزمایشی'}
        finance.mutate(self.manager,self.deal.id,'agreement',self.d)
        self.deal.refresh_from_db()
        return self.deal

    def act(self,action,**d):
        self.deal.refresh_from_db()
        return finance.mutate(self.manager,self.deal.id,action,{'version':self.deal.version,**d})

    def test_financial_receipt_vote_payment_idempotence_and_reversal(self):
        self.setup_deal();a=Agreement.objects.get(deal=self.deal)
        finance.mutate(self.first,self.deal.id,'vote',{'agreement':a.id,'decision':'accepted','reason':''})
        self.act('receipt',operation=uuid.uuid4(),amount=60,distributable=50,reference='bank')
        row=next(x for x in finance.output(self.manager,self.deal)['shares'] if x['beneficiary']==str(self.first.id))
        op=uuid.uuid4();payload={'operation':op,'amount':int(row['payable']),'beneficiary':str(self.first.id),'reference':'bank','distributable':0}
        self.act('payout',**payload)
        version=DealVersion(self.deal)
        self.act('payout',**payload)
        self.assertEqual(Ledger.objects.filter(operation=op).count(),1)
        self.assertEqual(DealVersion(self.deal),version)
        with self.assertRaises(finance.Conflict):self.act('payout',**{**payload,'amount':100})
        entry=Ledger.objects.get(operation=op)
        self.act('reverse',operation=uuid.uuid4(),entry=entry.id,reason='اصلاح')
        self.assertEqual(Ledger.objects.filter(kind='payout_back').get().amount,-entry.amount)
        with self.assertRaises(finance.Conflict):self.act('reverse',operation=uuid.uuid4(),entry=entry.id,reason='تکرار')
        row=next(x for x in finance.output(self.first,self.deal)['shares'] if x['beneficiary']==str(self.first.id))
        self.assertEqual(row['paid'],'0')

    def test_dispute_blocks_payment_and_requires_manager_resolution(self):
        self.setup_deal();a=Agreement.objects.get(deal=self.deal)
        finance.mutate(self.first,self.deal.id,'vote',{'agreement':a.id,'decision':'disputed','reason':'اختلاف'})
        self.act('receipt',operation=uuid.uuid4(),amount=101,distributable=101,reference='bank')
        with self.assertRaises(finance.Conflict):self.act('payout',operation=uuid.uuid4(),amount=1,beneficiary=str(self.first.id),distributable=0,reference='bank')
        with self.assertRaises(finance.Conflict):finance.mutate(self.first,self.deal.id,'vote',{'agreement':a.id,'decision':'accepted','reason':''})
        finance.mutate(self.manager,self.deal.id,'vote',{'agreement':a.id,'beneficiary':self.first.id,'decision':'resolved','reason':'حل اختلاف'})
        self.act('payout',operation=uuid.uuid4(),amount=30,beneficiary=str(self.first.id),distributable=0,reference='bank')

    def test_receipt_reversal_creates_recoverable_without_deleting_payout(self):
        self.setup_deal()
        op=uuid.uuid4();self.act('receipt',operation=op,amount=101,distributable=101,reference='bank')
        self.act('payout',operation=uuid.uuid4(),amount=51,beneficiary='office',distributable=0,reference='bank')
        self.act('cancel',reason='لغو')
        self.act('reverse',operation=uuid.uuid4(),entry=Ledger.objects.get(operation=op).id,reason='برگشت')
        row=next(x for x in finance.output(self.manager,self.deal)['shares'] if x['beneficiary']=='office')
        self.assertEqual(row['recoverable'],'51');self.assertEqual(row['paid'],'51')

    def test_financial_scope_version_and_immutable_history(self):
        self.setup_deal()
        for actor in [self.first,self.other]:
            with self.assertRaises((finance.PermissionDenied,finance.NotFound)):
                finance.mutate(actor,self.deal.id,'receipt',{'version':2,'operation':uuid.uuid4(),'amount':10,'distributable':10,'reference':'bank'})
        with self.assertRaises(finance.Conflict):finance.mutate(self.manager,self.deal.id,'agreement',self.d)
        with self.assertRaises(DatabaseError),transaction.atomic():Agreement.objects.filter(deal=self.deal).update(basis=0)
        self.act('receipt',operation=uuid.uuid4(),amount=10,distributable=10,reference='bank')
        with self.assertRaises(DatabaseError),transaction.atomic():Ledger.objects.filter(deal=self.deal).delete()
        out=finance.output(self.first,self.deal)
        self.assertNotIn('fee',out);self.assertNotIn('ledger',out);self.assertEqual(len(out['shares']),1)
        with self.assertRaises(finance.NotFound):finance.output(self.third,self.deal)

    def test_invalid_agreements_and_zero_basis(self):
        self.setup_deal()
        for changes in [{'shares':[{'beneficiary':'office','value':11000}]},{'deductions':[{'title':'کسر','amount':102}]},{'shares':[{'beneficiary':str(self.other.id),'value':10000},{'beneficiary':'office','value':0}]}]:
            with self.assertRaises(finance.ValidationError):self.act('agreement',**{k:v for k,v in {**self.d,**changes}.items() if k!='version'})
        self.act('agreement',fee=0,deductions=[],mode='fixed',shares=[{'beneficiary':'office','value':0},{'beneficiary':str(self.first.id),'value':0},{'beneficiary':str(self.second.id),'value':0}],reason='صفر')
        self.assertEqual(finance.output(self.manager,self.deal)['shares'][0]['payable'],'0')

    def publish(self):
        self.o=self.approve(self.create());c=self.client_for(self.first,True)
        url=f'/api/v1/offerings/{self.o.id}/publication'
        r=c.post(url,{'version':1,'action':'consent','reference':'اجازه عرضه‌کننده'},format='json');self.assertEqual(r.status_code,200,r.content)
        m=self.client_for(self.manager,True);r=m.post(url,{'version':r.json()['version'],'action':'publish','content_reviewed':True},format='json');self.assertEqual(r.status_code,200,r.content)
        self.pub=Publication.objects.get(offering=self.o)
        return c,m,url

    def test_public_snapshot_and_immediate_revocation(self):
        c,m,url=self.publish();anon=APIClient()
        result=anon.get('/api/v1/public/listings').json()
        self.assertEqual(result['count'],1)
        for key in ['SECRET_ADDRESS_771','PRIVATE_OWNER','09123456789',str(self.o.id),str(self.first.id)]:self.assertNotIn(key,str(result))
        self.assertEqual(anon.get('/api/v1/public/listings?q=نمونه').json()['count'],1)
        self.assertEqual(anon.get('/api/v1/public/listings?transaction=sale&price_max=6000000000&area_min=80').json()['count'],1)
        self.assertEqual(anon.get('/api/v1/public/listings?transaction=sale&price_max=1').json()['count'],0)
        r=c.post(url,{'version':self.pub.version,'action':'revoke'},format='json');self.assertEqual(r.status_code,200)
        self.assertEqual(anon.get('/api/v1/public/listings').json()['count'],0)
        self.assertEqual(anon.get('/api/v1/public/listings/'+str(self.pub.id)).status_code,404)
        self.assertIn(str(self.office.id),[x['id'] for x in anon.get('/api/v1/public/offices').json()])

    def test_publish_requires_consent_review_and_authority(self):
        o=self.approve(self.create());url=f'/api/v1/offerings/{o.id}/publication'
        for member in [self.second,self.senior]:
            self.assertEqual(self.client_for(member,True).post(url,{'version':1,'action':'consent','reference':'test'},format='json').status_code,403)
        self.assertEqual(self.client_for(self.manager,True).post(url,{'version':1,'action':'publish','content_reviewed':True},format='json').status_code,409)
        self.assertEqual(Publication.objects.count(),0)

    def test_revision_requires_independent_review_and_stops_publication(self):
        c,m,url=self.publish()
        r=c.post(f'/api/v1/offerings/{self.o.id}/revisions',{'base_version':self.o.version,'changes':{'version':self.o.version,'price_toman':'600'}},format='json')
        self.assertEqual(r.status_code,201,r.content);pk=r.json()['id']
        self.assertEqual(c.post(f'/api/v1/revisions/{pk}/review',{'decision':'approved','reason':'x'},format='json').status_code,403)
        r=m.post(f'/api/v1/revisions/{pk}/review',{'decision':'approved','reason':'بررسی'},format='json');self.assertEqual(r.status_code,200,r.content)
        self.o.refresh_from_db();self.pub.refresh_from_db();self.assertEqual(self.o.price_toman,600);self.assertFalse(self.pub.published)
        self.assertEqual(m.post(f'/api/v1/revisions/{pk}/review',{'decision':'approved','reason':'x'},format='json').status_code,409)

    def test_customer_sessions_csrf_requests_favorites_and_scope(self):
        _,m,_=self.publish();password=secrets.token_urlsafe(20)
        def account(username):
            c=APIClient(enforce_csrf_checks=True);token=c.get('/api/v1/auth/csrf').json()['csrfToken']
            r=c.post('/api/v1/customer/auth/register',{'office':str(self.office.id),'username':username,'password':password},format='json',HTTP_X_CSRFTOKEN=token)
            self.assertEqual(r.status_code,200,r.content);c.credentials(HTTP_X_CSRFTOKEN=r.json()['csrfToken']);return c
        a=account('clienta');b=account('clientb')
        body={'publication':str(self.pub.id),'kind':'visit','message':'شماره خود مشتری خصوصی'}
        self.assertEqual(a.post('/api/v1/customer/requests',body,format='json').status_code,201)
        self.assertEqual(a.post('/api/v1/customer/requests',body,format='json').status_code,409)
        self.assertEqual(len(a.get('/api/v1/customer/requests').json()),1);self.assertEqual(b.get('/api/v1/customer/requests').json(),[])
        self.assertEqual(a.get('/api/v1/finance/deals').status_code,403)
        self.assertEqual(a.post(f'/api/v1/customer/favorites/{self.pub.id}',{},format='json').status_code,200)
        self.assertEqual(len(a.get('/api/v1/customer/favorites').json()),1)
        self.assertEqual(b.get('/api/v1/customer/favorites').json(),[])
        csrf=APIClient(enforce_csrf_checks=True)
        self.assertEqual(csrf.post('/api/v1/customer/auth/login',{'office':str(self.office.id),'username':'clienta','password':password},format='json').status_code,403)
        self.assertEqual(len(m.get('/api/v1/customer-inbox').json()),1)
        self.assertEqual(self.client_for(self.second).get('/api/v1/customer-inbox').json(),[])
        obj=Customer.objects.get(username='clienta');obj.active=False;obj.save()
        self.assertEqual(a.get('/api/v1/customer/requests').status_code,403)

    def test_office_settings_version_and_authority(self):
        c=self.client_for(self.manager,True);initial=c.get('/api/v1/settings/office').json()
        payload={'version':initial['version'],'name':'دفتر آزمایش','city':'تهران','color':'#17685c'}
        self.assertEqual(c.put('/api/v1/settings/office',payload,format='json').status_code,200)
        self.assertEqual(c.put('/api/v1/settings/office',payload,format='json').status_code,409)
        self.assertEqual(self.client_for(self.first).get('/api/v1/settings/office').status_code,403)


def DealVersion(deal):
    deal.refresh_from_db();return deal.version

class AdditionalFlows(TestCase):
    setUpTestData = classmethod(BusinessFlow.setUpTestData.__func__)
    payload=BusinessFlow.payload
    create=BusinessFlow.create
    approve=BusinessFlow.approve
    client_for=BusinessFlow.client_for
    publish=BusinessFlow.publish
    # Reuse fixture helpers without re-running inherited test methods below.
    def test_invitation_single_use_csrf_scope_and_fixed_role(self):
        manager=self.client_for(self.manager,True)
        r=manager.post('/api/v1/invitations',{},format='json');self.assertEqual(r.status_code,201)
        token=r.json()['token'];self.assertNotIn(token,str(manager.get('/api/v1/invitations').json()))
        client=APIClient(enforce_csrf_checks=True);csrf=client.get('/api/v1/auth/csrf').json()['csrfToken']
        payload={'token':token,'username':'invited_advisor','name':'همکار','password':secrets.token_urlsafe(20)}
        self.assertEqual(client.post('/api/v1/public/accept-invitation',payload,format='json').status_code,403)
        r=client.post('/api/v1/public/accept-invitation',payload,format='json',HTTP_X_CSRFTOKEN=csrf);self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(Membership.objects.get(user__username='invited_advisor').role,'advisor')
        self.assertEqual(client.post('/api/v1/public/accept-invitation',payload,format='json',HTTP_X_CSRFTOKEN=csrf).status_code,400)
        self.assertEqual(self.client_for(self.first).get('/api/v1/reports/office').status_code,403)
        self.assertIn('payouts',manager.get('/api/v1/reports/office').json())

    def test_public_photo_private_until_publication_and_revoked_after_consent(self):
        import os
        if os.getenv('RUN_STORAGE_TESTS')!='1':self.skipTest('Requires real S3')
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.conf import settings
        from core.storage import client
        from .models import PublicImage
        _,manager,url=self.publish()
        data=BytesIO();img=Image.new('RGB',(20,20),'white');exif=Image.Exif();exif[270]='private metadata';img.save(data,'JPEG',exif=exif)
        r=manager.post(f'/api/v1/offerings/{self.o.id}/public-images',{'file':SimpleUploadedFile('photo.jpg',data.getvalue(),content_type='image/jpeg'),'content_reviewed':'true'},format='multipart')
        self.assertEqual(r.status_code,201,r.content);photo=PublicImage.objects.get(pk=r.json()['id'])
        try:
            anonymous=APIClient();r=anonymous.get('/api/v1/public/images/'+str(photo.id));self.assertEqual(r.status_code,200)
            self.assertFalse(Image.open(BytesIO(r.content)).getexif());self.assertIn('no-store',r['Cache-Control'])
            self.pub.refresh_from_db();self.assertEqual(manager.post(url,{'version':self.pub.version,'action':'revoke'},format='json').status_code,200)
            self.assertEqual(anonymous.get('/api/v1/public/images/'+str(photo.id)).status_code,404)
        finally:client().delete_object(Bucket=settings.S3_PUBLIC_BUCKET,Key=photo.storage_key)


class ReminderTests(TestCase):
    setUpTestData = classmethod(BusinessFlow.setUpTestData.__func__)
    payload=BusinessFlow.payload
    create=BusinessFlow.create
    approve=BusinessFlow.approve

    def test_due_reminders_idempotent_and_no_private_payload(self):
        from datetime import timedelta
        from django.utils import timezone
        from crm import services
        from crm.models import Notification
        from business.reminders import run
        o=self.approve(self.create())
        d=services.create_demand(self.second,{'name':'ساختگی','phone':'09900000111','kind':'apartment','transaction':'sale','districts':[], 'area_min':80,'area_max':100,'budget_min_toman':0,'budget_max_toman':6000000000})
        c,_=services.request_cooperation(self.second,{'demand_id':str(d.id),'offering_id':str(o.id)})
        c=services.decide_cooperation(self.first,c.id,{'version':c.version,'decision':'accepted'})
        services.create_followup(self.second,{'cooperation_id':str(c.id),'kind':'task','body':'محرمانه','due_at':(timezone.now()-timedelta(hours=1)).isoformat()})
        self.assertEqual(run(),1);self.assertEqual(run(),0)
        n=Notification.objects.get(event_code='followup.due')
        self.assertEqual(n.recipient_id,self.second.id)
        self.assertNotIn('محرمانه',str(n.__dict__))

from django.test import TransactionTestCase

class FinanceConcurrency(TransactionTestCase):
    payload=BusinessFlow.payload
    create=BusinessFlow.create
    approve=BusinessFlow.approve
    setup_deal=BusinessFlow.setup_deal
    def setUp(self):BusinessFlow.setUpTestData.__func__(type(self))
    def test_concurrent_receipts_using_one_version_have_one_winner(self):
        import threading
        from django.db import connections, close_old_connections
        self.setup_deal();pk=self.deal.id;member_id=self.manager.id
        barrier=threading.Barrier(2);results=[]
        def attempt():
            close_old_connections()
            try:
                m=Membership.objects.get(pk=member_id);barrier.wait(timeout=10)
                finance.mutate(m,pk,'receipt',{'version':2,'operation':uuid.uuid4(),'amount':50,'distributable':50,'reference':'concurrency test'})
                results.append('ok')
            except finance.Conflict:results.append('conflict')
            except Exception as exc:results.append(type(exc).__name__)
            finally:connections.close_all()
        threads=[threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=20)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertCountEqual(results,['ok','conflict'])
        self.assertEqual(Ledger.objects.filter(deal_id=pk).count(),1)
