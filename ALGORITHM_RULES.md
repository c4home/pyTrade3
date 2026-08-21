# 📐 ALGORITHM_RULES.md — Core Trading Bot Architecture & Rules

This document specifies the exact trading rules, entry/exit algorithms, indicator formulas, and safety boundaries enforced in `pyTrade3`.

> [!CAUTION]
> **MANDATORY MAINTENANCE REQUIREMENT**:
> Whenever ANY rule, formula, threshold, or indicator calculation in `trading_bot.py` or `core_backtest_engine.py` is updated, **THIS DOCUMENT AND `AGENTS.md` MUST BE UPDATED IMMEDIATELY**.

---

## 📌 1. Mission & Objective
The goal of `pyTrade3` is to automate swing-trading across US and European stocks with Interactive Brokers. It aims to generate market-outperforming risk-adjusted returns by:
1. Entering quality stocks during temporary pullbacks (**DIP Buyer**).
2. Capturing high-momentum breakouts (**MOMENTUM Breakout**).
3. Locking in profit dynamically while preventing severe drawdowns using ATR-scaled trailing stops and protective gain floors.

---

## 🧮 2. Technical Indicators Used
* **ATR (14):** 14-period Average True Range for dynamic volatility scaling.
* **RSI (14):** 14-period Relative Strength Index for oversold (`<= 30` / `<= 45`) and overbought (`>= 70` / `>= 80`) signals.
* **Bollinger Bands (20, 2):** `BB_Mid` (20 SMA), `BB_Upper`, `BB_Lower`, and `BB_PctB`.
* **Moving Averages:** 20-day, 50-day, and 200-day Simple Moving Averages (`MA20`, `MA50`, `MA200`).
* **MACD (12, 26, 9):** MACD Line, Signal Line, Histogram, and state tracking (`BULL`, `S_BULL`, `BEAR`, `S_BEAR`).
* **ADX (14):** Trend strength indicator.

---

## 📊 3. Detailed Smart Score Calculation (`calculate_score()`)

The bot calculates a dynamic multi-factor score between **0 and 12 points** for every stock in real time:

```text
smart_score = min(12, max(0, base_score + analyst_modifier + target_bonus + etf_boost))
```

---

### Step 1: Trend Baseline Context (0 to +3 Points)
Evaluates long-term structural health of the stock:
* **`Market Value > MA200`**: **+3 Points** (Bullish long-term trend context)
* **`Market Value > Previous Close`**: **+1 Point** (Short-term price recovery)
* Otherwise: **0 Points**

---

### Step 2: Base Strategy Scoring (Max 10 Points)
The bot calculates two sub-scores (**Candidate A: DIP** and **Candidate B: MOMENTUM**) and selects the strategy with the higher score:

```text
base_score = max(DIP_Points, MOMENTUM_Points)
```

#### 🟢 Candidate A: DIP Buyer Score Breakdown (Max 10 Points)
1. **RSI Oversold Level (Max 4 Points):**
   * `RSI < 25`: **+4 Points** (Extreme oversold)
   * `RSI < 30`: **+3 Points** (Deep oversold)
   * `RSI < 40`: **+2 Points** (Moderate oversold)
2. **Bollinger Band Position `BB_PctB` (Max 3 Points):**
   * `BB_PctB < 0.0` (Price below Lower Band): **+3 Points**
   * `BB_PctB < 0.1`: **+2 Points**
   * `BB_PctB < 0.2`: **+1 Point**
3. **Trend Baseline Context:** **+0 to +3 Points** (From Step 1 above)

#### 🚀 Candidate B: MOMENTUM Breakout Score Breakdown (Max 10 Points)
1. **MACD Alignment (Max 3 Points):**
   * `MACD == S_BULL` (Strong bullish trend alignment): **+3 Points**
   * `MACD == BULL` (Bullish trend alignment): **+2 Points**
2. **ADX Trend Strength (Max 2 Points — Only awarded if `Price > MA50`):**
   * `ADX > 35`: **+2 Points** (Strong trend)
   * `ADX > 25`: **+1 Point** (Developing trend)
3. **Volume Surge Support (Max 2 Points):**
   * `Projected Volume > 1.5 * MA(Volume, 14)`: **+2 Points**
   * `Projected Volume > MA(Volume, 14)`: **+1 Point**
4. **RSI Sweet Spot (Max 3 Points):**
   * `50 <= RSI <= 70`: **+3 Points** (Active momentum zone without overbought risk)
   * `40 <= RSI <= 50`: **+1 Point** (Weak momentum)

---

