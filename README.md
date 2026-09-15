# ⚡ Men Trading - AI Quantitative Crypto & Forex Terminal & Signal Bot

An automated crypto **and Forex** trading signal and chart analysis system.
Analyzes real-time candlestick data across multi-timeframe charts to detect trend alignment, momentum shifts, and volatility-adjusted risk levels.

---

## 🎯 Features

- **Branding**: Official **Men Trading** AI Quantitative Terminal.
- **Dual Market Switching (🪙 Crypto / 💱 Forex)**: One-tap toggle between Binance crypto pairs and 28+ forex currency pairs.
- **50+ Cryptos & Sector Filters**:
  - Live scanning across **Majors, Layer 1/2, DeFi, AI & Big Data, and Trending Memes**.
  - Instant autocomplete search for 50+ Binance USDT trading pairs.
- **Forex Market (Majors / Minors / Exotics)**:
  - **28 pairs**: majors (EURUSD, GBPUSD, USDJPY…), minors/crosses (EURGBP, GBPJPY, AUDNZD…) and exotics (USDTRY, USDZAR, EURNOK…).
  - Twelve Data primary feed with automatic **Yahoo Finance fallback**, plus a built-in rate-limit throttle for the free tier.
  - **Pip-based precision** (5 decimals / 3 for JPY pairs) with SL/TP distances shown in pips.
  - **Market-hours awareness**: "Forex Market Closed" banner + Sydney / Tokyo / London / New York session badges (Mon–Fri only).
- **Multi-Timeframe (MTF) Confluence Matrix**:
  - Real-time trend & momentum consensus across **5m, 15m, 1h, 4h, and 1D** simultaneously.
  - Overall Confluence Percentage Score and 1-click timeframe switching.
- **Interactive Position Size & Risk Calculator (with Leverage)**:
  - Calculates exact position size in USD and coins (or base-currency units for FX) based on your account size and risk %.
  - Live leverage simulator (1x to 50x) with margin requirement and liquidation safety warning.
  - Projected profit and R:R calculations for TP1, TP2, and TP3.
- **Live Audio Chime & Visual Signal Alerts**:
  - Synthesized Web Audio alert chimes when new BUY/SELL signals trigger.
  - One-click sound toggle (Mute / Sound ON).
- **Automated Entry & Exit Targets**:
  - **Optimal Entry Price**: Trend & momentum confluence trigger.
  - **Stop Loss (SL)**: Dynamically adjusted via ATR (Average True Range) and swing pivots — **asset-class aware** (crypto: 1.5× ATR, FX: 2.0× ATR with pip-scaled stop bands).
  - **Take Profit 1 (TP1)**: 1 : 1.5 Risk-to-Reward ratio.
  - **Take Profit 2 (TP2)**: 1 : 2.5 Risk-to-Reward ratio.
  - **Take Profit 3 (TP3)**: 1 : 3.5 Risk-to-Reward runner.
- **Market Sentiment Intelligence**:
  - **Crypto**: Fear & Greed Index, trending coins, global market stats.
  - **Forex**: **DXY dollar-strength gauge**, **VIX risk-on/risk-off regime**, USD bias and active session liquidity — fed into the strategy engine as pair-aware sentiment (USD base vs USD quote vs crosses).
- **Interactive Web Dashboard**:
  - TradingView Lightweight Charts rendering candles and volume.
  - Live horizontal visual lines for Entry, SL, and TP levels directly on the chart.
  - EMA (20, 50, 200) trend indicator overlays.
- **24/7 Telegram Alerts**:
  - Background worker continuously monitors signals and pushes alerts directly to your phone (crypto always; forex during market hours).
  - Forex alerts use pip precision and a `FOREX SIGNAL` header, crypto keeps the `BINANCE SIGNAL` header.
- **CLI Runner**:
  - Fast command-line interface for terminal users (crypto).

---

## 🚀 Quick Start (Local)

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Telegram & Forex Data (Optional)**:
   Create a `.env` file:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here

   # Forex data provider (free key: https://twelvedata.com — 800 req/day, 8 req/min)
   # Leave empty to run Forex mode entirely on the keyless Yahoo Finance fallback.
   TWELVE_DATA_API_KEY=
   ```

3. **Launch the Dashboard**:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```
   Open [http://localhost:8000](http://localhost:8000) in your browser.

4. **Terminal CLI Scan**:
   ```bash
   python cli_bot.py --scan
   python cli_bot.py --symbol BTCUSDT --interval 15m
   ```

---

## 🧪 Tests

```bash
python -m pytest test_analysis.py -v   # 16 unit tests (crypto + forex), no network needed
python test_analysis.py               # unit tests + live integration checks
```

---

## 🔌 API Reference

All endpoints accept a `market` query parameter (`crypto` default, or `forex`):

| Endpoint | Description |
| --- | --- |
| `GET /api/analyze?symbol=EURUSD&interval=15m&market=forex` | Candles, indicators and signals (pip-precise for FX) |
| `GET /api/symbols?market=forex&category=majors` | Categorized instrument list with live quotes |
| `GET /api/scanner?market=forex&category=exotics&interval=1h` | Multi-pair trade scanner |
| `GET /api/mtf?symbol=GBPJPY&market=forex` | 5m/15m/1h/4h/1d confluence matrix |
| `GET /api/sentiment?market=forex` | Crypto Fear & Greed **or** FX DXY/VIX/session snapshot |
| `POST /api/notify?symbol=EURUSD&interval=15m&market=forex` | Push the current signal to Telegram |

---

## ☁️ Free Cloud Deployment (Render / Koyeb)

1. Connect this repository to [Render](https://render.com).
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Set Environment Variables:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `TWELVE_DATA_API_KEY` (optional, recommended for Forex)

---

## 🤖 Official Telegram Bot & Admin Contact

- **Live Signal Bot**: [https://t.me/menyoeungtradingaibot](https://t.me/menyoeungtradingaibot) (`@menyoeungtradingaibot`)
- **Admin Support**: [https://t.me/Menyoeunglong](https://t.me/Menyoeunglong) (`@Menyoeunglong`)
- **GitHub**: [https://github.com/longmenyoeung](https://github.com/longmenyoeung) (`@longmenyoeung`)

