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

## 📊 2. Strategy Regimes & Stock Scoring (`calculate_score()`)

Every stock is dynamically evaluated in real-time. The bot calculates a multi-factor `smart_score` (0 to 10+) and assigns one of two strategy regimes:

### 🟢 Strategy A: DIP Buyer (Pullback Strategy)
* **Target:** Quality stocks experiencing a short-term pullback within an overall uptrend.
* **Scoring Criteria:** `smart_score >= 7`
* **Technical Triggers:**
  * Price touching/near Lower Bollinger Band (`BB_PctB <= 0.20`).
  * Oversold RSI (`RSI <= 45`).
  * Bullish trend context (`MA20 > MA50` or `Close > MA200`).

### 🚀 Strategy B: MOMENTUM Breakout (Trend Strategy)
* **Target:** High-volatility trend continuations breaking above resistance.
* **Scoring Criteria:** `smart_score >= 8`
* **Technical Triggers:**
  * 14-day High breakout (`Close >= 14-Day High`).
  * MACD bullish alignment (`MACD > Signal`).
  * High relative volume (`Volume >= 1.5 * 20-Day Volume MA`).
  * Trend strength confirmed (`ADX >= 25`).
  * RSI in active trend zone (`45 <= RSI < 70`).

---

## 🛑 3. Hard Buy Safeguards & Entry Filters (NON-NEGOTIABLE)

Before executing any **BUY** order, the bot checks and enforces these strict safety guards:

1. **Market Open Cooldown:** No automated buys during the first **15 minutes** after market open (avoids open-trap volatility).
2. **24-Hour Trade Cooldown:** Min **24 hours** between consecutive buy/sell trades on the same stock.
3. **Earnings Blackout:** Skip buys **3 days before** and **2 days after** scheduled earnings announcements.
4. **Daily Rise Cap:** Block buys if the stock rose **> +5.0%** today (prevents buying at the top of a vertical pump).
5. **3-Day Cumulative Rise Cap:** Block buys if the stock rose **> +15.0%** over the last 3 days.
6. **RSI Overbought Filter:** Block buys if **`RSI >= 70`**.
7. **Single-Day Drop Limit (Falling Knife Guard):**
   * Block DIP buys if daily drop is worse than **`-7.0%`** (prevents buying earnings crashes or panic dumps).
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
   └─ Sell if pnl_percent <= highest_pnl - dynamic_trail_drop (1% - 3% drop based on ATR)

2. Proportional Protective Trailing   (highest_pnl >= 5.0%)
   └─ Sell if pnl_percent <= highest_pnl * 0.5 (locks in 50% of peak gains)

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
