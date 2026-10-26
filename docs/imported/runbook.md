# راهنمای اجرای هسته و مرحله دوم

پیش‌نیاز: Docker Engine و Docker Compose v2 روی سیستم شخصی یا سرور آزمایش، و Python 3 برای تولید env. هیچ انتشار عمومی در این پروژه انجام نشده است.

## اجرای محلی

از ریشه پروژه:

```bash
python3 infra/init_env.py
docker compose up --build -d
docker compose logs migrate storage-init
docker compose run --rm backend python manage.py seed_demo
```

init_env فقط یک‌بار اجرا می‌شود و فایل موجود را بازنویسی نمی‌کند. دستور seed_demo یک مدیر و دو مشاور با نام‌های manager،advisor1 و advisor2 و رمز تصادفی تولید می‌کند و همان زمان در ترمینال نشان می‌دهد. هیچ رمز ثابتی در سورس نیست. seed روی بانک غیرخالی اجرا نمی‌شود. خروجی رمزها را عمومی نکنید.

رابط: http://localhost:8080

OpenAPI پس از ورود: http://localhost:8080/api/schema/ و http://localhost:8080/api/docs/

Swagger صفحه مستندات است؛ احراز هویت فرم اصلی سامانه استفاده شود. برای درخواست‌های تغییردهنده از ابزار API، CSRF token باید از /api/v1/auth/csrf گرفته و بعد از ورود تازه شود.

راه‌اندازی بدون نمونه و مخصوص مشتری، به‌جای seed_demo:

```bash
docker compose run --rm backend python manage.py bootstrap_office --organization 'مجموعه مشتری' --office 'دفتر مشتری' --city 'شهر مشتری' --username office_manager
```

رمز مدیر به صورت تعاملی و دوبار دریافت می‌شود. مدیریت اعضا از صفحه «مشاوران» است؛ فقط حساب مشاور ساخته می‌شود و فیلد نقش از مرورگر پذیرفته نمی‌شود. Django superuser به‌تنهایی عضویت عملیاتی ایجاد نمی‌کند و جایگزین bootstrap نیست.

## توسعه با بارگذاری مجدد

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
```

توسعه نیز از همان PostgreSQL استفاده می‌کند. SQLite در هیچ تنظیمی وجود ندارد.

## آزمون‌ها

```bash
docker compose run --rm backend python manage.py test core crm --noinput
docker compose run --rm backend python manage.py check
docker compose run --rm backend python manage.py makemigrations --check --dry-run
docker compose run --rm backend python manage.py spectacular --file /tmp/openapi.yaml --validate
cd frontend
npm ci
npm run typecheck
npm run build
```

آزمون Django بانک test_estate جدا می‌سازد. کاربر POSTGRES_USER در Compose توسعه مجوز ایجاد آن را دارد. این دستور را روی نصب عملیاتی با داده واقعی اجرا نکنید؛ محیط آزمون جدا باشد. آزمون‌های امنیتی APIClient، نشست واقعی Django و PostgreSQL واقعی دارند و اتصال بانک mock نمی‌شود.

آزمون اختصاصی S3، پس از موفق‌شدن storage-init:

```bash
docker compose run --rm -e RUN_STORAGE_TESTS=1 backend python manage.py test core.test_live_storage --noinput
```

## سناریوی بررسی دستی

۱. با manager وارد شوید؛ یک مشاور تازه بسازید یا حساب آزمایشی را غیرفعال/فعال کنید.
۲. با advisor1 در مرورگر یا نمایه جدا وارد شوید و ملک و عرضه پیش‌نویس بسازید.
۳. با advisor2 نبود پیش‌نویس را بررسی کنید؛ URL دقیق نیز نباید مجاز باشد.
۴. advisor1 «ارسال برای بررسی» را بزند؛ manager با دلیل برگرداند؛ advisor1 اطلاعات یا قیمت را اصلاح و دوباره ارسال کند.
۵. manager تأیید کند؛ عرضه در «بانک مشترک» advisor2 ظاهر شود. پاسخ شبکه فقط فیلدهای مجاز داشته باشد.
۶. اطلاعات خصوصی برای manager و advisor1 با درخواست مستقل و ثبت contact.view در رویدادها دریافت شود. advisor2 مجوز ندارد؛ ساخت URL نیز 403 می‌گیرد.
۷. همان پیش‌نویس را در دو پنجره باز و قیمت را ویرایش کنید؛ پنجره دوم باید 409 و امکان بارگذاری نسخه جدید بگیرد.
۸. manager مشاور را غیرفعال کند؛ درخواست بعدی نشست قبلی 403 می‌شود. فعال‌سازی دوباره نیز همان نشست قدیمی را احیا نمی‌کند؛ ورود تازه لازم است.
۹. مدرک تصویری واقعی فقط در محیط آزمایشی مجاز بارگذاری شود؛ کاربر دیگر نتواند آن را دانلود کند. ذخیره‌ساز قطع باشد، 503 دریافت می‌شود و موفقیت اعلام نمی‌شود.

## تولید

.env را برای دامنه مشتری تنظیم کنید: DEBUG=0، ALLOWED_HOSTS و CSRF_TRUSTED_ORIGINS با دامنه HTTPS. سپس:

```bash
docker compose -f compose.yaml -f compose.production.yaml up --build -d
```

Nginx داخلی فقط روی loopback:8080 است. TLS reverse proxy میزبان باید https را خاتمه و به 127.0.0.1:8080 هدایت کند؛ پیکربندی عملیاتی داخل پروژه فقط در همین توپولوژی معتبر است. کوکی در تولید Secure است؛ ورود با HTTP به‌درستی کار نخواهد کرد. قبل از هر عرضه تجاری باید آزمون یکپارچه، رسانه، مرورگر و بازیابی در محیط استقرار قبول شوند.

تنظیمات مجموعه/دفتر در جدول‌هاست. branding JSON می‌تواند color و logo و contact داشته باشد؛ رابط کنونی فقط نام و رنگ شش‌رقمی hex را نمایش می‌دهد. صفحه ویرایش کامل تنظیمات هنوز ساخته نشده است.

## پشتیبان و بازیابی

dump بانک، نسخه هم‌زمان داده ذخیره‌ساز، .env و کلید FIELD_ENCRYPTION_KEY جداگانه و امن نگهداری شوند. بدون این کلید اطلاعات رمزنگاری‌شده قابل بازیابی نیستند.

```bash
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/database.dump
```

برای snapshot رسانه، ابتدا تغییرهای برنامه را متوقف کنید و از volume رسانه در همان نقطه زمانی نسخه بگیرید. نسخه dump را در محیط کاملاً جدا، بانک خالی و با همان کلید رمزنگاری بازیابی و دسترسی به مدارک را بررسی کنید:

```bash
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' < backups/database.dump
```

restore باید فقط در نصب خالی و مجزا اجرا شود. migrationهای حفاظتی برگشت خودکار ندارند؛ downgrade یا بازگردانی داده روی نصب فعال بدون نسخه پشتیبان آزمایش‌شده پشتیبانی نمی‌شود. آزمون restore در محیط این گفتگو اجرا نشده است.

## ادامه مرحله دوم

راهنمای قابلیت‌ها، ارتقا، seed_crm_demo و سناریوی بررسی در [phase2.md](phase2.md) است. برای آزمون واقعی هر دو مرحله همراه S3 در محیط جدا: `sh infra/verify.sh`.
