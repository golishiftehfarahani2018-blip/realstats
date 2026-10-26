import hashlib
import re
from datetime import timedelta
from django.db import transaction, IntegrityError
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoError
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.db.models import Q, F
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError, Throttled
from drf_spectacular.utils import extend_schema
from core.views import member, checked
from core import services as core
from core.models import Office, Offering, Membership, LoginAttempt
from core.serializers import OfferingQuery
from . import serializers as inp, finance
from .models import OfficeSettings, OfferingRevision, Publication, Customer, CustomerRequest, Favorite, Deal


def fetch(qs,pk):
    try:return qs.get(pk=pk)
    except qs.model.DoesNotExist:raise NotFound()


def public_row(p):
    return {'id':str(p.id),'office':str(p.office_id),'office_name':p.office.name,'images':[str(x.id) for x in p.publicimage_set.all()],**p.snapshot}


def active_publications():
    return Publication.objects.select_related('office').filter(published=True,consent=True,office__active=True,offering__status='approved')


class SettingsView(APIView):
    @extend_schema(responses=dict)
    def get(self,request):
        m=member(request);core.manager(m)
        obj,_=OfficeSettings.objects.get_or_create(office=m.office)
        return Response({'version':obj.version,'name':m.office.name,'city':m.office.city,'response_hours':obj.response_hours,'color':m.office.branding.get('color','#17685c')})
    @extend_schema(request=inp.SettingsInput,responses=dict)
    @transaction.atomic
    def put(self,request):
        m=member(request);core.manager(m);d=checked(inp.SettingsInput,request.data)
        obj,_=OfficeSettings.objects.get_or_create(office=m.office)
        obj=OfficeSettings.objects.select_for_update().get(pk=obj.pk)
        if obj.version!=d['version']:raise core.Conflict()
        office=Office.objects.select_for_update().get(pk=m.office_id)
        office.name=d['name'];office.city=d['city'];office.branding={**office.branding,'color':d['color']};office.save()
        obj.response_hours=d['response_hours'];obj.version+=1;obj.save();core.audit(m,'office.settings',office.id)
        return Response({'ok':True,'version':obj.version})


class RevisionsView(APIView):
    @extend_schema(responses=dict)
    def get(self,request,pk):
        m=member(request);o=core.get_offering(m,pk)
        if not core.private_allowed(m,o) and m.role!='senior':raise PermissionDenied()
        return Response([{'id':str(x.id),'base_version':x.base_version,'changes':x.changes,'state':x.state,'reason':x.reason,
                          'can_review':m.role in ['manager','senior'] and x.author_id!=m.id and x.state=='submitted'}
                         for x in OfferingRevision.objects.filter(offering=o).order_by('-created_at')[:100]])
    @extend_schema(request=inp.RevisionInput,responses=dict)
    @transaction.atomic
    def post(self,request,pk):
        m=member(request);o=core.get_offering(m,pk,True);d=checked(inp.RevisionInput,request.data)
        if not core.private_allowed(m,o):raise PermissionDenied()
        if o.status!='approved' or o.version!=d['base_version']:raise core.Conflict()
        if OfferingRevision.objects.filter(offering=o,state='submitted').exists():raise core.Conflict('بازنگری در انتظار بررسی وجود دارد.')
        obj=OfferingRevision.objects.create(**finance.scope(m),offering=o,author=m,base_version=o.version,changes=d['changes'])
        core.audit(m,'revision.submit',o.id)
        return Response({'id':str(obj.id)},status=201)


class RevisionReview(APIView):
    @extend_schema(request=inp.ReviewRevision,responses=dict)
    @transaction.atomic
    def post(self,request,pk):
        m=member(request);d=checked(inp.ReviewRevision,request.data)
        # Always lock offering before revision, matching revision creation order.
        obj=fetch(OfferingRevision.objects.filter(**finance.scope(m)),pk)
        o=core.get_offering(m,obj.offering_id,True)
        obj=OfferingRevision.objects.select_for_update().get(pk=pk)
        if m.role not in ['manager','senior'] or obj.author_id==m.id:raise PermissionDenied()
        if obj.state!='submitted' or o.status!='approved' or o.version!=obj.base_version:raise core.Conflict()
        if d['decision']=='approved':
            prop=type(o.property).objects.select_for_update().get(pk=o.property_id)
            if set(obj.changes)&{'kind','district','area','details'} and Offering.objects.filter(property=prop).exclude(pk=o.pk).exists():raise core.Conflict('ملک مشترک چند عرضه نیازمند بازنگری مستقل مشخصات است.')
            for k,v in obj.changes.items():
                if k in ['kind','district','area','details']:setattr(prop,k,{**prop.details,**v} if k=='details' else v)
                else:setattr(o,k,v)
            prop.save();o.version+=1;o.save();core.price_history(m,o)
            Publication.objects.filter(offering=o).update(published=False,version=F('version')+1)
        obj.state=d['decision'];obj.reason=d['reason'];obj.reviewer=m;obj.save()
        core.audit(m,'revision.'+d['decision'],o.id)
        return Response({'ok':True})


