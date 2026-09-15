"""
Forex (FX) Market Data Client — Twelve Data (primary) + Yahoo Finance (fallback).

Normalizes Forex OHLC data into the exact candle format used by binance_client.py
({time, open, high, low, close, volume, close_time}) so the shared indicator engine,
strategy engine, charting layer and dashboard UI work unchanged for both asset classes.

Features
- 28+ currency pairs grouped into majors / minors / exotics
- Twelve Data primary feed (free key: https://twelvedata.com) with automatic
  Yahoo Finance fallback when the key is missing, the request budget is spent,
  or the provider errors/rate-limits
- Built-in request throttle so the Twelve Data free tier (8 req/min, 800/day)
  is never exceeded — requests that would block too long are routed to Yahoo
- Forex market-hours + session detection (Sydney / Tokyo / London / New York)
- Pip helpers (4th / 2nd decimal) shared by the strategy engine, notifier and UI
"""

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# PROVIDER ENDPOINTS
# =============================================================================
TWELVE_DATA_BASE = "https://api.twelvedata.com"

YAHOO_CHART_BASES = [
    "https://query1.finance.yahoo.com/v8/finance/chart",
    "https://query2.finance.yahoo.com/v8/finance/chart",
]

YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}

# Twelve Data free tier guard rails (override with env vars if you upgrade)
DEFAULT_MAX_REQUESTS_PER_MIN = 8
DEFAULT_MAX_REQUESTS_PER_DAY = 800
MAX_AUTO_THROTTLE_WAIT = 3.0  # seconds — longer waits fall back to Yahoo instead
DEFAULT_SYMBOL_ENRICH_LIMIT = 12  # quotes pulled for the symbol list / datalist

# =============================================================================
# INTERVALS
# =============================================================================
FOREX_INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]

INTERVAL_SECONDS: Dict[str, int] = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800,
}

TWELVEDATA_INTERVALS: Dict[str, str] = {
    "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1h", "4h": "4h", "1d": "1day", "1w": "1week",
}

# interval -> (yahoo interval, yahoo range, aggregation factor)
YAHOO_INTERVALS: Dict[str, Tuple[str, str, int]] = {
    "1m": ("1m", "5d", 1),
    "5m": ("5m", "1mo", 1),
    "15m": ("15m", "1mo", 1),
    "30m": ("30m", "1mo", 1),
    "1h": ("60m", "3mo", 1),
    "4h": ("60m", "6mo", 4),
    "1d": ("1d", "1y", 1),
    "1w": ("1wk", "5y", 1),
}

# =============================================================================
# CURRENCY UNIVERSE (28 pairs: majors, minors, exotics)
# =============================================================================
FOREX_CATEGORIES: Dict[str, List[str]] = {
    "majors": [
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD",
    ],
    "minors": [
        "EURGBP", "EURJPY", "GBPJPY", "AUDNZD", "EURAUD", "GBPAUD",
        "EURCHF", "CADJPY", "GBPCAD", "AUDCAD", "EURNZD", "GBPCHF",
        "AUDCHF", "CADCHF",
    ],
    "exotics": [
        "USDTRY", "USDZAR", "USDMXN", "EURNOK", "USDSEK", "USDSGD", "USDHKD",
    ],
}

# Unified default watchlist (majors first, then minors, then exotics)
DEFAULT_FOREX_WATCHLIST: List[str] = []
for _cat_pairs in FOREX_CATEGORIES.values():
    for _pair in _cat_pairs:
        if _pair not in DEFAULT_FOREX_WATCHLIST:
            DEFAULT_FOREX_WATCHLIST.append(_pair)

# Default Telegram / background-monitor watchlist for FX
FOREX_ALERT_WATCHLIST: List[str] = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF"]

MAJOR_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"}

CURRENCY_CODES = MAJOR_CURRENCIES | {
    "TRY", "ZAR", "MXN", "NOK", "SEK", "SGD", "HKD", "DKK", "PLN", "HUF",
    "CZK", "CNH", "CNY", "ILS", "THB", "INR", "KRW", "BRL", "RUB", "SAR", "AED",
}


