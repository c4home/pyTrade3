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
        print("\n--- TOP 20 STOCKS ---")
        for s, stat in sorted_stats[:20]:
            print(f"{s:8s}: PnL: {stat['pnl']:+7.0f} | WR: {stat['wr']*100:5.1f}% | Trades: {stat['trades']:2d}")
            
        print("\n--- BOTTOM 20 STOCKS ---")
        for s, stat in sorted_stats[-20:]:
            print(f"{s:8s}: PnL: {stat['pnl']:+7.0f} | WR: {stat['wr']*100:5.1f}% | Trades: {stat['trades']:2d}")
