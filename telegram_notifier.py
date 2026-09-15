"""
Telegram Alert Notifier (Optional).
Sends formatted Telegram alerts when a high-probability trade setup triggers.
Works for both Binance crypto pairs and Forex currency pairs (pip precision).
Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env or environment.
"""

import os
import re
from typing import Any, Dict, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Minimal currency universe used to detect FX symbols when asset_class is not supplied.
# Mirrors forex_client.CURRENCY_CODES without importing the data-provider module.
_FX_CURRENCIES = {
    "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD",
    "TRY", "ZAR", "MXN", "NOK", "SEK", "SGD", "HKD", "DKK",
    "PLN", "HUF", "CZK", "CNH", "CNY", "ILS", "THB", "INR", "KRW", "BRL", "RUB",
}


def _is_forex_symbol(symbol: str) -> bool:
    """True when a symbol looks like an FX pair (e.g. EURUSD, USDJPY)."""
    clean = re.sub(r"[^A-Z]", "", str(symbol or "").upper())
    if len(clean) != 6:
        return False
    base, quote = clean[:3], clean[3:]
    return base != quote and base in _FX_CURRENCIES and quote in _FX_CURRENCIES


def _forex_decimals(symbol: str) -> int:
    """Broker quote precision: 3 decimals for JPY pairs, 5 for everything else."""
    return 3 if str(symbol or "").upper().endswith("JPY") else 5


def build_alert_text(
    signal_data: Dict[str, Any],
    interval: str = "15m",
    asset_class: Optional[str] = None,
) -> str:
    """
    Builds the Markdown alert body (no network calls — unit-testable).

    Forex signals use pip precision (5 decimals / 3 for JPY pairs) plus a pip
    distance line, while crypto signals keep the classic BINANCE header format.
    """
    symbol = signal_data.get("symbol", "CRYPTO")
    signal = signal_data.get("signal", "NEUTRAL")
    price = signal_data.get("price", 0.0)
    entry = signal_data.get("entry", 0.0)
    sl = signal_data.get("stop_loss", 0.0)
    tp1 = signal_data.get("take_profit_1", 0.0)
    tp2 = signal_data.get("take_profit_2", 0.0)
    risk_pct = signal_data.get("risk_pct", 0.0)
    tp1_pct = signal_data.get("tp1_pct", 0.0)
    tp2_pct = signal_data.get("tp2_pct", 0.0)
    bias = signal_data.get("bias", "LONG")

    # Asset class: explicit argument > strategy output > symbol shape
    resolved_class = (asset_class or signal_data.get("asset_class") or "").lower().strip()
    is_forex = resolved_class == "forex" or (resolved_class != "crypto" and _is_forex_symbol(symbol))

    if is_forex:
        decimals = int(signal_data.get("price_decimals") or _forex_decimals(symbol))
        header = "FOREX SIGNAL"
        money = lambda value: f"`{float(value or 0.0):,.{decimals}f}`"
    else:
        header = "BINANCE SIGNAL"
        money = lambda value: f"`${float(value or 0.0):,.4f}`"

    action_emoji = "🟢🚀" if "BUY" in signal else ("🔴🔻" if "SELL" in signal else "⚪⚖️")

    text = (
        f"{action_emoji} *{header}: {symbol}* [{interval.upper()}]\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *Signal:* `{signal}` ({bias})\n"
        f"💰 *Current Price:* {money(price)}\n\n"
        f"📌 *Recommended Entry:* {money(entry)}\n"
        f"🛑 *Stop Loss (SL):* {money(sl)} (-{risk_pct}%)\n"
        f"🎯 *Take Profit 1 (TP1):* {money(tp1)} (+{tp1_pct}%)\n"
        f"🚀 *Take Profit 2 (TP2):* {money(tp2)} (+{tp2_pct}%)\n"
        f"⚖️ *Risk/Reward (TP2):* `{signal_data.get('risk_reward_tp2', '1:2.5')}`\n"
    )

    if is_forex:
        risk_pips = signal_data.get("risk_pips")
        tp1_pips = signal_data.get("tp1_pips")
        if risk_pips is not None:
            text += f"📏 *SL Distance:* `{risk_pips} pips`"
            if tp1_pips is not None:
                text += f" | *TP1:* `{tp1_pips} pips`"
            text += "\n"

    text += "\n📊 *Key Confluences:*\n"

    reasons = signal_data.get("reasons", [])
    for r in reasons[:4]:
        text += f"• {r}\n"

    return text


async def send_signal_alert(
    signal_data: Dict[str, Any],
    interval: str = "15m",
    asset_class: Optional[str] = None,
) -> bool:
    """Send formatted markdown alert to Telegram chat (crypto or forex)."""
    load_dotenv(override=True)
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token or not chat_id:
        return False

    text = build_alert_text(signal_data, interval, asset_class)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception:
        return False
