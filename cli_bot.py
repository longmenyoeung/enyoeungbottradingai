"""
CLI Crypto Analysis & Signal Bot.
Run from terminal to inspect any Binance pair or scan top cryptos.

Usage:
  python cli_bot.py --symbol BTCUSDT --interval 15m
  python cli_bot.py --scan
  python cli_bot.py --watch --symbol ETHUSDT --interval 5m
"""

import argparse
import asyncio
import sys
import time

# Ensure Windows terminal handles UTF-8 properly
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from binance_client import fetch_klines, get_top_symbols, DEFAULT_WATCHLIST
from indicators import calculate_all_indicators
from strategy import analyze_market_signals
from telegram_notifier import send_signal_alert


def print_banner():
    print("""
 ==================================================================
         BINANCE CRYPTO CHART ANALYZER & SIGNAL BOT               
          Smart Entry | Take Profit (TP) | Stop Loss (SL)         
 ==================================================================
    """)



def format_signal(analysis: dict, interval: str):
    sig = analysis["signal"]
    symbol = analysis["symbol"]
    price = analysis["price"]
    bias = analysis["bias"]

    color_reset = "\033[0m"
    color_green = "\033[92m\033[1m"
    color_red = "\033[91m\033[1m"
    color_yellow = "\033[93m\033[1m"
    color_cyan = "\033[96m"

    if "BUY" in sig:
        badge = f"{color_green}[ {sig} ({bias}) ]{color_reset}"
    elif "SELL" in sig:
        badge = f"{color_red}[ {sig} ({bias}) ]{color_reset}"
    else:
        badge = f"{color_yellow}[ {sig} ({bias}) ]{color_reset}"

    print("-" * 68)
    print(f"PAIR: {symbol} | INTERVAL: {interval.upper()} | CURRENT PRICE: ${price:,.4f}")
    print(f"SIGNAL: {badge}  |  Confidence Score: {analysis['confidence']}%")
    print("-" * 68)
    print(f"  [*] ENTRY PRICE        : ${analysis['entry']:,.4f}")
    print(f"  [!] STOP LOSS (SL)     : ${analysis['stop_loss']:,.4f}  (-{analysis['risk_pct']}%)")
    print(f"  [+] TAKE PROFIT 1 (TP1): ${analysis['take_profit_1']:,.4f}  (+{analysis['tp1_pct']}%)  [R:R {analysis['risk_reward_tp1']}]")
    print(f"  [+] TAKE PROFIT 2 (TP2): ${analysis['take_profit_2']:,.4f}  (+{analysis['tp2_pct']}%)  [R:R {analysis['risk_reward_tp2']}]")
    print(f"  [+] TAKE PROFIT 3 (TP3): ${analysis['take_profit_3']:,.4f}  (+{analysis['tp3_pct']}%)")
    print("-" * 68)
    print("INDICATOR SNAPSHOT:")
    print(f"  - RSI (14) : {analysis['rsi']}  |  MACD Hist: {analysis['macd_hist']}  |  ATR: {analysis['atr']}")
    print(f"  - EMA 20   : ${analysis['ema20']:,.2f}  |  EMA 50: ${analysis['ema50']:,.2f}  |  EMA 200: ${analysis['ema200']:,.2f}")
    print(f"  - Support  : ${analysis['support']:,.2f}  |  Resistance: ${analysis['resistance']:,.2f}")
    print("-" * 68)
    print("ANALYSIS CONFLUENCES:")
    for r in analysis["reasons"]:
        print(f"  > {r}")
    print("=" * 68 + "\n")


async def analyze_symbol(symbol: str, interval: str, alert: bool = False):
    candles = await fetch_klines(symbol, interval, limit=250)
    indicators = calculate_all_indicators(candles)
    analysis = analyze_market_signals(candles, indicators, symbol)
    format_signal(analysis, interval)

    if alert and ("BUY" in analysis["signal"] or "SELL" in analysis["signal"]):
        sent = await send_signal_alert(analysis, interval)
        if sent:
            print("🔔 Telegram alert sent successfully!")


async def scan_market(interval: str = "15m"):
    print_banner()
    print(f"🔍 Scanning Binance Top Pairs for signals on [{interval}] timeframe...\n")
    top_items = await get_top_symbols(12)
    symbols = [item["symbol"] for item in top_items] if top_items else DEFAULT_WATCHLIST

    results = []
    for sym in symbols:
        try:
            candles = await fetch_klines(sym, interval, limit=150)
            indicators = calculate_all_indicators(candles)
            analysis = analyze_market_signals(candles, indicators, sym)
            results.append(analysis)
        except Exception as e:
            pass

    print(f"{'SYMBOL':<10} {'PRICE':<12} {'SIGNAL':<14} {'ENTRY':<12} {'SL (-%)':<14} {'TP1 (+%)':<14} {'TP2 (+%)':<14}")
    print("-" * 92)
    for r in results:
        sig = r["signal"]
        sl_str = f"${r['stop_loss']:<7} (-{r['risk_pct']}%)"
        tp1_str = f"${r['take_profit_1']:<7} (+{r['tp1_pct']}%)"
        tp2_str = f"${r['take_profit_2']:<7} (+{r['tp2_pct']}%)"
        print(f"{r['symbol']:<10} ${r['price']:<11.4f} {sig:<14} ${r['entry']:<11.4f} {sl_str:<14} {tp1_str:<14} {tp2_str:<14}")
    print("-" * 92)
    print("\n💡 Run `python cli_bot.py --symbol <COIN> --interval <15m/1h>` for full breakdown.\n")


async def main():
    parser = argparse.ArgumentParser(description="Binance Crypto Chart Analysis & Signal Bot")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair (default: BTCUSDT)")
    parser.add_argument("--interval", type=str, default="15m", help="Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)")
    parser.add_argument("--scan", action="store_true", help="Scan top crypto pairs for signals")
    parser.add_argument("--watch", action="store_true", help="Continuously monitor every 30s")
    parser.add_argument("--alert", action="store_true", help="Send alert to Telegram if configured")

    args = parser.parse_args()

    if args.scan:
        await scan_market(args.interval)
        return

    print_banner()
    if args.watch:
        print(f"👀 Live monitoring {args.symbol} on {args.interval} every 30 seconds... (Ctrl+C to stop)")
        while True:
            try:
                await analyze_symbol(args.symbol, args.interval, args.alert)
                await asyncio.sleep(30)
            except KeyboardInterrupt:
                print("\nMonitoring stopped.")
                break
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(10)
    else:
        await analyze_symbol(args.symbol, args.interval, args.alert)


if __name__ == "__main__":
    asyncio.run(main())
