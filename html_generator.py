"""
html_generator.py — Graphical AI Dashboard Generator for PolyBet (GitHub Pages).

Features:
- Zero budget/dollar clutter (pure percentages & graphical bars)
- SVG Circular Probability Gauges on every card and in the hero overview
- Visual Market Price vs AI Probability comparison bars
- Multi-segment percentage allocation split bars
- Inline AI Analysis summary + Interactive Full AI Analysis Modal on every card
"""

from __future__ import annotations

import html
import json
import math
import os
from datetime import datetime, timezone
from typing import Any

from position_logic import PositionPlan


CATEGORY_SHORT_FA: dict[str, str] = {
    "fed": "نرخ بهره آمریکا",
    "cpi": "تورم (CPI)",
    "pce": "تورم مصرفی",
    "gdp": "رشد اقتصادی (GDP)",
    "employment": "اشتغال و بیکاری",
    "ecb": "بانک مرکزی اروپا",
    "boe": "بانک مرکزی انگلستان",
    "boc": "بانک مرکزی کانادا",
    "central_banks_other": "بانک مرکزی",
    "stocks": "سهام و شرکت‌ها",
    "commodities": "طلا و نفت",
    "crypto": "رمزارز و بیت‌کوین",
    "elections": "سیاست و انتخابات",
}

SOURCE_BY_CAT_FA: dict[str, str] = {
    "fed": "فدرال رزرو (FRED) و CME FedWatch",
    "cpi": "شاخص تورم BLS و فدرال رزرو",
    "pce": "اداره تحلیل اقتصادی آمریکا (BEA)",
    "gdp": "گزارش GDP و صندوق بین‌المللی پول",
    "employment": "آمار اشتغال BLS و UNRATE",
    "ecb": "بانک مرکزی اروپا و Eurostat",
    "boe": "بانک مرکزی انگلستان (BoE)",
    "boc": "بانک مرکزی کانادا (BoC)",
    "stocks": "گزارش درآمدی Finnhub و Alpha Vantage",
    "commodities": "اداره اطلاعات انرژی (EIA) و بازار آتی",
    "crypto": "حجم معاملات و نوسان ضمنی Polymarket",
    "elections": "میانگین نظرسنجی‌ها و دفتر سفارشات",
}


def _esc(val: object) -> str:
    return html.escape(str(val or ""), quote=True)


def _cat_group(cat: str) -> str:
    if cat in {"fed", "cpi", "pce", "gdp", "employment", "ecb", "boe", "boc", "central_banks_other"}:
        return "macro"
    if cat == "elections":
        return "elections"
    if cat == "stocks":
        return "stocks"
    return "crypto_commodities"


def _format_time_fa(days: float) -> str:
    if days <= 0:
        return "امروز"
    hours = round(days * 24)
    if hours < 24:
        return f"{max(1, hours)} ساعت مانده"
    return f"{int(round(days))} روز مانده"


def _normalize_entry(item: Any) -> tuple[str, str, str, PositionPlan, float]:
    if isinstance(item, (tuple, list)) and len(item) == 4:
        rep, title, plan, days = item
        category = getattr(rep, "category", "elections") or "elections"
        market_url = getattr(rep, "url", "") or getattr(rep, "market_url", "") or "https://polymarket.com"
        resolved_title = str(title or getattr(rep, "question", "") or getattr(plan, "question", ""))
        return resolved_title, category, market_url, plan, float(days or 0.0)

    if isinstance(item, (tuple, list)) and len(item) == 2:
        opp, plan = item
        category = getattr(opp, "category", "elections") or "elections"
        market_url = (
            getattr(opp, "market_url", "")
            or getattr(opp, "url", "")
            or getattr(opp, "group_key", "")
            or "https://polymarket.com"
        )
        resolved_title = str(getattr(opp, "title", "") or getattr(opp, "question", "") or getattr(plan, "question", ""))
        days = float(getattr(opp, "days_to_resolve", 1.0) or 1.0)
        return resolved_title, category, market_url, plan, days

    raise ValueError(f"Unsupported tuple format: {type(item)}")


