# ماژول‌های بهبود NTS / SMC (Pine Script v5)

هر فایل یک «بهبود» مستقل است که می‌تواند به صورت قطعه‌قطعه در اندیکاتور اصلی شما درج شود.
ترتیب درج بسیار مهم است (ستون «ترتیب»).

| # | فایل | موضوع | ترتیب درج | خروجی‌های کلیدی |
|---|------|-------|-----------|-----------------|
| ۱ | `01_nts_mode_params.pine` | تفکیک حالت تریدینگ از تایم‌فریم پایه | بعد از تعریف ورودی‌های `ntsTradingMode` / `ntsBaseTimeframe` | `ntsPeriod`, `ntsFactor`, `basePeriod`, `baseFactor` |
| ۲ | `02_true_range_gaps.pine` | True Range دقیق‌تر با وزن گپ | داخل/قبل از هسته محاسبه NTS | `ntsTrueRange`, `ntsGapUp`, `ntsGapDown`, `ntsGapAdjustment` |
| ۳ | `03_adx_atr_regime.pine` | تشخیص رژیم روند/رنج با ADX+ATR | **بعد از ۱**، قبل از استفاده از `ntsPeriod` | `atrNorm`, `chopRegime`, `trendRegime` + تنظیم پویای `ntsPeriod` |
| ۴ | `04_session_volatility_xau.pine` | فیلتر سشن و نوسان برای XAUUSD | بعد از ۳ و ۹a، قبل از ۶ | `xauNyHour`, `xauInSession`, `xauGoldenHour`, `xauVolOk`, `xauTradeOk`, `ntsGoldenHourBonus` |
| ۵ | `05_dynamic_reversal_cloud.pine` | Reversal Cloud پویا بر اساس ATR | بعد از محاسبه `cloudBasis`/`cloudRange` و `atrNorm` (ماژول ۳) | `upperCloud1..3`, `lowerCloud1..3`, `revBuyOk`, `revSellOk` |
| ۶ | `06_confluence_scoring.pine` | سیستم امتیازدهی Confluence | بعد از ۵ و **۷a** | `ntsBuyConfluencePts`, `ntsSellConfluencePts`, `ntsBuyThreshold`, `ntsSellThreshold` |
| 7a | `07a_zone_volume_filters.pine` | ناحیه روزانه + فیلتر حجم | **قبل از ۶** | `inDailyDiscount`, `inDailyPremium`, `ntsVolBoost` |
| 7b | `07b_final_signals.pine` | سیگنال‌های نهایی ترکیبی | بعد از ۴ و ۶ | `ntsKafSignal`, `ntsSaghfSignal`, `finalBuySignal`, `finalSellSignal` |
| ۸ | `08_display_alerts.pine` | پنل نمایش و هشدارها | انتهای فایل (بعد از همه) | ردیف‌های ۹–۱۱ پنل + `alertcondition` |
| 9a | `09a_symbol_detection.pine` | تشخیص نوع نماد + حداقل نوسان مؤثر | **زود**: بلافاصله بعد از بخش `input.*` | `symU`, `autoSymbolType`, `autoPeriod`, `autoFactor`, `autoMinAtrPct`, `xauMinAtrPctEff` |
| 9b | `09b_apply_autotune.pine` | اعمال تنظیم خودکار روی هسته | بعد از ۳، قبل از محاسبه هسته NTS | `ntsPeriodFinal`, `ntsFactorFinal` |
| ۱۰ | `10_trendlines_pa.pine` | خطوط روندِ پرایس‌اکشن + ناحیهٔ روزانهٔ قبل | **بعد از ۷a و قبل از ۶** | `tlPdHigh/Low/Eq`, `tlDnLive`/`tlUpLive`, `tlDnYNow`/`tlUpYNow`, `tlDnBreakNow`/`tlUpBreakNow`, `tlAtSupport`/`tlAtResistance` |

### ترتیب پیشنهادیِ نهایی برای درج

```
input.*  →  09a  →  01  →  03  →  09b  →  02  →  هسته NTS
        →  05  →  04  →  07a  →  10  →  06  →  07b  →  نمایش/هشدار (08)
```
(فایل مرجع `src/SMC_NTS_Pro.pine` دقیقاً همین ترتیب را دارد.)

## نکات مهم ادغام (Integration Notes)

1. **ترتیب اجرا در Pine خطی است.** هر متغیری که در ماژولی استفاده می‌شود باید «قبل از» آن ماژول تعریف شده باشد.
2. **ورودی‌ها (`input.*`) قابل بازنویسی نیستند.** در بهبود ۹ نمی‌توان `xauMinAtrPct := ...` نوشت؛
   به جای آن از متغیر مؤثر `xauMinAtrPctEff` استفاده کنید و در هسته NTS جایگزین نمایید.
3. **`ntsPeriod` در سه مرحله تغییر می‌کند:** مقدار پایه (ماژول ۱) ← تنظیم رژیم (ماژول ۳) ← تنظیم خودکار (ماژول ۹).
   اگر ترتیب درج رعایت شود، همان متغیر به‌صورت زنجیره‌ای اصلاح می‌شود.
4. **هشدارها:** در Pine v5 تنها می‌توان به پلات‌های واقعی ارجاع داد (`{{plot("title")}}`).
   برای نمایش ناحیه روزانه در پیام هشدار، یک پلات کمکی با `display=display.data_window` تعریف شده است.

## اصلاحات نحو (Syntax Fixes) اعمال‌شده نسبت به متن اولیه

| مشکل در متن اولیه | اصلاح |
|---|---|
| `ntsPeriod = int(math.round(...))))` (پرانتز اضافه) | یک پرانتز بسته حذف شد |
| `ntsFactor = ... )` پرانتز سرگردان قبل از `:=` | حذف شد |
| `int(ntsPeriod * 0.85))))` | دو پرانتز اضافه حذف شد |
| `orinRevSellZone` | `or inRevSellZone` |
| `ntsTrend == -1and`, `bearishConfirmationand`, `kdBuySignaland`, `xauTradeOkand` | فاصله‌گذاری اصلاح شد |
| `{{plot("inDailyDiscount")}}` در `alertcondition` | تبدیل به `{{plot("DailyZone")}}` + پلات کمکی |
| `xauMinAtrPct := autoMinAtrPct` (بازنویسی ورودی) | تبدیل به `xauMinAtrPctEff` |

## نکتهٔ ویژهٔ ماژول ۱۰ (خطوط روند)

این ماژول **اشیاء گرافیکی** (`line` و `label`) می‌سازد، بنابراین اندیکاتور مقصد
باید این مقادیر را داشته باشد:

```pine
indicator(..., overlay=true, max_lines_count=500, max_labels_count=500)
```

همچنین چون خروجی‌های `tlAtSupport` / `tlAtResistance` در امتیازدهیِ M06 استفاده
می‌شوند، ماژول ۱۰ باید **قبل از** M06 درج شود.
