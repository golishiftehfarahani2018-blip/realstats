from decimal import Decimal
import uuid
from rest_framework import serializers as s
from core.serializers import StrictSerializer, Money, VersionInput, EditInput


class SettingsInput(VersionInput):
    response_hours = s.IntegerField(min_value=0,max_value=720,default=0)
    name = s.CharField(max_length=120)
    city = s.CharField(max_length=100, allow_blank=True)
    color = s.RegexField(r'^#[0-9a-fA-F]{6}$')


class RevisionInput(StrictSerializer):
    base_version = s.IntegerField(min_value=1)
    changes = EditInput()
    def validate_changes(self, value):
        if set(value) - {'version','kind','district','area','transaction','price_toman','deposit_toman','rent_toman','details','negotiable_price'}:
            raise s.ValidationError('بازنگری عمومی نباید اطلاعات هویتی یا خصوصی را تغییر دهد.')
        value.pop('version', None)
        if not value:
            raise s.ValidationError('تغییری ثبت نشده است.')
        return {k:str(v) if isinstance(v,Decimal) else v for k,v in value.items()}


class ReviewRevision(StrictSerializer):
    decision = s.ChoiceField(choices=['approved','rejected'])
    reason = s.CharField(max_length=500)


class PublishInput(VersionInput):
    action = s.ChoiceField(choices=['consent','revoke','publish','stop'])
    reference = s.CharField(max_length=500, required=False)
    content_reviewed = s.BooleanField(default=False)


class CustomerAuth(StrictSerializer):
    office = s.UUIDField()
    username = s.RegexField(r'^[a-zA-Z0-9_.-]{3,100}$')
    password = s.CharField(min_length=12,max_length=128,trim_whitespace=False)


class RequestInput(StrictSerializer):
    publication = s.UUIDField()
    kind = s.ChoiceField(choices=['visit','information'])
    message = s.CharField(max_length=1000)


class RequestChange(VersionInput):
    status = s.ChoiceField(choices=['received','contacted','closed'])


class CreateDeal(StrictSerializer):
    offering = s.UUIDField()
    amount = Money()


class Deduction(StrictSerializer):
    title = s.CharField(max_length=100)
    amount = Money()


class ShareInput(StrictSerializer):
    roles = s.ListField(child=s.ChoiceField(choices=["office","supplier","customer","collaborator"]),max_length=4,default=list)
    beneficiary = s.CharField(max_length=40)
    value = Money()
    def validate_beneficiary(self, value):
        if value=='office':return value
        try:return str(uuid.UUID(value))
        except ValueError:raise s.ValidationError('ذی‌نفع نامعتبر است.')


class AgreementInput(VersionInput):
    fee = Money()
    deductions = Deduction(many=True, max_length=50)
    mode = s.ChoiceField(choices=['percent','fixed'])
    shares = ShareInput(many=True, min_length=1,max_length=50)
    reason = s.CharField(max_length=1000)


class CashInput(VersionInput):
    operation = s.UUIDField()
    amount = Money()
    distributable = Money(default=0)
    beneficiary = s.CharField(max_length=40,required=False)
    reference = s.CharField(max_length=500)


class ReverseInput(VersionInput):
    operation = s.UUIDField()
    entry = s.UUIDField()
    reason = s.CharField(max_length=500)


class VoteInput(StrictSerializer):
    agreement = s.UUIDField()
    decision = s.ChoiceField(choices=['accepted','disputed','resolved'])
    beneficiary = s.UUIDField(required=False)
    reason = s.CharField(max_length=500,allow_blank=True,default='')


class CancelInput(VersionInput):
    reason = s.CharField(max_length=500)


class InviteAccept(StrictSerializer):
    token = s.CharField(min_length=40,max_length=128)
    username = s.RegexField(r'^[a-zA-Z0-9_.-]{3,100}$')
    name = s.CharField(max_length=100)
    password = s.CharField(min_length=12,max_length=128,trim_whitespace=False)


class PublicImageInput(StrictSerializer):
    file = s.FileField()
    content_reviewed = s.BooleanField()