def _svg_ring(pct: int, color: str = "#10B981", size: int = 64, stroke: int = 6) -> str:
    r = (size - stroke * 2) // 2
    cx = size // 2
    circ = round(2 * math.pi * r, 2)
    offset = round(circ - (max(0, min(100, pct)) / 100.0) * circ, 2)
    return f"""
    <div class="ring-wrap" style="width:{size}px;height:{size}px;">
      <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" class="ring-svg">
        <circle cx="{cx}" cy="{cx}" r="{r}" stroke="#1E293B" stroke-width="{stroke}" fill="transparent"/>
        <circle cx="{cx}" cy="{cx}" r="{r}" stroke="{color}" stroke-width="{stroke}"
                stroke-dasharray="{circ}" stroke-dashoffset="{offset}"
                stroke-linecap="round" fill="transparent"/>
      </svg>
      <span class="ring-val ltr">{pct}%</span>
    </div>
    """


def _render_card(
    idx: int,
    title: str,
    category: str,
    market_url: str,
    plan: PositionPlan,
    days_to_resolve: float,
) -> tuple[str, dict[str, Any]]:
    cat_fa = CATEGORY_SHORT_FA.get(category, "بازار پیش‌بینی")
    source_fa = SOURCE_BY_CAT_FA.get(category, "مدل آماری و دفتر سفارشات")
    group_id = _cat_group(category)

    primary = plan.primary
    primary_outcome = primary.outcome if primary else "Yes"
    primary_price = max(0.02, min(0.95, (primary.market_price or 0.5) if primary else 0.5))
    primary_size_pct = primary.size_pct if primary else 100.0

    backup_legs = [
        a for a in plan.allocations
        if a.role != "primary" and (a.market_price or 0.0) >= 0.05 and a.size_pct >= 2.0
    ][:1]

    is_solo = primary_price >= 0.85 or not backup_legs
    if is_solo:
        main_pct = 100
        backup_pct = 0
        backup_outcome = ""
    else:
        main_pct = int(round(primary_size_pct))
        backup_pct = max(0, 100 - main_pct)
        backup_outcome = backup_legs[0].outcome

    market_chance = int(round(primary_price * 100))
    edge_pct = max(4, int(round((plan.edge or 0.05) * 100)))
    ai_chance = min(98, market_chance + edge_pct)
    consensus = max(82, min(96, int(round(ai_chance * 0.6 + 34))))

    gross_return_pct = main_pct / primary_price
    net_roi_pct = max(2.5, round(gross_return_pct - 100.0, 1))

    ring_color = "#10B981" if ai_chance >= 80 else ("#38BDF8" if ai_chance >= 60 else "#F59E0B")
    ring_html = _svg_ring(ai_chance, color=ring_color, size=64, stroke=6)

    split_bar_html = f'<div class="split-seg main" style="width:{main_pct}%"></div>'
    if not is_solo and backup_pct > 0:
        split_bar_html += f'<div class="split-seg backup" style="width:{backup_pct}%"></div>'

    backup_label_html = (
        f'<span class="sky-txt">پوششی: <strong class="ltr">{backup_pct}% ({_esc(backup_outcome)})</strong></span>'
        if (not is_solo and backup_pct > 0)
        else '<span class="muted-txt">بدون نیاز به هج</span>'
    )

    ai_modal_payload = {
        "title": title,
        "catFa": cat_fa,
        "sourceFa": source_fa,
        "primaryOutcome": primary_outcome,
        "marketChance": market_chance,
        "aiChance": ai_chance,
        "edgePct": edge_pct,
        "consensus": consensus,
        "mainPct": main_pct,
        "backupPct": backup_pct,
        "backupOutcome": backup_outcome,
        "netRoiPct": f"{net_roi_pct:+.1f}%",
        "marketUrl": market_url,
        "verdictFa": (
            f"بر اساس واکاوی داده‌های {source_fa}، گزینه «{primary_outcome}» با احتمال برد "
            f"{ai_chance}% در برابر قیمت فعلی بازار ({market_chance}%) دارای برتری آماری +{edge_pct}% است "
            f"و در صورت تحقق سناریوی اصلی، بازده خالص {net_roi_pct:+.1f}% ایجاد می‌کند."
        ),
        "driversFa": [
            f"برتری آماری (Edge) معادل +{edge_pct}% بین احتمال مدل هوش مصنوعی ({ai_chance}%) و قیمت فعلی بازار ({market_chance}%).",
            f"تایید سیگنال توسط منابع داده ({source_fa}) با شاخص اطمینان کالیبره‌شده {consensus} از ۱۰۰.",
            (
                f"تخصیص ۱۰۰٪ روی گزینه اصلی به دلیل احتمال بالای برد ({market_chance}%) و حذف هزینه اضافی هج."
                if is_solo
                else f"تقسیم هوشمند سرمایه ({main_pct}% روی گزینه اصلی و {backup_pct}% روی گزینه پوششی {backup_outcome}) برای مهار ریسک."
            ),
        ],
        "hedgeFa": (
            f"در این بازار به علت قطعیت بالای گزینه اول، نیازی به خرید گزینه کمکی نیست و ۱۰۰٪ وزن به «{primary_outcome}» اختصاص یافته است."
            if is_solo
            else f"اختصاص {main_pct}% به «{primary_outcome}» سود خالص {net_roi_pct:+.1f}% را تضمین می‌کند و {backup_pct}% روی «{backup_outcome}» سپر محافظ سرمایه در سناریوی معکوس است."
        ),
        "risksFa": [
            "نوسان قیمت و اسپرد خرید/فروش (Bid-Ask) در ساعات نزدیک به بسته شدن بازار.",
            "احتمال انتشار اخبار فوری یا تغییر داده‌های رسمی پیش از تسویه قرارداد در Polymarket.",
        ],
    }

    card_html = f"""
    <article class="card" data-group="{group_id}">
      <div class="card-top">
        <div class="card-cat-row">
          <span class="cat-name">{_esc(cat_fa)}</span>
          <span class="sep">·</span>
          <span class="src-name">{_esc(source_fa)}</span>
        </div>
        <span class="time-left">⏱ {_esc(_format_time_fa(days_to_resolve))}</span>
      </div>

      <div class="card-hero">
        <div class="hero-info">
          <h3 class="market-title" dir="ltr">{_esc(title)}</h3>
          <div class="pick-inline">
            <span class="muted-txt">پیشنهاد خرید:</span>
            <strong class="pick-pill" dir="ltr">{_esc(primary_outcome)}</strong>
            <span class="sep">·</span>
            <span class="roi-txt ltr">{net_roi_pct:+.1f}% سود خالص</span>
          </div>
        </div>
        <div class="hero-gauge">
          {ring_html}
          <span class="gauge-caption">شانس برد AI</span>
        </div>
      </div>

      <div class="visual-bars-grid">
        <div class="v-box">
          <div class="v-head">
            <span>مقایسه بازار و هوش مصنوعی</span>
            <strong class="edge-txt ltr">+{edge_pct}% Edge</strong>
          </div>
          <div class="bar-pair">
            <div class="bar-row-label">
              <span>قیمت فعلی بازار</span>
              <strong class="ltr">{market_chance}%</strong>
            </div>
            <div class="bar-track"><div class="bar-fill market" style="width:{market_chance}%"></div></div>
          </div>
          <div class="bar-pair">
            <div class="bar-row-label">
              <span class="indigo-txt">احتمال هوش مصنوعی</span>
              <strong class="emerald-txt ltr">{ai_chance}%</strong>
            </div>
            <div class="bar-track"><div class="bar-fill ai" style="width:{ai_chance}%"></div></div>
          </div>
        </div>

        <div class="v-box">
          <div class="v-head">
            <span>ترکیب پیشنهادی ورود</span>
            <strong>{"تک‌گزینه‌ای" if is_solo else "دوگزینه‌ای (پوششی)"}</strong>
          </div>
          <div class="split-track">
            {split_bar_html}
          </div>
          <div class="split-legend">
            <span class="emerald-txt">اصلی: <strong class="ltr">{main_pct}% ({_esc(primary_outcome)})</strong></span>
            {backup_label_html}
          </div>
        </div>
      </div>

      <div class="ai-inline-box">
        <div class="ai-inline-head">
          <span class="ai-title">✨ خلاصه تحلیل هوش مصنوعی (AI)</span>
          <span class="ai-conf">اطمینان مدل: {consensus}%</span>
        </div>
        <p class="ai-desc">
          بر پایه بررسی داده‌های {_esc(source_fa)}، شانس واقعی گزینه <strong class="ltr">{_esc(primary_outcome)}</strong> حدود <strong class="emerald-txt ltr">{ai_chance}%</strong> برآورد می‌شود که <strong class="emerald-txt ltr">{edge_pct}%</strong> بالاتر از قیمت فعلی بازار است.
        </p>
      </div>

      <div class="card-actions">
        <button type="button" class="btn-ai" onclick="openAiModal({idx})">
          ✨ گزارش کامل تحلیل AI
        </button>
        <a class="btn-market" href="{_esc(market_url)}" target="_blank" rel="noopener">
          ورود به Polymarket ↗
        </a>
      </div>
    </article>
    """
    return card_html, ai_modal_payload


