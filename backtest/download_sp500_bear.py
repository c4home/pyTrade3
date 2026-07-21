import yfinance as yf
import pandas as pd
import numpy as np
import ssl
import pickle
import concurrent.futures
import warnings
import os
import requests
import io

warnings.filterwarnings('ignore')

def compute_indicators(df):
    if len(df) < 200:
        return None
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

def download_and_process(ticker):
    try:
        # Fetching 2021-2022 to give warmup for moving averages, and test 2022
        df = yf.Ticker(ticker).history(start="2021-01-01", end="2023-01-01", auto_adjust=False, actions=False)
        if df.empty or len(df) < 200:
            return ticker, None
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.droplevel(1)
        df_processed = compute_indicators(df)
        print(f"[{ticker}] Processed successfully.")
        return ticker, df_processed
    except Exception as e:
        print(f"[{ticker}] Failed: {e}")
        return ticker, None

if __name__ == "__main__":
    print("Fetching S&P 500 list...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
    sp500 = pd.read_html(io.StringIO(response.text))[0]
    tickers = sp500['Symbol'].tolist()
    tickers = [t.replace('.', '-') for t in tickers]

    print(f"Found {len(tickers)} tickers. Starting 2021-2022 download...")
    
    cached_data = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(download_and_process, t): t for t in tickers}
        for future in concurrent.futures.as_completed(futures):
            ticker, df = future.result()
            if df is not None:
                cached_data[ticker] = df

    print(f"Successfully processed {len(cached_data)} stocks.")
    
    cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sp500_data_bear.pkl")
    with open(cache_path, 'wb') as f:
        pickle.dump(cached_data, f)
    
    print(f"Bear Market data cached to {cache_path}")
