import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Q
from .fields import EncryptedTextField


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class Entity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Organization(Entity):
    name = models.CharField(max_length=120)


class Office(Entity):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=100, blank=True)
    branding = models.JSONField(default=dict)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id", "organization"], name="office_org_pair"
            )
        ]


class Scoped(Entity):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    office = models.ForeignKey(Office, on_delete=models.PROTECT)

    class Meta:
        abstract = True


class Membership(Scoped):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    role = models.CharField(
        max_length=20,
        choices=[("manager", "مدیر"), ("senior", "ارشد"), ("advisor", "مشاور")],
    )
    active = models.BooleanField(default=True)
    auth_epoch = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "office"], name="unique_membership"
            ),
            models.UniqueConstraint(
                fields=["id", "office", "organization"], name="membership_scope_pair"
            ),
            models.CheckConstraint(
                condition=Q(role__in=["manager", "senior", "advisor"]),
                name="valid_role",
            ),
        ]


class Person(Scoped):
    version = models.PositiveIntegerField(default=1)
    name = EncryptedTextField()
    phone = EncryptedTextField()


class Property(Scoped):
    details = models.JSONField(default=dict)
    kind = models.CharField(max_length=30)
    district = models.CharField(max_length=100)
    area = models.DecimalField(max_digits=10, decimal_places=2)
    exact_address = EncryptedTextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id", "office", "organization"], name="property_scope_pair"
            ),
            models.CheckConstraint(condition=Q(area__gt=0), name="positive_area"),
        ]


class Offering(Scoped):
    negotiable_price = models.BooleanField(default=False)
    property = models.ForeignKey(Property, on_delete=models.PROTECT)
    owner = models.ForeignKey(Person, on_delete=models.PROTECT)
    introducer = models.ForeignKey(
        Membership, on_delete=models.PROTECT, related_name="introduced"
    )
    assignee = models.ForeignKey(
        Membership, on_delete=models.PROTECT, related_name="assigned"
    )
    transaction = models.CharField(
        max_length=10, choices=[("sale", "فروش"), ("rent", "اجاره")]
    )
    price_toman = models.BigIntegerField()
    deposit_toman = models.BigIntegerField(default=0)
    rent_toman = models.BigIntegerField(default=0)
    status = models.CharField(
        max_length=12,
        default="draft",
        choices=[
            ("draft", "پیش‌نویس"),
            ("submitted", "در انتظار بررسی"),
            ("revision", "نیازمند اصلاح"),
            ("approved", "تأییدشده"),
        ],
    )
    review_reason = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)
    reviewed_by = models.ForeignKey(
        Membership, null=True, on_delete=models.PROTECT, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    price_toman__gte=0, deposit_toman__gte=0, rent_toman__gte=0
                ),
                name="nonnegative_money",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["draft", "submitted", "revision", "approved"]),
                name="valid_status",
            ),
            models.CheckConstraint(
                condition=Q(transaction__in=["sale", "rent"]), name="valid_transaction"
            ),
        ]
        indexes = [models.Index(fields=["office", "status"])]


class PriceHistory(Scoped):
    offering = models.ForeignKey(Offering, on_delete=models.PROTECT)
    actor = models.ForeignKey(Membership, on_delete=models.PROTECT)
    offering_version = models.PositiveIntegerField()
    price_toman = models.BigIntegerField()
    deposit_toman = models.BigIntegerField()
    rent_toman = models.BigIntegerField()


class PublicListing(Scoped):
    # Separate snapshot, intentionally no publishing endpoint in phase 1.
    offering = models.ForeignKey(Offering, on_delete=models.PROTECT)
    approved_snapshot = models.JSONField(default=dict)
    consent_at = models.DateTimeField(null=True)
    published_at = models.DateTimeField(null=True)


class PrivateDocument(Scoped):
    offering = models.ForeignKey(Offering, on_delete=models.PROTECT)
    storage_key = models.CharField(max_length=255)
    content_type = models.CharField(max_length=50)
    size = models.PositiveIntegerField()


class AuditEvent(Scoped):
    actor = models.ForeignKey(Membership, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    record_id = models.UUIDField(null=True)
    outcome = models.CharField(max_length=10, default="allowed")
    # No payload or before/after dumps: never record phone, address or credentials.


class LoginAttempt(models.Model):
    key = models.CharField(primary_key=True, max_length=64)
    count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField()
