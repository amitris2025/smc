# SMC + NTS PRO v6 — سند نسخهٔ نهایی

فایل تحویلی: `src/SMC_NTS_PRO_v6.pine` (۳۳۰۲ خط، Pine Script v6، آمادهٔ درج
مستقیم در Pine Editor؛ خط اول `//@version=6` است).

نسخهٔ v5 (`src/SMC_NTS_Pro.pine`) بدون تغییر باقی مانده است تا مقایسه ممکن بماند.

## ۱. آمار

| مورد | مقدار |
|---|---|
| تعداد خط | 3302 |
| ماژول | 31 (M01 تا M31) |
| ورودی تنظیم‌شدنده | 212 در ۱۹ گروه |
| تابع تعریف‌شده | 68 |
| `request.security` | 9 فراخوانی (همه `gaps_off` + `lookahead_off`) |
| `alertcondition()` | 15 |
| `alert()` پویا | 7 |
| پلات Data Window | 49 |
| ردیف پنل اطلاعات | 48 |

## ۲. معماری (به ترتیب اجرا)

| ماژول | مسئولیت |
|---|---|
| M01 | ورودی‌ها و گروه‌بندی تنظیمات |
| M02 | توابع کمکی، NaN Guard، مدیریت مرکزی آبجکت‌ها |
| M03 | تشخیص نماد و Auto-Tune ترکیبی + مقایسهٔ تایم‌فریم‌ها |
| M04 | دروازه‌های نمایش (Minimal / Standard / Full Analysis) |
| M05 | هستهٔ NTS و NTS Trail — کاملاً MTF در یک `request.security` |
| M06 | Pivot تأییدشده، CHoCH، BOS، Supply / Demand |
| M07 | Premium / Equilibrium / Discount روزانه (یک منطق واحد) |
| M08 | Reversal Cloud پویا |
| M09 | RSI / Stoch / MACD / EMA / ATR نمودار |
| M10 | Hull Suite به‌عنوان فیلتر تأیید |
| M11 | Smart Divergence — Pending و Confirmed کاملاً جدا |
| M12 | موتور Fib (Retracement و Extension) + واکنش قیمت + Cooldown |
| M13 | Session Filter و Volume Filter |
| M14 | سطوح مرجع SMC (PDH/PDL/PWH/PWL/Open) و جاروی نقدینگی |
| M15 | ماتریس تأیید تایم‌فریم بالاتر |
| M16 | امتیازدهی Confluence (Buy و Sell مستقل و متقارن) |
| M17 | موتور سیگنال: SETUP / CONFIRMED / PRO BUY / PRO SELL |
| M18 | مدیریت ریسک و Trade Plan |
| M19 | باکس سشن‌های جهانی |
| M20 | خطوط روند خودکار و تاریخی |
| M21 | لایهٔ نمایش (Trail / Cloud / PD / Hull) |
| M22 | رسم سطوح Fib، ناحیه‌های S/D و لیبل سیگنال‌ها |
| M23 | تصویرسازی موج NTS و نشانگرهای رویداد |
| M24 | جدول لاگ سیگنال‌ها |
| M25–M26 | پنل اطلاعات و پلات‌های Data Window |
| M27 | هشدارها |
| M28–M30 | تکمیل پنل، آمار روزانه، پلات‌های تشخیصی |
| M31 | خودآزمایی داخلی (۱۳ Invariant) |

## ۳. تضمین‌های ضد ری‌پینت

1. **`lookahead_off` در همه‌جا.** هیچ `lookahead_on` در فایل وجود ندارد؛ ممیزی
   خودکار (`tools/pine_audit.py`) این مورد را به‌عنوان یک قانون سخت بررسی می‌کند.
2. **فقط کندل بسته‌شده.** `buyGateCore` و `sellGateCore` با `barstate.isconfirmed`
   شروع می‌شوند؛ بنابراین حتی سطح SETUP هم روی کندل باز صادر نمی‌شود. هشدارهای
   پویا نیز با همان شرط و `alert.freq_once_per_bar_close` ارسال می‌شوند.
