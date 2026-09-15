"""
Forex Market Sentiment Module — DXY Dollar Strength, VIX Risk Regime & Session Context.

The crypto Fear & Greed Index (alternative.me) is crypto-specific, so FX pairs use
three institutional proxies instead:

1. DXY (US Dollar Index) strength — primary driver of every USD pair
2. VIX (CBOE Volatility Index) — global risk-on / risk-off regime
3. FX trading session — liquidity & volatility change dramatically per session

DXY and VIX candles come from Twelve Data (when the free-tier budget allows) with a
Yahoo Finance fallback, so the module degrades gracefully with no API key at all.
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from forex_client import (
    fetch_twelvedata_time_series,
    fetch_yahoo_chart,
    get_forex_session_summary,
    normalize_forex_pair,
    twelvedata_budget_available,
)

# Yahoo Finance symbols for the FX sentiment proxies
DXY_YAHOO_SYMBOL = "DX-Y.NYB"
VIX_YAHOO_SYMBOL = "^VIX"
DXY_TWELVEDATA_SYMBOL = "DXY"

# Currencies considered "safe havens" (bid up when volatility spikes)
SAFE_HAVEN_CURRENCIES = {"USD", "JPY", "CHF"}
# Currencies considered "risk-on" / commodity-linked
RISK_SENSITIVE_CURRENCIES = {"AUD", "NZD", "CAD", "EUR", "GBP"}


# =============================================================================
# PURE MAPPING HELPERS (unit-testable, no network)
# =============================================================================
def vix_risk_off_score(value: float) -> int:
    """Maps a VIX level (0-100 scale) to a 0-100 risk-off intensity score."""
    try:
        vix = float(value)
    except (TypeError, ValueError):
        return 50

    if vix <= 13:
        score = 20
    elif vix <= 15:
        score = 30
    elif vix <= 18:
        score = 42
    elif vix <= 22:
        score = 55
    elif vix <= 28:
        score = 70
    elif vix <= 35:
        score = 85
    else:
        score = 95
    return int(max(0, min(100, score)))


def vix_zone(score: int) -> str:
    """Human zone label for a risk-off score."""
    if score <= 30:
        return "RISK_ON"
    if score <= 48:
        return "CALM"
    if score <= 65:
        return "ELEVATED"
    if score <= 82:
        return "RISK_OFF"
    return "PANIC"


def map_usd_score_to_zone(score: float) -> Dict[str, str]:
    """Maps a 0-100 USD strength score (50 = neutral) to a labelled DXY zone."""
    value = int(max(0, min(100, round(float(score)))))
    if value <= 20:
        return {
            "zone": "EXTREME_DOLLAR_WEAKNESS",
            "classification": "Very Weak Dollar",
            "advice": "Aggressive USD selling — USD-quoted pairs (EURUSD, GBPUSD) get a strong tailwind.",
        }
    if value <= 40:
        return {
            "zone": "WEAK_DOLLAR",
            "classification": "Weak Dollar",
            "advice": "USD under pressure — favour long EUR/USD, GBP/USD, AUD/USD and short USD/JPY.",
        }
    if value <= 60:
        return {
            "zone": "NEUTRAL_DOLLAR",
            "classification": "Balanced Dollar",
            "advice": "No dominant USD trend — trade pair-specific structure and cross-currency flows.",
        }
    if value <= 80:
        return {
            "zone": "STRONG_DOLLAR",
            "classification": "Strong Dollar",
            "advice": "USD bid — favour long USD/JPY, USD/CHF, USD/CAD and short EUR/USD, GBP/USD.",
        }
    return {
        "zone": "EXTREME_DOLLAR_STRENGTH",
        "classification": "Very Strong Dollar",
        "advice": "USD squeeze in play — expect USD-quoted pairs to bleed while USD crosses extend.",
    }


def map_dxy_vix_to_sentiment_zone(score: float) -> str:
    """Maps a 0-100 pair-bullish score onto the strategy engine's sentiment zones."""
    value = max(0.0, min(100.0, float(score)))
    if value <= 10:
        return "EXTREME_FEAR"
    if value <= 25:
        return "FEAR"
    if value <= 45:
        return "CAUTION"
    if value <= 55:
        return "NEUTRAL"
    if value <= 75:
        return "GREED"
    return "EXTREME_GREED"


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def dxy_score_from_closes(closes: List[float], change_5d_pct: float = 0.0) -> int:
    """
    Builds a 0-100 USD strength score from daily DXY closes.

    - Position versus the 20-day mean (trend deviation) weighted at 12 pts per 1%
    - 5-day momentum weighted at 8 pts per 1%
    - 50 is neutral; >75 = strongly bid USD, <25 = heavily offered USD
    """
    series = [float(c) for c in closes if c]
    if len(series) < 5:
        return 50

    last = series[-1]
    window = series[-20:] if len(series) >= 20 else series
    mean = sum(window) / len(window)
    deviation_pct = ((last - mean) / mean * 100) if mean else 0.0

    return _clamp_score(50.0 + deviation_pct * 12.0 + float(change_5d_pct) * 8.0)


