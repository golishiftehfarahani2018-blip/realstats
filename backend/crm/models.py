from django.db import models
from django.db.models import Q
from core.models import Scoped, Person, Membership, Offering
from core.fields import EncryptedTextField
from .constants import NOTIFICATION_LABELS, REASON_CODES, OUTCOME_CODES


class PersonRelation(Scoped):
    person = models.ForeignKey(Person, on_delete=models.PROTECT)
    membership = models.ForeignKey(Membership, on_delete=models.PROTECT)
    relation = models.CharField(
        max_length=12, choices=[("owner", "مالک"), ("applicant", "متقاضی")]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person", "membership", "relation"],
                name="crm_unique_person_relation",
            ),
            models.CheckConstraint(
                condition=Q(relation__in=["owner", "applicant"]),
                name="crm_valid_relation",
            ),
        ]


class PhoneIndex(Scoped):
    digest = models.CharField(max_length=64)
    person = models.ForeignKey(Person, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["office", "organization", "digest"],
                name="crm_unique_office_phone",
            )
        ]


class Demand(Scoped):
    person = models.ForeignKey(Person, on_delete=models.PROTECT)
    introducer = models.ForeignKey(
        Membership, on_delete=models.PROTECT, related_name="customer_demands"
    )
    assignee = models.ForeignKey(
        Membership, on_delete=models.PROTECT, related_name="assigned_demands"
    )
    kind = models.CharField(max_length=30)
    transaction = models.CharField(
        max_length=10, choices=[("sale", "خرید"), ("rent", "اجاره")]
    )
    districts = models.JSONField(default=list)
    area_min = models.DecimalField(max_digits=10, decimal_places=2)
    area_max = models.DecimalField(max_digits=10, decimal_places=2)
    budget_min_toman = models.BigIntegerField(default=0)
    budget_max_toman = models.BigIntegerField(default=0)
    deposit_max_toman = models.BigIntegerField(default=0)
    rent_max_toman = models.BigIntegerField(default=0)
    status = models.CharField(
        max_length=10, default="open", choices=[("open", "باز"), ("closed", "بسته")]
    )
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id", "office", "organization"], name="crm_demand_scope_unique"
            ),
            models.CheckConstraint(
                condition=Q(area_min__gt=0, area_max__gte=models.F("area_min")),
                name="crm_valid_area_range",
            ),
            models.CheckConstraint(
                condition=Q(
                    budget_min_toman__gte=0,
                    budget_max_toman__gte=models.F("budget_min_toman"),
                    deposit_max_toman__gte=0,
                    rent_max_toman__gte=0,
                ),
                name="crm_valid_budget",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["open", "closed"]),
                name="crm_valid_demand_status",
            ),
            models.CheckConstraint(
                condition=Q(transaction__in=["sale", "rent"]),
                name="crm_valid_demand_transaction",
            ),
        ]
        indexes = [models.Index(fields=["office", "status", "kind", "transaction"])]


class AssignmentEvent(Scoped):
    demand = models.ForeignKey(Demand, on_delete=models.PROTECT)
    previous = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name="+")
    assignee = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name="+")
    actor = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name="+")
    reason = EncryptedTextField()


class Cooperation(Scoped):
    demand = models.ForeignKey(Demand, on_delete=models.PROTECT)
    offering = models.ForeignKey(Offering, on_delete=models.PROTECT)
    requested_by = models.ForeignKey(
        Membership, on_delete=models.PROTECT, related_name="+"
    )
    supplier = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name="+")
    status = models.CharField(
        max_length=12,
        default="requested",
        choices=[
            ("requested", "درخواست‌شده"),
            ("accepted", "پذیرفته"),
            ("rejected", "ردشده"),
            ("closed", "بسته"),
        ],
    )
    reason_code = models.CharField(
        max_length=30, blank=True, choices=[(v, v) for v in REASON_CODES]
    )
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id", "office", "organization"],
                name="crm_cooperation_scope_unique",
            ),
            models.UniqueConstraint(
                fields=["demand", "offering"], name="crm_unique_cooperation_pair"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["requested", "accepted", "rejected", "closed"]),
                name="crm_valid_cooperation_status",
            ),
        ]


class Visit(Scoped):
    cooperation = models.ForeignKey(Cooperation, on_delete=models.PROTECT)
    scheduled_at = models.DateTimeField()
    status = models.CharField(
        max_length=12,
        default="scheduled",
        choices=[
            ("scheduled", "برنامه‌ریزی"),
            ("completed", "انجام‌شده"),
            ("cancelled", "لغوشده"),
        ],
    )
    outcome_code = models.CharField(
        max_length=30,
        blank=True,
        choices=[(v, v) for v in REASON_CODES + OUTCOME_CODES],
    )
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["id", "office", "organization"], name="crm_visit_scope_unique"
            ),
            models.UniqueConstraint(
                fields=["cooperation"],
                condition=Q(status="scheduled"),
                name="crm_one_scheduled_visit",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["scheduled", "completed", "cancelled"]),
                name="crm_valid_visit_status",
            ),
        ]


class FollowUp(Scoped):
    cooperation = models.ForeignKey(Cooperation, on_delete=models.PROTECT)
    author = models.ForeignKey(Membership, on_delete=models.PROTECT)
    kind = models.CharField(
        max_length=10,
        choices=[("call", "تماس"), ("note", "یادداشت"), ("task", "وظیفه")],
    )
    body = EncryptedTextField()
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["call", "note", "task"]),
                name="crm_valid_followup_kind",
            )
        ]


class Notification(Scoped):
    recipient = models.ForeignKey(Membership, on_delete=models.PROTECT)
    event_code = models.CharField(
        max_length=40, choices=list(NOTIFICATION_LABELS.items())
    )
    record_type = models.CharField(
        max_length=15,
        choices=[
            (v, v) for v in ["cooperation", "visit", "demand", "offering", "followup"]
        ],
    )
    record_id = models.UUIDField()
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(event_code__in=list(NOTIFICATION_LABELS)),
                name="crm_safe_notification_code",
            ),
            models.CheckConstraint(
                condition=Q(
                    record_type__in=[
                        "cooperation",
                        "visit",
                        "demand",
                        "offering",
                        "followup",
                    ]
                ),
                name="crm_safe_notification_type",
            ),
        ]
        indexes = [models.Index(fields=["recipient", "read_at", "created_at"])]


class OfferingAssignmentEvent(Scoped):
    offering = models.ForeignKey(Offering, on_delete=models.PROTECT)
    previous = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name="+")
    assignee = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name="+")
    actor = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name="+")
    reason = EncryptedTextField()


class CooperationHistory(Scoped):
    cooperation = models.ForeignKey(Cooperation, on_delete=models.PROTECT)
    actor = models.ForeignKey(Membership, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12)
    reason_code = models.CharField(
        max_length=30, blank=True, choices=[(v, v) for v in REASON_CODES]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cooperation", "version"],
                name="crm_unique_cooperation_history_version",
            )
        ]


class VisitHistory(Scoped):
    visit = models.ForeignKey(Visit, on_delete=models.PROTECT)
    actor = models.ForeignKey(Membership, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=12)
    outcome_code = models.CharField(
        max_length=30,
        blank=True,
        choices=[(v, v) for v in REASON_CODES + OUTCOME_CODES],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["visit", "version"], name="crm_unique_visit_history_version"
            )
        ]
