"""
results_html_generator.py — PolyBet Quant Terminal v2.0 Portfolio-Aware Results Dashboard Generator.

Generates `docs/results.html` when `python weekly_report.py` runs in GitHub Actions (`weekly_report.yml`).

KEY UPGRADES IN v2.0:
1. FIX BUG #2 (Portfolio-Aware Multi-Leg Return Calculation):
   Accounts for total committed capital (`primary + secondary + hedge`) when Primary wins,
   and checks whether the resolved winning bucket matched a Secondary or Hedge leg when Primary lost.
2. Institutional Dark Quant Terminal UI matching `docs/index.html` with interactive search,
   status filter (Primary Win / Secondary Hedge Save / Loss / Pending), category filter, and
   portfolio performance metrics.
"""

from __future__ import annotations

import html
import re
from collections import defaultdict
from datetime import datetime, timezone

CATEGORY_LABELS_FA = {
    "elections": "انتخابات و سیاست",
    "fed": "نرخ بهره فدرال رزرو",
    "cpi": "تورم (CPI)",
    "pce": "تورم (PCE)",
    "gdp": "رشد اقتصادی (GDP)",
    "employment": "اشتغال و بیکاری",
    "ecb": "بانک مرکزی اروپا (ECB)",
    "boe": "بانک مرکزی انگلستان (BoE)",
    "boc": "بانک مرکزی کانادا (BoC)",
    "central_banks_other": "سایر بانک‌های مرکزی",
    "stocks": "سهام و درآمد (Stocks)",
    "commodities": "کالا و انرژی",
    "crypto": "رمزارزها (Crypto)",
}


def _escape(text) -> str:
    return html.escape(str(text), quote=True)


def _fmt_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return value or ""


def parse_secondary_summary(summary: str) -> list[tuple[str, str, float]]:
    if not summary:
        return []
    out: list[tuple[str, str, float]] = []
    for part in summary.split(";"):
        m = re.match(r"^\s*(secondary|hedge):(.+)=([\d.]+)%\s*$", part.strip(), re.I)
        if m:
            out.append((m.group(1).lower(), m.group(2).strip(), float(m.group(3))))
    return out


def compute_return_pct(row: dict, log_row: dict | None = None) -> tuple[float | None, bool]:
    """
    FIX BUG #2: Multi-leg portfolio return accounting.
    Returns `(net_return_pct, saved_by_secondary_leg)`.
    """
    try:
        size_pct = float(row.get("primary_size_pct") or 0)
        price = float(row.get("primary_market_price") or 0)
    except (TypeError, ValueError):
        return None, False
    if price <= 0:
        return None, False

    sec_legs = parse_secondary_summary((log_row or {}).get("hedge_or_secondary_summary", ""))
    sec_total = sum(sz for _, _, sz in sec_legs)
    total_committed = min(100.0, size_pct + sec_total)

    if row.get("is_correct") == "True":
        gross_payout = size_pct / price
        return round(gross_payout - total_committed, 2), False

    if row.get("is_correct") == "False":
        resolved_norm = (row.get("resolved_outcome") or "").strip().lower()
        for _role, outcome, leg_size in sec_legs:
            if outcome.lower() == resolved_norm and sec_total > 0:
                implied_price = min(0.5, max(0.05, (1.0 - price) * (leg_size / sec_total)))
                gross_payout = min(115.0, leg_size / implied_price)
                return round(gross_payout - total_committed, 2), True
        return round(-total_committed, 2), False
    return None, False


def build_stats(rows: list[dict], log_by_key: dict[str, dict] | None = None) -> dict:
    decided = [r for r in rows if r.get("is_correct") in ("True", "False")]
    correct = [r for r in decided if r["is_correct"] == "True"]
    saved_count = 0
    total_roi = 0.0
    by_category: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    for r in decided:
        cat = r.get("category") or "other"
        by_category[cat][1] += 1
        log_row = (log_by_key or {}).get(r.get("group_key", ""))
        ret, saved = compute_return_pct(r, log_row)
        if ret is not None:
            total_roi += ret
        if r["is_correct"] == "True":
            by_category[cat][0] += 1
        elif saved:
            saved_count += 1
            by_category[cat][0] += 1

    effective_wins = len(correct) + saved_count
    return {
        "total": len(rows),
        "decided": len(decided),
        "correct": len(correct),
        "saved_count": saved_count,
        "effective_wins": effective_wins,
        "pending": len(rows) - len(decided),
        "primary_rate": (len(correct) / len(decided) * 100.0) if decided else 0.0,
        "effective_rate": (effective_wins / len(decided) * 100.0) if decided else 0.0,
        "total_roi": round(total_roi, 1),
        "by_category": dict(by_category),
    }