def sentiment_zone_advice(zone: str, symbol: str = "") -> str:
    """Strategy-engine advice string for an FX sentiment zone."""
    pair = normalize_forex_pair(symbol) if symbol else ""
    target = f" for {pair}" if pair else ""
    if zone in ("EXTREME_FEAR",):
        return f"Extreme FX pessimism{target} — contrarian reversal risk is elevated."
    if zone == "FEAR":
        return f"Sentiment is stretched against this direction{target} — watch for mean reversion."
    if zone == "CAUTION":
        return "Mild sentiment headwind — size positions normally."
    if zone == "NEUTRAL":
        return "Balanced USD/risk sentiment — no sentiment edge either way."
    if zone == "GREED":
        return f"Sentiment tailwind{target} — trend continuation favoured, trail stops."
    return f"Extreme crowding{target} — high pullback risk, take partial profits."


# =============================================================================
# LIVE PROXY FETCHERS (DXY & VIX)
# =============================================================================
def _dxy_fallback() -> Dict[str, Any]:
    """Neutral DXY snapshot used when every provider is unavailable."""
    zone = map_usd_score_to_zone(50)
    return {"value": 0.0, "change_pct": 0.0, "score": 50, "source": "fallback", **zone}


def _vix_fallback() -> Dict[str, Any]:
    """Neutral VIX snapshot used when every provider is unavailable."""
    score = 50
    return {
        "value": 0.0,
        "change_pct": 0.0,
        "score": score,
        "zone": vix_zone(score),
        "regime": "MIXED",
        "source": "fallback",
        "advice": "Volatility data unavailable — assume normal risk conditions.",
    }


def _pct_change(closes: List[float], bars: int) -> float:
    if len(closes) <= bars or not closes[-bars - 1]:
        return 0.0
    return round((closes[-1] - closes[-bars - 1]) / closes[-bars - 1] * 100, 2)


async def _fetch_proxy_closes(
    td_symbol: str, yahoo_symbol: str, limit: int = 30
) -> Tuple[List[float], str]:
    """Fetches daily closes for a proxy index, Twelve Data first then Yahoo Finance."""
    if twelvedata_budget_available():
        try:
            candles = await fetch_twelvedata_time_series(td_symbol, "1d", limit)
            if candles:
                return [c["close"] for c in candles], "twelvedata"
        except Exception:
            pass
    try:
        candles = await fetch_yahoo_chart(yahoo_symbol, "1d", limit)
        if candles:
            return [c["close"] for c in candles], "yahoo"
    except Exception:
        pass
    return [], "fallback"


