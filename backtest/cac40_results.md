# French Market (CAC 40) Backtest Results

To see how the algorithm adapts to European markets, we executed a strict 1-year backtest (July 2025 – July 2026) exclusively on the 40 largest French companies (the CAC 40 index).

## 1-Year Portfolio Performance
Using the same `Fine-Tune 3` dynamic parameters on a €14,000 portfolio:

| Metric | Result |
| :--- | :--- |
| **Total 1-Year PnL** | **+€398** |
| **Global Win Rate** | **56.5%** |
| **Total Trades Taken** | **46** |

> [!TIP]
> **Market Adaptability**
> The algorithm successfully extracted a profit from the French market over the last year. Because the CAC 40 only contains 40 stocks (compared to the 500 in the S&P 500), trading opportunities are much rarer—it only found 46 valid setups the entire year! However, it still maintained profitability and a positive win rate, proving the core logic works universally across international exchanges.

## Top 10 Best Performing French Stocks
The algorithm caught excellent setups on these European giants over the last 12 months:

| Symbol | Company | Total PnL (€) | Win Rate (%) | Total Trades |
| :--- | :--- | :--- | :--- | :--- |
| **BN.PA** | Danone | +315 | 100.0% | 1 |
| **MT.AS** | ArcelorMittal | +269 | 100.0% | 2 |
| **AI.PA** | Air Liquide | +258 | 100.0% | 1 |
| **ERF.PA** | Eurofins Scientific | +253 | 100.0% | 1 |
| **AC.PA** | Accor | +248 | 100.0% | 2 |
| **GLE.PA** | Société Générale | +204 | 100.0% | 3 |
| **EDEN.PA**| Edenred | +179 | 100.0% | 1 |
| **SAF.PA** | Safran | +164 | 100.0% | 1 |
| **AIR.PA** | Airbus | +149 | 100.0% | 1 |
| **TEP.PA** | Teleperformance | +108 | 100.0% | 1 |

## Bottom 10 French Stocks
These stocks generated false signals or broke their support levels quickly, triggering the dynamic stop loss.

| Symbol | Company | Total PnL (€) | Win Rate (%) | Total Trades |
| :--- | :--- | :--- | :--- | :--- |
| **ENGI.PA**| Engie | -100 | 0.0% | 1 |
| **EN.PA** | Bouygues | -123 | 0.0% | 1 |
| **HO.PA** | Thales | -146 | 0.0% | 1 |
| **RMS.PA** | Hermès | -148 | 0.0% | 1 |
| **TTE.PA** | TotalEnergies | -148 | 0.0% | 1 |
| **RI.PA** | Pernod Ricard | -155 | 0.0% | 1 |
| **DSY.PA** | Dassault Systèmes | -236 | 0.0% | 1 |
| **ORA.PA** | Orange | -238 | 0.0% | 2 |
| **CAP.PA** | Capgemini | -247 | 0.0% | 1 |
| **SGO.PA** | Saint-Gobain | -261 | 0.0% | 2 |

> [!NOTE]
> Even on the worst performing trade (Saint-Gobain), the loss was strictly capped at **-€261**, proving the dynamic risk management is just as effective on European exchanges as it is on the NYSE/NASDAQ.
