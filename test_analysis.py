"""
Automated unit & integration verification for trading bot indicators and strategy.
Covers both asset classes: Binance crypto pairs and Forex currency pairs.
"""

import asyncio
from datetime import datetime, timezone
from binance_client import fetch_klines
from indicators import (
    calculate_all_indicators,
    compute_ema,
    compute_rsi,
    compute_macd,
    compute_atr,
    detect_market_structure,
    detect_candle_patterns,
    compute_volume_profile,
    compute_bollinger_squeeze,
    compute_bollinger_bands,
)
from strategy import (
    analyze_market_signals,
    ASSET_CLASS_PARAMS,
    _asset_price_decimals,
    _describe_forex_context,
)
from sentiment import get_sentiment_summary
from forex_client import (
    FOREX_CATEGORIES,
    DEFAULT_FOREX_WATCHLIST,
    aggregate_candles,
    forex_pip_size,
    forex_price_decimals,
    forex_symbol_formats,
    get_active_forex_sessions,
    get_category_for_forex_pair,
    get_forex_session_summary,
    is_forex_market_open,
    is_forex_pair,
    normalize_forex_pair,
    normalize_twelvedata_payload,
    normalize_yahoo_payload,
    to_pips,
)
from forex_sentiment import (
    build_forex_sentiment_for_pair,
    dxy_score_from_closes,
    get_forex_sentiment_summary,
    map_dxy_vix_to_sentiment_zone,
    map_usd_score_to_zone,
    vix_risk_off_score,
)
from telegram_notifier import build_alert_text
import numpy as np


def test_indicator_math():
    prices = np.array([100 + i + (i % 3) for i in range(50)], dtype=np.float64)
    ema = compute_ema(prices, 10)
    assert not np.isnan(ema[-1])
    assert len(ema) == 50

    rsi = compute_rsi(prices, 14)
    assert not np.isnan(rsi[-1])
    assert 0 <= rsi[-1] <= 100

    macd = compute_macd(prices, 12, 26, 9)
    assert "macd" in macd and "signal" in macd and "histogram" in macd

    highs = prices + 2.0
    lows = prices - 2.0
    atr = compute_atr(highs, lows, prices, 14)
    assert atr[-1] > 0


def test_strategy_signals():
    # Mock bullish candles
    candles = []
    base_time = 1700000000
    price = 50000.0
    for i in range(100):
        price += (i * 0.5)
        candles.append({
            "time": base_time + i * 900,
            "open": price - 10,
            "high": price + 20,
            "low": price - 15,
            "close": price,
            "volume": 1000.0,
            "close_time": base_time + (i + 1) * 900 - 1
        })

    indicators = calculate_all_indicators(candles)
    analysis = analyze_market_signals(candles, indicators, "BTCUSDT")

    assert "signal" in analysis
    assert "entry" in analysis
    assert "stop_loss" in analysis
    assert "take_profit_1" in analysis
    assert "take_profit_2" in analysis
    assert analysis["entry"] > 0
    assert analysis["stop_loss"] > 0
    assert analysis["take_profit_1"] > 0
    assert analysis["take_profit_2"] > 0

    if analysis["bias"] == "LONG":
        assert analysis["stop_loss"] < analysis["entry"]
        assert analysis["take_profit_1"] > analysis["entry"]
        assert analysis["take_profit_2"] > analysis["take_profit_1"]
    else:
        assert analysis["stop_loss"] > analysis["entry"]
        assert analysis["take_profit_1"] < analysis["entry"]
        assert analysis["take_profit_2"] < analysis["take_profit_1"]


def _mock_candles(n=120, start=50000.0, drift=0.4):
    """Build a synthetic uptrending candle series with varied volume."""
    candles = []
    base_time = 1700000000
    price = start
    for i in range(n):
        price += i * drift
        candles.append({
            "time": base_time + i * 900,
            "open": price - 10,
            "high": price + 20,
            "low": price - 15,
            "close": price,
            "volume": 1000.0 + (i % 6) * 300.0,
            "close_time": base_time + (i + 1) * 900 - 1,
        })
    return candles