3. **لچ کردن مقادیر HTF روی نمودار LTF.** با `lookahead_off`، مقدار تایم‌فریم
   بالاتر روی نمودار پایین‌تر در طول دورهٔ جاری «در حال شکل‌گیری» است. در M05،
   M10 و M15 مقدارِ بسته‌شدهٔ آخرین کندل HTF در مرز تغییر دوره از تاریخ `[1]`
   خوانده و در متغیر `var` ذخیره می‌شود و تا پایان دوره ثابت می‌ماند:
   بدون دادهٔ آینده، بدون ری‌پینت و بدون تأخیر اضافی.
4. **یک سیگنال به ازای هر کندل پایه.** `ntsSampled` اجازهٔ صدور سیگنال را فقط
   در اولین کندلِ هر دورهٔ تایم‌فریم پایه می‌دهد؛ `sigSell` نیز با
   `and not sigBuy` قفل شده تا BUY و SELL هرگز هم‌زمان ثبت نشوند.
5. **CHoCH/BOS و Pivotها فقط با `sdPivotRight`/`structPivotLen` تأییدشده** و روی
   کندل بسته‌شده ساخته می‌شوند؛ سطوح تا رویداد بعدی ثابت می‌مانند.
6. **رسم فقط روی آخرین کندل** (`drawGate`)؛ در Realtime هیچ آبجکتی با حرکت
   قیمت جابه‌جا نمی‌شود.

## ۴. قراردادهای Fib

```
Retracement : level = extreme - dir * |extreme - anchor| * ratio      (ratio < 1)
Extension   : level = anchor  + dir * |extreme - anchor| * ratio      (ratio >= 1)
```

- دسته ۰ و ۱: Retracement کم‌عمق و اصلی (سه نسبت اصلی از ورودی کاربر: `fibRetr1/2/3`
  که همیشه مرتب می‌شوند).
- دسته ۲ و ۳: Normal Pullback و Early Extension → فقط **واکنش هم‌جهت**.
- دسته ۴ و ۵: Deep / Extreme Reversal → فقط **واکنش خلاف‌جهت** و مشروط به
  `deepNeedConfirm` با تأیید **هم‌جهت** (CHoCH/BOS یا واگرایی Confirmed).
- هر سطح Cooldown مستقل دارد (`fibCooldownRetr` برای Retracement و
  `fibCooldownExt` برای Extension) که بر حسب کندلِ تایم‌فریم پایه تبدیل می‌شود.

## ۵. مدیریت آبجکت‌ها

هر ماژول استخر اختصاصی خود را دارد؛ پاک‌سازی یک ماژول هرگز آبجکت ماژول دیگر را
حذف نمی‌کند:

`omSigLabels` • `omDivLabels` • `omDivLines` • `omDivBoxes` • `omSdBoxes` •
`omPdBoxes` • `omExtLines` • `omExtLabels` • `omFibLines` • `omTlLines` •
`omTlLabels` • `omPlanLines` • `omStructLbl` • `omSessBoxes` • `omWaveLines` •
`omWaveLabels`

سقف‌های کاربر: Signal Labels ≤ 120، Divergence Labels ≤ 40، Trendlines ≤ 20،
Boxes ≤ 30، Extension Lines ≤ 40؛ و `max_lines_count/labels/boxes = 500` در
`indicator()`. لیبل سیگنال هرگز به دلیل پر بودن اسلات حذف نمی‌شود — در هر کندل
حداکثر یک سیگنال ممکن است و ارتفاع لیبل بر اساس سطح سیگنال تنظیم می‌شود.

## ۶. خودآزمایی داخلی (M31)

۱۳ قرارداد روی آخرین کندل بررسی و در پنل گزارش می‌شود:

تناقض BUY/SELL • محدودهٔ Score • صدور فقط روی کندل بسته • Warm-up • سقف خطوط •
سقف لیبل‌ها • سقف باکس‌ها • ترتیب PD (Discount ≤ EQ ≤ Premium) • انحصار ناحیهٔ
PD • سازگاری مرجع موج • قرارگیری Retracement بین Anchor و Extreme •
عدم ساخت PRO از واگرایی Pending • استقلال Cooldown.

با روشن کردن «هشدار در صورت نقض قرارداد داخلی» هر نقض با `alert()` گزارش می‌شود
(پیش‌فرض خاموش است؛ فقط برای تست).

## ۷. ابزارهای بررسی خودکار

| ابزار | کار |
|---|---|
| `tools/check_pine.py` | توازن براکت/کمانت، چسبیدگی نام‌ها، ساختار کلی |
| `tools/undefined_ids.py` | شناسهٔ تعریف‌نشده یا استفاده پیش از تعریف |
| `tools/pine_audit.py` | ۱۰ بررسی معنایی: بازتعریفی، ترتیب، عملگر بیتی، `lookahead_on`، تعداد عضو tuple، استخر آبجکت‌ها، `alertcondition`، `ta.*` داخل شرط، کرانهٔ حلقه، کاراکتر نامرئی |
| `tools/scan_globalmod.py` | تابعی که متغیر global را با `:=` بازنویسی می‌کند (خطای v6) |
| `tools/namespace_check.py` | سه بررسی: عضو نامعتبر namespace (مثل `syminfo.title`)، ثابت «نوع یکتا» در متغیر با نوع صریح، و پاس‌دادن چنین ثابتی به تابع کاربردی |
| `tools/v6_pitfalls.py` | قواعد ناسازگار v6 از راهنمای مهاجرت رسمی: `na` برای bool، `na()/nz()` با آرگومان bool، شرط int/float، پارامتر تکراری، timeframe بدون multiplier، طول mutable برای `ta.*`، `offset` سری |
| `tools/plot_count.py` | شمارش دقیق plot count طبق قواعد مستند (سقف ۶۴) |

فیکسچرهای تست (برای اطمینان از اینکه ابزارها خطا را واقعاً می‌گیرند):
`tools/testdata/v6_typebugs_BAD.pine` و نمونه‌های `tools/testdata/original_snippets_BAD.pine`.

هر سه ابزار روی فایل نهایی بدون هیچ یافته‌ای اجرا می‌شوند:

```bash
python3 tools/check_pine.py    src/SMC_NTS_PRO_v6.pine
python3 tools/undefined_ids.py src/SMC_NTS_PRO_v6.pine
python3 tools/pine_audit.py    src/SMC_NTS_PRO_v6.pine
```

## ۸. منبع واحد و ترتیب ماژول‌ها

منبع نهایی و معتبر، فایل یکپارچهٔ `src/SMC_NTS_PRO_v6.pine` است؛ همهٔ
ویرایش‌ها مستقیماً روی همان فایل انجام می‌شود. ترتیب ماژول‌ها درون فایل
اجباری است و با هدرهای `▍M01` تا `▍M31` مشخص شده:

1. ورودی‌ها (M01) باید پیش از هر استفاده باشند.
2. توابع کمکی و استخرهای آبجکت (M02/M03) پیش از همهٔ ماژول‌های محاسباتی.
3. دروازه‌های نمایش (M04) پیش از هر بخش رسم.
4. هستهٔ NTS (M05) پیش از هر ماژولی که `chartAtrSafe`، `ntsAtr` یا `ntsTrend`
   را مصرف می‌کند.
5. ماتریس HTF (M15) پیش از امتیازدهی (M16) چون `mtfBuyAdj/mtfSellAdj` در
   Score اعمال می‌شوند.
6. خودآزمایی (M31) در انتها چون به همهٔ متغیرها نیاز دارد.

اجرای کامل بررسی‌ها:

```bash
for t in check_pine undefined_ids pine_audit scan_globalmod namespace_check v6_pitfalls; do
  python3 tools/$t.py src/SMC_NTS_PRO_v6.pine | tail -1
done
python3 tools/plot_count.py src/SMC_NTS_PRO_v6.pine | tail -2
```

