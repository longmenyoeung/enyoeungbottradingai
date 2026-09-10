"""
Automated unit & integration verification for trading bot indicators and strategy.
"""

import asyncio
from binance_client import fetch_klines
from indicators import calculate_all_indicators, compute_ema, compute_rsi, compute_macd, compute_atr
from strategy import analyze_market_signals
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


async def async_integration_test():
    candles = await fetch_klines("BTCUSDT", "15m", limit=50)
    assert len(candles) >= 30
    indicators = calculate_all_indicators(candles)
    analysis = analyze_market_signals(candles, indicators, "BTCUSDT")
    print(f"Live Test Result for BTCUSDT: {analysis['signal']} at ${analysis['price']}")
    print(f"Entry: ${analysis['entry']} | SL: ${analysis['stop_loss']} | TP1: ${analysis['take_profit_1']} | TP2: ${analysis['take_profit_2']}")


if __name__ == "__main__":
    test_indicator_math()
    test_strategy_signals()
    print("Unit tests passed!")
    asyncio.run(async_integration_test())
    print("Integration test passed!")
