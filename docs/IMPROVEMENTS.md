# اصلاحات NTS / SMC و منطق Extension

این مخزن علاوه بر ۹ بهبود اولیه و خط روند Price Action، ایرادهای منطقی
بررسی‌شده در هستهٔ NTS و Extensionها را نیز اصلاح می‌کند.

| # | بهبود | وضعیت |
|---|-------|-------|
| ۱ | تفکیک حالت تریدینگ و تایم‌فریم پایه | ✅ |
| ۲ | True Range با گپ + SMA در TF پایه | ✅ |
| ۳ | تشخیص رژیم با ADX + ATR نرمال‌شده | ✅ |
| ۴ | سشن تهران و فیلتر نوسان XAU | ✅ |
| ۵ | Reversal Cloud پویا با نزدیکی فعلی | ✅ |
| ۶ | Confluence و کراس‌های پیش‌محاسبه‌شده | ✅ |
| ۷ | Premium/Discount از رنج روز قبل | ✅ |
| ۸ | پنل و هشدارهای مستقل Extension | ✅ |
| ۹ | تشخیص نماد و Auto-Tune ترکیبی | ✅ |
| ۱۰ | خط روند Price Action از Pivotهای تأییدشده | ✅ |
| ۱۱ | مدیریت موج، واکنش Wick، Pullback و CHoCH | ✅ |

## اصلاحات هستهٔ MTF

در نسخهٔ قبلی `ntsHigh`، `ntsLow` و `ntsClose` جداگانه درخواست می‌شدند و
`ta.sma(ntsHigh - ntsLow, 14)` روی تایم‌فریم نمودار اجرا می‌شد. روی M5 با NTS
پایهٔ M15، یک کندل M15 چند بار تکرار می‌شود و این SMA معادل ۱۴ کندل M15 نیست.

اکنون یک tuple واحد استفاده می‌شود:

```pine
[ntsHigh, ntsLow, ntsClose, ntsHtfTime, ntsRangeSma] = request.security(
     ntsTicker, ntsBaseTimeframe,
     [high, low, close, time, ta.sma(high - low, 14)],
     gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
```

`ntsOnBaseBar` تغییر `ntsHtfTime` را تشخیص می‌دهد و state مربوط به Wilders ATR،
باند و روند فقط یک بار برای هر نمونهٔ پایه به‌روزرسانی می‌شود. `ntsReadyBars`
نیز از شروع سیگنال با روند فرضی جلوگیری می‌کند.

## مرجع موج و فرمول Extension

دو مسئله از هم جدا شده‌اند:

1. **موج جاری عملیاتی:** `ntsExtreme` و `ntsTrail` در هر نمونهٔ پایه جاری هستند؛
   بنابراین `activeWaveSize` در تمام طول موج ثابتِ اشتباه نمی‌ماند.
2. **موج کامل‌شده تاریخی:** هنگام تغییر روند، Extreme/Trail/Fib1 و جهت موج قبلی
   در آرایه ذخیره می‌شوند. خطوط تاریخی از همین Snapshot ساخته می‌شوند و از
   اندازهٔ موج بعدی تأثیر نمی‌گیرند.

تنظیم `ntsExtensionWaveMode` امکان استفاده از مرجع ثابت را هم می‌دهد. در حالت
ثابت، Extensionهای نمایش و اهداف از آخرین موج کامل‌شده می‌آیند؛ برای جلوگیری از
مخلوط‌شدن semantics، سیگنال‌های continuation فقط در حالت موج جاری فعال‌اند.

فرمول عمداً تغییر نکرده است:

```text
level = fib1 + direction * abs(trail - fib1) * (ratio - 1)
```

بنابراین 0.300 در فاصلهٔ `-0.700 * waveSize` نسبت به Fib1 قرار دارد. این با
۳۰٪ کل رنج یکی نیست، اما حالا همین قرارداد در رسم، سیگنال و Snapshot استفاده
می‌شود.

## واکنش قیمت و ترتیب سیگنال

توابع `buyReactionConfirmed` و `sellReactionConfirmed` موارد زیر را کنترل
می‌کنند:

