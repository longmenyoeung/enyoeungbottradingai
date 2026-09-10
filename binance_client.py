"""
Binance Market Data Client (Public REST API)
Fetches real-time Kline/Candlestick data and ticker statistics without requiring API keys.
"""

from typing import Any, Dict, List, Optional
import httpx

# Primary and fallback Binance public API endpoints
BINANCE_API_BASES = [
    "https://data-api.binance.vision/api/v3",
    "https://api.binance.com/api/v3",
    "https://api1.binance.com/api/v3",
    "https://api3.binance.com/api/v3",
]

# Common intervals supported by Binance
VALID_INTERVALS = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"]

# Curated default top liquid pairs
DEFAULT_WATCHLIST = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "PEPEUSDT",
]


async def fetch_klines(
    symbol: str = "BTCUSDT", interval: str = "15m", limit: int = 200
) -> List[Dict[str, Any]]:
    """
    Fetch historical candlestick bars from Binance.
    Format returned per item:
      - time: unix timestamp in seconds
      - open, high, low, close, volume: floats
    """
    symbol = symbol.upper().strip()
    if interval not in VALID_INTERVALS:
        interval = "15m"

    params = {"symbol": symbol, "interval": interval, "limit": min(limit, 1000)}
    last_err = None

    for base_url in BINANCE_API_BASES:
        url = f"{base_url}/klines"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    raw_klines = response.json()
                    candles = []
                    for k in raw_klines:
                        candles.append(
                            {
                                "time": int(k[0] // 1000),
                                "open": float(k[1]),
                                "high": float(k[2]),
                                "low": float(k[3]),
                                "close": float(k[4]),
                                "volume": float(k[5]),
                                "close_time": int(k[6] // 1000),
                            }
                        )
                    return candles
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise last_err
    return []


async def fetch_ticker_24h(symbol: Optional[str] = None) -> Any:
    """Fetch 24-hour price change statistics for a symbol or all symbols."""
    params = {"symbol": symbol.upper().strip()} if symbol else {}
    last_err = None

    for base_url in BINANCE_API_BASES:
        url = f"{base_url}/ticker/24hr"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise last_err
    return []


async def get_top_symbols(limit: int = 15) -> List[Dict[str, Any]]:
    """
    Get top liquid USDT trading pairs from Binance sorted by quote volume.
    Falls back to curated DEFAULT_WATCHLIST if network issues or throttling occur.
    """
    try:
        all_tickers = await fetch_ticker_24h()
        usdt_tickers = [
            t
            for t in all_tickers
            if t["symbol"].endswith("USDT")
            and not t["symbol"].endswith("UPUSDT")
            and not t["symbol"].endswith("DOWNUSDT")
            and not t["symbol"].startswith("USDC")
            and not t["symbol"].startswith("FDUSD")
            and not t["symbol"].startswith("TUSD")
            and not t["symbol"].startswith("EUR")
        ]
        usdt_tickers.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)

        top = []
        for t in usdt_tickers[:limit]:
            top.append(
                {
                    "symbol": t["symbol"],
                    "price": float(t["lastPrice"]),
                    "change24h": float(t["priceChangePercent"]),
                    "volume": float(t["quoteVolume"]),
                    "high24h": float(t["highPrice"]),
                    "low24h": float(t["lowPrice"]),
                }
            )
        return top
    except Exception:
        return [{"symbol": s, "price": 0.0, "change24h": 0.0} for s in DEFAULT_WATCHLIST[:limit]]