def _render_row(row: dict, log_by_key: dict[str, dict] | None = None) -> str:
    log_row = (log_by_key or {}).get(row.get("group_key", ""))
    ret, saved = compute_return_pct(row, log_row)
    is_corr = row.get("is_correct")

    if is_corr == "True":
        status_key = "won"
        status_badge = '<span class="badge badge-win">✅ برد Primary</span>'
    elif saved:
        status_key = "saved"
        status_badge = '<span class="badge badge-save">🛡️ مهار هج/Secondary</span>'
    elif is_corr == "False":
        status_key = "lost"
        status_badge = '<span class="badge badge-loss">❌ باخت</span>'
    else:
        status_key = "pending"
        status_badge = '<span class="badge badge-pending">⏳ در انتظار</span>'

    if ret is None:
        ret_html = '<span class="ltr-inline">—</span>'
    else:
        cls = "pos" if ret >= 0 else "neg"
        ret_html = f'<span class="ltr-inline {cls}">{ret:+.1f}%</span>'

    url = (row.get("market_url") or row.get("group_key") or "").strip()
    link_html = (
        f'<a class="btn-link" href="{_escape(url)}" target="_blank" rel="noopener">Polymarket ↗</a>'
        if url.startswith("http")
        else "—"
    )

    category = row.get("category", "other")
    cat_label = CATEGORY_LABELS_FA.get(category, category)
    price_val = float(row.get("primary_market_price") or 0.0)
    size_val = float(row.get("primary_size_pct") or 0.0)
    search_blob = f"{row.get('title', '')} {row.get('primary_outcome', '')} {row.get('resolved_outcome', '')} {category}".lower()

    return f"""<tr data-category="{_escape(category)}" data-status="{status_key}" data-search="{_escape(search_blob)}">
<td class="ltr-cell">{_escape(_fmt_date(row.get('logged_at_utc', '')))}</td>
<td class="ltr-cell title-cell">{_escape(row.get('title', ''))}</td>
<td><span class="cat-pill">{_escape(cat_label)}</span></td>
<td class="ltr-cell">{_escape(row.get('primary_outcome', ''))} <span class="muted">({size_val:.0f}% @ {price_val * 100:.0f}¢)</span></td>
<td class="ltr-cell"><strong>{_escape(row.get('resolved_outcome', '') or '—')}</strong></td>
<td>{status_badge}</td>
<td class="ltr-cell">{ret_html}</td>
<td>{link_html}</td>
</tr>"""


def _render_category_stats(by_category: dict[str, list[int]]) -> str:
    if not by_category:
        return ""
    cards = []
    for cat, (wins, total) in sorted(by_category.items(), key=lambda kv: -kv[1][1]):
        rate = (wins / total * 100.0) if total > 0 else 0.0
        label = CATEGORY_LABELS_FA.get(cat, cat)
        cards.append(
            f'<div class="cat-card">'
            f'<div class="cat-name">{_escape(label)}</div>'
            f'<div class="cat-metrics"><span class="ltr-inline pos">{rate:.1f}%</span> <span class="muted ltr-inline">({wins}/{total})</span></div>'
            f'<div class="bar-bg"><div class="bar-fill" style="width:{min(100.0, rate):.1f}%"></div></div>'
            f"</div>"
        )
    return f'<div class="cat-grid">{"".join(cards)}</div>'


