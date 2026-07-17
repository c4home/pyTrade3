"""
Backtest of pyTrade3 trading algorithm.
Simulates the full buy/sell logic over the past year using daily OHLCV data from yfinance.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ── STOCK CONFIGURATION (from database) ──
STOCKS = {
    "AAPL":   {"max_amount": 1000, "profit_target": 2.0, "drop_threshold": 5.0},
    "ABT":    {"max_amount": 1500, "profit_target": 5.0, "drop_threshold": 5.0},
    "AIR.PA": {"max_amount": 1000, "profit_target": 3.0, "drop_threshold": 5.0},
    "AMD":    {"max_amount": 2000, "profit_target": 2.0, "drop_threshold": 5.0},
    "AMZN":   {"max_amount": 2000, "profit_target": 2.0, "drop_threshold": 5.0},
    "ARM":    {"max_amount": 2000, "profit_target": 3.0, "drop_threshold": 5.0},
    "ASML":   {"max_amount": 3000, "profit_target": 3.0, "drop_threshold": 5.0},
    "AVGO":   {"max_amount": 1000, "profit_target": 5.0, "drop_threshold": 5.0},
    "BARC.L": {"max_amount": 1000, "profit_target": 3.0, "drop_threshold": 5.0},
    "EGLN.L": {"max_amount": 5500, "profit_target": 2.0, "drop_threshold": 5.0},
    "ESE.PA": {"max_amount": 7500, "profit_target": 2.0, "drop_threshold": 5.0},
    "GOOG":   {"max_amount": 2000, "profit_target": 2.0, "drop_threshold": 5.0},
    "HO.PA":  {"max_amount": 1000, "profit_target": 3.0, "drop_threshold": 5.0},
    "INTC":   {"max_amount": 1000, "profit_target": 5.0, "drop_threshold": 5.0},
    "JPM":    {"max_amount": 1000, "profit_target": 5.0, "drop_threshold": 5.0},
    "MRNA":   {"max_amount": 1000, "profit_target": 3.0, "drop_threshold": 5.0},
    "MSFT":   {"max_amount": 2000, "profit_target": 2.0, "drop_threshold": 5.0},
    "MU":     {"max_amount": 1000, "profit_target": 3.0, "drop_threshold": 5.0},
    "NVDA":   {"max_amount": 1000, "profit_target": 3.0, "drop_threshold": 5.0},
    "ORCL":   {"max_amount": 1000, "profit_target": 5.0, "drop_threshold": 5.0},
    "QCOM":   {"max_amount": 1000, "profit_target": 2.0, "drop_threshold": 5.0},
    "SAF.PA": {"max_amount": 1000, "profit_target": 5.0, "drop_threshold": 5.0},
    "TSLA":   {"max_amount": 3000, "profit_target": 3.0, "drop_threshold": 5.0},
    "TSM":    {"max_amount": 2000, "profit_target": 3.0, "drop_threshold": 5.0},
}

# ── ALGORITHM PARAMETERS ──
ATR_MULTIPLIER = 1.5
MIN_PROFIT_PCT = None  # Per stock
MAX_PROFIT_PCT = 15.0
STOP_MULTIPLIER = 2.5
MAX_STOP_LOSS = -15.0
MIN_STOP_LOSS = -3.0
BUY_COOLDOWN_DAYS = 1   # 24 hours
SELL_COOLDOWN_DAYS = 1
INITIAL_CASH = 50000.0
MIN_CASH = 5000.0

# ── TECHNICAL INDICATOR CALCULATIONS ──
def compute_indicators(df):
    """Compute all technical indicators needed by the algorithm."""
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']

    # ATR (14)
    tr0 = abs(high - low)
    tr1 = abs(high - close.shift())
    tr2 = abs(low - close.shift())
    tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
    df['ATR14'] = tr.rolling(14).mean()

    # RSI (14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))

    # Moving Averages
    df['MA20'] = close.rolling(20).mean()
    df['MA50'] = close.rolling(50).mean()
    df['MA200'] = close.rolling(200).mean()

    # Bollinger Bands (20, 2)
    df['BB_Mid'] = df['MA20']
    bb_std = close.rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + 2 * bb_std
    df['BB_Lower'] = df['BB_Mid'] - 2 * bb_std
    df['BB_PctB'] = (close - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])

    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    # Classify MACD signal
    df['MACD_Class'] = 'NEUTRAL'
    df.loc[(df['MACD'] > df['MACD_Signal']) & (df['MACD_Hist'] > df['MACD_Hist'].shift()), 'MACD_Class'] = 'S_BULL'
    df.loc[(df['MACD'] > df['MACD_Signal']) & (df['MACD_Hist'] <= df['MACD_Hist'].shift()), 'MACD_Class'] = 'BULL'
    df.loc[(df['MACD'] < df['MACD_Signal']) & (df['MACD_Hist'] < df['MACD_Hist'].shift()), 'MACD_Class'] = 'S_BEAR'
    df.loc[(df['MACD'] < df['MACD_Signal']) & (df['MACD_Hist'] >= df['MACD_Hist'].shift()), 'MACD_Class'] = 'BEAR'

    # ADX (14)
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    # Zero out when opposite is larger
    plus_dm[plus_dm < minus_dm] = 0
    minus_dm[minus_dm < plus_dm] = 0
    atr_smooth = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_smooth.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_smooth.replace(0, np.nan))
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
    df['ADX'] = dx.rolling(14).mean()

    # Volume average
    df['AvgVol14'] = volume.rolling(14).mean()

    # 14-day High/Low
    df['High14'] = high.rolling(14).max()
    df['Low14'] = low.rolling(14).min()

    return df


def calculate_score(row, prev_row):
    """Replicate the smart score calculation. Returns (score, strategy)."""
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

    # Trend score
    trend_score = 0
    if price > ma200:
        trend_score = 3
    elif price > prev_close:
        trend_score = 1

    # DIP strategy
    dip_points = 0
    if rsi < 25: dip_points += 4
    elif rsi < 30: dip_points += 3
    elif rsi < 40: dip_points += 2

    if bb_pct_b < 0: dip_points += 3
    elif bb_pct_b < 0.1: dip_points += 2
    elif bb_pct_b < 0.2: dip_points += 1

    dip_points += trend_score

    # MOMENTUM strategy
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
        return min(12, max(0, dip_points)), "DIP"
    else:
        return min(12, max(0, mom_points)), "MOMENTUM"


def run_backtest(symbol, config, data):
    """Run backtest for a single stock."""
    profit_target = config["profit_target"]
    max_amount = config["max_amount"]

    trades = []
    position = None  # {'qty': int, 'buy_price': float, 'buy_date': date, 'highest_pnl': float}
    last_buy_day = None
    last_sell_day = None
    prev_macd_class = 'NEUTRAL'

    for i in range(200, len(data)):  # Start after 200 days for MA200
        row = data.iloc[i]
        prev_row = data.iloc[i - 1]
        date = data.index[i]
        price = row['Close']
        atr = row.get('ATR14', 1.0)
        rsi = row.get('RSI', 50)
        prev_close = prev_row['Close']

        if pd.isna(price) or price <= 0:
            continue

        # Dynamic profit target
        if atr > 0 and price > 0:
            atr_pct = (atr / price) * 100
            dynamic_profit_target = max(profit_target, min(ATR_MULTIPLIER * atr_pct, MAX_PROFIT_PCT)) / 100
            # Dynamic stop loss
            raw_stop_pct = STOP_MULTIPLIER * atr_pct
            dynamic_stop_loss = -max(abs(MIN_STOP_LOSS), min(raw_stop_pct, abs(MAX_STOP_LOSS)))
        else:
            dynamic_profit_target = profit_target / 100
            dynamic_stop_loss = -5.0

        # ── SELL LOGIC ──
        if position is not None:
            pnl_pct = ((price - position['buy_price']) / position['buy_price']) * 100
            if pnl_pct > position['highest_pnl']:
                position['highest_pnl'] = pnl_pct

            sell_reason = None

            # 1. Dynamic ATR Trailing Profit Lock
            profit_target_pct = dynamic_profit_target * 100
            current_atr_pct = (atr / price) * 100 if price > 0 else 0
            dynamic_trail_drop = max(1.0, min(current_atr_pct * 1.0, 3.0))

            if position['highest_pnl'] >= profit_target_pct:
                trail_activation = position['highest_pnl'] - dynamic_trail_drop
                if pnl_pct <= trail_activation:
                    sell_reason = f"Trailing Profit (Peak:{position['highest_pnl']:.1f}%)"

            # 1.5 Proportional Protective Trailing Stop (>= 5%)
            elif position['highest_pnl'] >= 5.0:
                protective_trail_drop = position['highest_pnl'] * 0.5
                protective_floor = position['highest_pnl'] - protective_trail_drop
                if pnl_pct <= protective_floor:
                    sell_reason = f"Protective Stop (Peak:{position['highest_pnl']:.1f}%)"

            # 2. Dynamic Stop Loss
            if sell_reason is None and pnl_pct <= dynamic_stop_loss:
                sell_reason = f"Stop Loss ({dynamic_stop_loss:.1f}%)"

            # 3. RSI Overbought Exit
            if sell_reason is None and rsi >= 80 and pnl_pct > 1.0:
                sell_reason = f"RSI Overbought ({rsi:.0f})"

            # 4. MACD Bearish Crossover
            macd_class = row.get('MACD_Class', 'NEUTRAL')
            if sell_reason is None:
                if macd_class in ('S_BEAR', 'BEAR') and prev_macd_class in ('S_BULL', 'BULL') and pnl_pct > 1.0:
                    sell_reason = f"MACD Bearish ({prev_macd_class}→{macd_class})"

            prev_macd_class = macd_class

            if sell_reason:
                trades.append({
                    'symbol': symbol,
                    'buy_date': position['buy_date'],
                    'buy_price': position['buy_price'],
                    'sell_date': date,
                    'sell_price': price,
                    'qty': position['qty'],
                    'pnl_pct': pnl_pct,
                    'pnl_eur': position['qty'] * (price - position['buy_price']),
                    'hold_days': (date - position['buy_date']).days,
                    'reason': sell_reason,
                    'peak_pnl': position['highest_pnl'],
                })
                last_sell_day = date
                position = None
            continue  # Don't buy on the same day we're evaluating a sell

        # ── BUY LOGIC ──
        if position is not None:
            continue

        # Cooldown check
        if last_buy_day and (date - last_buy_day).days < BUY_COOLDOWN_DAYS:
            continue
        if last_sell_day and (date - last_sell_day).days < SELL_COOLDOWN_DAYS:
            continue

        # Daily growth check (block if > 5% rise)
        if prev_close > 0:
            daily_change = (price - prev_close) / prev_close
            if daily_change > 0.05:
                continue

        # RSI Overbought check
        if rsi >= 70:
            continue

        # 3-day cumulative rise check
        if i >= 3:
            close_3d_ago = data.iloc[i - 3]['Close']
            if close_3d_ago > 0:
                three_day_change = (price - close_3d_ago) / close_3d_ago
                if three_day_change > 0.15:
                    continue

        # Calculate score
        score, strategy = calculate_score(row, prev_row)

        buy_signal = False

        # DIP strategy
        if strategy == "DIP" and score >= 7:
            if prev_close > 0:
                daily_drop = (price - prev_close) / prev_close
                if daily_drop < -0.07:
                    continue  # Too extreme
                if daily_drop < -0.03 and rsi > 45:
                    continue  # Falling knife
            buy_signal = True

        # MOMENTUM strategy
        if strategy == "MOMENTUM" and score >= 8:
            if prev_close > 0:
                daily_change = (price - prev_close) / prev_close
                if daily_change > 0.05:
                    continue
            if i >= 2:
                yest_close = data.iloc[i - 2]['Close']
                if yest_close > 0:
                    yesterday_change = (prev_close - yest_close) / yest_close
                    if yesterday_change > 0.15:
                        continue
            if rsi > 70:
                continue
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

    # Close any remaining position at last price
    if position is not None:
        last_price = data['Close'].iloc[-1]
        pnl_pct = ((last_price - position['buy_price']) / position['buy_price']) * 100
        trades.append({
            'symbol': symbol,
            'buy_date': position['buy_date'],
            'buy_price': position['buy_price'],
            'sell_date': data.index[-1],
            'sell_price': last_price,
            'qty': position['qty'],
            'pnl_pct': pnl_pct,
            'pnl_eur': position['qty'] * (last_price - position['buy_price']),
            'hold_days': (data.index[-1] - position['buy_date']).days,
            'reason': 'STILL OPEN',
            'peak_pnl': position['highest_pnl'],
        })

    return trades


# ── MAIN ──
if __name__ == "__main__":
    print("=" * 80)
    print("  pyTrade3 BACKTEST — Full Algorithm Simulation (1 Year)")
    print("=" * 80)
    print()

    all_trades = []
    stock_summaries = []

    for symbol, config in STOCKS.items():
        print(f"  Downloading {symbol}...", end=" ", flush=True)
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="2y", interval="1d", auto_adjust=False, actions=False)
            if data.empty or len(data) < 250:
                print(f"SKIP (only {len(data)} rows)")
                continue

            # Handle MultiIndex columns
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(1)

            data = compute_indicators(data)
            trades = run_backtest(symbol, config, data)

            if trades:
                total_pnl = sum(t['pnl_eur'] for t in trades)
                win_trades = [t for t in trades if t['pnl_pct'] > 0]
                loss_trades = [t for t in trades if t['pnl_pct'] <= 0]
                avg_pnl = np.mean([t['pnl_pct'] for t in trades])
                max_gain = max(t['pnl_pct'] for t in trades)
                max_loss = min(t['pnl_pct'] for t in trades)
                avg_hold = np.mean([t['hold_days'] for t in trades])

                stock_summaries.append({
                    'symbol': symbol,
                    'trades': len(trades),
                    'wins': len(win_trades),
                    'losses': len(loss_trades),
                    'win_rate': len(win_trades) / len(trades) * 100,
                    'total_pnl': total_pnl,
                    'avg_pnl_pct': avg_pnl,
                    'max_gain': max_gain,
                    'max_loss': max_loss,
                    'avg_hold_days': avg_hold,
                })
                all_trades.extend(trades)
                status = f"✅ {len(trades)} trades, PnL: €{total_pnl:+,.0f}"
            else:
                stock_summaries.append({
                    'symbol': symbol, 'trades': 0, 'wins': 0, 'losses': 0,
                    'win_rate': 0, 'total_pnl': 0, 'avg_pnl_pct': 0,
                    'max_gain': 0, 'max_loss': 0, 'avg_hold_days': 0,
                })
                status = "⚪ No trades"
            print(status)
        except Exception as e:
            print(f"❌ Error: {e}")

    # ── PRINT RESULTS ──
    print()
    print("=" * 80)
    print("  PER-STOCK SUMMARY")
    print("=" * 80)
    print(f"{'Symbol':<10} {'Trades':>6} {'Wins':>5} {'Loss':>5} {'Win%':>6} {'Total PnL':>12} {'Avg%':>7} {'MaxGain':>8} {'MaxLoss':>8} {'AvgHold':>8}")
    print("-" * 80)

    stock_summaries.sort(key=lambda x: x['total_pnl'], reverse=True)
    for s in stock_summaries:
        print(f"{s['symbol']:<10} {s['trades']:>6} {s['wins']:>5} {s['losses']:>5} {s['win_rate']:>5.0f}% {s['total_pnl']:>+11,.0f} {s['avg_pnl_pct']:>+6.1f}% {s['max_gain']:>+7.1f}% {s['max_loss']:>+7.1f}% {s['avg_hold_days']:>6.0f}d")

    # ── OVERALL ──
    if all_trades:
        print()
        print("=" * 80)
        print("  PORTFOLIO SUMMARY")
        print("=" * 80)
        total_pnl = sum(t['pnl_eur'] for t in all_trades)
        win_trades = [t for t in all_trades if t['pnl_pct'] > 0]
        loss_trades = [t for t in all_trades if t['pnl_pct'] <= 0]
        avg_pnl = np.mean([t['pnl_pct'] for t in all_trades])

        print(f"  Total Trades   : {len(all_trades)}")
        print(f"  Winning Trades : {len(win_trades)} ({len(win_trades)/len(all_trades)*100:.0f}%)")
        print(f"  Losing Trades  : {len(loss_trades)} ({len(loss_trades)/len(all_trades)*100:.0f}%)")
        print(f"  Avg PnL/Trade  : {avg_pnl:+.2f}%")
        print(f"  Avg Hold Time  : {np.mean([t['hold_days'] for t in all_trades]):.0f} days")
        print(f"  Total PnL      : €{total_pnl:+,.2f}")
        print(f"  Return on {INITIAL_CASH:,.0f} : {total_pnl/INITIAL_CASH*100:+.1f}%")
        print()

        # Top 5 best and worst trades
        sorted_trades = sorted(all_trades, key=lambda t: t['pnl_pct'], reverse=True)
        print("  TOP 5 BEST TRADES:")
        for t in sorted_trades[:5]:
            buy_d = t['buy_date'].strftime('%m/%d') if hasattr(t['buy_date'], 'strftime') else str(t['buy_date'])[:10]
            sell_d = t['sell_date'].strftime('%m/%d') if hasattr(t['sell_date'], 'strftime') else str(t['sell_date'])[:10]
            print(f"    {t['symbol']:<8} {buy_d}→{sell_d}  {t['pnl_pct']:+.1f}%  €{t['pnl_eur']:+,.0f}  ({t['reason']})")

        print()
        print("  TOP 5 WORST TRADES:")
        for t in sorted_trades[-5:]:
            buy_d = t['buy_date'].strftime('%m/%d') if hasattr(t['buy_date'], 'strftime') else str(t['buy_date'])[:10]
            sell_d = t['sell_date'].strftime('%m/%d') if hasattr(t['sell_date'], 'strftime') else str(t['sell_date'])[:10]
            print(f"    {t['symbol']:<8} {buy_d}→{sell_d}  {t['pnl_pct']:+.1f}%  €{t['pnl_eur']:+,.0f}  ({t['reason']})")

        # Sell reason breakdown
        print()
        print("  SELL REASON BREAKDOWN:")
        reason_stats = {}
        for t in all_trades:
            key = t['reason'].split('(')[0].strip()
            if key not in reason_stats:
                reason_stats[key] = {'count': 0, 'total_pnl': 0, 'wins': 0}
            reason_stats[key]['count'] += 1
            reason_stats[key]['total_pnl'] += t['pnl_eur']
            if t['pnl_pct'] > 0:
                reason_stats[key]['wins'] += 1

        for reason, stats in sorted(reason_stats.items(), key=lambda x: x[1]['total_pnl'], reverse=True):
            wr = stats['wins'] / stats['count'] * 100 if stats['count'] > 0 else 0
            print(f"    {reason:<30} {stats['count']:>4} trades  WR:{wr:>4.0f}%  PnL: €{stats['total_pnl']:>+10,.0f}")

    print()
    print("=" * 80)
    print("  ⚠️  This backtest uses daily close prices only (no intraday simulation).")
    print("  ⚠️  No transaction costs, slippage, or exchange rates are included.")
    print("  ⚠️  Analyst targets & bank notes are NOT available in backtest.")
    print("=" * 80)
