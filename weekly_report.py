"""
weekly_report.py — PolyBet v2.0 Resolution & Self-Healing Cache Auditor (Zero-Config Unique GitHub Links).

REPLACES your current weekly_report.py.

KEY FEATURES & FIXES IN THIS VERSION:
1. ZERO-CONFIG UNIQUE GITHUB LINKS PER WEEKLY REPORT:
   You do NOT need to configure `DASHBOARD_URL`!
   Automatically detects `owner/repo` from GitHub Actions (`GITHUB_REPOSITORY`)
   or local `git remote`, saves a permanent timestamped snapshot
   `docs/scans/results-<YYYYMMDD-HHMMSS>.html` alongside `docs/results.html`,
   and includes both the instant web preview link (`htmlpreview.github.io`)
   and the GitHub Pages link in every Telegram report.
2. FIX BUG #1 (Self-Healing for Single-Market Binary Events):
   Automatically repairs cached rows where `primary_outcome.lower() == title.lower()`
   and `resolved_outcome in ("Yes", "No")`.
3. FIX BUG #7 (Cumulative "By Date" Multi-Market Resolution):
   Immediately resolves date-specific sub-markets that settled `"No"`.
"""

from __future__ import annotations

import csv
import glob
import json
import logging
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

from results_html_generator import build_results_html, write_results_html
from telegram_bot import send_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GAMMA_EVENTS_ENDPOINT = "https://gamma-api.polymarket.com/events"
REQUEST_TIMEOUT_SECONDS = 15
RESOLVED_PRICE_THRESHOLD = 0.99
DEBUG_RESOLUTION = os.getenv("DEBUG_RESOLUTION", "false").lower() == "true"
REBUILD_RESOLVED_CACHE = os.getenv("REBUILD_RESOLVED_CACHE", "false").lower() == "true"

PREDICTIONS_LOG_PATH = os.getenv("PREDICTIONS_LOG_PATH", "predictions_log.csv")
PREDICTIONS_RESOLVED_PATH = os.getenv("PREDICTIONS_RESOLVED_PATH", "predictions_resolved.csv")
RESULTS_HTML_PATH = os.getenv("RESULTS_HTML_PATH", "docs/results.html")
SCANS_ARCHIVE_DIR = os.getenv("SCANS_ARCHIVE_DIR", "docs/scans")
MAX_ARCHIVED_REPORTS = 30

RESOLVED_FIELDS = [
    "group_key", "title", "category", "logged_at_utc", "market_url",
    "primary_outcome", "primary_size_pct", "primary_market_price",
    "resolved_outcome", "is_correct", "checked_at_utc",
]

REPORT_TITLES = {
    "scheduled": "📈 *گزارش هفتگی و بک‌تست PolyBet Quant v2.0*",
    "telegram_button": "🔘 *نتایج نهایی PolyBet Quant v2.0 (به‌درخواست شما)*",
}


def detect_github_repo() -> tuple[str, str]:
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


def build_unique_results_urls(report_id: str) -> dict[str, str]:
    explicit_base = (os.getenv("DASHBOARD_URL") or "").strip().rstrip("/")
    gh_repo, branch = detect_github_repo()

    urls: dict[str, str] = {}
    if gh_repo and "/" in gh_repo:
        owner, repo = gh_repo.split("/", 1)
        pages_base = explicit_base or f"https://{owner}.github.io/{repo}"
        raw_blob_url = f"https://github.com/{owner}/{repo}/blob/{branch}/docs/scans/results-{report_id}.html"
        urls["instant_preview_url"] = f"https://htmlpreview.github.io/?{raw_blob_url}"
        urls["unique_pages_url"] = f"{pages_base}/scans/results-{report_id}.html"
        urls["live_results_url"] = f"{pages_base}/results.html?run={report_id}"
    elif explicit_base:
        urls["unique_pages_url"] = f"{explicit_base}/scans/results-{report_id}.html"
        urls["live_results_url"] = f"{explicit_base}/results.html?run={report_id}"

    return urls


