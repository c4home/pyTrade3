# Backtest Results: Dynamic Position Sizing vs Static Allocation

## Overview
This backtest evaluates the performance of the algorithm over a 2-year historical period across all 24 assets in the portfolio. The objective was to compare the newly implemented **Dynamic Position Sizing** (based on 1% total portfolio risk and ATR stop-loss distance) against the previous hardcoded static `MaxEUR` allocations.

## Key Findings

> [!TIP]
> **Performance Surge**
> Implementing dynamic sizing resulted in a **+36% increase** in overall profitability (PnL) without sacrificing the win rate. By allocating more capital to lower-risk setups and less capital to highly volatile setups, the portfolio achieves better capital efficiency.

## Test Results Summary

| Configuration | Static PnL | Dynamic PnL | Win Rate | Trades |
| :--- | :--- | :--- | :--- | :--- |
| **Baseline** | +€7,120 | +€8,965 | 73.4% | 233 |
| **Fine-Tune 3 (Current)** | +€7,503 | **+€10,234** | **72.6%** | 237 |
| **Test 5** | +€7,499 | **+€10,588** | 71.2% | 240 |
| **Fine-Tune 4** | +€6,733 | +€9,547 | 70.8% | 243 |


## Per-Stock Breakdown (Fine-Tune 3 Dynamic Sizing)

Here is the exact performance breakdown of all 24 stocks over the 2-year backtest using the optimized Dynamic Position Sizing algorithm:

| Symbol | Total PnL (€) | Win Rate (%) | Total Trades |
| :--- | :--- | :--- | :--- |
| **NVDA**   | +1,009 | 100.0% | 12 |
| **INTC**   | +964   | 81.8%  | 11 |
| **AMD**    | +936   | 80.0%  | 10 |
| **ESE.PA** | +792   | 87.5%  | 8  |
| **ASML**   | +761   | 72.7%  | 11 |
| **JPM**    | +754   | 88.9%  | 9  |
| **AVGO**   | +749   | 100.0% | 9  |
| **MU**     | +693   | 77.8%  | 9  |
| **GOOG**   | +658   | 60.0%  | 10 |
| **ORCL**   | +627   | 70.0%  | 10 |
| **AAPL**   | +607   | 64.3%  | 14 |
| **BARC.L** | +596   | 88.9%  | 9  |
| **TSM**    | +457   | 87.5%  | 8  |
| **MRNA**   | +401   | 75.0%  | 8  |
| **ARM**    | +391   | 61.5%  | 13 |
| **SAF.PA** | +364   | 66.7%  | 12 |
| **AIR.PA** | +154   | 66.7%  | 12 |
| **AMZN**   | +96    | 75.0%  | 8  |
| **EGLN.L** | +3     | 70.0%  | 10 |
| **QCOM**   | -17    | 63.6%  | 11 |
| **HO.PA**  | -24    | 60.0%  | 10 |
| **ABT**    | -159   | 55.6%  | 9  |
| **MSFT**   | -193   | 42.9%  | 7  |
| **TSLA**   | -385   | 42.9%  | 7  |

## Why Did Performance Improve?
1. **Capital Optimization**: Instead of capping a stock like Apple at exactly €1,000, if Apple's volatility (ATR) drops and its stop-loss tightens to 2.5%, the dynamic math safely allocates €2,520 to the trade (respecting the 18% portfolio rule). This maximizes gains on safe, low-volatility setups.
2. **Risk Mitigation**: For highly volatile stocks (e.g., a stock with an 8% stop loss), the dynamic math automatically shrinks the position size down to ~€1,750, ensuring that a stop-out never exceeds exactly 1% (€140) of your total portfolio. 
3. **ETF Scaling**: The new logic successfully permitted larger allocations (up to 35% of the portfolio) for safer instruments like the S&P 500 ETF, capturing more absolute return on highly probable index trends.