class PublicationView(APIView):
    @extend_schema(responses=dict)
    def get(self,request,pk):
        m=member(request);o=core.get_offering(m,pk)
        p=Publication.objects.filter(offering=o).first()
        return Response({'version':p.version if p else 0,'consent':p.consent if p else False,'published':p.published if p else False,'image_count':p.publicimage_set.count() if p else 0})
    @extend_schema(request=inp.PublishInput,responses=dict)
    @transaction.atomic
    def post(self,request,pk):
        m=member(request);o=core.get_offering(m,pk,True);d=checked(inp.PublishInput,request.data)
        if not core.private_allowed(m,o):raise PermissionDenied()
        p=Publication.objects.filter(offering=o).first()
        if not p:
            if d['version']!=1:raise core.Conflict()
            p=Publication.objects.create(**finance.scope(m),offering=o,version=1)
        elif p.version!=d['version']:raise core.Conflict()
        if d['action']=='consent':
            if not d.get('reference'):raise ValidationError('مرجع رضایت عرضه‌کننده الزامی است.')
            p.consent=True;p.consent_reference=d['reference'];p.consent_by=m;p.consent_at=timezone.now()
        elif d['action']=='revoke':p.consent=False;p.published=False
        elif d['action']=='stop':p.published=False
        else:
            core.manager(m)
            if not p.consent or o.status!='approved' or not d['content_reviewed']:raise core.Conflict('رضایت، تأیید عرضه و بازبینی محتوای عمومی الزامی است.')
            # No free-form private or owner fields are copied; district must be reviewed.
            if re.search(r'[0-9۰-۹٠-٩]{5,}',o.property.district):raise ValidationError('محله ممکن است حاوی شماره یا نشانی خصوصی باشد.')
            p.snapshot={key:value for key,value in core.summary(o,m).items() if key in ['kind','district','area','transaction','price_toman','deposit_toman','rent_toman','currency','details','negotiable_price']}
            p.source_version=o.version;p.published=True
        p.version+=1;p.save();core.audit(m,'publication.'+d['action'],o.id)
        return Response({'version':p.version,'consent':p.consent,'published':p.published})


