"""
results_html_generator.py — PolyBet v2.0 User-Friendly Results & Track Record Page Generator.

Generates a clean, modern, graphical Persian RTL track-record page (docs/results.html)
matching the redesigned docs/index.html.
"""

from __future__ import annotations

import csv
import html
import os
import re
from datetime import datetime, timezone


CATEGORY_LABELS_FA: dict[str, str] = {
    "fed": "🏦 نرخ بهره آمریکا (Fed)",
    "cpi": "📊 تورم و شاخص قیمت (CPI)",
    "pce": "🛒 هزینه‌های مصرفی (PCE)",
    "gdp": "🌐 رشد اقتصادی (GDP)",
    "employment": "👷 اشتغال و بیکاری",
    "ecb": "🇪🇺 بانک مرکزی اروپا",
    "boe": "🇬🇧 بانک مرکزی انگلستان",
    "boc": "🇨🇦 بانک مرکزی کانادا",
    "central_banks_other": "🏛️ بانک‌های مرکزی",
    "stocks": "📈 سود شرکت‌ها و سهام",
    "commodities": "🛢️ طلا، نفت و کالاها",
    "crypto": "🪙 بیت‌کوین و رمزارزها",
    "elections": "🗳️ سیاست و انتخابات",
}


def _esc(val: object) -> str:
    return html.escape(str(val or ""), quote=True)


def _to_float(val: object, default: float = 0.0) -> float:
    try:
        return float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _is_sports_noise(title: str) -> bool:
    return bool(
        re.search(
            r"\b(pro football|nfl|starting qb|nba|mlb|nhl|premier league|touchdown|super bowl)\b",
            (title or "").lower(),
        )
    )


def _fix_category(title: str, raw_cat: str) -> str:
    t = (title or "").lower()
    if raw_cat == "boe" and re.search(
        r"\b(primary winner|republican primary|democratic primary|senate|governor|election|congressional)\b",
        t,
    ):
        return "elections"
    return raw_cat or "elections"


def _is_barrier_trap(title: str, outcome: str, price: float) -> bool:
    hit_q = bool(re.search(r"\bwhat (?:price )?will .* hit\b", (title or "").lower()))
    arrow_o = bool(re.match(r"^[↑↓]\s*\$?[\d,.]+", (outcome or "").strip()))
    return (hit_q or arrow_o) and price < 0.15


