# اصلاحات نسخهٔ ادغام‌شده (Merged Fixed)

این فایل، خلاصهٔ ۱۰ اصلاح اعمال‌شده در `src/SMC_NTS_Pro_Merged_Fixed.pine` است.
همهٔ اصلاحات روی همان ساختار فایل ارسالی (بخش‌های ۱ تا ۴) اعمال شده‌اند.

## ۱. `f_atrAt()` — ایندکس تاریخی ATR در Auto Trendlines

**مشکل:** آرایهٔ `atrHistArr` از قدیمی به جدید ذخیره می‌شود، ولی تابع قبلی از ابتدای
آرایه می‌خواند (`offset` را به‌عنوان ایندکس مستقیم استفاده می‌کرد). در نتیجه تلورانس
لمس/شکست خط روند در کندل‌های قدیمی اشتباه می‌شد.

**اصلاح:**

```pine
f_atrAt(offset) =>
    int sz = array.size(atrHistArr)
    int idx = math.max(0, math.min(sz - 1, sz - 1 - offset))
    array.get(atrHistArr, idx)
```

## ۲. `doRedraw` — بازترسیم فقط روی آخرین کندل

**مشکل:** شرط قبلی `updateOnClose ? barstate.isconfirmed : barstate.islast`
در دادهٔ تاریخی روی تقریباً همهٔ کندل‌ها `true` بود و کل خطوط/لیبل‌ها/باکس‌ها و اسکن
خط روند در هر کندل تکرار می‌شد.

**اصلاح:**

```pine
bool doRedraw = barstate.islast and (not updateOnClose or barstate.isconfirmed)
```

نتیجه: رسم گرافیکی فقط روی آخرین کندل انجام می‌شود؛ با `updateOnClose=true` حتی در
کندل زنده هم تا لحظهٔ بسته‌شدن رسم نمی‌شود.

## ۳. `autoTuneThisChart` — ترکیب با تنظیمات کاربر

**مشکل:** قبلاً `ntsPeriod := autoPeriod` و `ntsFactor := autoFactor` وضعیت تریدینگ
و تایم‌فریم پایه را کاملاً بی‌اثر می‌کرد.

**اصلاح:**

```pine
if autoTuneThisChart
    ntsPeriod := int(math.round(math.max(4.0, math.min(40.0, autoPeriod * (basePeriod / 10.0)))))
    ntsFactor := math.max(1.5, math.min(20.0, autoFactor * (baseFactor / 3.5)))
```

## ۴. تشخیص نوع نماد — کریپتو قبل از forex

**مشکل:** برای `BTCUSD` شرط `USD` قبل از `BTC` بررسی می‌شد و به‌اشتباه forex
انتخاب می‌شد.

**اصلاح:**

```pine
autoSymbolType = 
     str.contains(symU, "XAU") or str.contains(symU, "GOLD") ? "gold" :
     str.contains(symU, "XAG") ? "silver" :
     str.contains(symU, "BTC") or
     str.contains(symU, "ETH") or
     str.contains(symU, "SOL") ? "crypto" :
     str.contains(symU, "USD") and not str.contains(symU, "USDT") ? "forex" :
     "other"
```

## ۵. NTS MTF — محاسبهٔ SMA داخل تایم‌فریم پایه

**مشکل:** قبلاً `ntsHiLo` از `ta.sma(ntsHigh-ntsLow,14)` استفاده می‌کرد که روی
تایم‌فریم چارت و با داده‌های تکراری MTF محاسبه می‌شد.

**اصلاح:** همهٔ مقادیر شامل `time` و `ta.sma(high-low,14)` در یک‌بار `request.security`
بازگردانده می‌شوند:

```pine
[ntsHigh, ntsLow, ntsClose, ntsHtfTime, ntsRangeSma] =
     request.security(ntsTicker, ntsResolution,
          [high, low, close, time, ta.sma(high - low, 14)],
          barmerge.gaps_off, barmerge.lookahead_off)
ntsHiLo = math.min(ntsHigh - ntsLow, 1.5 * nz(ntsRangeSma))
```