## ۸٫۱. دو خطای کامپایلی که در بازبینی v6 برطرف شد

1. **`Undeclared identifier "syminfo.title"`** — در Pine v6 چنین عضوی وجود
   ندارد؛ نام توصیف نماد `syminfo.description` است.
2. **`Cannot assign a value of the "series string" type to the "_style"
   variable. The variable is declared with the "const int" type.`** — ثابت‌های
   `line.style_*` (و `label.style_*`، `plot.style_*`، `size.*`، `extend.*`،
   `shape.*`، `location.*`، `display.*`) در v6 از «نوع یکتا» هستند و نه
   `int`/`string` معمولی؛ بنابراین نمی‌توان آن‌ها را در متغیری با نوع صریح
   نگه داشت. مقدار باید مستقیماً به پارامتر همان built-in پاس داده شود:

```pine
// نادرست در v6
int _style = isRetr ? line.style_solid : line.style_dashed
line.new(x1, y1, x2, y2, style = _style)

// درست در v6
line.new(x1, y1, x2, y2, style = isRetr ? line.style_solid : line.style_dashed)
```

به همین دلیل `f_txt(x, format.mintick)` هم به `f_txtTick(x)` تبدیل شد تا ثابت
`format.mintick` هیچ‌گاه از مرز یک تابع کاربردی با پارامتر `string` عبور نکند.

## ۹. تنظیمات پیشنهادی

مقادیر پیش‌فرض برای **XAUUSD روی M15 با تایم‌فریم پایهٔ NTS = 15** بهینه شده‌اند
(`ntsBaseTimeframe = "15"`، سشن `0430-0830` و Golden Hour `0630-0830` به وقت
`Asia/Tehran`).

| پارامتر | اسکالپ (M5 با پایهٔ M15) | روزانه (M15 با پایهٔ M15) | سوئینگ (H1 با پایهٔ H4) |
|---|---|---|---|
| `ntsBaseTimeframe` | `15` | `15` | `240` |
| `ntsAtrLen` / `ntsAdxLen` | `14` / `14` | `14` / `14` | `14` / `14` |
| `ntsMinPeriod` – `ntsMaxPeriod` | `8` – `24` | `10` – `30` | `14` – `40` |
| `scoreSetup` / `scoreConfirmed` / `scorePro` | `48` / `64` / `80` | `52` / `68` / `84` | `56` / `72` / `86` |
| `buyCooldown` / `sellCooldown` | `2` | `3` | `4` |
| `planSlAtrMult` / `planTpAtrMult` | `1.0` / `1.8` | `1.5` / `2.5` | `2.0` / `4.0` |
| `useVolumeFilter` | روشن | روشن | خاموش (حجم H1 برای طلا کم‌معناست) |
| `hullUseHtf` | خاموش | خاموش | روشن (`hullHtf = 240`) |
| `displayMode` | `Minimal` | `Standard` | `Full Analysis` |
| `mtfTf1/2/3` | `60` / `240` / `D` | `60` / `240` / `D` | `240` / `D` / `W` |

نکتهٔ مهم: اگر تایم‌فریم نمودار از تایم‌فریم پایه پایین‌تر باشد (ستون اول)،
همهٔ محاسبات NTS همان‌طور که در بخش ۳ توضیح داده شد در تایم‌فریم پایه باقی
می‌مانند و سیگنال فقط یک بار به ازای هر کندل M15 صادر می‌شود؛ Cooldown هم بر
حسب کندل پایه تبدیل می‌شود، بنابراین تنظیمات بالا برای هر دو حالت معتبرند.

## ۱۰. روش تست پیشنهادی

1. اندیکاتور را روی `OANDA:XAUUSD` یا `TVC:GOLDUS` با تایم‌فریم M15 اضافه کنید.
2. در پنل، ردیف **Self-Test** باید `ALL PASS (13)` باشد و ردیف **Lookahead**
   مقدار `OFF (ALL REQUESTS)` را نشان دهد.
