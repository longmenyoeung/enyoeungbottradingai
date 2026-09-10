"""
Telegram Chat ID Auto-Detector & Test Notifier.
Run this script to automatically detect your Chat ID when you message your bot.
"""

import asyncio
import time
import httpx
from pathlib import Path

TOKEN = "8791914168:AAGyKMKNlIF-LUT26nvd8Hqc2xyW7X1AOcA"
ENV_PATH = Path(__file__).resolve().parent / ".env"


def update_env_file(chat_id: str):
    content = f"TELEGRAM_BOT_TOKEN={TOKEN}\nTELEGRAM_CHAT_ID={chat_id}\n"
    ENV_PATH.write_text(content, encoding="utf-8")
    print(f"\n✅ Saved TELEGRAM_CHAT_ID={chat_id} to .env!")


async def detect_and_test():
    print("=" * 60)
    print("🤖 TELEGRAM BOT CONNECTION HELPER")
    print("Bot Username: @menyoeungtradingaibot")
    print("=" * 60)
    print("\n👉 Please open Telegram on your phone or PC, search for:")
    print("   @menyoeungtradingaibot")
    print("   and send the message: /start (or any message)")
    print("\n⏳ Listening for incoming message from you (Ctrl+C to stop)...")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Check updates in a loop
        for attempt in range(60):
            try:
                res = await client.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates")
                data = res.json()
                results = data.get("result", [])

                if results:
                    latest = results[-1]
                    message = latest.get("message") or latest.get("channel_post") or {}
                    chat = message.get("chat", {})
                    chat_id = str(chat.get("id", ""))
                    user_name = chat.get("first_name", "Trader")

                    if chat_id:
                        print(f"\n🎉 Message detected from {user_name}! Chat ID: {chat_id}")
                        update_env_file(chat_id)

                        # Send test notification
                        welcome_text = (
                            f"👋 *Hello {user_name}!*\n\n"
                            f"⚡ *Binance Trading Signal Bot Connected Successfully!*\n"
                            f"You will now receive Entry, Take Profit (TP), and Stop Loss (SL) alerts directly in this chat.\n\n"
                            f"Happy Trading! 🚀"
                        )
                        send_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                        await client.post(
                            send_url,
                            json={"chat_id": chat_id, "text": welcome_text, "parse_mode": "Markdown"},
                        )
                        print("🚀 Sent welcome confirmation message to your Telegram!")
                        return chat_id
            except Exception as e:
                pass

            await asyncio.sleep(2)

    print("\n⚠️ Timed out waiting for message. Make sure to open @menyoeungtradingaibot and send /start.")


if __name__ == "__main__":
    asyncio.run(detect_and_test())
