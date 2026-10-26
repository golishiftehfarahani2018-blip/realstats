import uuid
from io import BytesIO
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError, APIException
from PIL import Image, UnidentifiedImageError


class StorageUnavailable(APIException):
    status_code = 503
    default_detail = "ذخیره‌ساز در دسترس نیست؛ عملیات موفق اعلام نشده است."


def client():
    if not settings.S3_ACCESS_KEY or not settings.S3_SECRET_KEY:
        raise StorageUnavailable()
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name="us-east-1",
    )


def image_bytes(f):
    if f.size > 8 * 1024 * 1024:
        raise ValidationError("حداکثر حجم تصویر ۸ مگابایت است.")
    try:
        img = Image.open(f)
        if img.format not in ["JPEG", "PNG"] or img.width * img.height > 24000000:
            raise ValidationError("فقط تصویر JPEG یا PNG تا ۲۴ مگاپیکسل مجاز است.")
        img.load()
        output = BytesIO()
        img.convert("RGB").save(output, "JPEG", quality=88)
        return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError("تصویر معتبر نیست.")


def save_private(f):
    # Image documents only in phase 1. PDF and video require a later scanner pipeline.
    content = image_bytes(f)
    key = f"documents/{uuid.uuid4()}.jpg"
    try:
        client().put_object(
            Bucket=settings.S3_PRIVATE_BUCKET,
            Key=key,
            Body=content,
            ContentType="image/jpeg",
        )
    except (BotoCoreError, ClientError):
        raise StorageUnavailable()
    return key, "image/jpeg"


def download_private(doc):
    try:
        content = (
            client()
            .get_object(Bucket=settings.S3_PRIVATE_BUCKET, Key=doc.storage_key)["Body"]
            .read()
        )
    except (BotoCoreError, ClientError):
        raise StorageUnavailable()
    response = HttpResponse(content, content_type=doc.content_type)
    response["Content-Disposition"] = 'attachment; filename="document.jpg"'
    return response
