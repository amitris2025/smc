# ماژول‌های بهبود NTS / SMC (Pine Script v5)

هر فایل یک قطعهٔ قابل درج در اندیکاتور اصلی است. ترتیب درج مهم است؛
`src/SMC_NTS_Pro.pine` نسخهٔ کامل و یکپارچهٔ همین منطق را دارد.

| # | فایل | موضوع | خروجی‌های کلیدی |
|---|------|-------|-----------------|
| ۱ | `01_nts_mode_params.pine` | تفکیک حالت تریدینگ از تایم‌فریم پایه | `ntsPeriod`, `ntsFactor` |
| ۲ | `02_true_range_gaps.pine` | True Range و SMA رنج در TF پایه | `ntsHigh/Low/Close`, `ntsRangeSma`, `ntsTrueRange` |
| ۳ | `03_adx_atr_regime.pine` | رژیم رنج/روند با ADX + ATR | `atrNorm`, `chopRegime`, `trendRegime` |
| ۴ | `04_session_volatility_xau.pine` | سشن تهران + فیلتر ATR طلا | `xauTradeOk`, `ntsGoldenHourBonus` |
| ۵ | `05_dynamic_reversal_cloud.pine` | ابر ریورسال پویا و تماس نزدیک | `upper/lowerCloud1..3`, `revBuyOk`, `revSellOk` |
| ۶ | `06_confluence_scoring.pine` | امتیازدهی با کراس‌های پیش‌محاسبه‌شده | `ntsBuy/SellConfluencePts` |
| ۷الف | `07a_zone_volume_filters.pine` | PD بر اساس رنج روز قبل + حجم | `inDailyDiscount`, `inDailyPremium` |
| ۷ب | `07b_final_signals.pine` | Final با threshold و bar close | `finalBuySignal`, `finalSellSignal` |
| ۸ | `08_display_alerts.pine` | پنل و هشدار همهٔ گروه‌های Fib (جفت‌های Buy/Sell ادغام‌شده برای سقف ۶۴ plot) | `alertcondition`های Extension |
| ۹الف | `09a_symbol_detection.pine` | تشخیص Gold/Silver/Crypto/Forex | `autoSymbolType`, `xauMinAtrPctEff` |
| ۹ب | `09b_apply_autotune.pine` | ترکیب Auto-Tune با mode/TF/regime | `ntsPeriodFinal`, `ntsFactorFinal` |
| ۱۰ | `10_price_action_trendlines.pine` | خط روند بر پایهٔ پیوت‌های معتبر | `tlDnLine`, `tlUpLine` |
| ۱۱ | `11_nts_extensions_confirmed.pine` | موج، Extension، Wick، Pullback و CHoCH | سطوح 0.300 تا 10.618 و سیگنال‌های تأییدشده |

## ترتیب پیشنهادی درج

```text
input.*
  → 09a → 01 → 03 → 09b → 02 → هسته NTS با ntsOnBaseBar
  → پیوت‌ها/ساختار → 05 → 04 → PD/07a → 11 → 06 → 07b
  → 10 → نمایش و هشدارهای 08
```

## قراردادهای مهم ادغام

1. **MTF:** بخش ۲ باید با یک `request.security` پنج‌تایی درج شود تا
   `ta.sma(high - low, 14)` داخل context تایم‌فریم پایه اجرا شود. در TF پایین‌تر
   state تریل فقط وقتی `ntsHtfTime` عوض می‌شود آپدیت شود.
2. **موج:** `ntsExtreme` و `ntsTrail` موج جاری هر بار پایه بازتنظیم می‌شوند.
   هنگام تغییر روند، مقادیر موج قبلی در آرایه Snapshot ذخیره می‌شوند؛ خطوط تاریخی
   نباید از `activeWaveSize` موج جدید ساخته شوند.
3. **سطح:** فرمول Extension عمداً همان قرارداد کد است:
   `level = fib1 + direction * abs(trail - fib1) * (ratio - 1)`.
   بنابراین 0.300 در فاصلهٔ منفی 0.700 نسبت به Fib1 قرار دارد، نه «۳۰٪ کل موج».
4. **واکنش:** برای BUY، `low <= level` و `close > level`؛ برای SELL،
   `high >= level` و `close < level`. Wick واقعی از `min/max(open, close)`
   محاسبه می‌شود و با `barstate.isconfirmed` نهایی می‌گردد.
5. **ترتیب 1.470/2.100:** بلوغ موج → لمس بعد از شروع موج → واکنش → CHoCH مبتنی
   بر Pivot تأییدشده. فلگ لمس با تغییر/انقضای موج پاک می‌شود.
6. **تفکیک سیگنال:** 0.300/1.470/2.100 ادامه‌روند هستند و Hull/RSI/CHoCH
   می‌گیرند؛ 2.618 به بعد بازگشتی هستند و فیلتر location/momentum مستقل دارند.
7. **PD:** `pdHigh/pdLow` از `[high[1], low[1]]` تایم‌فریم D می‌آید و ناحیهٔ
   عملیاتی لبهٔ قابل تنظیم (پیش‌فرض ۵٪) است؛ EQ به‌تنهایی Discount/Premium نیست.
8. **هشدار:** همهٔ Extensionها هشدار گروهی مستقل دارند و هشدارها مستقیماً به
   شروطی متصل‌اند که قبلاً `barstate.isconfirmed` گرفته‌اند. جفت‌های Buy/Sell هر
   گروه عمداً در یک `alertcondition` جهت‌دار ادغام شده‌اند، چون هر
   `alertcondition` یک plot count مصرف می‌کند و سقف ۶۴ تایی خطای RE10140 می‌دهد.
   قبل از افزودن خروجی جدید، `python3 tools/check_plot_budget.py src/SMC_NTS_Pro.pine`
   اجرا شود (فعلاً ۴۹/۶۴).

## بررسی محلی

```bash
python3 tools/check_pine.py modules/
python3 tools/check_pine.py src/
```

این بررسی‌کننده جایگزین کامپایلر TradingView نیست؛ پس از درج، یک بار Add to
chart در TradingView برای بررسی محدودیت‌های نسخه/حساب اجرا شود.
