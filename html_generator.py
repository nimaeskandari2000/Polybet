"""
html_generator.py — PolyBet v2.0 User-Friendly Visual Dashboard Generator.

Generates a crystal-clear, graphical Persian RTL dashboard (docs/index.html)
designed for instant comprehension without confusing quant jargon or cluttered tables.
"""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from position_logic import PositionPlan

if TYPE_CHECKING:
    from scanner import MarketOpportunity


CATEGORY_META: dict[str, tuple[str, str, str]] = {
    "fed": ("🏦 نرخ بهره آمریکا (Fed)", "economy", "#38BDF8"),
    "cpi": ("📊 تورم و شاخص قیمت (CPI)", "economy", "#10B981"),
    "pce": ("🛒 هزینه‌های مصرفی (PCE)", "economy", "#10B981"),
    "gdp": ("🌐 رشد اقتصادی کشورها (GDP)", "economy", "#60A5FA"),
    "employment": ("👷 اشتغال و بیکاری", "economy", "#34D399"),
    "ecb": ("🇪🇺 بانک مرکزی اروپا", "economy", "#818CF8"),
    "boe": ("🇬🇧 بانک مرکزی انگلستان", "economy", "#A78BFA"),
    "boc": ("🇨🇦 بانک مرکزی کانادا", "economy", "#F472B6"),
    "central_banks_other": ("🏛️ بانک‌های مرکزی جهان", "economy", "#94A3B8"),
    "stocks": ("📈 گزارش سود شرکت‌ها و سهام", "markets", "#F59E0B"),
    "commodities": ("🛢️ طلا، نفت و کالاها", "markets", "#FBBF24"),
    "crypto": ("🪙 بیت‌کوین و رمزارزها", "markets", "#F97316"),
    "elections": ("🗳️ سیاست و انتخابات", "politics", "#C084FC"),
}


def _esc(val: object) -> str:
    return html.escape(str(val or ""), quote=True)


def _format_time_left_fa(days: float) -> str:
    if days <= 0:
        return "در حال بسته شدن"
    hours = round(days * 24)
    if hours < 24:
        return f"{max(1, hours)} ساعت مانده"
    whole_days = int(days)
    rem_hours = int(round((days - whole_days) * 24))
    if rem_hours > 0 and whole_days < 3:
        return f"{whole_days} روز و {rem_hours} ساعت مانده"
    return f"{days:.1f} روز مانده"


def _compute_confidence(plan: PositionPlan, primary_price: float) -> float:
    if plan.num_sources > 0 and plan.consensus_score > 0:
        k = 1.5
        weight = plan.num_sources / (plan.num_sources + k)
        return round(min(99.0, max(15.0, plan.consensus_score * weight)), 1)
    return round(min(98.0, max(35.0, primary_price * 100.0)), 1)


