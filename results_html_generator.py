"""
results_html_generator.py — Graphical Results & Accuracy Page Generator (GitHub Pages).
"""

from __future__ import annotations

import csv
import html
import math
import os
import re
from datetime import datetime, timezone


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


def _is_barrier_trap(title: str, outcome: str, price: float) -> bool:
    hit_q = bool(re.search(r"\bwhat (?:price )?will .* hit\b", (title or "").lower()))
    arrow_o = bool(re.match(r"^[↑↓]\s*\$?[\d,.]+", (outcome or "").strip()))
    return (hit_q or arrow_o) and price < 0.15


def _svg_ring(pct: float, color: str = "#10B981", size: int = 76, stroke: int = 7) -> str:
    r = (size - stroke * 2) // 2
    cx = size // 2
    circ = round(2 * math.pi * r, 2)
    offset = round(circ - (max(0.0, min(100.0, pct)) / 100.0) * circ, 2)
    return f"""
    <div class="ring-wrap" style="width:{size}px;height:{size}px;">
      <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" class="ring-svg">
        <circle cx="{cx}" cy="{cx}" r="{r}" stroke="#1E293B" stroke-width="{stroke}" fill="transparent"/>
        <circle cx="{cx}" cy="{cx}" r="{r}" stroke="{color}" stroke-width="{stroke}"
                stroke-dasharray="{circ}" stroke-dashoffset="{offset}"
                stroke-linecap="round" fill="transparent"/>
      </svg>
      <span class="ring-val ltr">{pct:.1f}%</span>
    </div>
    """


