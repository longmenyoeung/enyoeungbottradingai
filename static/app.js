/**
 * BINANCE SIGNAL PRO - Interactive Chart & Strategy Engine Frontend
 * Utilizes TradingView Lightweight Charts for high-performance rendering.
 */

// Application State
let currentSymbol = "BTCUSDT";
let currentInterval = "15m";
let currentFilter = "all";
let autoRefreshTimer = null;

// Chart instance & series references
let chart = null;
let candleSeries = null;
let volumeSeries = null;
let ema20Series = null;
let ema50Series = null;
let ema200Series = null;
let activePriceLines = [];

// DOM Elements
const chartContainer = document.getElementById("tvChartContainer");
const chartLoading = document.getElementById("chartLoading");
const symbolInput = document.getElementById("symbolInput");
const searchBtn = document.getElementById("searchBtn");
const refreshBtn = document.getElementById("refreshBtn");
const telegramBtn = document.getElementById("telegramBtn");
const currentPairText = document.getElementById("currentPairText");
const currentPriceText = document.getElementById("currentPriceText");
const chartTitle = document.getElementById("chartTitle");

// Signal DOM elements
const signalHero = document.getElementById("signalHero");
const signalStatusText = document.getElementById("signalStatusText");
const biasTag = document.getElementById("biasTag");
const confidenceTag = document.getElementById("confidenceTag");
const entryVal = document.getElementById("entryVal");
const slVal = document.getElementById("slVal");
const slSub = document.getElementById("slSub");
const tp1Val = document.getElementById("tp1Val");
const tp1Sub = document.getElementById("tp1Sub");
const tp2Val = document.getElementById("tp2Val");
const tp2Sub = document.getElementById("tp2Sub");
const tp3Val = document.getElementById("tp3Val");
const tp3Sub = document.getElementById("tp3Sub");
const rsiVal = document.getElementById("rsiVal");
const rsiStatus = document.getElementById("rsiStatus");
const macdVal = document.getElementById("macdVal");
const atrVal = document.getElementById("atrVal");
const supportVal = document.getElementById("supportVal");
const resistVal = document.getElementById("resistVal");
const reasonsList = document.getElementById("reasonsList");
const confluenceCount = document.getElementById("confluenceCount");

// Scanner elements
const scannerCards = document.getElementById("scannerCards");

/**
 * Initialize TradingView Lightweight Chart
 */
function initChart() {
  if (typeof LightweightCharts === "undefined") {
    console.error("LightweightCharts library not loaded");
    return;
  }

  // Clear previous container content except loading overlay
  chartContainer.innerHTML = "";
  chartContainer.appendChild(chartLoading);

  const containerRect = chartContainer.getBoundingClientRect();
  const width = containerRect.width || 800;
  const height = containerRect.height || 520;

  chart = LightweightCharts.createChart(chartContainer, {
    width: width,
    height: height,
    layout: {
      background: { color: "#080c14" },
      textColor: "#94a3b8",
      fontFamily: "'Inter', sans-serif",
    },
    grid: {
      vertLines: { color: "#131b29" },
      horzLines: { color: "#131b29" },
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
    },
    rightPriceScale: {
      borderColor: "#1e293b",
      scaleMargins: {
        top: 0.1,
        bottom: 0.2,
      },
    },
    timeScale: {
      borderColor: "#1e293b",
      timeVisible: true,
      secondsVisible: false,
    },
  });

  // Candlestick series
  candleSeries = chart.addCandlestickSeries({
    upColor: "#10b981",
    downColor: "#f43f5e",
    borderUpColor: "#10b981",
    borderDownColor: "#f43f5e",
    wickUpColor: "#10b981",
    wickDownColor: "#f43f5e",
  });

  // Volume series (histogram)
  volumeSeries = chart.addHistogramSeries({
    priceFormat: { type: "volume" },
    priceScaleId: "",
    scaleMargins: {
      top: 0.8,
      bottom: 0,
    },
  });

  // EMA series
  ema20Series = chart.addLineSeries({
    color: "#38bdf8",
    lineWidth: 1.5,
    title: "EMA 20",
  });

  ema50Series = chart.addLineSeries({
    color: "#f59e0b",
    lineWidth: 1.5,
    title: "EMA 50",
  });

  ema200Series = chart.addLineSeries({
    color: "#a855f7",
    lineWidth: 2,
    title: "EMA 200",
  });

  // Handle container and window resizing responsively
  const resizeChart = () => {
    if (chart && chartContainer) {
      const rect = chartContainer.getBoundingClientRect();
      chart.applyOptions({
        width: rect.width || chartContainer.clientWidth,
        height: rect.height || chartContainer.clientHeight,
      });
    }
  };

  window.addEventListener("resize", resizeChart);
  window.addEventListener("orientationchange", () => setTimeout(resizeChart, 200));

  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => resizeChart());
    ro.observe(chartContainer);
  }
}