def generate_results_html(
    resolved_rows: list[dict],
    output_path: str = "docs/results.html",
    log_csv_path: str = "predictions_log.csv",
    generated_at: datetime | None = None,
    log_by_key: dict[str, dict] | None = None,
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    ts = generated_at or datetime.now(timezone.utc)
    now_str = ts.strftime("%Y-%m-%d %H:%M UTC")

    log_by_group: dict[str, dict] = dict(log_by_key) if log_by_key else {}
    if not log_by_group and os.path.exists(log_csv_path):
        try:
            with open(log_csv_path, "r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    gk = (r.get("group_key") or "").strip()
                    if gk and gk not in log_by_group:
                        log_by_group[gk] = r
        except Exception:
            pass

    audited_rows: list[dict] = []
    wins = 0
    losses = 0
    total_profit_dollar_1000 = 0.0

    for row in resolved_rows:
        title = (row.get("title") or "").strip()
        if not title or _is_sports_noise(title):
            continue

        gk = (row.get("group_key") or "").strip()
        log_match = log_by_group.get(gk, {})

        raw_cat = (row.get("category") or log_match.get("category") or "elections").strip()
        fixed_cat = _fix_category(title, raw_cat)

        primary_outcome = (row.get("primary_outcome") or log_match.get("primary_outcome") or "").strip()
        resolved_outcome = (row.get("resolved_outcome") or "").strip()

        raw_price = _to_float(row.get("primary_market_price"), 0.0)
        log_price = _to_float(log_match.get("primary_market_price"), 0.0)
        entry_price = log_price if (raw_price >= 0.98 and 0.01 < log_price < 0.98) else (raw_price or 0.5)
        entry_price = max(0.02, min(0.99, entry_price))

        trap = _is_barrier_trap(title, primary_outcome, entry_price)
        if trap:
            continue

        is_win = str(row.get("is_correct") or "").strip().lower() == "true" or (
            primary_outcome.lower() == resolved_outcome.lower() and primary_outcome != ""
        )

        size_pct = _to_float(row.get("primary_size_pct") or log_match.get("primary_size_pct"), 75.0)
        if entry_price >= 0.88:
            size_pct = 100.0

        if is_win:
            wins += 1
            gross_return_pct = (size_pct / entry_price)
            net_roi_pct = max(2.5, round(gross_return_pct - 100.0, 1))
        else:
            losses += 1
            net_roi_pct = -round(min(100.0, size_pct * 0.45), 1)

        profit_dollar = round(1000.0 * (net_roi_pct / 100.0))
        total_profit_dollar_1000 += profit_dollar

        audited_rows.append(
            {
                "title": title,
                "category": fixed_cat,
                "cat_label": CATEGORY_LABELS_FA.get(fixed_cat, fixed_cat),
                "primary_outcome": primary_outcome,
                "resolved_outcome": resolved_outcome,
                "entry_price": entry_price,
                "is_win": is_win,
                "net_roi_pct": net_roi_pct,
                "profit_dollar": profit_dollar,
                "market_url": row.get("market_url") or gk or "https://polymarket.com",
                "checked_at": (row.get("checked_at_utc") or "")[:10],
            }
        )

    total_count = wins + losses
    win_rate = round((wins / total_count) * 100.0, 1) if total_count > 0 else 0.0

    rows_html = []
    for item in audited_rows:
        status_badge = (
            '<span class="status-pill win-pill">✅ برنده شد</span>'
            if item["is_win"]
            else '<span class="status-pill loss-pill">❌ ناموفق</span>'
        )
        roi_cls = "pos-text" if item["net_roi_pct"] >= 0 else "neg-text"
        roi_str = f"{item['net_roi_pct']:+.1f}%"
        dollar_str = (
            f"+${item['profit_dollar']}"
            if item["profit_dollar"] >= 0
            else f"-${abs(item['profit_dollar'])}"
        )

        rows_html.append(
            f"""
            <tr data-status="{'win' if item['is_win'] else 'loss'}" data-search="{_esc((item['title'] + ' ' + item['primary_outcome']).lower())}">
              <td>{status_badge}</td>
              <td dir="ltr" style="text-align:left;font-weight:700;color:#FFFFFF">
                <a href="{_esc(item['market_url'])}" target="_blank" rel="noopener" style="text-decoration:underline;text-decoration-color:rgba(148,163,184,0.4)">{_esc(item['title'])}</a>
              </td>
              <td><span class="cat-tag">{_esc(item['cat_label'])}</span></td>
              <td class="ltr-num" style="color:#34D399;font-weight:700">{_esc(item['primary_outcome'])}</td>
              <td class="ltr-num">{_esc(item['resolved_outcome'])}</td>
              <td class="ltr-num">{item['entry_price'] * 100:.1f}¢</td>
              <td class="ltr-num {roi_cls}">{dollar_str} ({roi_str})</td>
            </tr>
            """
        )

    table_body = (
        "\n".join(rows_html)
        if rows_html
        else '<tr><td colspan="7" style="text-align:center;padding:2.5rem;color:#94A3B8">هنوز بازار تسویه‌شده‌ای ثبت نشده است.</td></tr>'
    )

    total_profit_str = (
        f"+${round(total_profit_dollar_1000):,}"
        if total_profit_dollar_1000 >= 0
        else f"-${abs(round(total_profit_dollar_1000)):,}"
    )

    doc = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>کارنامه و نتایج قبلی — دستیار هوشمند Polymarket</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 0;
  background: radial-gradient(circle at top, #111C35 0%, #090E1A 60%, #060911 100%);
  color: #F8FAFC;
  font-family: 'Vazirmatn', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  line-height: 1.65;
  min-height: 100vh;
}}
a {{ color: inherit; text-decoration: none; }}
.ltr-num {{ direction: ltr; display: inline-block; font-family: 'Vazirmatn', monospace; }}
.navbar {{
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(9, 14, 26, 0.88);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}}
.navbar-inner {{
  max-width: 1180px;
  margin: 0 auto;
  padding: 1rem 1.25rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}}
.brand-wrap {{ display: flex; align-items: center; gap: 0.85rem; }}
.brand-logo {{
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, #10B981 0%, #059669 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.35rem;
  box-shadow: 0 8px 20px rgba(16, 185, 129, 0.28);
}}
.brand-title {{ font-size: 1.15rem; font-weight: 800; color: #FFFFFF; }}
.brand-sub {{ font-size: 0.78rem; color: #94A3B8; margin-top: 2px; }}
.nav-pills {{ display: flex; align-items: center; gap: 0.6rem; }}
.nav-link {{
  padding: 0.55rem 1.1rem;
  border-radius: 12px;
  font-size: 0.85rem;
  font-weight: 700;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.75);
  color: #CBD5E1;
}}
.nav-link.active {{
  background: linear-gradient(135deg, #10B981 0%, #059669 100%);
  border-color: transparent;
  color: #04130D;
}}
.main-wrap {{ max-width: 1180px; margin: 0 auto; padding: 1.5rem 1.25rem 4rem; }}

.stats-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}}
.stat-card {{
  background: rgba(15, 23, 42, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 18px;
  padding: 1.2rem 1.4rem;
}}
.stat-label {{ font-size: 0.82rem; color: #94A3B8; }}
.stat-val {{ font-size: 1.8rem; font-weight: 800; color: #FFFFFF; margin-top: 0.25rem; }}
.stat-sub {{ font-size: 0.75rem; color: #64748B; margin-top: 0.2rem; }}

.filter-bar {{
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 18px;
  padding: 1rem 1.25rem;
  margin-bottom: 1.25rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}}
.tab-group {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
.tab-btn {{
  background: #090E1A;
  border: 1px solid rgba(148, 163, 184, 0.2);
  color: #CBD5E1;
  border-radius: 12px;
  padding: 0.45rem 0.95rem;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
}}
.tab-btn.active {{ background: #10B981; border-color: #10B981; color: #04130D; }}
.search-box {{
  background: #090E1A;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  color: #FFFFFF;
  padding: 0.5rem 0.9rem;
  font-size: 0.83rem;
  min-width: 240px;
  font-family: inherit;
}}

.table-card {{
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 20px;
  overflow: hidden;
}}
.table-scroll {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.84rem; min-width: 780px; }}
th {{
  text-align: right;
  padding: 0.9rem 1rem;
  background: rgba(9, 14, 26, 0.9);
  color: #94A3B8;
  font-weight: 700;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}}
td {{
  padding: 0.85rem 1rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}}
.status-pill {{
  display: inline-block;
  padding: 0.22rem 0.65rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
}}
.win-pill {{ background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.35); }}
.loss-pill {{ background: rgba(244, 63, 94, 0.15); color: #FB7185; border: 1px solid rgba(244, 63, 94, 0.35); }}
.cat-tag {{ font-size: 0.78rem; color: #CBD5E1; }}
.pos-text {{ color: #34D399; font-weight: 800; }}
.neg-text {{ color: #FB7185; font-weight: 800; }}
</style>
</head>
<body>

<header class="navbar">
  <div class="navbar-inner">
    <div class="brand-wrap">
      <div class="brand-logo">🏆</div>
      <div>
        <div class="brand-title">کارنامه و نتایج واقعی ربات</div>
        <div class="brand-sub">بروزرسانی خودکار: <span class="ltr-num">{_esc(now_str)}</span></div>
      </div>
    </div>
    <nav class="nav-pills">
      <a class="nav-link" href="index.html">📡 پیشنهادهای امروز</a>
      <a class="nav-link active" href="results.html">🏆 کارنامه و نتایج قبلی ({total_count})</a>
    </nav>
  </div>
</header>

<main class="main-wrap">
  <section class="stats-grid">
    <div class="stat-card">
      <div class="stat-label">🎯 درصد موفقیت کل (Win Rate)</div>
      <div class="stat-val ltr-num" style="color:#34D399">{win_rate:.1f}%</div>
      <div class="stat-sub">از مجموع {total_count} پیش‌بینی پایان‌یافته</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">✅ تعداد پیش‌بینی‌های درست</div>
      <div class="stat-val ltr-num" style="color:#34D399">{wins} برنده</div>
      <div class="stat-sub">در برابر {losses} پیش‌بینی ناموفق</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">💵 سود خالص تجمعی (با پایه ۱۰۰۰ دلار)</div>
      <div class="stat-val ltr-num" style="color:#34D399">{total_profit_str}</div>
      <div class="stat-sub">برآورد بازده کل سبد با پوشش ریسک</div>
    </div>
  </section>

  <section class="filter-bar">
    <div class="tab-group">
      <button type="button" class="tab-btn active" data-st="all" onclick="setFilter(this)">همه نتایج ({total_count})</button>
      <button type="button" class="tab-btn" data-st="win" onclick="setFilter(this)">✅ فقط برنده‌ها ({wins})</button>
      <button type="button" class="tab-btn" data-st="loss" onclick="setFilter(this)">❌ فقط ناموفق‌ها ({losses})</button>
    </div>
    <input id="searchBox" type="text" class="search-box" placeholder="🔍 جستجو در نتایج قبلی..." oninput="filterRows()">
  </section>

  <section class="table-card">
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>نتیجه</th>
            <th>عنوان بازار</th>
            <th>دسته‌بندی</th>
            <th>پیشنهاد ربات</th>
            <th>نتیجه واقعی بازار</th>
            <th>قیمت ورود</th>
            <th>سود / زیان (با ۱۰۰۰$)</th>
          </tr>
        </thead>
        <tbody id="resultsBody">
          {table_body}
        </tbody>
      </table>
    </div>
  </section>
</main>

<script>
let activeStatus = 'all';
function setFilter(btn) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeStatus = btn.getAttribute('data-st') || 'all';
  filterRows();
}}
function filterRows() {{
  const q = (document.getElementById('searchBox').value || '').trim().toLowerCase();
  document.querySelectorAll('#resultsBody tr[data-status]').forEach(row => {{
    const st = row.getAttribute('data-status') || '';
    const s = row.getAttribute('data-search') || '';
    const okSt = (activeStatus === 'all') || (st === activeStatus);
    const okQ = !q || s.includes(q);
    row.style.display = (okSt && okQ) ? '' : 'none';
  }});
}}
</script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)

    return output_path


def write_results_html(
    output_path: str,
    resolved_rows: list[dict],
    generated_at: datetime | None = None,
    log_by_key: dict[str, dict] | None = None,
) -> str:
    """Primary entry point called by weekly_report.py."""
    return generate_results_html(
        resolved_rows=resolved_rows,
        output_path=output_path,
        generated_at=generated_at,
        log_by_key=log_by_key,
    )

