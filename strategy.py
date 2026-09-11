"""
Professional Trading Strategy Engine — 8-Layer Confluence System.
Thinks like a real trader: analyzes market structure, volume conviction,
candlestick psychology, entry timing, dynamic risk levels, Bollinger volatility,
and global crypto sentiment to produce institutional-grade trade recommendations.

Layers:
1. Market Structure (BOS / CHoCH / Trend)
2. Smart Money Volume Analysis
3. Candlestick Pattern Recognition
4. EMA Trend Alignment
5. Momentum (RSI + MACD)
6. Bollinger Squeeze & Volatility
7. Entry Timing Quality (pullback detection)
8. Sentiment Context (Fear & Greed)
"""

from typing import Any, Dict, List, Optional
import numpy as np


# =============================================================================
# SIGNAL GRADING THRESHOLDS
# =============================================================================
GRADE_THRESHOLDS = {
    "A+": 90,
    "A": 80,
    "B": 65,
    "C": 50,
    "D": 0,
}

MINIMUM_RR_RATIO = 1.5  # Minimum Risk:Reward ratio to issue a trade signal


def _price_decimals(price: float) -> int:
    """Choose decimal precision appropriate to an asset's price magnitude.

    Handles micro-cap meme coins (e.g. PEPE at ~3e-06) so prices never round to 0.
    """
    if price <= 0:
        return 8
    if price >= 1000:
        return 2
    if price >= 1:
        return 4
    if price >= 0.01:
        return 6
    if price >= 0.0001:
        return 8
    return 10


def _fmt_price(value: float) -> str:
    """Format a price string scaled to the asset's magnitude."""
    return f"{value:,.{_price_decimals(value)}f}"


