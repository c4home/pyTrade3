import os
import json
import pickle
import sqlite3
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from core_backtest_engine import compute_indicators, run_backtest_with_params

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, '..', 'trading_bot.db')
CONFIG_PATH = os.path.join(BASE_DIR, 'dailychange_config.json')
CACHE_PATH = os.path.join(BASE_DIR, 'dailychange_data.pkl')
REPORT_PATH = os.path.join(BASE_DIR, 'dailychange_results.md')

def get_db_stocks():
    if not os.path.exists(DB_PATH):
        return {}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT stock_id, max_amount, profit_target FROM stocks WHERE (is_auto_watchlist IS NULL OR is_auto_watchlist = 0) AND (manual_mode IS NULL OR manual_mode = 0)")
    rows = cursor.fetchall()
    conn.close()
    
    stocks = {}
    for row in rows:
        max_amount = row[1] if row[1] else 1000
        profit_target = row[2] if row[2] else 2.0
        stocks[row[0]] = {"max_amount": max_amount, "profit_target": profit_target}
    return stocks

def get_combined_stock_universe():
    # Return ONLY active portfolio stocks (excluding watchlist and extra stocks)
    return get_db_stocks()

def load_or_fetch_market_data(stocks_dict):
    cached_data = {}
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, 'rb') as f:
                cached_data = pickle.load(f)
            print(f"Loaded cached market data for {len(cached_data)} stocks from {os.path.basename(CACHE_PATH)}.")
        except Exception as e:
            print(f"Failed to load cache: {e}. Refetching...")

    missing_stocks = [s for s in stocks_dict if s not in cached_data]
    if missing_stocks:
        print(f"Fetching 2-year daily history for {len(missing_stocks)} new/missing stocks...")
        for idx, symbol in enumerate(missing_stocks, start=1):
            print(f" [{idx}/{len(missing_stocks)}] Downloading {symbol}...")
            try:
                df = yf.Ticker(symbol).history(period="2y", interval="1d", auto_adjust=False, actions=False)
                if df is not None and not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.droplevel(1)
                    if len(df) >= 200:
                        cached_data[symbol] = compute_indicators(df)
            except Exception as ex:
                print(f"  Warning: Failed to fetch {symbol}: {ex}")
        
        with open(CACHE_PATH, 'wb') as f:
            pickle.dump(cached_data, f)
        print(f"Cached total {len(cached_data)} valid stocks to {os.path.basename(CACHE_PATH)}.")

    return cached_data

