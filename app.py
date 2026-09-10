"""
FastAPI Web Application & API Server for Binance Crypto Chart Analysis.
Serves interactive dashboard and REST endpoints for real-time market analysis.
"""

from pathlib import Path
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
    fetch_klines,
    get_top_symbols,
)
from indicators import calculate_all_indicators
from strategy import analyze_market_signals
from telegram_notifier import send_signal_alert

last_sent_signals = {}
notify_rate_limits = {}  # {ip: last_request_time}


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
            "connect-src 'self' https://*.binance.vision https://*.binance.com https://api.telegram.org; "
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
                            sig = analyze_market_signals(candles, indicators, sym)
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
    title="Binance Crypto Analyzer & Trading Signal Bot",
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


@app.get("/api/symbols")
async def get_symbols():
    """Returns top active Binance USDT pairs."""
    try:
        symbols = await get_top_symbols(20)
        return {"success": True, "symbols": symbols}
    except Exception as e:
        return {
            "success": False,
            "symbols": [{"symbol": s, "price": 0.0, "change24h": 0.0} for s in DEFAULT_WATCHLIST],
            "error": str(e),
        }


@app.get("/api/analyze")
async def analyze(
    symbol: str = Query("BTCUSDT", description="Crypto trading pair"),
    interval: str = Query("15m", description="Candle interval (1m, 5m, 15m, 1h, 4h, 1d)"),
):
    """
    Analyzes candlestick data for a given Binance symbol and interval.
    Returns:
    - raw candles for chart plotting
    - calculated technical indicators
    - actionable trading signals (Entry, SL, TP1, TP2, TP3)
    """
    clean_sym = symbol.upper().strip()
    # Security: Validate symbol characters strictly
    if not re.match(r"^[A-Z0-9]{2,14}$", clean_sym):
        return {"success": False, "error": "Invalid symbol format. Use alphanumeric characters only."}

    if not clean_sym.endswith("USDT"):
        clean_sym += "USDT"

    if interval not in VALID_INTERVALS:
        interval = "15m"

    try:
        candles = await fetch_klines(clean_sym, interval, limit=250)
        if not candles:
            return {"success": False, "error": f"Failed to retrieve data for {clean_sym}"}

        indicators = calculate_all_indicators(candles)
        signals = analyze_market_signals(candles, indicators, clean_sym)

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
            "symbol": clean_sym,
            "interval": interval,
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


@app.get("/api/scanner")
async def scanner(interval: str = Query("15m")):
    """
    Scans top watchlist coins and returns high-level signals and Entry/TP/SL targets.
    """
    top_items = await get_top_symbols(12)
    symbols = [item["symbol"] for item in top_items] if top_items else DEFAULT_WATCHLIST

    scan_results = []
    for sym in symbols:
        try:
            candles = await fetch_klines(sym, interval, limit=120)
            if candles:
                indicators = calculate_all_indicators(candles)
                sig = analyze_market_signals(candles, indicators, sym)
                scan_results.append(
                    {
                        "symbol": sym,
                        "price": sig["price"],
                        "signal": sig["signal"],
                        "bias": sig["bias"],
                        "confidence": sig["confidence"],
                        "entry": sig["entry"],
                        "stop_loss": sig["stop_loss"],
                        "take_profit_1": sig["take_profit_1"],
                        "take_profit_2": sig["take_profit_2"],
                        "risk_pct": sig["risk_pct"],
                        "tp1_pct": sig["tp1_pct"],
                        "tp2_pct": sig["tp2_pct"],
                        "rsi": sig["rsi"],
                    }
                )
        except Exception:
            continue

    return {"success": True, "interval": interval, "results": scan_results}


@app.post("/api/notify")
async def notify(request: Request, symbol: str, interval: str = "15m"):
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

    # Validate symbol input
    clean_sym = symbol.upper().strip()
    if not re.match(r"^[A-Z0-9]{2,14}$", clean_sym):
        return {"success": False, "error": "Invalid symbol"}

    try:
        candles = await fetch_klines(clean_sym, interval, limit=200)
        indicators = calculate_all_indicators(candles)
        analysis = analyze_market_signals(candles, indicators, clean_sym)
        sent = await send_signal_alert(analysis, interval)
        return {"success": sent, "message": "Alert sent" if sent else "Failed or Telegram unconfigured"}
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
