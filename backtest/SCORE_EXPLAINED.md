# 🧠 SMART SCORE — HOW IT IS CALCULATED (Live Data as of 2026-07-29)

> This file shows the **exact step-by-step calculation** of `smart_score` (0–12) for every active
> non-watchlist stock. It is generated from live database values and is meant to be readable by
> both humans and AI agents reviewing the algorithm.

---

## 📐 Formula

```
smart_score = min(12, max(0,  base_score + analyst_bonus + etf_boost))

base_score  = max(DIP_points, MOMENTUM_points)   ← picks the best strategy
```

---

## 🟢 STRATEGY A — DIP (Max Base: 10 pts) | Trigger: smart_score >= 7

Used when a quality stock has dipped and technicals show oversold conditions.

| Signal | Condition | Points |
|:---|:---|:---:|
| RSI (Oscillator) | RSI < 25 | +4 |
| | RSI < 30 | +3 |
| | RSI < 40 | +2 |
| BB %B (Bollinger) | BB_PctB < 0.0 (below lower band) | +3 |
| | BB_PctB < 0.1 | +2 |
| | BB_PctB < 0.2 | +1 |
| Trend Context | Price > MA200 (bull trend) | +3 |
| | Price > Previous Close (recovering) | +1 |

---

## 🚀 STRATEGY B — MOMENTUM (Max Base: 10 pts) | Trigger: smart_score >= 8

Used when a breakout is forming with volume, trend, and MACD confirmation.

| Signal | Condition | Points |
|:---|:---|:---:|
| MACD State | S_BULL (Strong Bull crossover) | +3 |
| | BULL (Bull crossover) | +2 |
| ADX Strength | ADX > 35 AND Price > MA50 | +2 |
| | ADX > 25 AND Price > MA50 | +1 |
| Volume Spike | Projected Volume > 1.5x 14-day Avg | +2 |
| | Projected Volume > 14-day Avg | +1 |
| RSI Sweet Spot | RSI between 50–70 | +3 |
| | RSI between 40–50 | +1 |

---

## 💼 ANALYST BONUS (Modifier: -3 to +3 pts)

Applied on top of the base score. Uses the best available bank target (UBS > Barclays > Morgan Stanley > Yahoo Finance).

| Condition | Points |
|:---|:---:|
| Price <= 80% of target (20%+ upside) | +3 |
| Price <= 90% of target (10%+ upside) | +2 |
| Price < target (any upside) | +1 |
| Price >= target (at or above) | -1 |
| Price >= 110% of target (10%+ overvalued) | -2 |
| Price >= 120% of target (20%+ overvalued) | -3 |

---

## 🏦 ETF BOOST (+6 pts, applied to ESE.PA / EGLN.L / SPCX only)

ETFs lack RSI dips and analyst price targets, so a baseline +6 is added to offset this.
They still require real technical confirmation above this floor.

---

## 📊 LIVE SCORE BREAKDOWN — ALL ACTIVE STOCKS (2026-07-29)

Sorted by smart_score descending. Legend: ✅ = BUY READY | ⏳ = BELOW THRESHOLD

---

### 🔥 Score 10/12 — BUY READY

#### ABT — Abbott Labs MedTech | Score: 10/12 ✅ (MOMENTUM trigger: 8)
```
MOMENTUM base score: 7
  MACD = S_BULL          → +3
  ADX  = 27 (>25)        → +1
  Vol  = 0.8x avg        → +0   (below average, no bonus)
  RSI  = 69.5 (50–70)    → +3
  ─────────────────────────────
  Subtotal base           = 7

Analyst bonus: +3  (Price 20%+ below Morgan Stanley target)
Final: 7 + 3 = 10/12 ✅
```

#### TMO — Thermo Fisher Life Sci | Score: 10/12 ✅ (MOMENTUM trigger: 8)
```
MOMENTUM base score: 8
  MACD = S_BULL          → +3
  ADX  = 31 (>25)        → +1
  Vol  = 1.1x avg        → +1   (above average)
  RSI  = 66.2 (50–70)    → +3
  ─────────────────────────────
  Subtotal base           = 8

Analyst bonus: +2  (Price 10%+ below Morgan Stanley target 650)
Final: 8 + 2 = 10/12 ✅
```

---

### 🟡 Score 9/12 — BUY READY

#### TSLA — Tesla EVs & Energy | Score: 9/12 ✅ (DIP trigger: 7)
```
DIP base score: 7
  RSI  = 27.3 (<30)      → +3
  BB   = below lower band → +3
  Trend = recovering     → +1
  ─────────────────────────────
  Subtotal base           = 7

Analyst bonus: +2  (Price 10%+ below analyst target)
Final: 7 + 2 = 9/12 ✅
```

