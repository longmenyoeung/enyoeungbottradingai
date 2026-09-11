"""
Automated unit & integration verification for trading bot indicators and strategy.
"""

import asyncio
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
from strategy import analyze_market_signals
from sentiment import get_sentiment_summary
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


if __name__ == "__main__":
    test_indicator_math()
    test_strategy_signals()
    test_indicator_layer_functions()
    test_professional_layers()
    print("Unit tests passed!")
    asyncio.run(async_sentiment_test())
    asyncio.run(async_integration_test())
    print("Integration test passed!")
