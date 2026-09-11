/**
 * MEN TRADING - AI Quantitative Crypto Chart & Strategy Engine Frontend
 * Interactive TradingView Lightweight Charts, Multi-Timeframe Confluence,
 * 50+ Coin Scanner, Position Size & Risk Calculator, and Audio Alerts.
 */

// Application State
let currentSymbol = "BTCUSDT";
let currentInterval = "15m";
let currentFilter = "all";
let currentCategory = "all";
let audioEnabled = true;
let lastObservedSignal = "";
let activeSignalData = null;
let autoRefreshTimer = null;
let allSymbolsCache = [];

// Chart instance & series references
let chart = null;
let candleSeries = null;
let volumeSeries = null;
let ema20Series = null;
let ema50Series = null;
let ema200Series = null;
let activePriceLines = [];

// DOM Elements - Navigation & Header
const chartContainer = document.getElementById("tvChartContainer");
const chartLoading = document.getElementById("chartLoading");
const symbolInput = document.getElementById("symbolInput");
const searchBtn = document.getElementById("searchBtn");
const refreshBtn = document.getElementById("refreshBtn");
const telegramBtn = document.getElementById("telegramBtn");
const audioToggleBtn = document.getElementById("audioToggleBtn");
const audioIcon = document.getElementById("audioIcon");
const audioText = document.getElementById("audioText");
const calcModalBtn = document.getElementById("calcModalBtn");
const signalCalcBtn = document.getElementById("signalCalcBtn");
const currentPairText = document.getElementById("currentPairText");
const currentPriceText = document.getElementById("currentPriceText");
const pairCategoryBadge = document.getElementById("pairCategoryBadge");
const chartTitle = document.getElementById("chartTitle");
const coinDatalist = document.getElementById("coinDatalist");

// DOM Elements - MTF Matrix
const mtfGrid = document.getElementById("mtfGrid");
const mtfConsensusBadge = document.getElementById("mtfConsensusBadge");
const mtfScoreVal = document.getElementById("mtfScoreVal");

// DOM Elements - Signal Card
const signalHero = document.getElementById("signalHero");
const signalStatusText = document.getElementById("signalStatusText");
const signalGradeBadge = document.getElementById("signalGradeBadge");
const biasTag = document.getElementById("biasTag");
const confidenceTag = document.getElementById("confidenceTag");
const structureTag = document.getElementById("structureTag");
const volumeTag = document.getElementById("volumeTag");
const entryQualityTag = document.getElementById("entryQualityTag");
const entryStrategyText = document.getElementById("entryStrategyText");
const narrativeText = document.getElementById("narrativeText");
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

// DOM Elements - Sentiment
const fngFill = document.getElementById("fngFill");
const fngPointer = document.getElementById("fngPointer");
const fngValue = document.getElementById("fngValue");
const fngClass = document.getElementById("fngClass");
const fngAdvice = document.getElementById("fngAdvice");
const gsMktCap = document.getElementById("gsMktCap");
const gsBtcDom = document.getElementById("gsBtcDom");
const gsEthDom = document.getElementById("gsEthDom");
const trendingCoins = document.getElementById("trendingCoins");

// DOM Elements - Scanner
const scannerCards = document.getElementById("scannerCards");

// DOM Elements - Calculator Modal
const calcModal = document.getElementById("calcModal");
const calcCloseBtn = document.getElementById("calcCloseBtn");
const calcSyncBtn = document.getElementById("calcSyncBtn");
const calcSyncSymbol = document.getElementById("calcSyncSymbol");
const calcSyncDir = document.getElementById("calcSyncDir");
const calcBalance = document.getElementById("calcBalance");
const calcRiskPct = document.getElementById("calcRiskPct");
const calcDirection = document.getElementById("calcDirection");
const calcEntry = document.getElementById("calcEntry");
const calcSL = document.getElementById("calcSL");
const calcLeverage = document.getElementById("calcLeverage");
const leverageDisplay = document.getElementById("leverageDisplay");

