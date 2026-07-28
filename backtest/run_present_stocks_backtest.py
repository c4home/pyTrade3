import sqlite3
import os
import yfinance as yf
import pandas as pd
from core_backtest_engine import compute_indicators, run_backtest_with_params

db_path = os.path.join(os.path.dirname(__file__), '..', 'trading_bot.db')

PRODUCT_MAP = {
    "VRT": "AI Power & Cooling",
    "EBAY": "E-Commerce Marketplace",
    "DELL": "Enterprise Servers & PCs",
    "INTC": "Semiconductors & Foundry",
    "DVA": "Kidney Care & Dialysis",
    "MU": "Memory & Storage (DRAM)",
    "CIEN": "Optical Networking",
    "NVDA": "AI GPUs & Infrastructure",
    "MRK": "Pharmaceuticals",
    "TXN": "Analog Chips & Sensors",
    "IBKR": "Global Brokerage Platform",
    "AMD": "High-Perf CPUs & GPUs",
    "CSCO": "Enterprise Networks & Sec",
    "AVGO": "Broadcom Chips & Software",
    "BAC": "Consumer & Invest Bank",
    "ESE.PA": "BNP S&P 500 ETF (EUR)",
    "JPM": "Global Investment Bank",
    "ORCL": "Cloud Database & Software",
    "AAPL": "iPhone, Mac & Ecosystem",
    "GOOG": "Search, Cloud & AI",
    "BARC.L": "Barclays Retail Banking",
    "MRNA": "mRNA Vaccines & Biotech",
    "WFC": "Wells Fargo Bank",
    "XOM": "ExxonMobil Energy & Gas",
    "TSM": "TSMC Chip Foundry",
    "ASML": "EUV Lithography Systems",
    "CVX": "Chevron Oil & Energy",
    "COP": "ConocoPhillips Oil E&P",
    "KO": "Coca-Cola Beverages",
    "SAF.PA": "Safran Aerospace & Defense",
    "HAL": "Halliburton Oilfield Tech",
    "WMT": "Walmart Superstore Retail",
    "META": "Meta Platforms & AI",
    "TMO": "Thermo Fisher Life Sci",
    "UNH": "UnitedHealth Group Care",
    "JNJ": "Johnson & Johnson Health",
    "PFE": "Pfizer BioPharmaceuticals",
    "IBM": "Hybrid Cloud, AI & Mainframe",
    "AIR.PA": "Airbus Commercial Aircraft",
    "APP": "AppLovin Ad Tech Platform",
    "ALB": "Albemarle Specialty Lithium",
    "ABBV": "AbbVie BioPharma",
    "LLY": "Eli Lilly Obesity & Pharma",
    "QCOM": "Qualcomm Mobile Chips",
    "GE": "GE Aerospace Jet Engines",
    "SPCX": "SPAC Investment ETF",
    "EGLN.L": "iShares Physical Gold ETF",
    "ARM": "ARM Semiconductor IP",
    "AMZN": "Amazon E-Commerce & AWS",
    "MCD": "McDonald's Fast Food",
    "AMGN": "Amgen Biopharmaceuticals",
    "MSFT": "Microsoft Cloud & AI",
    "ABT": "Abbott Labs MedTech",
    "HO.PA": "Thales Defense & Security",
    "V": "Visa Payment Network",
    "CVNA": "Carvana Online Used Auto",
    "ISRG": "Intuitive Surgical Robots",
    "COST": "Costco Wholesale Clubs",
    "MA": "Mastercard Payments",
    "NFLX": "Netflix Streaming Video",
    "BSX": "Boston Scientific MedTech",
    "FLEX": "Flex Industrial Mfg",
    "TSLA": "Tesla EVs & Energy",
    "ADSK": "Autodesk CAD Software",
    "KKR": "KKR Private Equity Assets",
    "DECK": "Deckers Footwear & UGG"
}

