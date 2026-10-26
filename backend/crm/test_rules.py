from decimal import Decimal
from types import SimpleNamespace as Record
from datetime import timedelta
from django.test import SimpleTestCase
from django.utils import timezone
from .matching import evaluate
from .serializers import (
    DemandInput,
    DemandEditInput,
    VisitInput,
    VisitEditInput,
    CooperationDecision,
    FollowUpInput,
)
from .people import phone_digest


class MatchingRulesTests(SimpleTestCase):
    def demand(self, **changes):
        return Record(
            **(
                {
                    "kind": "apartment",
                    "transaction": "sale",
                    "districts": ["کیان"],
                    "area_min": Decimal("80.25"),
                    "area_max": Decimal("100.75"),
                    "budget_min_toman": 100,
                    "budget_max_toman": 200,
                    "deposit_max_toman": 0,
                    "rent_max_toman": 0,
                }
                | changes
            )
        )

    def offering(self, **changes):
        prop = Record(
            kind=changes.pop("kind", "apartment"),
            district=changes.pop("district", "کیان"),
            area=changes.pop("area", Decimal("90.50")),
        )
        return Record(
            **(
                {
                    "property": prop,
                    "transaction": "sale",
                    "price_toman": 150,
                    "deposit_toman": 0,
                    "rent_toman": 0,
                }
                | changes
            )
        )

    def test_exact_match_with_explanation(self):
        result = evaluate(self.demand(), self.offering())
        self.assertTrue(result["eligible"])
        self.assertEqual(result["score"], 100)
        self.assertEqual(len(result["reasons"]), 5)
        self.assertTrue(all(x["matched"] for x in result["reasons"]))

    def test_preferred_district_is_not_a_hard_exclusion(self):
        result = evaluate(self.demand(), self.offering(district="دیگر"))
        self.assertTrue(result["eligible"])
        self.assertEqual(result["score"], 80)

    def test_unspecified_district_accepts_all(self):
        self.assertEqual(
            evaluate(self.demand(districts=[]), self.offering(district="دیگر"))[
                "score"
            ],
            100,
        )

    def test_mandatory_mismatch_has_zero_score(self):
        for changes in [
            {"kind": "villa"},
            {"transaction": "rent"},
            {"area": Decimal("80.24")},
            {"price_toman": 201},
        ]:
            result = evaluate(self.demand(), self.offering(**changes))
            self.assertFalse(result["eligible"])
            self.assertEqual(result["score"], 0)

    def test_budget_and_decimal_area_boundaries_are_inclusive(self):
        for price, area in [(100, Decimal("80.25")), (200, Decimal("100.75"))]:
            self.assertTrue(
                evaluate(self.demand(), self.offering(price_toman=price, area=area))[
                    "eligible"
                ]
            )

    def test_rent_and_deposit_never_convert_into_each_other(self):
        d = self.demand(
            transaction="rent",
            budget_min_toman=0,
            budget_max_toman=0,
            deposit_max_toman=100,
            rent_max_toman=10,
        )
        self.assertTrue(
            evaluate(
                d, self.offering(transaction="rent", deposit_toman=100, rent_toman=10)
            )["eligible"]
        )
        self.assertFalse(
            evaluate(
                d, self.offering(transaction="rent", deposit_toman=0, rent_toman=11)
            )["eligible"]
        )
        self.assertFalse(
            evaluate(
                d, self.offering(transaction="rent", deposit_toman=101, rent_toman=0)
            )["eligible"]
        )

    def test_bigint_precision_and_no_hidden_tolerance(self):
        amount = 9007199254740993
        d = self.demand(budget_min_toman=amount, budget_max_toman=amount)
        self.assertTrue(evaluate(d, self.offering(price_toman=amount))["eligible"])
        self.assertFalse(evaluate(d, self.offering(price_toman=amount + 1))["eligible"])

    def test_result_is_deterministic_and_has_no_private_fields(self):
        a = evaluate(self.demand(), self.offering())
        b = evaluate(self.demand(), self.offering())
        self.assertEqual(a, b)
        self.assertNotIn("phone", str(a))
        self.assertNotIn("address", str(a))


