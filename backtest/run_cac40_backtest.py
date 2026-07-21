import pickle
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core_backtest_engine import run_backtest_with_params

if __name__ == "__main__":
    cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cac40_data.pkl")
    if not os.path.exists(cache_path):
        print(f"Cache file not found at {cache_path}. Please run download_cac40.py first.")
        sys.exit(1)

    print("Loading cached CAC 40 data...")
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
            # Slice to only include the last 1 year (July 2025 - July 2026)
            df_1yr = df.loc['2025-07-21':]
            if len(df_1yr) < 20:
                continue
            
            stock_trades = run_backtest_with_params(s, default_config, df_1yr, p)
            trades.extend(stock_trades)
            
            stock_pnl = sum(t['pnl_eur'] for t in stock_trades)
            stock_wr = len([t for t in stock_trades if t['pnl_pct'] > 0]) / len(stock_trades) if stock_trades else 0
            stock_stats[s] = {'pnl': stock_pnl, 'wr': stock_wr, 'trades': len(stock_trades)}
            
        pnl = sum(t['pnl_eur'] for t in trades)
        wr = len([t for t in trades if t['pnl_pct'] > 0]) / len(trades) if trades else 0
        print(f"Total Last Year PnL: {pnl:+8.0f} | WR: {wr*100:4.1f}% | Trades: {len(trades):3d} | {p}")
        
        sorted_stats = sorted(stock_stats.items(), key=lambda item: item[1]['pnl'], reverse=True)
        print("\n--- TOP STOCKS ---")
        for s, stat in sorted_stats[:10]:
            print(f"{s:8s}: PnL: {stat['pnl']:+7.0f} | WR: {stat['wr']*100:5.1f}% | Trades: {stat['trades']:2d}")
            
        print("\n--- BOTTOM STOCKS ---")
        for s, stat in sorted_stats[-10:]:
            print(f"{s:8s}: PnL: {stat['pnl']:+7.0f} | WR: {stat['wr']*100:5.1f}% | Trades: {stat['trades']:2d}")
