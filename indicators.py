"""
Technical Indicators Calculation Engine — Professional Grade.
Calculates EMA, SMA, RSI, MACD, ATR, Bollinger Bands, Swing Pivots,
Market Structure (BOS/CHoCH), Volume Profile, Candlestick Patterns,
and Bollinger Squeeze detection using NumPy.
"""

from typing import Any, Dict, List, Optional
import numpy as np


def compute_sma(data: np.ndarray, period: int) -> np.ndarray:
    """Calculate Simple Moving Average."""
    n = len(data)
    result = np.full(n, np.nan)
    if n < period:
        return result
    kernel = np.ones(period) / period
    convolved = np.convolve(data, kernel, mode="valid")
    result[period - 1 :] = convolved
    return result


def compute_ema(data: np.ndarray, period: int) -> np.ndarray:
    """Calculate Exponential Moving Average."""
    n = len(data)
    result = np.full(n, np.nan)
    if n < period:
        return result

    # Initial SMA seed
    initial_sma = np.mean(data[:period])
    result[period - 1] = initial_sma
    alpha = 2.0 / (period + 1.0)

    for i in range(period, n):
        result[i] = alpha * data[i] + (1.0 - alpha) * result[i - 1]

    return result


def compute_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Calculate Relative Strength Index (RSI) using Wilder's smoothing.
    """
    n = len(close)
    rsi = np.full(n, np.nan)
    if n <= period:
        return rsi

    delta = np.diff(close)
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, n):
        gain = gains[i - 1]
        loss = losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def compute_macd(
    close: np.ndarray, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
) -> Dict[str, np.ndarray]:
    """
    Calculate MACD, Signal Line, and MACD Histogram.
    """
    fast_ema = compute_ema(close, fast_period)
    slow_ema = compute_ema(close, slow_period)
    macd_line = fast_ema - slow_ema

    # Calculate Signal Line as EMA of valid MACD line
    valid_mask = ~np.isnan(macd_line)
    signal_line = np.full(len(close), np.nan)
    if np.sum(valid_mask) >= signal_period:
        valid_indices = np.where(valid_mask)[0]
        macd_valid = macd_line[valid_mask]
        signal_valid = compute_ema(macd_valid, signal_period)
        signal_line[valid_indices] = signal_valid

    histogram = macd_line - signal_line

    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }


def compute_atr(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
) -> np.ndarray:
    """
    Calculate Average True Range (ATR) using Wilder's smoothing.
    """
    n = len(close)
    atr = np.full(n, np.nan)
    if n <= period:
        return atr

    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        hl = high[i] - low[i]
        hpc = abs(high[i] - close[i - 1])
        lpc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hpc, lpc)

    atr[period - 1] = np.mean(tr[:period])
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


def compute_bollinger_bands(
    close: np.ndarray, period: int = 20, num_std: float = 2.0
) -> Dict[str, np.ndarray]:
    """Calculate Bollinger Bands (Middle, Upper, Lower)."""
    sma = compute_sma(close, period)
    n = len(close)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)

    for i in range(period - 1, n):
        window = close[i - period + 1 : i + 1]
        std = np.std(window)
        upper[i] = sma[i] + num_std * std
        lower[i] = sma[i] - num_std * std

    return {"middle": sma, "upper": upper, "lower": lower}


def find_swing_points(
    high: np.ndarray, low: np.ndarray, lookback: int = 5
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Detect local swing highs and swing lows for support/resistance and stop loss targeting.
    """
    n = len(high)
    swing_highs = []
    swing_lows = []

    for i in range(lookback, n - lookback):
        # Swing High: Highest in range [i - lookback, i + lookback]
        if high[i] == np.max(high[i - lookback : i + lookback + 1]):
            swing_highs.append({"index": i, "price": float(high[i])})

        # Swing Low: Lowest in range [i - lookback, i + lookback]
        if low[i] == np.min(low[i - lookback : i + lookback + 1]):
            swing_lows.append({"index": i, "price": float(low[i])})

    return {"highs": swing_highs, "lows": swing_lows}


