"""
Telegram Alert Notifier (Optional).
Sends formatted Telegram alerts when a high-probability trade setup triggers.
Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env or environment.
"""

import os
from typing import Any, Dict
import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


async def send_signal_alert(signal_data: Dict[str, Any], interval: str = "15m") -> bool:
    """Send formatted markdown alert to Telegram chat."""
    load_dotenv(override=True)
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token or not chat_id:
        return False

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

    action_emoji = "🟢🚀" if "BUY" in signal else ("🔴🔻" if "SELL" in signal else "⚪⚖️")

    text = (
        f"{action_emoji} *BINANCE SIGNAL: {symbol}* [{interval.upper()}]\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *Signal:* `{signal}` ({bias})\n"
        f"💰 *Current Price:* `${price:,.4f}`\n\n"
        f"📌 *Recommended Entry:* `${entry:,.4f}`\n"
        f"🛑 *Stop Loss (SL):* `${sl:,.4f}` (-{risk_pct}%)\n"
        f"🎯 *Take Profit 1 (TP1):* `${tp1:,.4f}` (+{tp1_pct}%)\n"
        f"🚀 *Take Profit 2 (TP2):* `${tp2:,.4f}` (+{tp2_pct}%)\n"
        f"⚖️ *Risk/Reward (TP2):* `{signal_data.get('risk_reward_tp2', '1:2.5')}`\n\n"
        f"📊 *Key Confluences:*\n"
    )

    reasons = signal_data.get("reasons", [])
    for r in reasons[:4]:
        text += f"• {r}\n"

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
