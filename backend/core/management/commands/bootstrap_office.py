from getpass import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from core.models import Organization, Office, User, Membership


class Command(BaseCommand):
    help = "Initialize one customer and one office with a manager. Interactive password; no fixed secret."

    def add_arguments(self, p):
        p.add_argument("--organization", required=True)
        p.add_argument("--office", required=True)
        p.add_argument("--city", default="")
        p.add_argument("--username", required=True)

    @transaction.atomic
    def handle(self, *args, **o):
        if Organization.objects.exists():
            raise CommandError(
                "Already initialized; additional offices are not enabled in this release."
            )
        password = getpass("Manager password: ")
        if password != getpass("Repeat password: "):
            raise CommandError("Passwords differ.")
        try:
            validate_password(password)
        except ValidationError as e:
            raise CommandError("; ".join(e.messages))
        org = Organization.objects.create(name=o["organization"])
        office = Office.objects.create(
            organization=org, name=o["office"], city=o["city"]
        )
        user = User.objects.create_user(username=o["username"], password=password)
        Membership.objects.create(
            organization=org, office=office, user=user, role="manager"
        )
        self.stdout.write("Office and manager initialized.")
