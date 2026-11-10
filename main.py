"""
main.py — PolyBet v2.0 Orchestrator (Zero-Config Unique GitHub Links per Scan).

REPLACES your current main.py.

KEY FEATURES & FIXES IN THIS VERSION:
1. ZERO-CONFIG UNIQUE GITHUB LINKS PER TELEGRAM MESSAGE:
   You do NOT need to configure `DASHBOARD_URL`!
   On every run, `main.py` automatically detects your GitHub repository
   (`owner/repo`) from GitHub Actions' built-in `GITHUB_REPOSITORY` variable
   (or `git remote get-url origin`) and generates a unique timestamped snapshot:
     `docs/scans/scan-<YYYYMMDD-HHMMSS>.html`
   Every Telegram message automatically includes:
   - Instant Unique Web Preview Link (`htmlpreview.github.io` — works immediately
     on any public GitHub repo even without enabling GitHub Pages!)
   - Unique GitHub Pages Snapshot Link (`https://<owner>.github.io/<repo>/scans/scan-<id>.html`)
   - Main Live Dashboard Link (`https://<owner>.github.io/<repo>/?scan=<id>`)
2. PUSH-FIRST WORKFLOW SUPPORT (`--prepare-telegram`):
   Allows `daily_scan.yml` to commit & push `docs/scans/scan-<id>.html` to GitHub
   FIRST, and then send the Telegram message so the unique link is already live
   on GitHub the moment the Telegram notification arrives.
3. FIX BUG #1 (Binary Single-Market Outcome Bug):
   Preserves `["Yes", "No"]` outcomes for single binary markets inside event wrappers.
"""

from __future__ import annotations

import csv
import glob
import logging
import os
import re
import subprocess
import sys
from collections import OrderedDict
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from html_generator import build_html, write_html
from position_logic import PositionPlan, build_position_plan
from scanner import ScannedMarket, scan_markets
from sources.aggregator import build_signal
from telegram_bot import format_signal_message, send_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DOCS_HTML_PATH = os.getenv("HTML_OUTPUT_PATH", "docs/index.html")
SCANS_ARCHIVE_DIR = os.getenv("SCANS_ARCHIVE_DIR", "docs/scans")
MAX_ARCHIVED_SCANS = 30
PREDICTIONS_LOG_PATH = os.getenv("PREDICTIONS_LOG_PATH", "predictions_log.csv")
SEND_PER_MARKET_MESSAGES = os.getenv("SEND_PER_MARKET_MESSAGES", "false").lower() == "true"

PREDICTIONS_LOG_FIELDS = [
    "logged_at_utc", "group_key", "title", "category", "days_to_resolve_at_scan",
    "consensus_score", "edge", "num_sources", "primary_outcome", "primary_size_pct",
    "primary_market_price", "hedge_or_secondary_summary", "warning", "market_url",
]

NUMERIC_SIGNAL_DOMAINS: frozenset[str] = frozenset(
    {"fed", "cpi", "pce", "gdp", "employment", "ecb", "boc", "boe"}
)


def detect_github_repo() -> tuple[str, str]:
    """Auto-detect `(owner/repo, branch)` from GitHub Actions env or local `.git` remote."""
    gh_repo = (os.getenv("GITHUB_REPOSITORY") or "").strip()
    branch = (os.getenv("GITHUB_REF_NAME") or "main").strip() or "main"

    if "/" not in gh_repo:
        try:
            remote_url = subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            m = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?$", remote_url)
            if m:
                gh_repo = m.group(1)
        except Exception:
            pass

    return gh_repo, branch


def build_unique_scan_urls(scan_id: str) -> dict[str, str]:
    """Build unique, clickable GitHub links for this specific scan with zero manual config."""
    explicit_base = (os.getenv("DASHBOARD_URL") or "").strip().rstrip("/")
    gh_repo, branch = detect_github_repo()

    urls: dict[str, str] = {}
    if gh_repo and "/" in gh_repo:
        owner, repo = gh_repo.split("/", 1)
        pages_base = explicit_base or f"https://{owner}.github.io/{repo}"
        raw_blob_url = f"https://github.com/{owner}/{repo}/blob/{branch}/docs/scans/scan-{scan_id}.html"
        urls["instant_preview_url"] = f"https://htmlpreview.github.io/?{raw_blob_url}"
        urls["unique_pages_url"] = f"{pages_base}/scans/scan-{scan_id}.html"
        urls["live_dashboard_url"] = f"{pages_base}/?scan={scan_id}"
        urls["github_Run_url"] = (
            f"https://github.com/{gh_repo}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"
            if os.getenv("GITHUB_RUN_ID")
            else raw_blob_url
        )
    elif explicit_base:
        urls["unique_pages_url"] = f"{explicit_base}/scans/scan-{scan_id}.html"
        urls["live_dashboard_url"] = f"{explicit_base}/?scan={scan_id}"

    return urls