async def fetch_dxy() -> Dict[str, Any]:
    """Fetches DXY (US Dollar Index) and converts it into a 0-100 USD strength score."""
    try:
        closes, source = await _fetch_proxy_closes(DXY_TWELVEDATA_SYMBOL, DXY_YAHOO_SYMBOL)
    except Exception:
        closes, source = [], "fallback"

    if not closes:
        return _dxy_fallback()

    change_5d = _pct_change(closes, 5)
    score = dxy_score_from_closes(closes, change_5d)
    return {
        "value": round(closes[-1], 3),
        "change_pct": change_5d,
        "score": score,
        "source": source,
        **map_usd_score_to_zone(score),
    }


async def fetch_vix() -> Dict[str, Any]:
    """Fetches VIX and converts it into a 0-100 risk-off intensity score."""
    try:
        closes, source = await _fetch_proxy_closes("VIX", VIX_YAHOO_SYMBOL)
    except Exception:
        closes, source = [], "fallback"

    if not closes:
        return _vix_fallback()

    change_5d = _pct_change(closes, 5)
    score = _clamp_score(vix_risk_off_score(closes[-1]) + max(-10.0, min(10.0, change_5d)))
    zone = vix_zone(score)
    if zone == "RISK_ON":
        advice = "Low volatility / risk-on: commodity FX (AUD, NZD) and EUR get a tailwind."
    elif zone == "CALM":
        advice = "Calm volatility regime — trend-following setups work best."
    elif zone == "ELEVATED":
        advice = "Volatility expanding — widen stops and reduce leverage."
    elif zone == "RISK_OFF":
        advice = "Risk-off: USD/JPY/CHF havens bid, high-beta FX vulnerable."
    else:
        advice = "Panic volatility — hunt for capitulation reversals, keep size small."

    return {
        "value": round(closes[-1], 2),
        "change_pct": change_5d,
        "score": score,
        "zone": zone,
        "regime": "RISK_OFF" if score >= 60 else ("RISK_ON" if score <= 40 else "MIXED"),
        "source": source,
        "advice": advice,
    }



# =============================================================================
# AGGREGATED SENTIMENT (API / UI payload)
# =============================================================================
def _rate_differential_note(pair: str) -> str:
    """Short educational note about what actually drives this pair."""
    base, quote = pair[:3], pair[3:]
    if "JPY" in pair:
        return "JPY is a funding/haven currency — risk-off flows and yield spreads move this pair."
    if quote in ("TRY", "ZAR", "MXN", "NOK", "SEK", "SGD", "HKD"):
        return "High-beta exotic: wider spreads and headline gap risk — trade with smaller size."
    if base in RISK_SENSITIVE_CURRENCIES and quote in RISK_SENSITIVE_CURRENCIES:
        return "Cross pair: driven by relative rate expectations rather than pure USD flows."
    return "USD leg is the primary driver — track DXY direction for context."


async def get_forex_sentiment_summary() -> Dict[str, Any]:
    """
    Complete FX sentiment snapshot (mirrors sentiment.get_sentiment_summary for crypto):
    - dxy: Dollar Index level, 5d change and 0-100 USD strength score/zone
    - vix: volatility level and risk-on/risk-off regime
    - session: active FX session(s), liquidity and next open time
    """
    dxy, vix = await asyncio.gather(fetch_dxy(), fetch_vix())
    session = get_forex_session_summary()

    if dxy["score"] >= 60:
        usd_bias = "BULLISH"
    elif dxy["score"] <= 40:
        usd_bias = "BEARISH"
    else:
        usd_bias = "NEUTRAL"

    summary = (
        f"DXY {dxy['value']} ({dxy['change_pct']:+.2f}%) — {dxy['classification']}; "
        f"VIX {vix['value']} — {vix['zone']} ({vix['regime']}); {session['description']}"
    )

    return {
        "dxy": dxy,
        "vix": vix,
        "session": session,
        "market_status": session,
        "usd_bias": usd_bias,
        "risk_regime": vix["regime"],
        "gauge": {
            "value": dxy["score"],
            "zone": dxy["zone"],
            "classification": dxy["classification"],
            "advice": dxy["advice"],
        },
        "summary": summary,
    }