def generate_results_html(
    resolved_rows: list[dict],
    output_path: str = "docs/results.html",
    log_csv_path: str = "predictions_log.csv",
    generated_at: datetime | None = None,
    log_by_key: dict[str, dict] | None = None,
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

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

    for row in resolved_rows:
        title = (row.get("title") or "").strip()
        if not title or _is_sports_noise(title):
            continue

        gk = (row.get("group_key") or "").strip()
        log_match = log_by_group.get(gk, {})

        primary_outcome = (row.get("primary_outcome") or log_match.get("primary_outcome") or "").strip()
        resolved_outcome = (row.get("resolved_outcome") or "").strip()
        if not resolved_outcome:
            continue

        raw_price = _to_float(row.get("primary_market_price"), 0.0)
        log_price = _to_float(log_match.get("primary_market_price"), 0.0)
        entry_price = log_price if (raw_price >= 0.98 and 0.01 < log_price < 0.98) else (raw_price or 0.5)
        entry_price = max(0.02, min(0.99, entry_price))

        if _is_barrier_trap(title, primary_outcome, entry_price):
            continue

        is_win = str(row.get("is_correct") or "").strip().lower() == "true" or (
            primary_outcome.lower() == resolved_outcome.lower() and primary_outcome != ""
        )

        if is_win:
            wins += 1
        else:
            losses += 1

        audited_rows.append(
            {
                "title": title,
                "primary_outcome": primary_outcome,
                "resolved_outcome": resolved_outcome,
                "is_win": is_win,
                "market_url": row.get("market_url") or gk or "https://polymarket.com",
            }
        )

    total_count = wins + losses
    win_rate = round((wins / total_count) * 100.0, 1) if total_count > 0 else 0.0
    loss_rate = round(100.0 - win_rate, 1) if total_count > 0 else 0.0
    ring_html = _svg_ring(win_rate, color="#10B981", size=78, stroke=7)

    rows_html = []
    for item in audited_rows:
        status_html = (
            '<span class="status win">✅ پیش‌بینی درست</span>'
            if item["is_win"]
            else '<span class="status loss">❌ پیش‌بینی خطا</span>'
        )
        rows_html.append(
            f"""
            <div class="res-card">
              <div class="res-top">
                {status_html}
                <a class="ext-link" href="{_esc(item['market_url'])}" target="_blank" rel="noopener">مشاهده در Polymarket ↗</a>
              </div>
              <a class="res-title" href="{_esc(item['market_url'])}" target="_blank" rel="noopener" dir="ltr">{_esc(item['title'])}</a>
              <div class="res-compare">
                <div>پیشنهاد ربات: <strong class="pick ltr">{_esc(item['primary_outcome'])}</strong></div>
                <div>نتیجه نهایی بازار: <strong class="final ltr">{_esc(item['resolved_outcome'])}</strong></div>
              </div>
            </div>
            """
        )

    list_body = (
        "\n".join(rows_html)
        if rows_html
        else '<div class="empty">هنوز نتیجه‌ای ثبت نشده است.</div>'
    )

    doc = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>کارنامه و نتایج قبلی — PolyBet AI</title>
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
.ltr {{ direction: ltr; display: inline-block; font-variant-numeric: tabular-nums; }}

.header {{
  background: rgba(17, 24, 39, 0.95);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid #1E293B;
  position: sticky;
  top: 0;
  z-index: 20;
}}
.header-inner {{
  max-width: 1140px;
  margin: 0 auto;
  padding: 0.75rem 1rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
}}
.brand {{
  display: flex;
  align-items: center;
  gap: 0.55rem;
  font-weight: 800;
  font-size: 1rem;
  white-space: nowrap;
}}
.brand-logo {{
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: linear-gradient(135deg, #10B981, #4F46E5);
  color: #052E16;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
  flex-shrink: 0;
}}
.nav {{
  display: flex;
  align-items: center;
  gap: 0.35rem;
  background: #0B0F19;
  padding: 0.25rem;
  border-radius: 12px;
  border: 1px solid #1E293B;
}}
.nav-btn {{
  padding: 0.4rem 0.75rem;
  border-radius: 9px;
  font-size: 0.78rem;
  font-weight: 800;
  color: #94A3B8;
  white-space: nowrap;
}}
.nav-btn.active {{
  background: #10B981;
  color: #052E16;
}}

.container {{
  max-width: 1140px;
  margin: 0 auto;
  padding: 1.5rem 1.25rem 4rem;
}}

.hero-summary {{
  background: #111827;
  border: 1px solid #1E293B;
  border-radius: 20px;
  padding: 1.35rem;
  margin-bottom: 1.5rem;
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 1.5rem;
}}
@media (max-width: 640px) {{
  .hero-summary {{ grid-template-columns: 1fr; }}
}}
.ring-wrap {{
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}}
.ring-svg {{ transform: rotate(-90deg); }}
.ring-val {{
  position: absolute;
  font-size: 0.9rem;
  font-weight: 800;
  color: #34D399;
}}

.bar-wrap {{ display: flex; flex-direction: column; gap: 0.6rem; }}
.bar-head {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}}
.bar-track {{
  height: 14px;
  background: #1E293B;
  border-radius: 999px;
  overflow: hidden;
  display: flex;
  padding: 2px;
  gap: 3px;
}}
.seg-win {{ height: 100%; background: #10B981; border-radius: 999px; }}
.seg-loss {{ height: 100%; background: #F43F5E; border-radius: 999px; }}

.res-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(460px, 1fr));
  gap: 1rem;
}}
@media (max-width: 640px) {{
  .res-grid {{ grid-template-columns: 1fr; }}
}}
.res-card {{
  background: #111827;
  border: 1px solid #1E293B;
  border-radius: 16px;
  padding: 1.1rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.75rem;
}}
.res-top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.76rem;
}}
.status.win {{ color: #34D399; font-weight: 800; }}
.status.loss {{ color: #FB7185; font-weight: 800; }}
.ext-link {{ color: #94A3B8; font-size: 0.74rem; }}
.res-title {{
  font-weight: 700;
  font-size: 0.94rem;
  color: #FFFFFF;
  text-align: left;
  line-height: 1.45;
}}
.res-compare {{
  background: #0B0F19;
  border: 1px solid #1E293B;
  border-radius: 12px;
  padding: 0.7rem 0.9rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  color: #94A3B8;
}}
.pick {{ color: #34D399; }}
.final {{ color: #FFFFFF; }}
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
      <a class="nav-btn" href="index.html">پیشنهادهای هوشمند امروز</a>
      <a class="nav-btn active" href="results.html">کارنامه و نتایج قبلی ({total_count})</a>
    </nav>
    <span></span>
  </div>
</header>

<main class="container">
  <div class="hero-summary">
    <div style="display:flex;align-items:center;gap:1rem;">
      {ring_html}
      <div>
        <div style="font-size:0.78rem;color:#34D399;font-weight:700;">دقت پیش‌بینی‌های ربات</div>
        <div style="font-size:1.3rem;font-weight:800;color:#FFF;">{wins} درست از {total_count} بازار</div>
        <div style="font-size:0.76rem;color:#94A3B8;">آمار واقعی بازارهای تسویه‌شده در Polymarket</div>
      </div>
    </div>

    <div class="bar-wrap">
      <div class="bar-head">
        <strong style="font-size:0.86rem;">نمودار مقایسه‌ای پیش‌بینی‌های درست در برابر خطا</strong>
        <div style="display:flex;gap:1rem;font-size:0.8rem;font-weight:700;">
          <span style="color:#34D399;">درست: {wins} ({win_rate:.1f}%)</span>
          <span style="color:#FB7185;">خطا: {losses} ({loss_rate:.1f}%)</span>
        </div>
      </div>
      <div class="bar-track">
        <div class="seg-win" style="width:{win_rate:.1f}%"></div>
        <div class="seg-loss" style="width:{loss_rate:.1f}%"></div>
      </div>
    </div>
  </div>

  <div class="res-grid">
    {list_body}
  </div>
</main>
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
    return generate_results_html(
        resolved_rows=resolved_rows,
        output_path=output_path,
        generated_at=generated_at,
        log_by_key=log_by_key,
    )