class PublicList(APIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    @extend_schema(parameters=[OfferingQuery],responses=dict)
    def get(self,request):
        d=checked(OfferingQuery,request.query_params.dict());qs=active_publications()
        # Filter frozen approved values; never expose private record identifiers.
        for key in ['kind','transaction']:
            if key in d:qs=qs.filter(**{'snapshot__'+key:d[key]})
        if d.get('q'):qs=qs.filter(snapshot__district__icontains=d['q'])
        # JSON numeric strings need integer/decimal comparisons, performed on a bounded page-independent queryset.
        from django.db.models.functions import Cast
        from django.db.models.fields.json import KeyTextTransform
        from django.db.models import DecimalField
        for key,target in [('area','area'),('price','price_toman'),('deposit','deposit_toman'),('rent','rent_toman')]:
            if key+'_min' in d or key+'_max' in d:
                qs=qs.annotate(**{key+'_number':Cast(KeyTextTransform(target,'snapshot'),DecimalField(max_digits=22,decimal_places=2))})
                for suffix,op in [('min','gte'),('max','lte')]:
                    if key+'_'+suffix in d:qs=qs.filter(**{key+'_number__'+op:d[key+'_'+suffix]})
        if 'price_min' in d or 'price_max' in d:qs=qs.exclude(snapshot__negotiable_price=True)
        offset,limit=d['offset'],d['limit'];count=qs.count()
        return Response({'count':count,'has_more':offset+limit<count,'results':[public_row(x) for x in qs.order_by('-created_at','id')[offset:offset+limit]]})


def customer(request):
    c=Customer.objects.filter(pk=request.session.get('customer_id'),active=True,office__active=True).first() if request.session.get('customer_id') else None
    if not c or request.session.get('customer_epoch')!=c.epoch:raise PermissionDenied('ابتدا وارد حساب مشتری شوید.')
    return c


@method_decorator(csrf_protect,name='dispatch')
class CustomerSession(APIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    @extend_schema(responses=dict)
    def get(self,request,action=None,pk=None):
        c=customer(request)
        return Response({'username':c.username,'office':str(c.office_id)})
    @extend_schema(request=inp.CustomerAuth,responses=dict)
    def post(self,request,action):
        if action=='logout':
            request.session.pop('customer_id',None);request.session.pop('customer_epoch',None);request.session.cycle_key()
            return Response({'csrfToken':get_token(request._request)})
        if action not in ['register','login']:raise NotFound()
        d=checked(inp.CustomerAuth,request.data);office=fetch(Office.objects.filter(active=True),d['office'])
        key=hashlib.sha256(('customer|'+str(office.id)+'|'+request.META.get('REMOTE_ADDR','')+'|'+d['username']).encode()).hexdigest()
        with transaction.atomic():
            a,_=LoginAttempt.objects.get_or_create(key=key,defaults={'started_at':timezone.now()})
            a=LoginAttempt.objects.select_for_update().get(pk=key)
            if a.started_at<timezone.now()-timedelta(minutes=15):a.count=0;a.started_at=timezone.now()
            if a.count>=8:raise Throttled(wait=900)
            a.count+=1;a.save()
        if action=='register':
            try:validate_password(d['password'])
            except DjangoError as e:raise ValidationError({'password':e.messages})
            try:
                with transaction.atomic():c=Customer.objects.create(office=office,username=d['username'],password=make_password(d['password']))
            except IntegrityError:raise ValidationError('این نام کاربری قابل استفاده نیست.')
        else:
            c=Customer.objects.filter(office=office,username=d['username'],active=True).first()
            # Hash once even for unknown usernames to avoid a fast rejection path.
            if not c:
                check_password(d['password'],make_password('unavailable'));raise PermissionDenied('ورود نامعتبر است.')
            if not check_password(d['password'],c.password):raise PermissionDenied('ورود نامعتبر است.')
        request.session.cycle_key();request.session['customer_id']=str(c.id);request.session['customer_epoch']=c.epoch
        LoginAttempt.objects.filter(pk=key).delete()
        return Response({'ok':True,'csrfToken':get_token(request._request)})


@method_decorator(csrf_protect,name='dispatch')
class CustomerRequests(APIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    @extend_schema(responses=dict)
    def get(self,request,action=None,pk=None):
        c=customer(request)
        return Response([{'id':str(x.id),'publication':str(x.publication_id),'kind':x.kind,'status':x.status,'message':x.message,'created_at':x.created_at.isoformat()}
                         for x in CustomerRequest.objects.filter(customer=c).order_by('-created_at')[:100]])
    @extend_schema(request=inp.RequestInput,responses=dict)
    def post(self,request):
        c=customer(request);d=checked(inp.RequestInput,request.data)
        with transaction.atomic():
            p=fetch(active_publications().select_for_update(of=('self',)).filter(office=c.office),d['publication'])
            if CustomerRequest.objects.filter(customer=c,publication=p,status__in=['received','contacted'],kind=d['kind']).exists():raise core.Conflict('درخواست باز برای این آگهی دارید.')
            obj=CustomerRequest.objects.create(customer=c,publication=p,kind=d['kind'],message=d['message'])
        return Response({'id':str(obj.id),'status':obj.status},status=201)


@method_decorator(csrf_protect,name='dispatch')
class Favorites(APIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    @extend_schema(responses=dict)
    def get(self,request,action=None,pk=None):
        c=customer(request)
        return Response([public_row(x.publication) for x in Favorite.objects.select_related('publication__office').filter(customer=c,publication__in=active_publications()).order_by('-created_at')[:100]])
    @extend_schema(request=None,responses=dict)
    def post(self,request,pk):
        c=customer(request);p=fetch(active_publications().filter(office=c.office),pk)
        Favorite.objects.get_or_create(customer=c,publication=p);return Response({'ok':True})
    @extend_schema(responses=dict)
    def delete(self,request,pk):
        Favorite.objects.filter(customer=customer(request),publication_id=pk).delete();return Response({'ok':True})


class Inbox(APIView):
    @extend_schema(responses=dict)
    def get(self,request,pk=None):
        m=member(request);qs=CustomerRequest.objects.filter(publication__office=m.office,publication__organization=m.organization)
        if m.role!='manager':qs=qs.filter(publication__offering__introducer=m)
        core.audit(m,'customer.requests.view')
        return Response([{'id':str(x.id),'offering':str(x.publication.offering_id),'kind':x.kind,'message':x.message,'status':x.status,'version':x.version} for x in qs.select_related('publication').order_by('-created_at')[:100]])
    @extend_schema(request=inp.RequestChange,responses=dict)
    @transaction.atomic
    def patch(self,request,pk):
        m=member(request);d=checked(inp.RequestChange,request.data)
        qs=CustomerRequest.objects.filter(publication__office=m.office,publication__organization=m.organization)
        if m.role!='manager':qs=qs.filter(publication__offering__introducer=m)
        obj=fetch(qs.select_for_update(of=('self',)),pk)
        if obj.version!=d['version']:raise core.Conflict()
        obj.status=d['status'];obj.version+=1;obj.save();core.audit(m,'customer.request.update',obj.id)
        return Response({'ok':True})


class Members(APIView):
    @extend_schema(responses=dict)
    def get(self,request):
        m=member(request);core.manager(m)
        return Response([{'id':str(x.id),'name':x.user.first_name or x.user.username,'active':x.active} for x in Membership.objects.select_related('user').filter(**finance.scope(m)).order_by('created_at')])


class Deals(APIView):
    @extend_schema(responses=dict)
    def get(self,request):
        m=member(request);rows=[]
        # Benefit-scoped lookup before pagination, no unrelated totals disclosed.
        qs=Deal.objects.filter(**finance.scope(m))
        if m.role!='manager':
            from .models import Agreement
            ids=[x.deal_id for x in Agreement.objects.filter(**finance.scope(m),shares__contains=[{'beneficiary':str(m.id)}])]
            qs=qs.filter(id__in=ids)
        for obj in qs.order_by('-created_at')[:100]:
            try:rows.append(finance.output(m,obj))
            except NotFound:pass
        return Response(rows)
    @extend_schema(request=inp.CreateDeal,responses=dict)
    def post(self,request):return Response(finance.output(member(request),finance.create(member(request),checked(inp.CreateDeal,request.data))),status=201)


class DealAction(APIView):
    @extend_schema(operation_id="business_deal_action",request=dict,responses=dict)
    def post(self,request,pk,action):
        cls={'agreement':inp.AgreementInput,'receipt':inp.CashInput,'payout':inp.CashInput,'reverse':inp.ReverseInput,'cancel':inp.CancelInput,'vote':inp.VoteInput}.get(action)
        if not cls:raise NotFound()
        m=member(request);obj=finance.mutate(m,pk,action,checked(cls,request.data));return Response(finance.output(m,obj))


class PublicImages(APIView):
    @extend_schema(request=inp.PublicImageInput,responses=dict)
    @transaction.atomic
    def post(self,request,pk):
        import uuid
        from .models import PublicImage
        from core.storage import image_bytes, client, StorageUnavailable
        from django.conf import settings
        from botocore.exceptions import BotoCoreError, ClientError
        m=member(request);core.manager(m);d=checked(inp.PublicImageInput,request.data)
        o=core.get_offering(m,pk,True);p=Publication.objects.filter(offering=o).first()
        if not p or not p.consent or not d['content_reviewed']:raise core.Conflict('رضایت و بازبینی تصویر الزامی است.')
        if PublicImage.objects.filter(publication=p).count()>=10:raise ValidationError('حداکثر ۱۰ تصویر برای هر آگهی مجاز است.')
        content=image_bytes(d['file']);key='reviewed/'+str(uuid.uuid4())+'.jpg'
        try:client().put_object(Bucket=settings.S3_PUBLIC_BUCKET,Key=key,Body=content,ContentType='image/jpeg')
        except (BotoCoreError,ClientError):raise StorageUnavailable()
        obj=PublicImage.objects.create(**finance.scope(m),publication=p,storage_key=key,reviewer=m)
        core.audit(m,'publication.image.reviewed',o.id)
        return Response({'id':str(obj.id)},status=201)


class PublicImageDownload(APIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    @extend_schema(responses={(200,'image/jpeg'):bytes})
    def get(self,request,pk):
        from .models import PublicImage
        from core.storage import client, StorageUnavailable
        from django.conf import settings
        from django.http import HttpResponse
        from botocore.exceptions import BotoCoreError, ClientError
        photo=fetch(PublicImage.objects.filter(publication__in=active_publications()),pk)
        try:content=client().get_object(Bucket=settings.S3_PUBLIC_BUCKET,Key=photo.storage_key)['Body'].read()
        except (BotoCoreError,ClientError):raise StorageUnavailable()
        response=HttpResponse(content,content_type='image/jpeg');response['Content-Disposition']='inline';return response


class Invitations(APIView):
    @extend_schema(responses=dict)
    def get(self,request):
        from .models import Invitation
        m=member(request);core.manager(m)
        return Response([{'id':str(x.id),'expires_at':x.expires_at.isoformat(),'used':x.accepted_at is not None,'revoked':x.revoked} for x in Invitation.objects.filter(**finance.scope(m)).order_by('-created_at')[:100]])
    @extend_schema(request=None,responses=dict)
    def post(self,request):
        import secrets
        from .models import Invitation
        m=member(request);core.manager(m)
        token=secrets.token_urlsafe(40)
        obj=Invitation.objects.create(**finance.scope(m),creator=m,digest=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(hours=24))
        core.audit(m,'invitation.create',obj.id)
        return Response({'id':str(obj.id),'token':token,'expires_at':obj.expires_at.isoformat()},status=201)
    @extend_schema(responses=dict)
    def delete(self,request,pk):
        from .models import Invitation
        m=member(request);core.manager(m);obj=fetch(Invitation.objects.filter(**finance.scope(m)),pk)
        obj.revoked=True;obj.save();core.audit(m,'invitation.revoke',obj.id);return Response({'ok':True})


@method_decorator(csrf_protect,name='dispatch')
class AcceptInvitation(APIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    @extend_schema(request=inp.InviteAccept,responses=dict)
    @transaction.atomic
    def post(self,request):
        from .models import Invitation
        from core.models import User
        d=checked(inp.InviteAccept,request.data)
        obj=Invitation.objects.select_for_update().filter(digest=hashlib.sha256(d['token'].encode()).hexdigest(),revoked=False,accepted_at=None,expires_at__gt=timezone.now(),office__active=True,creator__active=True,creator__user__is_active=True).first()
        if not obj:raise ValidationError('دعوت معتبر نیست یا منقضی شده است.')
        try:validate_password(d['password'])
        except DjangoError as e:raise ValidationError({'password':e.messages})
        try:
            with transaction.atomic():user=User.objects.create_user(username=d['username'],first_name=d['name'],password=d['password'])
        except IntegrityError:raise ValidationError('نام کاربری قابل استفاده نیست.')
        m=Membership.objects.create(organization=obj.organization,office=obj.office,user=user,role='advisor')
        obj.accepted_at=timezone.now();obj.save();core.audit(obj.creator,'invitation.accept',m.id)
        return Response({'ok':True},status=201)


class Reports(APIView):
    @extend_schema(responses=dict)
    def get(self,request):
        from crm.models import Demand, Cooperation, Visit
        from .models import Ledger
        from django.db.models import Sum
        m=member(request);core.manager(m);scope=finance.scope(m)
        result={name:cls.objects.filter(**scope).count() for name,cls in [('offerings',Offering),('demands',Demand),('cooperations',Cooperation),('visits',Visit),('deals',Deal)]}
        result['approved']=Offering.objects.filter(**scope,status='approved').count()
        result['published']=Publication.objects.filter(**scope,published=True,consent=True).count()
        for label,kinds in [('receipts',['receipt','receipt_back']),('payouts',['payout','payout_back'])]:
            result[label]=str(Ledger.objects.filter(**scope,kind__in=kinds).aggregate(n=Sum('amount'))['n'] or 0)
        core.audit(m,'report.office');return Response(result)


class PublicOffices(APIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    @extend_schema(responses=dict)
    def get(self,request):
        return Response([{'id':str(x.id),'name':x.name} for x in Office.objects.filter(active=True,publication__isnull=False).distinct().order_by('created_at')[:100]])


class PublicDetail(APIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    @extend_schema(operation_id="public_listing_detail",responses=dict)
    def get(self,request,pk):return Response(public_row(fetch(active_publications(),pk)))
