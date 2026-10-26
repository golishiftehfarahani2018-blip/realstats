import re
from collections.abc import Mapping
from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

TRANSLATE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩كي", "01234567890123456789کی")


def normalize(v):
    return v.translate(TRANSLATE).strip() if isinstance(v, str) else v


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["بدنه درخواست باید یک شیء باشد."]})
        if set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["فیلد غیرمجاز در درخواست."]})
        return super().to_internal_value(
            {k: (v if k == "password" else normalize(v)) for k, v in data.items()}
        )


class LoginInput(StrictSerializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["بدنه درخواست باید یک شیء باشد."]})
        if set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["فیلد غیرمجاز"]})
        return serializers.Serializer.to_internal_value(self, data)


class Money(serializers.IntegerField):
    def __init__(self, **kwargs):
        super().__init__(min_value=0, max_value=9223372036854775807, **kwargs)

    def to_internal_value(self, data):
        if isinstance(data, bool) or not re.fullmatch(r"\d+", str(normalize(data))):
            raise serializers.ValidationError("مبلغ باید عدد صحیح تومان باشد.")
        return super().to_internal_value(normalize(data))


class PropertyDetails(StrictSerializer):
    rooms = serializers.IntegerField(min_value=0,max_value=100,required=False,allow_null=True)
    floor = serializers.IntegerField(min_value=-20,max_value=300,required=False,allow_null=True)
    floors = serializers.IntegerField(min_value=1,max_value=300,required=False,allow_null=True)
    elevator = serializers.ChoiceField(choices=['unknown','yes','no'],required=False)
    parking = serializers.ChoiceField(choices=['unknown','yes','no'],required=False)
    water = serializers.ChoiceField(choices=['unknown','yes','no'],required=False)
    gas = serializers.ChoiceField(choices=['unknown','yes','no'],required=False)
    electricity = serializers.ChoiceField(choices=['unknown','yes','no'],required=False)
    land_use = serializers.ChoiceField(choices=['unknown','residential','agricultural','commercial'],required=False)
    access = serializers.ChoiceField(choices=['unknown','paved','dirt'],required=False)


class OfferingInput(StrictSerializer):
    negotiable_price = serializers.BooleanField(default=False)
    details = PropertyDetails(required=False,default=dict)
    kind = serializers.ChoiceField(
        choices=["apartment", "villa", "land", "commercial", "office", "other"]
    )
    district = serializers.CharField(max_length=100)
    area = serializers.DecimalField(
        min_value=Decimal("0.01"), max_digits=10, decimal_places=2
    )
    exact_address = serializers.CharField(max_length=1000)
    owner_name = serializers.CharField(max_length=150)
    owner_phone = serializers.RegexField(r"^09[0-9]{9}$", max_length=11)
    transaction = serializers.ChoiceField(choices=["sale", "rent"])
    price_toman = Money()
    deposit_toman = Money(default=0)
    rent_toman = Money(default=0)


class VersionInput(StrictSerializer):
    version = serializers.IntegerField(min_value=1)


class EditInput(VersionInput):
    negotiable_price = serializers.BooleanField(required=False)
    details = PropertyDetails(required=False)
    owner_version = serializers.IntegerField(min_value=1, required=False)
    kind = serializers.ChoiceField(
        choices=["apartment", "villa", "land", "commercial", "office", "other"],
        required=False,
    )
    district = serializers.CharField(max_length=100, required=False)
    area = serializers.DecimalField(
        min_value=Decimal("0.01"), max_digits=10, decimal_places=2, required=False
    )
    transaction = serializers.ChoiceField(choices=["sale", "rent"], required=False)
    exact_address = serializers.CharField(max_length=1000, required=False)
    owner_name = serializers.CharField(max_length=150, required=False)
    owner_phone = serializers.RegexField(r"^09[0-9]{9}$", max_length=11, required=False)
    price_toman = Money(required=False)
    deposit_toman = Money(required=False)
    rent_toman = Money(required=False)


class ReviewInput(VersionInput):
    decision = serializers.ChoiceField(choices=["approved", "revision"])
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate(self, d):
        if d["decision"] == "revision" and not d.get("reason"):
            raise serializers.ValidationError("دلیل اصلاح الزامی است.")
        return d


class AdvisorInput(StrictSerializer):
    username = serializers.RegexField(r"^[a-zA-Z0-9_.-]{3,100}$")
    first_name = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate_password(self, v):
        validate_password(v)
        return v


class ActiveInput(StrictSerializer):
    active = serializers.BooleanField()


class DocumentInput(StrictSerializer):
    file = serializers.FileField()


class OfferingOutput(serializers.Serializer):
    negotiable_price = serializers.BooleanField()
    details = PropertyDetails()
    id = serializers.UUIDField()
    property_id = serializers.UUIDField()
    kind = serializers.CharField()
    district = serializers.CharField()
    area = serializers.DecimalField(max_digits=10, decimal_places=2)
    transaction = serializers.CharField()
    price_toman = serializers.CharField(
        help_text="Integer toman encoded as a string to preserve bigint precision."
    )
    deposit_toman = serializers.CharField()
    rent_toman = serializers.CharField()
    currency = serializers.ChoiceField(choices=["IRT"])
    status = serializers.CharField()
    review_reason = serializers.CharField(allow_blank=True)
    version = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    can_edit = serializers.BooleanField()
    can_view_private = serializers.BooleanField()
    can_review = serializers.BooleanField()


class PrivateOutput(serializers.Serializer):
    owner_version = serializers.IntegerField()
    owner_name = serializers.CharField()
    owner_phone = serializers.CharField()
    exact_address = serializers.CharField()


class OfferingQuery(StrictSerializer):
    q = serializers.CharField(max_length=100, required=False, allow_blank=True)
    paginated = serializers.ChoiceField(choices=['1'], required=False)
    offset = serializers.IntegerField(min_value=0, default=0)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=30)
    kind = serializers.ChoiceField(choices=['apartment', 'villa', 'land', 'commercial', 'office', 'other'], required=False)
    transaction = serializers.ChoiceField(choices=['sale', 'rent'], required=False)
    status = serializers.ChoiceField(choices=['draft', 'submitted', 'revision', 'approved'], required=False)
    area_min = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), required=False)
    area_max = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), required=False)
    price_min = Money(required=False)
    price_max = Money(required=False)
    deposit_min = Money(required=False)
    deposit_max = Money(required=False)
    rent_min = Money(required=False)
    rent_max = Money(required=False)

    def validate(self, data):
        for field in ['area', 'price', 'deposit', 'rent']:
            if field+'_min' in data and field+'_max' in data and data[field+'_min'] > data[field+'_max']:
                raise serializers.ValidationError({field+'_max': 'حداکثر باید برابر یا بیشتر از حداقل باشد.'})
        if any(k.startswith('price_') for k in data) and data.get('transaction') != 'sale':
            raise serializers.ValidationError({'transaction': 'برای فیلتر قیمت فروش، نوع معامله را فروش انتخاب کنید.'})
        if any(k.startswith(('deposit_', 'rent_')) for k in data) and data.get('transaction') != 'rent':
            raise serializers.ValidationError({'transaction': 'برای فیلتر ودیعه یا اجاره، نوع معامله را اجاره انتخاب کنید.'})
        return data


class OfferingPage(serializers.Serializer):
    count = serializers.IntegerField()
    offset = serializers.IntegerField()
    limit = serializers.IntegerField()
    has_more = serializers.BooleanField()
    results = OfferingOutput(many=True)
