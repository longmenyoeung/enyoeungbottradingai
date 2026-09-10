"""
Technical Indicators Calculation Engine.
Calculates EMA, SMA, RSI, MACD, ATR, Bollinger Bands, and Swing Pivots using NumPy.
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


def calculate_all_indicators(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Given raw candle dictionaries, compute all technical indicators and attach them.
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
    }
