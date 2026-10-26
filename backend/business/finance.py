"""Explicit approvals; integer money; immutable agreements and ledger entries."""
import hashlib
import json
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Sum, Q
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from core.services import manager, audit, get_offering, Conflict
from core.models import Membership
from .models import Deal, Agreement, Ledger, AgreementVote


def scope(m):
    return {'organization_id':m.organization_id,'office_id':m.office_id}


def allocate(total, weights):
    """Largest remainder with stable beneficiary identifiers; no float arithmetic."""
    denominator = sum(weights.values())
    if not denominator:
        if total: raise ValidationError('مبنای تقسیم نامعتبر است.')
        return {key:0 for key in weights}
    result = {key:total*weight//denominator for key,weight in weights.items()}
    order = sorted(weights, key=lambda key:(-(total*weights[key]%denominator),key))
    for key in order[:total-sum(result.values())]: result[key] += 1
    return result


def current(deal):
    agreement = Agreement.objects.filter(deal=deal).order_by('-sequence').first()
    if not agreement: raise Conflict('ابتدا توافق سهم را ثبت کنید.')
    return agreement


def state(deal, agreement):
    entries = Ledger.objects.filter(deal=deal)
    received = entries.filter(kind__in=['receipt','receipt_back']).aggregate(n=Sum('distributable'))['n'] or 0
    gross = entries.filter(kind__in=['receipt','receipt_back']).aggregate(n=Sum('amount'))['n'] or 0
    weights = {row['beneficiary']:int(row['amount']) for row in agreement.shares}
    released = allocate(min(max(received,0),agreement.basis), weights)
    result=[]
    for key,amount in weights.items():
        paid = entries.filter(kind__in=['payout','payout_back'],beneficiary_id=None if key=='office' else key).aggregate(n=Sum('amount'))['n'] or 0
        vote = None if key=='office' else AgreementVote.objects.filter(agreement=agreement,beneficiary_id=key).order_by('-created_at','-id').first()
        decision = vote.decision if vote else 'pending'
        result.append({'beneficiary':key,'approved':str(amount),'released':str(released[key]),'paid':str(paid),
                       'remaining':str(amount-paid),'payable':str(max(0,released[key]-paid)) if decision in ['accepted','resolved'] or key=='office' else '0',
                       'recoverable':str(max(0,paid-released[key])),'decision':decision,'roles':next(x.get('roles',[]) for x in agreement.shares if x['beneficiary']==key)})
    return result, received, gross


def output(m, deal):
    if m.office_id!=deal.office_id or m.organization_id!=deal.organization_id:raise NotFound()
    agreement = Agreement.objects.filter(deal=deal).order_by('-sequence').first()
    if m.role!='manager' and (not agreement or not any(x['beneficiary']==str(m.id) for x in agreement.shares)):
        raise NotFound()
    result={'id':str(deal.id),'offering':str(deal.offering_id),'state':deal.state,'version':deal.version}
    if m.role=='manager': result['amount']=str(deal.amount)
    if agreement:
        shares,received,gross=state(deal,agreement)
        result.update(agreement=str(agreement.id), sequence=agreement.sequence,
                      shares=shares if m.role=='manager' else [x for x in shares if x['beneficiary']==str(m.id)])
        if m.role=='manager':
            result.update(fee=str(agreement.fee),basis=str(agreement.basis),deductions=agreement.deductions,
                          received=str(gross),distributable=str(received),excess=str(max(0,received-agreement.basis)))
            result['ledger']=[{'id':str(x.id),'kind':x.kind,'amount':str(x.amount),'distributable':str(x.distributable),
                              'beneficiary':str(x.beneficiary_id) if x.beneficiary_id else 'office','created_at':x.created_at.isoformat()}
                             for x in Ledger.objects.filter(deal=deal).order_by('created_at','id')]
            result['agreements']=[{'id':str(x.id),'sequence':x.sequence,'fee':str(x.fee),'basis':str(x.basis),'shares':x.shares}
                                  for x in Agreement.objects.filter(deal=deal).order_by('sequence')]
    return result


@transaction.atomic
def create(m,d):
    manager(m)
    offering=get_offering(m,d['offering'],True)
    if offering.status!='approved':raise Conflict('عرضه باید تأیید شده باشد.')
    obj=Deal.objects.create(**scope(m),offering=offering,amount=d['amount'])
    audit(m,'deal.create',obj.id)
    return obj


@transaction.atomic
def mutate(m,pk,action,d):
    try: deal=Deal.objects.select_for_update().get(pk=pk,**scope(m))
    except Deal.DoesNotExist:raise NotFound()
    if action=='vote':
        agreement=current(deal)
        if str(agreement.id)!=str(d['agreement']):raise Conflict('نسخه توافق تغییر کرده است.')
        beneficiary=str(d.get('beneficiary',m.id))
        if beneficiary!=str(m.id) and m.role!='manager':raise PermissionDenied()
        if not any(x['beneficiary']==beneficiary for x in agreement.shares):raise NotFound()
        if d['decision']=='resolved':manager(m)
        elif beneficiary!=str(m.id):raise PermissionDenied()
        if d['decision'] in ['disputed','resolved'] and not d['reason']:raise ValidationError('دلیل الزامی است.')
        last=AgreementVote.objects.filter(agreement=agreement,beneficiary_id=beneficiary).order_by('-created_at','-id').first()
        if last and last.decision=='disputed' and d['decision']=='accepted':raise Conflict('اختلاف نیازمند تصمیم مستند مدیر است.')
        AgreementVote.objects.create(**scope(m),agreement=agreement,actor=m,beneficiary_id=beneficiary,decision=d['decision'],reason=d['reason'])
        audit(m,'agreement.vote',deal.id)
        return deal
    manager(m)
    fingerprint=hashlib.sha256(json.dumps({'deal':str(pk),'action':action,**{k:str(v) for k,v in d.items() if k!='version'}},sort_keys=True).encode()).hexdigest()
    if 'operation' in d:
        previous=Ledger.objects.filter(office=m.office,operation=d['operation']).first()
        if previous:
            if previous.fingerprint!=fingerprint:raise Conflict('شناسه عملیات قبلاً با اطلاعات دیگری استفاده شده است.')
            return deal
    if deal.version!=d['version']:raise Conflict()
    if deal.state!='open' and action!='reverse':raise Conflict('معامله بسته است.')
    if action=='agreement':
        deductions=sum(x['amount'] for x in d['deductions'])
        if deductions>d['fee']:raise ValidationError('کسورات بیشتر از کارمزد است.')
        if len({x['title'] for x in d['deductions']})!=len(d['deductions']):raise ValidationError('عنوان کسر تکراری است.')
        basis=d['fee']-deductions
        weights={x['beneficiary']:x['value'] for x in d['shares']}
        if len(weights)!=len(d['shares']) or 'office' not in weights:raise ValidationError('سهم دفتر باید صریح و ذی‌نفعان یکتا باشند.')
        ids=[key for key in weights if key!='office']
        try:
            members=Membership.objects.filter(id__in=ids,**scope(m))
            if members.count()!=len(ids):raise ValidationError('ذی‌نفع نامعتبر است.')
        except (ValueError,DjangoValidationError):raise ValidationError('ذی‌نفع نامعتبر است.')
        if d['mode']=='percent' and sum(weights.values())!=10000:raise ValidationError('جمع درصدها باید ۱۰۰ باشد.')
        if d['mode']=='fixed' and sum(weights.values())!=basis:raise ValidationError('جمع سهم‌ها باید برابر مبنا باشد.')
        previous_agreement=Agreement.objects.filter(deal=deal).order_by('-sequence').first()
        if previous_agreement and not {x['beneficiary'] for x in previous_agreement.shares}.issubset(weights):raise ValidationError('ذی‌نفعان تاریخی را حذف نکنید؛ سهم صفر ثبت کنید.')
        amounts=allocate(basis,weights) if d['mode']=='percent' else weights
        old=Agreement.objects.filter(deal=deal).order_by('-sequence').first()
        Agreement.objects.create(**scope(m),deal=deal,sequence=old.sequence+1 if old else 1,fee=d['fee'],basis=basis,
                                 mode=d['mode'],deductions=[{'title':x['title'],'amount':str(x['amount'])} for x in d['deductions']],
                                 shares=[{'beneficiary':key,'value':str(weights[key]),'amount':str(amounts[key]),'roles':next(x.get('roles',[]) for x in d['shares'] if x['beneficiary']==key)} for key in sorted(weights)],reason=d['reason'])
    elif action in ['receipt','payout','reverse']:
        agreement=current(deal)
        values={'kind':action,'amount':d.get('amount',0),'distributable':0,'beneficiary_id':None,'reference':d.get('reference',d.get('reason',''))}
        if action=='reverse':
            try:entry=Ledger.objects.get(pk=d['entry'],deal=deal,kind__in=['receipt','payout'])
            except Ledger.DoesNotExist:raise NotFound()
            if Ledger.objects.filter(reversal_of=entry).exists():raise Conflict('قبلاً معکوس شده است.')
            values.update(kind=entry.kind+'_back',amount=-entry.amount,distributable=-entry.distributable,
                          beneficiary_id=entry.beneficiary_id,reversal_of=entry)
        else:
            if d['amount']<=0:raise ValidationError('مبلغ باید مثبت باشد.')
            if action=='receipt':
                if d['distributable']>d['amount']:raise ValidationError('بخش قابل تقسیم بیش از دریافت است.')
                if d.get('beneficiary'):raise ValidationError('دریافت ذی‌نفع ندارد.')
                values['distributable']=d['distributable']
            else:
                shares,_,_=state(deal,agreement)
                key=d.get('beneficiary')
                selected=next((x for x in shares if x['beneficiary']==key),None)
                if not selected or d['amount']>int(selected['payable']):raise Conflict('مبلغ قابل پرداخت کافی یا موافقت سهم وجود ندارد.')
                if d['distributable']:raise ValidationError('پرداخت بخش قابل تقسیم ندارد.')
                values['beneficiary_id']=None if key=='office' else key
        try:
            with transaction.atomic():
                Ledger.objects.create(**scope(m),deal=deal,agreement=agreement,actor=m,operation=d['operation'],fingerprint=fingerprint,**values)
        except IntegrityError:
            previous=Ledger.objects.filter(office=m.office,operation=d['operation']).first()
            if previous and previous.fingerprint==fingerprint:return deal
            raise Conflict('شناسه عملیات تکراری یا سند معکوس نامعتبر است.')
    elif action=='cancel':
        deal.state='cancelled';deal.reason=d['reason']
    else:raise ValidationError('عملیات نامعتبر است.')
    deal.version+=1;deal.save()
    audit(m,'deal.'+action,deal.id)
    return deal
