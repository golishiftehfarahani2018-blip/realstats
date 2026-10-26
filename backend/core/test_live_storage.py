import os
import secrets
from io import BytesIO
from unittest import skipUnless
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from PIL import Image
from .models import Organization, Office, Membership, User, PrivateDocument
from .services import create_offering, change_offering, deactivate
from .storage import client


@skipUnless(
    os.getenv("RUN_STORAGE_TESTS") == "1",
    "Requires actual S3 service; run with RUN_STORAGE_TESTS=1.",
)
class LiveStorageTests(TestCase):
    def test_actual_private_upload_download_and_revocation(self):
        password = secrets.token_urlsafe(20)
        org = Organization.objects.create(name="Storage test")
        office = Office.objects.create(organization=org, name="Storage test office")
        members = []
        for name, role in [
            ("storage_manager", "manager"),
            ("storage_first", "advisor"),
            ("storage_second", "advisor"),
        ]:
            user = User.objects.create_user(username=name, password=password)
            members.append(
                Membership.objects.create(
                    organization=org, office=office, user=user, role=role
                )
            )
        manager, first, second = members

        def session(m):
            c = APIClient(enforce_csrf_checks=True)
            csrf = c.get("/api/v1/auth/csrf").json()["csrfToken"]
            response = c.post(
                "/api/v1/auth/login",
                {"username": m.user.username, "password": password},
                format="json",
                HTTP_X_CSRFTOKEN=csrf,
            )
            self.assertEqual(response.status_code, 200)
            c.credentials(HTTP_X_CSRFTOKEN=response.json()["csrfToken"])
            return c

        o = create_offering(
            first,
            {
                "kind": "apartment",
                "district": "نمونه",
                "area": 90,
                "exact_address": "نشانی ساختگی",
                "owner_name": "مالک ساختگی",
                "owner_phone": "09123456789",
                "transaction": "sale",
                "price_toman": 1234,
                "deposit_toman": 0,
                "rent_toman": 0,
            },
        )
        img = Image.new("RGB", (30, 30), "white")
        exif = Image.Exif()
        exif[270] = "private metadata"
        data = BytesIO()
        img.save(data, "JPEG", exif=exif)
        a = session(first)
        b = session(second)
        url = f"/api/v1/offerings/{o.id}/documents"
        response = a.post(
            url,
            {
                "file": SimpleUploadedFile(
                    "document.jpg", data.getvalue(), content_type="image/jpeg"
                )
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)
        doc = PrivateDocument.objects.get(pk=response.json()["id"])
        try:
            change_offering(first, o.id, {"version": 1}, "submit")
            change_offering(
                manager, o.id, {"version": 2, "decision": "approved"}, "review"
            )
            download = url + "/" + str(doc.id)
            self.assertEqual(b.get(download).status_code, 403)
            result = a.get(download)
            self.assertEqual(result.status_code, 200)
            self.assertFalse(Image.open(BytesIO(result.content)).getexif())
            self.assertIn("no-store", result["Cache-Control"])
            anonymous = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT,
                config=Config(signature_version=UNSIGNED),
                region_name="us-east-1",
            )
            with self.assertRaises(ClientError) as denied:
                anonymous.get_object(
                    Bucket=settings.S3_PRIVATE_BUCKET, Key=doc.storage_key
                )
            self.assertIn(
                denied.exception.response["ResponseMetadata"]["HTTPStatusCode"],
                [401, 403],
            )
            deactivate(manager, first.id, False)
            self.assertEqual(a.get(download).status_code, 403)
        finally:
            client().delete_object(
                Bucket=settings.S3_PRIVATE_BUCKET, Key=doc.storage_key
            )