def _render_card(opp: MarketOpportunity, plan: PositionPlan, default_bankroll: float = 1000.0) -> str:
    cat_label, section_key, cat_color = CATEGORY_META.get(
        opp.category, ("📌 بازار پیش‌بینی", "politics", "#38BDF8")
    )
    primary = plan.primary
    primary_outcome = primary.outcome if primary else "—"
    primary_price = (primary.market_price or 0.5) if primary else 0.5
    primary_size_pct = primary.size_pct if primary else 0.0
    primary_dollar = round(default_bankroll * (primary_size_pct / 100.0))

    total_committed_pct = sum(a.size_pct for a in plan.allocations) or 100.0
    primary_gross_pct = (primary_size_pct / primary_price) if primary_price > 0 else 0.0
    primary_net_roi_pct = round(primary_gross_pct - total_committed_pct, 1)
    primary_net_profit_dollar = round(default_bankroll * (primary_net_roi_pct / 100.0))

    win_prob_pct = round(primary_price * 100.0, 1)
    confidence = _compute_confidence(plan, primary_price)
    time_left_fa = _format_time_left_fa(opp.days_to_resolve)

    hit_q = bool(re.search(r"\bwhat (?:price )?will .* hit\b", (opp.title or "").lower()))
    arrow_o = bool(re.match(r"^[↑↓]\s*\$?[\d,.]+", primary_outcome.strip()))
    is_trap = (hit_q or arrow_o) and primary_price < 0.15

    # Filter backup legs (exclude micro-tail options < 4 cents so the user is never confused)
    backup_legs = [
        a for a in plan.allocations
        if a.role != "primary" and (a.market_price or 0.0) >= 0.04 and a.size_pct >= 1.5
    ][:2]

    if not backup_legs:
        # Clean solo primary view
        backup_html = f"""
        <div class="plan-box plan-solo">
          <div class="plan-box-header">
            <span class="step-pill pill-solo">🛡️ وضعیت بیمه و پوشش ریسک</span>
          </div>
          <div class="solo-text">
            <strong>نیاز به خرید گزینه کمکی ندارد.</strong>
            شانس برد گزینه اصلی بسیار بالاست (<span class="ltr-num">{win_prob_pct:.1f}%</span>)؛ بنابراین کل بودجه این معامله فقط روی همان گزینه اصلی قرار می‌گیرد.
          </div>
        </div>
        """
    else:
        backup_items_html = []
        for idx, b in enumerate(backup_legs, 1):
            b_price = b.market_price or 0.1
            b_price_cents = round(b_price * 100, 1)
            b_dollar = round(default_bankroll * (b.size_pct / 100.0))
            b_payout_dollar = round((default_bankroll * (b.size_pct / 100.0)) / b_price) if b_price > 0 else 0
            backup_items_html.append(
                f"""
                <div class="backup-item" data-size-pct="{b.size_pct:.4f}" data-price="{b_price:.6f}">
                  <div class="backup-top">
                    <span class="backup-label">گزینه جایگزین {idx}: <strong class="ltr-num">{_esc(b.outcome)}</strong></span>
                    <span class="backup-price">قیمت: <strong class="ltr-num">{b_price_cents:.1f}¢</strong></span>
                  </div>
                  <div class="backup-bottom">
                    <span>مبلغ خرید: <strong class="ltr-num backup-dollar js-backup-dollar">${b_dollar}</strong> (<span class="ltr-num">{b.size_pct:.0f}%</span> بودجه)</span>
                    <span class="backup-return">دریافتی اگر این گزینه ببرد: <strong class="ltr-num js-backup-payout">${b_payout_dollar}</strong></span>
                  </div>
                </div>
                """
            )
        backup_html = f"""
        <div class="plan-box plan-hedge">
          <div class="plan-box-header">
            <span class="step-pill pill-hedge">گام ۲ · بیمه ریسک (برای نسوختن کل پول)</span>
          </div>
          <p class="hedge-helper">
            اگر گزینه اول برنده نشود و یکی از گزینه‌های محتمل زیر اتفاق بیفتد، این پوشش باعث می‌شود پول شما نسوزد:
          </p>
          <div class="backup-list">
            {"".join(backup_items_html)}
          </div>
        </div>
        """

    # Details rows (only Primary + viable backups)
    visible_allocs = ([primary] if primary else []) + backup_legs
    detail_rows_html = []
    for a in visible_allocs:
        if not a:
            continue
        p_val = a.market_price or 0.5
        d_val = round(default_bankroll * (a.size_pct / 100.0), 1)
        shares_val = (d_val / p_val) if p_val > 0 else 0.0
        payout_val = round(shares_val, 1)
        net_dollar = round(payout_val - default_bankroll, 1)
        role_fa = "گزینه اصلی (Primary)" if a.role == "primary" else "پوشش ریسک (بیمه)"
        role_cls = "badge-green" if a.role == "primary" else "badge-blue"
        net_cls = "pos-text" if net_dollar >= 0 else "neg-text"
        net_str = f"+${net_dollar:.0f}" if net_dollar >= 0 else f"-${abs(net_dollar):.0f}"

        detail_rows_html.append(
            f"""
            <tr data-size-pct="{a.size_pct:.4f}" data-price="{p_val:.6f}">
              <td><span class="mini-badge {role_cls}">{role_fa}</span></td>
              <td class="ltr-num"><strong>{_esc(a.outcome)}</strong></td>
              <td class="ltr-num">{p_val * 100:.1f}¢</td>
              <td class="ltr-num">{a.size_pct:.1f}%</td>
              <td class="ltr-num js-row-dollar">${d_val:.0f}</td>
              <td class="ltr-num js-row-shares">{shares_val:.1f} سهم</td>
              <td class="ltr-num {net_cls} js-row-net">{net_str}</td>
            </tr>
            """
        )

    market_url = _esc(opp.market_url or opp.group_key or "https://polymarket.com")
    profit_sign = "+" if primary_net_profit_dollar >= 0 else "-"
    profit_abs = abs(primary_net_profit_dollar)
    roi_sign = "+" if primary_net_roi_pct >= 0 else ""

    return f"""
    <article class="signal-card"
      data-section="{_esc(section_key)}"
      data-trap="{'1' if is_trap else '0'}"
      data-prob="{win_prob_pct:.2f}"
      data-roi="{primary_net_roi_pct:.2f}"
      data-days="{opp.days_to_resolve:.2f}"
      data-search="{_esc((opp.title + ' ' + primary_outcome + ' ' + cat_label).lower())}">

      <!-- Card Top Bar -->
      <div class="card-top">
        <div class="card-badges">
          <span class="cat-pill" style="border-color:{cat_color}44;color:{cat_color}">{_esc(cat_label)}</span>
          <span class="time-pill">⏳ {_esc(time_left_fa)}</span>
        </div>
        <a class="poly-btn" href="{market_url}" target="_blank" rel="noopener">
          ورود به بازار در Polymarket ↗
        </a>
      </div>

      <!-- Market Question -->
      <h2 class="market-title" dir="ltr">{_esc(opp.title)}</h2>

      <!-- Probability Visual Bar -->
      <div class="prob-bar-wrap">
        <div class="prob-bar-labels">
          <span>شانس برد گزینه پیشنهادی (بر اساس قیمت لحظه‌ای بازار)</span>
          <strong class="ltr-num prob-pct-text">{win_prob_pct:.1f}%</strong>
        </div>
        <div class="prob-track">
          <div class="prob-fill" style="width:{min(100.0, max(5.0, win_prob_pct)):.1f}%"></div>
        </div>
      </div>

      <!-- Two-Box Clear Action Plan -->
      <div class="plan-grid">
        <!-- Box 1: Primary Action -->
        <div class="plan-box plan-primary" data-primary-pct="{primary_size_pct:.4f}" data-primary-roi="{primary_net_roi_pct:.4f}">
          <div class="plan-box-header">
            <span class="step-pill pill-primary">گام ۱ · پیشنهاد اصلی خرید</span>
            <span class="price-tag">قیمت هر سهم: <strong class="ltr-num">{primary_price * 100:.1f}¢</strong></span>
          </div>

          <div class="target-outcome-row">
            <span class="target-label">این گزینه را بخرید:</span>
            <span class="target-value" dir="ltr">{_esc(primary_outcome)}</span>
          </div>

          <div class="money-summary-grid">
            <div class="money-item">
              <span class="money-label">مبلغی که وارد می‌کنید</span>
              <strong class="money-val ltr-num js-primary-dollar">${primary_dollar}</strong>
              <span class="money-sub">(<span class="ltr-num">{primary_size_pct:.0f}%</span> از سرمایه شما)</span>
            </div>
            <div class="money-item money-profit-box">
              <span class="money-label">سود خالص شما در صورت برد</span>
              <strong class="money-val pos-text ltr-num js-primary-profit">{profit_sign}${profit_abs}</strong>
              <span class="money-sub pos-text ltr-num">({roi_sign}{primary_net_roi_pct:.1f}% سود خالص)</span>
            </div>
          </div>
        </div>

        <!-- Box 2: Backup / Insurance -->
        {backup_html}
      </div>

      <!-- Expandable Details Drawer (Hidden by Default to Avoid Clutter) -->
      <details class="details-drawer">
        <summary class="details-summary">
          <span>📋 مشاهده جدول دقیق تعداد سهام و جزئیات محاسبه</span>
          <span class="summary-arrow">▼</span>
        </summary>
        <div class="details-body">
          <div class="table-scroll">
            <table class="clean-table">
              <thead>
                <tr>
                  <th>نوع انتخاب</th>
                  <th>گزینه</th>
                  <th>قیمت هر سهم</th>
                  <th>درصد از بودجه</th>
                  <th>مبلغ دلاری</th>
                  <th>تعداد سهام دریافتی</th>
                  <th>سود/زیان خالص کل سبد</th>
                </tr>
              </thead>
              <tbody>
                {"".join(detail_rows_html)}
              </tbody>
            </table>
          </div>
        </div>
      </details>
    </article>
    """


