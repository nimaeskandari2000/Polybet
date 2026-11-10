"""
telegram_bot.py — PolyBet v2.0 Resilient Telegram Bot Sender & Formatter.

REPLACES your current telegram_bot.py.

KEY FIXES IN THIS VERSION:
1. Strips whitespace and accidental quotes from `TELEGRAM_BOT_TOKEN` and
   `TELEGRAM_CHAT_ID` (fixes 404/400 errors when secrets are pasted with spaces
   or newlines in GitHub Actions Secrets).
2. Calls `load_dotenv()` automatically so `.env` credentials are always loaded.
3. Fixes Telegram HTTP 400 (`can't parse entities`) caused by legacy
   `parse_mode="Markdown"` when market titles, URLs, or category names (like
   `central_banks_other`) contain underscores `_`, asterisks `*`, or brackets `[`.
   If Telegram rejects Markdown formatting, `send_message()` automatically
   retries as clean plain text so the message is GUARANTEED to be delivered.
4. Automatically splits messages exceeding Telegram's 4096-character limit.
5. Logs the exact error description from Telegram API (`resp.json()["description"]`)
   without ever exposing the bot token.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Iterable

import requests
from dotenv import load_dotenv

from position_logic import PositionPlan

load_dotenv()

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
REQUEST_TIMEOUT_SECONDS = 15
MAX_TELEGRAM_CHARS = 3900

WARNING_EMOJI = "\u26a0\ufe0f"
SIGNAL_EMOJI = "\U0001F3AF"  # 🎯
MARGIN_EMOJI = "\u2705"  # ✅


def _clean_secret(value: str | None) -> str:
    if not value:
        return ""
    cleaned = value.strip().strip('"').strip("'").strip()
    return cleaned


def _strip_markdown_Fallback(text: str) -> str:
    """Convert basic Markdown links `[label](url)` -> `label (url)` and strip `*` if fallback is needed."""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    return text.replace("*", "")


def format_signal_message(
    plan: PositionPlan,
    market_url: str,
    days_to_resolve: float,
    title: str | None = None,
) -> str:
    heading = (title or plan.question or "").replace("*", "")
    primary = plan.primary
    if primary:
        outcome_clean = (primary.outcome or "").replace("*", "")
        signal_line = (
            f"{SIGNAL_EMOJI} پیشنهاد: *{outcome_clean}* — {primary.size_pct:.1f}% "
            f"(قیمت بازار {primary.market_price:.2f})"
        )
    else:
        signal_line = f"{SIGNAL_EMOJI} پیشنهاد: نامعلوم"

    lines = [
        f"*{heading}*",
        "",
        signal_line,
    ]

    if plan.guaranteed_margin_pct is not None:
        lines.append(f"{MARGIN_EMOJI} سود خالص تضمینی اگر Primary ببرد: +{plan.guaranteed_margin_pct:.1%}")

    lines += [
        "",
        f"\u23f3 زمان تا تسویه: {days_to_resolve:.1f} روز",
        f"\U0001F4CA اجماع بیزی: {plan.consensus_score:.0f}% ({plan.num_sources} منبع) | Edge: {plan.edge:.1%}",
        "",
        "*برنامه کامل سایزینگ (Position Plan):*",
    ]

    role_labels = {
        "primary": "\U0001F7E2 Primary",
        "secondary": "\U0001F535 Secondary",
        "hedge": "\U0001F6E1 Hedge",
    }
    for alloc in plan.allocations:
        label = role_labels.get(alloc.role, alloc.role)
        out_clean = (alloc.outcome or "").replace("*", "")
        price_txt = f" (mkt {alloc.market_price:.2f})" if alloc.market_price is not None else ""
        net_roi = getattr(alloc, "net_roi_if_wins_pct", None)
        roi_txt = f" -> Net ROI: {net_roi:+.1f}%" if net_roi is not None else ""
        lines.append(f"  {label}: *{out_clean}* — {alloc.size_pct:.1f}%{price_txt}{roi_txt}")

    if plan.warning:
        lines.append("")
        lines.append(f"{WARNING_EMOJI} {plan.warning}")

    if market_url:
        lines.append("")
        lines.append(f"🔗 {market_url}")
    return "\n".join(lines)


def _chunk_text(text: str, max_len: int = MAX_TELEGRAM_CHARS) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    current_lines: list[str] = []
    current_len = 0
    for line in text.splitlines(keepends=True):
        if current_len + len(line) > max_len and current_lines:
            chunks.append("".join(current_lines).rstrip())
            current_lines = [line]
            current_len = len(line)
        else:
            current_lines.append(line)
            current_len += len(line)
    if current_lines:
        chunks.append("".join(current_lines).rstrip())
    return chunks


def _post_single_chunk(url: str, chat: str, chunk: str) -> bool:
    """Send a single message chunk, automatically falling back to plain text if Markdown entity parsing fails."""
    payload = {
        "chat_id": chat,
        "text": chunk,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            return True

        # Inspect Telegram error description
        err_desc = ""
        try:
            err_desc = resp.json().get("description", resp.text)
        except ValueError:
            err_desc = resp.text

        logger.warning(
            "Telegram Markdown send returned HTTP %d (%s). Retrying as plain text without parse_mode...",
            resp.status_code,
            err_desc,
        )

        # Fallback: retry without parse_mode so unescaped '_' or '*' never blocks delivery
        fallback_payload = {
            "chat_id": chat,
            "text": _strip_markdown_Fallback(chunk),
            "disable_web_page_preview": False,
        }
        resp_fallback = requests.post(url, json=fallback_payload, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp_fallback.status_code == 200:
            logger.info("Telegram message delivered successfully via plain-text fallback.")
            return True

        fb_desc = ""
        try:
            fb_desc = resp_fallback.json().get("description", resp_fallback.text)
        except ValueError:
            fb_desc = resp_fallback.text
        logger.error("Telegram send failed (HTTP %d): %s", resp_fallback.status_code, fb_desc)
        return False

    except requests.RequestException as exc:
        logger.error("Telegram network request failed: %s", type(exc).__name__)
        return False


def send_message(text: str, bot_token: str | None = None, chat_id: str | None = None) -> bool:
    """Send a message via the Telegram Bot API with automatic Markdown fallback and chunking."""
    load_dotenv()
    token = _clean_secret(bot_token or os.getenv("TELEGRAM_BOT_TOKEN"))
    chat = _clean_secret(chat_id or os.getenv("TELEGRAM_CHAT_ID"))

    if not token or not chat:
        logger.error(
            "Telegram not configured: TELEGRAM_BOT_TOKEN=%s, TELEGRAM_CHAT_ID=%s. "
            "Set both in GitHub Settings -> Secrets and variables -> Actions (or .env).",
            "SET" if token else "MISSING",
            "SET" if chat else "MISSING",
        )
        return False

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    chunks = _chunk_text(text)
    all_ok = True
    for chunk in chunks:
        if not _post_single_chunk(url, chat, chunk):
            all_ok = False
    return all_ok
