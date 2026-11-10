"""
html_generator.py — PolyBet Quant Terminal v2.0 Static Dashboard Generator for GitHub Pages.

Generates `docs/index.html` when `python main.py` runs in GitHub Actions (`daily_scan.yml`).

KEY UPGRADES IN v2.0:
1. Institutional Dark Quant Terminal UI (RTL Persian + LTR Monospace Numerals) matching
   the full PolyBet v2.0 design system — zero external build step required on GitHub Pages.
2. Interactive Live Bankroll ($) Calculator: changing the bankroll input dynamically updates
   the Dollar Allocation ($) and Share Count (Shares) for every Primary, Secondary, and Hedge leg.
3. Interactive Search, Sort (Confidence / Edge / Net ROI / Days to Resolve), Category Filters,
   and Barrier Option Trap (<15¢) toggle.
4. Interactive Kelly Criterion & Multi-Leg Hedge Simulator Modal built directly into the page.
5. Full Candidate Outcomes & Prices passed to the AI Analysis Worker (Fix Bug #8).
6. Exact Net ROI if Wins (`(size_pct / market_price) - 100%`) displayed for every leg.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from position_logic import PositionPlan
from scanner import ScannedMarket

ROLE_LABELS_FA = {
    "primary": "گزینه اصلی (Primary)",
    "secondary": "گزینه دوم (Secondary)",
    "hedge": "پوشش هج (Hedge)",
}
ROLE_BADGE_CLASSES = {
    "primary": "role-primary",
    "secondary": "role-secondary",
    "hedge": "role-hedge",
}

CATEGORY_LABELS_FA = {
    "elections": "انتخابات و سیاست",
    "fed": "نرخ بهره فدرال رزرو (FOMC)",
    "cpi": "تورم و شاخص قیمت (CPI)",
    "pce": "تورم مصرف‌کننده (PCE)",
    "gdp": "رشد اقتصادی (GDP)",
    "employment": "اشتغال و نرخ بیکاری (NFP/BLS)",
    "ecb": "بانک مرکزی اروپا (ECB)",
    "boe": "بانک مرکزی انگلستان (BoE)",
    "boc": "بانک مرکزی کانادا (BoC)",
    "central_banks_other": "سایر بانک‌های مرکزی",
    "stocks": "سهام و گزارش درآمدی (EPS)",
    "commodities": "کالاهای اساسی و انرژی",
    "crypto": "رمزارزها و نوسان ضمنی",
}

AI_WORKER_URL = "https://polybet-ai-research.ericlamar008.workers.dev/"
HIGH_CONFIDENCE_PRICE_THRESHOLD = 0.90

SECTION_DEFS: list[tuple[str, str, str, frozenset[str]]] = [
    ("politics", "انتخابات و سیاست", "انتخابات و سیاست (Politics & Elections)", frozenset({"elections"})),
    (
        "economy",
        "اقتصاد کلان و بانک‌های مرکزی",
        "اقتصاد کلان و بانک‌های مرکزی (Macro & Central Banks)",
        frozenset({"fed", "cpi", "pce", "gdp", "employment", "ecb", "boc", "boe", "central_banks_other"}),
    ),
    (
        "markets",
        "سهام، کالا و رمزارز",
        "بازارهای مالی، سهام و رمزارز (Stocks, Commodities & Crypto)",
        frozenset({"stocks", "commodities", "crypto"}),
    ),
]
OTHER_KEY = "other"


def _escape(text) -> str:
    return html.escape(str(text), quote=True)


def _section_for_category(category: str) -> str:
    for key, _nav_label, _title, categories in SECTION_DEFS:
        if category in categories:
            return key
    return OTHER_KEY


def _render_allocation_row(alloc) -> str:
    role_cls = ROLE_BADGE_CLASSES.get(alloc.role, "role-hedge")
    role_label = ROLE_LABELS_FA.get(alloc.role, alloc.role)
    price = float(alloc.market_price or 0.0)
    size_pct = float(alloc.size_pct or 0.0)
    price_cents = f"{price * 100:.2f}¢" if price > 0 else "—"

    net_roi = getattr(alloc, "net_roi_if_wins_pct", None)
    if net_roi is None and price > 0:
        net_roi = round((size_pct / price) - 100.0, 2)
    gross_payout = round(size_pct / price, 1) if price > 0 else 0.0
    roi_txt = f"{net_roi:+.2f}%" if net_roi is not None else "—"
    roi_cls = "pos" if (net_roi or 0) >= 0 else "neg"

    default_dollars = round(1000.0 * (size_pct / 100.0), 2)
    default_shares = round(default_dollars / price, 1) if price > 0 else 0.0

    return (
        f'<tr data-size-pct="{size_pct:.4f}" data-price="{price:.6f}">'
        f'<td><span class="role-badge {role_cls}">{_escape(role_label)}</span></td>'
        f'<td class="ltr-cell outcome-cell">{_escape(alloc.outcome)}</td>'
        f'<td class="ltr-cell">{size_pct:.2f}%</td>'
        f'<td class="ltr-cell js-dollar-cell">${default_dollars:.2f}</td>'
        f'<td class="ltr-cell">{price_cents}</td>'
        f'<td class="ltr-cell js-shares-cell">{default_shares:.1f}</td>'
        f'<td class="ltr-cell">{gross_payout:.1f}%</td>'
        f'<td class="ltr-cell {roi_cls}">{roi_txt}</td>'
        f"</tr>"
    )


def _render_ai_widget(market: ScannedMarket, title: str, plan: PositionPlan) -> str:
    """FIX BUG #8: Send the full event's candidate outcomes and prices to the AI Worker."""
    outcomes = [a.outcome for a in plan.allocations] or market.outcomes
    outcome_prices = [a.market_price or 0.0 for a in plan.allocations] or market.outcome_prices
    payload = {
        "market_id": market.market_id,
        "question": title or market.question,
        "outcomes": outcomes,
        "outcome_prices": outcome_prices,
        "end_date": market.end_date.isoformat() if market.end_date else None,
        "category": market.category,
        "consensus_score": plan.consensus_score,
        "edge": plan.edge,
    }
    payload_attr = _escape(json.dumps(payload))
    return (
        f'<button type="button" class="btn-action btn-ai" data-market="{payload_attr}" '
        f'onclick="runAiAnalysis(this)">🧠 تحلیل هوش مصنوعی</button>'
    )


