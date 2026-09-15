"""
FastAPI Web Application & API Server for Binance Crypto Chart Analysis.
Serves interactive dashboard and REST endpoints for real-time market analysis.
"""

from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import re
import asyncio
import os
import time
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from binance_client import (
    DEFAULT_WATCHLIST,
    VALID_INTERVALS,
    COIN_CATEGORIES,
    get_category_for_symbol,
    fetch_klines,
    get_top_symbols,
)
from indicators import calculate_all_indicators
from strategy import analyze_market_signals
from telegram_notifier import send_signal_alert
from sentiment import get_sentiment_summary
from forex_client import (
    DEFAULT_FOREX_WATCHLIST,
    FOREX_ALERT_WATCHLIST,
    FOREX_CATEGORIES,
    FOREX_INTERVALS,
    get_category_for_forex_pair,
    get_forex_session_summary,
    get_top_forex_pairs,
    is_forex_pair,
    normalize_forex_pair,
    fetch_forex_klines,
)
from forex_sentiment import (
    build_forex_sentiment_for_pair,
    get_forex_sentiment_summary,
)

# Supported markets / asset classes
MARKET_CRYPTO = "crypto"
MARKET_FOREX = "forex"
VALID_MARKETS = (MARKET_CRYPTO, MARKET_FOREX)

last_sent_signals = {}
notify_rate_limits = {}  # {ip: last_request_time}


def _normalize_market(market: Optional[str]) -> str:
    """Maps the ?market= query param onto a supported market key."""
    key = str(market or "").strip().lower()
    if key in ("forex", "fx", "currency"):
        return MARKET_FOREX
    return MARKET_CRYPTO


def _market_symbol(symbol: str, market: str) -> str:
    """Normalizes a user supplied symbol for the requested market."""
    if market == MARKET_FOREX:
        return normalize_forex_pair(symbol)
    clean = str(symbol or "").upper().strip()
    if clean and not clean.endswith("USDT"):
        clean += "USDT"
    return clean


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Hardens HTTP response headers to achieve 100% web security rating."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Content Security Policy (allows Lightweight charts CDN and Google Fonts)
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' https://*.binance.vision https://*.binance.com https://api.telegram.org https://api.alternative.me https://api.coingecko.com https://api.twelvedata.com https://query1.finance.yahoo.com https://query2.finance.yahoo.com; "
            "img-src 'self' data: https:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"

        # Strip server signature
        if "server" in response.headers:
            del response.headers["server"]

        return response


async def background_signal_monitor():
    """Background worker that continuously scans market and sends Telegram alerts."""
    await asyncio.sleep(10)
    while True:
        try:
            load_dotenv(override=True)
            token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

            if token and chat_id:
                for sym in DEFAULT_WATCHLIST[:8]:
                    try:
                        candles = await fetch_klines(sym, "15m", limit=100)
                        if candles:
                            indicators = calculate_all_indicators(candles)
                            sig = analyze_market_signals(candles, indicators, sym, sentiment=None)
                            signal_type = sig["signal"]

                            if "BUY" in signal_type or "SELL" in signal_type:
                                last_sig, last_time = last_sent_signals.get(sym, ("", 0))
                                # Only alert if new signal or 45 mins elapsed
                                if last_sig != signal_type or (time.time() - last_time > 2700):
                                    await send_signal_alert(sig, "15m")
                                    last_sent_signals[sym] = (signal_type, time.time())
                                    await asyncio.sleep(2)
                    except Exception:
                        continue

                # Forex watchlist (only while the FX market is actually open)
                fx_status = get_forex_session_summary()
                if fx_status.get("is_open"):
                    for sym in FOREX_ALERT_WATCHLIST:
                        try:
                            candles = await fetch_forex_klines(sym, "15m", limit=100)
                            if candles:
                                indicators = calculate_all_indicators(candles)
                                fx_sentiment = await _get_forex_pair_sentiment(sym)
                                sig = analyze_market_signals(
                                    candles, indicators, sym,
                                    sentiment=fx_sentiment, asset_class=MARKET_FOREX,
                                )
                                signal_type = sig["signal"]
                                key = f"FOREX:{sym}"

                                if "BUY" in signal_type or "SELL" in signal_type:
                                    last_sig, last_time = last_sent_signals.get(key, ("", 0))
                                    if last_sig != signal_type or (time.time() - last_time > 2700):
                                        await send_signal_alert(sig, "15m", asset_class=MARKET_FOREX)
                                        last_sent_signals[key] = (signal_type, time.time())
                                        await asyncio.sleep(2)
                        except Exception:
                            continue
        except Exception:
            pass

        await asyncio.sleep(120)  # Check every 2 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background alert monitor
    monitor_task = asyncio.create_task(background_signal_monitor())
    yield
    monitor_task.cancel()


