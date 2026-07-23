import yfinance as yf
import pandas as pd

ticker = yf.Ticker("AAPL")
info = ticker.info

print("Current Price:", info.get('currentPrice'))
print("Target Mean Price:", info.get('targetMeanPrice'))
print("Target High Price:", info.get('targetHighPrice'))
print("Target Low Price:", info.get('targetLowPrice'))

try:
    sp500_table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    df = sp500_table[0]
    tickers = df['Symbol'].tolist()
    print("S&P 500 count:", len(tickers))
    print("Sample:", tickers[:5])
except Exception as e:
    print("Error fetching SP500:", e)