def write_unique_results_snapshot(
    report_id: str,
    resolved_rows: list[dict],
    generated_at: datetime,
    log_by_key: dict[str, dict] | None = None,
) -> str:
    os.makedirs(SCANS_ARCHIVE_DIR, exist_ok=True)
    snapshot_path = os.path.join(SCANS_ARCHIVE_DIR, f"results-{report_id}.html")
    content = build_results_html(resolved_rows, generated_at=generated_at, log_by_key=log_by_key)
    content_adjusted = content.replace('href="index.html"', 'href="../index.html"').replace(
        'href="results.html"', 'href="../results.html"'
    )
    with open(snapshot_path, "w", encoding="utf-8") as f:
        f.write(content_adjusted)

    existing = sorted(glob.glob(os.path.join(SCANS_ARCHIVE_DIR, "results-*.html")))
    if len(existing) > MAX_ARCHIVED_REPORTS:
        for old_file in existing[:-MAX_ARCHIVED_REPORTS]:
            try:
                os.remove(old_file)
            except OSError:
                pass
    return snapshot_path


def load_predictions_log(path: str) -> list[dict]:
    if not os.path.isfile(path):
        logger.warning("predictions_log.csv not found at %s -- nothing to report yet.", path)
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def dedupe_by_market(log_rows: list[dict]) -> list[dict]:
    earliest: dict[str, dict] = {}
    for row in log_rows:
        key = row.get("group_key", "")
        if not key:
            continue
        existing = earliest.get(key)
        if existing is None or (row.get("logged_at_utc", "") < existing.get("logged_at_utc", "")):
            earliest[key] = row
    return list(earliest.values())


def _repair_binary_cache_row(row: dict) -> dict:
    """Self-heal cached rows in predictions_resolved.csv affected by Bug #1."""
    title = (row.get("title") or "").strip()
    primary = (row.get("primary_outcome") or "").strip()
    resolved = (row.get("resolved_outcome") or "").strip()
    if title and primary.lower() == title.lower():
        row["primary_outcome"] = "Yes"
        if resolved.lower() in ("yes", "no"):
            row["is_correct"] = str(resolved.lower() == "yes")
    return row


