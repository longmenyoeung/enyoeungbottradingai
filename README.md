# ⚡ Men Trading - AI Quantitative Crypto Terminal & Signal Bot

An automated crypto trading signal and chart analysis system for **Binance**.
Analyzes real-time candlestick data across multi-timeframe charts to detect trend alignment, momentum shifts, and volatility-adjusted risk levels.

---

## 🎯 Features

- **Branding**: Official **Men Trading** AI Quantitative Terminal.
- **50+ Cryptos & Sector Filters**:
  - Live scanning across **Majors, Layer 1/2, DeFi, AI & Big Data, and Trending Memes**.
  - Instant autocomplete search for 50+ Binance USDT trading pairs.
- **Multi-Timeframe (MTF) Confluence Matrix**:
  - Real-time trend & momentum consensus across **5m, 15m, 1h, 4h, and 1D** simultaneously.
  - Overall Confluence Percentage Score and 1-click timeframe switching.
- **Interactive Position Size & Risk Calculator (with Leverage)**:
  - Calculates exact position size in USD and coins based on your account size and risk %.
  - Live leverage simulator (1x to 50x) with margin requirement and liquidation safety warning.
  - Projected profit and R:R calculations for TP1, TP2, and TP3.
- **Live Audio Chime & Visual Signal Alerts**:
  - Synthesized Web Audio alert chimes when new BUY/SELL signals trigger.
  - One-click sound toggle (Mute / Sound ON).
- **Automated Entry & Exit Targets**:
  - **Optimal Entry Price**: Trend & momentum confluence trigger.
  - **Stop Loss (SL)**: Dynamically adjusted via ATR (Average True Range) and swing pivots.
  - **Take Profit 1 (TP1)**: 1 : 1.5 Risk-to-Reward ratio.
  - **Take Profit 2 (TP2)**: 1 : 2.5 Risk-to-Reward ratio.
  - **Take Profit 3 (TP3)**: 1 : 3.5 Risk-to-Reward runner.
- **Interactive Web Dashboard**:
  - TradingView Lightweight Charts rendering candles and volume.
  - Live horizontal visual lines for Entry, SL, and TP levels directly on the chart.
  - EMA (20, 50, 200) trend indicator overlays.
- **24/7 Telegram Alerts**:
  - Background worker continuously monitors signals and pushes alerts directly to your phone.
- **CLI Runner**:
  - Fast command-line interface for terminal users.

---

## 🚀 Quick Start (Local)

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Telegram (Optional)**:
   Create a `.env` file:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
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

## ☁️ Free Cloud Deployment (Render / Koyeb)

1. Connect this repository to [Render](https://render.com).
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Set Environment Variables:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

---

## 🤖 Official Telegram Bot & Admin Contact

- **Live Signal Bot**: [https://t.me/menyoeungtradingaibot](https://t.me/menyoeungtradingaibot) (`@menyoeungtradingaibot`)
- **Admin Support**: [https://t.me/Menyoeunglong](https://t.me/Menyoeunglong) (`@Menyoeunglong`)
- **GitHub**: [https://github.com/longmenyoeung](https://github.com/longmenyoeung) (`@longmenyoeung`)

