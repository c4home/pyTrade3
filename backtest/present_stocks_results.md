# Backtest Results: 56 Stocks vs S&P 500 (Buy and Hold)

## Overview
This backtest evaluates the performance of the trading bot over a 2-year historical period across the **expanded list of 56 active assets** stored in the database (SPCX had no trades/data). The objective was to test the algorithm with a **20,000 EUR global account size** and compare its active trading performance against a simple "Buy and Hold" strategy of the S&P 500 ETF (ESE.PA) with the same initial capital.

## Key Findings

> [!TIP]
> **Massive Outperformance**
> The bot dramatically outperformed the S&P 500 benchmark. Over the 2-year period, a 20,000 EUR buy-and-hold in the S&P 500 yielded +28.89% (+€5,779), whereas the bot generated a massive **+€32,915 in pure PnL**, beating the market by over **+€27,000** while maintaining a highly consistent **71.5% win rate** across 530 trades.

## Test Results Summary

| Strategy | Total PnL (€) | Return (%) | Win Rate | Trades |
| :--- | :--- | :--- | :--- | :--- |
| **Buy & Hold S&P 500 (ESE.PA)** | +€5,779 | +28.89% | N/A | 1 |
| **Trading Bot (56 Stocks)** | **+€32,915** | **+164.57%** | **71.5%** | **530** |

**Difference (Bot vs B&H): +€27,136 EUR**

---

## Full Per-Stock Breakdown (Ranked Best to Worst)

Here is the exact performance breakdown of all stocks tested, ranked from highest profit to lowest profit:

| Symbol | Total PnL (€) | Win Rate (%) | Total Trades |
| :--- | :--- | :--- | :--- |
| **EBAY**  | +3,014 | 93.3%  | 15 |
| **VRT**   | +2,069 | 92.3%  | 13 |
| **DELL**  | +2,034 | 90.0%  | 10 |
| **DVA**   | +1,880 | 83.3%  | 6  |
| **IBKR**  | +1,823 | 100.0% | 11 |
| **MRK**   | +1,503 | 88.9%  | 9  |
| **NVDA**  | +1,446 | 100.0% | 12 |
| **TXN**   | +1,432 | 77.8%  | 9  |
| **AMD**   | +1,382 | 80.0%  | 10 |
| **INTC**  | +1,378 | 81.8%  | 11 |
| **CSCO**  | +1,265 | 77.8%  | 9  |
| **BAC**   | +1,137 | 83.3%  | 12 |
| **ESE.PA**| +1,135 | 87.5%  | 8  |
| **JPM**   | +1,111 | 88.9%  | 9  |
| **AVGO**  | +1,097 | 100.0% | 9  |
| **MU**    | +1,007 | 77.8%  | 9  |
| **GOOG**  | +961   | 60.0%  | 10 |
| **ORCL**  | +927   | 70.0%  | 10 |
| **ASML**  | +906   | 72.7%  | 11 |
| **AAPL**  | +882   | 64.3%  | 14 |
| **BARC.L**| +859   | 88.9%  | 9  |
| **WFC**   | +735   | 80.0%  | 10 |
| **CVX**   | +728   | 85.7%  | 7  |
| **TSM**   | +700   | 87.5%  | 8  |
| **MRNA**  | +588   | 75.0%  | 8  |
| **SAF.PA**| +499   | 66.7%  | 12 |
| **KO**    | +496   | 75.0%  | 12 |
| **WMT**   | +489   | 75.0%  | 12 |
| **XOM**   | +441   | 71.4%  | 14 |
| **TMO**   | +335   | 66.7%  | 9  |
| **ARM**   | +325   | 58.3%  | 12 |
| **JNJ**   | +306   | 62.5%  | 8  |
| **PFE**   | +267   | 83.3%  | 6  |
| **META**  | +237   | 46.2%  | 13 |
| **UNH**   | +227   | 83.3%  | 6  |
| **AIR.PA**| +197   | 66.7%  | 12 |
| **ABBV**  | +148   | 60.0%  | 10 |
| **AMZN**  | +136   | 75.0%  | 8  |
| **IBM**   | +129   | 66.7%  | 6  |
| **GE**    | +58    | 60.0%  | 10 |
| **SPCX**  | +0     | 0.0%   | 0  |
| **EGLN.L**| -1     | 70.0%  | 10 |
| **QCOM**  | -16    | 63.6%  | 11 |
| **COP**   | -28    | 50.0%  | 6  |
| **MCD**   | -35    | 62.5%  | 8  |
| **HO.PA** | -54    | 60.0%  | 10 |
| **LLY**   | -120   | 60.0%  | 10 |
| **AMGN**  | -140   | 66.7%  | 9  |
| **ABT**   | -221   | 55.6%  | 9  |
| **MSFT**  | -260   | 42.9%  | 7  |
| **V**     | -338   | 60.0%  | 10 |
| **ISRG**  | -352   | 37.5%  | 8  |
| **COST**  | -375   | 42.9%  | 7  |
| **NFLX**  | -386   | 40.0%  | 10 |
| **MA**    | -472   | 44.4%  | 9  |
| **TSLA**  | -573   | 42.9%  | 7  |
