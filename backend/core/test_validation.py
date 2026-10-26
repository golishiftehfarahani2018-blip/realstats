from io import BytesIO
from django.test import SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.exceptions import ValidationError
from .serializers import OfferingInput, LoginInput, AdvisorInput
from .storage import image_bytes, client, StorageUnavailable


class BoundaryValidationTests(SimpleTestCase):
    def payload(self):
        return {
            "kind": "apartment",
            "district": "كيان",
            "area": "٩٠",
            "exact_address": "نشانی ساختگی",
            "owner_name": "نام ساختگی",
            "owner_phone": "٠٩١٢٣٤٥٦٧٨٩",
            "transaction": "sale",
            "price_toman": "۱۲۳۴",
        }

    def test_persian_arabic_normalization(self):
        v = OfferingInput(data=self.payload())
        self.assertTrue(v.is_valid(), v.errors)
        self.assertEqual(v.validated_data["district"], "کیان")
        self.assertEqual(v.validated_data["area"], 90)
        self.assertEqual(v.validated_data["price_toman"], 1234)
        self.assertEqual(v.validated_data["owner_phone"], "09123456789")

    def test_money_is_strict_integer(self):
        for price in [1.2, True, "1.0", -1, 9223372036854775808]:
            d = self.payload()
            d["price_toman"] = price
            self.assertFalse(OfferingInput(data=d).is_valid())

    def test_reject_authority_fields(self):
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
            self.assertFalse(OfferingInput(data=d).is_valid())

    def test_passwords_are_never_normalized(self):
        raw = "  Password-كي۱۲٣  "
        v = LoginInput(data={"username": "first", "password": raw})
        self.assertTrue(v.is_valid())
        self.assertEqual(v.validated_data["password"], raw)
        v = AdvisorInput(
            data={"username": "first", "first_name": "كيان", "password": raw}
        )
        self.assertTrue(v.is_valid(), v.errors)
        self.assertEqual(v.validated_data["password"], raw)

    def test_reencode_strips_exif_gps(self):
        img = Image.new("RGB", (20, 20), "white")
        exif = Image.Exif()
        exif[270] = "Private address"
        exif[315] = "Owner"
        source = BytesIO()
        img.save(source, "JPEG", exif=exif)
        output = image_bytes(
            SimpleUploadedFile(
                "source.jpg", source.getvalue(), content_type="image/jpeg"
            )
        )
        self.assertFalse(Image.open(BytesIO(output)).getexif())
        self.assertNotIn(b"Private address", output)

    def test_reject_spoofed_mime(self):
        with self.assertRaises(ValidationError):
            image_bytes(
                SimpleUploadedFile(
                    "photo.jpg",
                    b"<script>not an image</script>",
                    content_type="image/jpeg",
                )
            )

    def test_reject_oversized_upload(self):
        f = SimpleUploadedFile("big.jpg", b"")
        f.size = 9 * 1024 * 1024
        with self.assertRaises(ValidationError):
            image_bytes(f)

    @override_settings(S3_ACCESS_KEY="", S3_SECRET_KEY="")
    def test_no_fake_storage_success(self):
        with self.assertRaises(StorageUnavailable):
            client()
