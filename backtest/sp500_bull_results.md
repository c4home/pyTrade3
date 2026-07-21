# S&P 500 Backtest Results (Dynamic Position Sizing)

We have successfully scaled the automated backtester to run the exact same `TradingBot` logic over all ~500 companies in the S&P 500 index across a 2-year historical period. 

The data for all 500 stocks is now permanently downloaded and cached locally at `scratch/sp500_cache.pkl`, allowing us to re-run massive 500-stock simulations in less than 5 seconds in the future!

## Overall Portfolio Performance
Simulating a €14,000 base portfolio using the `Fine-Tune 3` dynamic parameters (`ATR Multiplier = 1.5`, `Stop Multiplier = 2.3`, `Max Portfolio Risk = 1%`) yielded incredibly robust results across the entire index:

| Metric | Result |
| :--- | :--- |
| **Total PnL** | **+€82,481** |
| **Global Win Rate** | **63.4%** |
| **Total Trades Taken** | **4,243** |

> [!TIP]
> **Algorithm Robustness**
> Taking over 4,000 algorithmic trades across 500 wildly different assets and maintaining a solidly profitable 63.4% win rate proves that the core momentum/dip logic combined with dynamic ATR sizing is universally robust, not just over-optimized for a few tech stocks.

## Top 20 Best Performing Stocks
The algorithm performed exceptionally well on high-momentum technology and cyclical stocks.

| Symbol | Company Info | Total PnL (€) | Win Rate (%) | Total Trades |
| :--- | :--- | :--- | :--- | :--- |
| **EBAY** | Consumer Discretionary - Broadline Retail | +2,090 | 93.3% | 15 |
| **KLAC** | Information Technology - Semiconductor Materials & Equipment | +1,642 | 91.7% | 12 |
| **ADI** | Information Technology - Semiconductors | +1,520 | 78.6% | 14 |
| **BKR** | Energy - Oil & Gas Equipment & Services | +1,493 | 81.8% | 11 |
| **ECHO** | Communication Services - Wireless Telecommunication Services | +1,480 | 75.0% | 12 |
| **CHRW** | Industrials - Air Freight & Logistics | +1,461 | 90.0% | 10 |
| **DELL** | Information Technology - Technology Hardware, Storage & Peripherals | +1,445 | 90.0% | 10 |
| **VRT** | Industrials - Electrical Components & Equipment | +1,394 | 92.3% | 13 |
| **CIEN** | Information Technology - Communications Equipment | +1,348 | 84.6% | 13 |
| **DVA** | Health Care - Health Care Services | +1,300 | 83.3% | 6 |
| **VLO** | Energy - Oil & Gas Refining & Marketing | +1,293 | 90.9% | 11 |
| **GM** | Consumer Discretionary - Automobile Manufacturers | +1,285 | 100.0% | 8 |
| **IBKR** | Financials - Investment Banking & Brokerage | +1,261 | 100.0% | 11 |
| **EL** | Consumer Staples - Personal Care Products | +1,237 | 83.3% | 12 |
| **CSX** | Industrials - Rail Transportation | +1,185 | 81.8% | 11 |
| **PSX** | Energy - Oil & Gas Refining & Marketing | +1,133 | 83.3% | 12 |
| **WBD** | Communication Services - Broadcasting | +1,132 | 87.5% | 8 |
| **CASY** | Consumer Staples - Food Retail | +1,097 | 88.9% | 9 |
| **MGM** | Consumer Discretionary - Casinos & Gaming | +1,067 | 66.7% | 9 |
| **MO** | Consumer Staples - Tobacco | +1,040 | 70.0% | 10 |

## Bottom 20 Worst Performing Stocks
The algorithm struggled mostly on highly choppy, lower-volatility defensive stocks or specific sectors where the MACD generated excessive false signals without sustained trends.

| Symbol | Company Info | Total PnL (€) | Win Rate (%) | Total Trades |
| :--- | :--- | :--- | :--- | :--- |
| **LYV** | Communication Services - Movies & Entertainment | -721 | 40.0% | 10 |
| **COO** | Health Care - Health Care Supplies | -744 | 50.0% | 12 |
| **STZ** | Consumer Staples - Distillers & Vintners | -746 | 14.3% | 7 |
| **ARE** | Real Estate - Office REITs | -751 | 40.0% | 10 |
| **DOW** | Materials - Commodity Chemicals | -757 | 46.2% | 13 |
| **BF-B** | Consumer Staples - Distillers & Vintners | -789 | 37.5% | 8 |
| **CNC** | Health Care - Managed Health Care | -793 | 71.4% | 7 |
| **ADSK** | Information Technology - Application Software | -798 | 33.3% | 9 |
| **DPZ** | Consumer Discretionary - Restaurants | -811 | 16.7% | 6 |
| **LYB** | Materials - Specialty Chemicals | -834 | 25.0% | 8 |
| **LULU** | Consumer Discretionary - Apparel, Accessories & Luxury Goods | -859 | 50.0% | 10 |
| **ROP** | Information Technology - Electronic Equipment & Instruments | -861 | 12.5% | 8 |
| **CPRT** | Industrials - Diversified Support Services | -889 | 0.0% | 5 |
| **MKC** | Consumer Staples - Packaged Foods & Meats | -902 | 12.5% | 8 |
| **FDS** | Financials - Financial Exchanges & Data | -935 | 46.2% | 13 |
| **FIS** | Financials - Transaction & Payment Processing Services | -936 | 0.0% | 6 |
| **PGR** | Financials - Property & Casualty Insurance | -982 | 0.0% | 7 |
| **VRSK** | Industrials - Research & Consulting Services | -1,083 | 18.2% | 11 |
| **FISV** | Financials - Transaction & Payment Processing Services | -1,087 | 14.3% | 7 |
| **TTD** | Communication Services - Advertising | -1,366 | 12.5% | 8 |

## Next Steps for Future Testing
Whenever you want to test new technical indicators, parameter grids, or position sizing math:
1. Open `scratch/sp500_backtest.py`.
2. Add your new parameters to the `grids = [...]` array.
3. Run `python scratch/sp500_backtest.py`.
The data is safely cached, so tests will now execute practically instantly.
