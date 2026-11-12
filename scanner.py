"""
scanner.py — PolyBet v2.0 Deep Multi-Pass Market Scanner & Classifier.

UPGRADES IN THIS VERSION:
1. Deep 3-Pass Polymarket Gamma Scan:
   - Pass 1: Top active markets ordered by 24h Volume (`order=volume24hr&ascending=false`)
   - Pass 2: Top active markets ordered by Liquidity (`order=liquidityNum&ascending=false`)
   - Pass 3: Date-window sweep (`end_date_min` .. `end_date_max`)
   This avoids Polymarket's offset=2100 HTTP 422 wall where un-ordered queries returned
   98% low-volume soccer props and missed major Fed, CPI, Stocks, and Crypto markets.
2. Filters out 5-minute/15-minute "Up or Down" coin-flip noise and dead ($0 volume) markets.
3. Expands default resolve window to 21 days so flagship Fed/CPI/Earnings events are included.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import requests

logger = logging.getLogger(__name__)

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
MARKETS_ENDPOINT = f"{GAMMA_API_BASE}/markets"
DEFAULT_RESOLVE_WINDOW_DAYS = 21
DEFAULT_PAGE_LIMIT = 100
DEFAULT_MAX_PAGES = 15
REQUEST_TIMEOUT_SECONDS = 15
MAX_FETCH_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 2
MIN_MARKET_VOLUME_USD = 300.0

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fed": ("fed", "federal reserve", "fomc", "jerome powell", "fed rate", "interest rate", "rate cut", "rate hike"),
    "cpi": ("cpi", "inflation", "consumer price index"),
    "pce": ("pce", "personal consumption expenditures", "core pce"),
    "employment": ("unemployment", "nonfarm", "payroll", "jobs report", "jobless"),
    "gdp": ("gdp", "gross domestic product", "recession", "economic growth"),
    "ecb": ("ecb", "european central bank", "christine lagarde", "eurozone rate"),
    "boc": ("bank of canada", "boc rate", "boc decision", "tiff macklem"),
    "boe": ("bank of england", "boe rate", "boe decision", "mpc vote", "andrew bailey"),
    "central_banks_other": (
        "bank of korea", "boj", "bank of japan", "reserve bank of australia",
        "rba rate", "reserve bank of new zealand", "rbnz", "snb",
        "swiss national bank", "pboc", "people's bank of china",
        "bank of mexico", "banxico", "sarb", "south african reserve bank",
    ),
    "stocks": (
        "s&p", "nasdaq", "dow jones", "stock", "equity", "earnings",
        "quarterly earnings", "eps", "revenue", "market cap", "nvda", "nvidia",
        "apple", "aapl", "tesla", "tsla", "microsoft", "msft", "amazon", "amzn",
        "google", "alphabet", "meta", "palantir", "pltr",
    ),
    "commodities": ("oil", "gold", "silver", "crude", "opec", "commodity", "natural gas", "wti", "brent"),
    "elections": (
        "election", "president", "presidential", "senate", "congress", "governor",
        "mayor", "parliament", "prime minister", "chancellor", "nominee", "approval rating",
    ),
    "crypto": ("bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp", "crypto", "fdv", "airdrop"),
}
DEFAULT_CATEGORY = "other"
ROADMAP_DOMAINS: frozenset[str] = frozenset(CATEGORY_KEYWORDS.keys())

SPORTS_SIGNALS: tuple[str, ...] = (
    "medal", "olympic", "olympics", "tournament", "championship",
    "playoffs", "playoff", "world cup", "super bowl", "grand slam",
    "final four", "world series", "stanley cup", "nba", "nfl", "mlb",
    "nhl", "ufc", "boxing", "wrestlemania", "grand prix", "match",
    "vs.", "vs ", "wins the game", "wins the match", "fight card",
    "pro football", "starting qb", "touchdown", "premier league",
    "champions league", "la liga", "serie a", "bundesliga", "mvp",
    "dota", "counter-strike", "valorant", "league of legends", "esports",
    "halftime", "exact score", "fc ", " cf ", "united fc", "city fc",
    "formula 1", "f1 ", "nascar", "pga", "tennis", "atp", "wta", "cricket",
)

AMBIGUOUS_COMMODITY_KEYWORDS: frozenset[str] = frozenset({"gold", "silver"})
PRICE_CONTEXT_SIGNALS: tuple[str, ...] = (
    "price", "xau", "xag", "ounce", "$", "hit high", "hit low", "per ounce", "above", "below", "close",
)

TRUMP_BEHAVIOR_VERBS: tuple[str, ...] = (
    "insult", "mention", "tweet", "post", "say", "says", "said", "name",
    "named", "fire", "call", "publicly",
)


def word_in_text(keyword: str, text: str) -> bool:
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return re.search(pattern, text) is not None


def is_sports_market(haystack: str) -> bool:
    for sig in SPORTS_SIGNALS:
        stripped = sig.strip()
        if "." in stripped or " " in stripped:
            if stripped in haystack:
                return True
        elif word_in_text(stripped, haystack):
            return True
    return False


def is_trump_behavior_market(haystack: str) -> bool:
    if "leavitt" in haystack:
        return True
    if "trump" not in haystack:
        return False
    return any(word_in_text(verb, haystack) for verb in TRUMP_BEHAVIOR_VERBS)


def is_micro_timeframe_noise(haystack: str) -> bool:
    """Filter out 5-minute / 15-minute 'Bitcoin Up or Down - 2:00PM-2:15PM ET' coin-flip noise."""
    if "up or down" in haystack and ("et" in haystack or "am" in haystack or "pm" in haystack):
        return True
    if re.search(r"\b\d{1,2}:\d{2}\s*(?:am|pm)\s*-\s*\d{1,2}:\d{2}\s*(?:am|pm)\b", haystack):
        return True
    return False


def is_price_hit_gap_market(haystack: str) -> bool:
    return bool(re.search(r"[↑↓]\s*\$?[\d,]+", haystack))


def categorize_market(question: str, tags: Iterable[str], event_title: str = "") -> str:
    haystack = " ".join([question or ""] + [t or "" for t in tags] + [event_title or ""]).lower()

    if is_trump_behavior_market(haystack):
        return DEFAULT_CATEGORY
    if is_sports_market(haystack):
        return DEFAULT_CATEGORY
    if is_micro_timeframe_noise(haystack):
        return DEFAULT_CATEGORY

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if not word_in_text(kw, haystack):
                continue
            if category == "commodities" and kw in AMBIGUOUS_COMMODITY_KEYWORDS:
                if not any(ctx in haystack for ctx in PRICE_CONTEXT_SIGNALS):
                    continue
            if category in {"stocks", "commodities", "crypto"} and is_price_hit_gap_market(haystack):
                return DEFAULT_CATEGORY
            return category
    return DEFAULT_CATEGORY


@dataclass
class ScannedMarket:
    market_id: str
    question: str
    slug: str
    end_date: datetime
    category: str
    tags: list[str] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)
    outcome_prices: list[float] = field(default_factory=list)
    volume: float = 0.0
    liquidity: float = 0.0
    url: str = ""
    group_label: str = ""
    event_title: str = ""

    @property
    def days_to_resolve(self) -> float:
        now = datetime.now(timezone.utc)
        return (self.end_date - now).total_seconds() / 86400.0

    @property
    def is_grouped(self) -> bool:
        return bool(self.group_label)


def parse_end_date(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        text = str(raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def parse_float_list(raw: Any) -> list[float]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if isinstance(raw, list):
        out = []
        for v in raw:
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                continue
        return out
    return []


def parse_str_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except json.JSONDecodeError:
            return [raw] if raw else []
    if isinstance(raw, list):
        return [str(v) for v in raw]
    return []


def resolve_public_slug(raw_market: dict[str, Any]) -> str:
    events = raw_market.get("events")
    if isinstance(events, list) and events:
        event_slug = events[0].get("slug") if isinstance(events[0], dict) else None
        if event_slug:
            return event_slug
    return raw_market.get("slug") or ""


def resolve_group_metadata(raw_market: dict[str, Any], question: str) -> tuple[str, str]:
    group_label = (raw_market.get("groupItemTitle") or "").strip()
    events = raw_market.get("events")
    event_title = ""
    if isinstance(events, list) and events and isinstance(events[0], dict):
        event_title = (events[0].get("title") or "").strip()
    return group_label, event_title


def parse_market(raw_market: dict[str, Any]) -> ScannedMarket | None:
    end_date = parse_end_date(raw_market.get("endDate"))
    if end_date is None:
        return None

    market_id = str(raw_market.get("id") or raw_market.get("conditionId") or "")
    question = raw_market.get("question") or raw_market.get("title") or ""
    slug = raw_market.get("slug") or ""
    if not market_id or not question:
        return None

    tags_field = raw_market.get("tags")
    if isinstance(tags_field, list) and tags_field and isinstance(tags_field[0], dict):
        tags = [t.get("label") or t.get("slug") or "" for t in tags_field]
    else:
        tags = parse_str_list(tags_field)

    group_label, event_title = resolve_group_metadata(raw_market, question)
    category = categorize_market(question, tags, event_title)

    outcomes = parse_str_list(raw_market.get("outcomes"))
    outcome_prices = parse_float_list(raw_market.get("outcomePrices"))
    volume = float(raw_market.get("volume") or raw_market.get("volumeNum") or 0.0)
    liquidity = float(raw_market.get("liquidity") or raw_market.get("liquidityNum") or 0.0)

    public_slug = resolve_public_slug(raw_market)
    url = f"https://polymarket.com/event/{public_slug}" if public_slug else ""

    return ScannedMarket(
        market_id=market_id,
        question=question,
        slug=slug,
        end_date=end_date,
        category=category,
        tags=[t for t in tags if t],
        outcomes=outcomes,
        outcome_prices=outcome_prices,
        volume=volume,
        liquidity=liquidity,
        url=url,
        group_label=group_label,
        event_title=event_title,
    )


def filter_by_resolve_window(
    markets: Iterable[ScannedMarket],
    window_days: float = DEFAULT_RESOLVE_WINDOW_DAYS,
    now: datetime | None = None,
) -> list[ScannedMarket]:
    now = now or datetime.now(timezone.utc)
    cutoff = now + timedelta(days=window_days)
    # Require at least 1 hour remaining and minimum volume/liquidity so dead 5-min markets are excluded
    min_end = now + timedelta(hours=1)
    return [
        m for m in markets
        if min_end <= m.end_date <= cutoff and (m.volume >= MIN_MARKET_VOLUME_USD or m.liquidity >= 150.0)
    ]


def filter_to_roadmap_domains(markets: Iterable[ScannedMarket]) -> list[ScannedMarket]:
    return [m for m in markets if m.category in ROADMAP_DOMAINS]


def _request_with_retry(sess: requests.Session, url: str, params: dict[str, Any]) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        try:
            resp = sess.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code >= 500:
                raise requests.exceptions.HTTPError(f"Server error {resp.status_code}", response=resp)
            return resp
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError) as exc:
            last_exc = exc
            if attempt == MAX_FETCH_RETRIES:
                break
            wait_seconds = RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "Request to %s failed (attempt %d/%d): %s -- retrying in %ds",
                url, attempt, MAX_FETCH_RETRIES, exc, wait_seconds,
            )
            time.sleep(wait_seconds)
    assert last_exc is not None
    raise last_exc


def fetch_raw_markets_page(
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = 0,
    active: bool = True,
    closed: bool = False,
    end_date_min: str | None = None,
    end_date_max: str | None = None,
    order: str | None = None,
    ascending: bool | None = None,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    sess = session or requests.Session()
    params: dict[str, Any] = {
        "limit": limit,
        "offset": offset,
        "active": str(active).lower(),
        "closed": str(closed).lower(),
    }
    if end_date_min:
        params["end_date_min"] = end_date_min
    if end_date_max:
        params["end_date_max"] = end_date_max
    if order:
        params["order"] = order
    if ascending is not None:
        params["ascending"] = str(ascending).lower()

    resp = _request_with_retry(sess, MARKETS_ENDPOINT, params)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    if isinstance(data, list):
        return data
    return []


def fetch_all_raw_markets(
    page_limit: int = DEFAULT_PAGE_LIMIT,
    active: bool = True,
    closed: bool = False,
    max_pages: int = DEFAULT_MAX_PAGES,
    end_date_min: str | None = None,
    end_date_max: str | None = None,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """Multi-pass deep scanner:
    Pass 1: Top markets by 24h trading volume (captures major Fed, CPI, Stocks, Elections, Crypto).
    Pass 2: Top markets by Orderbook Liquidity.
    Pass 3: Date-bounded sweep for upcoming events.
    """
    sess = session or requests.Session()
    seen_ids: set[str] = set()
    all_markets: list[dict[str, Any]] = []

    passes = [
        {"order": "volume24hr", "ascending": False, "use_dates": False, "pages": 12},
        {"order": "liquidityNum", "ascending": False, "use_dates": False, "pages": 10},
        {"order": None, "ascending": None, "use_dates": True, "pages": max_pages},
    ]

    for p in passes:
        offset = 0
        for _ in range(int(p["pages"])):
            try:
                page = fetch_raw_markets_page(
                    limit=page_limit,
                    offset=offset,
                    active=active,
                    closed=closed,
                    end_date_min=end_date_min if p["use_dates"] else None,
                    end_date_max=end_date_max if p["use_dates"] else None,
                    order=p["order"],
                    ascending=p["ascending"],
                    session=sess,
                )
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status in (400, 406, 422):
                    break
                raise
            if not page:
                break
            for item in page:
                mid = str(item.get("id") or item.get("conditionId") or "")
                if mid and mid not in seen_ids:
                    seen_ids.add(mid)
                    all_markets.append(item)
            offset += len(page)

    return all_markets


def scan_markets(
    window_days: float = DEFAULT_RESOLVE_WINDOW_DAYS,
    raw_markets: list[dict[str, Any]] | None = None,
    exclude_other: bool = True,
) -> list[ScannedMarket]:
    if raw_markets is not None:
        raw = raw_markets
    else:
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=window_days)
        raw = fetch_all_raw_markets(
            end_date_min=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            end_date_max=cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    parsed = [m for m in (parse_market(r) for r in raw) if m is not None]
    filtered = filter_by_resolve_window(parsed, window_days=window_days)
    if exclude_other:
        filtered = filter_to_roadmap_domains(filtered)
    filtered.sort(key=lambda m: m.end_date)
    return filtered


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for m in scan_markets():
        print(f"[{m.category}] {m.question} (resolves in {m.days_to_resolve:.1f}d) {m.url}")