/**
 * Clear existing Entry / TP / SL price lines
 */
function clearPriceLines() {
  if (!candleSeries) return;
  activePriceLines.forEach((line) => {
    try {
      candleSeries.removePriceLine(line);
    } catch (e) {}
  });
  activePriceLines = [];
}

/**
 * Draw horizontal visual levels for Entry, Stop Loss, and Take Profit
 */
function drawTradeLevels(sig) {
  clearPriceLines();
  if (!sig || !candleSeries) return;

  const showLines = document.getElementById("toggleLevels") ? document.getElementById("toggleLevels").checked : true;
  if (!showLines) return;

  // 1. Entry Line
  const entryLine = candleSeries.createPriceLine({
    price: sig.entry,
    color: "#06b6d4",
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: "🎯 ENTRY",
  });
  activePriceLines.push(entryLine);

  // 2. Stop Loss Line
  const slLine = candleSeries.createPriceLine({
    price: sig.stop_loss,
    color: "#f43f5e",
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Solid,
    axisLabelVisible: true,
    title: `🛑 SL (-${sig.risk_pct}%)`,
  });
  activePriceLines.push(slLine);

  // 3. Take Profit 1
  const tp1Line = candleSeries.createPriceLine({
    price: sig.take_profit_1,
    color: "#34d399",
    lineWidth: 1.5,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: `🟢 TP1 (+${sig.tp1_pct}%)`,
  });
  activePriceLines.push(tp1Line);

  // 4. Take Profit 2
  const tp2Line = candleSeries.createPriceLine({
    price: sig.take_profit_2,
    color: "#10b981",
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Solid,
    axisLabelVisible: true,
    title: `🚀 TP2 (+${sig.tp2_pct}%)`,
  });
  activePriceLines.push(tp2Line);
}

/**
 * Fetch and render market data for active symbol & interval
 */
async function loadChartData(symbol = currentSymbol, interval = currentInterval) {
  chartLoading.style.display = "flex";
  try {
    const res = await fetch(`/api/analyze?symbol=${encodeURIComponent(symbol)}&interval=${interval}`);
    const data = await res.json();

    if (!data.success) {
      showToast(data.error || "Failed to load data", "error");
      chartLoading.style.display = "none";
      return;
    }

    currentSymbol = data.symbol;
    currentInterval = data.interval;

    // Update Header Labels
    currentPairText.textContent = data.symbol;
    currentPriceText.textContent = `$${formatPrice(data.latest_price)}`;
    chartTitle.textContent = `${data.symbol} • ${interval.toUpperCase()} Binance Candlesticks`;

    // Populate chart candles & volume
    candleSeries.setData(data.candles);
    volumeSeries.setData(data.volume);

    // Populate EMAs
    const showEMA = document.getElementById("toggleEMA") ? document.getElementById("toggleEMA").checked : true;
    if (showEMA) {
      ema20Series.setData(data.ema20);
      ema50Series.setData(data.ema50);
      ema200Series.setData(data.ema200);
    } else {
      ema20Series.setData([]);
      ema50Series.setData([]);
      ema200Series.setData([]);
    }

    // Adjust chart time range
    chart.timeScale().fitContent();

    // Render Strategy Recommendations & Price Lines
    renderSignalDetails(data.signal);
    drawTradeLevels(data.signal);

  } catch (err) {
    console.error(err);
    showToast("Network error connecting to API", "error");
  } finally {
    chartLoading.style.display = "none";
  }
}

