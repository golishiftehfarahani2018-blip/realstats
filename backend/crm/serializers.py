from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from core.serializers import (
    StrictSerializer,
    VersionInput,
    Money,
    OfferingOutput,
    normalize,
)

KINDS = ["apartment", "villa", "land", "commercial", "office", "other"]
from .constants import REASON_CODES as REASONS, OUTCOME_CODES as OUTCOMES


class PersonInput(StrictSerializer):
    name = serializers.CharField(max_length=150)
    phone = serializers.RegexField(r"^09[0-9]{9}$", max_length=11)


class DemandCriteria(StrictSerializer):
    kind = serializers.ChoiceField(choices=KINDS)
    transaction = serializers.ChoiceField(choices=["sale", "rent"])
    districts = serializers.ListField(
        child=serializers.CharField(max_length=100), max_length=30, default=list
    )
    area_min = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    area_max = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    budget_min_toman = Money(default=0)
    budget_max_toman = Money(default=0)
    deposit_max_toman = Money(default=0)
    rent_max_toman = Money(default=0)

    def validate_districts(self, values):
        return sorted(set(normalize(v) for v in values))

    def validate(self, d):
        if (
            d["area_min"] > d["area_max"]
            or d["budget_min_toman"] > d["budget_max_toman"]
        ):
            raise serializers.ValidationError("حداقل نباید از حداکثر بیشتر باشد.")
        if d["transaction"] == "rent" and (
            d["budget_min_toman"] or d["budget_max_toman"]
        ):
            raise serializers.ValidationError(
                "برای اجاره، ودیعه و اجاره را جدا وارد کنید؛ بودجه فروش باید صفر باشد."
            )
        if d["transaction"] == "sale" and (
            d["deposit_max_toman"] or d["rent_max_toman"]
        ):
            raise serializers.ValidationError("برای خرید فقط بودجه فروش را وارد کنید.")
        return d


class DemandInput(DemandCriteria):
    person_id = serializers.UUIDField(required=False)
    name = serializers.CharField(max_length=150, required=False)
    phone = serializers.RegexField(r"^09[0-9]{9}$", max_length=11, required=False)

    def validate(self, d):
        super().validate(d)
        if "person_id" in d:
            if "name" in d or "phone" in d:
                raise serializers.ValidationError(
                    "شخص موجود یا مشخصات شخص جدید را انتخاب کنید."
                )
        elif not d.get("name") or not d.get("phone"):
            raise serializers.ValidationError("نام و شماره متقاضی الزامی است.")
        return d


class DemandEditInput(DemandCriteria):
    version = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=["open", "closed"])


class AssignInput(VersionInput):
    assignee_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=500)


class CooperationInput(StrictSerializer):
    demand_id = serializers.UUIDField()
    offering_id = serializers.UUIDField()


class CooperationDecision(VersionInput):
    decision = serializers.ChoiceField(
        choices=["accepted", "rejected", "closed", "reopen"]
    )
    reason_code = serializers.ChoiceField(
        choices=REASONS, required=False, allow_blank=True
    )

    def validate(self, d):
        if d["decision"] in ["rejected", "closed", "reopen"] and not d.get(
            "reason_code"
        ):
            raise serializers.ValidationError("علت تصمیم را انتخاب کنید.")
        return d


class VisitInput(StrictSerializer):
    cooperation_id = serializers.UUIDField()
    cooperation_version = serializers.IntegerField(min_value=1)
    scheduled_at = serializers.DateTimeField()

    def validate_scheduled_at(self, v):
        if v <= timezone.now():
            raise serializers.ValidationError("زمان بازدید باید در آینده باشد.")
        return v


class VisitEditInput(VersionInput):
    action = serializers.ChoiceField(choices=["reschedule", "complete", "cancel"])
    scheduled_at = serializers.DateTimeField(required=False)
    outcome_code = serializers.ChoiceField(
        choices=OUTCOMES + REASONS, required=False, allow_blank=True
    )

    def validate(self, d):
        if d["action"] == "reschedule":
            if not d.get("scheduled_at") or d["scheduled_at"] <= timezone.now():
                raise serializers.ValidationError("زمان آینده الزامی است.")
            if not d.get("outcome_code"):
                raise serializers.ValidationError("علت تغییر زمان الزامی است.")
        elif "scheduled_at" in d:
            raise serializers.ValidationError(
                "تغییر زمان فقط در عملیات جابه‌جایی مجاز است."
            )
        if d["action"] == "complete" and d.get("outcome_code") not in OUTCOMES:
            raise serializers.ValidationError("نتیجه بازدید را مشخص کنید.")
        if d["action"] == "cancel" and d.get("outcome_code") not in REASONS:
            raise serializers.ValidationError("علت لغو را مشخص کنید.")
        return d