def build_forex_sentiment_for_pair(
    symbol: str,
    summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Converts the macro FX snapshot into a pair-aware sentiment payload shaped exactly like
    the crypto Fear & Greed payload, so strategy Layer 8 works for both asset classes.

    Logic:
    - USD base pairs (USDJPY, USDTRY): score = DXY strength score
    - USD quote pairs (EURUSD, GBPUSD): score = 100 - DXY strength score
    - Crosses (EURGBP, AUDJPY): driven by the VIX risk regime instead
    - Safe-haven legs gain when VIX spikes; risk currencies lose
    """
    pair = normalize_forex_pair(symbol)
    base, quote = (pair[:3], pair[3:]) if len(pair) == 6 else ("", "")

    data = summary or {}
    dxy = data.get("dxy") or {}
    vix = data.get("vix") or {}
    session = data.get("session") or get_forex_session_summary()

    usd_score = float(dxy.get("score", 50))
    risk_off = float(vix.get("score", 50))

    usd_is_base = base == "USD"
    usd_is_quote = quote == "USD"
    non_usd = quote if usd_is_base else base

    if usd_is_base:
        pair_score = usd_score
    elif usd_is_quote:
        pair_score = 100.0 - usd_score
    else:
        pair_score = 50.0

    if usd_is_base or usd_is_quote:
        if non_usd in SAFE_HAVEN_CURRENCIES:
            pair_score += (risk_off - 50.0) * 0.20
        elif non_usd in RISK_SENSITIVE_CURRENCIES:
            pair_score -= (risk_off - 50.0) * 0.25
    else:
        if base in RISK_SENSITIVE_CURRENCIES:
            pair_score = 50.0 - (risk_off - 50.0) * 0.20
        elif base in SAFE_HAVEN_CURRENCIES:
            pair_score = 50.0 + (risk_off - 50.0) * 0.20

    score = _clamp_score(pair_score)
    zone = map_dxy_vix_to_sentiment_zone(score)
    dxy_zone_info = dxy if dxy.get("classification") else map_usd_score_to_zone(usd_score)
    advice = sentiment_zone_advice(zone, pair)

    context = {
        "pair": pair,
        "usd_is_base": usd_is_base,
        "usd_is_quote": usd_is_quote,
        "dxy_value": dxy.get("value", 0.0),
        "dxy_change_pct": dxy.get("change_pct", 0.0),
        "dxy_score": _clamp_score(usd_score),
        "dxy_zone": dxy_zone_info.get("zone", "NEUTRAL_DOLLAR"),
        "dxy_classification": dxy_zone_info.get("classification", "Balanced Dollar"),
        "dxy_advice": dxy.get("advice", dxy_zone_info.get("advice", "")),
        "vix_value": vix.get("value", 0.0),
        "vix_zone": vix.get("zone", "CALM"),
        "vix_regime": vix.get("regime", "MIXED"),
        "risk_off_score": _clamp_score(risk_off),
        "session": session,
        "session_description": session.get("description", ""),
        "liquidity": session.get("liquidity", "UNKNOWN"),
        "pair_sentiment_score": score,
        "pair_sentiment_zone": zone,
        "rate_differential_note": _rate_differential_note(pair) if pair else "",
    }
    context["description"] = (
        f"{pair}: DXY {context['dxy_value']} ({context['dxy_change_pct']:+.2f}%, "
        f"{context['dxy_classification']}) with VIX {context['vix_value']} → {context['vix_zone']} "
        f"({context['vix_regime']}); {context['session_description']}."
    )

    return {
        "fear_greed": {
            "value": score,
            "classification": f"FX {context['dxy_classification']}",
            "zone": zone,
            "advice": advice,
            "source": "forex_dxy_vix",
        },
        "forex_context": context,
        "source": "forex_dxy_vix",
    }


async def get_forex_sentiment_for_pair(symbol: str) -> Dict[str, Any]:
    """Async convenience wrapper: fetches the macro snapshot then derives pair sentiment."""
    summary = await get_forex_sentiment_summary()
    return build_forex_sentiment_for_pair(symbol, summary)