3. با Bar Replay روی یک بازهٔ پرنوسان بروید؛ در هر کندل M15 حداکثر یک لیبل
   سیگنال باید ظاهر شود و لیبل‌های قبلی جابه‌جا یا حذف نشوند.
4. جدول **لاگ سیگنال** را بررسی کنید: هیچ ردیف BUY نباید بلافاصله پس از یک
   ردیف SELL در همان کندل ثبت شده باشد و زمان‌ها باید یکنوا رو به جلو باشند.
5. نمودار را به M5 تغییر دهید؛ تعداد سیگنال‌های ثبت‌شده در یک بازهٔ زمانی
   مشخص باید با حالت M15 یکسان بماند (دروازهٔ `ntsSampled`).
6. ردیف **MTF Sampling** در پنل باید روی M5 مقدار `MTF GATED (3×)` و روی M15
   مقدار `1:1 SAMPLED` را نشان دهد.

## ۱۱. بودجهٔ محدودیت‌های TradingView

سقف‌های مستند (صفحهٔ Limitations در داکیومنت Pine) و مصرف این اسکریپت:

| محدودیت | سقف | مصرف این اسکریپت |
|---|---|---|
| plot count (شامل `plot`، `plotshape`، `alertcondition`، `fill` با رنگ series) | 64 | **39** (۱۲ پلات بصری + ۱ fill + ۶ plotshape + ۱۰ alertcondition + ۱۱ پلات Data Window) |
| فراخوانی `request.*` | 40 | 9 |
| Local scopes | ~550 | ~292 |
| خطوط / لیبل‌ها / باکس‌ها | 500 (با `max_*_count`) | 500 تنظیم شده؛ مصرف واقعی با استخرها زیر ۲۰۰ |
| سلول‌های جدول | 500 | 166 (پنل 56×2 + لاگ سیگنال 9×6) |

ابزار `tools/plot_count.py` سهم هر فراخوانی را طبق همان قواعد مستند
(هر آرگومان رنگیِ series = یک سهم اضافه) می‌شمارد و در صورت عبور از ۶۴
خطا می‌دهد. به همین دلیل مقادیر تشخیصیِ پرتعداد به‌جای `plot(display.data_window)`
در ردیف‌های ۴۸ تا ۵۲ پنل نمایش داده می‌شوند — جدول هیچ سهمی مصرف نمی‌کند.

## ۱۲. قواعد Pine v6 که در این نسخه رعایت شده‌اند

- **تابع نمی‌تواند متغیر global را با `:=` بازنویسی کند**
  (خطای `Cannot modify global variable ... in function`). وضعیت اسلات لیبل‌ها
  بنابراین در دو آرایهٔ global نگه داشته می‌شود و با `array.set()` تغییر
  می‌کند که مجاز است. ابزار `tools/scan_globalmod.py` کل فایل را برای این
  الگو بررسی می‌کند.
- **پارامترهای تابع که طول `ta.*` هستند باید `simple int` باشند** —
  `f_ntsCore(simple int ...)`، `f_hullMa(..., simple int _len, ...)` و
  `f_htfContext(simple int ...)`.
- **`source` نوع مجاز پارامتر نیست** — منبع Hull با `float _src` پاس داده می‌شود.
- **Pine عملگر بیتی ندارد** — پرچم‌های سطوح Fib با `array<bool>` و توابع
  `f_fibFlagGet/Set` پیاده شده‌اند.
- **`bar_index(time)` وجود ندارد** — جای هر موج با ردیابی bar_index در
  `ntsWaveStartBar` و آرایهٔ `histWaveStarts` نگهداری می‌شود.
- **متغیر `var` داخل تابعی که از `request.security` صدا زده می‌شود مجاز است**
  و state را در تایم‌فریم پایه نگه می‌دارد (پایهٔ طراحی M05).
