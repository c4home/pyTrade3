import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

STOCKS = {
    "AAPL":   {"max_amount": 1000, "profit_target": 2.0},
    "ABT":    {"max_amount": 1500, "profit_target": 5.0},
    "AIR.PA": {"max_amount": 1000, "profit_target": 3.0},
    "AMD":    {"max_amount": 2000, "profit_target": 2.0},
    "AMZN":   {"max_amount": 2000, "profit_target": 2.0},
    "ARM":    {"max_amount": 2000, "profit_target": 3.0},
    "ASML":   {"max_amount": 3000, "profit_target": 3.0},
    "AVGO":   {"max_amount": 1000, "profit_target": 5.0},
    "BARC.L": {"max_amount": 1000, "profit_target": 3.0},
    "EGLN.L": {"max_amount": 5500, "profit_target": 2.0},
    "ESE.PA": {"max_amount": 7500, "profit_target": 2.0},
    "GOOG":   {"max_amount": 2000, "profit_target": 2.0},
    "HO.PA":  {"max_amount": 1000, "profit_target": 3.0},
    "INTC":   {"max_amount": 1000, "profit_target": 5.0},
    "JPM":    {"max_amount": 1000, "profit_target": 5.0},
    "MRNA":   {"max_amount": 1000, "profit_target": 3.0},
    "MSFT":   {"max_amount": 2000, "profit_target": 2.0},
    "MU":     {"max_amount": 1000, "profit_target": 3.0},
    "NVDA":   {"max_amount": 1000, "profit_target": 3.0},
    "ORCL":   {"max_amount": 1000, "profit_target": 5.0},
    "QCOM":   {"max_amount": 1000, "profit_target": 2.0},
    "SAF.PA": {"max_amount": 1000, "profit_target": 5.0},
    "TSLA":   {"max_amount": 3000, "profit_target": 3.0},
    "TSM":    {"max_amount": 2000, "profit_target": 3.0},
}

def compute_indicators(df):
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']

    tr = pd.concat([abs(high - low), abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    df['ATR14'] = tr.rolling(14).mean()

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))

    df['MA20'] = close.rolling(20).mean()
    df['MA50'] = close.rolling(50).mean()
    df['MA200'] = close.rolling(200).mean()

    df['BB_Mid'] = df['MA20']
    bb_std = close.rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + 2 * bb_std
    df['BB_Lower'] = df['BB_Mid'] - 2 * bb_std
    df['BB_PctB'] = (close - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])

    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    df['MACD_Class'] = 'NEUTRAL'
    df.loc[(df['MACD'] > df['MACD_Signal']) & (df['MACD_Hist'] > df['MACD_Hist'].shift()), 'MACD_Class'] = 'S_BULL'
    df.loc[(df['MACD'] > df['MACD_Signal']) & (df['MACD_Hist'] <= df['MACD_Hist'].shift()), 'MACD_Class'] = 'BULL'
    df.loc[(df['MACD'] < df['MACD_Signal']) & (df['MACD_Hist'] < df['MACD_Hist'].shift()), 'MACD_Class'] = 'S_BEAR'
    df.loc[(df['MACD'] < df['MACD_Signal']) & (df['MACD_Hist'] >= df['MACD_Hist'].shift()), 'MACD_Class'] = 'BEAR'

    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    plus_dm[plus_dm < minus_dm] = 0
    minus_dm[minus_dm < plus_dm] = 0
    atr_smooth = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_smooth.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_smooth.replace(0, np.nan))
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
    df['ADX'] = dx.rolling(14).mean()

    df['AvgVol14'] = volume.rolling(14).mean()
    return df