def test_indicator_layer_functions():
    """Directly exercise the new professional indicator helpers (Layers 1-6)."""
    candles = _mock_candles(80)
    highs = np.array([c["high"] for c in candles], dtype=np.float64)
    lows = np.array([c["low"] for c in candles], dtype=np.float64)
    closes = np.array([c["close"] for c in candles], dtype=np.float64)
    volumes = np.array([c["volume"] for c in candles], dtype=np.float64)

    ms = detect_market_structure(highs, lows, closes, lookback=4)
    assert ms["trend"] in ("UPTREND", "DOWNTREND", "RANGING")
    assert "bos_direction" in ms and "choch_direction" in ms

    vp = compute_volume_profile(closes, volumes, period=20)
    assert vp["volume_ratio"] > 0
    assert "accumulation" in vp

    cp = detect_candle_patterns(candles)
    assert isinstance(cp["patterns"], list)

    bb = compute_bollinger_bands(closes, 20, 2.0)
    bbs = compute_bollinger_squeeze(closes, bb["upper"], bb["lower"], bb["middle"])
    assert "is_squeeze" in bbs
    assert "band_walk" in bbs


def test_professional_layers():
    """Verify the 8-layer professional intelligence engine output contract."""
    candles = _mock_candles(120)
    indicators = calculate_all_indicators(candles)

    # --- Professional layers exist in the indicator engine ---
    for key in ("market_structure", "volume_profile", "candle_patterns", "bb_squeeze"):
        assert key in indicators, f"Missing indicator layer: {key}"

    # --- Strategy output contract ---
    analysis = analyze_market_signals(candles, indicators, "BTCUSDT")
    for key in (
        "signal", "grade", "confidence", "entry_strategy", "entry_quality",
        "management_advice", "market_structure", "volume_analysis",
        "candle_patterns_summary", "bb_squeeze_active", "layer_scores",
        "rr_gate_passed", "narrative",
    ):
        assert key in analysis, f"Missing strategy field: {key}"

    assert analysis["grade"] in ("A+", "A", "B", "C", "D")
    assert 0 <= analysis["confidence"] <= 100

    # Weighted 100-point confluence budget
    total_weight = sum(v["max"] for v in analysis["layer_scores"].values())
    assert total_weight == 100, f"Layer weights should total 100, got {total_weight}"

    # Monotonic take-profit ladder holds with dynamic (Bollinger/Fib) targets
    if analysis["bias"] == "LONG":
        assert analysis["take_profit_1"] < analysis["take_profit_2"] < analysis["take_profit_3"]
    else:
        assert analysis["take_profit_1"] > analysis["take_profit_2"] > analysis["take_profit_3"]


async def async_sentiment_test():
    """Verify the sentiment module returns a well-formed summary (graceful offline)."""
    summary = await get_sentiment_summary()
    assert "fear_greed" in summary and "trending_coins" in summary and "global_market" in summary
    fng = summary["fear_greed"]
    assert 0 <= fng["value"] <= 100
    print(f"Sentiment: Fear & Greed = {fng['value']} ({fng['classification']}) | source={fng['source']}")


async def async_integration_test():
    candles = await fetch_klines("BTCUSDT", "15m", limit=150)
    assert len(candles) >= 30
    indicators = calculate_all_indicators(candles)
    sentiment = await get_sentiment_summary()
    analysis = analyze_market_signals(candles, indicators, "BTCUSDT", sentiment=sentiment)
    print(f"Live Test Result for BTCUSDT: {analysis['signal']} [Grade {analysis['grade']}] at ${analysis['price']}")
    print(f"Entry: ${analysis['entry']} | SL: ${analysis['stop_loss']} | TP1: ${analysis['take_profit_1']} | TP2: ${analysis['take_profit_2']} | TP3: ${analysis['take_profit_3']}")
    print(f"Structure: {analysis['market_structure'].get('trend')} | Entry quality: {analysis['entry_quality']} | R:R gate: {analysis['rr_gate_passed']}")
    print(f"Entry strategy: {analysis['entry_strategy']}")

    # High-volatility meme coin sanitation check
    pepe = await fetch_klines("PEPEUSDT", "15m", limit=150)
    if pepe and len(pepe) >= 30:
        pepe_ind = calculate_all_indicators(pepe)
        pepe_sig = analyze_market_signals(pepe, pepe_ind, "PEPEUSDT", sentiment=sentiment)
        assert pepe_sig["entry"] > 0 and pepe_sig["stop_loss"] > 0
        assert pepe_sig["grade"] in ("A+", "A", "B", "C", "D")
        print(f"PEPEUSDT handled: {pepe_sig['signal']} [Grade {pepe_sig['grade']}]")


