from django.db import models
from django.db.models import Q
from core.models import Scoped, Offering, Membership, Entity
from core.fields import EncryptedTextField


class OfficeSettings(Entity):
    office = models.OneToOneField('core.Office', on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)
    response_hours = models.PositiveIntegerField(default=0)


class OfferingRevision(Scoped):
    offering = models.ForeignKey(Offering, on_delete=models.PROTECT)
    author = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name='+')
    reviewer = models.ForeignKey(Membership, null=True, on_delete=models.PROTECT, related_name='+')
    base_version = models.PositiveIntegerField()
    changes = models.JSONField()
    state = models.CharField(max_length=12, default='submitted')
    reason = models.CharField(max_length=500, blank=True)


class Publication(Scoped):
    offering = models.OneToOneField(Offering, on_delete=models.PROTECT)
    consent = models.BooleanField(default=False)
    consent_reference = EncryptedTextField(default='')
    consent_by = models.ForeignKey(Membership, null=True, on_delete=models.PROTECT, related_name='+')
    consent_at = models.DateTimeField(null=True)
    published = models.BooleanField(default=False)
    snapshot = models.JSONField(default=dict)
    source_version = models.PositiveIntegerField(default=1)
    version = models.PositiveIntegerField(default=1)


class Customer(Entity):
    office = models.ForeignKey('core.Office', on_delete=models.PROTECT)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    epoch = models.PositiveIntegerField(default=1)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['office','username'], name='customer_office_username')]


class CustomerRequest(Entity):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    publication = models.ForeignKey(Publication, on_delete=models.PROTECT)
    kind = models.CharField(max_length=12, default='visit')
    message = EncryptedTextField()
    status = models.CharField(max_length=12, default='received')
    version = models.PositiveIntegerField(default=1)


class Favorite(Entity):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    publication = models.ForeignKey(Publication, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['customer','publication'], name='customer_favorite')]


class Deal(Scoped):
    offering = models.ForeignKey(Offering, on_delete=models.PROTECT)
    amount = models.BigIntegerField()
    state = models.CharField(max_length=12, default='open')
    version = models.PositiveIntegerField(default=1)
    reason = EncryptedTextField(default='')
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gte=0), name='deal_amount_nonnegative')]


class Agreement(Scoped):
    deal = models.ForeignKey(Deal, on_delete=models.PROTECT)
    sequence = models.PositiveIntegerField()
    fee = models.BigIntegerField()
    deductions = models.JSONField(default=list)
    basis = models.BigIntegerField()
    mode = models.CharField(max_length=12)
    shares = models.JSONField()
    reason = EncryptedTextField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['deal','sequence'], name='agreement_sequence'),
                      models.CheckConstraint(condition=Q(fee__gte=0,basis__gte=0),name='agreement_nonnegative')]


class Ledger(Scoped):
    deal = models.ForeignKey(Deal, on_delete=models.PROTECT)
    agreement = models.ForeignKey(Agreement, on_delete=models.PROTECT)
    actor = models.ForeignKey(Membership, on_delete=models.PROTECT)
    kind = models.CharField(max_length=12)
    amount = models.BigIntegerField()
    distributable = models.BigIntegerField(default=0)
    beneficiary = models.ForeignKey(Membership, null=True, on_delete=models.PROTECT, related_name='+')
    reference = EncryptedTextField()
    operation = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    reversal_of = models.OneToOneField('self', null=True, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['office','operation'],name='ledger_operation_unique')]


class AgreementVote(Scoped):
    agreement = models.ForeignKey(Agreement, on_delete=models.PROTECT)
    actor = models.ForeignKey(Membership, on_delete=models.PROTECT)
    beneficiary = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name='+')
    decision = models.CharField(max_length=12)
    reason = EncryptedTextField(default='')


class PublicImage(Scoped):
    publication = models.ForeignKey(Publication, on_delete=models.PROTECT)
    storage_key = models.CharField(max_length=255)
    reviewer = models.ForeignKey(Membership, on_delete=models.PROTECT)


class Invitation(Scoped):
    digest = models.CharField(max_length=64, unique=True)
    creator = models.ForeignKey(Membership, on_delete=models.PROTECT)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True)
    revoked = models.BooleanField(default=False)


class ReminderSent(Scoped):
    recipient = models.ForeignKey(Membership,on_delete=models.PROTECT)
    record_id = models.UUIDField()
    event_code = models.CharField(max_length=40)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['recipient','record_id','event_code'],name='business_reminder_once')]