def _render_card(market: ScannedMarket, title: str, plan: PositionPlan, days_to_resolve: float) -> str:
    primary = plan.primary
    primary_outcome = primary.outcome if primary else "—"
    primary_size = float(primary.size_pct) if primary else 0.0
    primary_price = float(primary.market_price or 0.5) if primary else 0.5
    primary_net_roi = getattr(primary, "net_roi_if_wins_pct", None)
    if primary_net_roi is None and primary_price > 0:
        primary_net_roi = round((primary_size / primary_price) - 100.0, 2)
    primary_net_roi = primary_net_roi or 0.0

    is_barrier_trap = "1" if primary_price < 0.15 else "0"
    sec_key = _section_for_category(market.category)
    cat_label = CATEGORY_LABELS_FA.get(market.category, market.category)
    stop_loss_cents = round(primary_price * 0.65 * 100, 1)
    take_profit_cents = round(min(0.98, primary_price + (1.0 - primary_price) * 0.65) * 100, 1)

    warning_html = ""
    if plan.warning:
        warning_html = f'<div class="warning-banner">⚠️ {_escape(plan.warning)}</div>'

    rows_html = "".join(_render_allocation_row(a) for a in plan.allocations)
    ai_btn_html = _render_ai_widget(market, title, plan)
    result_id = f"ai-result-{_escape(market.market_id)}"

    sim_payload = _escape(
        json.dumps(
            {
                "title": title,
                "primaryOutcome": primary_outcome,
                "primaryPrice": primary_price,
                "edge": plan.edge,
                "consensus": plan.consensus_score,
            }
        )
    )

    return f"""<article class="market-card"
  data-section="{_escape(sec_key)}"
  data-category="{_escape(market.category)}"
  data-trap="{is_barrier_trap}"
  data-confidence="{plan.consensus_score:.2f}"
  data-edge="{plan.edge:.4f}"
  data-roi="{primary_net_roi:.2f}"
  data-days="{days_to_resolve:.2f}"
  data-search="{_escape((title + ' ' + primary_outcome + ' ' + market.category).lower())}">
  <div class="card-header">
    <div>
      <div class="card-meta">
        <span class="cat-tag">{_escape(cat_label)}</span>
        <span>·</span>
        <span>تسویه: <strong class="ltr-inline">{days_to_resolve:.1f}d</strong></span>
        <span>·</span>
        <span>تعداد منابع: <strong class="ltr-inline">{plan.num_sources}</strong></span>
        <span>·</span>
        <span>لبه کوانت (Edge): <strong class="ltr-inline pos">+{plan.edge * 100:.1f}%</strong></span>
      </div>
      <h3 class="card-title" dir="ltr">{_escape(title)}</h3>
    </div>
    <div class="card-actions">
      {ai_btn_html}
      <button type="button" class="btn-action" data-sim="{sim_payload}" onclick="openKellyModal(this)">⚖️ شبیه‌ساز کِلی</button>
      <a class="btn-action btn-link" href="{_escape(market.url)}" target="_blank" rel="noopener">Polymarket ↗</a>
    </div>
  </div>

  <div class="metrics-strip">
    <div class="metric-cell">
      <div class="metric-label">گزینه اصلی (Primary)</div>
      <div class="metric-val ltr-inline">{_escape(primary_outcome)}</div>
    </div>
    <div class="metric-cell">
      <div class="metric-label">سایز بهینه (کِلی v2)</div>
      <div class="metric-val ltr-inline pos">{primary_size:.2f}% <span class="js-primary-dollar" data-pct="{primary_size:.4f}">(${round(10 * primary_size)})</span></div>
    </div>
    <div class="metric-cell">
      <div class="metric-label">قیمت بازار (CLOB)</div>
      <div class="metric-val ltr-inline">{primary_price * 100:.1f}¢</div>
    </div>
    <div class="metric-cell">
      <div class="metric-label">اجماع بیزی (کالیبره)</div>
      <div class="metric-val ltr-inline">{plan.consensus_score:.1f}%</div>
    </div>
    <div class="metric-cell">
      <div class="metric-label">سود خالص اگر Primary ببرد</div>
      <div class="metric-val ltr-inline {'pos' if primary_net_roi >= 0 else 'neg'}">{primary_net_roi:+.2f}%</div>
    </div>
    <div class="metric-cell">
      <div class="metric-label">حد ضرر / حد سود پیشنهادی</div>
      <div class="metric-val ltr-inline">SL: {stop_loss_cents}¢ · TP: {take_profit_cents}¢</div>
    </div>
  </div>

  {warning_html}
  <div class="ai-result" id="{result_id}"></div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>نقش پایه (Role)</th>
          <th>گزینه (Outcome)</th>
          <th>سهم بودجه</th>
          <th>مبلغ دلاری ($)</th>
          <th>قیمت فعلی</th>
          <th>تعداد سهام (Shares)</th>
          <th>دریافتی ناخالص</th>
          <th>سود/زیان خالص کل سبد در صورت برد</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>
</article>"""