app = FastAPI(
    title="Men Trading - AI Crypto & Forex Chart Analysis & Signal Terminal",
    lifespan=lifespan,
    docs_url=None,  # Disabled public Swagger docs for security
    redoc_url=None,  # Disabled public ReDoc for security
    openapi_url=None,
)

# Apply Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# Enable CORS for trusted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)


# Cached sentiment data (refreshed every 2 minutes to avoid spamming free APIs)
_sentiment_cache = {"data": None, "ts": 0}
SENTIMENT_CACHE_TTL = 120  # seconds

# Cached FX macro snapshot (DXY / VIX / session) — refreshed every 5 minutes
_forex_sentiment_cache = {"data": None, "ts": 0}
FOREX_SENTIMENT_CACHE_TTL = 300  # seconds


async def _get_cached_sentiment() -> dict:
    """Returns cached sentiment data, refreshing if stale."""
    now = time.time()
    if _sentiment_cache["data"] is None or (now - _sentiment_cache["ts"]) > SENTIMENT_CACHE_TTL:
        try:
            _sentiment_cache["data"] = await get_sentiment_summary()
            _sentiment_cache["ts"] = now
        except Exception:
            if _sentiment_cache["data"] is None:
                _sentiment_cache["data"] = {"fear_greed": {"value": 50, "zone": "NEUTRAL"}, "trending_coins": [], "global_market": {}}
    return _sentiment_cache["data"]


async def _get_cached_forex_sentiment() -> dict:
    """Returns the cached FX macro snapshot (DXY, VIX, session), refreshing if stale."""
    now = time.time()
    if _forex_sentiment_cache["data"] is None or (now - _forex_sentiment_cache["ts"]) > FOREX_SENTIMENT_CACHE_TTL:
        try:
            _forex_sentiment_cache["data"] = await get_forex_sentiment_summary()
            _forex_sentiment_cache["ts"] = now
        except Exception:
            if _forex_sentiment_cache["data"] is None:
                _forex_sentiment_cache["data"] = {
                    "dxy": {"value": 0.0, "change_pct": 0.0, "score": 50,
                            "zone": "NEUTRAL_DOLLAR", "classification": "Balanced Dollar", "advice": ""},
                    "vix": {"value": 0.0, "change_pct": 0.0, "score": 50, "zone": "CALM",
                            "regime": "MIXED", "advice": ""},
                    "session": get_forex_session_summary(),
                    "usd_bias": "NEUTRAL",
                    "risk_regime": "MIXED",
                    "summary": "FX sentiment data unavailable — using neutral defaults.",
                }
    return _forex_sentiment_cache["data"]


async def _get_forex_pair_sentiment(symbol: str) -> dict:
    """Builds pair-aware FX sentiment (DXY/VIX/session) for the strategy engine."""
    summary = await _get_cached_forex_sentiment()
    return build_forex_sentiment_for_pair(symbol, summary)


