from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


def cipher():
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


class EncryptedTextField(models.TextField):
    def from_db_value(self, value, expression, connection):
        return cipher().decrypt(value.encode()).decode() if value else value

    def get_prep_value(self, value):
        return cipher().encrypt(str(value).encode()).decode() if value else value