def generate_html(
    opportunities: list[tuple[MarketOpportunity, PositionPlan]],
    output_path: str = "docs/index.html",
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    cards_html = []
    high_prob_count = 0
    for opp, plan in opportunities:
        p = plan.primary
        if p and (p.market_price or 0.0) >= 0.80:
            high_prob_count += 1
        cards_html.append(_render_card(opp, plan))

    cards_joined = (
        "\n".join(cards_html)
        if cards_html
        else '<div class="empty-box">در حال حاضر هیچ موقعیت فعالی در این بازه زمانی یافت نشد.</div>'
    )

    doc = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>داشبورد سیگنال‌های هوشمند Polymarket</title>
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
.ltr-num {{ direction: ltr; display: inline-block; font-family: 'Vazirmatn', monospace; font-feature-settings: "tnum"; }}

/* Top Navigation Header */
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
  transition: all 0.2s ease;
}}
.nav-link.active {{
  background: linear-gradient(135deg, #10B981 0%, #059669 100%);
  border-color: transparent;
  color: #04130D;
  box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
}}
.nav-link:hover:not(.active) {{ border-color: #38BDF8; color: #FFFFFF; }}

.main-wrap {{ max-width: 1180px; margin: 0 auto; padding: 1.5rem 1.25rem 4rem; }}

/* 3-Step Visual Guide Banner */
.guide-banner {{
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(56, 189, 248, 0.08) 100%);
  border: 1px solid rgba(16, 185, 129, 0.28);
  border-radius: 20px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.5rem;
}}
.guide-title {{
  font-size: 0.95rem;
  font-weight: 800;
  color: #34D399;
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}}
.guide-steps {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.85rem;
}}
.guide-step {{
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 14px;
  padding: 0.85rem 1rem;
  font-size: 0.83rem;
  color: #E2E8F0;
}}
.guide-step strong {{ color: #FFFFFF; display: block; margin-bottom: 0.2rem; font-size: 0.88rem; }}

/* Top Controls & Bankroll Calculator */
.dashboard-bar {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}}
.stat-card {{
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 18px;
  padding: 1.1rem 1.35rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
}}
.stat-card-highlight {{
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.16) 0%, rgba(15, 23, 42, 0.9) 100%);
  border-color: rgba(16, 185, 129, 0.45);
}}
.stat-label {{ font-size: 0.8rem; color: #94A3B8; font-weight: 500; }}
.stat-val {{ font-size: 1.7rem; font-weight: 800; color: #FFFFFF; margin-top: 0.2rem; }}
.stat-hint {{ font-size: 0.75rem; color: #64748B; margin-top: 0.2rem; }}

.bankroll-box {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.4rem;
}}
.bankroll-input {{
  background: #090E1A;
  border: 2px solid #10B981;
  border-radius: 12px;
  color: #34D399;
  font-size: 1.3rem;
  font-weight: 800;
  padding: 0.35rem 0.75rem;
  width: 145px;
  text-align: left;
  direction: ltr;
  font-family: inherit;
}}
.bankroll-input:focus {{ outline: none; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.25); }}

/* Filter & Search Bar */
.filter-bar {{
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 18px;
  padding: 1rem 1.25rem;
  margin-bottom: 1.5rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}}
.cat-tabs {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
.cat-tab {{
  background: rgba(9, 14, 26, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.2);
  color: #CBD5E1;
  border-radius: 12px;
  padding: 0.5rem 1rem;
  font-size: 0.83rem;
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s ease;
}}
.cat-tab.active {{
  background: #10B981;
  border-color: #10B981;
  color: #04130D;
}}
.filter-inputs {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.65rem; flex: 1; justify-content: flex-end; }}
.search-box {{
  background: #090E1A;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  color: #FFFFFF;
  padding: 0.55rem 0.9rem;
  font-size: 0.84rem;
  min-width: 230px;
  font-family: inherit;
}}
.sort-select {{
  background: #090E1A;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  color: #FFFFFF;
  padding: 0.52rem 0.8rem;
  font-size: 0.83rem;
  font-family: inherit;
}}

/* Market Signal Card */
.signal-card {{
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 22px;
  padding: 1.5rem;
  margin-bottom: 1.35rem;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.28);
  transition: transform 0.15s ease, border-color 0.15s ease;
}}
.signal-card:hover {{
  border-color: rgba(56, 189, 248, 0.4);
}}
.card-top {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.85rem;
}}
.card-badges {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.55rem; }}
.cat-pill {{
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid;
  border-radius: 999px;
  padding: 0.3rem 0.85rem;
  font-size: 0.78rem;
  font-weight: 700;
}}
.time-pill {{
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #FBBF24;
  border-radius: 999px;
  padding: 0.3rem 0.85rem;
  font-size: 0.78rem;
  font-weight: 700;
}}
.poly-btn {{
  background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
  color: #FFFFFF;
  padding: 0.5rem 1.05rem;
  border-radius: 12px;
  font-size: 0.82rem;
  font-weight: 700;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
  transition: opacity 0.15s ease;
}}
.poly-btn:hover {{ opacity: 0.92; }}

.market-title {{
  margin: 0 0 1rem 0;
  font-size: 1.22rem;
  font-weight: 800;
  color: #FFFFFF;
  text-align: left;
  letter-spacing: -0.01em;
}}

/* Probability Bar */
.prob-bar-wrap {{
  background: rgba(9, 14, 26, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 14px;
  padding: 0.75rem 1rem;
  margin-bottom: 1.15rem;
}}
.prob-bar-labels {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.82rem;
  color: #CBD5E1;
  margin-bottom: 0.45rem;
}}
.prob-pct-text {{ font-size: 1rem; color: #34D399; font-weight: 800; }}
.prob-track {{
  width: 100%;
  height: 10px;
  background: rgba(30, 41, 59, 0.9);
  border-radius: 999px;
  overflow: hidden;
}}
.prob-fill {{
  height: 100%;
  background: linear-gradient(90deg, #10B981 0%, #34D399 100%);
  border-radius: 999px;
}}

/* Two-Column Action Plan Grid */
.plan-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
}}
.plan-box {{
  border-radius: 18px;
  padding: 1.2rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}}
.plan-primary {{
  background: linear-gradient(145deg, rgba(16, 185, 129, 0.14) 0%, rgba(9, 14, 26, 0.9) 100%);
  border: 1px solid rgba(16, 185, 129, 0.4);
}}
.plan-hedge {{
  background: linear-gradient(145deg, rgba(56, 189, 248, 0.12) 0%, rgba(9, 14, 26, 0.9) 100%);
  border: 1px solid rgba(56, 189, 248, 0.35);
}}
.plan-solo {{
  background: rgba(9, 14, 26, 0.6);
  border: 1px dashed rgba(148, 163, 184, 0.25);
  justify-content: center;
}}

.plan-box-header {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 1rem;
}}
.step-pill {{
  font-size: 0.78rem;
  font-weight: 800;
  padding: 0.28rem 0.75rem;
  border-radius: 999px;
}}
.pill-primary {{ background: #10B981; color: #04130D; }}
.pill-hedge {{ background: #38BDF8; color: #04131D; }}
.pill-solo {{ background: rgba(148, 163, 184, 0.18); color: #CBD5E1; }}
.price-tag {{ font-size: 0.8rem; color: #94A3B8; }}

.target-outcome-row {{
  background: rgba(9, 14, 26, 0.75);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 14px;
  padding: 0.8rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 1rem;
}}
.target-label {{ font-size: 0.85rem; color: #CBD5E1; font-weight: 600; }}
.target-value {{
  font-size: 1.25rem;
  font-weight: 800;
  color: #34D399;
  background: rgba(16, 185, 129, 0.12);
  padding: 0.2rem 0.75rem;
  border-radius: 10px;
}}

.money-summary-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}}
.money-item {{
  background: rgba(9, 14, 26, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  padding: 0.75rem 0.9rem;
  display: flex;
  flex-direction: column;
}}
.money-profit-box {{
  border-color: rgba(16, 185, 129, 0.3);
  background: rgba(16, 185, 129, 0.07);
}}
.money-label {{ font-size: 0.74rem; color: #94A3B8; }}
.money-val {{ font-size: 1.35rem; font-weight: 800; color: #FFFFFF; margin-top: 0.15rem; }}
.money-sub {{ font-size: 0.74rem; color: #94A3B8; margin-top: 0.1rem; }}

.solo-text {{
  font-size: 0.88rem;
  color: #CBD5E1;
  line-height: 1.75;
}}
.solo-text strong {{ color: #34D399; display: block; margin-bottom: 0.3rem; font-size: 0.95rem; }}

.hedge-helper {{
  margin: 0 0 0.75rem 0;
  font-size: 0.8rem;
  color: #CBD5E1;
}}
.backup-list {{ display: flex; flex-direction: column; gap: 0.6rem; }}
.backup-item {{
  background: rgba(9, 14, 26, 0.75);
  border: 1px solid rgba(56, 189, 248, 0.25);
  border-radius: 12px;
  padding: 0.7rem 0.9rem;
  font-size: 0.82rem;
}}
.backup-top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.35rem;
  color: #F8FAFC;
}}
.backup-price {{ color: #94A3B8; font-size: 0.78rem; }}
.backup-bottom {{
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.78rem;
  color: #94A3B8;
}}
.backup-dollar {{ color: #38BDF8; font-size: 0.92rem; }}
.backup-return strong {{ color: #E2E8F0; }}

/* Collapsible Details Drawer */
.details-drawer {{
  margin-top: 1rem;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  padding-top: 0.75rem;
}}
.details-summary {{
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.8rem;
  font-weight: 600;
  color: #94A3B8;
  padding: 0.3rem 0.2rem;
}}
.details-summary::-webkit-details-marker {{ display: none; }}
.details-summary:hover {{ color: #E2E8F0; }}
.details-body {{ margin-top: 0.75rem; }}
.table-scroll {{ overflow-x: auto; border-radius: 12px; border: 1px solid rgba(148, 163, 184, 0.16); }}
.clean-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
  min-width: 600px;
  background: rgba(9, 14, 26, 0.8);
}}
.clean-table th {{
  text-align: right;
  padding: 0.65rem 0.85rem;
  background: rgba(15, 23, 42, 0.95);
  color: #94A3B8;
  font-weight: 600;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}}
.clean-table td {{
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}}
.mini-badge {{
  display: inline-block;
  padding: 0.18rem 0.55rem;
  border-radius: 8px;
  font-size: 0.73rem;
  font-weight: 700;
}}
.badge-green {{ background: rgba(16, 185, 129, 0.15); color: #34D399; }}
.badge-blue {{ background: rgba(56, 189, 248, 0.15); color: #38BDF8; }}
.pos-text {{ color: #34D399 !important; font-weight: 800; }}
.neg-text {{ color: #FB7185 !important; font-weight: 800; }}
.empty-box {{
  text-align: center;
  padding: 3rem;
  background: rgba(15, 23, 42, 0.8);
  border-radius: 20px;
  color: #94A3B8;
}}
</style>
</head>
<body>

<header class="navbar">
  <div class="navbar-inner">
    <div class="brand-wrap">
      <div class="brand-logo">🎯</div>
      <div>
        <div class="brand-title">دستیار هوشمند معاملات Polymarket</div>
        <div class="brand-sub">آخرین بروزرسانی خودکار: <span class="ltr-num">{_esc(now_str)}</span></div>
      </div>
    </div>
    <nav class="nav-pills">
      <a class="nav-link active" href="index.html">📡 پیشنهادهای امروز ({len(opportunities)})</a>
      <a class="nav-link" href="results.html">🏆 کارنامه و نتایج قبلی</a>
    </nav>
  </div>
</header>

<main class="main-wrap">

  <!-- Simple 3-Step Visual Guide -->
  <section class="guide-banner">
    <div class="guide-title">💡 راهنمای سریع (در ۳ قدم ساده):</div>
    <div class="guide-steps">
      <div class="guide-step">
        <strong>۱. تعیین مبلغ سرمایه</strong>
        در کادر سبز زیر بنویسید قصد دارید برای هر بازار چند دلار وارد کنید (مثلاً ۱۰۰ یا ۱۰۰۰ دلار).
      </div>
      <div class="guide-step">
        <strong>۲. مشاهده گزینه پیشنهادی</strong>
        در هر کارت، <b>«گام ۱ (کادر سبز)»</b> دقیقاً می‌گوید کدام گزینه را بخرید و چقدر سود خالص می‌کنید.
      </div>
      <div class="guide-step">
        <strong>۳. ثبت در سایت Polymarket</strong>
        روی دکمه آبی <b>«ورود به بازار در Polymarket»</b> بالای هر کارت بزنید و همان گزینه را بخرید.
      </div>
    </div>
  </section>

  <!-- Summary & Live Money Calculator -->
  <section class="dashboard-bar">
    <div class="stat-card stat-card-highlight">
      <div class="stat-label">💰 سرمایه شما برای هر بازار (دلار $)</div>
      <div class="bankroll-box">
        <input id="bankrollInput" type="number" min="10" step="50" value="1000" class="bankroll-input" oninput="recalcBankroll()">
        <span style="font-size:0.85rem;color:#34D399;font-weight:700">دلار</span>
      </div>
      <div class="stat-hint">با تغییر این عدد، تمام مبالغ و سودها خودکار حساب می‌شوند</div>
    </div>

    <div class="stat-card">
      <div class="stat-label">📊 تعداد موقعیت‌های آماده معامله</div>
      <div class="stat-val ltr-num">{len(opportunities)}</div>
      <div class="stat-hint">بازارهای نزدیک به اعلام نتیجه (کمتر از ۷ روز)</div>
    </div>

    <div class="stat-card">
      <div class="stat-label">✅ موقعیت‌های با شانس برد بالای ۸۰٪</div>
      <div class="stat-val ltr-num" style="color:#34D399">{high_prob_count}</div>
      <div class="stat-hint">گزینه‌هایی که احتمال برد بسیار بالایی دارند</div>
    </div>
  </section>

  <!-- Category Tabs & Search -->
  <section class="filter-bar">
    <div class="cat-tabs">
      <button type="button" class="cat-tab active" data-sec="all" onclick="setCategory(this)">همه بازارها ({len(opportunities)})</button>
      <button type="button" class="cat-tab" data-sec="economy" onclick="setCategory(this)">📊 اقتصاد و تورم</button>
      <button type="button" class="cat-tab" data-sec="markets" onclick="setCategory(this)">📈 سهام و رمزارز</button>
      <button type="button" class="cat-tab" data-sec="politics" onclick="setCategory(this)">🗳️ سیاست و انتخابات</button>
    </div>

    <div class="filter-inputs">
      <input id="searchInput" type="text" class="search-box" placeholder="🔍 جستجوی نام بازار (مثلاً CPI، Bitcoin...)" oninput="applyFilters()">
      <select id="sortSelect" class="sort-select" onchange="applyFilters()">
        <option value="prob">مرتب‌سازی: بیشترین شانس برد</option>
        <option value="days">مرتب‌سازی: نزدیک‌ترین زمان نتیجه</option>
        <option value="roi">مرتب‌سازی: بیشترین درصد سود</option>
      </select>
    </div>
  </section>

  <!-- Cards List -->
  <section id="cardsContainer">
    {cards_joined}
  </section>

</main>

<script>
let activeSection = 'all';

function setCategory(btn) {{
  document.querySelectorAll('.cat-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeSection = btn.getAttribute('data-sec') || 'all';
  applyFilters();
}}

function applyFilters() {{
  const q = (document.getElementById('searchInput').value || '').trim().toLowerCase();
  const sortBy = document.getElementById('sortSelect').value;
  const container = document.getElementById('cardsContainer');
  const cards = Array.from(container.querySelectorAll('.signal-card'));

  cards.forEach(card => {{
    const sec = card.getAttribute('data-section') || '';
    const search = card.getAttribute('data-search') || '';
    const okSec = (activeSection === 'all') || (sec === activeSection);
    const okSearch = !q || search.includes(q);
    card.style.display = (okSec && okSearch) ? '' : 'none';
  }});

  cards.sort((a, b) => {{
    if (sortBy === 'days') {{
      return parseFloat(a.getAttribute('data-days') || '99') - parseFloat(b.getAttribute('data-days') || '99');
    }}
    if (sortBy === 'roi') {{
      return parseFloat(b.getAttribute('data-roi') || '0') - parseFloat(a.getAttribute('data-roi') || '0');
    }}
    return parseFloat(b.getAttribute('data-prob') || '0') - parseFloat(a.getAttribute('data-prob') || '0');
  }});

  cards.forEach(c => container.appendChild(c));
}}

function recalcBankroll() {{
  const raw = parseFloat(document.getElementById('bankrollInput').value || '1000');
  const bankroll = (!isNaN(raw) && raw > 0) ? raw : 1000;

  // Update Primary Boxes
  document.querySelectorAll('.plan-primary').forEach(box => {{
    const pct = parseFloat(box.getAttribute('data-primary-pct') || '0');
    const roi = parseFloat(box.getAttribute('data-primary-roi') || '0');
    const dollar = Math.round(bankroll * (pct / 100.0));
    const profit = Math.round(bankroll * (roi / 100.0));

    const dollarEl = box.querySelector('.js-primary-dollar');
    const profitEl = box.querySelector('.js-primary-profit');
    if (dollarEl) dollarEl.textContent = '$' + dollar.toLocaleString();
    if (profitEl) {{
      profitEl.textContent = (profit >= 0 ? '+$' : '-$') + Math.abs(profit).toLocaleString();
    }}
  }});

  // Update Backup Items
  document.querySelectorAll('.backup-item').forEach(item => {{
    const pct = parseFloat(item.getAttribute('data-size-pct') || '0');
    const price = parseFloat(item.getAttribute('data-price') || '0.5');
    const dollar = Math.round(bankroll * (pct / 100.0));
    const payout = price > 0 ? Math.round((bankroll * (pct / 100.0)) / price) : 0;

    const dEl = item.querySelector('.js-backup-dollar');
    const pEl = item.querySelector('.js-backup-payout');
    if (dEl) dEl.textContent = '$' + dollar.toLocaleString();
    if (pEl) pEl.textContent = '$' + payout.toLocaleString();
  }});

  // Update Expandable Details Rows
  document.querySelectorAll('tr[data-size-pct]').forEach(row => {{
    const pct = parseFloat(row.getAttribute('data-size-pct') || '0');
    const price = parseFloat(row.getAttribute('data-price') || '0.5');
    const dollar = bankroll * (pct / 100.0);
    const shares = price > 0 ? (dollar / price) : 0;
    const netDollar = Math.round(shares - bankroll);

    const dCell = row.querySelector('.js-row-dollar');
    const sCell = row.querySelector('.js-row-shares');
    const nCell = row.querySelector('.js-row-net');
    if (dCell) dCell.textContent = '$' + Math.round(dollar).toLocaleString();
    if (sCell) sCell.textContent = shares.toFixed(1) + ' سهم';
    if (nCell) nCell.textContent = (netDollar >= 0 ? '+$' : '-$') + Math.abs(netDollar).toLocaleString();
  }});
}}
</script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)

    return output_path