@app.get("/api/sentiment")
async def get_sentiment(market: str = Query("crypto", description="crypto | forex")):
    """Returns market sentiment: crypto Fear & Greed, or FX DXY/VIX/session context."""
    mkt = _normalize_market(market)

    if mkt == MARKET_FOREX:
        forex = await _get_cached_forex_sentiment()
        return {"success": True, "market": mkt, **forex}

    sentiment = await _get_cached_sentiment()
    return {"success": True, "market": mkt, **sentiment}


@app.get("/api/symbols")
async def get_symbols(
    category: Optional[str] = Query(None, description="Optional category filter"),
    market: str = Query("crypto", description="crypto | forex"),
):
    """Returns categorized active Binance USDT pairs or forex currency pairs."""
    mkt = _normalize_market(market)

    if mkt == MARKET_FOREX:
        try:
            pairs = await get_top_forex_pairs(limit=len(DEFAULT_FOREX_WATCHLIST), category=category)
            return {
                "success": True,
                "market": mkt,
                "symbols": pairs,
                "categories": list(FOREX_CATEGORIES.keys()),
                "total": len(pairs),
            }
        except Exception as e:
            fallback = FOREX_CATEGORIES.get(category, DEFAULT_FOREX_WATCHLIST) if category and category != "all" else DEFAULT_FOREX_WATCHLIST
            return {
                "success": False,
                "market": mkt,
                "symbols": [
                    {"symbol": s, "price": 0.0, "change24h": 0.0, "category": get_category_for_forex_pair(s)}
                    for s in fallback
                ],
                "categories": list(FOREX_CATEGORIES.keys()),
                "error": str(e),
            }

    try:
        symbols = await get_top_symbols(limit=60, category=category)
        return {
            "success": True,
            "market": mkt,
            "symbols": symbols,
            "categories": list(COIN_CATEGORIES.keys()),
            "total": len(symbols),
        }
    except Exception as e:
        fallback = COIN_CATEGORIES.get(category, DEFAULT_WATCHLIST) if category and category != "all" else DEFAULT_WATCHLIST
        return {
            "success": False,
            "market": mkt,
            "symbols": [{"symbol": s, "price": 0.0, "change24h": 0.0, "category": get_category_for_symbol(s)} for s in fallback],
            "categories": list(COIN_CATEGORIES.keys()),
            "error": str(e),
        }