class FollowUpInput(StrictSerializer):
    cooperation_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=["call", "note", "task"])
    body = serializers.CharField(max_length=2000)
    due_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, d):
        if d["kind"] == "task" and not d.get("due_at"):
            raise serializers.ValidationError("سررسید وظیفه الزامی است.")
        return d


class DemandOutput(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    transaction = serializers.CharField()
    districts = serializers.ListField(child=serializers.CharField())
    area_min = serializers.CharField()
    area_max = serializers.CharField()
    budget_min_toman = serializers.CharField()
    budget_max_toman = serializers.CharField()
    deposit_max_toman = serializers.CharField()
    rent_max_toman = serializers.CharField()
    currency = serializers.CharField()
    status = serializers.CharField()
    version = serializers.IntegerField()
    can_edit = serializers.BooleanField()
    can_operate = serializers.BooleanField()
    can_view_private = serializers.BooleanField()
    introducer_id = serializers.UUIDField()
    assignee_id = serializers.UUIDField()
    created_at = serializers.DateTimeField()


class CooperationOutput(serializers.Serializer):
    id = serializers.UUIDField()
    demand_id = serializers.UUIDField()
    offering_id = serializers.UUIDField()
    status = serializers.CharField()
    reason_code = serializers.CharField()
    version = serializers.IntegerField()
    can_decide = serializers.BooleanField()
    can_schedule = serializers.BooleanField()
    can_close = serializers.BooleanField()
    can_reopen = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class VisitOutput(serializers.Serializer):
    id = serializers.UUIDField()
    cooperation_id = serializers.UUIDField()
    scheduled_at = serializers.DateTimeField()
    status = serializers.CharField()
    outcome_code = serializers.CharField()
    version = serializers.IntegerField()
    can_change = serializers.BooleanField()


class MatchReason(serializers.Serializer):
    criterion = serializers.CharField()
    label = serializers.CharField()
    matched = serializers.BooleanField()
    required = serializers.BooleanField()
    weight = serializers.IntegerField()


class MatchOutput(serializers.Serializer):
    offering = OfferingOutput()
    eligible = serializers.BooleanField()
    score = serializers.IntegerField()
    reasons = MatchReason(many=True)
    rules_version = serializers.CharField()


class PersonOutput(serializers.Serializer):
    id = serializers.UUIDField()
    label = serializers.CharField()
    relations = serializers.ListField(
        child=serializers.ChoiceField(choices=["owner", "applicant"])
    )


class ContactOutput(serializers.Serializer):
    name = serializers.CharField()
    phone = serializers.CharField()


class FollowUpOutput(serializers.Serializer):
    id = serializers.UUIDField()
    cooperation_id = serializers.UUIDField()
    kind = serializers.CharField()
    due_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    overdue = serializers.BooleanField()
    version = serializers.IntegerField()


class NoteOutput(serializers.Serializer):
    body = serializers.CharField()


class NotificationOutput(serializers.Serializer):
    id = serializers.UUIDField()
    event_code = serializers.CharField()
    label = serializers.CharField()
    record_id = serializers.UUIDField()
    record_type = serializers.CharField()
    read_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class PaginatedOutput(serializers.Serializer):
    count = serializers.IntegerField()
    offset = serializers.IntegerField()
    limit = serializers.IntegerField()
    has_more = serializers.BooleanField()


class PersonPage(PaginatedOutput):
    results = PersonOutput(many=True)


class DemandPage(PaginatedOutput):
    results = DemandOutput(many=True)


class MatchPage(PaginatedOutput):
    results = MatchOutput(many=True)
    candidate_limit = serializers.IntegerField()


class CooperationPage(PaginatedOutput):
    results = CooperationOutput(many=True)


class VisitPage(PaginatedOutput):
    results = VisitOutput(many=True)


class FollowUpPage(PaginatedOutput):
    results = FollowUpOutput(many=True)


class NotificationPage(PaginatedOutput):
    results = NotificationOutput(many=True)