# =============================================================================
# LAYER 1: MARKET STRUCTURE ANALYSIS (BOS / CHoCH / Trend Classification)
# =============================================================================

def detect_market_structure(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, lookback: int = 4
) -> Dict[str, Any]:
    """
    Analyzes price structure to determine trend state:
    - Higher Highs + Higher Lows = UPTREND
    - Lower Highs + Lower Lows = DOWNTREND
    - Mixed = RANGING
    Also detects Break of Structure (BOS) and Change of Character (CHoCH).
    """
    swings = find_swing_points(high, low, lookback=lookback)
    sh = swings["highs"]
    sl_pts = swings["lows"]

    structure = {
        "trend": "RANGING",
        "higher_highs": 0,
        "lower_lows": 0,
        "higher_lows": 0,
        "lower_highs": 0,
        "bos_detected": False,
        "bos_direction": None,
        "choch_detected": False,
        "choch_direction": None,
        "last_swing_high": float(high[-1]),
        "last_swing_low": float(low[-1]),
        "description": "Insufficient swing points for structure analysis",
    }

    # Need at least 3 swing highs and 3 swing lows for structure analysis
    if len(sh) < 3 or len(sl_pts) < 3:
        return structure

    # Analyze the last 4 swing points of each type for recency
    recent_highs = sh[-4:]
    recent_lows = sl_pts[-4:]

    structure["last_swing_high"] = recent_highs[-1]["price"]
    structure["last_swing_low"] = recent_lows[-1]["price"]

    # Count higher highs / lower highs
    hh_count = 0
    lh_count = 0
    for i in range(1, len(recent_highs)):
        if recent_highs[i]["price"] > recent_highs[i - 1]["price"]:
            hh_count += 1
        elif recent_highs[i]["price"] < recent_highs[i - 1]["price"]:
            lh_count += 1

    # Count higher lows / lower lows
    hl_count = 0
    ll_count = 0
    for i in range(1, len(recent_lows)):
        if recent_lows[i]["price"] > recent_lows[i - 1]["price"]:
            hl_count += 1
        elif recent_lows[i]["price"] < recent_lows[i - 1]["price"]:
            ll_count += 1

    structure["higher_highs"] = hh_count
    structure["lower_lows"] = ll_count
    structure["higher_lows"] = hl_count
    structure["lower_highs"] = lh_count

    # Determine trend from structure
    if hh_count >= 2 and hl_count >= 2:
        structure["trend"] = "UPTREND"
        structure["description"] = f"Confirmed uptrend: {hh_count} Higher Highs + {hl_count} Higher Lows"
    elif ll_count >= 2 and lh_count >= 2:
        structure["trend"] = "DOWNTREND"
        structure["description"] = f"Confirmed downtrend: {ll_count} Lower Lows + {lh_count} Lower Highs"
    elif hh_count >= 2 or hl_count >= 2:
        structure["trend"] = "UPTREND"
        structure["description"] = f"Developing uptrend: {hh_count} HH, {hl_count} HL"
    elif ll_count >= 2 or lh_count >= 2:
        structure["trend"] = "DOWNTREND"
        structure["description"] = f"Developing downtrend: {ll_count} LL, {lh_count} LH"
    else:
        structure["trend"] = "RANGING"
        structure["description"] = "Choppy / ranging market — no clear directional structure"

    # Break of Structure (BOS): current price broke past the last swing high (bullish) or low (bearish)
    price = float(close[-1])
    if price > recent_highs[-1]["price"]:
        structure["bos_detected"] = True
        structure["bos_direction"] = "BULLISH"
    elif price < recent_lows[-1]["price"]:
        structure["bos_detected"] = True
        structure["bos_direction"] = "BEARISH"

    # Change of Character (CHoCH): reversal of the prevailing pattern
    if structure["trend"] == "DOWNTREND" and hl_count >= 1 and hh_count >= 1:
        structure["choch_detected"] = True
        structure["choch_direction"] = "BULLISH_REVERSAL"
    elif structure["trend"] == "UPTREND" and lh_count >= 1 and ll_count >= 1:
        structure["choch_detected"] = True
        structure["choch_direction"] = "BEARISH_REVERSAL"

    return structure