def write_unique_scan_snapshot(scan_id: str, html_results: list, generated_at: datetime) -> str:
    """Write a permanent unique snapshot `docs/scans/scan-<scan_id>.html` and prune old archives."""
    os.makedirs(SCANS_ARCHIVE_DIR, exist_ok=True)
    snapshot_path = os.path.join(SCANS_ARCHIVE_DIR, f"scan-{scan_id}.html")
    content = build_html(html_results, generated_at=generated_at)
    # Adjust relative navbar links (`href="index.html"` -> `href="../index.html"`) inside `docs/scans/`
    content_adjusted = content.replace('href="index.html"', 'href="../index.html"').replace(
        'href="results.html"', 'href="../results.html"'
    )
    with open(snapshot_path, "w", encoding="utf-8") as f:
        f.write(content_adjusted)

    # Keep only the latest MAX_ARCHIVED_SCANS files so the git repo stays lightweight
    existing = sorted(glob.glob(os.path.join(SCANS_ARCHIVE_DIR, "scan-*.html")))
    if len(existing) > MAX_ARCHIVED_SCANS:
        for old_file in existing[:-MAX_ARCHIVED_SCANS]:
            try:
                os.remove(old_file)
            except OSError:
                pass

    return snapshot_path


def group_scanned_markets(markets: list[ScannedMarket]) -> list[list[ScannedMarket]]:
    """Group scanned markets that belong to the same real-world event."""
    groups: "OrderedDict[str, list[ScannedMarket]]" = OrderedDict()
    for m in markets:
        key = m.url or m.market_id
        groups.setdefault(key, []).append(m)
    return list(groups.values())


def extract_yes_price(market: ScannedMarket) -> float:
    """Extract the market-implied probability that THIS candidate/outcome wins."""
    if market.outcomes and market.outcome_prices and len(market.outcomes) == len(market.outcome_prices):
        for outcome, price in zip(market.outcomes, market.outcome_prices):
            if outcome.strip().lower() == "yes":
                return price
    return 0.5


def favorite_market(group: list[ScannedMarket]) -> ScannedMarket:
    """The single outcome the market currently prices as most likely."""
    return max(group, key=extract_yes_price)


def is_single_binary_market(group: list[ScannedMarket]) -> bool:
    """Return True when the group has only 1 sub-market and its outcomes are Yes/No."""
    if len(group) != 1:
        return False
    m = group[0]
    norm_outcomes = {o.strip().lower() for o in (m.outcomes or [])}
    return norm_outcomes == {"yes", "no"} or not m.group_label or m.group_label.strip() == m.question.strip()


def resolve_signal_query(group: list[ScannedMarket], representative: ScannedMarket) -> str:
    if is_single_binary_market(group):
        return representative.question
    if representative.category in NUMERIC_SIGNAL_DOMAINS:
        favorite = favorite_market(group)
        return favorite.question
    return representative.event_title or representative.question


def build_group_plan(group: list[ScannedMarket], signal) -> tuple[PositionPlan, str]:
    """Build ONE PositionPlan for the whole group (Fixes Bug #1 & Bug #8)."""
    representative = group[0]
    if is_single_binary_market(group):
        outcomes = list(representative.outcomes) if representative.outcomes else ["Yes", "No"]
        yes_p = extract_yes_price(representative)
        outcome_prices = (
            list(representative.outcome_prices)
            if representative.outcome_prices and len(representative.outcome_prices) == len(outcomes)
            else [yes_p, round(max(0.0, 1.0 - yes_p), 4)]
        )
        plan = build_position_plan(
            market_id=representative.market_id,
            question=representative.question,
            outcomes=outcomes,
            outcome_prices=outcome_prices,
            signal=signal,
        )
        return plan, representative.question

    title = representative.event_title or representative.question
    outcomes = [m.group_label or m.question for m in group]
    outcome_prices = [extract_yes_price(m) for m in group]
    plan = build_position_plan(
        market_id=representative.market_id,
        question=title,
        outcomes=outcomes,
        outcome_prices=outcome_prices,
        signal=signal,
    )
    return plan, title