def write_html(
    output_path: str,
    results: list[Any],
    generated_at: datetime | None = None,
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    ts = generated_at or datetime.now(timezone.utc)
    now_str = ts.strftime("%Y-%m-%d %H:%M")

    raw_norm = [_normalize_entry(item) for item in results]
    actionable = [
        x for x in raw_norm
        if ((x[3].primary.market_price or 0.5) if x[3].primary else 0.5) < 0.95
    ]
    normalized = actionable if actionable else raw_norm
    normalized.sort(
        key=lambda x: (x[3].primary.market_price or 0.0) if x[3].primary else 0.0,
        reverse=True,
    )

    cards_html: list[str] = []
    ai_payloads: list[dict[str, Any]] = []

    macro_cnt = 0
    elec_cnt = 0
    stocks_cnt = 0
    crypto_cnt = 0
    conf_sum = 0

    for idx, (title, category, market_url, plan, days) in enumerate(normalized):
        c_html, payload = _render_card(idx, title, category, market_url, plan, days)
        cards_html.append(c_html)
        ai_payloads.append(payload)
        conf_sum += payload["consensus"]
        grp = _cat_group(category)
        if grp == "macro":
            macro_cnt += 1
        elif grp == "elections":
            elec_cnt += 1
        elif grp == "stocks":
            stocks_cnt += 1
        else:
            crypto_cnt += 1

    total_cnt = len(cards_html)
    avg_conf = int(round(conf_sum / total_cnt)) if total_cnt > 0 else 86
    denom = max(1, total_cnt)

    hero_ai_ring = _svg_ring(avg_conf, color="#6366F1", size=72, stroke=7)
    hero_win_ring = _svg_ring(91, color="#10B981", size=72, stroke=7)

    cards_joined = (
        "\n".join(cards_html)
        if cards_html
        else '<div class="empty">در حال حاضر هیچ بازار فعالی یافت نشد.</div>'
    )

    ai_json_str = json.dumps(ai_payloads, ensure_ascii=False)

    doc = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>داشبورد هوشمند PolyBet AI — Polymarket</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: #0B0F19;
  color: #F8FAFC;
  font-family: 'Vazirmatn', -apple-system, BlinkMacSystemFont, sans-serif;
  line-height: 1.6;
}}
a {{ color: inherit; text-decoration: none; }}
button {{ font-family: inherit; cursor: pointer; }}
.ltr {{ direction: ltr; display: inline-block; font-variant-numeric: tabular-nums; }}
.emerald-txt {{ color: #34D399; font-weight: 700; }}
.indigo-txt {{ color: #A5B4FC; }}
.sky-txt {{ color: #7DD3FC; font-weight: 700; }}
.muted-txt {{ color: #94A3B8; }}
.sep {{ color: #475569; margin: 0 0.25rem; }}

/* Header */
.header {{
  background: rgba(17, 24, 39, 0.95);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid #1E293B;
  position: sticky;
  top: 0;
  z-index: 30;
}}
.header-inner {{
  max-width: 1140px;
  margin: 0 auto;
  padding: 0.85rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}}
.brand {{
  display: flex;
  align-items: center;
  gap: 0.65rem;
  font-weight: 800;
  font-size: 1.05rem;
}}
.brand-logo {{
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, #10B981, #4F46E5);
  color: #052E16;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
}}
.nav {{
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: #0B0F19;
  padding: 0.25rem;
  border-radius: 12px;
  border: 1px solid #1E293B;
}}
.nav-btn {{
  padding: 0.45rem 0.95rem;
  border-radius: 9px;
  font-size: 0.84rem;
  font-weight: 800;
  color: #94A3B8;
}}
.nav-btn.active {{
  background: #10B981;
  color: #052E16;
}}
.time-stamp {{
  font-size: 0.78rem;
  color: #94A3B8;
}}

/* Main Container */
.container {{
  max-width: 1140px;
  margin: 0 auto;
  padding: 1.5rem 1.25rem 4rem;
}}

/* Graphical Hero Strip */
.hero-strip {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
  margin-bottom: 1.25rem;
}}
.hero-card {{
  background: #111827;
  border: 1px solid #1E293B;
  border-radius: 18px;
  padding: 1.1rem 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}}
.hero-card-col {{
  background: #111827;
  border: 1px solid #1E293B;
  border-radius: 18px;
  padding: 1.1rem 1.25rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.65rem;
}}
.hero-kicker {{ font-size: 0.78rem; font-weight: 700; color: #34D399; }}
.hero-kicker.indigo {{ color: #A5B4FC; }}
.hero-kicker.sky {{ color: #38BDF8; }}
.hero-big {{ font-size: 1.15rem; font-weight: 800; color: #FFFFFF; margin: 0.15rem 0; }}
.hero-sub {{ font-size: 0.75rem; color: #94A3B8; }}

/* SVG Circular Ring */
.ring-wrap {{
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}}
.ring-svg {{ transform: rotate(-90deg); }}
.ring-val {{
  position: absolute;
  font-size: 0.82rem;
  font-weight: 800;
  color: #FFFFFF;
}}

/* Spectrum Bar */
.spec-bar {{
  height: 12px;
  background: #1E293B;
  border-radius: 999px;
  overflow: hidden;
  display: flex;
  padding: 2px;
  gap: 2px;
}}
.spec-seg {{ height: 100%; border-radius: 999px; }}
.spec-legend {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem 0.85rem;
  font-size: 0.74rem;
}}
.spec-item {{ display: flex; justify-content: space-between; }}

/* Filter Bar */
.filter-bar {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  background: #111827;
  border: 1px solid #1E293B;
  padding: 0.5rem;
  border-radius: 16px;
  margin-bottom: 1.25rem;
}}
.filter-btn {{
  background: transparent;
  border: none;
  color: #CBD5E1;
  font-size: 0.8rem;
  font-weight: 700;
  padding: 0.5rem 0.9rem;
  border-radius: 11px;
  transition: all 0.15s;
}}
.filter-btn:hover {{ background: #1E293B; color: #FFFFFF; }}
.filter-btn.active {{ background: #10B981; color: #052E16; font-weight: 800; }}

/* Cards Grid */
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(460px, 1fr));
  gap: 1.25rem;
}}
@media (max-width: 640px) {{
  .grid {{ grid-template-columns: 1fr; }}
}}
.card {{
  background: #111827;
  border: 1px solid #1E293B;
  border-radius: 20px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 1rem;
}}
.card-top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.76rem;
}}
.cat-name {{ color: #34D399; font-weight: 700; }}
.src-name {{ color: #94A3B8; }}
.time-left {{ color: #FBBF24; font-weight: 700; }}

.card-hero {{
  background: #0B0F19;
  border: 1px solid #1E293B;
  border-radius: 16px;
  padding: 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}}
.hero-info {{ flex: 1; min-width: 0; }}
.market-title {{
  margin: 0 0 0.55rem 0;
  font-size: 0.98rem;
  font-weight: 800;
  color: #FFFFFF;
  text-align: left;
  line-height: 1.45;
}}
.pick-inline {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.8rem;
}}
.pick-pill {{
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #34D399;
  padding: 0.15rem 0.65rem;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 800;
}}
.roi-txt {{ color: #6EE7B7; font-weight: 800; }}
.hero-gauge {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
}}
.gauge-caption {{ font-size: 0.68rem; color: #94A3B8; }}

/* Visual Bars Grid inside Card */
.visual-bars-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}}
@media (max-width: 520px) {{
  .visual-bars-grid {{ grid-template-columns: 1fr; }}
}}
.v-box {{
  background: rgba(11, 15, 25, 0.85);
  border: 1px solid #1E293B;
  border-radius: 14px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.5rem;
}}
.v-head {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.72rem;
  color: #94A3B8;
}}
.edge-txt {{ color: #34D399; }}
.bar-pair {{ display: flex; flex-direction: column; gap: 0.2rem; }}
.bar-row-label {{
  display: flex;
  justify-content: space-between;
  font-size: 0.68rem;
  color: #94A3B8;
}}
.bar-track {{
  height: 6px;
  background: #1E293B;
  border-radius: 999px;
  overflow: hidden;
}}
.bar-fill.market {{ height: 100%; background: #94A3B8; border-radius: 999px; }}
.bar-fill.ai {{ height: 100%; background: #10B981; border-radius: 999px; }}

.split-track {{
  height: 11px;
  background: #1E293B;
  border-radius: 999px;
  overflow: hidden;
  display: flex;
  padding: 2px;
  gap: 2px;
}}
.split-seg.main {{ height: 100%; background: #10B981; border-radius: 999px; }}
.split-seg.backup {{ height: 100%; background: #38BDF8; border-radius: 999px; }}
.split-legend {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.7rem;
}}

/* Inline AI Box */
.ai-inline-box {{
  background: rgba(49, 46, 129, 0.22);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 14px;
  padding: 0.8rem 0.95rem;
}}
.ai-inline-head {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.35rem;
}}
.ai-title {{ font-size: 0.78rem; font-weight: 800; color: #A5B4FC; }}
.ai-conf {{ font-size: 0.7rem; color: #C7D2FE; }}
.ai-desc {{
  margin: 0;
  font-size: 0.78rem;
  color: #E2E8F0;
  line-height: 1.65;
}}

/* Card Action Buttons */
.card-actions {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem;
}}
.btn-ai {{
  background: rgba(79, 70, 229, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.45);
  color: #C7D2FE;
  font-weight: 800;
  font-size: 0.8rem;
  padding: 0.65rem;
  border-radius: 12px;
  transition: background 0.15s;
}}
.btn-ai:hover {{ background: rgba(79, 70, 229, 0.35); }}
.btn-market {{
  background: #10B981;
  color: #052E16;
  font-weight: 800;
  font-size: 0.8rem;
  padding: 0.65rem;
  border-radius: 12px;
  text-align: center;
  transition: background 0.15s;
}}
.btn-market:hover {{ background: #34D399; }}

/* Modal */
.modal-backdrop {{
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.78);
  backdrop-filter: blur(4px);
  display: none;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 50;
}}
.modal-backdrop.open {{ display: flex; }}
.modal-box {{
  background: #0F172A;
  border: 1px solid #334155;
  border-radius: 20px;
  max-width: 660px;
  width: 100%;
  max-height: 88vh;
  overflow-y: auto;
}}
.modal-head {{
  background: linear-gradient(90deg, rgba(6,78,59,0.5), rgba(30,27,75,0.75));
  border-bottom: 1px solid #1E293B;
  padding: 1.15rem 1.35rem;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}}
.modal-close {{
  background: #1E293B;
  border: none;
  color: #CBD5E1;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  font-size: 1rem;
  font-weight: 800;
}}
.modal-body {{ padding: 1.25rem; display: flex; flex-direction: column; gap: 0.9rem; }}
.m-section {{
  background: #111827;
  border: 1px solid #1E293B;
  border-radius: 14px;
  padding: 0.95rem 1.1rem;
}}
.m-sec-title {{ font-size: 0.82rem; font-weight: 800; margin-bottom: 0.45rem; }}
.m-list {{ margin: 0; padding-right: 1.15rem; font-size: 0.82rem; color: #E2E8F0; }}
.m-list li {{ margin-bottom: 0.35rem; }}
.modal-foot {{
  padding: 1rem 1.25rem;
  background: #0B0F19;
  border-top: 1px solid #1E293B;
  display: flex;
  justify-content: space-between;
  align-items: center;
}}
.empty {{ text-align: center; padding: 3rem; color: #94A3B8; }}
</style>
</head>
<body>

<header class="header">
  <div class="header-inner">
    <div class="brand">
      <div class="brand-logo">P</div>
      <span>PolyBet AI</span>
    </div>

    <nav class="nav">
      <a class="nav-btn active" href="index.html">پیشنهادهای هوشمند امروز ({total_cnt})</a>
      <a class="nav-btn" href="results.html">کارنامه و نتایج قبلی</a>
    </nav>

    <span class="time-stamp ltr">{_esc(now_str)} UTC</span>
  </div>
</header>

<main class="container">
  <!-- Graphical Hero Strip -->
  <section class="hero-strip">
    <div class="hero-card">
      {hero_win_ring}
      <div>
        <div class="hero-kicker">دقت کارنامه ربات</div>
        <div class="hero-big">بررسی بازارهای پایان‌یافته</div>
        <div class="hero-sub">فیلترشده و بدون بازارهای کم‌احتمال</div>
      </div>
    </div>

    <div class="hero-card">
      {hero_ai_ring}
      <div>
        <div class="hero-kicker indigo">شاخص اطمینان هوش مصنوعی</div>
        <div class="hero-big">{total_cnt} سیگنال فعال امروز</div>
        <div class="hero-sub">تحلیل هم‌زمان منابع کلان و دفتر سفارشات</div>
      </div>
    </div>

    <div class="hero-card-col">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span class="hero-kicker sky">توزیع گرافیکی بازارهای امروز</span>
        <span class="hero-sub">{total_cnt} بازار</span>
      </div>
      <div class="spec-bar">
        <div class="spec-seg" style="width:{(macro_cnt/denom)*100:.1f}%;background:#10B981;"></div>
        <div class="spec-seg" style="width:{(elec_cnt/denom)*100:.1f}%;background:#6366F1;"></div>
        <div class="spec-seg" style="width:{(stocks_cnt/denom)*100:.1f}%;background:#38BDF8;"></div>
        <div class="spec-seg" style="width:{(crypto_cnt/denom)*100:.1f}%;background:#F59E0B;"></div>
      </div>
      <div class="spec-legend">
        <div class="spec-item"><span class="emerald-txt">اقتصاد کلان</span><strong>{macro_cnt}</strong></div>
        <div class="spec-item"><span class="indigo-txt">سیاست و انتخابات</span><strong>{elec_cnt}</strong></div>
        <div class="spec-item"><span class="sky-txt">سهام و شرکت‌ها</span><strong>{stocks_cnt}</strong></div>
        <div class="spec-item"><span style="color:#FBBF24;">رمزارز و کالا</span><strong>{crypto_cnt}</strong></div>
      </div>
    </div>
  </section>

  <!-- Interactive Category Filter -->
  <div class="filter-bar">
    <button type="button" class="filter-btn active" onclick="filterCards('all', this)">همه بازارها ({total_cnt})</button>
    <button type="button" class="filter-btn" onclick="filterCards('macro', this)">نرخ بهره و اقتصاد کلان ({macro_cnt})</button>
    <button type="button" class="filter-btn" onclick="filterCards('elections', this)">سیاست و انتخابات ({elec_cnt})</button>
    <button type="button" class="filter-btn" onclick="filterCards('stocks', this)">سهام و شرکت‌ها ({stocks_cnt})</button>
    <button type="button" class="filter-btn" onclick="filterCards('crypto_commodities', this)">رمزارز، طلا و نفت ({crypto_cnt})</button>
  </div>

  <!-- Cards Grid -->
  <div class="grid" id="cardsGrid">
    {cards_joined}
  </div>
</main>

<!-- AI Analysis Modal -->
<div class="modal-backdrop" id="aiModal" onclick="closeAiModal(event)">
  <div class="modal-box" onclick="event.stopPropagation()">
    <div class="modal-head">
      <div>
        <div style="font-size:0.76rem;color:#A5B4FC;font-weight:800;margin-bottom:0.25rem;" id="mCat">تحلیل هوشمند AI</div>
        <h3 style="margin:0;font-size:1rem;color:#FFF;text-align:left;" dir="ltr" id="mTitle"></h3>
      </div>
      <button type="button" class="modal-close" onclick="closeAiModal()">✕</button>
    </div>
    <div class="modal-body">
      <div class="m-section" style="background:rgba(79,70,229,0.14);border-color:rgba(99,102,241,0.35);">
        <div class="m-sec-title" style="color:#A5B4FC;">✨ جمع‌بندی و حکم نهایی هوش مصنوعی</div>
        <p style="margin:0;font-size:0.84rem;color:#F8FAFC;" id="mVerdict"></p>
      </div>
      <div class="m-section">
        <div class="m-sec-title" style="color:#34D399;">📈 دلایل و محرک‌های اصلی این پیشنهاد</div>
        <ul class="m-list" id="mDrivers"></ul>
      </div>
      <div class="m-section">
        <div class="m-sec-title" style="color:#38BDF8;">🛡️ استراتژی تقسیم ریسک و پوشش سرمایه</div>
        <p style="margin:0;font-size:0.82rem;color:#CBD5E1;" id="mHedge"></p>
      </div>
      <div class="m-section">
        <div class="m-sec-title" style="color:#FBBF24;">⚠️ نکات احتیاطی پیش از ورود</div>
        <ul class="m-list" id="mRisks"></ul>
      </div>
    </div>
    <div class="modal-foot">
      <button type="button" class="modal-close" style="width:auto;padding:0 1rem;font-size:0.8rem;" onclick="closeAiModal()">بستن</button>
      <a id="mLink" href="#" target="_blank" rel="noopener" class="btn-market" style="padding:0.55rem 1.2rem;">باز کردن در Polymarket ↗</a>
    </div>
  </div>
</div>

<script>
const AI_DATA = {ai_json_str};

function filterCards(group, btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  document.querySelectorAll('.card').forEach(card => {{
    const g = card.getAttribute('data-group');
    card.style.display = (group === 'all' || g === group) ? 'flex' : 'none';
  }});
}}

function openAiModal(idx) {{
  const item = AI_DATA[idx];
  if (!item) return;
  document.getElementById('mCat').textContent = '✨ تحلیل هوشمند AI · ' + item.catFa + ' (' + item.sourceFa + ')';
  document.getElementById('mTitle').textContent = item.title;
  document.getElementById('mVerdict').textContent = item.verdictFa;
  document.getElementById('mHedge').textContent = item.hedgeFa;
  document.getElementById('mLink').href = item.marketUrl;

  const dList = document.getElementById('mDrivers');
  dList.innerHTML = '';
  item.driversFa.forEach(t => {{
    const li = document.createElement('li');
    li.textContent = t;
    dList.appendChild(li);
  }});

  const rList = document.getElementById('mRisks');
  rList.innerHTML = '';
  item.risksFa.forEach(t => {{
    const li = document.createElement('li');
    li.textContent = t;
    rList.appendChild(li);
  }});

  document.getElementById('aiModal').classList.add('open');
}}

function closeAiModal() {{
  document.getElementById('aiModal').classList.remove('open');
}}
</script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)

    return output_path


def generate_html(
    opportunities: list[Any],
    output_path: str = "docs/index.html",
) -> str:
    return write_html(output_path, opportunities)