### Step 3: Institutional Analyst Modifiers (-5 to +5 Points)

#### A. Valuation vs UBS / Analyst Price Target (`target_bonus`)
Compares current market price against cached bank notes / UBS price targets:
* **`Market Value <= 80% of Target`** (>=20% Undervalued): **+3 Points**
* **`Market Value <= 90% of Target`** (>=10% Undervalued): **+2 Points**
* **`Market Value < Target`**: **+1 Point**
* **`Market Value > Target`**: **-1 Point**
* **`Market Value >= 110% of Target`** (>=10% Overvalued): **-2 Points**
* **`Market Value >= 120% of Target`** (>=20% Overvalued): **-3 Points**

#### B. Rating Conviction (`analyst_modifier`)
* High-conviction Buy / Outperform notes: **+1 to +2 Points**
* Rating downgrades / Sell notes: **-1 to -2 Points**

---

### Step 4: Asset Class Adjustment (`etf_boost`)
* **ETF / ETC Asset Class:** **+6 Points baseline**
  * Applied to index funds (`ESE.PA`, `EGLN.L`, `SPCX`) to compensate for their lower volatility and lack of single-stock analyst price targets.

---

## 📥 4. Entry Logic & Buy Conditions

### A. Global Pre-Buy Safeguards (All Strategies)
* **Market Open Cooldown:** No automated buys in the first 30 minutes after market open.
* **Trade Cooldown:** 24-hour minimum gap between consecutive buy/sell trades per stock.
* **Earnings Guard:** No buys 3 days before or 2 days after earnings announcements.
* **Overbought Cap:** No buys if `RSI >= 70`.
* **Daily Surge Cap:** No buys if today's change `> +5.0%`.
* **3-Day Surge Cap:** No buys if 3-day change `> +15.0%`.
* **Falling Knife Limit:** No DIP buys if today's drop is worse than `-7.0%`.
* **Cash & PDT Guards:** Available cash check and Pattern Day Trader limit protection.

### B. Strategy Regimes
```text
1. DIP Buyer Strategy (smart_score >= 7)
   - Triggers when a strong stock experiences a controlled dip.
   - Requirements:
     * Daily drop between -3.0% and -7.0%.
     * If drop is moderate (-3% to -7%), RSI must be <= 45.
     * Bullish trend alignment (MA20 > MA50 or Close > MA200).

2. MOMENTUM Breakout Strategy (smart_score >= 8)
   - Triggers on technical breakouts.
   - Requirements:
     * Close >= 14-Day High.
     * MACD in bullish state (BULL or S_BULL).
     * Volume >= 1.5 * MA(Volume, 20).
     * ADX >= 25.
     * 45 <= RSI < 70.
```

---

## 📤 5. Exit Logic & Sell Conditions (Execution Hierarchy)

Sell triggers bypass buy cooldowns and execute in this order of precedence:

1. **Dynamic ATR Trailing Profit Lock:**
   * Activates when `highest_pnl >= dynamic_profit_target * 100`.
   * Sells if `pnl_percent <= highest_pnl - dynamic_trail_drop` (1% to 3% ATR trailing distance).

2. **Proportional Protective Trailing Stop:**
   * Activates when `highest_pnl >= 5.0%`.
   * Sells if `pnl_percent <= highest_pnl * 0.5` (locks in 50% of peak gains).

3. **Dynamic ATR Stop Loss:**
   * Sells if `pnl_percent <= dynamic_stop_loss`.
   * Dynamic stop cap: `-7.0%` for DIP strategy, `-9.0%` for MOMENTUM strategy.

4. **RSI Overbought Exit:**
   * Sells if `RSI >= 80` AND `pnl_percent > +1.0%`.

5. **MACD Bearish Crossover Exit:**
   * Sells on fresh transition from `BULL`/`S_BULL` to `BEAR`/`S_BEAR` AND `pnl_percent > +1.5%`.

6. **Analyst Target Override:**
   * Sells if market price is `10%+` above cached UBS target AND `pnl_percent > +0.5%`.

---

## 🔄 6. Synchronization & Change Protocol
When updating the trading algorithm:
1. Modify [trading_bot.py](file:///Users/canhhung/Documents/pyTrade3/trading_bot.py).
2. Update [core_backtest_engine.py](file:///Users/canhhung/Documents/pyTrade3/backtest/core_backtest_engine.py) to keep backtests identical.
3. Update [AGENTS.md](file:///Users/canhhung/Documents/pyTrade3/AGENTS.md) and [ALGORITHM_RULES.md](file:///Users/canhhung/Documents/pyTrade3/ALGORITHM_RULES.md).