def calculate_score(row, prev_row):
    price = row['Close']
    rsi = row.get('RSI', 50)
    ma200 = row.get('MA200', price)
    ma50 = row.get('MA50', price)
    prev_close = prev_row['Close'] if prev_row is not None else price
    bb_pct_b = row.get('BB_PctB', 0.5)
    macd_class = row.get('MACD_Class', 'NEUTRAL')
    adx = row.get('ADX', 0)
    volume = row.get('Volume', 0)
    avg_vol = row.get('AvgVol14', 0)

    trend_score = 3 if price > ma200 else (1 if price > prev_close else 0)
    dip_points = trend_score
    if rsi < 25: dip_points += 4
    elif rsi < 30: dip_points += 3
    elif rsi < 40: dip_points += 2
    if bb_pct_b < 0: dip_points += 3
    elif bb_pct_b < 0.1: dip_points += 2
    elif bb_pct_b < 0.2: dip_points += 1

    mom_points = 0
    if 'S_BULL' in macd_class: mom_points += 3
    elif 'BULL' in macd_class: mom_points += 2
    if price > ma50:
        if adx > 25: mom_points += 1
        if adx > 35: mom_points += 1
    if avg_vol > 0 and volume > avg_vol: mom_points += 1
    if avg_vol > 0 and volume > avg_vol * 1.5: mom_points += 1
    if 50 <= rsi <= 70: mom_points += 3
    elif 40 <= rsi <= 50: mom_points += 1

    if dip_points >= mom_points:
        return min(12, max(0, dip_points)), "DIP", dip_points
    else:
        return min(12, max(0, mom_points)), "MOMENTUM", mom_points

def run_backtest_with_params(symbol, config, data, params):
    profit_target = config["profit_target"]
    max_amount = config["max_amount"]
    
    ATR_MUL = params['atr_mul']
    STOP_MUL = params['stop_mul']
    MAX_STOP = params['max_stop']
    RSI_EXIT = params['rsi_exit']
    PROT_ACT = params['prot_act']
    PROT_DROP = params['prot_drop']
    DIP_TH = params['dip_th']
    MOM_TH = params['mom_th']
    # Option 4: minimum raw base technical score required before analyst bonus can trigger a buy
    DIP_BASE_MIN = params.get('dip_base_min', 5)   # DIP: RSI+BB+Trend must be >= 5
    MOM_BASE_MIN = params.get('mom_base_min', 6)   # MOM: MACD+ADX+Vol+RSI must be >= 6
    DAILY_CHANGE_CAP = params.get('daily_change_cap', 0.05) # None or float (e.g. 0.05 for 5%)
    DAILY_CHANGE_MIN = params.get('daily_change_min', None) # None or float (e.g. -0.05 for -5%)
    
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

        score, strategy, base_score = calculate_score(row, prev_row)
        max_stop_cap = 7.0 if strategy == "DIP" else 9.0

        if atr > 0 and price > 0:
            atr_pct = (atr / price) * 100
            dynamic_profit_target = max(profit_target, min(ATR_MUL * atr_pct, 15.0)) / 100
            dynamic_stop_loss = -max(abs(3.0), min(STOP_MUL * atr_pct, max_stop_cap))
        else:
            dynamic_profit_target = profit_target / 100
            dynamic_stop_loss = -5.0

        # Dynamic Sizing Calculation
        global_acc = 20000
        risk_euro = global_acc * 0.01
        stop_loss_dist = abs(dynamic_stop_loss) / 100.0
        if stop_loss_dist < 0.01: stop_loss_dist = 0.01
        
        dyn_max = risk_euro / stop_loss_dist
        
        is_etf = symbol in ["EGLN.L", "ESE.PA"]
        max_cap_pct = 0.35 if is_etf else 0.18
        cap_limit = global_acc * max_cap_pct
        
        if dyn_max > cap_limit:
            dyn_max = cap_limit

        if position is not None:
            pnl_pct = ((price - position['buy_price']) / position['buy_price']) * 100
            if pnl_pct > position['highest_pnl']: position['highest_pnl'] = pnl_pct

            sell_reason = None
            if position['highest_pnl'] >= (dynamic_profit_target * 100):
                trail = max(0.5, min((atr / price) * 50, 1.5)) if price > 0 else 0.5
                if pnl_pct <= position['highest_pnl'] - trail: sell_reason = "Trailing"
            elif position['highest_pnl'] >= PROT_ACT:
                if pnl_pct <= position['highest_pnl'] - (position['highest_pnl'] * PROT_DROP): sell_reason = "Protective"
            
            if not sell_reason and pnl_pct <= dynamic_stop_loss: sell_reason = "Stop"
            if not sell_reason and rsi >= RSI_EXIT and pnl_pct > 1.0: sell_reason = "RSI"
            
            macd_class = row.get('MACD_Class', 'NEUTRAL')
            if not sell_reason and macd_class in ('S_BEAR', 'BEAR') and prev_macd_class in ('S_BULL', 'BULL') and pnl_pct > 1.0:
                sell_reason = "MACD"
            prev_macd_class = macd_class

            if sell_reason:
                trades.append({
                    'pnl_pct': pnl_pct, 
                    'pnl_eur': position['qty'] * (price - position['buy_price']), 
                    'sell_date': date,
                    'strategy': position.get('strategy', 'UNKNOWN'),
                    'sell_reason': sell_reason
                })
                last_sell_day = date
                position = None
            continue

        if last_buy_day and (date - last_buy_day).days < 1: continue
        if last_sell_day and (date - last_sell_day).days < 1: continue
        if prev_close > 0:
            chg = (price - prev_close) / prev_close
            if DAILY_CHANGE_CAP is not None and chg > DAILY_CHANGE_CAP: continue
            if DAILY_CHANGE_MIN is not None and chg < DAILY_CHANGE_MIN: continue
        if rsi >= 70: continue
        if i >= 3 and data.iloc[i - 3]['Close'] > 0 and (price - data.iloc[i - 3]['Close']) / data.iloc[i - 3]['Close'] > 0.15: continue

        score, strategy, base_score = calculate_score(row, prev_row)
        buy_signal = False
        if strategy == "DIP" and score >= DIP_TH and base_score >= DIP_BASE_MIN:
            if prev_close > 0:
                drop = (price - prev_close) / prev_close
                if drop > -0.07 and not (drop < -0.03 and rsi > 45): buy_signal = True
        if strategy == "MOMENTUM" and score >= MOM_TH and base_score >= MOM_BASE_MIN:
            if prev_close > 0:
                chg = (price - prev_close) / prev_close
                mom_ok = (DAILY_CHANGE_CAP is None or chg <= DAILY_CHANGE_CAP) and (DAILY_CHANGE_MIN is None or chg >= DAILY_CHANGE_MIN)
                if mom_ok and i >= 2 and data.iloc[i - 2]['Close'] > 0 and (prev_close - data.iloc[i - 2]['Close']) / data.iloc[i - 2]['Close'] <= 0.15:
                    buy_signal = True

        if buy_signal:
            # Use dyn_max instead of max_amount
            qty = max(1, int(dyn_max / price))
            position = {'qty': qty, 'buy_price': price, 'highest_pnl': 0.0, 'strategy': strategy}
            last_buy_day = date
            
    return trades