def build_html(results, generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    timestamp_txt = generated_at.strftime("%Y-%m-%d %H:%M UTC")

    total_count = len(results)
    trap_count = sum(
        1
        for _m, _t, plan, _d in results
        if plan.primary is not None and (plan.primary.market_price or 0.5) < 0.15
    )
    high_conf_count = sum(
        1
        for _m, _t, plan, _d in results
        if plan.primary is not None and (plan.primary.market_price or 0.0) >= HIGH_CONFIDENCE_PRICE_THRESHOLD
    )

    cards_html = "\n".join(
        _render_card(market, card_title, plan, days_to_resolve)
        for market, card_title, plan, days_to_resolve in results
    )
    if not cards_html:
        cards_html = '<div class="empty-state">هیچ بازاری در بازه زمانی تسویه یافت نشد.</div>'

    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PolyBet Quant Terminal v2.0 — سیگنال‌های زنده و سایزینگ کِلی</title>
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
  border: 1px solid #1E293B; background: #0B111E; color: #CBD5E1; cursor: pointer;
}}
.nav-tab.active {{ background: #10B981; border-color: #10B981; color: #04130D; font-weight: 700; }}
.nav-tab:hover:not(.active) {{ border-color: #334155; color: #FFFFFF; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 1.5rem 1.25rem 4rem; }}
.kpi-strip {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  border: 1px solid #1E293B; background: #0F1623; margin-bottom: 1.25rem;
}}
.kpi-box {{ padding: 1rem 1.25rem; border-left: 1px solid #1E293B; }}
.kpi-box:last-child {{ border-left: none; }}
.kpi-label {{ font-size: 0.75rem; color: #94A3B8; margin-bottom: 0.35rem; }}
.kpi-val {{ font-family: monospace; font-size: 1.55rem; font-weight: 700; color: #F8FAFC; }}
.kpi-sub {{ font-size: 0.72rem; color: #64748B; margin-top: 0.25rem; }}
.bankroll-input {{
  background: #080C14; border: 1px solid #334155; color: #34D399;
  font-family: monospace; font-size: 1.15rem; font-weight: 700;
  padding: 0.25rem 0.5rem; width: 130px; text-align: left; direction: ltr;
}}
.controls-panel {{
  border: 1px solid #1E293B; background: #0F1623; padding: 1rem 1.25rem; margin-bottom: 1.25rem;
}}
.controls-row {{
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
.filter-pills {{
  display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.85rem; padding-top: 0.85rem;
  border-top: 1px solid #1E293B;
}}
.filter-btn {{
  background: #080C14; border: 1px solid #1E293B; color: #94A3B8;
  padding: 0.35rem 0.75rem; font-size: 0.76rem; cursor: pointer; font-family: inherit;
}}
.filter-btn.active {{ background: #10B981; border-color: #10B981; color: #04130D; font-weight: 700; }}
.market-card {{
  border: 1px solid #1E293B; background: #0F1623; margin-bottom: 1rem;
  transition: border-color 0.15s ease;
}}
.market-card:hover {{ border-color: #334155; }}
.card-header {{
  padding: 1rem 1.25rem; border-bottom: 1px solid #1E293B;
  display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 1rem;
}}
.card-meta {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem; font-size: 0.75rem; color: #94A3B8; margin-bottom: 0.35rem; }}
.cat-tag {{ color: #34D399; font-weight: 600; }}
.card-title {{ margin: 0; font-size: 1rem; font-weight: 700; color: #F8FAFC; text-align: left; }}
.card-actions {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem; }}
.btn-action {{
  background: #1E293B; border: 1px solid #334155; color: #E2E8F0;
  padding: 0.38rem 0.7rem; font-size: 0.75rem; cursor: pointer; font-family: inherit;
}}
.btn-action:hover {{ background: #334155; color: #FFFFFF; }}
.btn-ai {{ background: rgba(16, 185, 129, 0.14); border-color: rgba(16, 185, 129, 0.4); color: #34D399; }}
.metrics-strip {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
  background: rgba(8, 12, 20, 0.65); border-bottom: 1px solid #1E293B;
}}
.metric-cell {{ padding: 0.65rem 1rem; border-left: 1px solid #1E293B; }}
.metric-cell:last-child {{ border-left: none; }}
.metric-label {{ font-size: 0.7rem; color: #64748B; margin-bottom: 0.2rem; }}
.metric-val {{ font-family: monospace; font-size: 0.88rem; font-weight: 700; color: #F1F5F9; }}
.warning-banner {{
  padding: 0.6rem 1.25rem; background: rgba(245, 158, 11, 0.12);
  border-bottom: 1px solid rgba(245, 158, 11, 0.3); color: #FBBF24; font-size: 0.78rem;
}}
.ai-result {{
  padding: 0.85rem 1.25rem; background: #0B1320; border-bottom: 1px solid #1E293B;
  font-size: 0.8rem; color: #E2E8F0;
}}
.ai-result:empty {{ display: none; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; min-width: 720px; }}
th {{
  text-align: right; padding: 0.6rem 0.9rem; background: #0B111E;
  color: #94A3B8; font-weight: 600; border-bottom: 1px solid #1E293B;
}}
td {{ padding: 0.6rem 0.9rem; border-bottom: 1px solid rgba(30, 41, 59, 0.6); }}
.ltr-cell {{ direction: ltr; text-align: left; font-family: monospace; }}
.ltr-inline {{ direction: ltr; display: inline-block; font-family: monospace; }}
.outcome-cell {{ font-weight: 600; color: #F8FAFC; }}
.role-badge {{
  display: inline-block; padding: 0.15rem 0.5rem; font-size: 0.72rem; font-weight: 600;
  border: 1px solid transparent;
}}
.role-primary {{ background: rgba(16, 185, 129, 0.12); border-color: rgba(16, 185, 129, 0.35); color: #34D399; }}
.role-secondary {{ background: rgba(56, 189, 248, 0.12); border-color: rgba(56, 189, 248, 0.35); color: #38BDF8; }}
.role-hedge {{ background: rgba(245, 158, 11, 0.12); border-color: rgba(245, 158, 11, 0.35); color: #FBBF24; }}
.pos {{ color: #34D399; font-weight: 700; }}
.neg {{ color: #FB7185; font-weight: 700; }}
.empty-state {{ padding: 3rem; text-align: center; color: #94A3B8; border: 1px solid #1E293B; background: #0F1623; }}
.modal-backdrop {{
  display: none; position: fixed; inset: 0; z-index: 60;
  background: rgba(5, 8, 14, 0.8); backdrop-filter: blur(4px);
  align-items: center; justify-content: center; padding: 1rem;
}}
.modal-backdrop.open {{ display: flex; }}
.modal-box {{
  background: #0F1623; border: 1px solid #334155; max-width: 620px; width: 100%;
  padding: 1.5rem;
}}
</style>
</head>
<body>
<header class="topbar">
  <div class="topbar-inner">
    <div class="brand">
      <span class="brand-badge">POLYBET QUANT v2.0</span>
      <div>
        <div class="brand-title">ترمینال کوانت، سایزینگ کِلی و هجینگ بازارهای پیش‌بینی</div>
        <div class="brand-sub">به‌روزرسانی خودکار GitHub Actions: <span class="ltr-inline">{timestamp_txt}</span></div>
      </div>
    </div>
    <nav class="nav-links">
      <a class="nav-tab active" href="index.html">📡 سیگنال‌های روزانه ({total_count})</a>
      <a class="nav-tab" href="results.html">📈 بک‌تست و نتایج تسویه‌شده</a>
    </nav>
  </div>
</header>

<main class="container">
  <section class="kpi-strip">
    <div class="kpi-box">
      <div class="kpi-label">فرصت‌های فعال در پنجره تسویه</div>
      <div class="kpi-val">{total_count}</div>
      <div class="kpi-sub">فیلتر خودکار بازارهای ورزشی و اصلاح دسته‌بندی BoE</div>
    </div>
    <div class="kpi-box">
      <div class="kpi-label">سیگنال‌های احتمال بالا (≥90¢)</div>
      <div class="kpi-val">{high_conf_count}</div>
      <div class="kpi-sub">مناسب استراتژی کسب بازده کوتاه‌مدت</div>
    </div>
    <div class="kpi-box">
      <div class="kpi-label">تله‌های آپشن مانعی شناسایی‌شده (&lt;15¢)</div>
      <div class="kpi-val">{trap_count}</div>
      <div class="kpi-sub">محافظت خودکار سرمایه با سقف تخصیص ۵٪</div>
    </div>
    <div class="kpi-box">
      <div class="kpi-label">سرمایه پایه هر موقعیت (Bankroll $)</div>
      <div>
        <input id="bankrollInput" type="number" min="10" step="50" value="1000" class="bankroll-input" oninput="recalcBankroll()">
      </div>
      <div class="kpi-sub">محاسبه زنده دلاری و تعداد سهام (Shares) در تمام جداول</div>
    </div>
  </section>

  <section class="controls-panel">
    <div class="controls-row">
      <input id="searchInput" type="text" class="search-input" placeholder="جستجوی عنوان بازار، تیکر سهام (NVDA, SPY)، نرخ بهره یا کاندیدا..." oninput="applyFilters()">
      <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap">
        <label style="font-size:0.78rem;color:#94A3B8">
          مرتب‌سازی:
          <select id="sortSelect" class="select-input" onchange="applyFilters()">
            <option value="confidence">امتیاز اجماع بیزی (Confidence)</option>
            <option value="edge">لبه آماری مدل (Quant Edge)</option>
            <option value="roi">بیشترین بازده خالص Primary</option>
            <option value="days">نزدیک‌ترین زمان تسویه</option>
          </select>
        </label>
        <label style="font-size:0.78rem;color:#CBD5E1;cursor:pointer;display:flex;align-items:center;gap:0.35rem">
          <input id="hideTrapsCheck" type="checkbox" onchange="applyFilters()">
          <span>حذف تله‌های مانعی (&lt;15¢)</span>
        </label>
      </div>
    </div>
    <div class="filter-pills">
      <button type="button" class="filter-btn active" data-sec="all" onclick="setSectionFilter(this)">همه بازارها ({total_count})</button>
      <button type="button" class="filter-btn" data-sec="economy" onclick="setSectionFilter(this)">اقتصاد کلان و بانک‌های مرکزی</button>
      <button type="button" class="filter-btn" data-sec="markets" onclick="setSectionFilter(this)">سهام، کالا و رمزارز</button>
      <button type="button" class="filter-btn" data-sec="politics" onclick="setSectionFilter(this)">انتخابات و سیاست</button>
    </div>
  </section>

  <section id="cardsContainer">
    {cards_html}
  </section>
</main>

<!-- Kelly Criterion Interactive Modal -->
<div id="kellyModal" class="modal-backdrop" onclick="if(event.target===this)closeKellyModal()">
  <div class="modal-box">
    <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1E293B;padding-bottom:0.75rem;margin-bottom:1rem">
      <strong style="font-size:0.95rem">⚖️ شبیه‌ساز تعاملی فرمول کِلی (Fractional Kelly Simulator)</strong>
      <button type="button" class="btn-action" onclick="closeKellyModal()">بستن ✕</button>
    </div>
    <div id="kellyModalTitle" dir="ltr" style="font-family:monospace;font-size:0.85rem;color:#34D399;margin-bottom:1rem"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem">
      <label style="font-size:0.78rem;color:#94A3B8">
        قیمت بازار (Market Price 0.01 - 0.99):
        <input id="simPrice" type="number" step="0.01" min="0.01" max="0.99" class="search-input" style="width:100%;margin-top:0.3rem;direction:ltr" oninput="updateKellySim()">
      </label>
      <label style="font-size:0.78rem;color:#94A3B8">
        احتمال واقعی مدل شما (Model Prob 0.01 - 0.99):
        <input id="simProb" type="number" step="0.01" min="0.01" max="0.99" class="search-input" style="width:100%;margin-top:0.3rem;direction:ltr" oninput="updateKellySim()">
      </label>
    </div>
    <div id="kellySimOutput" style="padding:1rem;background:#080C14;border:1px solid #1E293B;font-size:0.82rem;line-height:1.8"></div>
  </div>
</div>

<script>
let currentSection = 'all';

function recalcBankroll() {{
  const bankroll = Math.max(1, parseFloat(document.getElementById('bankrollInput').value) || 1000);
  document.querySelectorAll('tr[data-size-pct]').forEach(tr => {{
    const pct = parseFloat(tr.getAttribute('data-size-pct')) || 0;
    const price = parseFloat(tr.getAttribute('data-price')) || 0;
    const dollars = bankroll * (pct / 100.0);
    const shares = price > 0 ? (dollars / price) : 0;
    const dCell = tr.querySelector('.js-dollar-cell');
    const sCell = tr.querySelector('.js-shares-cell');
    if (dCell) dCell.textContent = '$' + dollars.toFixed(2);
    if (sCell) sCell.textContent = shares.toFixed(1);
  }});
  document.querySelectorAll('.js-primary-dollar').forEach(el => {{
    const pct = parseFloat(el.getAttribute('data-pct')) || 0;
    el.textContent = '($' + Math.round(bankroll * (pct / 100.0)) + ')';
  }});
}}

function setSectionFilter(btn) {{
  currentSection = btn.getAttribute('data-sec') || 'all';
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyFilters();
}}

function applyFilters() {{
  const q = (document.getElementById('searchInput').value || '').trim().toLowerCase();
  const sortBy = document.getElementById('sortSelect').value;
  const hideTraps = document.getElementById('hideTrapsCheck').checked;
  const container = document.getElementById('cardsContainer');
  const cards = Array.from(container.querySelectorAll('.market-card'));

  cards.forEach(card => {{
    const sec = card.getAttribute('data-section');
    const trap = card.getAttribute('data-trap') === '1';
    const text = card.getAttribute('data-search') || '';
    const matchSec = (currentSection === 'all' || sec === currentSection);
    const matchTrap = (!hideTraps || !trap);
    const matchQ = (!q || text.includes(q));
    card.style.display = (matchSec && matchTrap && matchQ) ? '' : 'none';
  }});

  cards.sort((a, b) => {{
    if (sortBy === 'days') {{
      return (parseFloat(a.getAttribute('data-days')) || 0) - (parseFloat(b.getAttribute('data-days')) || 0);
    }}
    const attr = sortBy === 'edge' ? 'data-edge' : (sortBy === 'roi' ? 'data-roi' : 'data-confidence');
    return (parseFloat(b.getAttribute(attr)) || 0) - (parseFloat(a.getAttribute(attr)) || 0);
  }});

  cards.forEach(c => container.appendChild(c));
}}

function openKellyModal(btn) {{
  const data = JSON.parse(btn.getAttribute('data-sim') || '{{}}');
  document.getElementById('kellyModalTitle').textContent = data.title + ' — ' + data.primaryOutcome;
  const p = Number(data.primaryPrice || 0.5);
  const edge = Math.max(0.03, Number(data.edge || 0.05));
  document.getElementById('simPrice').value = p.toFixed(2);
  document.getElementById('simProb').value = Math.min(0.99, p + edge).toFixed(2);
  updateKellySim();
  document.getElementById('kellyModal').classList.add('open');
}}

function closeKellyModal() {{
  document.getElementById('kellyModal').classList.remove('open');
}}

function updateKellySim() {{
  const price = Math.min(0.99, Math.max(0.01, parseFloat(document.getElementById('simPrice').value) || 0.5));
  const prob = Math.min(0.99, Math.max(0.01, parseFloat(document.getElementById('simProb').value) || 0.55));
  const b = (1.0 - price) / price;
  const fullKelly = Math.max(0, (prob * (b + 1) - 1) / b);
  const quarterKelly = fullKelly * 0.25;
  const bankroll = Math.max(1, parseFloat(document.getElementById('bankrollInput').value) || 1000);
  document.getElementById('kellySimOutput').innerHTML =
    '<div>ضریب پرداخت خالص (Net Odds b): <strong class="ltr-inline">' + b.toFixed(2) + 'x</strong></div>' +
    '<div>سهم کِلی کامل (Full Kelly): <strong class="ltr-inline">' + (fullKelly * 100).toFixed(1) + '%</strong></div>' +
    '<div>سهم کِلی کسری پیشنهادی (0.25x Fractional Kelly): <strong class="ltr-inline pos">' + (quarterKelly * 100).toFixed(1) + '% ($' + (bankroll * quarterKelly).toFixed(0) + ')</strong></div>';
}}

const AI_WORKER_URL = "{AI_WORKER_URL}";
async function runAiAnalysis(btn) {{
  const market = JSON.parse(btn.getAttribute('data-market'));
  const resultDiv = document.getElementById('ai-result-' + market.market_id);
  resultDiv.innerHTML = 'در حال دریافت تحلیل کوانت از ورکر هوش مصنوعی...';
  btn.disabled = true;
  try {{
    const resp = await fetch(AI_WORKER_URL, {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(market)
    }});
    const data = await resp.json();
    if (data.error) {{ resultDiv.innerHTML = '⚠️ ' + data.error; return; }}
    resultDiv.innerHTML =
      '<div><strong>جمع‌بندی تحلیل هوش مصنوعی:</strong> ' + (data.summary || '—') + '</div>' +
      '<div style="margin-top:0.35rem;color:#34D399"><strong>سطح اطمینان:</strong> ' + (data.confidence || '—') + '</div>';
  }} catch (e) {{
    resultDiv.innerHTML = '⚠️ خطا در ارتباط با سرویس تحلیل: ' + e.message;
  }} finally {{
    btn.disabled = false;
  }}
}}
</script>
</body>
</html>"""


def write_html(path: str, results, generated_at: datetime | None = None) -> None:
    content = build_html(results, generated_at=generated_at)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
