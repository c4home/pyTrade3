# 🤖 AGENTS.md — Mandatory AI & Developer Rules for `pyTrade3`

> [!IMPORTANT]
> **CRITICAL RULE FOR ALL AI ASSISTANTS & DEVELOPERS**:
> Before making ANY changes or refactoring in `trading_bot.py`, `core_backtest_engine.py`, `database.py`, `gui.py`, or `main.py`, you **MUST** read this document completely and respect all rules and thresholds defined below.
> Do NOT loosen risk boundaries, bypass PDT checks, or modify buy/sell triggers without running full backtests and obtaining explicit user confirmation.

---

## 🎯 1. Goal of the Bot
`pyTrade3` is an automated quantitative swing-trading bot for US & European equities using Interactive Brokers (IBKR TWS/Gateway) and a local SQLite state database.

* **Primary Objective:** Capital preservation and consistent profit extraction through structured **DIP Buying** and **MOMENTUM Breakout** strategies.
* **Core Philosophy:** High-probability setups, dynamic ATR-based profit locking, protective gain trailing, and strict risk control (stopping out quickly on bad setups while letting winners ride up to technical targets).

---

## 📊 2. Detailed Smart Score Calculation (`calculate_score()`)

The bot calculates a multi-factor `smart_score` (0 to 12 points) in real-time to select the active strategy regime and rank execution priority:

```text
smart_score = min(12, max(0, base_score + analyst_modifier + target_bonus + etf_boost))
```

### Step 1: Trend Baseline Context (0 to +3 Points)
* **`Market Value > MA200`**: **+3 Points** (Healthy long-term bull trend)
* **`Market Value > Previous Close`**: **+1 Point** (Short-term recovery)

### Step 2: Strategy Sub-Scoring (`base_score = max(DIP_Points, MOMENTUM_Points)`)

#### 🟢 Strategy A: DIP Buyer Base Score (Max 10 Points)
* **RSI Oversold Level (Max 4 Pts):** `RSI < 25` (+4) | `RSI < 30` (+3) | `RSI < 40` (+2)
* **Bollinger Band `BB_PctB` (Max 3 Pts):** `BB < 0.0` (+3) | `BB < 0.1` (+2) | `BB < 0.2` (+1)
* **Trend Baseline Context:** **+0 to +3 Points** (From Step 1 above)
* **Trigger Threshold:** `smart_score >= 7` **AND** `base_score >= 5` (Two-gate: analyst bonus alone cannot carry a weak setup)

#### 🚀 Strategy B: MOMENTUM Breakout Base Score (Max 10 Points)
* **MACD Trend Alignment (Max 3 Pts):** `S_BULL` (+3) | `BULL` (+2)
* **ADX Trend Strength (Max 2 Pts, if `Price > MA50`):** `ADX > 35` (+2) | `ADX > 25` (+1)
* **Volume Spike (Max 2 Pts):** `Projected Vol > 1.5 * MA(14)` (+2) | `Projected Vol > MA(14)` (+1)
* **RSI Sweet Spot (Max 3 Pts):** `50 <= RSI <= 70` (+3) | `40 <= RSI <= 50` (+1)
* **Trigger Threshold:** `smart_score >= 8` **AND** `base_score >= 6` (Two-gate: MACD + at least 2 other signals must align)

### Step 3: Valuation & Analyst Modifiers (-5 to +5 Points)
* **`Price <= 80% of Analyst Target`** (>=20% Undervalued): **+3 Points**
* **`Price <= 90% of Analyst Target`** (>=10% Undervalued): **+2 Points**
* **`Price < Analyst Target`**: **+1 Point**
* **`Price > Analyst Target`**: **-1 Point**
* **`Price >= 110% of Analyst Target`** (>=10% Overvalued): **-2 Points**
* **`Price >= 120% of Analyst Target`** (>=20% Overvalued): **-3 Points**
* **Analyst Rating Notes:** **-2 to +2 Points** (Upgrade notes vs Downgrade cuts)

### Step 4: Asset Class Adjustment
* **ETF / ETC Boost:** **+6 Points baseline** (For `ESE.PA`, `EGLN.L`, `SPCX` to offset lack of single-stock analyst targets).

---

## 🛑 3. Hard Buy Safeguards & Entry Filters (NON-NEGOTIABLE)

Before executing any **BUY** order, the bot checks and enforces these strict safety guards:

1. **Market Open Cooldown:** No automated buys during the first **30 minutes** after market open.
2. **24-Hour Trade Cooldown:** Min **24 hours** between consecutive buy/sell trades on the same stock.
3. **Earnings Blackout:** Skip buys **3 days before** and **2 days after** scheduled earnings announcements.
4. **Daily Rise Cap:** Block buys if the stock rose **> +5.0%** today.
5. **3-Day Cumulative Rise Cap:** Block buys if the stock rose **> +15.0%** over the last 3 days.
6. **RSI Overbought Filter:** Block buys if **`RSI >= 70`**.
7. **Single-Day Drop Limit (Falling Knife Guard):**
   * Block DIP buys if daily drop is worse than **`-7.0%`** (prevents buying earnings crashes).
   * Block moderate DIP buys if drop is between **`-3.0%` and `-7.0%`** while **`RSI > 45`**.
8. **Macro Market Guard:** Block DIP buys if S&P 500 ETF (ESE.PA) market drop limit is breached.
9. **Portfolio Score Priority:** Capital is allocated to the highest `smart_score` stock across the portfolio first.
10. **Usable Cash Guard:** Checks `ibapi.available_cash - min_cash >= max_amount` before placing orders.
11. **PDT (Pattern Day Trader) Protection:** Block buys if a day-trade could trigger a 90-day IBKR account lock.

---

## 🚪 4. Sell / Exit Triggers (Execution Order & Priority)

Sell evaluation is prioritized over buys and bypasses buy cooldowns. A sell order is triggered if ANY of the following rules are met:

```text
1. Dynamic ATR Trailing Profit Lock   (highest_pnl >= dynamic_profit_target)
   └─ Sell if pnl_percent <= highest_pnl - dynamic_trail_drop (0.5% - 1.5% drop based on 0.5x ATR)

2. Proportional Protective Trailing   (highest_pnl >= 5.0%)
   └─ Sell if pnl_percent <= highest_pnl * 0.75 floor (locks in 75% of peak gains, max 25% drop)

3. Dynamic ATR Stop Loss              (pnl_percent <= dynamic_stop_loss)
   └─ DIP Stop Cap: -7.0% | MOMENTUM Stop Cap: -9.0%

4. RSI Overbought Exit                (RSI >= 80 and pnl_percent > +1.0%)

5. MACD Bearish Reversal Exit         (MACD crosses BEAR/S_BEAR and pnl_percent > +1.5%)

6. Analyst Target Override            (Market price 10%+ above UBS target and pnl_percent > +0.5%)
```

---

## 🛠️ 5. Rules for AI Agents & Developers

1. **Read Before Modifying:** Always review `AGENTS.md` and `ALGORITHM_RULES.md` before making any code changes.
2. **Keep Backtester & Live Engine Synced:** Any change to trading logic in `trading_bot.py` **MUST** be mirrored in `core_backtest_engine.py` to keep live results aligned with backtest benchmarks.
3. **Database Schema Integrity:** Preserve SQLite database schema (`stocks` table, `highest_pnl`, `max_amount`, `profit_target`).
4. **Update This File:** Whenever the algorithm, indicators, thresholds, or execution rules change, **UPDATE THIS FILE IMMEDIATELY**.
