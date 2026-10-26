from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from core.models import Membership, Offering
from core import services as core
from crm.models import Demand
from crm import services as crm


class Command(BaseCommand):
    help = "Add fictional phase-two workflow to the neutral seed_demo office; no real messages or payments."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        if Demand.objects.exists() or Offering.objects.exists():
            raise CommandError(
                "Existing work records found; refusing to overwrite or duplicate demo data."
            )
        try:
            manager = Membership.objects.get(
                user__username="manager",
                role="manager",
                active=True,
                office__name="دفتر نمونه",
            )
            first = Membership.objects.get(
                user__username="advisor1", office=manager.office, active=True
            )
            second = Membership.objects.get(
                user__username="advisor2", office=manager.office, active=True
            )
        except Membership.DoesNotExist:
            raise CommandError("Run seed_demo on an empty test installation first.")
        o = core.create_offering(
            first,
            {
                "kind": "apartment",
                "district": "محله آزمایشی",
                "area": "95.50",
                "exact_address": "نشانی کاملاً ساختگی برای آزمایش",
                "owner_name": "مالک ساختگی",
                "owner_phone": "09900000001",
                "transaction": "sale",
                "price_toman": 5000000000,
                "deposit_toman": 0,
                "rent_toman": 0,
            },
        )
        core.change_offering(first, o.id, {"version": 1}, "submit")
        o = core.change_offering(
            manager, o.id, {"version": 2, "decision": "approved"}, "review"
        )
        d = crm.create_demand(
            second,
            {
                "name": "متقاضی ساختگی",
                "phone": "09900000002",
                "kind": "apartment",
                "transaction": "sale",
                "districts": ["محله آزمایشی"],
                "area_min": "80",
                "area_max": "110",
                "budget_min_toman": 4000000000,
                "budget_max_toman": 6000000000,
            },
        )
        c, _ = crm.request_cooperation(
            second, {"demand_id": str(d.id), "offering_id": str(o.id)}
        )
        c = crm.decide_cooperation(first, c.id, {"version": 1, "decision": "accepted"})
        crm.create_visit(
            first,
            {
                "cooperation_id": str(c.id),
                "cooperation_version": c.version,
                "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat(),
            },
        )
        crm.create_followup(
            second,
            {
                "cooperation_id": str(c.id),
                "kind": "task",
                "body": "یادداشت ساختگی برای آزمون پیگیری؛ هماهنگی از مسیر معرف انجام شود.",
                "due_at": (timezone.now() + timedelta(hours=2)).isoformat(),
            },
        )
        self.stdout.write(
            f"Fictional CRM demo created. Demand: {d.id}; cooperation: {c.id}"
        )