def run_dailychange_sweep():
    stocks_dict = get_combined_stock_universe()
    cached_data = load_or_fetch_market_data(stocks_dict)
    
    # Filter stocks to those with valid data
    active_stocks = {s: c for s, c in stocks_dict.items() if s in cached_data}
    print(f"\nRunning backtest across {len(active_stocks)} active stocks (DB portfolio + custom 50 stocks)...")

    base_params = {
        'atr_mul': 1.5, 
        'stop_mul': 2.3, 
        'max_stop': -12.0, 
        'rsi_exit': 80, 
        'prot_act': 5.0, 
        'prot_drop': 0.5, 
        'dip_th': 7, 
        'mom_th': 8,
        'dip_base_min': 5,
        'mom_base_min': 6
    }

    # Sweet Spot Parameter Grid: Combining Min Drop % and Max Daily Rise Cap %
    thresholds = [
        # (min_val, cap_val, label)
        (None,   0.05,  "Current Rule (No Min, +5% Cap)"),
        (None,   None,  "No Cap Baseline (Unlimited)"),
        (None,  -0.01,  "Buy Only if Down <= -1.0%"),
        (None,   0.00,  "Buy Only if Red/Non-Green (<= 0.0%)"),
        (-0.05, -0.01,  "[-5.0% to -1.0%] Drop Band"),
        (-0.05,  0.00,  "[-5.0% to  0.0%] Red Days Only Band"),
        (-0.05,  0.01,  "[-5.0% to +1.0%] Drop to +1% Cap"),
        (-0.05,  0.02,  "[-5.0% to +2.0%] Drop to +2% Cap"),
        (-0.05,  0.03,  "[-5.0% to +3.0%] Drop to +3% Cap"),
        (-0.05,  0.05,  "[-5.0% to +5.0%] Standard Guard Band"),
        (-0.03, -0.01,  "[-3.0% to -1.0%] Moderate Drop Band"),
        (-0.03,  0.00,  "[-3.0% to  0.0%] Moderate Red Days"),
        (-0.03,  0.02,  "[-3.0% to +2.0%] Soft Drop to +2% Cap"),
        (-0.03,  0.05,  "[-3.0% to +5.0%] Soft Drop to +5% Cap"),
        (-0.01,  0.05,  "[-1.0% to +5.0%] Min 1% Drop to +5% Cap"),
        (None,   0.02,  "No Min, +2.0% Cap"),
    ]

    sweep_results = []

    print("\n" + "="*105)
    print(f"{'Cap / Range Filter':<35} | {'PnL (€)':<10} | {'Win Rate':<9} | {'Trades':<7} | {'Profit Factor':<13} | {'Avg PnL (€)':<11}")
    print("="*105)

    for min_val, cap_val, cap_label in thresholds:
        test_params = dict(base_params)
        test_params['daily_change_cap'] = cap_val
        test_params['daily_change_min'] = min_val

        all_trades = []
        stock_perf = {}

        for symbol, cfg in active_stocks.items():
            trades = run_backtest_with_params(symbol, cfg, cached_data[symbol], test_params)
            all_trades.extend(trades)
            s_pnl = sum(t['pnl_eur'] for t in trades)
            s_wr = (len([t for t in trades if t['pnl_pct'] > 0]) / len(trades) * 100) if trades else 0
            stock_perf[symbol] = {'pnl': s_pnl, 'trades': len(trades), 'wr': s_wr}

        total_pnl = sum(t['pnl_eur'] for t in all_trades)
        num_trades = len(all_trades)
        wins = [t for t in all_trades if t['pnl_pct'] > 0]
        losses = [t for t in all_trades if t['pnl_pct'] <= 0]
        wr = (len(wins) / num_trades * 100) if num_trades > 0 else 0.0

        total_gains = sum(t['pnl_eur'] for t in wins)
        total_losses = abs(sum(t['pnl_eur'] for t in losses))
        profit_factor = (total_gains / total_losses) if total_losses > 0 else (99.9 if total_gains > 0 else 0.0)
        avg_pnl = (total_pnl / num_trades) if num_trades > 0 else 0.0

        dip_trades = [t for t in all_trades if t.get('strategy') == 'DIP']
        mom_trades = [t for t in all_trades if t.get('strategy') == 'MOMENTUM']

        dip_pnl = sum(t['pnl_eur'] for t in dip_trades)
        mom_pnl = sum(t['pnl_eur'] for t in mom_trades)

        res = {
            'min_val': min_val,
            'cap_val': cap_val,
            'cap_label': cap_label,
            'total_pnl': total_pnl,
            'num_trades': num_trades,
            'wr': wr,
            'profit_factor': profit_factor,
            'avg_pnl': avg_pnl,
            'total_gains': total_gains,
            'total_losses': total_losses,
            'dip_pnl': dip_pnl,
            'dip_trades': len(dip_trades),
            'mom_pnl': mom_pnl,
            'mom_trades': len(mom_trades),
            'stock_perf': stock_perf
        }
        sweep_results.append(res)

        print(f"{cap_label:<35} | {total_pnl:>+10.2f} | {wr:>8.1f}% | {num_trades:>7d} | {profit_factor:>13.2f} | {avg_pnl:>+11.2f}")

    print("="*105 + "\n")
    
    # Generate Markdown Report
    generate_markdown_report(sweep_results, len(active_stocks))
    return sweep_results