# =============================================================================
# LAYER 2: SMART MONEY VOLUME ANALYSIS
# =============================================================================

def compute_volume_profile(
    close: np.ndarray, volume: np.ndarray, period: int = 20
) -> Dict[str, Any]:
    """
    Analyzes volume patterns for smart-money signals:
    - Volume spikes (>2x average)
    - Accumulation vs Distribution
    - Climactic volume (exhaustion signal)
    - Volume trend (rising/falling over recent bars)
    """
    n = len(volume)
    if n < period + 5:
        return {
            "avg_volume": 0.0,
            "current_volume": 0.0,
            "volume_ratio": 1.0,
            "is_spike": False,
            "is_climactic": False,
            "accumulation": "NEUTRAL",
            "volume_trend": "FLAT",
            "description": "Insufficient volume data",
        }

    avg_vol = float(np.mean(volume[-period:]))
    curr_vol = float(volume[-1])
    prev_vol = float(volume[-2])
    vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

    # Volume spike detection
    is_spike = vol_ratio > 2.0
    is_climactic = vol_ratio > 3.5  # Extreme volume = potential exhaustion

    # Accumulation vs Distribution
    # Rising price + rising volume = accumulation (bullish)
    # Rising price + falling volume = weak rally (distribution)
    # Falling price + rising volume = distribution (bearish)
    # Falling price + falling volume = weak selloff (accumulation starting)
    price_change = close[-1] - close[-5]  # 5-bar price direction
    vol_change = float(np.mean(volume[-3:])) - float(np.mean(volume[-8:-3]))  # 3-bar vs prior 5-bar

    if price_change > 0 and vol_change > 0:
        acc_dist = "ACCUMULATION"
        desc = "Price rising with increasing volume — strong institutional buying"
    elif price_change > 0 and vol_change <= 0:
        acc_dist = "WEAK_RALLY"
        desc = "Price rising but volume declining — weak rally, possible bull trap"
    elif price_change < 0 and vol_change > 0:
        acc_dist = "DISTRIBUTION"
        desc = "Price falling with increasing volume — institutional selling pressure"
    elif price_change < 0 and vol_change <= 0:
        acc_dist = "WEAK_SELLOFF"
        desc = "Price falling but volume declining — selling exhaustion, accumulation may start"
    else:
        acc_dist = "NEUTRAL"
        desc = "No significant volume pattern"

    # Volume trend over last 10 bars
    if n >= 10:
        recent_vols = volume[-10:]
        first_half = float(np.mean(recent_vols[:5]))
        second_half = float(np.mean(recent_vols[5:]))
        if second_half > first_half * 1.15:
            vol_trend = "RISING"
        elif second_half < first_half * 0.85:
            vol_trend = "FALLING"
        else:
            vol_trend = "FLAT"
    else:
        vol_trend = "FLAT"

    return {
        "avg_volume": round(avg_vol, 2),
        "current_volume": round(curr_vol, 2),
        "volume_ratio": round(vol_ratio, 2),
        "is_spike": is_spike,
        "is_climactic": is_climactic,
        "accumulation": acc_dist,
        "volume_trend": vol_trend,
        "description": desc,
    }


# =============================================================================
# LAYER 3: PROFESSIONAL CANDLESTICK PATTERN RECOGNITION
# =============================================================================