def _mock_forex_candles(n=140, start=1.08500, drift=0.000012, symbol="EURUSD"):
    """Build a synthetic EURUSD-style uptrend series with tick-volume noise."""
    candles = []
    base_time = 1700000000
    price = start
    for i in range(n):
        price += drift * (1 + (i % 5) * 0.1)
        pip = forex_pip_size(symbol)
        candles.append({
            "time": base_time + i * 900,
            "open": price - pip * 0.6,
            "high": price + pip * 1.8,
            "low": price - pip * 1.6,
            "close": price,
            "volume": 1200.0 + (i % 7) * 95.0,
            "close_time": base_time + (i + 1) * 900 - 1,
        })
    return candles


# =============================================================================
# FOREX: SYMBOL, CATEGORY & PIP HELPERS
# =============================================================================
def test_forex_symbol_normalization():
    assert normalize_forex_pair("eurusd") == "EURUSD"
    assert normalize_forex_pair("EUR/USD") == "EURUSD"
    assert normalize_forex_pair("eur_usd") == "EURUSD"
    assert normalize_forex_pair("EURUSD=X") == "EURUSD"

    assert is_forex_pair("EURUSD") is True
    assert is_forex_pair("USDJPY") is True
    assert is_forex_pair("usd/try") is True
    assert is_forex_pair("BTCUSDT") is False
    assert is_forex_pair("ETHBTC") is False
    assert is_forex_pair("PEPE") is False

    td_symbol, yahoo_symbol = forex_symbol_formats("usdjpy")
    assert td_symbol == "USD/JPY"
    assert yahoo_symbol == "USDJPY=X"


def test_forex_category_classification():
    assert get_category_for_forex_pair("EURUSD") == "majors"
    assert get_category_for_forex_pair("GBPJPY") == "minors"
    assert get_category_for_forex_pair("USDTRY") == "exotics"
    # Not in the curated list but inferable from the currency pair shape
    assert get_category_for_forex_pair("EURCAD") == "minors"
    assert get_category_for_forex_pair("USDPLN") == "exotics"

    # Universe covers majors + minors + exotics with 28+ pairs
    assert set(FOREX_CATEGORIES.keys()) == {"majors", "minors", "exotics"}
    assert len(DEFAULT_FOREX_WATCHLIST) >= 28
    assert len(set(DEFAULT_FOREX_WATCHLIST)) == len(DEFAULT_FOREX_WATCHLIST)


def test_forex_price_formatting():
    assert forex_price_decimals("EURUSD") == 5
    assert forex_price_decimals("GBPUSD") == 5
    assert forex_price_decimals("USDJPY") == 3
    assert forex_price_decimals("CADJPY") == 3

    assert forex_pip_size("EURUSD") == 0.0001
    assert forex_pip_size("USDJPY") == 0.01

    assert to_pips(0.0042, "EURUSD") == 42.0
    assert to_pips(-0.15, "USDJPY") == 15.0

    # Strategy helper resolves pip precision per asset class
    assert _asset_price_decimals(1.085, "EURUSD", "forex") == 5
    assert _asset_price_decimals(150.25, "USDJPY", "forex") == 3
    assert _asset_price_decimals(1.085, "EURUSD", "crypto") == 4