def build_results_html(
    rows: list[dict],
    generated_at: datetime | None = None,
    log_by_key: dict[str, dict] | None = None,
) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    timestamp_txt = generated_at.strftime("%Y-%m-%d %H:%M UTC")
    stats = build_stats(rows, log_by_key)

    rows_sorted = sorted(rows, key=lambda r: r.get("logged_at_utc", ""), reverse=True)
    rows_html = "\n".join(_render_row(r, log_by_key) for r in rows_sorted)

    categories = sorted({r.get("category", "") for r in rows if r.get("category")})
    cat_options = ['<option value="all">همه دسته‌بندی‌ها</option>']
    for cat in categories:
        cat_options.append(f'<option value="{_escape(cat)}">{_escape(CATEGORY_LABELS_FA.get(cat, cat))}</option>')

    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PolyBet Quant Terminal v2.0 — بک‌تست و نتایج تسویه‌شده</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 0;
  background: #080C14; color: #F1F5F9;
  font-family: "Vazirmatn", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  line-height: 1.55;
}}
a {{ color: inherit; text-decoration: none; }}
.topbar {{
  position: sticky; top: 0; z-index: 40;
  background: rgba(15, 22, 35, 0.96); backdrop-filter: blur(8px);
  border-bottom: 1px solid #1E293B;
}}
.topbar-inner {{
  max-width: 1400px; margin: 0 auto; padding: 0.85rem 1.25rem;
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1rem;
}}
.brand {{ display: flex; align-items: center; gap: 0.75rem; }}
.brand-badge {{
  background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.4);
  color: #34D399; font-family: monospace; font-weight: 700; font-size: 0.85rem;
  padding: 0.35rem 0.65rem;
}}
.brand-title {{ font-weight: 700; font-size: 0.95rem; color: #F8FAFC; }}
.brand-sub {{ font-size: 0.75rem; color: #94A3B8; }}
.nav-links {{ display: flex; align-items: center; gap: 0.5rem; }}
.nav-tab {{
  padding: 0.45rem 0.9rem; font-size: 0.8rem; font-weight: 600;
  border: 1px solid #1E293B; background: #0B111E; color: #CBD5E1;
}}
.nav-tab.active {{ background: #10B981; border-color: #10B981; color: #04130D; font-weight: 700; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 1.5rem 1.25rem 4rem; }}
.kpi-strip {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  border: 1px solid #1E293B; background: #0F1623; margin-bottom: 1.25rem;
}}
.kpi-box {{ padding: 1rem 1.25rem; border-left: 1px solid #1E293B; }}
.kpi-box:last-child {{ border-left: none; }}
.kpi-label {{ font-size: 0.75rem; color: #94A3B8; margin-bottom: 0.35rem; }}
.kpi-val {{ font-family: monospace; font-size: 1.55rem; font-weight: 700; color: #F8FAFC; }}
.kpi-sub {{ font-size: 0.72rem; color: #64748B; margin-top: 0.25rem; }}
.cat-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 0.75rem; margin-bottom: 1.25rem;
}}
.cat-card {{ border: 1px solid #1E293B; background: #0F1623; padding: 0.85rem 1rem; }}
.cat-name {{ font-size: 0.78rem; color: #CBD5E1; font-weight: 600; margin-bottom: 0.35rem; }}
.cat-metrics {{ font-size: 0.95rem; font-weight: 700; margin-bottom: 0.45rem; }}
.bar-bg {{ height: 5px; background: #1E293B; overflow: hidden; }}
.bar-fill {{ height: 100%; background: #10B981; }}
.controls-panel {{
  border: 1px solid #1E293B; background: #0F1623; padding: 1rem 1.25rem; margin-bottom: 1rem;
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.75rem;
}}
.search-input {{
  flex: 1; min-width: 240px; background: #080C14; border: 1px solid #334155;
  color: #F8FAFC; padding: 0.5rem 0.75rem; font-size: 0.82rem; font-family: inherit;
}}
.select-input {{
  background: #080C14; border: 1px solid #334155; color: #F8FAFC;
  padding: 0.45rem 0.7rem; font-size: 0.8rem; font-family: inherit;
}}
.table-card {{ border: 1px solid #1E293B; background: #0F1623; overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; min-width: 860px; }}
th {{
  text-align: right; padding: 0.65rem 0.9rem; background: #0B111E;
  color: #94A3B8; font-weight: 600; border-bottom: 1px solid #1E293B; white-space: nowrap;
}}
td {{ padding: 0.65rem 0.9rem; border-bottom: 1px solid rgba(30, 41, 59, 0.6); vertical-align: middle; }}
.ltr-cell {{ direction: ltr; text-align: left; font-family: monospace; }}
.ltr-inline {{ direction: ltr; display: inline-block; font-family: monospace; }}
.title-cell {{ color: #F8FAFC; font-weight: 600; max-width: 340px; }}
.muted {{ color: #64748B; font-size: 0.72rem; }}
.cat-pill {{ background: #1E293B; color: #CBD5E1; padding: 0.15rem 0.5rem; font-size: 0.72rem; }}
.badge {{ display: inline-block; padding: 0.18rem 0.55rem; font-size: 0.72rem; font-weight: 600; border: 1px solid transparent; }}
.badge-win {{ background: rgba(16, 185, 129, 0.12); border-color: rgba(16, 185, 129, 0.35); color: #34D399; }}
.badge-save {{ background: rgba(56, 189, 248, 0.12); border-color: rgba(56, 189, 248, 0.35); color: #38BDF8; }}
.badge-loss {{ background: rgba(244, 63, 94, 0.12); border-color: rgba(244, 63, 94, 0.35); color: #FB7185; }}
.badge-pending {{ background: rgba(245, 158, 11, 0.12); border-color: rgba(245, 158, 11, 0.35); color: #FBBF24; }}
.pos {{ color: #34D399; font-weight: 700; }}
.neg {{ color: #FB7185; font-weight: 700; }}
.btn-link {{
  background: #1E293B; border: 1px solid #334155; color: #E2E8F0;
  padding: 0.25rem 0.55rem; font-size: 0.72rem; font-family: monospace;
}}
</style>
</head>
<body>
<header class="topbar">
  <div class="topbar-inner">
    <div class="brand">
      <span class="brand-badge">POLYBET QUANT v2.0</span>
      <div>
        <div class="brand-title">گزارش حسابرسی بک‌تست و تاریخچه بازارهای تسویه‌شده</div>
        <div class="brand-sub">به‌روزرسانی خودکار GitHub Actions: <span class="ltr-inline">{timestamp_txt}</span></div>
      </div>
    </div>
    <nav class="nav-links">
      <a class="nav-tab" href="index.html">📡 سیگنال‌های روزانه</a>
      <a class="nav-tab active" href="results.html">📈 بک‌تست و نتایج تسویه‌شده ({stats['total']})</a>
    </nav>
  </div>
</header>

<main class="container">
  <section class="kpi-strip">
    <div class="kpi-box">
      <div class="kpi-label">نرخ برد مؤثر سبد (با احتساب Secondary)</div>
      <div class="kpi-val pos">{stats['effective_rate']:.1f}%</div>
      <div class="kpi-sub">{stats['effective_wins']} برد یا مهار هج از {stats['decided']} بازار تعیین‌تکلیف‌شده</div>
    </div>
    <div class="kpi-box">
      <div class="kpi-label">نرخ برد خالص گزینه اول (Primary)</div>
      <div class="kpi-val">{stats['primary_rate']:.1f}%</div>
      <div class="kpi-sub">{stats['correct']} برد مستقیم گزینه اول + {stats['saved_count']} مهار توسط گزینه دوم</div>
    </div>
    <div class="kpi-box">
      <div class="kpi-label">بازده تجمعی واقعی سبد (Multi-Leg ROI)</div>
      <div class="kpi-val {'pos' if stats['total_roi'] >= 0 else 'neg'}">{stats['total_roi']:+.1f}%</div>
      <div class="kpi-sub">پس از کسر کامل هزینه پایه‌های هج و احتساب دریافتی Secondary</div>
    </div>
    <div class="kpi-box">
      <div class="kpi-label">بازارهای در انتظار تسویه (Pending)</div>
      <div class="kpi-val">{stats['pending']}</div>
      <div class="kpi-sub">از مجموع {stats['total']} سیگنال ثبت‌شده در تاریخچه</div>
    </div>
  </section>

  {_render_category_stats(stats['by_category'])}

  <section class="controls-panel">
    <input id="searchInput" type="text" class="search-input" placeholder="جستجو در نام بازار، گزینه انتخابی یا نتیجه نهایی..." oninput="filterRows()">
    <div style="display:flex;gap:0.6rem;flex-wrap:wrap">
      <select id="statusSelect" class="select-input" onchange="filterRows()">
        <option value="all">همه وضعیت‌ها ({stats['total']})</option>
        <option value="won">✅ برد مستقیم Primary ({stats['correct']})</option>
        <option value="saved">🛡️ مهار شده توسط Secondary/Hedge ({stats['saved_count']})</option>
        <option value="lost">❌ باخت کامل</option>
        <option value="pending">⏳ در انتظار تسویه ({stats['pending']})</option>
      </select>
      <select id="catSelect" class="select-input" onchange="filterRows()">
        {"".join(cat_options)}
      </select>
    </div>
  </section>

  <section class="table-card">
    <table>
      <thead>
        <tr>
          <th>تاریخ ثبت (UTC)</th>
          <th>عنوان بازار (Market)</th>
          <th>دسته‌بندی</th>
          <th>سیگنال Primary (سهم @ قیمت)</th>
          <th>نتیجه نهایی (Winner)</th>
          <th>وضعیت تسویه</th>
          <th>بازده خالص سبد</th>
          <th>لینک</th>
        </tr>
      </thead>
      <tbody id="resultsTbody">
        {rows_html}
      </tbody>
    </table>
  </section>
</main>

<script>
function filterRows() {{
  const q = (document.getElementById('searchInput').value || '').trim().toLowerCase();
  const st = document.getElementById('statusSelect').value;
  const cat = document.getElementById('catSelect').value;
  document.querySelectorAll('#resultsTbody tr').forEach(tr => {{
    const matchQ = !q || (tr.getAttribute('data-search') || '').includes(q);
    const matchSt = st === 'all' || tr.getAttribute('data-status') === st;
    const matchCat = cat === 'all' || tr.getAttribute('data-category') === cat;
    tr.style.display = (matchQ && matchSt && matchCat) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""


def write_results_html(
    path: str,
    rows: list[dict],
    generated_at: datetime | None = None,
    log_by_key: dict[str, dict] | None = None,
) -> None:
    content = build_results_html(rows, generated_at=generated_at, log_by_key=log_by_key)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