def load_resolved_cache(path: str) -> dict[str, dict]:
    if REBUILD_RESOLVED_CACHE or not os.path.isfile(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cache: dict[str, dict] = {}
    for r in rows:
        key = r.get("group_key", "")
        if key:
            cache[key] = _repair_binary_cache_row(r)
    return cache


def slug_from_url(url: str) -> str | None:
    if not url:
        return None
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    return parts[-1] if parts else None


def _parse_json_field(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []
    return []


def _parse_outcomes(market: dict) -> tuple[list[str], list[float]]:
    outcomes = _parse_json_field(market.get("outcomes"))
    prices_raw = _parse_json_field(market.get("outcomePrices"))
    try:
        prices = [float(p) for p in prices_raw]
    except (TypeError, ValueError):
        prices = []
    if not outcomes or not prices or len(outcomes) != len(prices):
        return [], []
    return outcomes, prices


def fetch_event_markets(slug: str, session: requests.Session) -> list[dict] | None:
    try:
        resp = session.get(GAMMA_EVENTS_ENDPOINT, params={"slug": slug}, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Could not fetch event for slug=%s: %s", slug, exc)
        return None

    events = data if isinstance(data, list) else data.get("data", [])
    if not events:
        return None
    return events[0].get("markets", [])


def resolve_single_prediction(
    slug: str, primary_outcome: str, title: str, session: requests.Session
) -> tuple[str | None, bool | None, bool]:
    sub_markets = fetch_event_markets(slug, session)
    if not sub_markets:
        return None, None, False

    any_closed = any(m.get("closed") for m in sub_markets)
    if not any_closed:
        return None, None, False

    primary_norm = (primary_outcome or "").strip().lower()
    title_norm = (title or "").strip().lower()

    if len(sub_markets) == 1:
        effective_primary = "yes" if primary_norm == title_norm else primary_norm
        outcomes, prices = _parse_outcomes(sub_markets[0])
        for outcome, price in zip(outcomes, prices):
            if price >= RESOLVED_PRICE_THRESHOLD:
                settled = outcome.strip()
                return settled, settled.lower() == effective_primary, True
        return None, None, True

    for market in sub_markets:
        outcomes, prices = _parse_outcomes(market)
        label = (market.get("groupItemTitle") or market.get("question") or "").strip()
        for outcome, price in zip(outcomes, prices):
            if price >= RESOLVED_PRICE_THRESHOLD and outcome.strip().lower() == "yes":
                if not label:
                    label = primary_outcome.strip()
                is_correct = label.strip().lower() == primary_norm
                return label, is_correct, True
            if (
                market.get("closed")
                and price >= RESOLVED_PRICE_THRESHOLD
                and outcome.strip().lower() == "no"
                and label.strip().lower() == primary_norm
            ):
                return f"Not {label}", False, True

    return None, None, True


def resolve_predictions(log_rows: list[dict], cache: dict[str, dict]) -> list[dict]:
    session = requests.Session()
    resolved: list[dict] = []

    for row in log_rows:
        key = row.get("group_key", "")
        cached = cache.get(key)
        if cached and cached.get("is_correct") in ("True", "False"):
            resolved.append(_repair_binary_cache_row(cached))
            continue

        title = row.get("title", "")
        raw_primary = row.get("primary_outcome", "")
        clean_primary = "Yes" if raw_primary.strip().lower() == title.strip().lower() else raw_primary

        base = {
            "group_key": key,
            "title": title,
            "category": row.get("category", ""),
            "logged_at_utc": row.get("logged_at_utc", ""),
            "market_url": row.get("market_url", ""),
            "primary_outcome": clean_primary,
            "primary_size_pct": row.get("primary_size_pct", ""),
            "primary_market_price": row.get("primary_market_price", ""),
        }

        slug = slug_from_url(row.get("market_url", ""))
        if not slug:
            resolved.append({**base, "resolved_outcome": "", "is_correct": "", "checked_at_utc": datetime.now(timezone.utc).isoformat()})
            continue

        winner, is_correct, _any_closed = resolve_single_prediction(slug, clean_primary, title, session)
        resolved.append({
            **base,
            "resolved_outcome": winner or "",
            "is_correct": "" if is_correct is None else str(is_correct),
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        })

    return resolved


def write_resolved_cache(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESOLVED_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in RESOLVED_FIELDS})


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def build_weekly_stats(resolved_rows: list[dict], since: datetime) -> dict:
    this_week = [r for r in resolved_rows if _parse_ts(r["logged_at_utc"]) and _parse_ts(r["logged_at_utc"]) >= since]
    target_rows = this_week if this_week else resolved_rows
    total = len(target_rows)
    decided = [r for r in target_rows if r["is_correct"] in ("True", "False")]
    correct = [r for r in decided if r["is_correct"] == "True"]
    pending = total - len(decided)

    by_category: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in decided:
        by_category[r["category"]][1] += 1
        if r["is_correct"] == "True":
            by_category[r["category"]][0] += 1

    return {
        "total": total,
        "decided": len(decided),
        "correct": len(correct),
        "pending": pending,
        "success_rate": (len(correct) / len(decided) * 100.0) if decided else None,
        "by_category": dict(by_category),
        "is_all_time_fallback": len(this_week) == 0,
    }


def format_weekly_report(stats: dict, report_id: str, trigger_source: str = "scheduled") -> str:
    header = REPORT_TITLES.get(trigger_source, REPORT_TITLES["scheduled"])
    scope_label = "کل تاریخچه" if stats.get("is_all_time_fallback") else "۷ روز اخیر"
    urls = build_unique_results_urls(report_id)

    lines = [header, f"🆔 شناسه گزارش: `{report_id}`", ""]
    lines.append(f"🔢 سیگنال‌های بررسی‌شده ({scope_label}): {stats['total']}")
    lines.append(f"✅ نتیجه‌ی نهایی مشخص شده: {stats['decided']}")
    lines.append(f"⏳ هنوز در انتظار نتیجه: {stats['pending']}")
    if stats["success_rate"] is not None:
        lines.append(f"🎯 درصد موفقیت (از میان نتیجه‌دارها): *{stats['success_rate']:.1f}%* ({stats['correct']}/{stats['decided']})")
    else:
        lines.append("🎯 هنوز هیچ سیگنالی نتیجه‌ی نهایی نگرفته -- بعداً دوباره چک می‌شود.")

    if stats["by_category"]:
        lines.append("")
        lines.append(f"📊 تفکیک بر اساس دسته ({scope_label}):")
        for category, (correct, total) in sorted(stats["by_category"].items(), key=lambda kv: -kv[1][1]):
            rate = (correct / total * 100.0) if total else 0.0
            clean_cat = (category or "other").replace("_", " ")
            lines.append(f"  • {clean_cat}: {correct}/{total} ({rate:.0f}%)")

    if urls.get("instant_preview_url"):
        lines.append("")
        lines.append(f"⚡ مشاهده فوری جدول کامل این گزارش (بدون نیاز به تنظیمات):\n{urls['instant_preview_url']}")
    if urls.get("unique_pages_url"):
        lines.append("")
        lines.append(f"🌐 لینک یکتای GitHub Pages این گزارش:\n{urls['unique_pages_url']}")
    if urls.get("live_results_url"):
        lines.append("")
        lines.append(f"📄 جدول اصلی نتایج:\n{urls['live_results_url']}")

    return "\n".join(lines)


def run(dry_run: bool = False, prepare_telegram_path: str | None = None) -> str:
    load_dotenv()
    trigger_source = os.getenv("TRIGGER_SOURCE", "scheduled")
    now_utc = datetime.now(timezone.utc)
    report_id = now_utc.strftime("%Y%m%d-%H%M%S")

    raw_log_rows = load_predictions_log(PREDICTIONS_LOG_PATH)
    if not raw_log_rows:
        message = "📈 گزارش PolyBet: هنوز هیچ سیگنالی در predictions_log.csv ثبت نشده."
        if prepare_telegram_path:
            with open(prepare_telegram_path, "w", encoding="utf-8") as f:
                f.write(message)
        elif not dry_run:
            send_message(message)
        else:
            print(message)
        return message

    log_rows = dedupe_by_market(raw_log_rows)
    log_by_key = {r.get("group_key", ""): r for r in log_rows if r.get("group_key")}
    logger.info("Deduped %d logged rows down to %d unique markets.", len(raw_log_rows), len(log_rows))

    cache = load_resolved_cache(PREDICTIONS_RESOLVED_PATH)
    resolved_rows = resolve_predictions(log_rows, cache)
    write_resolved_cache(PREDICTIONS_RESOLVED_PATH, resolved_rows)

    try:
        os.makedirs(os.path.dirname(RESULTS_HTML_PATH) or ".", exist_ok=True)
        write_results_html(RESULTS_HTML_PATH, resolved_rows, generated_at=now_utc, log_by_key=log_by_key)
        snapshot_path = write_unique_results_snapshot(
            report_id, resolved_rows, generated_at=now_utc, log_by_key=log_by_key
        )
        logger.info("Wrote results dashboard to %s and unique snapshot to %s", RESULTS_HTML_PATH, snapshot_path)
    except OSError as exc:
        logger.warning("Failed to write results dashboard: %s", exc)

    since = now_utc - timedelta(days=7)
    stats = build_weekly_stats(resolved_rows, since)
    report = format_weekly_report(stats, report_id=report_id, trigger_source=trigger_source)

    if prepare_telegram_path:
        with open(prepare_telegram_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info("Prepared weekly Telegram report at %s", prepare_telegram_path)
    elif dry_run:
        print(report)
    else:
        ok = send_message(report)
        if not ok:
            logger.warning("Failed to send report to Telegram.")
    return report


if __name__ == "__main__":
    if "--send-prepared" in sys.argv:
        idx = sys.argv.index("--send-prepared")
        msg_file = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "/tmp/polybet_weekly_msg.txt"
        if os.path.isfile(msg_file):
            with open(msg_file, encoding="utf-8") as f:
                content = f.read()
            ok = send_message(content)
            sys.exit(0 if ok else 1)
        sys.exit(0)

    prep_file = None
    if "--prepare-telegram" in sys.argv:
        idx = sys.argv.index("--prepare-telegram")
        prep_file = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "/tmp/polybet_weekly_msg.txt"

    run(dry_run="--dry-run" in sys.argv, prepare_telegram_path=prep_file)