# =============================================================================
# SYMBOL HELPERS
# =============================================================================
def normalize_forex_pair(symbol: str) -> str:
    """Normalizes any FX symbol flavour to the internal format (e.g. 'EURUSD').

    Accepts 'eurusd', 'EUR/USD', 'EUR_USD', 'EURUSD=X' and 'EURUSD'.
    """
    if not symbol:
        return ""
    text = str(symbol).upper().strip()
    text = text.replace("=X", "").replace("/", "").replace("_", "")
    text = text.replace("-", "").replace(" ", "")
    return text


def is_forex_pair(symbol: str) -> bool:
    """True when the symbol looks like a real FX pair (both legs are currencies)."""
    pair = normalize_forex_pair(symbol)
    if len(pair) != 6 or not pair.isalpha():
        return False
    base, quote = pair[:3], pair[3:]
    return base != quote and base in CURRENCY_CODES and quote in CURRENCY_CODES


def get_category_for_forex_pair(symbol: str) -> str:
    """Returns majors / minors / exotics for a pair, inferring unknown pairs sensibly."""
    pair = normalize_forex_pair(symbol)
    for cat, pairs in FOREX_CATEGORIES.items():
        if pair in pairs:
            return cat
    if not is_forex_pair(pair):
        return "majors"
    base, quote = pair[:3], pair[3:]
    if "USD" in (base, quote) and base in MAJOR_CURRENCIES and quote in MAJOR_CURRENCIES:
        return "majors"
    if base in MAJOR_CURRENCIES and quote in MAJOR_CURRENCIES:
        return "minors"
    return "exotics"


def get_forex_watchlist(category: Optional[str] = None) -> List[str]:
    """Returns curated FX pairs for a category ('all' or None returns the full list)."""
    if category and category != "all":
        return list(FOREX_CATEGORIES.get(category, DEFAULT_FOREX_WATCHLIST))
    return list(DEFAULT_FOREX_WATCHLIST)


def forex_pip_size(symbol: str) -> float:
    """Pip size: 0.01 for JPY-quoted pairs, 0.0001 for everything else."""
    pair = normalize_forex_pair(symbol)
    return 0.01 if pair[3:] == "JPY" else 0.0001


def forex_price_decimals(symbol: str) -> int:
    """Broker-style quote precision: 3 decimals for JPY pairs, 5 for all others."""
    pair = normalize_forex_pair(symbol)
    return 3 if pair[3:] == "JPY" else 5


def to_pips(price_distance: float, symbol: str) -> float:
    """Converts a raw price distance into pips."""
    pip = forex_pip_size(symbol)
    return round(abs(float(price_distance)) / pip, 1) if pip else 0.0


def forex_symbol_formats(symbol: str) -> Tuple[str, str]:
    """Returns (twelve_data_symbol, yahoo_symbol) for a normalized pair."""
    pair = normalize_forex_pair(symbol)
    return f"{pair[:3]}/{pair[3:]}", f"{pair}=X"

# =============================================================================
# FOREX MARKET HOURS & SESSIONS (all times UTC)
# =============================================================================
# The FX market opens Sunday ~21:00 UTC (Sydney) and closes Friday ~21:00 UTC (New York).
FOREX_SESSIONS: Dict[str, Dict[str, Any]] = {
    "SYDNEY": {
        "label": "Sydney", "emoji": "🌏", "open": 21.0, "close": 6.0, "liquidity": "LOW",
        "note": "Asian-Pacific open — thin liquidity, ranges often set here.",
    },
    "TOKYO": {
        "label": "Tokyo", "emoji": "🗼", "open": 0.0, "close": 9.0, "liquidity": "MEDIUM",
        "note": "Asian session — JPY and AUD pairs are most active.",
    },
    "LONDON": {
        "label": "London", "emoji": "🏛️", "open": 7.0, "close": 16.0, "liquidity": "HIGH",
        "note": "London session — highest FX turnover, strong EUR/GBP trends.",
    },
    "NEW_YORK": {
        "label": "New York", "emoji": "🗽", "open": 12.0, "close": 21.0, "liquidity": "HIGH",
        "note": "New York session — US data releases drive USD volatility.",
    },
}

