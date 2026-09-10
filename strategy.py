"""
Trading Strategy Engine: Multi-Confluence Signal Generator.
Calculates Entry, Take Profit (TP1, TP2, TP3), and Stop Loss (SL) based on:
1. Trend alignment (EMA 20, 50, 200)
2. Momentum (RSI 14 + MACD Crossover)
3. Volatility-adjusted Risk (ATR 14)
4. Key Swing Highs & Lows (Price Action)
"""

from typing import Any, Dict, List, Optional
import numpy as np


def analyze_market_signals(
    candles: List[Dict[str, Any]], indicators: Dict[str, Any], symbol: str = "BTCUSDT"
) -> Dict[str, Any]:
    """
    Evaluates market conditions and outputs precise trading recommendations:
    - Signal: STRONG BUY, BUY, NEUTRAL, SELL, STRONG SELL
    - Entry Price
    - Stop Loss (SL) & Risk %
    - Take Profit 1 & 2 (TP1, TP2) & Profit %
    - Risk/Reward Ratio
    - Confluence reasons list
    """
    if not candles or len(candles) < 30:
        return {
            "symbol": symbol,
            "signal": "INSUFFICIENT_DATA",
            "score": 0,
            "reasons": ["Not enough candle history for analysis."],
        }

    latest = candles[-1]
    prev = candles[-2]
    price = latest["close"]

    # Extract indicator values for the last few bars
    rsi_list = [x for x in indicators["rsi"] if x is not None]
    macd_list = [x for x in indicators["macd"] if x is not None]
    signal_list = [x for x in indicators["macd_signal"] if x is not None]
    hist_list = [x for x in indicators["macd_hist"] if x is not None]
    ema20_list = [x for x in indicators["ema20"] if x is not None]
    ema50_list = [x for x in indicators["ema50"] if x is not None]
    ema200_list = [x for x in indicators["ema200"] if x is not None]
    atr_list = [x for x in indicators["atr"] if x is not None]

    curr_rsi = rsi_list[-1] if rsi_list else 50.0
    prev_rsi = rsi_list[-2] if len(rsi_list) > 1 else 50.0

    curr_macd = macd_list[-1] if macd_list else 0.0
    prev_macd = macd_list[-2] if len(macd_list) > 1 else 0.0
    curr_sig = signal_list[-1] if signal_list else 0.0
    prev_sig = signal_list[-2] if len(signal_list) > 1 else 0.0
    curr_hist = hist_list[-1] if hist_list else 0.0
    prev_hist = hist_list[-2] if len(hist_list) > 1 else 0.0

    curr_ema20 = ema20_list[-1] if ema20_list else price
    curr_ema50 = ema50_list[-1] if ema50_list else price
    curr_ema200 = ema200_list[-1] if ema200_list else price
    curr_atr = atr_list[-1] if atr_list else (price * 0.02)

    # Bullish vs Bearish scoring
    bull_score = 0
    bear_score = 0
    reasons = []

    # 1. EMA Trend Structure
    if price > curr_ema200:
        bull_score += 25
        reasons.append(f"Price is above 200 EMA (${curr_ema200:,.2f}), confirming macro bullish trend")
    else:
        bear_score += 25
        reasons.append(f"Price is below 200 EMA (${curr_ema200:,.2f}), signaling macro bearish pressure")

    if curr_ema50 > curr_ema200:
        bull_score += 15
        reasons.append("EMA 50 is above EMA 200 (Golden structure)")
    elif curr_ema50 < curr_ema200:
        bear_score += 15
        reasons.append("EMA 50 is below EMA 200 (Death structure)")

    if price > curr_ema20 > curr_ema50:
        bull_score += 15
        reasons.append("Short-term momentum is bullish (Price > EMA20 > EMA50)")
    elif price < curr_ema20 < curr_ema50:
        bear_score += 15
        reasons.append("Short-term momentum is bearish (Price < EMA20 < EMA50)")

    # 2. RSI Momentum
    if curr_rsi < 30:
        bull_score += 20
        reasons.append(f"RSI is oversold ({curr_rsi:.1f}), strong bounce potential")
    elif curr_rsi > 70:
        bear_score += 20
        reasons.append(f"RSI is overbought ({curr_rsi:.1f}), pullback risk")
    elif 45 <= curr_rsi <= 65 and bull_score > bear_score:
        bull_score += 10
        reasons.append(f"RSI in healthy bullish continuation zone ({curr_rsi:.1f})")
    elif 35 <= curr_rsi <= 55 and bear_score > bull_score:
        bear_score += 10
        reasons.append(f"RSI in bearish continuation zone ({curr_rsi:.1f})")

    # 3. MACD Momentum
    macd_crossed_up = prev_macd <= prev_sig and curr_macd > curr_sig
    macd_crossed_down = prev_macd >= prev_sig and curr_macd < curr_sig

    if macd_crossed_up:
        bull_score += 25
        reasons.append("MACD fresh Bullish Crossover detected")
    elif curr_macd > curr_sig and curr_hist > prev_hist:
        bull_score += 15
        reasons.append("MACD histogram expanding green (positive momentum)")
    elif macd_crossed_down:
        bear_score += 25
        reasons.append("MACD fresh Bearish Crossover detected")
    elif curr_macd < curr_sig and curr_hist < prev_hist:
        bear_score += 15
        reasons.append("MACD histogram expanding red (downward momentum)")

    # Swing levels for Stop Loss & Support/Resistance
    recent_candles = candles[-20:]
    recent_low = min(c["low"] for c in recent_candles)
    recent_high = max(c["high"] for c in recent_candles)

    # Determine overall signal
    net_score = bull_score - bear_score

    if net_score >= 50:
        signal = "STRONG BUY"
        bias = "LONG"
    elif net_score >= 25:
        signal = "BUY"
        bias = "LONG"
    elif net_score <= -50:
        signal = "STRONG SELL"
        bias = "SHORT"
    elif net_score <= -25:
        signal = "SELL"
        bias = "SHORT"
    else:
        signal = "NEUTRAL"
        # Slight bias based on EMA200
        bias = "LONG" if price >= curr_ema200 else "SHORT"

    # Precise Entry, Stop Loss, and Take Profit Calculations
    entry_price = price

    if bias == "LONG":
        # Stop loss: below recent swing low or 1.5 * ATR, whichever provides safe cushion
        atr_sl_distance = max(1.5 * curr_atr, entry_price * 0.008)  # Minimum 0.8% stop distance
        sl_from_swing = recent_low * 0.9985
        calculated_sl = max(entry_price - atr_sl_distance, sl_from_swing)

        # Ensure SL is strictly below entry and reasonable (0.5% to 5%)
        if calculated_sl >= entry_price or (entry_price - calculated_sl) / entry_price > 0.06:
            calculated_sl = entry_price - (entry_price * 0.018)  # 1.8% standard stop

        risk = entry_price - calculated_sl
        tp1 = entry_price + (1.5 * risk)  # 1:1.5 Risk-Reward
        tp2 = entry_price + (2.5 * risk)  # 1:2.5 Risk-Reward
        tp3 = entry_price + (3.5 * risk)  # 1:3.5 Risk-Reward

    else:
        # SHORT / SELL Setup
        atr_sl_distance = max(1.5 * curr_atr, entry_price * 0.008)
        sl_from_swing = recent_high * 1.0015
        calculated_sl = min(entry_price + atr_sl_distance, sl_from_swing)

        if calculated_sl <= entry_price or (calculated_sl - entry_price) / entry_price > 0.06:
            calculated_sl = entry_price + (entry_price * 0.018)

        risk = calculated_sl - entry_price
        tp1 = entry_price - (1.5 * risk)
        tp2 = entry_price - (2.5 * risk)
        tp3 = entry_price - (3.5 * risk)

    # Percentage metrics
    risk_pct = abs((calculated_sl - entry_price) / entry_price) * 100
    tp1_pct = abs((tp1 - entry_price) / entry_price) * 100
    tp2_pct = abs((tp2 - entry_price) / entry_price) * 100
    tp3_pct = abs((tp3 - entry_price) / entry_price) * 100

    return {
        "symbol": symbol,
        "price": price,
        "signal": signal,
        "bias": bias,
        "net_score": net_score,
        "confidence": min(abs(net_score) + 20, 98),
        "entry": round(entry_price, 4 if price < 10 else 2),
        "stop_loss": round(calculated_sl, 4 if price < 10 else 2),
        "take_profit_1": round(tp1, 4 if price < 10 else 2),
        "take_profit_2": round(tp2, 4 if price < 10 else 2),
        "take_profit_3": round(tp3, 4 if price < 10 else 2),
        "risk_reward_tp1": "1 : 1.5",
        "risk_reward_tp2": "1 : 2.5",
        "risk_pct": round(risk_pct, 2),
        "tp1_pct": round(tp1_pct, 2),
        "tp2_pct": round(tp2_pct, 2),
        "tp3_pct": round(tp3_pct, 2),
        "rsi": round(curr_rsi, 2),
        "macd_hist": round(curr_hist, 4),
        "atr": round(curr_atr, 4),
        "ema20": round(curr_ema20, 2),
        "ema50": round(curr_ema50, 2),
        "ema200": round(curr_ema200, 2),
        "support": round(recent_low, 2),
        "resistance": round(recent_high, 2),
        "reasons": reasons,
    }