# =============================================================================
# FOREX: CANDLE NORMALIZATION (Twelve Data / Yahoo Finance)
# =============================================================================
def test_forex_candle_normalization():
    td_payload = {
        "meta": {"symbol": "EUR/USD", "interval": "15min"},
        "values": [
            {"datetime": "2024-05-01 12:15:00", "open": "1.08500", "high": "1.08620",
             "low": "1.08460", "close": "1.08590", "volume": "1420"},
            {"datetime": "2024-05-01 12:00:00", "open": "1.08420", "high": "1.08540",
             "low": "1.08390", "close": "1.08500", "volume": "1210"},
        ],
        "status": "ok",
    }
    candles = normalize_twelvedata_payload(td_payload, "15m")
    assert len(candles) == 2
    first, second = candles[0], candles[1]
    assert set(first.keys()) == {"time", "open", "high", "low", "close", "volume", "close_time"}
    assert first["time"] < second["time"]  # ascending order guaranteed
    assert first["open"] == 1.08420 and second["close"] == 1.08590
    assert second["close_time"] - second["time"] == 900 - 1

    # Provider error payloads are surfaced, never silently treated as candles
    try:
        normalize_twelvedata_payload({"code": 429, "message": "rate limit", "status": "error"}, "15m")
        raise AssertionError("Expected ValueError for Twelve Data error payload")
    except ValueError:
        pass

    yahoo_payload = {
        "chart": {
            "error": None,
            "result": [{
                "meta": {"symbol": "EURUSD=X"},
                "timestamp": [1714564800, 1714565700, 1714566600],
                "indicators": {"quote": [{
                    "open": [1.0850, None, 1.0860],
                    "high": [1.0855, None, 1.0865],
                    "low": [1.0845, None, 1.0855],
                    "close": [1.0852, None, 1.0862],
                    "volume": [1000, None, 1100],
                }]},
            }],
        }
    }
    y_candles = normalize_yahoo_payload(yahoo_payload, "15m")
    assert len(y_candles) == 2  # null (gap) candle skipped
    assert y_candles[0]["close"] == 1.0852
    assert y_candles[1]["volume"] == 1100.0

    # 4h aggregation from 1h candles (Yahoo has no native 4h interval)
    hourly = [{
        "time": 1700000000 + i * 3600,
        "open": 1.08 + i * 0.0001,
        "high": 1.0850 + i * 0.0001,
        "low": 1.0790 + i * 0.0001,
        "close": 1.0840 + i * 0.0001,
        "volume": 100.0,
        "close_time": 1700000000 + (i + 1) * 3600 - 1,
    } for i in range(8)]
    aggregated = aggregate_candles(hourly, 4)
    assert len(aggregated) == 2
    assert aggregated[0]["open"] == hourly[0]["open"]
    assert aggregated[0]["close"] == hourly[3]["close"]
    assert aggregated[0]["high"] == max(c["high"] for c in hourly[:4])
    assert aggregated[0]["volume"] == 400.0


# =============================================================================
# FOREX: MARKET HOURS & SESSIONS
# =============================================================================
def test_forex_market_hours():
    wednesday = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)   # mid-week
    friday_close = datetime(2026, 9, 18, 21, 30, tzinfo=timezone.utc)
    saturday = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    sunday_pre = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    sunday_open = datetime(2026, 9, 20, 22, 0, tzinfo=timezone.utc)

    assert is_forex_market_open(wednesday) is True
    assert is_forex_market_open(friday_close) is False
    assert is_forex_market_open(saturday) is False
    assert is_forex_market_open(sunday_pre) is False
    assert is_forex_market_open(sunday_open) is True

    # Naive datetimes are treated as UTC
    assert is_forex_market_open(datetime(2026, 9, 16, 12, 0)) is True

    # Sessions: Wednesday 13:00 UTC = London + New York overlap
    session = get_forex_session_summary(wednesday)
    assert session["is_open"] is True
    assert session["overlap"] is True
    assert session["liquidity"] == "HIGH"
    keys = [s["key"] for s in session["active_sessions"]]
    assert "LONDON" in keys and "NEW_YORK" in keys
    assert session["primary_session"] in ("LONDON", "NEW_YORK")

    # Monday 01:00 UTC = Tokyo only (Sydney has closed)
    monday_asia = datetime(2026, 9, 14, 1, 0, tzinfo=timezone.utc)
    asia_keys = [s["key"] for s in get_active_forex_sessions(monday_asia)]
    assert "TOKYO" in asia_keys and "NEW_YORK" not in asia_keys

    # Weekend → no active sessions and a next-open timestamp
    closed = get_forex_session_summary(saturday)
    assert closed["is_open"] is False
    assert closed["active_sessions"] == []
    assert closed["liquidity"] == "CLOSED"
    assert closed["next_open_utc"]


