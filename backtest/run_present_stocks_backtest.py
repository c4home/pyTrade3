import sqlite3
import os
import yfinance as yf
import pandas as pd
from core_backtest_engine import compute_indicators, run_backtest_with_params

db_path = os.path.join(os.path.dirname(__file__), '..', 'trading_bot.db')

def get_stocks_from_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT stock_id, max_amount, profit_target FROM stocks")
    rows = cursor.fetchall()
    conn.close()
    
    stocks = {}
    for row in rows:
        max_amount = row[1] if row[1] else 1000
        profit_target = row[2] if row[2] else 2.0
        stocks[row[0]] = {"max_amount": max_amount, "profit_target": profit_target}
    return stocks

def run_backtest_for_db_stocks(progress_callback=None, pause_callback=None):
    STOCKS = get_stocks_from_db()
    if progress_callback: progress_callback(0, f"Loaded {len(STOCKS)} stocks from the database.")
    
    cached_data = {}
    total = len(STOCKS)
    for i, s in enumerate(STOCKS):
        if pause_callback:
            while pause_callback():
                import time
                time.sleep(1.0)
        if progress_callback: progress_callback(int((i/total)*50), f"Downloading {s} ({i+1}/{total})...")
        try:
            df = yf.Ticker(s).history(period="2y", interval="1d", auto_adjust=False, actions=False)
            if df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.droplevel(1)
            cached_data[s] = compute_indicators(df)
        except Exception:
            pass
            
        import time
        time.sleep(1.0)

    grid = {'atr_mul': 1.5, 'stop_mul': 2.3, 'max_stop': -12.0, 'rsi_exit': 80, 'prot_act': 5.0, 'prot_drop': 0.5, 'dip_th': 7, 'mom_th': 8}
    
    trades = []
    stock_stats = {}
    
    now = pd.Timestamp.utcnow()
    cutoff_date = now - pd.Timedelta(days=365)
    
    bot_y1_pnl, bot_y2_pnl = 0, 0
    bot_y1_trades, bot_y2_trades = 0, 0
    
    for i, (s, c) in enumerate(STOCKS.items()):
        if progress_callback: progress_callback(50 + int((i/total)*50), f"Simulating {s} ({i+1}/{total})...")
        if s not in cached_data:
            continue
        stock_trades = run_backtest_with_params(s, c, cached_data[s], grid)
        trades.extend(stock_trades)
        
        y1_pnl, y2_pnl = 0, 0
        y1_tc, y2_tc = 0, 0
        for t in stock_trades:
            sd = pd.to_datetime(t['sell_date'], utc=True)
            if sd < cutoff_date:
                y1_pnl += t['pnl_eur']
                y1_tc += 1
            else:
                y2_pnl += t['pnl_eur']
                y2_tc += 1
                
        stock_pnl = y1_pnl + y2_pnl
        stock_wr = len([t for t in stock_trades if t['pnl_pct'] > 0]) / len(stock_trades) if stock_trades else 0
        stock_stats[s] = {'pnl': stock_pnl, 'wr': stock_wr, 'trades': len(stock_trades), 'y1_pnl': y1_pnl, 'y2_pnl': y2_pnl, 'y1_tc': y1_tc, 'y2_tc': y2_tc}
        
        bot_y1_pnl += y1_pnl
        bot_y2_pnl += y2_pnl
        bot_y1_trades += y1_tc
        bot_y2_trades += y2_tc

    bot_total_pnl = sum(t['pnl_eur'] for t in trades)
    bot_wr = len([t for t in trades if t['pnl_pct'] > 0]) / len(trades) if trades else 0

    output_lines = []
    output_lines.append(f"# BOT PERFORMANCE ({len(STOCKS)} STOCKS)")
    output_lines.append(f"**Total PnL:** {bot_total_pnl:+8.0f} EUR  ")
    output_lines.append(f"**Year 1 PnL (older):** {bot_y1_pnl:+8.0f} EUR ({bot_y1_trades} trades)  ")
    output_lines.append(f"**Year 2 PnL (recent):** {bot_y2_pnl:+8.0f} EUR ({bot_y2_trades} trades)  ")
    output_lines.append(f"**Win Rate:** {bot_wr*100:4.1f}%  ")
    output_lines.append(f"**Total Trades:** {len(trades)}  \n")
    
    y2_end = now.strftime('%Y')
    y2_start = cutoff_date.strftime('%Y')
    y1_start = (cutoff_date - pd.Timedelta(days=365)).strftime('%Y')

    output_lines.append("## FULL PER STOCK BREAKDOWN")
    output_lines.append("```text")
    header_y1 = f"Y1 ({y1_start}-{y2_start})"
    header_y2 = f"Y2 ({y2_start}-{y2_end})"
    output_lines.append(f"{'Symbol':<8} | {'Total':>8} | {header_y1:>14} | {header_y2:>14} | {'WR':>6} | {'Trades':>6}")
    output_lines.append("-" * 69)
    
    sorted_stats = sorted(stock_stats.items(), key=lambda item: item[1]['pnl'], reverse=True)
    for s, stat in sorted_stats:
        output_lines.append(f"{s:8s} | {stat['pnl']:+8.0f} | {stat['y1_pnl']:+14.0f} | {stat['y2_pnl']:+14.0f} | {stat['wr']*100:5.1f}% | {stat['trades']:6d}")
    output_lines.append("```\n")

    output_lines.append("## BUY AND HOLD SP500 ETF (ESE.PA) COMPARISON")
    if "ESE.PA" in cached_data:
        df_sp500 = cached_data["ESE.PA"]
    else:
        df_sp500 = yf.Ticker("ESE.PA").history(period="2y", interval="1d", auto_adjust=False, actions=False)

    if len(df_sp500) >= 2:
        start_price = df_sp500['Close'].iloc[0]
        end_price = df_sp500['Close'].iloc[-1]
        
        df_sp500_utc = df_sp500.copy()
        if df_sp500_utc.index.tz is None:
            df_sp500_utc.index = df_sp500_utc.index.tz_localize('UTC')
        else:
            df_sp500_utc.index = df_sp500_utc.index.tz_convert('UTC')
            
        cutoff_prices = df_sp500_utc.loc[:cutoff_date]['Close']
        cutoff_price = cutoff_prices.iloc[-1] if not cutoff_prices.empty else start_price
        
        shares_bought = 20000 / start_price
        end_value = shares_bought * end_price
        buy_hold_pnl = end_value - 20000
        buy_hold_pct = (end_price - start_price) / start_price * 100
        
        cutoff_value = shares_bought * cutoff_price
        y1_bh_pnl = cutoff_value - 20000
        y2_bh_pnl = end_value - cutoff_value
        
        output_lines.append("```text")
        output_lines.append(f"Start Price (2y ago) : {start_price:.2f}")
        output_lines.append(f"Cutoff Price (1y ago): {cutoff_price:.2f}")
        output_lines.append(f"End Price (Today)    : {end_price:.2f}")
        output_lines.append(f"Total Return (%)     : {buy_hold_pct:+.2f}%")
        output_lines.append(f"Buy & Hold PnL (20k) : {buy_hold_pnl:+8.0f} EUR")
        output_lines.append(f"   -> Year 1 PnL     : {y1_bh_pnl:+8.0f} EUR")
        output_lines.append(f"   -> Year 2 PnL     : {y2_bh_pnl:+8.0f} EUR")
        
        diff = bot_total_pnl - buy_hold_pnl
        diff_y1 = bot_y1_pnl - y1_bh_pnl
        diff_y2 = bot_y2_pnl - y2_bh_pnl
        output_lines.append(f"\nDifference (Bot vs B&H): {diff:+8.0f} EUR")
        output_lines.append(f"   -> Year 1 Diff      : {diff_y1:+8.0f} EUR")
        output_lines.append(f"   -> Year 2 Diff      : {diff_y2:+8.0f} EUR")
        
        if diff > 0:
            output_lines.append("\nBot OUTPERFORMED Buy & Hold S&P 500 overall!")
        else:
            output_lines.append("\nBot UNDERPERFORMED Buy & Hold S&P 500 overall.")
        output_lines.append("```")
    else:
        output_lines.append("Not enough data to calculate SP500 B&H.")

    result_path = os.path.join(os.path.dirname(__file__), 'present_stocks_results.md')
    with open(result_path, 'w') as f:
        f.write('\n'.join(output_lines))
        
    return result_path

if __name__ == "__main__":
    def print_progress(pct, msg):
        print(f"[{pct}%] {msg}")
    path = run_backtest_for_db_stocks(print_progress)
    print(f"Results saved to {path}")
