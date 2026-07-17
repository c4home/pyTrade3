import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from backtest import STOCKS, compute_indicators, calculate_score

MAX_PROFIT_PCT = 15.0
MIN_STOP_LOSS = -3.0
MAX_STOP_LOSS = -15.0
BUY_COOLDOWN_DAYS = 1
SELL_COOLDOWN_DAYS = 1

def run_backtest_sim(symbol, config, data, stop_multiplier, atr_multiplier=1.5):
    profit_target = config["profit_target"]
    max_amount = config["max_amount"]

    trades = []
    position = None
    last_buy_day = None
    last_sell_day = None
    prev_macd_class = 'NEUTRAL'

    for i in range(200, len(data)):
        row = data.iloc[i]
        prev_row = data.iloc[i - 1]
        date = data.index[i]
        price = row['Close']
        atr = row.get('ATR14', 1.0)
        rsi = row.get('RSI', 50)
        prev_close = prev_row['Close']

        if pd.isna(price) or price <= 0:
            continue

        if atr > 0 and price > 0:
            atr_pct = (atr / price) * 100
            dynamic_profit_target = max(profit_target, min(atr_multiplier * atr_pct, MAX_PROFIT_PCT)) / 100
            raw_stop_pct = stop_multiplier * atr_pct
            dynamic_stop_loss = -max(abs(MIN_STOP_LOSS), min(raw_stop_pct, abs(MAX_STOP_LOSS)))
        else:
            dynamic_profit_target = profit_target / 100
            dynamic_stop_loss = -5.0

        if position is not None:
            pnl_pct = ((price - position['buy_price']) / position['buy_price']) * 100
            if pnl_pct > position['highest_pnl']:
                position['highest_pnl'] = pnl_pct

            sell_reason = None
            profit_target_pct = dynamic_profit_target * 100
            current_atr_pct = (atr / price) * 100 if price > 0 else 0
            dynamic_trail_drop = max(1.0, min(current_atr_pct * 1.0, 3.0))

            if position['highest_pnl'] >= profit_target_pct:
                trail_activation = position['highest_pnl'] - dynamic_trail_drop
                if pnl_pct <= trail_activation:
                    sell_reason = "Trailing Profit"
            elif position['highest_pnl'] >= 2.0:
                protective_trail_drop = position['highest_pnl'] * 0.5
                protective_floor = position['highest_pnl'] - protective_trail_drop
                if pnl_pct <= protective_floor:
                    sell_reason = "Protective Stop"

            if sell_reason is None and pnl_pct <= dynamic_stop_loss:
                sell_reason = "Stop Loss"
            if sell_reason is None and rsi >= 80 and pnl_pct > 1.0:
                sell_reason = "RSI Overbought"

            macd_class = row.get('MACD_Class', 'NEUTRAL')
            if sell_reason is None:
                if macd_class in ('S_BEAR', 'BEAR') and prev_macd_class in ('S_BULL', 'BULL') and pnl_pct > 1.0:
                    sell_reason = "MACD Bearish"

            prev_macd_class = macd_class

            if sell_reason:
                trades.append({
                    'symbol': symbol,
                    'pnl_pct': pnl_pct,
                    'pnl_eur': position['qty'] * (price - position['buy_price']),
                    'reason': sell_reason,
                })
                last_sell_day = date
                position = None
            continue

        if position is not None:
            continue

        if last_buy_day and (date - last_buy_day).days < BUY_COOLDOWN_DAYS: continue
        if last_sell_day and (date - last_sell_day).days < SELL_COOLDOWN_DAYS: continue

        if prev_close > 0:
            daily_change = (price - prev_close) / prev_close
            if daily_change > 0.05: continue

        if rsi >= 70: continue

        if i >= 3:
            close_3d_ago = data.iloc[i - 3]['Close']
            if close_3d_ago > 0:
                three_day_change = (price - close_3d_ago) / close_3d_ago
                if three_day_change > 0.15: continue

        score, strategy = calculate_score(row, prev_row)
        buy_signal = False

        if strategy == "DIP" and score >= 7:
            if prev_close > 0:
                daily_drop = (price - prev_close) / prev_close
                if daily_drop < -0.07: continue
                if daily_drop < -0.03 and rsi > 45: continue
            buy_signal = True

        if strategy == "MOMENTUM" and score >= 8:
            if prev_close > 0:
                daily_change = (price - prev_close) / prev_close
                if daily_change > 0.05: continue
            if i >= 2:
                yest_close = data.iloc[i - 2]['Close']
                if yest_close > 0:
                    yesterday_change = (prev_close - yest_close) / yest_close
                    if yesterday_change > 0.15: continue
            if rsi > 70: continue
            buy_signal = True

        if buy_signal:
            qty = max(1, int(max_amount / price))
            position = {
                'qty': qty,
                'buy_price': price,
                'buy_date': date,
                'highest_pnl': 0.0,
            }
            last_buy_day = date

    if position is not None:
        last_price = data['Close'].iloc[-1]
        pnl_pct = ((last_price - position['buy_price']) / position['buy_price']) * 100
        trades.append({
            'symbol': symbol,
            'pnl_pct': pnl_pct,
            'pnl_eur': position['qty'] * (last_price - position['buy_price']),
            'reason': 'STILL OPEN',
        })

    return trades

if __name__ == "__main__":
    print("Pre-fetching data...")
    cache = {}
    for symbol in STOCKS:
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="2y", interval="1d", auto_adjust=False, actions=False)
            if not data.empty and len(data) >= 250:
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.droplevel(1)
                cache[symbol] = compute_indicators(data)
        except:
            pass

    print("Testing STOP_MULTIPLIER variations...")
    multipliers = [1.0, 1.2, 1.5, 2.0, 2.5, 3.0]
    results = []

    for mult in multipliers:
        total_pnl = 0
        total_trades = 0
        stop_losses = 0
        sl_pnl = 0
        for symbol, data in cache.items():
            trades = run_backtest_sim(symbol, STOCKS[symbol], data, stop_multiplier=mult)
            total_trades += len(trades)
            total_pnl += sum(t['pnl_eur'] for t in trades)
            
            sl_trades = [t for t in trades if t['reason'] == 'Stop Loss']
            stop_losses += len(sl_trades)
            sl_pnl += sum(t['pnl_eur'] for t in sl_trades)
            
        results.append((mult, total_trades, total_pnl, stop_losses, sl_pnl))

    print(f"{'SL_Mult':<10} {'Trades':<8} {'Total PnL':<12} {'SL Hits':<10} {'SL PnL':<12}")
    print("-" * 55)
    for res in results:
        print(f"{res[0]:<10.1f} {res[1]:<8} €{res[2]:<11.0f} {res[3]:<10} €{res[4]:<11.0f}")