# =============================================================================
# FOREX: SENTIMENT (DXY / VIX → pair-aware zones)
# =============================================================================
def test_dxy_sentiment_zone_mapping():
    assert map_usd_score_to_zone(90)["zone"] == "EXTREME_DOLLAR_STRENGTH"
    assert map_usd_score_to_zone(70)["zone"] == "STRONG_DOLLAR"
    assert map_usd_score_to_zone(50)["zone"] == "NEUTRAL_DOLLAR"
    assert map_usd_score_to_zone(30)["zone"] == "WEAK_DOLLAR"
    assert map_usd_score_to_zone(10)["zone"] == "EXTREME_DOLLAR_WEAKNESS"

    assert map_dxy_vix_to_sentiment_zone(90) == "EXTREME_GREED"
    assert map_dxy_vix_to_sentiment_zone(60) == "GREED"
    assert map_dxy_vix_to_sentiment_zone(50) == "NEUTRAL"
    assert map_dxy_vix_to_sentiment_zone(30) == "CAUTION"
    assert map_dxy_vix_to_sentiment_zone(20) == "FEAR"
    assert map_dxy_vix_to_sentiment_zone(8) == "EXTREME_FEAR"

    assert vix_risk_off_score(11) <= 30
    assert 40 <= vix_risk_off_score(17) <= 60
    assert vix_risk_off_score(40) >= 85

    # DXY score reacts to trend deviation and 5-day momentum
    flat = [100.0] * 25
    assert dxy_score_from_closes(flat, 0.0) == 50
    assert dxy_score_from_closes([100.0 + i * 0.5 for i in range(25)], 1.0) > 60
    assert dxy_score_from_closes([100.0 - i * 0.5 for i in range(25)], -1.0) < 40


def test_forex_pair_sentiment_logic():
    summary = {
        "dxy": {"value": 105.2, "change_pct": 1.1, "score": 85, **map_usd_score_to_zone(85)},
        "vix": {"value": 14.2, "score": 30, "zone": "RISK_ON", "regime": "RISK_ON"},
        "session": get_forex_session_summary(datetime(2026, 9, 16, 13, 0, tzinfo=timezone.utc)),
    }

    usd_jpy = build_forex_sentiment_for_pair("USDJPY", summary)
    eur_usd = build_forex_sentiment_for_pair("EURUSD", summary)
    eur_gbp = build_forex_sentiment_for_pair("EURGBP", summary)

    # Strong USD is bullish for a USD-base pair and bearish for a USD-quote pair
    assert usd_jpy["fear_greed"]["value"] > 70
    assert eur_usd["fear_greed"]["value"] < 30
    assert eur_usd["fear_greed"]["zone"] in ("EXTREME_FEAR", "FEAR")

    # Cross pairs are driven by the risk regime, not DXY
    assert 45 <= eur_gbp["fear_greed"]["value"] <= 55

    ctx = eur_usd["forex_context"]
    assert ctx["usd_is_quote"] is True and ctx["usd_is_base"] is False
    assert ctx["dxy_score"] == 85
    assert ctx["vix_zone"] == "RISK_ON"
    assert "DXY" in ctx["description"]

    # Layer-8 reasons are generated from the FX context
    reasons = _describe_forex_context(ctx, "EURUSD")
    assert len(reasons) >= 3
    assert any("DXY" in r for r in reasons)
    assert any("VIX" in r for r in reasons)
    assert any("FX session" in r for r in reasons)