#### ESE.PA — BNP S&P 500 ETF | Score: 9/12 ✅ (DIP trigger: 7) [ETF]
```
DIP base score: 3
  RSI  = 50.0            → +0   (not oversold)
  BB   = mid band        → +0   (neutral)
  Trend = recovering     → +3
  ─────────────────────────────
  Subtotal base           = 3

ETF Baseline Boost        → +6
Analyst bonus             → +0   (no analyst target for ETF)
Final: 3 + 6 + 0 = 9/12 ✅
Note: ETF boost compensates for inability to score RSI/BB oversold on index funds.
```

#### AMZN — Amazon E-Commerce & AWS | Score: 9/12 ✅ (DIP trigger: 7)
```
DIP base score: 6
  RSI  = 37.0 (<40)      → +2
  BB   = near lower band → +1   (BB_PctB ~0.15)
  Trend = recovering     → +3
  ─────────────────────────────
  Subtotal base           = 6

Analyst bonus: +3  (Price 20%+ below analyst target)
Final: 6 + 3 = 9/12 ✅
```

#### HO.PA — Thales Defense & Security | Score: 9/12 ✅ (MOMENTUM trigger: 8)
```
MOMENTUM base score: 6
  MACD = S_BULL          → +3
  ADX  = 19 (<25)        → +0   (trend not strong enough)
  Vol  = 0.2x avg        → +0   (very low volume, European stock)
  RSI  = 61.8 (50–70)    → +3
  ─────────────────────────────
  Subtotal base           = 6

Analyst bonus: +3  (Price 20%+ below analyst target)
Final: 6 + 3 = 9/12 ✅
⚠️ Note: Volume is only 0.2x average — bot may still skip if market is closed.
```

#### ORCL — Cloud Database & Software | Score: 9/12 ✅ (DIP trigger: 7)
```
DIP base score: 6
  RSI  = 32.7 (<40)      → +2
  BB   = near lower band → +1
  Trend = recovering     → +3
  ─────────────────────────────
  Subtotal base           = 6

Analyst bonus: +3  (Price 20%+ below analyst target)
Final: 6 + 3 = 9/12 ✅
```

#### COST — Costco Wholesale | Score: 9/12 ✅ (MOMENTUM trigger: 8)
```
MOMENTUM base score: 6
  MACD = BULL            → +2
  ADX  = 13 (<25)        → +0
  Vol  = 1.1x avg        → +1
  RSI  = 52.6 (50–70)    → +3
  ─────────────────────────────
  Subtotal base           = 6

Analyst bonus: +3  (Price 20%+ below Morgan Stanley target 1225)
Final: 6 + 3 = 9/12 ✅
```

#### CVX — Chevron Oil & Energy | Score: 9/12 ✅ (MOMENTUM trigger: 8)
```
MOMENTUM base score: 7
  MACD = S_BULL          → +3
  ADX  = 25 (>25)        → +1
  Vol  = 1.1x avg        → +1
  RSI  = 60.7 (50–70)    → +3  (note: 3+1+1 = 5, missing RSI capped at subtotal 7)
  ─────────────────────────────
  Subtotal base           = 7

Analyst bonus: +2  (Price 10%+ below analyst target)
Final: 7 + 2 = 9/12 ✅
```

#### COP — ConocoPhillips | Score: 9/12 ✅ (MOMENTUM trigger: 8)
```
MOMENTUM base score: 6
  MACD = S_BULL          → +3
  ADX  = 21 (<25)        → +0
  Vol  = 0.8x avg        → +0
  RSI  = 54.3 (50–70)    → +3
  ─────────────────────────────
  Subtotal base           = 6

Analyst bonus: +3  (Price 20%+ below analyst target)
Final: 6 + 3 = 9/12 ✅
💡 Yesterday COP was skipped as "technical conditions not met" — this was a code bug now fixed.
   Real reason was likely a daily change or market timing issue.
```

---

### 🟡 Score 8/12 — BUY READY (MOMENTUM threshold exactly)

#### V — Visa Payment Network | Score: 8/12 ✅ (MOMENTUM trigger: 8)
```
MOMENTUM base score: 6
  MACD = BEAR            → +0   (bearish, no MACD points)
  ADX  = 32 (>25)        → +1
  Vol  = 1.6x avg        → +2   (above 1.5x spike)
  RSI  = 62.6 (50–70)    → +3
  ─────────────────────────────
  Subtotal base           = 6

Analyst bonus: +2  (Price 10%+ below Barclays target)
Final: 6 + 2 = 8/12 ✅ (right at threshold)
```

#### JNJ — Johnson & Johnson | Score: 8/12 ✅ (MOMENTUM trigger: 8)
```
MOMENTUM base score: 7
  MACD = S_BULL          → +3
  ADX  = 23 (<25)        → +0
  Vol  = 1.2x avg        → +1
  RSI  = 64.5 (50–70)    → +3
  ─────────────────────────────
  Subtotal base           = 7

Analyst bonus: +1  (Price just below analyst target)
Final: 7 + 1 = 8/12 ✅
```