def analyze_market_signals(
    candles: List[Dict[str, Any]],
    indicators: Dict[str, Any],
    symbol: str = "BTCUSDT",
    sentiment: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Professional 8-layer confluence analysis engine.
    Evaluates market like an experienced trader and outputs:
    - Signal: STRONG BUY, BUY, NEUTRAL, SELL, STRONG SELL
    - Signal Grade: A+, A, B, C, D
    - Entry Strategy advice (pullback vs market entry)
    - Dynamic SL/TP from swing structure
    - Human-readable narrative explaining the trade thesis
    - Detailed scoring breakdown per layer
    """

    if not candles or len(candles) < 30:
        return _insufficient_data(symbol)

    latest = candles[-1]
    prev = candles[-2]
    price = latest["close"]

    # Extract indicator values
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

    # Extract professional layers from indicators
    mkt_struct = indicators.get("market_structure", {})
    vol_profile = indicators.get("volume_profile", {})
    candle_pats = indicators.get("candle_patterns", {})
    bb_squeeze = indicators.get("bb_squeeze", {})

    # Scoring accumulators (each layer contributes to bull and bear scores)
    bull_score = 0.0
    bear_score = 0.0
    reasons = []  # Human-readable confluence reasons
    layer_scores = {}

    # =========================================================================
    # LAYER 1: MARKET STRUCTURE (20 points max)
    # =========================================================================
    struct_bull = 0.0
    struct_bear = 0.0
    struct_trend = mkt_struct.get("trend", "RANGING")

    if struct_trend == "UPTREND":
        struct_bull += 14
        reasons.append(f"📈 Market Structure: {mkt_struct.get('description', 'Uptrend confirmed')}")
    elif struct_trend == "DOWNTREND":
        struct_bear += 14
        reasons.append(f"📉 Market Structure: {mkt_struct.get('description', 'Downtrend confirmed')}")
    else:
        reasons.append(f"↔️ Market Structure: {mkt_struct.get('description', 'Ranging / choppy')}")

    if mkt_struct.get("bos_detected"):
        if mkt_struct["bos_direction"] == "BULLISH":
            struct_bull += 6
            reasons.append("💥 Break of Structure (BOS): Price broke above last swing high — bullish continuation")
        else:
            struct_bear += 6
            reasons.append("💥 Break of Structure (BOS): Price broke below last swing low — bearish continuation")

    if mkt_struct.get("choch_detected"):
        if mkt_struct["choch_direction"] == "BULLISH_REVERSAL":
            struct_bull += 4
            reasons.append("🔄 Change of Character (CHoCH): First higher low in downtrend — potential bullish reversal")
        elif mkt_struct["choch_direction"] == "BEARISH_REVERSAL":
            struct_bear += 4
            reasons.append("🔄 Change of Character (CHoCH): First lower high in uptrend — potential bearish reversal")

    bull_score += min(struct_bull, 20)
    bear_score += min(struct_bear, 20)
    layer_scores["structure"] = {"bull": round(struct_bull, 1), "bear": round(struct_bear, 1), "max": 20}

    # =========================================================================
    # LAYER 2: SMART MONEY VOLUME (15 points max)
    # =========================================================================
    vol_bull = 0.0
    vol_bear = 0.0
    acc_dist = vol_profile.get("accumulation", "NEUTRAL")
    vol_desc = vol_profile.get("description", "")

    if acc_dist == "ACCUMULATION":
        vol_bull += 10
        reasons.append(f"📊 Volume: {vol_desc}")
    elif acc_dist == "DISTRIBUTION":
        vol_bear += 10
        reasons.append(f"📊 Volume: {vol_desc}")
    elif acc_dist == "WEAK_RALLY":
        vol_bear += 5
        reasons.append(f"📊 Volume: {vol_desc}")
    elif acc_dist == "WEAK_SELLOFF":
        vol_bull += 5
        reasons.append(f"📊 Volume: {vol_desc}")

    if vol_profile.get("is_spike"):
        reasons.append(f"🔥 Volume Spike! Current volume is {vol_profile.get('volume_ratio', 0)}x the 20-bar average")
        # Volume spike with trend = confirmation; against trend = reversal warning
        if struct_trend == "UPTREND" and acc_dist in ("ACCUMULATION", "NEUTRAL"):
            vol_bull += 5
        elif struct_trend == "DOWNTREND" and acc_dist in ("DISTRIBUTION", "NEUTRAL"):
            vol_bear += 5

    if vol_profile.get("is_climactic"):
        reasons.append("⚠️ Climactic Volume: Extremely high volume may signal exhaustion / trend reversal")

    bull_score += min(vol_bull, 15)
    bear_score += min(vol_bear, 15)
    layer_scores["volume"] = {"bull": round(vol_bull, 1), "bear": round(vol_bear, 1), "max": 15}

    # =========================================================================
    # LAYER 3: CANDLESTICK PATTERNS (10 points max)
    # =========================================================================
    candle_bull = 0.0
    candle_bear = 0.0
    pats = candle_pats.get("patterns", [])

    for pat in pats:
        strength_pts = 4 if pat.get("strength") == "strong" else 2
        if pat["type"] == "bullish":
            candle_bull += strength_pts
            reasons.append(f"🕯️ {pat['name']}")
        elif pat["type"] == "bearish":
            candle_bear += strength_pts
            reasons.append(f"🕯️ {pat['name']}")
        else:
            reasons.append(f"🕯️ {pat['name']}")

    bull_score += min(candle_bull, 10)
    bear_score += min(candle_bear, 10)
    layer_scores["candles"] = {"bull": round(candle_bull, 1), "bear": round(candle_bear, 1), "max": 10}

    # =========================================================================
    # LAYER 4: EMA TREND ALIGNMENT (15 points max)
    # =========================================================================
    ema_bull = 0.0
    ema_bear = 0.0

    if price > curr_ema200:
        ema_bull += 6
        reasons.append(f"Price above 200 EMA (${_fmt_price(curr_ema200)}) — macro bullish bias")
    else:
        ema_bear += 6
        reasons.append(f"Price below 200 EMA (${_fmt_price(curr_ema200)}) — macro bearish pressure")

    if curr_ema20 > curr_ema50 > curr_ema200:
        ema_bull += 5
        reasons.append("EMA Stack: 20 > 50 > 200 — perfect bullish alignment")
    elif curr_ema20 < curr_ema50 < curr_ema200:
        ema_bear += 5
        reasons.append("EMA Stack: 20 < 50 < 200 — perfect bearish alignment")

    if price > curr_ema20 > curr_ema50:
        ema_bull += 4
    elif price < curr_ema20 < curr_ema50:
        ema_bear += 4

    bull_score += min(ema_bull, 15)
    bear_score += min(ema_bear, 15)
    layer_scores["ema"] = {"bull": round(ema_bull, 1), "bear": round(ema_bear, 1), "max": 15}

    # =========================================================================
    # LAYER 5: MOMENTUM — RSI + MACD (15 points max)
    # =========================================================================
    mom_bull = 0.0
    mom_bear = 0.0

    # RSI
    if curr_rsi < 25:
        mom_bull += 5
        reasons.append(f"RSI deeply oversold ({curr_rsi:.1f}) — strong bounce potential")
    elif curr_rsi < 35:
        mom_bull += 3
        reasons.append(f"RSI oversold ({curr_rsi:.1f}) — approaching bounce zone")
    elif curr_rsi > 75:
        mom_bear += 5
        reasons.append(f"RSI deeply overbought ({curr_rsi:.1f}) — high pullback risk")
    elif curr_rsi > 65:
        mom_bear += 3
        reasons.append(f"RSI overbought ({curr_rsi:.1f}) — caution on longs")
    elif 45 <= curr_rsi <= 60 and bull_score > bear_score:
        mom_bull += 2
        reasons.append(f"RSI in healthy bullish zone ({curr_rsi:.1f})")

    # RSI divergence detection (simplified)
    if len(rsi_list) >= 10:
        price_5ago = candles[-6]["close"]
        rsi_5ago = rsi_list[-6] if len(rsi_list) >= 6 else curr_rsi
        if price < price_5ago and curr_rsi > rsi_5ago:
            mom_bull += 3
            reasons.append("🔀 Bullish RSI Divergence: Price making lower lows but RSI making higher lows")
        elif price > price_5ago and curr_rsi < rsi_5ago:
            mom_bear += 3
            reasons.append("🔀 Bearish RSI Divergence: Price making higher highs but RSI making lower highs")

    # MACD
    macd_crossed_up = prev_macd <= prev_sig and curr_macd > curr_sig
    macd_crossed_down = prev_macd >= prev_sig and curr_macd < curr_sig

    if macd_crossed_up:
        mom_bull += 5
        reasons.append("MACD fresh Bullish Crossover — momentum shifting up")
    elif curr_macd > curr_sig and curr_hist > prev_hist:
        mom_bull += 3
        reasons.append("MACD histogram expanding green — accelerating bullish momentum")
    elif macd_crossed_down:
        mom_bear += 5
        reasons.append("MACD fresh Bearish Crossover — momentum shifting down")
    elif curr_macd < curr_sig and curr_hist < prev_hist:
        mom_bear += 3
        reasons.append("MACD histogram expanding red — accelerating bearish momentum")

    bull_score += min(mom_bull, 15)
    bear_score += min(mom_bear, 15)
    layer_scores["momentum"] = {"bull": round(mom_bull, 1), "bear": round(mom_bear, 1), "max": 15}

    # =========================================================================
    # LAYER 6: BOLLINGER SQUEEZE & VOLATILITY (5 points max)
    # =========================================================================
    vol_state_bull = 0.0
    vol_state_bear = 0.0

    if bb_squeeze.get("is_squeeze"):
        reasons.append(f"⚡ {bb_squeeze.get('description', 'Bollinger Squeeze — big move incoming')}")
        # Squeeze doesn't inherently favor a direction, but combined with trend:
        if struct_trend == "UPTREND":
            vol_state_bull += 3
        elif struct_trend == "DOWNTREND":
            vol_state_bear += 3

    bw = bb_squeeze.get("band_walk", "NONE")
    if bw == "UPPER_WALK":
        vol_state_bull += 3
        reasons.append("Price riding upper Bollinger Band — strong bullish trend")
    elif bw == "LOWER_WALK":
        vol_state_bear += 3
        reasons.append("Price riding lower Bollinger Band — strong bearish trend")

    pvb = bb_squeeze.get("price_vs_bands", "MIDDLE")
    if pvb == "UPPER_BAND" and bw != "UPPER_WALK":
        vol_state_bear += 2
    elif pvb == "LOWER_BAND" and bw != "LOWER_WALK":
        vol_state_bull += 2

    bull_score += min(vol_state_bull, 5)
    bear_score += min(vol_state_bear, 5)
    layer_scores["volatility"] = {"bull": round(vol_state_bull, 1), "bear": round(vol_state_bear, 1), "max": 5}

    # =========================================================================
    # LAYER 7: ENTRY TIMING QUALITY (10 points max)
    # =========================================================================
    entry_bull = 0.0
    entry_bear = 0.0
    entry_strategy = "Enter at market price"
    entry_quality = "FAIR"

    # Check if price is at a pullback to EMA (ideal entry) vs extended/chasing
    ema20_dist_pct = abs(price - curr_ema20) / price * 100 if price > 0 else 0

    if bull_score > bear_score:
        # For a bullish signal: best entry is at or near EMA 20/50 support
        if price <= curr_ema20 * 1.003:
            entry_bull += 7
            entry_quality = "EXCELLENT"
            entry_strategy = f"Ideal entry — price at EMA20 support (${_fmt_price(curr_ema20)}). Enter now."
            reasons.append(f"🎯 Entry Timing: Excellent — price pulling back to EMA20 support zone")
        elif price <= curr_ema50 * 1.005:
            entry_bull += 5
            entry_quality = "GOOD"
            entry_strategy = f"Good entry — price near EMA50 support (${_fmt_price(curr_ema50)})."
            reasons.append(f"🎯 Entry Timing: Good — price near EMA50 support")
        elif ema20_dist_pct > 2.5:
            entry_quality = "LATE"
            entry_strategy = f"⚠️ Late entry — price is {ema20_dist_pct:.1f}% above EMA20. Consider waiting for pullback to ${_fmt_price(curr_ema20)}."
            reasons.append(f"⚠️ Entry Timing: Late — price extended {ema20_dist_pct:.1f}% above EMA20. Pullback risk.")
        else:
            entry_bull += 3
            entry_quality = "FAIR"
            entry_strategy = f"Fair entry — price moderately above EMA20. Acceptable for trend following."
    else:
        # For a bearish signal: best short entry is at or near EMA 20/50 resistance
        if price >= curr_ema20 * 0.997:
            entry_bear += 7
            entry_quality = "EXCELLENT"
            entry_strategy = f"Ideal short entry — price at EMA20 resistance (${_fmt_price(curr_ema20)}). Enter now."
            reasons.append(f"🎯 Entry Timing: Excellent — price bouncing off EMA20 resistance")
        elif price >= curr_ema50 * 0.995:
            entry_bear += 5
            entry_quality = "GOOD"
            entry_strategy = f"Good short entry — price near EMA50 resistance (${_fmt_price(curr_ema50)})."
            reasons.append(f"🎯 Entry Timing: Good — price near EMA50 resistance")
        elif ema20_dist_pct > 2.5:
            entry_quality = "LATE"
            entry_strategy = f"⚠️ Late entry — price is {ema20_dist_pct:.1f}% below EMA20. Consider waiting for rally to ${_fmt_price(curr_ema20)}."
            reasons.append(f"⚠️ Entry Timing: Late — price extended {ema20_dist_pct:.1f}% below EMA20.")
        else:
            entry_bear += 3
            entry_quality = "FAIR"

    bull_score += min(entry_bull, 10)
    bear_score += min(entry_bear, 10)
    layer_scores["entry_timing"] = {"bull": round(entry_bull, 1), "bear": round(entry_bear, 1), "max": 10, "quality": entry_quality}

    # =========================================================================
    # LAYER 8: SENTIMENT CONTEXT (10 points max)
    # =========================================================================
    sent_bull = 0.0
    sent_bear = 0.0

    fng = sentiment.get("fear_greed", {}) if sentiment else {}
    fng_value = fng.get("value", 50)
    fng_zone = fng.get("zone", "NEUTRAL")

    if fng_zone in ("EXTREME_FEAR",):
        sent_bull += 8
        reasons.append(f"😱 Sentiment: Extreme Fear ({fng_value}/100) — historically the best time to buy (contrarian)")
    elif fng_zone == "FEAR":
        sent_bull += 5
        reasons.append(f"😰 Sentiment: Fear ({fng_value}/100) — market is scared, contrarian buy opportunity")
    elif fng_zone == "EXTREME_GREED":
        sent_bear += 8
        reasons.append(f"🤑 Sentiment: Extreme Greed ({fng_value}/100) — euphoria, high risk of correction")
    elif fng_zone == "GREED":
        sent_bear += 4
        reasons.append(f"🤩 Sentiment: Greed ({fng_value}/100) — market getting overconfident, tighten stops")
    elif fng_zone == "CAUTION":
        sent_bear += 2
        reasons.append(f"⚠️ Sentiment: Cautious ({fng_value}/100)")

    global_mkt = sentiment.get("global_market", {}) if sentiment else {}
    mkt_cap_change = global_mkt.get("total_market_cap_change_24h", 0.0)
    if mkt_cap_change > 3.0:
        sent_bull += 2
        reasons.append(f"🌍 Global crypto market cap up {mkt_cap_change}% in 24h — bullish macro flow")
    elif mkt_cap_change < -3.0:
        sent_bear += 2
        reasons.append(f"🌍 Global crypto market cap down {mkt_cap_change}% in 24h — bearish macro pressure")

    bull_score += min(sent_bull, 10)
    bear_score += min(sent_bear, 10)
    layer_scores["sentiment"] = {"bull": round(sent_bull, 1), "bear": round(sent_bear, 1), "max": 10}

    # =========================================================================
    # FINAL SIGNAL DETERMINATION
    # =========================================================================
    net_score = bull_score - bear_score
    dominant_score = max(bull_score, bear_score)

    # Confidence is the dominant score on the weighted 100-point confluence scale
    # (Market Structure 20 + Volume 15 + Candles 10 + EMA 15 + Momentum 15
    #  + Volatility 5 + Entry Timing 10 + Sentiment 10 = 100)
    confidence = min(int(round(dominant_score)), 98)

    if net_score >= 35:
        signal = "STRONG BUY"
        bias = "LONG"
    elif net_score >= 15:
        signal = "BUY"
        bias = "LONG"
    elif net_score <= -35:
        signal = "STRONG SELL"
        bias = "SHORT"
    elif net_score <= -15:
        signal = "SELL"
        bias = "SHORT"
    else:
        signal = "NEUTRAL"
        bias = "LONG" if price >= curr_ema200 else "SHORT"

    # Signal Grade
    grade = "D"
    for g, threshold in GRADE_THRESHOLDS.items():
        if confidence >= threshold:
            grade = g
            break

    # =========================================================================
    # DYNAMIC STOP LOSS & TAKE PROFIT (Structure-Based)
    # =========================================================================
    entry_price = price
    swings = indicators.get("swings", {"highs": [], "lows": []})
    recent_candles = candles[-25:]
    recent_low = min(c["low"] for c in recent_candles)
    recent_high = max(c["high"] for c in recent_candles)

    # Use swing points for smarter SL placement
    swing_lows = [s["price"] for s in swings.get("lows", []) if s["price"] < price]
    swing_highs = [s["price"] for s in swings.get("highs", []) if s["price"] > price]

    # Bollinger band boundaries for mean-reversion take-profit targets
    bb_upper_list = [x for x in indicators.get("bb_upper", []) if x is not None]
    bb_lower_list = [x for x in indicators.get("bb_lower", []) if x is not None]
    bb_upper_val = bb_upper_list[-1] if bb_upper_list else None
    bb_lower_val = bb_lower_list[-1] if bb_lower_list else None

    if bias == "LONG":
        # SL below nearest swing low or ATR-based, whichever is tighter but safe
        atr_sl = entry_price - max(1.5 * curr_atr, entry_price * 0.008)
        swing_sl = max(swing_lows[-3:]) * 0.998 if len(swing_lows) >= 1 else atr_sl  # Just below swing low
        calculated_sl = max(atr_sl, swing_sl)  # Use the higher (tighter) SL

        if calculated_sl >= entry_price or (entry_price - calculated_sl) / entry_price > 0.06:
            calculated_sl = entry_price - (entry_price * 0.018)

        risk = entry_price - calculated_sl

        # TP1 = next swing resistance from structure
        tp1_swing = min(swing_highs[:2]) if len(swing_highs) >= 1 else entry_price + (1.5 * risk)
        tp1 = max(tp1_swing, entry_price + (1.5 * risk))

        # TP2 = next Bollinger upper-band boundary (mean-reversion target) when sensible
        tp2 = entry_price + (2.5 * risk)
        if bb_upper_val and entry_price < bb_upper_val < entry_price + (8.0 * risk):
            tp2 = max(tp2, bb_upper_val)
        tp2 = max(tp2, tp1 + 0.5 * risk)

        # TP3 = extended Fibonacci-like projection (4.236 extension of risk)
        tp3 = max(entry_price + (3.5 * risk), entry_price + (4.236 * risk))
        tp3 = max(tp3, tp2 + 0.5 * risk)

    else:
        # SHORT setup
        atr_sl = entry_price + max(1.5 * curr_atr, entry_price * 0.008)
        swing_sl = min(swing_highs[-3:]) * 1.002 if len(swing_highs) >= 1 else atr_sl
        calculated_sl = min(atr_sl, swing_sl)

        if calculated_sl <= entry_price or (calculated_sl - entry_price) / entry_price > 0.06:
            calculated_sl = entry_price + (entry_price * 0.018)

        risk = calculated_sl - entry_price

        # TP1 = next swing support from structure
        tp1_swing = max(swing_lows[:2]) if len(swing_lows) >= 1 else entry_price - (1.5 * risk)
        tp1 = min(tp1_swing, entry_price - (1.5 * risk))

        # TP2 = next Bollinger lower-band boundary (mean-reversion target) when sensible
        tp2 = entry_price - (2.5 * risk)
        if bb_lower_val and entry_price - (8.0 * risk) < bb_lower_val < entry_price:
            tp2 = min(tp2, bb_lower_val)
        tp2 = min(tp2, tp1 - 0.5 * risk)

        # TP3 = extended Fibonacci-like projection (4.236 extension of risk)
        tp3 = min(entry_price - (3.5 * risk), entry_price - (4.236 * risk))
        tp3 = min(tp3, tp2 - 0.5 * risk)

    # Risk:Reward calculation
    if risk > 0:
        rr_tp1 = abs(tp1 - entry_price) / risk
        rr_tp2 = abs(tp2 - entry_price) / risk
        rr_tp3 = abs(tp3 - entry_price) / risk
    else:
        rr_tp1 = rr_tp2 = rr_tp3 = 0.0

    # Minimum R:R Gate — refuse bad trades
    rr_gate_passed = rr_tp1 >= MINIMUM_RR_RATIO
    if not rr_gate_passed and signal != "NEUTRAL":
        reasons.append(f"⛔ R:R Gate FAILED: TP1 R:R is only 1:{rr_tp1:.1f} (minimum 1:{MINIMUM_RR_RATIO}). Trade NOT recommended.")
        signal = "NEUTRAL"
        grade = "D"
        confidence = max(confidence - 20, 15)

    # Keep entry guidance honest: never recommend a directional entry on a neutral signal
    if signal == "NEUTRAL":
        entry_strategy = "No high-conviction setup — stand aside and wait for an A/B grade confluence before entering."

    # Percentage metrics
    risk_pct = abs((calculated_sl - entry_price) / entry_price) * 100
    tp1_pct = abs((tp1 - entry_price) / entry_price) * 100
    tp2_pct = abs((tp2 - entry_price) / entry_price) * 100
    tp3_pct = abs((tp3 - entry_price) / entry_price) * 100

    # =========================================================================
    # TRADE MANAGEMENT (Trailing stop / breakeven plan)
    # =========================================================================
    if signal != "NEUTRAL" and rr_gate_passed:
        management_advice = (
            f"Trade management: once TP1 (${_fmt_price(tp1)}) is hit, move the stop loss to breakeven "
            f"(${_fmt_price(entry_price)}), then trail the remaining position toward TP2/TP3."
        )
    else:
        management_advice = "No active trade — stand aside and wait for an A/B grade confluence setup."

    # =========================================================================
    # TRADE NARRATIVE (Human-readable reasoning like a pro would explain)
    # =========================================================================
    narrative = _build_narrative(
        signal, grade, bias, struct_trend, acc_dist, entry_quality,
        candle_pats, fng_value, fng_zone, symbol, price, curr_ema20, curr_ema50,
        entry_strategy, rr_tp1, rr_gate_passed, bb_squeeze, vol_profile,
    )
    narrative = f"{narrative} {management_advice}"

    # =========================================================================
    # ASSEMBLE OUTPUT
    # =========================================================================
    dp = _price_decimals(price)

    return {
        "symbol": symbol,
        "price": price,
        "signal": signal,
        "bias": bias,
        "grade": grade,
        "net_score": round(net_score, 1),
        "confidence": confidence,
        "entry": round(entry_price, dp),
        "stop_loss": round(calculated_sl, dp),
        "take_profit_1": round(tp1, dp),
        "take_profit_2": round(tp2, dp),
        "take_profit_3": round(tp3, dp),
        "risk_reward_tp1": f"1 : {rr_tp1:.1f}",
        "risk_reward_tp2": f"1 : {rr_tp2:.1f}",
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
        "support": round(recent_low, dp),
        "resistance": round(recent_high, dp),
        "reasons": reasons,
        # Professional additions
        "narrative": narrative,
        "entry_strategy": entry_strategy,
        "entry_quality": entry_quality,
        "management_advice": management_advice,
        "market_structure": {
            "trend": struct_trend,
            "description": mkt_struct.get("description", ""),
            "bos": mkt_struct.get("bos_direction"),
            "choch": mkt_struct.get("choch_direction"),
        },
        "volume_analysis": {
            "accumulation": acc_dist,
            "description": vol_profile.get("description", ""),
            "is_spike": bool(vol_profile.get("is_spike", False)),
            "volume_ratio": vol_profile.get("volume_ratio", 1.0),
        },
        "candle_patterns_summary": candle_pats.get("summary", ""),
        "bb_squeeze_active": bool(bb_squeeze.get("is_squeeze", False)),
        "layer_scores": layer_scores,
        "rr_gate_passed": rr_gate_passed,
    }


def _build_narrative(
    signal, grade, bias, struct_trend, acc_dist, entry_quality,
    candle_pats, fng_value, fng_zone, symbol, price, ema20, ema50,
    entry_strategy, rr_tp1, rr_gate_passed, bb_squeeze, vol_profile,
) -> str:
    """Build a human-readable trade thesis like a pro trader would explain to a colleague."""
    parts = []

    # Opening assessment
    if signal in ("STRONG BUY", "BUY"):
        parts.append(f"🟢 {signal} on {symbol} (Grade {grade})")
    elif signal in ("STRONG SELL", "SELL"):
        parts.append(f"🔴 {signal} on {symbol} (Grade {grade})")
    else:
        parts.append(f"⚪ NEUTRAL on {symbol} — no clear edge right now")

    # Structure context
    if struct_trend == "UPTREND":
        parts.append("Market structure is bullish with higher highs and higher lows.")
    elif struct_trend == "DOWNTREND":
        parts.append("Market structure is bearish with lower highs and lower lows.")
    else:
        parts.append("Market is ranging — structure is choppy with no clear direction.")

    # Volume context
    if acc_dist == "ACCUMULATION":
        parts.append("Smart money appears to be accumulating (price rising + volume increasing).")
    elif acc_dist == "DISTRIBUTION":
        parts.append("Institutional distribution detected (price falling + volume increasing).")
    elif acc_dist == "WEAK_RALLY":
        parts.append("⚠️ Current rally lacks volume conviction — potential fake-out risk.")

    # Candle patterns
    pats = candle_pats.get("patterns", [])
    strong_pats = [p["name"] for p in pats if p.get("strength") == "strong"]
    if strong_pats:
        parts.append(f"Key patterns: {', '.join(strong_pats)}.")

    # Bollinger squeeze
    if bb_squeeze.get("is_squeeze"):
        parts.append("⚡ Bollinger Bands squeezed tight — expect a breakout move soon.")

    # Entry advice
    if entry_quality == "EXCELLENT":
        parts.append("Entry timing is excellent — price is at a key support/resistance pullback zone.")
    elif entry_quality == "LATE":
        parts.append("⚠️ Entry timing is late — consider waiting for a pullback before entering.")

    # Sentiment
    if fng_zone in ("EXTREME_FEAR", "FEAR"):
        parts.append(f"Sentiment is fearful ({fng_value}/100) — contrarian opportunity for longs.")
    elif fng_zone in ("EXTREME_GREED", "GREED"):
        parts.append(f"Sentiment is greedy ({fng_value}/100) — exercise caution and tighten risk.")

    # R:R gate
    if not rr_gate_passed and signal != "NEUTRAL":
        parts.append(f"⛔ Risk:Reward ratio too low (1:{rr_tp1:.1f}). Signal downgraded to NEUTRAL.")

    return " ".join(parts)


def _insufficient_data(symbol: str) -> Dict[str, Any]:
    """Return a safe default when there isn't enough candle history."""
    return {
        "symbol": symbol,
        "signal": "INSUFFICIENT_DATA",
        "grade": "D",
        "score": 0,
        "net_score": 0,
        "confidence": 0,
        "bias": "NEUTRAL",
        "price": 0,
        "entry": 0, "stop_loss": 0,
        "take_profit_1": 0, "take_profit_2": 0, "take_profit_3": 0,
        "risk_reward_tp1": "0", "risk_reward_tp2": "0",
        "risk_pct": 0, "tp1_pct": 0, "tp2_pct": 0, "tp3_pct": 0,
        "rsi": 50, "macd_hist": 0, "atr": 0,
        "ema20": 0, "ema50": 0, "ema200": 0,
        "support": 0, "resistance": 0,
        "reasons": ["Not enough candle history for professional analysis."],
        "narrative": "Insufficient data for analysis.",
        "entry_strategy": "Wait for more data",
        "entry_quality": "N/A",
        "management_advice": "No active trade — insufficient data.",
        "market_structure": {"trend": "UNKNOWN", "description": "Insufficient data"},
        "volume_analysis": {"accumulation": "NEUTRAL", "description": ""},
        "candle_patterns_summary": "",
        "bb_squeeze_active": False,
        "layer_scores": {},
        "rr_gate_passed": False,
    }