# =============================================================================
# FOREX: STRATEGY ENGINE (asset_class-aware) & TELEGRAM ALERTS
# =============================================================================
def test_forex_strategy_engine():
    candles = _mock_forex_candles(140)
    indicators = calculate_all_indicators(candles)

    summary = {
        "dxy": {"value": 104.0, "change_pct": 0.2, "score": 58, **map_usd_score_to_zone(58)},
        "vix": {"value": 15.5, "score": 38, "zone": "CALM", "regime": "MIXED"},
        "session": get_forex_session_summary(datetime(2026, 9, 16, 13, 0, tzinfo=timezone.utc)),
    }
    sentiment = build_forex_sentiment_for_pair("EURUSD", summary)

    analysis = analyze_market_signals(
        candles, indicators, "EURUSD", sentiment=sentiment, asset_class="forex"
    )

    # Output contract
    for key in (
        "signal", "grade", "confidence", "entry", "stop_loss", "take_profit_1",
        "take_profit_2", "take_profit_3", "asset_class", "price_decimals", "pip_size",
        "risk_pips", "tp1_pips", "atr_pips", "strategy_profile", "layer_scores",
        "rr_gate_passed", "narrative", "forex_context",
    ):
        assert key in analysis, f"Missing forex strategy field: {key}"

    assert analysis["asset_class"] == "forex"
    assert analysis["symbol"] == "EURUSD"
    assert analysis["price_decimals"] == 5
    assert analysis["pip_size"] == 0.0001
    assert analysis["forex_context"] is not None
    assert analysis["grade"] in ("A+", "A", "B", "C", "D")

    # Layer weights still total the 100-point confluence budget
    assert sum(v["max"] for v in analysis["layer_scores"].values()) == 100

    # FX uses wider ATR stops and a reduced tick-volume weighting
    fx_params = ASSET_CLASS_PARAMS["forex"]
    assert analysis["layer_scores"]["volume"]["reliability"] == fx_params["volume_reliability"]
    assert analysis["volume_analysis"]["reliability"] == fx_params["volume_reliability"]
    assert analysis["strategy_profile"]["atr_sl_multiplier"] == fx_params["atr_sl_multiplier"] == 2.0

    # Pip distances are consistent with the rounded price levels
    assert analysis["risk_pips"] > 0
    assert abs(analysis["risk_pips"] - to_pips(analysis["entry"] - analysis["stop_loss"], "EURUSD")) < 1.0
    assert analysis["tp1_pips"] > 0

    # Prices are rounded to pip precision and the TP ladder stays monotonic
    for key in ("entry", "stop_loss", "take_profit_1", "take_profit_2", "take_profit_3"):
        assert round(analysis[key], 5) == analysis[key]
        assert analysis[key] > 0

    if analysis["bias"] == "LONG":
        assert analysis["stop_loss"] < analysis["entry"]
        assert analysis["entry"] < analysis["take_profit_1"] < analysis["take_profit_2"] < analysis["take_profit_3"]
    else:
        assert analysis["stop_loss"] > analysis["entry"]
        assert analysis["entry"] > analysis["take_profit_1"] > analysis["take_profit_2"] > analysis["take_profit_3"]

    # Stop distance respects the FX bounds (≈15 pips floor … 2.5% cap)
    stop_pct = abs(analysis["entry"] - analysis["stop_loss"]) / analysis["entry"] * 100
    assert 0.1 <= stop_pct <= 2.5

    # JPY-quoted pairs use 3 decimals with a 0.01 pip
    jpy_candles = _mock_forex_candles(140, start=150.25, drift=0.0018, symbol="USDJPY")
    jpy_analysis = analyze_market_signals(
        jpy_candles, calculate_all_indicators(jpy_candles), "USDJPY", asset_class="forex"
    )
    assert jpy_analysis["price_decimals"] == 3
    assert jpy_analysis["pip_size"] == 0.01
    assert jpy_analysis["atr_pips"] > 0


def test_crypto_strategy_unchanged_by_asset_class_default():
    """Default asset_class must keep the legacy crypto behaviour and precision."""
    candles = _mock_candles(120)
    crypto_analysis = analyze_market_signals(candles, calculate_all_indicators(candles), "BTCUSDT")
    assert crypto_analysis["asset_class"] == "crypto"
    assert crypto_analysis["pip_size"] is None
    assert crypto_analysis["risk_pips"] is None
    assert crypto_analysis["price_decimals"] == 2  # BTC-scale price → 2 decimals
    assert crypto_analysis["layer_scores"]["volume"]["reliability"] == 1.0