if __name__ == "__main__":
    cached_data = {}
    for s in STOCKS:
        df = yf.Ticker(s).history(period="2y", interval="1d", auto_adjust=False, actions=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        cached_data[s] = compute_indicators(df)
    
    grids = [
        # Fine-tune 3: The best current configuration
        {'atr_mul': 1.5, 'stop_mul': 2.3, 'max_stop': -12.0, 'rsi_exit': 80, 'prot_act': 5.0, 'prot_drop': 0.25, 'dip_th': 7, 'mom_th': 8},
    ]

    for p in grids:
        trades = []
        stock_stats = {}
        for s, c in STOCKS.items():
            stock_trades = run_backtest_with_params(s, c, cached_data[s], p)
            trades.extend(stock_trades)
            stock_pnl = sum(t['pnl_eur'] for t in stock_trades)
            stock_wr = len([t for t in stock_trades if t['pnl_pct'] > 0]) / len(stock_trades) if stock_trades else 0
            stock_stats[s] = {'pnl': stock_pnl, 'wr': stock_wr, 'trades': len(stock_trades)}
            
        pnl = sum(t['pnl_eur'] for t in trades)
        wr = len([t for t in trades if t['pnl_pct'] > 0]) / len(trades) if trades else 0
        print(f"Total PnL: {pnl:+8.0f} | WR: {wr*100:4.1f}% | Trades: {len(trades):3d} | {p}")
        print("\n--- PER STOCK BREAKDOWN ---")
        for s, stat in sorted(stock_stats.items(), key=lambda item: item[1]['pnl'], reverse=True):
            print(f"{s:8s}: PnL: {stat['pnl']:+7.0f} | WR: {stat['wr']*100:5.1f}% | Trades: {stat['trades']:2d}")
