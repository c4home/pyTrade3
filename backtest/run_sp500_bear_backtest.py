import pickle
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core_backtest_engine import run_backtest_with_params

if __name__ == "__main__":
    cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sp500_data_bear.pkl")
    if not os.path.exists(cache_path):
        print(f"Cache file not found at {cache_path}. Please run download_sp500_bear.py first.")
        sys.exit(1)

    print("Loading cached S&P 500 bear market data...")
    with open(cache_path, 'rb') as f:
        cached_data = pickle.load(f)
    print(f"Loaded {len(cached_data)} stocks.")

    grids = [
        {'atr_mul': 1.5, 'stop_mul': 2.3, 'max_stop': -12.0, 'rsi_exit': 80, 'prot_act': 5.0, 'prot_drop': 0.5, 'dip_th': 7, 'mom_th': 8},
    ]

    default_config = {'limit': 18, 'profit_target': 5.0, 'max_amount': 1000.0}

    for p in grids:
        trades = []
        stock_stats = {}
        for s, df in cached_data.items():
            df_2022 = df.loc['2022-01-01':'2022-12-31']
            if len(df_2022) < 20:
                continue
            
            stock_trades_2022 = run_backtest_with_params(s, default_config, df_2022, p)
            
            trades.extend(stock_trades_2022)
            stock_pnl = sum(t['pnl_eur'] for t in stock_trades_2022)
            stock_wr = len([t for t in stock_trades_2022 if t['pnl_pct'] > 0]) / len(stock_trades_2022) if stock_trades_2022 else 0
            stock_stats[s] = {'pnl': stock_pnl, 'wr': stock_wr, 'trades': len(stock_trades_2022)}
            
        pnl = sum(t['pnl_eur'] for t in trades)
        wr = len([t for t in trades if t['pnl_pct'] > 0]) / len(trades) if trades else 0
        print(f"Total 2022 PnL: {pnl:+8.0f} | WR: {wr*100:4.1f}% | Trades: {len(trades):3d} | {p}")
        
        sorted_stats = sorted(stock_stats.items(), key=lambda item: item[1]['pnl'], reverse=True)
        print("\n--- TOP 20 STOCKS (2022) ---")
        for s, stat in sorted_stats[:20]:
            print(f"{s:8s}: PnL: {stat['pnl']:+7.0f} | WR: {stat['wr']*100:5.1f}% | Trades: {stat['trades']:2d}")
            
        print("\n--- BOTTOM 20 STOCKS (2022) ---")
        for s, stat in sorted_stats[-20:]:
            print(f"{s:8s}: PnL: {stat['pnl']:+7.0f} | WR: {stat['wr']*100:5.1f}% | Trades: {stat['trades']:2d}")