def test_forex_insufficient_data_contract():
    analysis = analyze_market_signals([], {}, "EURUSD", asset_class="forex")
    assert analysis["signal"] == "INSUFFICIENT_DATA"
    assert analysis["asset_class"] == "forex"
    assert analysis["price_decimals"] == 5
    assert analysis["pip_size"] == 0.0001
    assert analysis["strategy_profile"]["atr_sl_multiplier"] == 2.0


def test_telegram_alert_formatting():
    forex_text = build_alert_text({
        "symbol": "EURUSD",
        "signal": "BUY",
        "bias": "LONG",
        "price": 1.08540,
        "entry": 1.08500,
        "stop_loss": 1.08300,
        "take_profit_1": 1.08800,
        "take_profit_2": 1.09250,
        "risk_pct": 0.18,
        "tp1_pct": 0.28,
        "tp2_pct": 0.69,
        "price_decimals": 5,
        "risk_pips": 20.0,
        "tp1_pips": 30.0,
        "reasons": ["💵 DXY 104.0 (+0.20%) — Balanced Dollar; USD is the quote leg of EURUSD"],
    }, "15m", asset_class="forex")
    assert "FOREX SIGNAL: EURUSD" in forex_text
    assert "1.08500" in forex_text  # pip precision
    assert "$1.08500" not in forex_text
    assert "20.0 pips" in forex_text

    jpy_text = build_alert_text({"symbol": "USDJPY", "signal": "SELL", "price": 150.123,
                                 "entry": 150.12, "stop_loss": 150.32, "take_profit_1": 149.82},
                                "1h", asset_class="forex")
    assert "150.123" in jpy_text  # 3 decimals for JPY pairs

    crypto_text = build_alert_text({"symbol": "BTCUSDT", "signal": "BUY", "price": 65000.5,
                                    "entry": 65000.0, "stop_loss": 64000.0, "take_profit_1": 66500.0,
                                    "take_profit_2": 67500.0})
    assert "BINANCE SIGNAL: BTCUSDT" in crypto_text
    assert "$65,000.0000" in crypto_text


async def async_forex_sentiment_test():
    """FX sentiment snapshot must always be well-formed, even fully offline."""
    summary = await get_forex_sentiment_summary()
    assert "dxy" in summary and "vix" in summary and "session" in summary
    assert 0 <= summary["dxy"]["score"] <= 100
    assert summary["dxy"]["zone"] in (
        "EXTREME_DOLLAR_WEAKNESS", "WEAK_DOLLAR", "NEUTRAL_DOLLAR",
        "STRONG_DOLLAR", "EXTREME_DOLLAR_STRENGTH",
    )
    assert summary["vix"]["regime"] in ("RISK_ON", "MIXED", "RISK_OFF")
    assert summary["usd_bias"] in ("BULLISH", "BEARISH", "NEUTRAL")
    print(f"FX sentiment: {summary['summary']}")


async def async_forex_integration_test():
    """Live FX pipeline check (gracefully skipped when providers are unreachable)."""
    from forex_client import fetch_forex_klines

    candles = []
    try:
        candles = await fetch_forex_klines("EURUSD", "15m", limit=150)
    except Exception as exc:
        print(f"Forex live fetch unavailable ({exc}) — skipping live FX check")

    if not candles or len(candles) < 30:
        print("No live FX candles available (offline or provider throttled) — skipping live FX check")
        return

    indicators = calculate_all_indicators(candles)
    summary = await get_forex_sentiment_summary()
    sentiment = build_forex_sentiment_for_pair("EURUSD", summary)
    analysis = analyze_market_signals(
        candles, indicators, "EURUSD", sentiment=sentiment, asset_class="forex"
    )

    assert analysis["asset_class"] == "forex"
    assert analysis["entry"] > 0 and analysis["stop_loss"] > 0
    print(
        f"Live FX Test EURUSD: {analysis['signal']} [Grade {analysis['grade']}] "
        f"@ {analysis['entry']} | SL {analysis['stop_loss']} ({analysis['risk_pips']} pips) | "
        f"TP1 {analysis['take_profit_1']} ({analysis['tp1_pips']} pips)"
    )


