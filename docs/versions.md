# نسخه‌ها و منابع رسمی — بررسی ۲۰۲۶/۱۰/۲۶

| جزء | نسخه ثابت | شاهد |
|---|---|---|
| Python | 3.12.14 | همان نسخه محیط؛ Django و DRF آن را پشتیبانی می‌کنند |
| Django | 5.2.18 LTS | https://www.djangoproject.com/download/ |
| Django REST Framework | 3.18.3 | https://www.django-rest-framework.org/community/release-notes/ و https://www.django-rest-framework.org/ |
| Next.js | 16.4.3 | نسخه پایدار موجود در registry؛ بالاتر از اصلاحیه امنیتی 16.4.1: https://nextjs.org/blog/nextjs-security-update-october-14-2026 |
| React | 19.3.1 | package-lock.json و نصب و build موفق با Next 16.4.3 |
| TypeScript | 7.0.2 | بررسی نوع و build موفق |
| Tailwind CSS | 4.3.3 | pipeline رسمی PostCSS و build موفق |
| Node | 24.22.1 | نسخه runtime حاضر و پایه Docker ثابت |
| PostgreSQL | 17.11 | https://www.postgresql.org/support/versioning/ ؛ شاخه ۱۷ پشتیبانی‌شده، استفاده یکسان در توسعه و آزمون Compose |
| Nginx | 1.30.6 | https://nginx.org/news.html ؛ اصلاحیه پایدار ۱۴ اکتبر ۲۰۲۶ |
| SeaweedFS S3 | 4.51 | https://github.com/seaweedfs/seaweedfs/releases و https://github.com/seaweedfs/seaweedfs/blob/master/README.md ؛ حالت mini تک‌گره‌ای، credential الزامی |

MinIO در بررسی رسمی archived اعلام شده بود؛ بنابراین وابستگی اولیه کنار گذاشته شد و SeaweedFS انتخاب شد. هیچ پورت ذخیره‌ساز، پایگاه داده یا پنل زیرساخت روی میزبان منتشر نشده است. جابه‌جایی به ارائه‌دهنده S3 دیگر با env انجام می‌شود؛ init_storage را فقط روی bucketهای متعلق به همین نصب اجرا کنید.

تمام وابستگی‌های مستقیم و گذرا Python در backend/requirements.lock و Node در frontend/package-lock.json ثابت‌اند. تصویرهای Docker با tag مشخص ثابت‌اند؛ digest واقعی باید پس از pull موفق در محیط استقرار ثبت شود. در این محیط Docker وجود نداشت، بنابراین pull یا صحت tag تصویرها اجرا و تأیید نشده است.

npm audit وابستگی‌های runtime در زمان بررسی: صفر مورد گزارش‌شده؛ این نتیجه جایگزین آزمون امنیت و کنترل به‌روزرسانی پیش از نصب مشتری نیست.