def contextualize_warning(category: str, warning: str | None) -> str | None:
    if not warning:
        return warning
    if category == "elections":
        return warning + " (RACE_PAGE_MAP در sources/polls.py تنظیم نشده است.)"
    return warning + f" ({category} API/.env؟)"


def _already_logged_today(path: str, group_key: str, today_prefix: str) -> bool:
    """Prevent duplicate rows if daily_scan.yml retries python main.py on the same day."""
    if not os.path.isfile(path):
        return False
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("group_key") == group_key and (row.get("logged_at_utc") or "").startswith(today_prefix):
                    return True
    except OSError:
        return False
    return False


def append_prediction_log(
    group_key: str, title: str, category: str, days_to_resolve: float,
    plan: PositionPlan, market_url: str, path: str = PREDICTIONS_LOG_PATH,
) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    today_prefix = now_iso[:10]
    if _already_logged_today(path, group_key, today_prefix):
        logger.info("Skipping duplicate same-day log entry for %s", group_key)
        return

    file_exists = os.path.isfile(path)
    non_primary = [a for a in plan.allocations if a.role != "primary"]
    hedge_summary = "; ".join(f"{a.role}:{a.outcome}={a.size_pct:.1f}%" for a in non_primary)
    row = {
        "logged_at_utc": now_iso,
        "group_key": group_key,
        "title": title,
        "category": category,
        "days_to_resolve_at_scan": round(days_to_resolve, 3),
        "consensus_score": plan.consensus_score,
        "edge": plan.edge,
        "num_sources": plan.num_sources,
        "primary_outcome": plan.primary.outcome if plan.primary else "",
        "primary_size_pct": plan.primary.size_pct if plan.primary else "",
        "primary_market_price": plan.primary.market_price if plan.primary else "",
        "hedge_or_secondary_summary": hedge_summary,
        "warning": plan.warning or "",
        "market_url": market_url,
    }
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PREDICTIONS_LOG_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def build_daily_summary_text(html_results: list, scan_id: str, generated_at: datetime) -> str:
    """Format the daily Telegram digest including unique GitHub links for this scan."""
    timestamp_str = generated_at.strftime("%Y-%m-%d %H:%M UTC")
    num_events = len(html_results)
    urls = build_unique_scan_urls(scan_id)

    lines = [
        "📊 *گزارش اسکن روزانه PolyBet Quant v2.0*",
        f"🆔 شناسه یکتای اسکن: `{scan_id}`",
        f"🕒 زمان اسکن: {timestamp_str}",
        f"🔢 تعداد رویدادهای تحلیل‌شده: {num_events}",
    ]

    if html_results:
        lines.append("")
        lines.append("🎯 *برترین موقعیت‌های کالیبره‌شده این اسکن:*")
        sorted_items = sorted(
            html_results,
            key=lambda item: (item[2].consensus_score, item[2].edge),
            reverse=True,
        )
        for idx, (market, title, plan, days_to_resolve) in enumerate(sorted_items[:8], start=1):
            primary = plan.primary
            if not primary:
                continue
            clean_title = (title or market.question or "").replace("*", "")
            clean_outcome = (primary.outcome or "").replace("*", "")
            price_c = (primary.market_price or 0.0) * 100.0
            net_roi = getattr(primary, "net_roi_if_wins_pct", None)
            roi_str = f" | سود خالص: {net_roi:+.1f}%" if net_roi is not None else ""
            lines.append(
                f"{idx}. *{clean_title}*\n"
                f"   🟢 گزینه اصلی: {clean_outcome} ({primary.size_pct:.1f}% @ {price_c:.1f}¢){roi_str} | ⏳ {days_to_resolve:.1f}d"
            )

    if urls.get("instant_preview_url"):
        lines.append("")
        lines.append(f"⚡ مشاهده فوری داشبورد یکتای این اسکن (بدون نیاز به تنظیمات):\n{urls['instant_preview_url']}")
    if urls.get("unique_pages_url"):
        lines.append("")
        lines.append(f"🌐 لینک یکتای GitHub Pages این اسکن:\n{urls['unique_pages_url']}")
    if urls.get("live_dashboard_url"):
        lines.append("")
        lines.append(f"📊 داشبورد اصلی (آخرین وضعیت):\n{urls['live_dashboard_url']}")

    return "\n".join(lines)