_LIQUIDITY_RANK = {"CLOSED": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


def _as_utc(now_utc: Optional[datetime] = None) -> datetime:
    """Returns a timezone-aware UTC datetime (accepts naive datetimes as UTC)."""
    if now_utc is None:
        return datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        return now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(timezone.utc)


def _hour_float(dt: datetime) -> float:
    return dt.hour + dt.minute / 60.0 + dt.second / 3600.0


def _session_is_open(session_key: str, hour: float) -> bool:
    """True when the given session window contains the UTC hour (handles wrap-around)."""
    sess = FOREX_SESSIONS.get(session_key)
    if not sess:
        return False
    start, end = sess["open"], sess["close"]
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end  # wraps midnight (Sydney)


def is_forex_market_open(now_utc: Optional[datetime] = None) -> bool:
    """FX market hours: Sunday 21:00 UTC → Friday 21:00 UTC (holidays not modelled)."""
    now = _as_utc(now_utc)
    weekday = now.weekday()  # Monday=0 ... Sunday=6
    hour = _hour_float(now)

    if weekday == 5:  # Saturday
        return False
    if weekday == 6:  # Sunday — opens 21:00 UTC
        return hour >= 21.0
    if weekday == 4 and hour >= 21.0:  # Friday after the New York close
        return False
    return True


def _next_forex_open(now_utc: Optional[datetime] = None) -> datetime:
    """Returns the next UTC datetime at which the FX market reopens."""
    now = _as_utc(now_utc)
    if is_forex_market_open(now):
        return now
    weekday = now.weekday()
    hour = _hour_float(now)
    days_ahead = (6 - weekday) % 7
    if weekday == 6 and hour < 21.0:
        days_ahead = 0
    elif weekday == 4:  # Friday close → Sunday reopen
        days_ahead = 2
    elif weekday == 5:  # Saturday → Sunday reopen
        days_ahead = 1
    target = (now + timedelta(days=days_ahead)).replace(
        hour=21, minute=0, second=0, microsecond=0
    )
    if target <= now:
        target += timedelta(days=7)
    return target


def get_active_forex_sessions(now_utc: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Returns the FX trading sessions currently active (in market-hours order)."""
    now = _as_utc(now_utc)
    if not is_forex_market_open(now):
        return []
    hour = _hour_float(now)
    order = ["SYDNEY", "TOKYO", "LONDON", "NEW_YORK"]
    active = []
    for key in order:
        if _session_is_open(key, hour):
            sess = FOREX_SESSIONS[key]
            active.append({
                "key": key,
                "label": sess["label"],
                "emoji": sess["emoji"],
                "liquidity": sess["liquidity"],
                "note": sess["note"],
            })
    return active


def get_forex_session_summary(now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    """Full FX market-status snapshot used by the API, strategy narrative and UI."""
    now = _as_utc(now_utc)
    is_open = is_forex_market_open(now)
    active = get_active_forex_sessions(now)

    if not is_open:
        primary = "CLOSED"
        liquidity = "CLOSED"
        overlap = False
        description = (
            f"Forex market is closed (weekend). Reopens "
            f"{_next_forex_open(now).strftime('%a %d %b %H:%M')} UTC."
        )
    else:
        primary = active[-1]["key"] if active else "LONDON"
        liquidity = max(
            (s["liquidity"] for s in active), key=lambda x: _LIQUIDITY_RANK.get(x, 0),
            default="LOW",
        )
        overlap = any(s["key"] == "LONDON" for s in active) and any(
            s["key"] == "NEW_YORK" for s in active
        )
        labels = ", ".join(f"{s['emoji']} {s['label']}" for s in active) or "Interbank"
        description = f"Active session: {labels} ({liquidity} liquidity)"
        if overlap:
            description += " — London/New York overlap (highest volatility window)"

    return {
        "is_open": is_open,
        "market": "FOREX",
        "active_sessions": active,
        "primary_session": primary,
        "liquidity": liquidity,
        "overlap": overlap,
        "description": description,
        "utc_time": now.strftime("%Y-%m-%d %H:%M UTC"),
        "next_open_utc": _next_forex_open(now).strftime("%Y-%m-%d %H:%M UTC"),
    }



# =============================================================================
# TWELVE DATA REQUEST BUDGET (free tier safe)
# =============================================================================
_td_lock: Optional[asyncio.Lock] = None
_td_request_log: Dict[str, List[float]] = {"minute": [], "day": []}


def _get_td_lock() -> asyncio.Lock:
    global _td_lock
    if _td_lock is None:
        _td_lock = asyncio.Lock()
    return _td_lock


def twelvedata_api_key() -> str:
    """Reads the Twelve Data API key from the environment (.env supported)."""
    load_dotenv(override=True)
    return os.getenv("TWELVE_DATA_API_KEY", "").strip()


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(str(os.getenv(name, "")).strip() or default))
    except Exception:
        return default


def _prune_td_log(now: float) -> None:
    _td_request_log["minute"] = [t for t in _td_request_log["minute"] if now - t < 60]
    _td_request_log["day"] = [t for t in _td_request_log["day"] if now - t < 86400]


def twelvedata_budget_available() -> bool:
    """True when a Twelve Data request can be made without blowing the free tier."""
    if not twelvedata_api_key():
        return False
    now = time.time()
    _prune_td_log(now)
    max_rpm = _env_int("TWELVE_DATA_MAX_RPM", DEFAULT_MAX_REQUESTS_PER_MIN)
    max_day = _env_int("TWELVE_DATA_MAX_DAILY", DEFAULT_MAX_REQUESTS_PER_DAY)
    if len(_td_request_log["day"]) >= max_day:
        return False
    if len(_td_request_log["minute"]) < max_rpm:
        return True
    wait = 60.0 - (now - _td_request_log["minute"][0])
    return wait <= MAX_AUTO_THROTTLE_WAIT


async def _throttle_twelvedata() -> bool:
    """Reserves a Twelve Data request slot. Returns False when the budget is spent."""
    if not twelvedata_api_key():
        return False
    async with _get_td_lock():
        now = time.time()
        _prune_td_log(now)
        max_rpm = _env_int("TWELVE_DATA_MAX_RPM", DEFAULT_MAX_REQUESTS_PER_MIN)
        max_day = _env_int("TWELVE_DATA_MAX_DAILY", DEFAULT_MAX_REQUESTS_PER_DAY)
        if len(_td_request_log["day"]) >= max_day:
            return False
        if len(_td_request_log["minute"]) >= max_rpm:
            wait = 60.0 - (now - _td_request_log["minute"][0])
            if wait > MAX_AUTO_THROTTLE_WAIT:
                return False
            await asyncio.sleep(max(wait, 0.05))
        stamp = time.time()
        _td_request_log["minute"].append(stamp)
        _td_request_log["day"].append(stamp)
        return True



# =============================================================================
# NORMALIZERS (provider payload → internal candle format)
# =============================================================================
def _parse_twelvedata_datetime(value: Any) -> int:
    """Parses Twelve Data 'YYYY-MM-DD HH:MM:SS' (or ISO) strings into unix seconds."""
    text = str(value).strip().replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = datetime.strptime(text[:10], "%Y-%m-%d")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_twelvedata_payload(payload: Dict[str, Any], interval: str = "15m") -> List[Dict[str, Any]]:
    """Converts a Twelve Data /time_series response into internal candle dicts."""
    if not isinstance(payload, dict):
        raise ValueError("Unexpected Twelve Data response")
    if payload.get("status") == "error" or payload.get("code"):
        raise ValueError(str(payload.get("message") or f"Twelve Data error {payload.get('code')}"))

    values = payload.get("values") or []
    if not isinstance(values, list):
        raise ValueError("Malformed Twelve Data payload")

    step = INTERVAL_SECONDS.get(interval, 900)
    candles: List[Dict[str, Any]] = []
    for row in values:
        if not isinstance(row, dict) or "datetime" not in row:
            continue
        ts = _parse_twelvedata_datetime(row["datetime"])
        candles.append({
            "time": ts,
            "open": _to_float(row.get("open")),
            "high": _to_float(row.get("high")),
            "low": _to_float(row.get("low")),
            "close": _to_float(row.get("close")),
            "volume": _to_float(row.get("volume")),
            "close_time": ts + step - 1,
        })

    candles.sort(key=lambda c: c["time"])
    return candles


def normalize_yahoo_payload(payload: Dict[str, Any], interval: str = "15m") -> List[Dict[str, Any]]:
    """Converts a Yahoo Finance /chart response into internal candle dicts."""
    if not isinstance(payload, dict):
        raise ValueError("Unexpected Yahoo Finance response")

    chart = payload.get("chart") or {}
    error = chart.get("error")
    if error:
        raise ValueError(str(error.get("description") or error))

    results = chart.get("result") or []
    if not results:
        raise ValueError("Yahoo Finance returned no chart result")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quotes.get("open") or []
    highs = quotes.get("high") or []
    lows = quotes.get("low") or []
    closes = quotes.get("close") or []
    volumes = quotes.get("volume") or []

    step = INTERVAL_SECONDS.get(interval, 900)
    candles: List[Dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        o = _to_float(opens[i], float("nan")) if i < len(opens) else float("nan")
        h = _to_float(highs[i], float("nan")) if i < len(highs) else float("nan")
        low = _to_float(lows[i], float("nan")) if i < len(lows) else float("nan")
        c = _to_float(closes[i], float("nan")) if i < len(closes) else float("nan")
        if any(v != v for v in (o, h, low, c)):  # NaN → market gap, skip
            continue
        vol = _to_float(volumes[i]) if i < len(volumes) else 0.0
        candles.append({
            "time": int(ts),
            "open": o,
            "high": h,
            "low": low,
            "close": c,
            "volume": vol,
            "close_time": int(ts) + step - 1,
        })

    candles.sort(key=lambda c: c["time"])
    return candles


def aggregate_candles(candles: List[Dict[str, Any]], factor: int) -> List[Dict[str, Any]]:
    """Aggregates candles into larger buckets (e.g. 4×1h → 4h) for providers lacking that interval."""
    if factor <= 1 or not candles:
        return list(candles)

    buckets: List[Dict[str, Any]] = []
    chunk: List[Dict[str, Any]] = []
    for candle in candles:
        chunk.append(candle)
        if len(chunk) == factor:
            buckets.append(_merge_candle_chunk(chunk))
            chunk = []
    if chunk:
        buckets.append(_merge_candle_chunk(chunk))
    return buckets


def _merge_candle_chunk(chunk: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "time": chunk[0]["time"],
        "open": chunk[0]["open"],
        "high": max(c["high"] for c in chunk),
        "low": min(c["low"] for c in chunk),
        "close": chunk[-1]["close"],
        "volume": float(sum(c.get("volume", 0.0) for c in chunk)),
        "close_time": chunk[-1]["close_time"],
    }



# =============================================================================
# PROVIDER REQUESTS
# =============================================================================
async def _http_get_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 10.0,
) -> Any:
    """Small JSON GET helper shared by the Twelve Data and Yahoo Finance paths."""
    async with httpx.AsyncClient(timeout=timeout, headers=headers or YAHOO_HEADERS) as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            raise ValueError(f"HTTP {response.status_code} from {url}")
        return response.json()


async def fetch_twelvedata_time_series(
    symbol: str, interval: str = "15m", limit: int = 200
) -> List[Dict[str, Any]]:
    """Fetches OHLC candles from Twelve Data (returns [] when the budget is exhausted)."""
    if not twelvedata_api_key():
        return []
    if not await _throttle_twelvedata():
        return []

    td_symbol, _ = forex_symbol_formats(symbol)
    if not is_forex_pair(td_symbol):
        # Non-FX Twelve Data symbols (e.g. DXY, SPX, AAPL) are passed through untouched
        td_symbol = str(symbol).upper().strip()
    params = {
        "symbol": td_symbol,
        "interval": TWELVEDATA_INTERVALS.get(interval, "15min"),
        "outputsize": max(30, min(int(limit), 1000)),
        "apikey": twelvedata_api_key(),
        "order": "ASC",
        "format": "JSON",
        "timezone": "UTC",
    }
    payload = await _http_get_json(
        f"{TWELVE_DATA_BASE}/time_series", params=params, headers={"Accept": "application/json"}
    )
    return normalize_twelvedata_payload(payload, interval)


async def fetch_yahoo_chart(
    yahoo_symbol: str,
    interval: str = "15m",
    limit: int = 200,
    range_override: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetches (and normalizes) Yahoo Finance chart candles for any Yahoo symbol."""
    y_interval, y_range, factor = YAHOO_INTERVALS.get(interval, ("15m", "1mo", 1))
    if range_override:
        y_range = range_override

    params = {
        "interval": y_interval,
        "range": y_range,
        "includePrePost": "false",
        "events": "div,split",
    }

    last_err: Optional[Exception] = None
    for base in YAHOO_CHART_BASES:
        try:
            payload = await _http_get_json(f"{base}/{yahoo_symbol}", params=params)
            candles = normalize_yahoo_payload(payload, interval)
            if factor > 1:
                candles = aggregate_candles(candles, factor)
            return candles[-limit:] if limit and len(candles) > limit else candles
        except Exception as exc:  # try the secondary Yahoo host
            last_err = exc
            continue

    if last_err:
        raise last_err
    return []


async def fetch_yahoo_meta(yahoo_symbol: str) -> Dict[str, Any]:
    """Returns the Yahoo Finance `meta` block (live quote snapshot) for a symbol."""
    payload = await _http_get_json(
        f"{YAHOO_CHART_BASES[0]}/{yahoo_symbol}",
        params={"interval": "1d", "range": "5d"},
    )
    results = ((payload.get("chart") or {}).get("result") or [])
    if not results:
        raise ValueError("Yahoo Finance returned no quote metadata")
    return results[0].get("meta", {})



# =============================================================================
# PRICE CACHE (keeps the symbol list & scanner cheap)
# =============================================================================
_price_cache: Dict[str, Dict[str, Any]] = {}


def record_forex_quote(pair: str, price: float, change24h: float = 0.0, **extra: Any) -> None:
    """Stores the latest known quote for a pair (used by the symbol list / datalist)."""
    pair = normalize_forex_pair(pair)
    if not pair or not price:
        return
    entry = dict(_price_cache.get(pair, {}))
    entry.update({
        "symbol": pair,
        "price": float(price),
        "change24h": round(float(change24h), 2),
        "category": get_category_for_forex_pair(pair),
        "price_decimals": forex_price_decimals(pair),
        "updated": time.time(),
    })
    entry.update({k: v for k, v in extra.items() if v is not None})
    _price_cache[pair] = entry


def get_cached_quote(pair: str) -> Optional[Dict[str, Any]]:
    """Returns the cached quote for a pair (or None when never fetched)."""
    return _price_cache.get(normalize_forex_pair(pair))


def _change_from_candles(candles: List[Dict[str, Any]]) -> float:
    """Approximates the 24h % change from a candle series."""
    if len(candles) < 2:
        return 0.0
    last = candles[-1]["close"]
    step = candles[-1]["time"] - candles[-2]["time"]
    bars = max(1, int(86400 / step)) if step > 0 else 1
    ref = candles[-min(len(candles), bars + 1)]["close"]
    return round((last - ref) / ref * 100, 2) if ref else 0.0


def _candle_stats(candles: List[Dict[str, Any]], hours: float = 24.0) -> Dict[str, float]:
    """High/low/tick-volume over the trailing window derived from the candle series."""
    if not candles:
        return {"high24h": 0.0, "low24h": 0.0, "volume": 0.0}
    step = candles[-1]["time"] - candles[-2]["time"] if len(candles) > 1 else 900
    bars = max(1, int((hours * 3600) / step)) if step > 0 else 1
    window = candles[-min(len(candles), bars):]
    return {
        "high24h": max(c["high"] for c in window),
        "low24h": min(c["low"] for c in window),
        "volume": float(sum(c.get("volume", 0.0) for c in window)),
    }


# =============================================================================
# PUBLIC DATA API (mirrors binance_client.py)
# =============================================================================
async def fetch_forex_klines(
    symbol: str = "EURUSD",
    interval: str = "15m",
    limit: int = 200,
    prefer: str = "auto",
) -> List[Dict[str, Any]]:
    """
    Fetch historical FX candlestick bars, normalized to the Binance candle format:
      - time: unix timestamp in seconds
      - open, high, low, close, volume: floats
      - close_time: unix timestamp of the bar close

    prefer:
      - "auto"      → Twelve Data when its free-tier budget allows, else Yahoo
      - "twelvedata"→ force Twelve Data first (Yahoo as fallback)
      - "yahoo"     → force Yahoo first (Twelve Data as fallback)
    """
    pair = normalize_forex_pair(symbol)
    if not is_forex_pair(pair):
        raise ValueError(f"Invalid forex pair: {symbol}")
    if interval not in FOREX_INTERVALS:
        interval = "15m"
    limit = max(30, min(int(limit), 1000))

    _, yahoo_symbol = forex_symbol_formats(pair)

    if prefer == "twelvedata":
        sources = ["twelvedata", "yahoo"]
    elif prefer == "yahoo":
        sources = ["yahoo", "twelvedata"]
    elif twelvedata_budget_available():
        sources = ["twelvedata", "yahoo"]
    else:
        sources = ["yahoo", "twelvedata"]

    last_err: Optional[Exception] = None
    for source in sources:
        try:
            if source == "twelvedata":
                candles = await fetch_twelvedata_time_series(pair, interval, limit)
            else:
                candles = await fetch_yahoo_chart(yahoo_symbol, interval, limit)

            if not candles:
                continue

            candles = candles[-limit:]
            stats = _candle_stats(candles)
            record_forex_quote(
                pair,
                candles[-1]["close"],
                _change_from_candles(candles),
                high24h=stats["high24h"],
                low24h=stats["low24h"],
                volume=stats["volume"],
                source=source,
            )
            return candles
        except Exception as exc:
            last_err = exc
            continue

    if last_err:
        raise last_err
    return []



async def fetch_forex_ticker(symbol: str) -> Dict[str, Any]:
    """
    Fetches a live quote snapshot for an FX pair (price, 24h change, high/low, tick volume).
    Twelve Data /quote is used when the free-tier budget allows, otherwise Yahoo Finance.
    """
    pair = normalize_forex_pair(symbol)
    if not is_forex_pair(pair):
        raise ValueError(f"Invalid forex pair: {symbol}")

    category = get_category_for_forex_pair(pair)
    _, yahoo_symbol = forex_symbol_formats(pair)

    if twelvedata_budget_available() and await _throttle_twelvedata():
        td_symbol, _ = forex_symbol_formats(pair)
        try:
            payload = await _http_get_json(
                f"{TWELVE_DATA_BASE}/quote",
                params={"symbol": td_symbol, "apikey": twelvedata_api_key()},
                headers={"Accept": "application/json"},
            )
            if isinstance(payload, dict) and not payload.get("code") and payload.get("close"):
                price = _to_float(payload.get("close"))
                prev = _to_float(payload.get("previous_close"), price)
                change = _to_float(payload.get("percent_change"))
                if not change and prev:
                    change = (price - prev) / prev * 100
                ticker = {
                    "symbol": pair,
                    "price": price,
                    "change24h": round(change, 2),
                    "volume": _to_float(payload.get("volume")),
                    "high24h": _to_float(payload.get("high"), price),
                    "low24h": _to_float(payload.get("low"), price),
                    "category": category,
                    "price_decimals": forex_price_decimals(pair),
                    "source": "twelvedata",
                }
                record_forex_quote(pair, price, ticker["change24h"],
                                   high24h=ticker["high24h"], low24h=ticker["low24h"],
                                   volume=ticker["volume"], source="twelvedata")
                return ticker
        except Exception:
            pass  # fall through to Yahoo Finance

    meta = await fetch_yahoo_meta(yahoo_symbol)
    price = _to_float(meta.get("regularMarketPrice"))
    prev = _to_float(meta.get("previousClose"), _to_float(meta.get("chartPreviousClose"), price))
    change = ((price - prev) / prev * 100) if (price and prev) else 0.0
    ticker = {
        "symbol": pair,
        "price": price,
        "change24h": round(change, 2),
        "volume": _to_float(meta.get("regularMarketVolume")),
        "high24h": _to_float(meta.get("regularMarketDayHigh"), price),
        "low24h": _to_float(meta.get("regularMarketDayLow"), price),
        "category": category,
        "price_decimals": forex_price_decimals(pair),
        "source": "yahoo",
    }
    record_forex_quote(pair, price, ticker["change24h"],
                       high24h=ticker["high24h"], low24h=ticker["low24h"],
                       volume=ticker["volume"], source="yahoo")
    return ticker


def _stub_pair_item(pair: str) -> Dict[str, Any]:
    """Curated fallback entry (used when live quotes are unavailable)."""
    return {
        "symbol": pair,
        "price": 0.0,
        "change24h": 0.0,
        "volume": 0.0,
        "high24h": 0.0,
        "low24h": 0.0,
        "category": get_category_for_forex_pair(pair),
        "price_decimals": forex_price_decimals(pair),
        "source": "curated",
    }


async def get_top_forex_pairs(
    limit: int = 28,
    category: Optional[str] = None,
    enrich: bool = True,
) -> List[Dict[str, Any]]:
    """
    Returns the curated FX pair universe (majors → minors → exotics) with live quotes.

    Quotes come from the in-process cache first (populated by every kline request) and
    only fresh pairs are enriched, capped by FOREX_SYMBOL_ENRICH_LIMIT, so calling this
    endpoint never exhausts the Twelve Data free tier.
    """
    pairs = get_forex_watchlist(category)[: max(1, int(limit))]
    items: Dict[str, Dict[str, Any]] = {}

    for pair in pairs:
        cached = get_cached_quote(pair)
        items[pair] = dict(cached) if cached else _stub_pair_item(pair)
        items[pair].setdefault("category", get_category_for_forex_pair(pair))

    if enrich:
        enrich_limit = _env_int("FOREX_SYMBOL_ENRICH_LIMIT", 6)
        missing = [p for p in pairs if not get_cached_quote(p)][:enrich_limit]
        if missing:
            sem = asyncio.Semaphore(6)

            async def enrich_one(pair: str) -> None:
                async with sem:
                    try:
                        ticker = await asyncio.wait_for(fetch_forex_ticker(pair), timeout=3.5)
                        if ticker and isinstance(ticker, dict):
                            items[pair] = ticker
                    except Exception:
                        pass

            await asyncio.gather(*[enrich_one(p) for p in missing], return_exceptions=True)

    return [items[p] for p in pairs]


def get_forex_market_status() -> Dict[str, Any]:
    """Convenience wrapper exposing FX session/holiday state to the API layer."""
    return get_forex_session_summary()