@app.get("/api/analyze")
async def analyze(
    symbol: str = Query("BTCUSDT", description="Trading pair (BTCUSDT or EURUSD)"),
    interval: str = Query("15m", description="Candle interval (1m, 5m, 15m, 1h, 4h, 1d)"),
    market: str = Query("crypto", description="crypto | forex"),
):
    """
    Analyzes candlestick data for a given symbol and interval on either market.
    Returns:
    - raw candles for chart plotting
    - calculated technical indicators
    - actionable trading signals (Entry, SL, TP1, TP2, TP3)
    """
    mkt = _normalize_market(market)

    if mkt == MARKET_FOREX:
        clean_sym = normalize_forex_pair(symbol)
        if not is_forex_pair(clean_sym):
            return {
                "success": False,
                "error": "Invalid forex pair. Use a 6-letter currency pair such as EURUSD, GBPJPY or USDTRY.",
            }
        if interval not in FOREX_INTERVALS:
            interval = "15m"
        category = get_category_for_forex_pair(clean_sym)
    else:
        clean_sym = symbol.upper().strip()
        if not re.match(r"^[A-Z0-9]{2,14}$", clean_sym):
            return {"success": False, "error": "Invalid symbol format. Use alphanumeric characters only."}

        if not clean_sym.endswith("USDT"):
            clean_sym += "USDT"

        if interval not in VALID_INTERVALS:
            interval = "15m"
        category = get_category_for_symbol(clean_sym)

    try:
        if mkt == MARKET_FOREX:
            candles = await fetch_forex_klines(clean_sym, interval, limit=250)
        else:
            candles = await fetch_klines(clean_sym, interval, limit=250)

        if not candles:
            return {"success": False, "error": f"Failed to retrieve data for {clean_sym}"}

        indicators = calculate_all_indicators(candles)

        if mkt == MARKET_FOREX:
            sentiment = await _get_forex_pair_sentiment(clean_sym)
        else:
            sentiment = await _get_cached_sentiment()

        signals = analyze_market_signals(
            candles, indicators, clean_sym, sentiment=sentiment, asset_class=mkt
        )

        # Build lightweight-chart formatted data
        chart_candles = [
            {
                "time": c["time"],
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
            }
            for c in candles
        ]

        chart_volume = [
            {
                "time": c["time"],
                "value": c["volume"],
                "color": "rgba(34, 197, 94, 0.4)" if c["close"] >= c["open"] else "rgba(239, 68, 68, 0.4)",
            }
            for c in candles
        ]

        # EMA line series
        ema20_line = [
            {"time": candles[i]["time"], "value": indicators["ema20"][i]}
            for i in range(len(candles))
            if indicators["ema20"][i] is not None
        ]
        ema50_line = [
            {"time": candles[i]["time"], "value": indicators["ema50"][i]}
            for i in range(len(candles))
            if indicators["ema50"][i] is not None
        ]
        ema200_line = [
            {"time": candles[i]["time"], "value": indicators["ema200"][i]}
            for i in range(len(candles))
            if indicators["ema200"][i] is not None
        ]

        return {
            "success": True,
            "market": mkt,
            "asset_class": mkt,
            "symbol": clean_sym,
            "interval": interval,
            "category": category,
            "market_status": get_forex_session_summary() if mkt == MARKET_FOREX else None,
            "candles": chart_candles,
            "volume": chart_volume,
            "ema20": ema20_line,
            "ema50": ema50_line,
            "ema200": ema200_line,
            "signal": signals,
            "latest_price": signals["price"],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/mtf")
async def get_mtf_confluence(
    symbol: str = Query("BTCUSDT", description="Trading pair (BTCUSDT or EURUSD)"),
    market: str = Query("crypto", description="crypto | forex"),
):
    """
    Analyzes multi-timeframe confluence across 5m, 15m, 1h, 4h, and 1d.
    Returns trend bias, RSI, EMA alignment, and confluence consensus score.
    """
    mkt = _normalize_market(market)

    if mkt == MARKET_FOREX:
        clean_sym = normalize_forex_pair(symbol)
        if not is_forex_pair(clean_sym):
            return {"success": False, "error": "Invalid forex pair. Use a 6-letter pair like EURUSD."}
    else:
        clean_sym = symbol.upper().strip()
        if not re.match(r"^[A-Z0-9]{2,14}$", clean_sym):
            return {"success": False, "error": "Invalid symbol format"}
        if not clean_sym.endswith("USDT"):
            clean_sym += "USDT"

    tf_list = ["5m", "15m", "1h", "4h", "1d"]

    async def fetch_and_analyze_tf(tf: str):
        try:
            if mkt == MARKET_FOREX:
                candles = await fetch_forex_klines(clean_sym, tf, limit=80)
            else:
                candles = await fetch_klines(clean_sym, tf, limit=80)
            if not candles or len(candles) < 25:
                return tf, None
            indicators = calculate_all_indicators(candles)
            sig = analyze_market_signals(
                candles, indicators, clean_sym, sentiment=None, asset_class=mkt
            )
            price = candles[-1]["close"]

            # EMA Trend condition
            e20 = indicators["ema20"][-1] if indicators.get("ema20") and indicators["ema20"][-1] is not None else price
            e50 = indicators["ema50"][-1] if indicators.get("ema50") and indicators["ema50"][-1] is not None else price
            if price >= e20 >= e50:
                trend = "BULLISH"
            elif price <= e20 <= e50:
                trend = "BEARISH"
            else:
                trend = "CONSOLIDATION"

            return tf, {
                "signal": sig["signal"],
                "bias": sig["bias"],
                "confidence": sig["confidence"],
                "rsi": sig["rsi"],
                "trend": trend,
                "price": price,
            }
        except Exception:
            return tf, None

    results = await asyncio.gather(*[fetch_and_analyze_tf(tf) for tf in tf_list])
    tf_data = {}
    bull_count = 0
    bear_count = 0
    valid_count = 0

    for tf, data in results:
        if data:
            tf_data[tf] = data
            valid_count += 1
            if "BUY" in data["signal"] or data["bias"] == "LONG":
                bull_count += 1
            elif "SELL" in data["signal"] or data["bias"] == "SHORT":
                bear_count += 1
        else:
            tf_data[tf] = {
                "signal": "NEUTRAL",
                "bias": "NEUTRAL",
                "confidence": 50,
                "rsi": 50.0,
                "trend": "NEUTRAL",
                "price": 0.0,
            }

    if valid_count > 0:
        if bull_count >= 4:
            overall_bias = "STRONG_BULLISH"
            consensus = f"{bull_count}/{len(tf_list)} Bullish Confluence"
        elif bull_count >= 3:
            overall_bias = "BULLISH"
            consensus = f"{bull_count}/{len(tf_list)} Bullish Confluence"
        elif bear_count >= 4:
            overall_bias = "STRONG_BEARISH"
            consensus = f"{bear_count}/{len(tf_list)} Bearish Confluence"
        elif bear_count >= 3:
            overall_bias = "BEARISH"
            consensus = f"{bear_count}/{len(tf_list)} Bearish Confluence"
        else:
            overall_bias = "NEUTRAL"
            consensus = "Mixed Market Structure"

        dominant = max(bull_count, bear_count)
        confluence_score = int(round((dominant / max(valid_count, 1)) * 100))
    else:
        overall_bias = "NEUTRAL"
        consensus = "Analyzing Market..."
        confluence_score = 50

    return {
        "success": True,
        "market": mkt,
        "asset_class": mkt,
        "symbol": clean_sym,
        "timeframes": tf_data,
        "overall_bias": overall_bias,
        "consensus": consensus,
        "confluence_score": confluence_score,
        "bull_count": bull_count,
        "bear_count": bear_count,
        "total_timeframes": len(tf_list),
    }


@app.get("/api/scanner")
async def scanner(
    interval: str = Query("15m"),
    category: str = Query("all", description="Category: all, majors, layer1_2, defi, ai, memes (crypto) / majors, minors, exotics (forex)"),
    limit: int = Query(25, description="Max symbols to scan"),
    market: str = Query("crypto", description="crypto | forex"),
):
    """
    Scans watchlist instruments across categories and returns real-time trade recommendations.
    Uses concurrency with semaphores to scan quickly without hitting provider rate limits.
    """
    mkt = _normalize_market(market)

    if mkt == MARKET_FOREX:
        if interval not in FOREX_INTERVALS:
            interval = "15m"
        is_category = category and category != "all" and category in FOREX_CATEGORIES
        selected_symbols = (FOREX_CATEGORIES[category] if is_category else DEFAULT_FOREX_WATCHLIST)[:limit]
        sem = asyncio.Semaphore(4)  # FX providers throttle harder than Binance
        fx_summary = await _get_cached_forex_sentiment()
    else:
        if category and category != "all" and category in COIN_CATEGORIES:
            selected_symbols = COIN_CATEGORIES[category][:limit]
        else:
            top_items = await get_top_symbols(limit=limit)
            selected_symbols = [item["symbol"] for item in top_items] if top_items else DEFAULT_WATCHLIST[:limit]
        sem = asyncio.Semaphore(8)
        sentiment = await _get_cached_sentiment()

    async def scan_one(sym: str):
        async with sem:
            try:
                if mkt == MARKET_FOREX:
                    candles = await fetch_forex_klines(sym, interval, limit=100)
                else:
                    candles = await fetch_klines(sym, interval, limit=100)

                if not candles or len(candles) < 25:
                    return None

                indicators = calculate_all_indicators(candles)

                if mkt == MARKET_FOREX:
                    sig_sentiment = build_forex_sentiment_for_pair(sym, fx_summary)
                else:
                    sig_sentiment = sentiment

                sig = analyze_market_signals(
                    candles, indicators, sym, sentiment=sig_sentiment, asset_class=mkt
                )
                return {
                    "symbol": sym,
                    "category": get_category_for_forex_pair(sym) if mkt == MARKET_FOREX else get_category_for_symbol(sym),
                    "price": sig["price"],
                    "price_decimals": sig.get("price_decimals"),
                    "asset_class": mkt,
                    "signal": sig["signal"],
                    "bias": sig["bias"],
                    "grade": sig.get("grade", "D"),
                    "confidence": sig["confidence"],
                    "entry": sig["entry"],
                    "stop_loss": sig["stop_loss"],
                    "take_profit_1": sig["take_profit_1"],
                    "take_profit_2": sig["take_profit_2"],
                    "risk_pct": sig["risk_pct"],
                    "tp1_pct": sig["tp1_pct"],
                    "tp2_pct": sig["tp2_pct"],
                    "risk_pips": sig.get("risk_pips"),
                    "tp1_pips": sig.get("tp1_pips"),
                    "rsi": sig["rsi"],
                    "net_score": sig.get("net_score", 0),
                    "risk_reward_tp1": sig.get("risk_reward_tp1", "0"),
                    "narrative": sig.get("narrative", ""),
                    "entry_quality": sig.get("entry_quality", "N/A"),
                    "entry_strategy": sig.get("entry_strategy", ""),
                    "management_advice": sig.get("management_advice", ""),
                    "market_structure": sig.get("market_structure", {}),
                    "volume_analysis": sig.get("volume_analysis", {}),
                    "candle_patterns_summary": sig.get("candle_patterns_summary", ""),
                    "bb_squeeze_active": sig.get("bb_squeeze_active", False),
                }
            except Exception:
                return None

    tasks = [scan_one(sym) for sym in selected_symbols]
    scan_results = [r for r in await asyncio.gather(*tasks) if r is not None]

    return {
        "success": True,
        "market": mkt,
        "interval": interval,
        "category": category,
        "results": scan_results,
    }



@app.post("/api/notify")
async def notify(
    request: Request,
    symbol: str,
    interval: str = "15m",
    market: str = Query("crypto", description="crypto | forex"),
):
    """Manually triggers Telegram alert for current analysis with rate limit protection."""
    # Security: Rate limit by client IP (max 1 request every 20 seconds per IP)
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    last_req = notify_rate_limits.get(client_ip, 0)
    if now - last_req < 20:
        remaining = int(20 - (now - last_req))
        return JSONResponse(
            status_code=429,
            content={"success": False, "error": f"Rate limit active. Please wait {remaining}s."}
        )
    notify_rate_limits[client_ip] = now

    mkt = _normalize_market(market)

    # Validate symbol input
    if mkt == MARKET_FOREX:
        clean_sym = normalize_forex_pair(symbol)
        if not is_forex_pair(clean_sym):
            return {"success": False, "error": "Invalid forex pair"}
    else:
        clean_sym = symbol.upper().strip()
        if not re.match(r"^[A-Z0-9]{2,14}$", clean_sym):
            return {"success": False, "error": "Invalid symbol"}
        if not clean_sym.endswith("USDT"):
            clean_sym += "USDT"

    try:
        if mkt == MARKET_FOREX:
            candles = await fetch_forex_klines(clean_sym, interval, limit=200)
            sentiment = await _get_forex_pair_sentiment(clean_sym)
        else:
            candles = await fetch_klines(clean_sym, interval, limit=200)
            sentiment = await _get_cached_sentiment()

        indicators = calculate_all_indicators(candles)
        analysis = analyze_market_signals(
            candles, indicators, clean_sym, sentiment=sentiment, asset_class=mkt
        )
        sent = await send_signal_alert(analysis, interval, asset_class=mkt)
        return {"success": sent, "market": mkt, "message": "Alert sent" if sent else "Failed or Telegram unconfigured"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Mount static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