class CRMInputTests(SimpleTestCase):
    def payload(self):
        return {
            "kind": "apartment",
            "transaction": "sale",
            "area_min": "۸۰.۲۵",
            "area_max": "١٠٠.٧٥",
            "budget_min_toman": "۱۰۰",
            "budget_max_toman": "۲۰۰",
            "districts": ["كيان", "کیان"],
            "name": "شخص ساختگی",
            "phone": "٠٩١٢٣٤٥٦٧٨٩",
        }

    def test_nested_normalization(self):
        v = DemandInput(data=self.payload())
        self.assertTrue(v.is_valid(), v.errors)
        self.assertEqual(v.validated_data["districts"], ["کیان"])
        self.assertEqual(v.validated_data["area_min"], Decimal("80.25"))

    def test_conflicting_customer_identity_rejected(self):
        d = self.payload()
        d["person_id"] = "00000000-0000-0000-0000-000000000001"
        self.assertFalse(DemandInput(data=d).is_valid())

    def test_forged_authority_rejected(self):
        for key in [
            "office",
            "organization",
            "introducer",
            "assignee",
            "role",
            "status",
        ]:
            d = self.payload()
            d[key] = "forged"
            self.assertFalse(DemandInput(data=d).is_valid())

    def test_range_and_mixed_budget_validation(self):
        for changes in [
            {"area_max": "1"},
            {"budget_max_toman": 1},
            {"rent_max_toman": 1},
            {"transaction": "rent"},
        ]:
            self.assertFalse(DemandInput(data=self.payload() | changes).is_valid())

    def test_missing_identity_and_float_money_rejected(self):
        d = self.payload()
        del d["phone"]
        self.assertFalse(DemandInput(data=d).is_valid())
        self.assertFalse(
            DemandInput(data=self.payload() | {"budget_max_toman": 200.1}).is_valid()
        )

    def test_customer_identity_cannot_be_changed_by_demand_edit(self):
        d = self.payload()
        d.update(version=1, status="open")
        self.assertFalse(DemandEditInput(data=d).is_valid())

    def test_hmac_index_does_not_reveal_phone(self):
        digest = phone_digest("09123456789")
        self.assertEqual(digest, phone_digest("٠٩١٢٣٤٥٦٧٨٩"))
        self.assertEqual(len(digest), 64)
        self.assertNotIn("09123456789", digest)

    def test_visit_rejects_past_time_and_normalizes_tehran(self):
        d = {
            "cooperation_id": "00000000-0000-0000-0000-000000000001",
            "cooperation_version": 1,
            "scheduled_at": (timezone.now() - timedelta(days=1)).isoformat(),
        }
        self.assertFalse(VisitInput(data=d).is_valid())
        d["scheduled_at"] = (timezone.now() + timedelta(days=1)).isoformat()
        v = VisitInput(data=d)
        self.assertTrue(v.is_valid(), v.errors)
        self.assertTrue(timezone.is_aware(v.validated_data["scheduled_at"]))

    def test_visit_outcome_is_controlled(self):
        for d in [
            {
                "version": 1,
                "action": "complete",
                "outcome_code": "arbitrary private text",
            },
            {"version": 1, "action": "cancel"},
            {
                "version": 1,
                "action": "reschedule",
                "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat(),
            },
        ]:
            self.assertFalse(VisitEditInput(data=d).is_valid())

    def test_rejection_needs_reason_and_task_needs_due_date(self):
        self.assertFalse(
            CooperationDecision(data={"version": 1, "decision": "rejected"}).is_valid()
        )
        self.assertFalse(
            FollowUpInput(
                data={
                    "cooperation_id": "00000000-0000-0000-0000-000000000001",
                    "kind": "task",
                    "body": "نمونه",
                }
            ).is_valid()
        )
