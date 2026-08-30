# smc — اندیکاتور SMC + NTS و ۹ بهبود آن

مخزن شامل پیاده‌سازی ۹ بهبود برای هستهٔ NTS و سیستم امتیازدهی Confluence
در اندیکاتور Smart Money Concepts، به زبان **Pine Script v5**.

## ساختار

```
modules/   قطعات مستقلِ هر بهبود (برای درج در اندیکاتور اصلی)
           00_INDEX.md  ← ترتیب درج و وابستگی‌ها را اینجا ببینید
src/       اندیکاتور مرجع و کاملِ قابل‌اجرا (SMC_NTS_Pro.pine)
docs/      مستندات (خلاصه بهبودها، موانع ادغام)
tools/     check_pine.py — بررسی نحو و کاراکترهای نامرئی
```

## شروع سریع

```bash
# بررسی سلامتِ قطعات (باید OK چاپ کند)
python3 tools/check_pine.py modules/

# بررسی اندیکاتور مرجع
python3 tools/check_pine.py src/

# دیدن نمونهٔ خطاها روی نسخهٔ اولیهٔ ارسالی
python3 tools/check_pine.py tools/testdata/original_snippets_BAD.pine

# شبیه‌سازیِ منطقِ خطوط روند روی داده‌ی مصنوعی (خروجی: tools/sample_trendlines.png)
python3 tools/sim_trendlines.py
```

## وضعیت فعلی

- `modules/0*.pine` — ۱۲ قطعه، آمادهٔ درج در اندیکاتور اصلی شما
- `src/SMC_NTS_Pro.pine` — نسخهٔ مرجعِ کامل (هسته پایه + ۹ بهبود)،
  که تا وقتی فایل اصلی‌تان را نفرستاده‌اید، قابل اجرا و تست است
- `modules/10_trendlines_pa.pine` — خطوط روندِ اصولیِ پرایس‌اکشن
  (حداقل ۲ سقف برای نزولی / ۲ کف برای صعودی) همراه با ناحیهٔ
  Previous Daily Premium / Discount؛ شرحِ کامل در
  [`docs/TRENDLINES.md`](docs/TRENDLINES.md)
- در انتظار دریافت فایل `.pine` اصلی برای ادغامِ اختصاصی

## نکات کلیدی ادغام

سه مانع فنی که هنگام ادغام باید حل شوند در
[`docs/IMPROVEMENTS.md`](docs/IMPROVEMENTS.md) توضیح داده شده‌اند:

1. `simple int` در برابر `series int` برای طولِ توابع `ta.*`
2. ممنوعیت بازنویسی ورودی‌ها (`input.*`)
3. ترتیب تعریف متغیرها (M07a باید قبل از M06 بیاید)
