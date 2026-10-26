import time
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from botocore.exceptions import BotoCoreError, ClientError
from core.storage import client


class Command(BaseCommand):
    help = "Create separate buckets; neither allows anonymous access."

    def handle(self, *args, **kwargs):
        c = client()
        for attempt in range(20):
            try:
                for bucket in [settings.S3_PRIVATE_BUCKET, settings.S3_PUBLIC_BUCKET]:
                    try:
                        c.head_bucket(Bucket=bucket)
                    except ClientError as e:
                        if str(e.response["Error"]["Code"]) not in [
                            "404",
                            "NoSuchBucket",
                        ]:
                            raise
                        c.create_bucket(Bucket=bucket)
                self.stdout.write("Buckets initialized, anonymous access disabled.")
                return
            except (BotoCoreError, ClientError):
                if attempt == 19:
                    raise CommandError("Storage initialization failed.")
                time.sleep(1)
