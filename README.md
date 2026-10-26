# سامانه مستقل مدیریت تخصصی دفتر املاک

نسخه اول تک‌دفتره: Next.js/React/TypeScript/Tailwind + Django 5.2 LTS/DRF + PostgreSQL، نشست امن و مسیر ثبت/بررسی عرضه. محصول وابسته به نام یا سیاست مشتری قبلی نیست.

**وضعیت جاری: قابلیت‌های اصلی نسخه اول ساخته و در محیط مجازی اجرا شده‌اند؛ ۸۸ آزمون با PostgreSQL و S3 واقعی موفق است.** تنظیمات دفتر، بازنگری، ویترین و حساب مشتری، دعوت، گزارش، یادآور داخلی و مالی نسخه‌دار به هسته قبلی اضافه شده‌اند. [راهنمای تحویل و حدود نسخه](docs/release-v1.md). استقرار عمومی، OTP/پیامک و تعرفه واقعی خودکار فعال نیستند.

```bash
python3 infra/init_env.py
docker compose up --build -d
docker compose logs migrate storage-init
docker compose run --rm backend python manage.py seed_demo
docker compose run --rm backend python manage.py test core crm business --noinput
```

رابط محلی: http://localhost:8080

حساب‌های manager و advisor1 و advisor2 با رمزهای تصادفی زمان اجرای seed_demo ساخته می‌شوند. فقط روی بانک خالی اجرا کنید. برای نصب مشتری، bootstrap_office جایگزین seed است؛ راهنمای کامل در docs/runbook.md آمده است.

- [دستور اجرا، آزمون و استقرار](docs/runbook.md)
- [وضعیت اجرا و ادامه کار](docs/status.md)
- [تصمیم‌ها و حل تعارض اسناد](docs/architecture-decisions.md)
- [مرز ماژول‌ها و مراحل](docs/modules-and-stages.md)
- [چهار منبع خوانده‌شده](docs/sources.md)
- [نسخه‌ها و منابع رسمی](docs/versions.md)
- [قرارداد OpenAPI](docs/openapi.yaml)

مرحله دوم، مشتری/تقاضا/تطبیق/همکاری/بازدید/پیگیری و اعلان داخلی را اضافه می‌کند. [راهنمای کامل مرحله دوم](docs/phase2.md).

برای آزمون کامل در محیط آزمایشی دارای Docker: `sh infra/verify.sh`.

منطق حساس: backend/core/services.py و backend/crm/services.py؛ سیاست نشست: backend/core/middleware.py؛ مدل و قیود بانک: backend/core/models.py و migrations/؛ آزمون دسترسی: backend/core/tests.py.

هیچ استقرار اینترنتی انجام نشده است. ویترین و مالی در محیط مجازی کار می‌کنند؛ پیامک، پنل مستقل سازندگان و چنددفتره عملیاتی خارج نسخه اول‌اند.
