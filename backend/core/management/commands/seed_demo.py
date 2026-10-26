import secrets
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import Organization, Office, User, Membership


class Command(BaseCommand):
    help = "Create a fictional office and three accounts. Passwords generated at runtime; never committed."

    @transaction.atomic
    def handle(self, *args, **options):
        if Organization.objects.exists():
            raise CommandError(
                "Database is not empty; demo seed will not overwrite records."
            )
        org = Organization.objects.create(name="مجموعه آزمایشی")
        office = Office.objects.create(
            organization=org,
            name="دفتر نمونه",
            city="شهر نمونه",
            branding={"color": "#17685c"},
        )
        for username, role, name in [
            ("manager", "manager", "مدیر آزمایشی"),
            ("advisor1", "advisor", "مشاور اول"),
            ("advisor2", "advisor", "مشاور دوم"),
        ]:
            password = secrets.token_urlsafe(18)
            user = User.objects.create_user(
                username=username, password=password, first_name=name
            )
            Membership.objects.create(
                organization=org, office=office, user=user, role=role
            )
            self.stdout.write(f"{username}: {password}")
