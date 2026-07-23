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
        # Defaulting max_amount to 1000 and profit_target to 2.0 if they are invalid
        max_amount = row[1] if row[1] else 1000
        profit_target = row[2] if row[2] else 2.0
        stocks[row[0]] = {"max_amount": max_amount, "profit_target": profit_target}
    return stocks

STOCKS = get_stocks_from_db()
print(f"Loaded {len(STOCKS)} stocks from the database.")

cached_data = {}
for i, s in enumerate(STOCKS):
    print(f"Downloading {s} ({i+1}/{len(STOCKS)})...")
    df = yf.Ticker(s).history(period="2y", interval="1d", auto_adjust=False, actions=False)
    if df.empty:
        print(f"Warning: No data for {s}")
        continue
    if isinstance(df.columns, pd.MultiIndex): 
        df.columns = df.columns.droplevel(1)
    cached_data[s] = compute_indicators(df)

grid = {'atr_mul': 1.5, 'stop_mul': 2.3, 'max_stop': -12.0, 'rsi_exit': 80, 'prot_act': 5.0, 'prot_drop': 0.5, 'dip_th': 7, 'mom_th': 8}

trades = []
stock_stats = {}
for s, c in STOCKS.items():
    if s not in cached_data:
        continue
    stock_trades = run_backtest_with_params(s, c, cached_data[s], grid)
    trades.extend(stock_trades)
    stock_pnl = sum(t['pnl_eur'] for t in stock_trades)
    stock_wr = len([t for t in stock_trades if t['pnl_pct'] > 0]) / len(stock_trades) if stock_trades else 0
    stock_stats[s] = {'pnl': stock_pnl, 'wr': stock_wr, 'trades': len(stock_trades)}

bot_total_pnl = sum(t['pnl_eur'] for t in trades)
bot_wr = len([t for t in trades if t['pnl_pct'] > 0]) / len(trades) if trades else 0

print(f"\n--- BOT PERFORMANCE (57 STOCKS) ---")
print(f"Total PnL: {bot_total_pnl:+8.0f} EUR")
print(f"Win Rate : {bot_wr*100:4.1f}%")
print(f"Trades   : {len(trades):3d}")

print("\n--- FULL PER STOCK BREAKDOWN ---")
sorted_stats = sorted(stock_stats.items(), key=lambda item: item[1]['pnl'], reverse=True)
for s, stat in sorted_stats:
    print(f"{s:8s}: PnL: {stat['pnl']:+7.0f} | WR: {stat['wr']*100:5.1f}% | Trades: {stat['trades']:2d}")

print("\n--- BUY AND HOLD SP500 ETF (ESE.PA) COMPARISON ---")
# Let's check ESE.PA which is the S&P 500 ETF in EUR
if "ESE.PA" in cached_data:
    df_sp500 = cached_data["ESE.PA"]
else:
    df_sp500 = yf.Ticker("ESE.PA").history(period="2y", interval="1d", auto_adjust=False, actions=False)

if len(df_sp500) >= 2:
    # Get the price 2 years ago (first row) and the latest price
    start_price = df_sp500['Close'].iloc[0]
    end_price = df_sp500['Close'].iloc[-1]
    
    # 20000 EUR invested
    shares_bought = 20000 / start_price
    end_value = shares_bought * end_price
    buy_hold_pnl = end_value - 20000
    buy_hold_pct = (end_price - start_price) / start_price * 100
    
    print(f"Start Price (2y ago) : {start_price:.2f}")
    print(f"End Price (Today)    : {end_price:.2f}")
    print(f"Total Return (%)     : {buy_hold_pct:+.2f}%")
    print(f"Buy & Hold PnL (20k) : {buy_hold_pnl:+8.0f} EUR")
    
    diff = bot_total_pnl - buy_hold_pnl
    print(f"\nDifference (Bot vs B&H): {diff:+8.0f} EUR")
    if diff > 0:
        print("Bot OUTPERFORMED Buy & Hold S&P 500!")
    else:
        print("Bot UNDERPERFORMED Buy & Hold S&P 500.")
else:
    print("Not enough data to calculate SP500 B&H.")