def test_short_bias_risk_paths():
    """Downtrend (SHORT bias) must produce a full risk plan for both asset classes."""
    # Crypto downtrend
    base_time = 1700000000
    price = 60000.0
    crypto_candles = []
    for i in range(130):
        price -= i * 0.4
        crypto_candles.append({
            "time": base_time + i * 900,
            "open": price + 10, "high": price + 20, "low": price - 25,
            "close": price, "volume": 1000.0 + (i % 5) * 200,
            "close_time": base_time + (i + 1) * 900 - 1,
        })
    crypto_analysis = analyze_market_signals(
        crypto_candles, calculate_all_indicators(crypto_candles), "BTCUSDT"
    )
    assert crypto_analysis["bias"] == "SHORT"
    assert crypto_analysis["stop_loss"] > crypto_analysis["entry"]
    assert crypto_analysis["take_profit_1"] < crypto_analysis["entry"]

    # Forex downtrend (EURUSD) — 260 bars so EMA200 is fully warmed up
    fx_price = 1.13000
    fx_candles = []
    for i in range(260):
        fx_price -= 0.00010 * (1 + (i % 4) * 0.2)
        fx_candles.append({
            "time": base_time + i * 900,
            "open": fx_price + 0.00005, "high": fx_price + 0.00018,
            "low": fx_price - 0.00030, "close": fx_price,
            "volume": 1500.0 + (i % 6) * 90,
            "close_time": base_time + (i + 1) * 900 - 1,
        })
    fx_analysis = analyze_market_signals(
        fx_candles, calculate_all_indicators(fx_candles), "EURUSD", asset_class="forex"
    )
    assert fx_analysis["bias"] == "SHORT"
    assert fx_analysis["asset_class"] == "forex"
    assert fx_analysis["price_decimals"] == 5
    assert fx_analysis["stop_loss"] > fx_analysis["entry"]
    assert fx_analysis["risk_pips"] > 0
def test_api_symbols_two_options():
    """Verify /api/symbols cleanly supports both Option 1 (Crypto) and Option 2 (Forex)."""
    import app

    # Option 1: Crypto Market
    crypto_res = asyncio.run(app.get_symbols(market="crypto", limit=60))
    assert crypto_res["success"] is True
    assert crypto_res["market"] == "crypto"
    assert len(crypto_res["symbols"]) >= 50
    btc_entry = next((s for s in crypto_res["symbols"] if s["symbol"] == "BTCUSDT"), None)
    assert btc_entry is not None
    assert "price" in btc_entry
    assert "change24h" in btc_entry
    assert "category" in btc_entry

    # Option 2: Forex Market
    forex_res = asyncio.run(app.get_symbols(market="forex", limit=30))
    assert forex_res["success"] is True
    assert forex_res["market"] == "forex"
    assert len(forex_res["symbols"]) >= 28
    eur_entry = next((s for s in forex_res["symbols"] if s["symbol"] == "EURUSD"), None)
    assert eur_entry is not None
    assert "price" in eur_entry
    assert "change24h" in eur_entry
    assert "price_decimals" in eur_entry


if __name__ == "__main__":
    test_indicator_math()
    test_strategy_signals()
    test_indicator_layer_functions()
    test_professional_layers()
    test_forex_symbol_normalization()
    test_forex_category_classification()
    test_forex_price_formatting()
    test_forex_candle_normalization()
    test_forex_market_hours()
    test_dxy_sentiment_zone_mapping()
    test_forex_pair_sentiment_logic()
    test_forex_strategy_engine()
    test_crypto_strategy_unchanged_by_asset_class_default()
    test_forex_insufficient_data_contract()
    test_short_bias_risk_paths()
    test_telegram_alert_formatting()
    print("Unit tests passed!")
    asyncio.run(async_sentiment_test())
    asyncio.run(async_forex_sentiment_test())
    asyncio.run(async_integration_test())
    asyncio.run(async_forex_integration_test())
    print("Integration test passed!")
