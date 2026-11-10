# PolyBet Quant Terminal v2.0 — Polymarket Quantitative Scanner & Multi-Leg Hedge Engine

موتور اسکنر کوانت، تجمیع سیگنال‌های اقتصاد کلان/انتخابات، سایزینگ کسری کِلی (Fractional Kelly)، و مدیریت پوشش ریسک (Multi-Leg Hedging) برای بازارهای پیش‌بینی **Polymarket** به همراه ورک‌فلوهای خودکار **GitHub Actions** و داشبورد تعاملی **GitHub Pages**.

---

## 📂 ساختار استاندارد ریپازیتوری گیت‌هاب (Repository Structure)

```text
polybet-quant-v2/
├── .github/
│   └── workflows/
│       ├── daily_scan.yml          # اسکن روزانه خودکار (08:00 UTC) + کامیت CSV و docs/index.html
│       └── weekly_report.yml       # ارزیابی تسویه هفتگی (یکشنبه‌ها 20:00 UTC) + کامیت docs/results.html
├── sources/
│   ├── __init__.py                 # پکیج رسمی منابع سیگنال مستقل
│   ├── aggregator.py               # تجمیع‌کننده چندمنبعی با امتیاز اجماع بیزی (Bayesian Consensus)
│   ├── base.py                     # مدل‌های پایه، انقباض بیزی تجربی و اتصال به باکت‌های عددی
│   ├── range_bucket.py             # پارسر بازه‌های عددی (<0.0%, 0.3%-0.5%) و انتگرال توزیع نرمال
│   ├── fred.py                     # داده‌های فدرال رزرو (نرخ بهره، CPI YoY pc1، GDP pch، UNRATE)
│   ├── bls.py                      # اداره آمار کار آمریکا (نرخ بیکاری LNS14000000 و تورم ۱۲ماهه CPI)
│   ├── bea.py                      # اداره تحلیل اقتصادی آمریکا (GDP و PCE)
│   ├── eia.py                      # اداره اطلاعات انرژی آمریکا (نفت خام WTI/Brent و گاز طبیعی)
│   ├── ecb.py                      # بانک مرکزی اروپا (ECB SDW)
│   ├── boe.py                      # بانک مرکزی انگلستان (BoE Official Bank Rate)
│   ├── boc.py                      # بانک مرکزی کانادا (BoC Valet API)
│   ├── eurostat.py                 # آمار تورم و رشد اقتصادی حوزه یورو (Eurostat)
│   ├── worldbank.py                # شاخص‌های کلان بانک جهانی (World Bank)
│   ├── imf.py                      # چشم‌انداز اقتصادی صندوق بین‌المللی پول (IMF WEO)
│   ├── alpha_vantage.py            # داده‌های قیمت و درآمد سهام (Alpha Vantage)
│   ├── finnhub.py                  # اجماع EPS و داده‌های بازار سهام (Finnhub)
│   ├── polls.py                    # میانگین نظرسنجی‌های انتخاباتی
│   └── ticker_map.py               # نگاشت نام شرکت‌ها به نماد معاملاتی (Ticker)
├── docs/
│   ├── index.html                  # داشبورد ترمینال کوانت سیگنال‌های روزانه (GitHub Pages)
│   └── results.html                # داشبورد بک‌تست و تاریخچه نتایج تسویه‌شده (GitHub Pages)
├── main.py                         # ارکستریتور اسکن روزانه، لاگ CSV بدون تکرار، تولید HTML و ارسال تلگرام
├── scanner.py                      # اسکنر Polymarket Gamma API با فیلتر دقیق دسته‌بندی و حذف ورزش‌ها
├── position_logic.py               # موتور سایزینگ کِلی v2، محافظ تله آپشن‌های مانعی (<15¢) و محاسبه Net ROI
├── weekly_report.py                # موتور تسویه خودترمیم‌گر (Self-Healing) و گزارش هفتگی تلگرام
├── html_generator.py               # مولد داشبورد تعاملی docs/index.html با ماشین‌حساب زنده Bankroll و کِلی
├── results_html_generator.py       # مولد داشبورد بک‌تست چندپایه docs/results.html
├── telegram_bot.py                 # ماژول ارسال پیام و خلاصه دسته‌بندی‌شده به تلگرام
├── predictions_log.csv             # لاگ تاریخی تمام سیگنال‌های اسکن‌شده
├── predictions_resolved.csv        # دیتاست تسویه‌شده و اصلاح‌شده (حسابرسی‌شده)
└── requirements.txt                # وابستگی‌های پایتون (requests, python-dotenv)
```

---

## 🛠️ خلاصه ۱۱ اصلاح کلیدی اعمال‌شده در نسخه v2.0