def detect_candle_patterns(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detects key candlestick patterns that professional traders watch:
    - Bullish/Bearish Engulfing
    - Hammer / Inverted Hammer / Shooting Star
    - Doji (indecision)
    - Morning Star / Evening Star (3-candle reversals)
    - Three White Soldiers / Three Black Crows
    """
    patterns = []
    bullish_count = 0
    bearish_count = 0

    if len(candles) < 5:
        return {"patterns": [], "bullish_count": 0, "bearish_count": 0, "summary": "Insufficient candle data"}

    # Helper: candle body and wick calculations
    def body(c):
        return abs(c["close"] - c["open"])

    def upper_wick(c):
        return c["high"] - max(c["close"], c["open"])

    def lower_wick(c):
        return min(c["close"], c["open"]) - c["low"]

    def is_bullish(c):
        return c["close"] > c["open"]

    def is_bearish(c):
        return c["close"] < c["open"]

    def total_range(c):
        return c["high"] - c["low"]

    c0 = candles[-1]  # Current candle
    c1 = candles[-2]  # Previous candle
    c2 = candles[-3]  # Two candles ago

    body0 = body(c0)
    body1 = body(c1)
    range0 = total_range(c0)
    range1 = total_range(c1)

    # Prevent divide by zero
    if range0 < 1e-10:
        range0 = 1e-10
    if range1 < 1e-10:
        range1 = 1e-10

    # ---- ENGULFING PATTERNS ----
    if is_bullish(c0) and is_bearish(c1) and c0["close"] > c1["open"] and c0["open"] < c1["close"] and body0 > body1:
        patterns.append({"name": "Bullish Engulfing", "type": "bullish", "strength": "strong"})
        bullish_count += 2

    if is_bearish(c0) and is_bullish(c1) and c0["close"] < c1["open"] and c0["open"] > c1["close"] and body0 > body1:
        patterns.append({"name": "Bearish Engulfing", "type": "bearish", "strength": "strong"})
        bearish_count += 2

    # ---- HAMMER / INVERTED HAMMER ----
    lw0 = lower_wick(c0)
    uw0 = upper_wick(c0)

    # Hammer: small body at top, long lower wick (>2x body), tiny upper wick
    if body0 > 0 and lw0 >= 2.0 * body0 and uw0 <= body0 * 0.5:
        patterns.append({"name": "Hammer (Bullish Reversal)", "type": "bullish", "strength": "moderate"})
        bullish_count += 1

    # Shooting Star / Inverted Hammer: small body at bottom, long upper wick
    if body0 > 0 and uw0 >= 2.0 * body0 and lw0 <= body0 * 0.5:
        if is_bearish(c0):
            patterns.append({"name": "Shooting Star (Bearish Reversal)", "type": "bearish", "strength": "moderate"})
            bearish_count += 1
        else:
            patterns.append({"name": "Inverted Hammer", "type": "bullish", "strength": "weak"})
            bullish_count += 1

    # ---- DOJI ----
    if range0 > 0 and body0 / range0 < 0.1:
        patterns.append({"name": "Doji (Market Indecision)", "type": "neutral", "strength": "moderate"})

    # ---- PIN BAR ----
    # Long wick on one side (>65% of total range) with small body
    if range0 > 0 and body0 / range0 < 0.35:
        if lw0 / range0 > 0.65:
            patterns.append({"name": "Bullish Pin Bar (Rejection Wick)", "type": "bullish", "strength": "strong"})
            bullish_count += 2
        elif uw0 / range0 > 0.65:
            patterns.append({"name": "Bearish Pin Bar (Rejection Wick)", "type": "bearish", "strength": "strong"})
            bearish_count += 2

    # ---- MORNING STAR (3-candle bullish reversal) ----
    if len(candles) >= 4:
        if is_bearish(c2) and body(c2) > body(c1) * 1.5 and is_bullish(c0) and body0 > body(c1) * 1.5:
            if c0["close"] > (c2["open"] + c2["close"]) / 2:
                patterns.append({"name": "Morning Star (Bullish Reversal)", "type": "bullish", "strength": "strong"})
                bullish_count += 2

    # ---- EVENING STAR (3-candle bearish reversal) ----
    if len(candles) >= 4:
        if is_bullish(c2) and body(c2) > body(c1) * 1.5 and is_bearish(c0) and body0 > body(c1) * 1.5:
            if c0["close"] < (c2["open"] + c2["close"]) / 2:
                patterns.append({"name": "Evening Star (Bearish Reversal)", "type": "bearish", "strength": "strong"})
                bearish_count += 2

    # ---- THREE WHITE SOLDIERS ----
    if len(candles) >= 4:
        c_3 = candles[-4]
        if all(is_bullish(c) for c in [c2, c1, c0]):
            if c1["close"] > c2["close"] and c0["close"] > c1["close"]:
                if body(c1) > range1 * 0.4 and body0 > range0 * 0.4:
                    patterns.append({"name": "Three White Soldiers (Strong Bullish)", "type": "bullish", "strength": "strong"})
                    bullish_count += 2

    # ---- THREE BLACK CROWS ----
    if len(candles) >= 4:
        if all(is_bearish(c) for c in [c2, c1, c0]):
            if c1["close"] < c2["close"] and c0["close"] < c1["close"]:
                if body(c1) > range1 * 0.4 and body0 > range0 * 0.4:
                    patterns.append({"name": "Three Black Crows (Strong Bearish)", "type": "bearish", "strength": "strong"})
                    bearish_count += 2

    # Summary
    if bullish_count > bearish_count:
        summary = f"Bullish candle bias: {len(patterns)} patterns detected"
    elif bearish_count > bullish_count:
        summary = f"Bearish candle bias: {len(patterns)} patterns detected"
    elif patterns:
        summary = f"Mixed candle signals: {len(patterns)} patterns detected"
    else:
        summary = "No significant candlestick patterns on recent bars"

    return {
        "patterns": patterns,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "summary": summary,
    }


# =============================================================================
# LAYER 6: BOLLINGER BAND SQUEEZE & VOLATILITY ANALYSIS
# =============================================================================

def compute_bollinger_squeeze(
    close: np.ndarray, bb_upper: np.ndarray, bb_lower: np.ndarray, bb_middle: np.ndarray
) -> Dict[str, Any]:
    """
    Detects Bollinger Band squeeze (low volatility = big move incoming)
    and band-walk conditions (strong trend riding the band).
    """
    n = len(close)
    if n < 25:
        return {
            "is_squeeze": False,
            "bandwidth": 0.0,
            "avg_bandwidth": 0.0,
            "band_walk": "NONE",
            "price_vs_bands": "MIDDLE",
            "description": "Insufficient data for squeeze analysis",
        }

    # Calculate bandwidth (upper - lower) / middle as % for the last 20 bars
    bandwidths = []
    for i in range(max(0, n - 20), n):
        if not np.isnan(bb_upper[i]) and not np.isnan(bb_lower[i]) and not np.isnan(bb_middle[i]) and bb_middle[i] > 0:
            bw = (bb_upper[i] - bb_lower[i]) / bb_middle[i]
            bandwidths.append(bw)

    if not bandwidths:
        return {
            "is_squeeze": False, "bandwidth": 0.0, "avg_bandwidth": 0.0,
            "band_walk": "NONE", "price_vs_bands": "MIDDLE",
            "description": "No valid Bollinger data",
        }

    curr_bw = float(bandwidths[-1])
    avg_bw = float(np.mean(bandwidths))

    # Squeeze: current bandwidth < 60% of average bandwidth
    # (bool() keeps this JSON/FastAPI serializable — avoids numpy.bool_)
    is_squeeze = bool(curr_bw < avg_bw * 0.6)

    # Price position relative to bands
    latest_price = float(close[-1])
    latest_upper = float(bb_upper[-1]) if not np.isnan(bb_upper[-1]) else latest_price
    latest_lower = float(bb_lower[-1]) if not np.isnan(bb_lower[-1]) else latest_price
    latest_mid = float(bb_middle[-1]) if not np.isnan(bb_middle[-1]) else latest_price

    band_range = latest_upper - latest_lower
    if band_range > 0:
        position = (latest_price - latest_lower) / band_range
    else:
        position = 0.5

    if position > 0.9:
        price_vs = "UPPER_BAND"
    elif position < 0.1:
        price_vs = "LOWER_BAND"
    elif position > 0.6:
        price_vs = "ABOVE_MIDDLE"
    elif position < 0.4:
        price_vs = "BELOW_MIDDLE"
    else:
        price_vs = "MIDDLE"

    # Band Walk: price consistently touching upper or lower band (last 5 candles)
    band_walk = "NONE"
    if n >= 5:
        upper_touches = 0
        lower_touches = 0
        for i in range(n - 5, n):
            if not np.isnan(bb_upper[i]) and close[i] >= bb_upper[i] * 0.998:
                upper_touches += 1
            if not np.isnan(bb_lower[i]) and close[i] <= bb_lower[i] * 1.002:
                lower_touches += 1
        if upper_touches >= 3:
            band_walk = "UPPER_WALK"
        elif lower_touches >= 3:
            band_walk = "LOWER_WALK"

    # Build description
    parts = []
    if is_squeeze:
        parts.append("⚡ Bollinger Squeeze detected — volatility compressed, expect a big move")
    if band_walk == "UPPER_WALK":
        parts.append("Price walking upper Bollinger Band — strong bullish momentum")
    elif band_walk == "LOWER_WALK":
        parts.append("Price walking lower Bollinger Band — strong bearish momentum")
    if price_vs == "UPPER_BAND" and not band_walk:
        parts.append("Price touching upper band — potential overbought / mean reversion risk")
    elif price_vs == "LOWER_BAND" and not band_walk:
        parts.append("Price touching lower band — potential oversold / bounce zone")

    desc = "; ".join(parts) if parts else "Normal volatility conditions"

    return {
        "is_squeeze": bool(is_squeeze),
        "bandwidth": round(curr_bw * 100, 3),  # as percentage
        "avg_bandwidth": round(avg_bw * 100, 3),
        "band_walk": band_walk,
        "price_vs_bands": price_vs,
        "description": desc,
    }


# =============================================================================
# MASTER INDICATOR CALCULATOR
# =============================================================================

def calculate_all_indicators(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Given raw candle dictionaries, compute ALL technical indicators:
    - Classic: EMA, RSI, MACD, ATR, Bollinger Bands, Swings
    - Pro: Market Structure, Volume Profile, Candle Patterns, BB Squeeze
    """
    if not candles:
        return {}

    closes = np.array([c["close"] for c in candles], dtype=np.float64)
    highs = np.array([c["high"] for c in candles], dtype=np.float64)
    lows = np.array([c["low"] for c in candles], dtype=np.float64)
    volumes = np.array([c["volume"] for c in candles], dtype=np.float64)

    ema20 = compute_ema(closes, 20)
    ema50 = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200)

    rsi = compute_rsi(closes, 14)
    macd_data = compute_macd(closes, 12, 26, 9)
    atr = compute_atr(highs, lows, closes, 14)
    bb = compute_bollinger_bands(closes, 20, 2.0)
    swings = find_swing_points(highs, lows, lookback=4)

    # Professional layers
    market_structure = detect_market_structure(highs, lows, closes, lookback=4)
    volume_profile = compute_volume_profile(closes, volumes, period=20)
    candle_patterns = detect_candle_patterns(candles)
    bb_squeeze = compute_bollinger_squeeze(closes, bb["upper"], bb["lower"], bb["middle"])

    # Convert NaNs to None for clean JSON serialization
    def clean(arr: np.ndarray) -> List[Optional[float]]:
        return [None if np.isnan(x) else round(float(x), 6) for x in arr]

    return {
        "closes": closes.tolist(),
        "ema20": clean(ema20),
        "ema50": clean(ema50),
        "ema200": clean(ema200),
        "rsi": clean(rsi),
        "macd": clean(macd_data["macd"]),
        "macd_signal": clean(macd_data["signal"]),
        "macd_hist": clean(macd_data["histogram"]),
        "atr": clean(atr),
        "bb_upper": clean(bb["upper"]),
        "bb_middle": clean(bb["middle"]),
        "bb_lower": clean(bb["lower"]),
        "swings": swings,
        "latest_price": float(closes[-1]),
        # Professional layers
        "market_structure": market_structure,
        "volume_profile": volume_profile,
        "candle_patterns": candle_patterns,
        "bb_squeeze": bb_squeeze,
    }