const resPosUsd = document.getElementById("resPosUsd");
const resPosCoins = document.getElementById("resPosCoins");
const resMargin = document.getElementById("resMargin");
const resLossVal = document.getElementById("resLossVal");
const resDistPct = document.getElementById("resDistPct");
const resLiqPrice = document.getElementById("resLiqPrice");
const resTp1Price = document.getElementById("resTp1Price");
const resTp1Pnl = document.getElementById("resTp1Pnl");
const resTp1Rr = document.getElementById("resTp1Rr");
const resTp2Price = document.getElementById("resTp2Price");
const resTp2Pnl = document.getElementById("resTp2Pnl");
const resTp2Rr = document.getElementById("resTp2Rr");
const resTp3Price = document.getElementById("resTp3Price");
const resTp3Pnl = document.getElementById("resTp3Pnl");
const resTp3Rr = document.getElementById("resTp3Rr");
const liqWarningBanner = document.getElementById("liqWarningBanner");

/**
 * ============================================================================
 * FEATURE 3: WEB AUDIO API CHIME & ALERT SYNTHESIZER
 * Pure client-side synthetic bell tones (No external audio file dependencies)
 * ============================================================================
 */
let audioCtx = null;

function getAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx.resume();
  }
  return audioCtx;
}

function playSignalChime(isBullish = true) {
  if (!audioEnabled) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    const now = ctx.currentTime;

    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const gain = ctx.createGain();

    osc1.type = "sine";
    osc2.type = "triangle";

    if (isBullish) {
      // Melodic ascending chime (C5 -> E5 -> G5)
      osc1.frequency.setValueAtTime(523.25, now);
      osc1.frequency.exponentialRampToValueAtTime(783.99, now + 0.15);
      osc2.frequency.setValueAtTime(659.25, now);
      osc2.frequency.exponentialRampToValueAtTime(1046.5, now + 0.2);
    } else {
      // Gentle warning chord (E5 -> C#5 -> A4)
      osc1.frequency.setValueAtTime(659.25, now);
      osc1.frequency.exponentialRampToValueAtTime(440.0, now + 0.18);
      osc2.frequency.setValueAtTime(554.37, now);
      osc2.frequency.exponentialRampToValueAtTime(369.99, now + 0.2);
    }

    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.linearRampToValueAtTime(0.18, now + 0.04);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.45);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(ctx.destination);

    osc1.start(now);
    osc2.start(now);
    osc1.stop(now + 0.45);
    osc2.stop(now + 0.45);
  } catch (e) {
    console.warn("Audio chime playback:", e);
  }
}

/**
 * ============================================================================
 * TRADINGVIEW LIGHTWEIGHT CHARTS INITIALIZATION
 * ============================================================================
 */
function initChart() {
  if (typeof LightweightCharts === "undefined") {
    console.error("LightweightCharts library not loaded");
    return;
  }

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

  // Trend EMA overlay series
  ema20Series = chart.addLineSeries({
    color: "#38bdf8",
    lineWidth: 1,
    title: "EMA 20",
  });
  ema50Series = chart.addLineSeries({
    color: "#f59e0b",
    lineWidth: 1,
    title: "EMA 50",
  });
  ema200Series = chart.addLineSeries({
    color: "#a855f7",
    lineWidth: 2,
    title: "EMA 200",
  });

  // Handle auto-resize on window adjustment
  window.addEventListener("resize", () => {
    if (chart && chartContainer) {
      const rect = chartContainer.getBoundingClientRect();
      chart.applyOptions({
        width: rect.width,
        height: rect.height,
      });
    }
  });
}

/**
 * Draw or update TP/SL and Entry horizontal price lines on chart
 */
function drawTradeLevels(sig) {
  if (!candleSeries || !sig) return;

  activePriceLines.forEach((line) => {
    try {
      candleSeries.removePriceLine(line);
    } catch (e) {}
  });
  activePriceLines = [];

  const showLevels = document.getElementById("toggleLevels") ? document.getElementById("toggleLevels").checked : true;
  if (!showLevels) return;

  const levels = [
    { price: sig.entry, title: "ENTRY", color: "#38bdf8", lineStyle: LightweightCharts.LineStyle.Solid },
    { price: sig.stop_loss, title: `SL (-${sig.risk_pct}%)`, color: "#f43f5e", lineStyle: LightweightCharts.LineStyle.Dashed },
    { price: sig.take_profit_1, title: `TP1 (+${sig.tp1_pct}%)`, color: "#10b981", lineStyle: LightweightCharts.LineStyle.Dotted },
    { price: sig.take_profit_2, title: `TP2 (+${sig.tp2_pct}%)`, color: "#10b981", lineStyle: LightweightCharts.LineStyle.Dashed },
    { price: sig.take_profit_3, title: `TP3 (+${sig.tp3_pct}%)`, color: "#10b981", lineStyle: LightweightCharts.LineStyle.Solid },
  ];

  levels.forEach((lvl) => {
    if (lvl.price && lvl.price > 0) {
      const pLine = candleSeries.createPriceLine({
        price: lvl.price,
        color: lvl.color,
        lineWidth: 1,
        lineStyle: lvl.lineStyle,
        axisLabelVisible: true,
        title: lvl.title,
      });
      activePriceLines.push(pLine);
    }
  });
}