1. **رفع باگ صفر شدن برد سهام در بازارهای باینری (`main.py` + `weekly_report.py`):** جلوگیری از ثبت عنوان کامل سؤال به جای گزینه `"Yes"` یا `"No"` در رویدادهای تک‌بازاری و ترمیم خودکار ۲۷ برد سهام در `predictions_resolved.csv`.
2. **محاسبه دقیق بازده چندپایه سبد (`results_html_generator.py` + `position_logic.py`):** کسر کامل هزینه پایه‌های Secondary و Hedge در زمان برد Primary و احتساب دریافتی پایه‌های هج در زمان باخت Primary.
3. **رفع باگ دسته‌بندی اشتباه نام کاندیداها (`scanner.py`):** حذف کلیدواژه تک‌کلمه‌ای `"bailey"` از بانک مرکزی انگلستان (`boe`) و افزودن فیلتر حذف بازارهای ورزشی (`NFL`, `NBA`, `Draft`, `Touchdowns`).
4. **اتصال ماژول `sources/range_bucket.py` به موتور سیگنال (`sources/base.py`):** محاسبه احتمال واقعی باکت‌های عددی (`0.2%–0.3%`، `≤3.8%`) با انتگرال‌گیری از توزیع نرمال (Gaussian CDF).
5. **اصلاح واحدهای آماری در `sources/fred.py` و `sources/bls.py`:** استفاده از نرخ تغییر سالانه (`units="pc1"`) برای شاخص قیمت مصرف‌کننده به جای عدد خام شاخص (`315.6`) و استفاده از نرخ بیکاری (`UNRATE` / `LNS14000000`) به جای کل شاغلین (`158,000`).
6. **محافظ تله آپشن‌های مانعی (`position_logic.py`):** شناسایی خودکار بازارهای غیرانحصاری `"What price will X hit?"` با قیمت زیر ۱۵ سنت و اعمال سقف تخصیص ۵٪ بدون خرید هج‌های متناقض.
7. **رفع قفل‌شدن بازارهای زمان‌دار (`weekly_report.py`):** تسویه فوری زیربازارهای تاریخ‌دار (`by August 31`, `by October 31`) به محض بسته‌شدن آن تاریخ با نتیجه `"No"`.
8. **اصلاح Payload دکمه تحلیل هوش مصنوعی (`html_generator.py`):** ارسال کامل لیست گزینه‌ها و قیمت‌های تمام باکت‌های رویداد به ورکر تحلیل هوش مصنوعی.
9. **رفع باگ نام فایل پکیج (`sources/__init__.py`):** تبدیل `init.py` به `__init__.py` استاندارد پایتون.
10. **انقباض بیزی تجربی برای امتیاز اجماع (`sources/base.py`):** جایگزینی فرمول خطی با Empirical Bayes Shrinkage تا یک منبع تکی امتیاز کاذب ۱۰۰٪ تولید نکند.
11. **اصلاح ورک‌فلوهای GitHub Actions (`.github/workflows/daily_scan.yml` و `weekly_report.yml`):** افزودن متغیر جااقتاده `BLS_API_KEY`، یکپارچه‌سازی قفل هم‌زمانی (`group: polybet-repo-write`)، جلوگیری از ثبت تکراری در تلاش مجدد (Retry) و افزودن `git pull --rebase --autostash` پیش از `git push`.

---

## 🚀 راهنمای راه‌اندازی در گیت‌هاب (GitHub Setup)

### ۱. تنظیم متغیرهای محرمانه (GitHub Actions Secrets)
در ریپازیتوری گیت‌هاب خود به مسیر **Settings → Secrets and variables → Actions** بروید و کلیدهای زیر را ثبت کنید:

| نام Secret | کاربرد | الزامی/اختیاری |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | توکن ربات تلگرام دریافتی از `@BotFather` | الزامی برای ارسال پیام تلگرام |
| `TELEGRAM_CHAT_ID` | شناسه چت یا کانال تلگرام | الزامی برای ارسال پیام تلگرام |
| `DASHBOARD_URL` | آدرس GitHub Pages شما (مثلاً `https://username.github.io/polybet`) | پیشنهادی |
| `FRED_API_KEY` | کلید API فدرال رزرو سنت‌لوئیس (FRED) | پیشنهادی |
| `BLS_API_KEY` | کلید API اداره آمار کار آمریکا (BLS v2) | پیشنهادی |
| `ALPHA_VANTAGE_API_KEY` | کلید API آلفا ونتیج برای سهام و کالا | اختیاری |
| `FINNHUB_API_KEY` | کلید API فین‌هاب برای گزارش درآمد سهام | اختیاری |
| `EIA_API_KEY` | کلید API اداره اطلاعات انرژی آمریکا | اختیاری |
| `BEA_API_KEY` | کلید API اداره تحلیل اقتصادی آمریکا | اختیاری |

### ۲. فعال‌سازی GitHub Pages برای داشبورد
1. در گیت‌هاب وارد **Settings → Pages** شوید.
2. در بخش **Build and deployment**، گزینه **Source** را روی **Deploy from a branch** قرار دهید.
3. شاخه (`Branch`) را روی `main` و پوشه را روی `/docs` تنظیم کرده و **Save** را بزنید.
4. داشبورد روزانه در مسیر `/` (`docs/index.html`) و داشبورد نتایج بک‌تست در مسیر `/results.html` (`docs/results.html`) منتشر می‌شود.

### ۳. اجرای محلی (Local Execution)
```bash
pip install -r requirements.txt
python main.py                  # اجرای اسکن روزانه و تولید docs/index.html
python weekly_report.py --dry-run  # اجرای حسابرسی تسویه و تولید docs/results.html
```