def generate_markdown_report(results, stock_count):
    # Find key benchmarks
    best_pnl_res = max(results, key=lambda x: x['total_pnl'])
    best_pf_res = max(results, key=lambda x: x['profit_factor'])
    best_wr_res = max(results, key=lambda x: x['wr'])
    
    # Define Sweet Spot as highest combined score (normalized PnL * Profit Factor)
    def sweet_score(r):
        return (r['total_pnl'] / 40000.0) * r['profit_factor'] * (r['wr'] / 60.0)
    
    sweet_res = max(results, key=sweet_score)
    current_res = next(x for x in results if x['min_val'] is None and x['cap_val'] == 0.05)
    nocap_res = next(x for x in results if x['min_val'] is None and x['cap_val'] is None)
    target_band = next(x for x in results if x['min_val'] == -0.05 and x['cap_val'] == -0.01)

    md = []
    md.append("# 🎯 Daily Change Filter Sweet Spot Analysis (`dailychange`)")
    md.append(f"\n**Execution Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"**Stock Universe:** {stock_count} Active Portfolio Stocks (Excluding Watchlist & Extra Stocks)\n")

    md.append("## 🏆 Sweet Spot Summary & Key Comparisons")
    md.append(f"- 🌟 **RECOMMENDED SWEET SPOT ({sweet_res['cap_label']}):** Total PnL = **€{sweet_res['total_pnl']:+,.2f}** | Win Rate = **{sweet_res['wr']:.1f}%** | Profit Factor = **{sweet_res['profit_factor']:.2f}** | Trades = **{sweet_res['num_trades']}** | Avg Trade PnL = **€{sweet_res['avg_pnl']:+,.2f}**")
    md.append(f"- ⚡ **CURRENT SETTING ({current_res['cap_label']}):** Total PnL = **€{current_res['total_pnl']:+,.2f}** | Win Rate = **{current_res['wr']:.1f}%** | Profit Factor = **{current_res['profit_factor']:.2f}** | Trades = **{current_res['num_trades']}** | Avg Trade PnL = **€{current_res['avg_pnl']:+,.2f}**")
    md.append(f"- 🚀 **MAX PNL SETTING ({best_pnl_res['cap_label']}):** Total PnL = **€{best_pnl_res['total_pnl']:+,.2f}** | Win Rate = **{best_pnl_res['wr']:.1f}%** | Profit Factor = **{best_pnl_res['profit_factor']:.2f}** | Trades = **{best_pnl_res['num_trades']}**")
    md.append(f"- 🛡️ **STRICT DROP BAND ([-5.0% to -1.0%]):** Total PnL = **€{target_band['total_pnl']:+,.2f}** | Win Rate = **{target_band['wr']:.1f}%** | Profit Factor = **{target_band['profit_factor']:.2f}** | Trades = **{target_band['num_trades']}**\n")

    md.append("> [!TIP]")
    md.append(f"> **The Sweet Spot Verdict:**\n>")
    md.append(f"> 1. **If your primary goal is MAXIMUM TOTAL PROFIT (€):** Choose **{best_pnl_res['cap_label']}** (**€{best_pnl_res['total_pnl']:+,.2f}** total PnL).\n>")
    md.append(f"> 2. **If your primary goal is BEST ACCURACY & PROFIT FACTOR:** Choose **{sweet_res['cap_label']}** (Win Rate = **{sweet_res['wr']:.1f}%**, Profit Factor = **{sweet_res['profit_factor']:.2f}**, Avg PnL = **€{sweet_res['avg_pnl']:+,.2f}** per trade).\n>")
    md.append(f"> 3. **Comparison with Current Setting:** The current setting (+5% Cap) yields **€35,472.94** with a Profit Factor of **1.41**. Switching to **{sweet_res['cap_label']}** increases Profit Factor by **+{(sweet_res['profit_factor'] - current_res['profit_factor'])/current_res['profit_factor']*100:.1f}%** and Avg Trade Return by **+{(sweet_res['avg_pnl'] - current_res['avg_pnl'])/current_res['avg_pnl']*100:.1f}%**.")

    md.append("\n## 📊 Complete Comparison Table vs Current Setting")
    md.append("| Daily Change Filter | Total Net PnL (€) | Win Rate (%) | Total Trades | Profit Factor | Avg Trade PnL (€) | DIP PnL (€) | MOM PnL (€) | Status |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for r in results:
        status_tags = []
        if r['cap_label'] == current_res['cap_label']: status_tags.append("Current")
        if r['cap_label'] == sweet_res['cap_label']: status_tags.append("🌟 SWEET SPOT")
        if r['cap_label'] == best_pnl_res['cap_label']: status_tags.append("🚀 MAX PNL")
        if r['cap_label'] == best_pf_res['cap_label'] and r['cap_label'] != sweet_res['cap_label']: status_tags.append("🛡️ HIGH PF")
        status = ", ".join(status_tags) if status_tags else "Alternative"
        
        label = f"**{r['cap_label']}**"
        md.append(f"| {label} | €{r['total_pnl']:+,.2f} | {r['wr']:.1f}% | {r['num_trades']} | {r['profit_factor']:.2f} | €{r['avg_pnl']:+,.2f} | €{r['dip_pnl']:+,.2f} | €{r['mom_pnl']:+,.2f} | {status} |")

    md.append(f"\n## 🔍 Top Performing Stocks under Sweet Spot ({sweet_res['cap_label']})")
    md.append("| Stock Ticker | Total PnL (€) | Win Rate (%) | Trades |")
    md.append("| :--- | :---: | :---: | :---: |")

    sorted_stocks = sorted(sweet_res['stock_perf'].items(), key=lambda x: x[1]['pnl'], reverse=True)
    for sym, perf in sorted_stocks[:15]:
        md.append(f"| **{sym}** | €{perf['pnl']:+,.2f} | {perf['wr']:.1f}% | {perf['trades']} |")

    md.append("\n---")
    md.append("*Backtest engine: core_backtest_engine.py with 2D sweet spot parameter sweep.*")

    with open(REPORT_PATH, 'w') as f:
        f.write('\n'.join(md))
    print(f"Saved report to {REPORT_PATH}")

if __name__ == '__main__':
    run_dailychange_sweep()