/**
 * Render Signal Intelligence Card details
 */
function renderSignalDetails(sig) {
  if (!sig) return;

  // Signal Hero class & text
  const signal = sig.signal || "NEUTRAL";
  signalHero.className = "signal-hero " + signal.toLowerCase().replace(" ", "-");
  signalStatusText.textContent = signal;

  biasTag.textContent = `BIAS: ${sig.bias || "NEUTRAL"}`;
  confidenceTag.textContent = `Confidence: ${sig.confidence || 50}%`;

  // Key Levels
  entryVal.textContent = `$${formatPrice(sig.entry)}`;
  slVal.textContent = `$${formatPrice(sig.stop_loss)}`;
  slSub.textContent = `Risk: -${sig.risk_pct}%  (SL Cushion)`;

  tp1Val.textContent = `$${formatPrice(sig.take_profit_1)}`;
  tp1Sub.textContent = `Target: +${sig.tp1_pct}%  (R:R ${sig.risk_reward_tp1 || "1:1.5"})`;

  tp2Val.textContent = `$${formatPrice(sig.take_profit_2)}`;
  tp2Sub.textContent = `Target: +${sig.tp2_pct}%  (R:R ${sig.risk_reward_tp2 || "1:2.5"})`;

  tp3Val.textContent = `$${formatPrice(sig.take_profit_3)}`;
  tp3Sub.textContent = `Runner: +${sig.tp3_pct}%  (Trend Continuation)`;

  // Indicators Bar
  rsiVal.textContent = sig.rsi || "--";
  if (sig.rsi < 30) {
    rsiStatus.textContent = "OVERSOLD";
    rsiStatus.style.background = "rgba(16, 185, 129, 0.2)";
    rsiStatus.style.color = "#10b981";
  } else if (sig.rsi > 70) {
    rsiStatus.textContent = "OVERBOUGHT";
    rsiStatus.style.background = "rgba(244, 63, 94, 0.2)";
    rsiStatus.style.color = "#f43f5e";
  } else {
    rsiStatus.textContent = "NEUTRAL";
    rsiStatus.style.background = "rgba(148, 163, 184, 0.2)";
    rsiStatus.style.color = "#94a3b8";
  }

  macdVal.textContent = sig.macd_hist !== undefined ? sig.macd_hist : "--";
  macdVal.style.color = sig.macd_hist >= 0 ? "#10b981" : "#f43f5e";

  atrVal.textContent = `$${formatPrice(sig.atr)}`;
  supportVal.textContent = `$${formatPrice(sig.support)}`;
  resistVal.textContent = `$${formatPrice(sig.resistance)}`;

  // Confluence Factors
  reasonsList.innerHTML = "";
  const reasons = sig.reasons || [];
  confluenceCount.textContent = `${reasons.length} factors`;

  if (reasons.length === 0) {
    reasonsList.innerHTML = `<li>Market consolidates with no strong catalyst yet.</li>`;
  } else {
    reasons.forEach((r) => {
      const li = document.createElement("li");
      li.textContent = r;
      reasonsList.appendChild(li);
    });
  }
}

/**
 * Fetch and populate Market Scanner Watchlist
 */
async function loadScanner(interval = currentInterval) {
  try {
    const res = await fetch(`/api/scanner?interval=${interval}`);
    const data = await res.json();
    if (!data.success) return;

    renderScannerCards(data.results || []);
  } catch (e) {
    console.warn("Scanner fetch error:", e);
  }
}