- لمس سطح با High/Low؛
- برگشت کلوز به سمت درست سطح؛
- رنگ کندل و حداقل نسبت بدنه؛
- Wick واقعی با `max(open, close)` یا `min(open, close)`؛
- engulfing به‌عنوان جایگزین Wick؛
- `barstate.isconfirmed` در شروط نهایی.

برای 1.470 و 2.100 فلگ Pullback فقط بعد از `ntsWaveMaturityBars` فعال می‌شود،
در تغییر روند پاک می‌شود و بعد از `ntsContinuationMaxBars` منقضی می‌گردد.
CHoCH از Pivot تأییدشدهٔ آخر (`ta.pivothigh/ta.pivotlow`) می‌آید و می‌تواند
حداقل بدنه و حجم را نیز الزام کند؛ Highest/Lowest خام دیگر ساختار CHoCH نیست.

## تفکیک سیگنال‌ها

- **Continuation:** 0.300، 1.470 و 2.100؛ موج هم‌جهت، Pullback و در سطوح
  1.470/2.100 CHoCH، همراه Hull و چرخش RSI.
- **Reversal Extension:** 2.618/3.000، 4.414/4.764، 6.618/8.618 و 10.618؛
  واکنش Wick/بدنه، location/momentum ابر و cooldown مستقل. این گروه به
  `ntsSellTrendOk` یا `ntsBuyTrendOk` عمومی وابسته نیست.
- **Final Trend Confluence:** شرط جداگانه‌ای است که Hull، ساختار، KD، PD و
  حداقل Confluence را با هم می‌خواهد.

برای 10.618 محدودیت فاصلهٔ ATR (`ntsMaxExtensionAtr`) اضافه شده است تا سطحی
که از نظر نموداری بسیار دور است، به‌صورت سیگنال عملیاتی تصادفی تفسیر نشود.

## Smart Divergence

موتور Smart Divergence با Pivotهای ثابت و تأییدشدهٔ قیمت، RSI، MACD، Stoch،
Twist، فاصلهٔ ATR و حجم امتیاز می‌سازد. `smartDivEffectiveMinScore` در حالت
نمایش واگرایی متوسط آستانه را پایین می‌آورد، درحالی‌که تأیید نهایی همچنان
`smartDivMinScore` و شکست ساختار را می‌خواهد. `smartDivTrendAdjust`،
`smartDivVolAdjust` و `smartDivBullTrend/smartDivBearTrend` در امتیاز مؤثرند؛
لیبل‌ها و zoneهای اختیاری نیز با آرایهٔ محدودشده مدیریت می‌شوند.

## Premium / Discount و Cloud

`pdHigh/pdLow` از `[high[1], low[1]]` تایم‌فریم روزانه می‌آیند. ناحیهٔ عملیاتی
و نمایش روزانه با یک `dailyZoneEdgePct` مشترک ساخته می‌شوند؛ EQ به‌تنهایی
Premium یا Discount محسوب نمی‌شود.

برای Cloud، `ta.barssince` فقط تماس نزدیک اخیر را نگه می‌دارد و علاوه بر آن
فاصلهٔ فعلی Close تا `cloudBasis` کنترل می‌شود. تماس ۱۲ کندل قبل، بدون نزدیک
بودن قیمت فعلی، دیگر به‌تنهایی فیلتر برگشت نیست.

## کنترل ری‌پینت و هشدار

- دادهٔ HTF با `lookahead_off` گرفته می‌شود.
- Hull در حالت HTF با مقدار `[1]` و `lookahead_on` استفاده می‌شود؛ چون مقدار
  قبلی است، مقدار تأییدشده و غیرری‌پینتی است.
- سیگنال‌ها و alertconditionها از شروطی استفاده می‌کنند که
  `barstate.isconfirmed` دارند.
- رسم خطوط فعلی در تنظیم `updateOnClose` فقط روی آخرین کندل بسته‌شده به‌روز
  می‌شود.

## محدودیت ابزار بررسی

`tools/check_pine.py` بررسی سبک است و جایگزین کامپایلر TradingView نیست. به‌دلیل
تفاوت نسخه‌ها و محدودیت‌های حساب TradingView، پس از درج `src/SMC_NTS_Pro.pine`
در Pine Editor باید یک بار Add to chart انجام شود.