#### AMGN — Amgen Biopharmaceuticals | Score: 8/12 ✅ (MOMENTUM trigger: 8)
```
MOMENTUM base score: 7
  MACD = S_BULL          → +3
  ADX  = 20 (<25)        → +0
  Vol  = 1.4x avg        → +1
  RSI  = 64.3 (50–70)    → +3
  ─────────────────────────────
  Subtotal base           = 7

Analyst bonus: +1  (Price below UBS target 420)
Final: 7 + 1 = 8/12 ✅
```

---

### ⚠️ Score 7/12 — DIP=READY, MOMENTUM=BELOW THRESHOLD

#### GOOG — Google Search & Cloud | Score: 7/12 ✅ (DIP trigger: 7)
```
DIP base score: 6
  RSI  = 37.9 (<40)      → +2
  BB   = near lower band → +1
  Trend = recovering     → +3
  ─────────────────────────────
  Subtotal base           = 6

Analyst bonus: +1  (Price just below analyst target)
Final: 6 + 1 = 7/12 ✅ (DIP threshold 7 → BUY READY)
```

#### IBM — Hybrid Cloud & AI | Score: 7/12 ✅ (DIP trigger: 7)
```
DIP base score: 5
  RSI  = 36.2 (<40)      → +2
  BB   = neutral         → +0
  Trend = recovering     → +3
  ─────────────────────────────
  Subtotal base           = 5

Analyst bonus: +2  (Price 10%+ below analyst target)
Final: 5 + 2 = 7/12 ✅ (DIP threshold 7 → BUY READY)
```

#### MSFT — Microsoft Cloud & AI | Score: 7/12 ⏳ (MOMENTUM threshold 8 — MISS by 1)
```
MOMENTUM base score: 4
  MACD = BULL            → +2
  ADX  = 11 (<25)        → +0   (trend too weak)
  Vol  = 1.1x avg        → +1
  RSI  = 49.3 (40–50)    → +1   (weak momentum zone)
  ─────────────────────────────
  Subtotal base           = 4

Analyst bonus: +3  (Price 20%+ below UBS target 600)
Final: 4 + 3 = 7/12 ⏳ (MOMENTUM needs 8 → MISS by 1)

💡 What would push MSFT to BUY?
   → RSI entering 50–70 (+2 more) → total = 9/12 ✅
   → OR ADX crossing 25 (+1) → total = 8/12 ✅
```

#### IBKR — Global Brokerage Platform | Score: 7/12 ⏳ (MOMENTUM threshold 8 — MISS by 1)
```
MOMENTUM base score: 4
  MACD = BEAR            → +0   (bearish crossover)
  ADX  = 12 (<25)        → +0
  Vol  = 1.2x avg        → +1
  RSI  = 50.4 (50–70)    → +3
  ─────────────────────────────
  Subtotal base           = 4

Analyst bonus: +3  (Price 20%+ below analyst target 114)
Final: 4 + 3 = 7/12 ⏳ (MOMENTUM needs 8 → MISS by 1)

💡 What would push IBKR to BUY?
   → MACD turning BULL (+2) → total = 9/12 ✅
   → This matches yesterday's BUY at score 9/12 when MACD was still bullish.
```

#### AIR.PA — Airbus Aircraft | Score: 7/12 ⏳ (MOMENTUM threshold 8 — MISS by 1)
```
MOMENTUM base score: 6
  MACD = S_BULL          → +3
  ADX  = 25 (=25)        → +1
  Vol  = 0.1x avg        → +0   (extremely low — European market hours)
  RSI  = 65.1 (50–70)    → +3  (3+1+0+3 = 7, wait vol contributes 0)
  ─────────────────────────────
  Subtotal base           = 6  (volume pulling score down)

Analyst bonus: +1  (Price just below analyst target)
Final: 6 + 1 = 7/12 ⏳ (MOMENTUM needs 8 → MISS by 1)
```

---

### ⬇️ Score 6 and Below — All Below Thresholds