function renderScannerCards(items) {
  scannerCards.innerHTML = "";

  const filtered = items.filter((item) => {
    if (currentFilter === "buy") return item.signal.includes("BUY");
    if (currentFilter === "sell") return item.signal.includes("SELL");
    return true;
  });

  if (filtered.length === 0) {
    scannerCards.innerHTML = `<div class="scanner-loading">No assets matching "${currentFilter}" filter.</div>`;
    return;
  }

  filtered.forEach((item) => {
    const card = document.createElement("div");
    card.className = "scan-card";
    const badgeClass = item.signal.toLowerCase().replace(" ", "-");

    card.innerHTML = `
      <div class="scan-card-top">
        <span class="scan-sym">${item.symbol}</span>
        <span class="scan-badge ${badgeClass}">${item.signal}</span>
      </div>
      <div class="scan-price-row">
        <span class="scan-price">$${formatPrice(item.price)}</span>
        <span style="font-size: 11px; color: #94a3b8;">RSI: ${item.rsi}</span>
      </div>
      <div class="scan-targets">
        <span class="scan-tp">TP: +${item.tp1_pct}%</span>
        <span class="scan-sl">SL: -${item.risk_pct}%</span>
      </div>
    `;

    card.addEventListener("click", () => {
      currentSymbol = item.symbol;
      loadChartData(currentSymbol, currentInterval);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    scannerCards.appendChild(card);
  });
}

/**
 * Number formatting helper
 */
function formatPrice(val) {
  if (val === undefined || val === null || isNaN(val)) return "0.00";
  const num = parseFloat(val);
  if (num >= 1000) return num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (num >= 1) return num.toFixed(4);
  return num.toFixed(6);
}

/**
 * Toast Notification system
 */
function showToast(msg, type = "info") {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.style.borderColor = type === "error" ? "#f43f5e" : "#38bdf8";
  toast.className = "toast show";
  setTimeout(() => {
    toast.className = "toast";
  }, 3500);
}

/**
 * Event Listeners & Initialization
 */
function setupEventListeners() {
  // Timeframe switch
  const tfButtons = document.querySelectorAll(".tf-btn");
  tfButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tfButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentInterval = btn.getAttribute("data-tf");
      loadChartData(currentSymbol, currentInterval);
      loadScanner(currentInterval);
    });
  });

  // Search input & button
  searchBtn.addEventListener("click", () => {
    const val = symbolInput.value.trim().toUpperCase();
    if (val) {
      currentSymbol = val.endsWith("USDT") ? val : val + "USDT";
      loadChartData(currentSymbol, currentInterval);
      symbolInput.value = "";
    }
  });

  symbolInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      searchBtn.click();
    }
  });

  // Manual Refresh
  refreshBtn.addEventListener("click", () => {
    loadChartData(currentSymbol, currentInterval);
    loadScanner(currentInterval);
    showToast("Data refreshed from Binance", "info");
  });

  // Telegram alert button
  telegramBtn.addEventListener("click", async () => {
    try {
      telegramBtn.disabled = true;
      const res = await fetch(`/api/notify?symbol=${encodeURIComponent(currentSymbol)}&interval=${currentInterval}`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.success) {
        showToast("✈️ Signal alert sent to Telegram!", "info");
      } else {
        showToast("ℹ️ " + (data.message || "Configure TELEGRAM_BOT_TOKEN in .env to enable"), "info");
      }
    } catch (e) {
      showToast("Error sending notification", "error");
    } finally {
      telegramBtn.disabled = false;
    }
  });

  // Indicator toggles
  const toggleEMA = document.getElementById("toggleEMA");
  if (toggleEMA) {
    toggleEMA.addEventListener("change", () => {
      loadChartData(currentSymbol, currentInterval);
    });
  }

  const toggleLevels = document.getElementById("toggleLevels");
  if (toggleLevels) {
    toggleLevels.addEventListener("change", () => {
      loadChartData(currentSymbol, currentInterval);
    });
  }

  // Scanner filter buttons
  const filterBtns = document.querySelectorAll(".filter-btn");
  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      filterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.getAttribute("data-filter");
      loadScanner(currentInterval);
    });
  });

  // Auto-refresh interval (every 20s)
  autoRefreshTimer = setInterval(() => {
    loadChartData(currentSymbol, currentInterval);
  }, 20000);
}

// Startup
document.addEventListener("DOMContentLoaded", () => {
  initChart();
  setupEventListeners();
  loadChartData(currentSymbol, currentInterval);
  loadScanner(currentInterval);
});
