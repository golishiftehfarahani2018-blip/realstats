"""Generate local secrets once. Never overwrite an existing env file."""

from pathlib import Path
import secrets, base64

p = Path(".env")
if p.exists():
    raise SystemExit(".env exists; refusing to overwrite secrets")
text = Path(".env.example").read_text()
for name, value in {
    "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
    "FIELD_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
    "S3_ACCESS_KEY": secrets.token_hex(12),
    "S3_SECRET_KEY": secrets.token_urlsafe(32),
}.items():
    text = text.replace(name + "=\n", name + "=" + value + "\n")
p.write_text(text)
p.chmod(0o600)
print(".env generated; keep it private and back up encryption key separately.")