def _should_dry_run(explicit_dry_run: bool | None) -> bool:
    if explicit_dry_run is not None:
        return explicit_dry_run
    if "--dry-run" in sys.argv or os.getenv("DRY_RUN", "").lower() == "true":
        return True
    send_live_env = os.getenv("SEND_LIVE_SIGNALS", "").strip().lower()
    if send_live_env == "false":
        return True
    if send_live_env == "true":
        return False
    has_creds = bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip() and os.getenv("TELEGRAM_CHAT_ID", "").strip())
    return not has_creds


def run(window_days: float = 7.0, dry_run: bool | None = None, prepare_telegram_path: str | None = None) -> list[str]:
    load_dotenv()
    dry_run = _should_dry_run(dry_run)
    now_utc = datetime.now(timezone.utc)
    scan_id = now_utc.strftime("%Y%m%d-%H%M%S")

    markets = scan_markets(window_days=window_days)
    logger.info("Scanned %d markets within %.0f-day resolve window.", len(markets), window_days)

    groups = group_scanned_markets(markets)
    logger.info("Consolidated into %d event sections.", len(groups))

    messages: list[str] = []
    html_results = []

    for group in groups:
        representative = group[0]
        signal_query = resolve_signal_query(group, representative)
        signal = build_signal(signal_query, representative.category)

        plan, title = build_group_plan(group, signal)
        plan.warning = contextualize_warning(representative.category, plan.warning)

        days_to_resolve = min(m.days_to_resolve for m in group)
        html_results.append((representative, title, plan, days_to_resolve))

        try:
            append_prediction_log(
                group_key=representative.url or representative.market_id,
                title=title,
                category=representative.category,
                days_to_resolve=days_to_resolve,
                plan=plan,
                market_url=representative.url,
                path=PREDICTIONS_LOG_PATH,
            )
        except OSError as exc:
            logger.warning("Failed to append prediction log for group %s: %s", title, exc)

        message = format_signal_message(plan, representative.url, days_to_resolve, title=title)
        messages.append(message)

        if not dry_run and SEND_PER_MARKET_MESSAGES and not prepare_telegram_path:
            send_message(message)

    try:
        os.makedirs(os.path.dirname(DOCS_HTML_PATH) or ".", exist_ok=True)
        write_html(DOCS_HTML_PATH, html_results, generated_at=now_utc)
        snapshot_path = write_unique_scan_snapshot(scan_id, html_results, generated_at=now_utc)
        logger.info("Wrote HTML dashboard to %s and unique snapshot to %s", DOCS_HTML_PATH, snapshot_path)
    except OSError as exc:
        logger.warning("Failed to write HTML dashboard: %s", exc)

    summary_text = build_daily_summary_text(html_results, scan_id=scan_id, generated_at=now_utc)

    if prepare_telegram_path:
        with open(prepare_telegram_path, "w", encoding="utf-8") as f:
            f.write(summary_text)
        logger.info("Prepared Telegram summary with unique links at %s", prepare_telegram_path)
    elif dry_run:
        logger.info("DRY RUN — prepared summary:\n%s", summary_text)
    else:
        send_message(summary_text)

    return messages


if __name__ == "__main__":
    if "--send-prepared" in sys.argv:
        idx = sys.argv.index("--send-prepared")
        msg_file = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "/tmp/polybet_telegram_msg.txt"
        if os.path.isfile(msg_file):
            with open(msg_file, encoding="utf-8") as f:
                content = f.read()
            ok = send_message(content)
            sys.exit(0 if ok else 1)
        sys.exit(0)

    prep_file = None
    if "--prepare-telegram" in sys.argv:
        idx = sys.argv.index("--prepare-telegram")
        prep_file = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "/tmp/polybet_telegram_msg.txt"

    run(prepare_telegram_path=prep_file)