def get_stocks_from_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT stock_id, max_amount, profit_target, is_auto_watchlist, manual_mode FROM stocks")
    rows = cursor.fetchall()
    conn.close()
    
    stocks = {}
    for row in rows:
        max_amount = row[1] if row[1] else 1000
        profit_target = row[2] if row[2] else 2.0
        is_wl = True if (row[3] == 1 or row[4] == 1) else False
        stocks[row[0]] = {"max_amount": max_amount, "profit_target": profit_target, "is_watchlist": is_wl}
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
            df = yf.Ticker(s).history(period="3y", interval="1d", auto_adjust=False, actions=False)
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
    y1_start = pd.Timestamp('2024-01-01', tz='UTC')
    y1_end = pd.Timestamp('2024-12-31 23:59:59', tz='UTC')
    y2_start = pd.Timestamp('2025-01-01', tz='UTC')
    y2_end = pd.Timestamp('2025-12-31 23:59:59', tz='UTC')
    y3_start = pd.Timestamp('2026-01-01', tz='UTC')
    
    bot_y1_pnl, bot_y2_pnl, bot_y3_pnl = 0, 0, 0
    bot_y1_trades, bot_y2_trades, bot_y3_trades = 0, 0, 0
    
    for i, (s, c) in enumerate(STOCKS.items()):
        if progress_callback: progress_callback(50 + int((i/total)*50), f"Simulating {s} ({i+1}/{total})...")
        if s not in cached_data:
            continue
        df_sim = cached_data[s].loc['2024-01-01':]
        if df_sim.empty:
            continue
        stock_trades = run_backtest_with_params(s, c, df_sim, grid)
        trades.extend(stock_trades)
        
        y1_pnl, y2_pnl, y3_pnl = 0, 0, 0
        y1_tc, y2_tc, y3_tc = 0, 0, 0
        dip_cnt, mom_cnt = 0, 0
        dip_pnl_stk, mom_pnl_stk = 0, 0
        rsi_exits, trail_exits, macd_exits, prot_exits, stop_exits = 0, 0, 0, 0, 0
        for t in stock_trades:
            sd = pd.to_datetime(t['sell_date'], utc=True)
            if sd <= y1_end:
                y1_pnl += t['pnl_eur']
                y1_tc += 1
            elif sd <= y2_end:
                y2_pnl += t['pnl_eur']
                y2_tc += 1
            else:
                y3_pnl += t['pnl_eur']
                y3_tc += 1
                
            if t.get('strategy') == 'DIP':
                dip_cnt += 1
                dip_pnl_stk += t['pnl_eur']
            elif t.get('strategy') == 'MOMENTUM':
                mom_cnt += 1
                mom_pnl_stk += t['pnl_eur']

            reason = t.get('sell_reason', '')
            if reason == 'RSI': rsi_exits += 1
            elif reason == 'Trailing': trail_exits += 1
            elif reason == 'MACD': macd_exits += 1
            elif reason == 'Protective': prot_exits += 1
            elif reason == 'Stop': stop_exits += 1
                
        stock_pnl = y1_pnl + y2_pnl + y3_pnl
        stock_wr = len([t for t in stock_trades if t['pnl_pct'] > 0]) / len(stock_trades) if stock_trades else 0
        stock_stats[s] = {
            'pnl': stock_pnl, 
            'wr': stock_wr, 
            'trades': len(stock_trades), 
            'y1_pnl': y1_pnl, 
            'y2_pnl': y2_pnl, 
            'y3_pnl': y3_pnl,
            'y1_tc': y1_tc, 
            'y2_tc': y2_tc,
            'y3_tc': y3_tc,
            'dip_cnt': dip_cnt,
            'mom_cnt': mom_cnt,
            'dip_pnl': dip_pnl_stk,
            'mom_pnl': mom_pnl_stk,
            'rsi_exits': rsi_exits,
            'trail_exits': trail_exits,
            'macd_exits': macd_exits,
            'prot_exits': prot_exits,
            'stop_exits': stop_exits,
            'is_watchlist': c.get('is_watchlist', False)
        }
        
        bot_y1_pnl += y1_pnl
        bot_y2_pnl += y2_pnl
        bot_y3_pnl += y3_pnl
        bot_y1_trades += y1_tc
        bot_y2_trades += y2_tc
        bot_y3_trades += y3_tc

    bot_total_pnl = sum(t['pnl_eur'] for t in trades)
    bot_wr = len([t for t in trades if t['pnl_pct'] > 0]) / len(trades) if trades else 0

    dip_trades_list = [t for t in trades if t.get('strategy') == 'DIP']
    mom_trades_list = [t for t in trades if t.get('strategy') == 'MOMENTUM']

    dip_pnl_total = sum(t['pnl_eur'] for t in dip_trades_list)
    dip_wr_total = (len([t for t in dip_trades_list if t['pnl_pct'] > 0]) / len(dip_trades_list) * 100) if dip_trades_list else 0.0

    mom_pnl_total = sum(t['pnl_eur'] for t in mom_trades_list)
    mom_wr_total = (len([t for t in mom_trades_list if t['pnl_pct'] > 0]) / len(mom_trades_list) * 100) if mom_trades_list else 0.0

    gross_profit = sum(t['pnl_eur'] for t in trades if t['pnl_eur'] > 0)
    gross_loss = abs(sum(t['pnl_eur'] for t in trades if t['pnl_eur'] < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

    winning_trades = [t for t in trades if t['pnl_pct'] > 0]
    losing_trades = [t for t in trades if t['pnl_pct'] <= 0]

    avg_win_eur = (sum(t['pnl_eur'] for t in winning_trades) / len(winning_trades)) if winning_trades else 0.0
    avg_loss_eur = (sum(t['pnl_eur'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0.0

    avg_win_pct = (sum(t['pnl_pct'] for t in winning_trades) / len(winning_trades)) if winning_trades else 0.0
    avg_loss_pct = (sum(t['pnl_pct'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0.0

    # Group by Exit Reason
    exit_reasons = {}
    for t in trades:
        reason = t.get('sell_reason', 'Unknown')
        if reason not in exit_reasons:
            exit_reasons[reason] = {'count': 0, 'pnl': 0.0, 'wins': 0}
        exit_reasons[reason]['count'] += 1
        exit_reasons[reason]['pnl'] += t['pnl_eur']
        if t['pnl_pct'] > 0:
            exit_reasons[reason]['wins'] += 1

    today_str = now.strftime('%Y-%m-%d')

    output_lines = []
    output_lines.append(f"# BOT PERFORMANCE ({len(STOCKS)} STOCKS)")
    output_lines.append(f"**Total PnL:** {bot_total_pnl:+8.0f} EUR  ")
    output_lines.append(f"**Profit Factor:** {profit_factor:4.2f} (Gross Gains: +{gross_profit:.0f}€ / Gross Losses: -{gross_loss:.0f}€)  ")
    output_lines.append(f"**Win Rate:** {bot_wr*100:4.1f}% ({len(winning_trades)} wins / {len(losing_trades)} losses)  ")
    output_lines.append(f"**Avg Win:** {avg_win_eur:+6.1f} EUR ({avg_win_pct:+.2f}%) | **Avg Loss:** {avg_loss_eur:+6.1f} EUR ({avg_loss_pct:+.2f}%)  ")
    output_lines.append(f"**Year 1 PnL (2024-01-01 to 2024-12-31):** {bot_y1_pnl:+8.0f} EUR ({bot_y1_trades} trades)  ")
    output_lines.append(f"**Year 2 PnL (2025-01-01 to 2025-12-31):** {bot_y2_pnl:+8.0f} EUR ({bot_y2_trades} trades)  ")
    output_lines.append(f"**Year 3 PnL (2026-01-01 to present):** {bot_y3_pnl:+8.0f} EUR ({bot_y3_trades} trades)  ")
    output_lines.append(f"**Total Trades:** {len(trades)}  \n")

    output_lines.append("### 🎯 BUY STRATEGY TRIGGER BREAKDOWN")
    output_lines.append(f"- **Strategy A (DIP Buyer):** {dip_pnl_total:+8.0f} EUR ({len(dip_trades_list)} trades, {dip_wr_total:4.1f}% WR)")
    output_lines.append(f"- **Strategy B (MOMENTUM Breakout):** {mom_pnl_total:+8.0f} EUR ({len(mom_trades_list)} trades, {mom_wr_total:4.1f}% WR)  \n")
    
    output_lines.append("### 🚪 EXIT TRIGGER BREAKDOWN (Why Trades Closed)")
    output_lines.append("```text")
    output_lines.append(f"{'Exit Reason':<18} | {'Trades':>6} | {'Total PnL (EUR)':>15} | {'Win Rate':>8}")
    output_lines.append("-" * 55)
    for reason, data in sorted(exit_reasons.items(), key=lambda x: x[1]['pnl'], reverse=True):
        wr_r = (data['wins'] / data['count'] * 100) if data['count'] > 0 else 0.0
        output_lines.append(f"{reason:<18} | {data['count']:6d} | {data['pnl']:+15.0f} | {wr_r:7.1f}%")
    output_lines.append("```\n")

    output_lines.append("## FULL PER STOCK BREAKDOWN")
    output_lines.append(f"*(W) = Watchlist / Auto-Watchlist stock*  ")
    output_lines.append(f"* **Year 1 Period:** `2024-01-01` to `2024-12-31`  ")
    output_lines.append(f"* **Year 2 Period:** `2025-01-01` to `2025-12-31`  ")
    output_lines.append(f"* **Year 3 Period:** `2026-01-01` to present (`{today_str}`)  ")
    output_lines.append("```text")
    output_lines.append(f"{'Symbol':<11} | {'Product / Sector':<28} | {'Total':>8} | {'Y1':>8} | {'Y2':>8} | {'Y3':>8} | {'WR':>6} | {'Trades':>6} | {'DIP':>5} | {'MOM':>5} | {'RSI':>5} | {'Trail':>5} | {'MACD':>5} | {'Prot':>5} | {'Stop':>5}")
    output_lines.append("-" * 159)
    
    sorted_stats = sorted(stock_stats.items(), key=lambda item: item[1]['pnl'], reverse=True)
    for s, stat in sorted_stats:
        sym_str = f"{s} (W)" if stat.get('is_watchlist') else s
        prod_str = PRODUCT_MAP.get(s, "Equities")
        output_lines.append(f"{sym_str:11s} | {prod_str:28s} | {stat['pnl']:+8.0f} | {stat['y1_pnl']:+8.0f} | {stat['y2_pnl']:+8.0f} | {stat['y3_pnl']:+8.0f} | {stat['wr']*100:5.1f}% | {stat['trades']:6d} | {stat['dip_cnt']:5d} | {stat['mom_cnt']:5d} | {stat['rsi_exits']:5d} | {stat['trail_exits']:5d} | {stat['macd_exits']:5d} | {stat['prot_exits']:5d} | {stat['stop_exits']:5d}")
    output_lines.append("```\n")

    output_lines.append("## BUY AND HOLD SP500 ETF (ESE.PA) COMPARISON")
    if "ESE.PA" in cached_data:
        df_sp500 = cached_data["ESE.PA"]
    else:
        df_sp500 = yf.Ticker("ESE.PA").history(period="3y", interval="1d", auto_adjust=False, actions=False)

    if len(df_sp500) >= 2:
        df_sp500_utc = df_sp500.copy()
        if df_sp500_utc.index.tz is None:
            df_sp500_utc.index = df_sp500_utc.index.tz_localize('UTC')
        else:
            df_sp500_utc.index = df_sp500_utc.index.tz_convert('UTC')
            
        df_2024 = df_sp500_utc.loc['2024-01-01':'2024-12-31']
        df_2025 = df_sp500_utc.loc['2025-01-01':'2025-12-31']
        df_2026 = df_sp500_utc.loc['2026-01-01':]

        start_price = df_2024['Close'].iloc[0] if not df_2024.empty else df_sp500_utc['Close'].iloc[0]
        p_2024_end = df_2024['Close'].iloc[-1] if not df_2024.empty else start_price
        p_2025_end = df_2025['Close'].iloc[-1] if not df_2025.empty else p_2024_end
        end_price = df_sp500_utc['Close'].iloc[-1]
        
        shares_bought = 20000 / start_price
        val_2024_end = shares_bought * p_2024_end
        val_2025_end = shares_bought * p_2025_end
        end_value = shares_bought * end_price
        
        buy_hold_pnl = end_value - 20000
        buy_hold_pct = (end_price - start_price) / start_price * 100
        
        y1_bh_pnl = val_2024_end - 20000
        y2_bh_pnl = val_2025_end - val_2024_end
        y3_bh_pnl = end_value - val_2025_end
        
        output_lines.append("```text")
        output_lines.append(f"Start Price (2024-01-01)  : {start_price:.2f}")
        output_lines.append(f"2024 End Price            : {p_2024_end:.2f}")
        output_lines.append(f"2025 End Price            : {p_2025_end:.2f}")
        output_lines.append(f"End Price (Present)       : {end_price:.2f}")
        output_lines.append(f"Total Return (%)          : {buy_hold_pct:+.2f}%")
        output_lines.append(f"Buy & Hold PnL (20k)      : {buy_hold_pnl:+8.0f} EUR")
        output_lines.append(f"   -> Year 1 PnL (2024)   : {y1_bh_pnl:+8.0f} EUR")
        output_lines.append(f"   -> Year 2 PnL (2025)   : {y2_bh_pnl:+8.0f} EUR")
        output_lines.append(f"   -> Year 3 PnL (2026)   : {y3_bh_pnl:+8.0f} EUR")
        
        diff = bot_total_pnl - buy_hold_pnl
        diff_y1 = bot_y1_pnl - y1_bh_pnl
        diff_y2 = bot_y2_pnl - y2_bh_pnl
        diff_y3 = bot_y3_pnl - y3_bh_pnl
        output_lines.append(f"\nDifference (Bot vs B&H): {diff:+8.0f} EUR")
        output_lines.append(f"   -> Year 1 Diff (2024)  : {diff_y1:+8.0f} EUR")
        output_lines.append(f"   -> Year 2 Diff (2025)  : {diff_y2:+8.0f} EUR")
        output_lines.append(f"   -> Year 3 Diff (2026)  : {diff_y3:+8.0f} EUR")
        
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