/**
 * ============================================================================
 * FETCH & RENDER CANDLESTICK CHART DATA
 * ============================================================================
 */
async function loadChartData(symbol = currentSymbol, interval = currentInterval) {
  try {
    chartLoading.style.display = "flex";

    const res = await fetch(`/api/analyze?symbol=${encodeURIComponent(symbol)}&interval=${interval}`);
    const data = await res.json();

    if (!data.success) {
      showToast(data.error || "Failed to load market data", "error");
      return;
    }

    // Update Header Pill & Meta
    currentSymbol = data.symbol;
    currentPairText.textContent = data.symbol;
    currentPriceText.textContent = `$${formatPrice(data.latest_price)}`;
    chartTitle.textContent = `${data.symbol} • ${interval.toUpperCase()} Binance Candlesticks`;

    if (pairCategoryBadge && data.category) {
      pairCategoryBadge.textContent = formatCategoryName(data.category);
    }

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

    // Cache active signal data for calculator
    activeSignalData = data.signal;

    // Check for Signal Change to play Audio Chime (Feature 3)
    const newSig = data.signal ? data.signal.signal : "";
    if (lastObservedSignal && newSig && lastObservedSignal !== newSig && (newSig.includes("BUY") || newSig.includes("SELL"))) {
      playSignalChime(newSig.includes("BUY"));
      showToast(`🔔 Signal Changed on ${data.symbol}: ${newSig}!`, "info");
    }
    lastObservedSignal = newSig;

    // Render Strategy Recommendations & Price Lines
    renderSignalDetails(data.signal);
    drawTradeLevels(data.signal);

    // Sync Calculator preview if open
    syncCalculatorFromSignal(data.signal);

    // Load Multi-Timeframe Confluence (Feature 2)
    loadMTFConfluence(currentSymbol);

    // Load Sentiment Data (Professional Feature)
    loadSentimentData();

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

  const signal = sig.signal || "NEUTRAL";
  signalHero.className = "signal-hero " + signal.toLowerCase().replace(" ", "-");
  signalStatusText.textContent = signal;

  // Signal Grade Badge
  const grade = sig.grade || "D";
  if (signalGradeBadge) {
    signalGradeBadge.textContent = grade;
    signalGradeBadge.className = "signal-grade-badge grade-" + grade.replace("+", "plus").toLowerCase();
  }

  biasTag.textContent = `BIAS: ${sig.bias || "NEUTRAL"}`;
  confidenceTag.textContent = `Confidence: ${sig.confidence || 50}%`;

  // Professional Tags (Structure, Volume, Entry Quality)
  if (structureTag) {
    const ms = sig.market_structure || {};
    const trend = ms.trend || "RANGING";
    const trendEmoji = trend === "UPTREND" ? "📈" : trend === "DOWNTREND" ? "📉" : "↔️";
    structureTag.textContent = `${trendEmoji} ${trend}`;
    structureTag.className = "pro-tag structure-tag trend-" + trend.toLowerCase();
  }

  if (volumeTag) {
    const va = sig.volume_analysis || {};
    const acc = va.accumulation || "NEUTRAL";
    const accLabels = { ACCUMULATION: "🟢 Accumulation", DISTRIBUTION: "🔴 Distribution", WEAK_RALLY: "🟡 Weak Rally", WEAK_SELLOFF: "🟡 Weak Selloff", NEUTRAL: "⚪ Neutral" };
    volumeTag.textContent = accLabels[acc] || "⚪ Neutral";
    volumeTag.className = "pro-tag volume-tag vol-" + acc.toLowerCase();
  }

  if (entryQualityTag) {
    const eq = sig.entry_quality || "N/A";
    const eqLabels = { EXCELLENT: "🎯 Excellent", GOOD: "✅ Good", FAIR: "⚠️ Fair", LATE: "🔴 Late", "N/A": "--" };
    entryQualityTag.textContent = eqLabels[eq] || eq;
    entryQualityTag.className = "pro-tag entry-quality-tag eq-" + eq.toLowerCase();
  }

  // Entry Strategy Panel
  if (entryStrategyText) {
    entryStrategyText.textContent = sig.entry_strategy || "Analyzing optimal entry...";
  }

  // AI Trade Narrative
  if (narrativeText) {
    narrativeText.textContent = sig.narrative || "Generating professional analysis...";
  }

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
 * ============================================================================
 * FEATURE 2: MULTI-TIMEFRAME (MTF) CONFLUENCE MATRIX
 * ============================================================================
 */
async function loadMTFConfluence(symbol = currentSymbol) {
  try {
    const res = await fetch(`/api/mtf?symbol=${encodeURIComponent(symbol)}`);
    const data = await res.json();
    if (!data.success) return;

    // Consensus tag & score
    if (mtfConsensusBadge) {
      mtfConsensusBadge.textContent = data.consensus || "Analyzing...";
      mtfConsensusBadge.className = "mtf-consensus-tag";
      if (data.overall_bias.includes("BULLISH")) {
        mtfConsensusBadge.classList.add("bullish");
      } else if (data.overall_bias.includes("BEARISH")) {
        mtfConsensusBadge.classList.add("bearish");
      }
    }

    if (mtfScoreVal) {
      mtfScoreVal.textContent = `${data.confluence_score}%`;
    }

    // Render 5 Timeframe cards
    mtfGrid.innerHTML = "";
    const tfKeys = ["5m", "15m", "1h", "4h", "1d"];

    tfKeys.forEach((tf) => {
      const item = data.timeframes[tf] || { signal: "NEUTRAL", rsi: 50, trend: "MIXED" };
      const card = document.createElement("div");
      card.className = "mtf-card";
      if (tf === currentInterval) {
        card.classList.add("active-chart-tf");
      }

      let sigClass = "neutral";
      if (item.signal.includes("BUY")) sigClass = "buy";
      else if (item.signal.includes("SELL")) sigClass = "sell";

      let trendClass = "mixed";
      if (item.trend === "BULLISH") trendClass = "up";
      else if (item.trend === "BEARISH") trendClass = "down";

      card.innerHTML = `
        <div class="mtf-card-top">
          <span class="mtf-tf-label">${tf.toUpperCase()}</span>
          <span class="mtf-sig-badge ${sigClass}">${item.signal}</span>
        </div>
        <div class="mtf-card-sub">
          <span class="mtf-rsi">RSI: ${item.rsi ? item.rsi.toFixed(0) : "--"}</span>
          <span class="mtf-trend ${trendClass}">${item.trend}</span>
        </div>
      `;

      // 1-Click timeframe switch directly from MTF matrix!
      card.addEventListener("click", () => {
        currentInterval = tf;
        // Sync header timeframe buttons
        document.querySelectorAll(".tf-btn").forEach((b) => {
          b.classList.toggle("active", b.getAttribute("data-tf") === tf);
        });
        loadChartData(currentSymbol, currentInterval);
        loadScanner(currentInterval, currentCategory);
      });

      mtfGrid.appendChild(card);
    });

  } catch (err) {
    console.warn("MTF fetch error:", err);
  }
}

/**
 * ============================================================================
 * FEATURE 1: 50+ COINS UNIVERSE & CATEGORIZED SCANNER
 * ============================================================================
 */
async function loadSymbolsDatalist() {
  try {
    const res = await fetch("/api/symbols");
    const data = await res.json();
    if (!data.success || !data.symbols) return;

    allSymbolsCache = data.symbols;
    coinDatalist.innerHTML = "";

    data.symbols.forEach((item) => {
      const opt = document.createElement("option");
      opt.value = item.symbol;
      opt.label = `${formatCategoryName(item.category)} • $${formatPrice(item.price)}`;
      coinDatalist.appendChild(opt);
    });
  } catch (e) {
    console.warn("Symbols list fetch error:", e);
  }
}

async function loadScanner(interval = currentInterval, category = currentCategory) {
  try {
    scannerCards.innerHTML = `<div class="scanner-loading">Scanning Binance ${category.toUpperCase()} assets (${interval})...</div>`;
    const res = await fetch(`/api/scanner?interval=${interval}&category=${category}&limit=30`);
    const data = await res.json();
    if (!data.success) return;

    renderScannerCards(data.results || []);
  } catch (e) {
    console.warn("Scanner fetch error:", e);
    scannerCards.innerHTML = `<div class="scanner-loading">Error loading scanner. Try refreshing.</div>`;
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
    scannerCards.innerHTML = `<div class="scanner-loading">No assets matching "${currentFilter}" filter in category "${currentCategory}".</div>`;
    return;
  }

  filtered.forEach((item) => {
    const card = document.createElement("div");
    card.className = "scan-card";
    const badgeClass = item.signal.toLowerCase().replace(" ", "-");
    const grade = item.grade || "D";
    const gradeClass = "grade-" + grade.replace("+", "plus").toLowerCase();
    const msTrend = item.market_structure ? item.market_structure.trend || "" : "";
    const trendEmoji = msTrend === "UPTREND" ? "📈" : msTrend === "DOWNTREND" ? "📉" : "↔️";

    card.innerHTML = `
      <div class="scan-card-top">
        <span class="scan-sym">${item.symbol}</span>
        <span class="scan-grade-badge ${gradeClass}">${grade}</span>
        <span class="scan-card-cat">${formatCategoryName(item.category)}</span>
        <span class="scan-badge ${badgeClass}">${item.signal}</span>
      </div>
      <div class="scan-price-row">
        <span class="scan-price">$${formatPrice(item.price)}</span>
        <span style="font-size: 11px; color: #94a3b8;">RSI: ${item.rsi}</span>
        <span class="scan-trend-tag">${trendEmoji} ${msTrend || "--"}</span>
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

function formatCategoryName(cat) {
  if (!cat) return "Majors";
  if (cat === "layer1_2") return "Layer 1/2";
  if (cat === "defi") return "DeFi";
  if (cat === "ai") return "AI";
  if (cat === "memes") return "Meme";
  return cat.charAt(0).toUpperCase() + cat.slice(1);
}

/**
 * ============================================================================
 * FEATURE 1: POSITION SIZE & RISK CALCULATOR (LEVERAGE SIMULATOR)
 * ============================================================================
 */
function openCalculatorModal() {
  calcModal.style.display = "flex";
  syncCalculatorFromSignal(activeSignalData);
  calculatePositionSize();
}

function closeCalculatorModal() {
  calcModal.style.display = "none";
}

function syncCalculatorFromSignal(sig) {
  if (!sig) return;
  calcSyncSymbol.textContent = currentSymbol;
  const isShort = sig.bias === "SHORT";
  calcSyncDir.textContent = isShort ? "SHORT" : "LONG";
  calcSyncDir.style.color = isShort ? "#f43f5e" : "#10b981";
  calcDirection.value = isShort ? "SHORT" : "LONG";

  if (sig.entry) calcEntry.value = sig.entry;
  if (sig.stop_loss) calcSL.value = sig.stop_loss;

  calculatePositionSize();
}

function calculatePositionSize() {
  const balance = parseFloat(calcBalance.value) || 1000;
  const riskPct = parseFloat(calcRiskPct.value) || 2;
  const entry = parseFloat(calcEntry.value) || 0;
  const sl = parseFloat(calcSL.value) || 0;
  const leverage = parseInt(calcLeverage.value) || 10;
  const direction = calcDirection.value;

  leverageDisplay.textContent = `${leverage}x`;

  if (entry <= 0 || sl <= 0 || balance <= 0) return;

  const riskDollar = balance * (riskPct / 100);
  const distancePct = Math.abs(entry - sl) / entry;

  if (distancePct <= 0.0001) {
    resPosUsd.textContent = "$0.00";
    return;
  }

  // Position Size in USD based on risk dollar & SL distance
  const positionUsd = riskDollar / distancePct;
  const positionCoins = positionUsd / entry;
  const initialMargin = positionUsd / leverage;

  resPosUsd.textContent = `$${formatPrice(positionUsd)}`;
  resPosCoins.textContent = `${formatPrice(positionCoins)} ${currentSymbol.replace("USDT", "")}`;
  resMargin.textContent = `$${formatPrice(initialMargin)}`;
  resLossVal.textContent = `-$${formatPrice(riskDollar)} (-${riskPct}%)`;
  resDistPct.textContent = `${(distancePct * 100).toFixed(2)}%`;

  // Estimated Liquidation Price with 0.5% maintenance margin
  let liqPrice = 0;
  const mm = 0.005; // 0.5% maintenance margin
  if (direction === "LONG") {
    liqPrice = entry * (1 - (1 / leverage) + mm);
  } else {
    liqPrice = entry * (1 + (1 / leverage) - mm);
  }
  resLiqPrice.textContent = `$${formatPrice(Math.max(0, liqPrice))}`;

  // Liquidation Safety Check
  // If longing and Liq > SL, or if shorting and Liq < SL, liquidation occurs BEFORE SL!
  let dangerousLeverage = false;
  if (direction === "LONG" && liqPrice >= sl) dangerousLeverage = true;
  if (direction === "SHORT" && liqPrice <= sl) dangerousLeverage = true;

  if (dangerousLeverage) {
    liqWarningBanner.style.display = "block";
    resLiqPrice.style.color = "#f43f5e";
  } else {
    liqWarningBanner.style.display = "none";
    resLiqPrice.style.color = "#38bdf8";
  }

  // Projected Profits on TP1, TP2, TP3
  if (activeSignalData) {
    const tp1 = activeSignalData.take_profit_1 || 0;
    const tp2 = activeSignalData.take_profit_2 || 0;
    const tp3 = activeSignalData.take_profit_3 || 0;

    resTp1Price.textContent = `$${formatPrice(tp1)}`;
    resTp2Price.textContent = `$${formatPrice(tp2)}`;
    resTp3Price.textContent = `$${formatPrice(tp3)}`;

    const pnl1 = Math.abs((tp1 - entry) / entry) * positionUsd;
    const pnl2 = Math.abs((tp2 - entry) / entry) * positionUsd;
    const pnl3 = Math.abs((tp3 - entry) / entry) * positionUsd;

    resTp1Pnl.textContent = `+$${formatPrice(pnl1)}`;
    resTp2Pnl.textContent = `+$${formatPrice(pnl2)}`;
    resTp3Pnl.textContent = `+$${formatPrice(pnl3)}`;

    resTp1Rr.textContent = `R:R ${(pnl1 / riskDollar).toFixed(1)}`;
    resTp2Rr.textContent = `R:R ${(pnl2 / riskDollar).toFixed(1)}`;
    resTp3Rr.textContent = `R:R ${(pnl3 / riskDollar).toFixed(1)}`;
  }
}

/**
 * ============================================================================
 * UTILITIES & TOAST
 * ============================================================================
 */
function formatPrice(val) {
  if (val === undefined || val === null || isNaN(val)) return "0.00";
  const num = parseFloat(val);
  if (num === 0) return "0.00";
  if (num >= 1000) return num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (num >= 1) return num.toFixed(4);
  if (num >= 0.01) return num.toFixed(6);
  if (num >= 0.0001) return num.toFixed(8);
  return num.toExponential(4);
}

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
 * ============================================================================
 * EVENT LISTENERS & APPLICATION BOOTSTRAP
 * ============================================================================
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
      loadScanner(currentInterval, currentCategory);
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
    loadScanner(currentInterval, currentCategory);
    showToast("Data refreshed from Binance", "info");
  });

  // Audio Toggle (Feature 3)
  if (audioToggleBtn) {
    audioToggleBtn.addEventListener("click", () => {
      audioEnabled = !audioEnabled;
      if (audioEnabled) {
        audioToggleBtn.className = "btn-icon active-audio";
        audioIcon.textContent = "🔊";
        audioText.textContent = "Sound ON";
        playSignalChime(true);
        showToast("🔊 Audio Signal Alerts Enabled", "info");
      } else {
        audioToggleBtn.className = "btn-icon muted-audio";
        audioIcon.textContent = "🔇";
        audioText.textContent = "Muted";
        showToast("🔇 Audio Alerts Muted", "info");
      }
    });
  }

  // Calculator Modal Triggers (Feature 1)
  if (calcModalBtn) calcModalBtn.addEventListener("click", openCalculatorModal);
  if (signalCalcBtn) signalCalcBtn.addEventListener("click", openCalculatorModal);
  if (calcCloseBtn) calcCloseBtn.addEventListener("click", closeCalculatorModal);
  if (calcSyncBtn) calcSyncBtn.addEventListener("click", () => syncCalculatorFromSignal(activeSignalData));

  // Close modal when clicking on overlay background
  if (calcModal) {
    calcModal.addEventListener("click", (e) => {
      if (e.target === calcModal) closeCalculatorModal();
    });
  }

  // Calculator Inputs real-time listener
  [calcBalance, calcRiskPct, calcDirection, calcEntry, calcSL].forEach((input) => {
    if (input) {
      input.addEventListener("input", calculatePositionSize);
      input.addEventListener("change", calculatePositionSize);
    }
  });

  // Leverage Slider & Presets
  if (calcLeverage) {
    calcLeverage.addEventListener("input", () => {
      document.querySelectorAll(".lev-preset-btn").forEach((b) => {
        b.classList.toggle("active", b.getAttribute("data-lev") === calcLeverage.value);
      });
      calculatePositionSize();
    });
  }

  document.querySelectorAll(".lev-preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".lev-preset-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const lev = btn.getAttribute("data-lev");
      calcLeverage.value = lev;
      calculatePositionSize();
    });
  });

  // Telegram Alert Trigger
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

  // Indicator Toggles
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

  // Scanner Buy/Sell/All Filter Buttons
  const filterBtns = document.querySelectorAll(".filter-btn");
  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      filterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.getAttribute("data-filter");
      loadScanner(currentInterval, currentCategory);
    });
  });

  // Category Filter Pills (Feature 1: 50+ Coins Categories)
  const catPills = document.querySelectorAll(".cat-pill");
  catPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      catPills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      currentCategory = pill.getAttribute("data-cat");
      loadScanner(currentInterval, currentCategory);
    });
  });

  // Auto-refresh interval (every 20s)
  autoRefreshTimer = setInterval(() => {
    loadChartData(currentSymbol, currentInterval);
  }, 20000);
}

// Startup Initialization
document.addEventListener("DOMContentLoaded", () => {
  initChart();
  setupEventListeners();
  loadSymbolsDatalist();
  loadChartData(currentSymbol, currentInterval);
  loadScanner(currentInterval, currentCategory);
  loadSentimentData();
});

/**
 * ============================================================================
 * MARKET SENTIMENT DATA (Fear & Greed + Trending + Global)
 * ============================================================================
 */
async function loadSentimentData() {
  try {
    const res = await fetch("/api/sentiment");
    const data = await res.json();
    if (!data.success) return;

    // Fear & Greed Gauge
    const fg = data.fear_greed || {};
    const val = fg.value || 50;

    if (fngFill) fngFill.style.width = `${val}%`;
    if (fngPointer) fngPointer.style.left = `${val}%`;
    if (fngValue) fngValue.textContent = val;
    if (fngClass) {
      fngClass.textContent = fg.classification || "Neutral";
      fngClass.className = "fng-class fng-zone-" + (fg.zone || "NEUTRAL").toLowerCase();
    }
    if (fngAdvice) fngAdvice.textContent = fg.advice || "";

    // Color the gauge fill based on value
    if (fngFill) {
      if (val <= 25) fngFill.style.background = "linear-gradient(90deg, #ef4444, #f97316)";
      else if (val <= 45) fngFill.style.background = "linear-gradient(90deg, #f97316, #eab308)";
      else if (val <= 55) fngFill.style.background = "linear-gradient(90deg, #eab308, #a3a3a3)";
      else if (val <= 75) fngFill.style.background = "linear-gradient(90deg, #84cc16, #22c55e)";
      else fngFill.style.background = "linear-gradient(90deg, #22c55e, #10b981)";
    }

    // Global Market Stats
    const gm = data.global_market || {};
    if (gsMktCap) {
      const change = gm.total_market_cap_change_24h || 0;
      gsMktCap.textContent = `${change >= 0 ? "+" : ""}${change}%`;
      gsMktCap.style.color = change >= 0 ? "#10b981" : "#f43f5e";
    }
    if (gsBtcDom) gsBtcDom.textContent = `${gm.btc_dominance || 0}%`;
    if (gsEthDom) gsEthDom.textContent = `${gm.eth_dominance || 0}%`;

    // Trending Coins
    const trending = data.trending_coins || [];
    if (trendingCoins) {
      if (trending.length === 0) {
        trendingCoins.innerHTML = `<span class="trending-placeholder">No trending data available</span>`;
      } else {
        trendingCoins.innerHTML = trending.map((c) =>
          `<span class="trending-coin-pill">
            <span class="tc-rank">#${c.market_cap_rank || "?"}</span>
            <span class="tc-name">${c.symbol}</span>
          </span>`
        ).join("");
      }
    }
  } catch (e) {
    console.warn("Sentiment fetch error:", e);
  }
}