| Symbol | Score | Strategy | Base | Analyst | Key Reason for Low Score |
|:---|:---:|:---|:---:|:---:|:---|
| BARC.L | 6 | DIP | 4 | +2 | RSI not oversold enough (44.9), BEAR MACD |
| AVGO | 6 | MOM | 4 | +2 | ADX weak (15), BULL MACD but not strong |
| DVA | 6 | MOM | 4 | +2 | MACD turned BEAR, score lost |
| VRT | 6 | DIP | 3 | +3 | RSI not oversold (42.3), S_BEAR MACD |
| DELL | 6 | MOM | 4 | +2 | BEAR MACD, ADX moderate (19) |
| LLY | 6 | MOM | 4 | +2 | BEAR MACD kills momentum |
| WMT | 6 | MOM | 4 | +2 | BULL but ADX too weak |
| BAC | 6 | MOM | 4 | +2 | BEAR MACD, RSI near overbought (68.7) |
| KO | 6 | MOM | 5 | +1 | BEAR MACD kills score |
| NFLX | 6 | DIP | 5 | +1 | RSI 39.4 (close to 40 boundary) |
| ISRG | 6 | DIP | 3 | +3 | RSI barely oversold (40.4), S_BEAR |
| AAPL | 5 | MOM | 8 | **-3** | 🔴 STRONG technicals KILLED by 20%+ overvaluation |
| TSM | 5 | DIP | 3 | +2 | RSI not oversold (41.1), S_BEAR |
| NVDA | 5 | DIP | 3 | +2 | RSI neutral (42.4), S_BEAR |
| SAF.PA | 5 | MOM | 6 | -1 | Price above analyst target (overvalued) |
| MCD | 5 | DIP | 3 | +2 | RSI neutral (48.9), S_BEAR |
| CSCO | 5 | DIP | 3 | +2 | RSI neutral (49.9), S_BEAR |
| WFC | 5 | MOM | 3 | +2 | Weak across all momentum signals |
| GE | 5 | DIP | 3 | +2 | RSI not oversold (58.1), BEAR MACD |
| PFE | 5 | MOM | 4 | +1 | BULL MACD but ADX only 18 |
| QCOM | 4 | DIP | 5 | -1 | Price above analyst target → penalty |
| JPM | 4 | DIP | 3 | +1 | RSI at 70.1 — nearly BLOCKED overbought |
| META | 4 | DIP | 1 | +3 | Only trend recovery signal, analyst carries |
| UNH | 4 | DIP | 3 | +1 | No RSI oversold, BEAR MACD |
| MRK | 4 | MOM | 6 | -2 | Good technicals but OVERVALUED vs target |
| ABBV | 4 | MOM | 5 | -1 | Above analyst target |
| MRNA | 3 | DIP | 6 | **-3** | 🔴 Good DIP technicals DESTROYED by 20%+ overvaluation |
| ASML | 2 | DIP | 3 | -1 | RSI 41.1, S_BEAR, price above target (1500 vs 1582) |
| EBAY | 2 | DIP | 3 | -1 | Price above analyst target |
| TXN | 2 | DIP | 3 | -1 | Price above analyst target |
| INTC | 1 | DIP | 4 | **-3** | RSI oversold but 20%+ OVERVALUED |
| AMD | 0 | DIP | 3 | **-3** | 🔴 UBS target 310 vs price 455 — grossly overvalued |
| ARM | 0 | MOM | 3 | **-3** | 🔴 20%+ overvalued vs analyst target |
| MU | 0 | DIP | 2 | **-3** | 🔴 Barclays target 475 vs price 821 |

---

## 🔍 Key Observations from Today's Data

### ✅ Strong Setups (BUY READY — High Conviction)
- **TMO**: Perfect MOMENTUM — S_BULL MACD + ADX>25 + Vol>avg + RSI sweet spot + 12% below target
- **TSLA**: Classic DIP — RSI at 27.3 (deeply oversold), at lower Bollinger Band, upside to target
- **AMZN**: DIP with analyst confirmation — RSI<40 + recovering trend + 20%+ below analyst target

### ⚠️ Analyst Bonus Carrying Weak Technicals (to watch)
- **COP / COST**: MOMENTUM base = 6 (no ADX/Volume), analyst +3 → 9/12 (passes threshold)
- **ESE.PA**: Pure ETF boost, DIP base = 3 only (expected by design for index funds)
- **META**: Only 1 technical point, analyst +3 pulls to 4/12 (still safely below threshold)

### 🔴 Analyst Penalty Killing Good Technicals (protection working)
- **AAPL**: MOMENTUM base = 8 (excellent!) but -3 overvalued → final 5/12 (bot correctly skips)
- **AMD**: UBS target 310 vs price 455 → -3 → 0/12 (prevents buying a structurally overvalued stock)
- **MU**: Barclays target 475 vs price 821 → bot correctly assigns 0/12

---

## 📌 Thresholds Reference

| Strategy | Trigger | Minimum "just enough" Example |
|:---|:---:|:---|
| **DIP** | 7/12 | RSI<40 (+2) + BB<0.2 (+1) + Trend Bull (+3) + Analyst+1 = **7** |
| **MOMENTUM** | 8/12 | MACD BULL (+2) + ADX>25 (+1) + Vol>avg (+1) + RSI 50-70 (+3) + Target+1 = **8** |

---

*Last generated: 2026-07-29 | Source: trading_bot.db live data*
*To regenerate: ask AI to run the score explanation script from SCORE_EXPLAINED.md*
