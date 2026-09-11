"""
Crypto Market Sentiment Module — Fear & Greed Index + Trending News.
Fetches live data from free public APIs (no API keys required):
- Fear & Greed Index: api.alternative.me
- Trending coins & news: CoinGecko public API
"""

from typing import Any, Dict, List
import httpx


async def fetch_fear_greed_index() -> Dict[str, Any]:
    """
    Fetch the current Crypto Fear & Greed Index from alternative.me.
    Returns a value from 0 (Extreme Fear) to 100 (Extreme Greed) and classification.
    """
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get("https://api.alternative.me/fng/?limit=1&format=json")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data"):
                    entry = data["data"][0]
                    value = int(entry.get("value", 50))
                    classification = entry.get("value_classification", "Neutral")

                    # Pro trader context for each zone
                    if value <= 10:
                        zone = "EXTREME_FEAR"
                        advice = "Maximum fear — historically the strongest buy zone. Smart money accumulates here."
                    elif value <= 25:
                        zone = "FEAR"
                        advice = "Market is fearful — contrarian opportunity. Look for bullish reversal setups."
                    elif value <= 45:
                        zone = "CAUTION"
                        advice = "Cautious market. Proceed with standard risk management."
                    elif value <= 55:
                        zone = "NEUTRAL"
                        advice = "Neutral sentiment — no strong directional bias from crowd psychology."
                    elif value <= 75:
                        zone = "GREED"
                        advice = "Market getting greedy — be cautious on longs. Tighten stop losses."
                    else:
                        zone = "EXTREME_GREED"
                        advice = "Extreme greed — high risk of pullback. Consider taking profits on longs."

                    return {
                        "value": value,
                        "classification": classification,
                        "zone": zone,
                        "advice": advice,
                        "source": "alternative.me",
                    }
    except Exception:
        pass

    return {
        "value": 50,
        "classification": "Neutral",
        "zone": "NEUTRAL",
        "advice": "Unable to fetch sentiment data — using neutral default.",
        "source": "fallback",
    }


async def fetch_trending_coins() -> List[Dict[str, Any]]:
    """
    Fetch trending coins from CoinGecko's free API for market context.
    Shows what the broader market is focused on right now.
    """
    trending = []
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get("https://api.coingecko.com/api/v3/search/trending")
            if resp.status_code == 200:
                data = resp.json()
                coins = data.get("coins", [])[:7]
                for item in coins:
                    coin = item.get("item", {})
                    trending.append({
                        "name": coin.get("name", ""),
                        "symbol": coin.get("symbol", "").upper(),
                        "market_cap_rank": coin.get("market_cap_rank", 0),
                        "score": coin.get("score", 0),
                    })
    except Exception:
        pass

    return trending


async def fetch_global_market_data() -> Dict[str, Any]:
    """
    Fetch global crypto market overview from CoinGecko:
    - Total market cap change %
    - BTC dominance
    - Number of active cryptocurrencies
    """
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get("https://api.coingecko.com/api/v3/global")
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return {
                    "total_market_cap_change_24h": round(data.get("market_cap_change_percentage_24h_usd", 0.0), 2),
                    "btc_dominance": round(data.get("market_cap_percentage", {}).get("btc", 0.0), 1),
                    "eth_dominance": round(data.get("market_cap_percentage", {}).get("eth", 0.0), 1),
                    "active_cryptos": data.get("active_cryptocurrencies", 0),
                }
    except Exception:
        pass

    return {
        "total_market_cap_change_24h": 0.0,
        "btc_dominance": 0.0,
        "eth_dominance": 0.0,
        "active_cryptos": 0,
    }


async def get_sentiment_summary() -> Dict[str, Any]:
    """
    Returns a complete sentiment snapshot for the trading bot:
    - Fear & Greed Index
    - Trending coins
    - Global market data
    """
    import asyncio
    fng, trending, global_data = await asyncio.gather(
        fetch_fear_greed_index(),
        fetch_trending_coins(),
        fetch_global_market_data(),
    )

    return {
        "fear_greed": fng,
        "trending_coins": trending,
        "global_market": global_data,
    }