## ۶. Hull HTF — کاهش ری‌پینت

**مشکل:** مقادیر Hull تایم‌فریم بالاتر در کندل زنده تا بسته‌شدن آن کندل تغییر می‌کرد.

**اصلاح:**

```pine
HULL = hullUseHTF
     ? request.security(syminfo.tickerid, hullHTF, _hullRaw[1], barmerge.gaps_off, barmerge.lookahead_on)
     : _hullRaw
```

و هشدارها:

```pine
alertcondition(barstate.isconfirmed and ta.crossover(MHULL, SHULL), ...)
alertcondition(barstate.isconfirmed and ta.crossover(SHULL, MHULL), ...)
```

## ۷. آستانهٔ Confluence در سیگنال‌های نهایی

**مشکل:** `finalBuySignal`/`finalSellSignal` امتیاز `ntsBuyConfluencePts`/
`ntsSellConfluencePts` را الزام نمی‌کردند.

**اصلاح:** شرط‌های زیر اضافه شد:

```pine
finalBuySignal = ... and ntsBuyConfluencePts >= ntsBuyThreshold
finalSellSignal = ... and ntsSellConfluencePts >= ntsSellThreshold
```

## ۸. یکسان‌سازی Premium/Discount

**مشکل:** بخش اصلی از `dailyOpen` و بخش PD از `pdHigh/pdLow` استفاده می‌کرد.

**اصلاح:** `pdHigh/pdLow` قبل از بخش امتیازدهی تعریف شد و تعریف نهایی ناحیه‌ها بر
اساس رنج روز قبل است:

```pine
[pdHigh, pdLow] = request.security(syminfo.tickerid, "D", [high[1], low[1]], barmerge.gaps_off, barmerge.lookahead_on)
prevDayRange = not na(pdHigh) and not na(pdLow) ? pdHigh - pdLow : na
eqLevel = not na(prevDayRange) and prevDayRange > 0 ? (pdHigh + pdLow) / 2 : na
inDailyDiscount = not na(prevDayRange) and prevDayRange > 0 and close <= pdLow + prevDayRange * 0.05
inDailyPremium  = not na(prevDayRange) and prevDayRange > 0 and close >= pdLow + prevDayRange * 0.95
```

تکرارِ `[pdHigh, pdLow] = request.security(...)` در بخش ۴ حذف شد.

## ۹. Smart Divergence — ورودی‌های بلااستفاده

- `smartDivTrendAdjust` در `smartDivPivotLeft` اعمال شد.
- `smartDivBullTrend` / `smartDivBearTrend` به امتیاز اضافه شدند.
- `smartDivEffectiveMinScore` اضافه شد که وقتی `smartDivShowMinor=true` است،
  واگرایی‌های با امتیاز پایین‌تر (حداقل ۴۰) هم رسم/هشدار کاندید می‌شوند،
  ولی تأیید نهایی همچنان به `smartDivMinScore` نیاز دارد.

## ۱۰. مدیریت لیبل

- لیبل‌های Smart Divergence (تأیید، کاندید، مثلث) در پول `smartDivLabels` با سقف ۱۲۰
  نگهداری و لیبل قدیمی حذف می‌شود.
- رسم خطوط/لیبل/باکس بخش ۴ فقط آخرین کندل انجام می‌شود (اصلاح ۲)، بنابراین `touch marks`
  و `swing marks` در تاریخچه تکرار نمی‌شوند.
- لیبل‌های شکست/تلاقی (بخش ۱۳) به `barstate.isconfirmed` محدود شدند تا در کندل زنده
  تکرار نشوند.

## بررسی

- `python3 tools/check_pine.py src/SMC_NTS_Pro_Merged_Fixed.pine` → OK
- `python3 tools/check_pine.py modules/ src/` → OK
- هنوز کامپایلر رسمی TradingView در دسترس نیست؛ قبل از استفادهٔ واقعی یک‌بار
  «Add to chart» را در TradingView اجرا کنید.
