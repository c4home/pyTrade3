import pickle
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core_backtest_engine import run_backtest_with_params

if __name__ == "__main__":
    cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sp500_data_bull.pkl")
    if not os.path.exists(cache_path):
        print(f"Cache file not found at {cache_path}. Please run download_sp500_bull.py first.")
        sys.exit(1)

    print("Loading cached S&P 500 data...")
    with open(cache_path, 'rb') as f:
        cached_data = pickle.load(f)
    print(f"Loaded {len(cached_data)} stocks.")

    grids = [
        # Fine-tune 3: The best current configuration
        {'atr_mul': 1.5, 'stop_mul': 2.3, 'max_stop': -12.0, 'rsi_exit': 80, 'prot_act': 5.0, 'prot_drop': 0.5, 'dip_th': 7, 'mom_th': 8},
    ]

    # Default stock config for SP500 constituents
    # Using 18% as the hard portfolio limit for individual stocks
    default_config = {'limit': 18, 'profit_target': 5.0, 'max_amount': 1000.0}

    for p in grids:
        trades = []
        stock_stats = {}
        for s, df in cached_data.items():
            stock_trades = run_backtest_with_params(s, default_config, df, p)
            trades.extend(stock_trades)
            stock_pnl = sum(t['pnl_eur'] for t in stock_trades)
            stock_wr = len([t for t in stock_trades if t['pnl_pct'] > 0]) / len(stock_trades) if stock_trades else 0
            stock_stats[s] = {'pnl': stock_pnl, 'wr': stock_wr, 'trades': len(stock_trades)}
            
        pnl = sum(t['pnl_eur'] for t in trades)
        wr = len([t for t in trades if t['pnl_pct'] > 0]) / len(trades) if trades else 0
        print(f"Total PnL: {pnl:+8.0f} | WR: {wr*100:4.1f}% | Trades: {len(trades):3d} | {p}")
        
        # Output top and bottom 20 stocks
        sorted_stats = sorted(stock_stats.items(), key=lambda item: item[1]['pnl'], reverse=True)
        print("\n--- FULL LIST OF STOCKS ---")
        with open('sp500_bull_results.md', 'r') as f:
            content = f.read()
        
        # Cut off at Top 20
        idx = content.find("## Top 20")
        if idx != -1:
            content = content[:idx]
            
        with open('sp500_bull_results.md', 'w') as f:
            f.write(content)
            f.write("## Full Per-Stock Breakdown (Ranked Best to Worst)\n")
            f.write("Here is the exact performance breakdown of all stocks tested, ranked from highest profit to lowest profit:\n\n")
            f.write("| Symbol | Total PnL (€) | Win Rate (%) | Total Trades |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for s, stat in sorted_stats:
                f.write(f"| **{s}** | {stat['pnl']:+7.0f} | {stat['wr']*100:5.1f}% | {stat['trades']} |\n")

        print("\n--- BUY AND HOLD SP500 ETF (ESE.PA) COMPARISON ---")
        import yfinance as yf
        import pandas as pd
        # We need to know the start and end dates from the first stock in cached_data
        first_stock = list(cached_data.values())[0]
        start_date = first_stock.index[0]
        end_date = first_stock.index[-1]
        
        df_sp500 = yf.Ticker("ESE.PA").history(start=start_date, end=end_date, auto_adjust=False, actions=False)
        if isinstance(df_sp500.columns, pd.MultiIndex):
            df_sp500.columns = df_sp500.columns.droplevel(1)
        
        if len(df_sp500) >= 2:
            start_price = df_sp500['Close'].iloc[0]
            end_price = df_sp500['Close'].iloc[-1]
            shares_bought = 20000 / start_price
            end_value = shares_bought * end_price
            buy_hold_pnl = end_value - 20000
            buy_hold_pct = (end_price - start_price) / start_price * 100
            
            print(f"Start Price ({start_date.date()}): {start_price:.2f}")
            print(f"End Price ({end_date.date()})  : {end_price:.2f}")
            print(f"Total Return (%)        : {buy_hold_pct:+.2f}%")
            print(f"Buy & Hold PnL (20k)    : {buy_hold_pnl:+8.0f} EUR")
            
            diff = pnl - buy_hold_pnl
            print(f"\nDifference (Bot vs B&H): {diff:+8.0f} EUR")
            if diff > 0:
                print("Bot OUTPERFORMED Buy & Hold S&P 500!")
            else:
                print("Bot UNDERPERFORMED Buy & Hold S&P 500.")
