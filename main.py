from dotenv import load_dotenv
import os
load_dotenv()
def _load_env_config():
    """Return a dict with all env vars the app needs."""
    return {
        "IBKR_HOST"        : os.getenv("IBKR_HOST"),
        "IBKR_PORT"        : os.getenv("IBKR_PORT"),
        "IBKR_CLIENT_ID"   : os.getenv("IBKR_CLIENT_ID"),
        "SMTP_SERVER"      : os.getenv("SMTP_SERVER"),
        "SMTP_PORT"        : os.getenv("SMTP_PORT"),
        "SENDER_EMAIL"     : os.getenv("SENDER_EMAIL"),
        "SENDER_EMAIL_PASS": os.getenv("SENDER_EMAIL_PASS"),
        "RECEIVER_EMAIL"   : os.getenv("RECEIVER_EMAIL"),
    }
ENV = _load_env_config()
from contextlib import contextmanager        
from email.mime.text import MIMEText
from locale import currency
import sys
import smtplib
import re
import time
import csv
import threading
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import yfinance as yf
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import sqlite3

import collections
from datetime import timedelta

from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=8)

import logging
# Configure logging at module level
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# File handler for persistent logs
file_handler = logging.FileHandler('trading_bot.log')
file_handler.setLevel(logging.DEBUG)

# Formatter with timestamp, level, and message
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

# ==================== DATABASE MANAGER ====================
class DatabaseManager:
    def __init__(self, db_path="trading_bot.db"):
        self.db_path = db_path
        self._local = threading.local()  # Thread-local storage for connections
        self._lock = threading.Lock()    # Lock for thread safety
        self.init_database()

    @property
    def connection(self):
        """Get or create thread-local connection"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            # Each thread gets its own connection
            self._local.conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=10.0  # Wait up to 10s if database is locked
            )
            # Enable WAL mode for better concurrent access
            self._local.conn.execute('PRAGMA journal_mode=WAL')
        return self._local.conn

    @contextmanager
    def get_cursor(self):
        """Context manager for database operations with automatic commit/rollback"""
        conn = self.connection
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

    def close(self):
        """Close the thread-local connection"""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def init_database(self):
        """Initialize database tables - only called once at startup"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    stock_id TEXT PRIMARY KEY,
                    max_amount REAL NOT NULL,
                    profit_target REAL NOT NULL,
                    drop_threshold REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trading_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (stock_id) REFERENCES stocks (stock_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS company_data (
                    symbol TEXT PRIMARY KEY,
                    company_name TEXT,
                    asset_type TEXT,
                    sector TEXT,
                    currency TEXT,
                    exchange_tz_name TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS latest_prices (
                    stock_id TEXT PRIMARY KEY,
                    price REAL NOT NULL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cached_indicators (
                    stock_id TEXT PRIMARY KEY,
                    high_14d REAL NOT NULL,
                    low_14d REAL NOT NULL,
                    rsi REAL NOT NULL,
                    ma_signal TEXT NOT NULL,
                    macd_signal TEXT NOT NULL,
                    next_earnings_date TEXT,
                    today_volume REAL NOT NULL,
                    avg_volume_14d REAL NOT NULL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for faster queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trading_history_stock_id ON trading_history(stock_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trading_history_timestamp ON trading_history(timestamp)")

    def get_company_info(self, symbol):
        """Get company information from cache or fetch from yfinance"""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT company_name, asset_type, sector, currency, exchange_tz_name FROM company_data WHERE symbol=?", 
                (symbol,)
            )
            row = cursor.fetchone()

        if row:
            return {
                "company_name": row[0],
                "asset_type": row[1],
                "sector": row[2],
                "currency": row[3],
                "exchange_tz_name": row[4]
            }

        # Not in cache, fetch from yfinance
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            quote_type = info.get('quoteType', '').upper()
            company_name = info.get('longName', info.get('shortName', symbol))

            if quote_type == "ETF":
                asset_type = "ETF"
            elif "ETC" in company_name or "Commodity" in company_name or "Trust" in company_name:
                asset_type = "ETC"
            elif quote_type == "EQUITY":
                asset_type = "STOCK"
            else:
                asset_type = "OTHER"

            if asset_type in ["ETC", "ETF"]:
                sector = info.get("sector", info.get("category", info.get('longName', 'N/A').split()[0]))
            elif asset_type == "STOCK":
                sector = info.get("industry", "N/A")
            else:
                sector = info.get("category", info.get('longName', 'N/A').split()[0])

            currency = info.get('currency', 'USD')
            exchange_tz_name = info.get('exchangeTimezoneName', 'Europe/Paris')

            # Save to cache
            with self.get_cursor() as cursor:
                cursor.execute(
                    "INSERT OR REPLACE INTO company_data (symbol, company_name, asset_type, sector, currency, exchange_tz_name) VALUES (?, ?, ?, ?, ?, ?)",
                    (symbol, company_name, asset_type, sector, currency, exchange_tz_name)
                )

            return {
                "company_name": company_name,
                "asset_type": asset_type,
                "sector": sector,
                "currency": currency,
                "exchange_tz_name": exchange_tz_name
            }
        except Exception as e:
            logger.error(f"Error fetching {symbol} info from yfinance: {e}")
            return {
                "company_name": symbol,
                "asset_type": "UNKNOWN",
                "sector": "N/A",
                "currency": "USD",
                "exchange_tz_name": "Europe/Paris"
            }

    def get_latest_price(self, stock_id):
        """Get latest cached price"""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT price, strftime('%s', fetched_at) FROM latest_prices WHERE stock_id=?", 
                (stock_id,)
            )
            row = cursor.fetchone()

        if row:
            return {"price": row[0], "fetched_at": int(row[1])}
        return None

    def update_latest_price(self, stock_id, price):
        """Update cached price"""
        with self.get_cursor() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO latest_prices (stock_id, price, fetched_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (stock_id, price)
            )

    def get_cached_indicators(self, stock_id):
        """Get cached technical indicators"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """SELECT high_14d, low_14d, rsi, ma_signal, macd_signal, next_earnings_date, 
                   today_volume, avg_volume_14d, strftime('%s', fetched_at) 
                   FROM cached_indicators WHERE stock_id=?""",
                (stock_id,)
            )
            row = cursor.fetchone()

        if row:
            return {
                "high_14d": row[0],
                "low_14d": row[1],
                "rsi": row[2],
                "ma_signal": row[3],
                "macd_signal": row[4],
                "next_earnings_date": row[5],
                "today_volume": row[6],
                "avg_volume_14d": row[7],
                "fetched_at": int(row[8])
            }
        return None

    def update_cached_indicators(self, stock_id, high_14d, low_14d, rsi,
                                  ma_signal, macd_signal, next_earnings_date,
                                  today_volume, avg_volume_14d):
        """Update cached technical indicators"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT OR REPLACE INTO cached_indicators
                   (stock_id, high_14d, low_14d, rsi, ma_signal, macd_signal,
                    next_earnings_date, today_volume, avg_volume_14d, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    stock_id,
                    float(high_14d or 0),
                    float(low_14d or 0),
                    float(rsi or 0),
                    str(ma_signal or ""),
                    str(macd_signal or ""),
                    str(next_earnings_date or ""),
                    float(today_volume or 0),
                    float(avg_volume_14d or 0),
                )
            )

    def add_stock(self, stock_id, max_amount, profit_target, drop_threshold):
        """Add or update stock in watchlist"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT OR REPLACE INTO stocks (stock_id, max_amount, profit_target, drop_threshold, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (stock_id, max_amount, profit_target, drop_threshold)
            )

    def get_all_stocks(self):
        """Get all stocks in watchlist"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT stock_id, max_amount, profit_target, drop_threshold FROM stocks")
            return cursor.fetchall()

    def remove_stock(self, stock_id):
        """Remove stock from watchlist"""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM stocks WHERE stock_id = ?", (stock_id,))

    def update_stock(self, stock_id, max_amount, profit_target, drop_threshold):
        """Update stock parameters"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """UPDATE stocks SET max_amount = ?, profit_target = ?, drop_threshold = ?, 
                   updated_at = CURRENT_TIMESTAMP WHERE stock_id = ?""",
                (max_amount, profit_target, drop_threshold, stock_id)
            )

    def log_trade(self, stock_id, action, quantity, price):
        """Log a trade to history"""
        with self.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO trading_history (stock_id, action, quantity, price) VALUES (?, ?, ?, ?)",
                (stock_id, action, quantity, price)
            )

    def log_trades_batch(self, trades):
        """
        Log multiple trades at once (batch operation)
        trades: list of tuples [(stock_id, action, quantity, price), ...]
        """
        with self.get_cursor() as cursor:
            cursor.executemany(
                "INSERT INTO trading_history (stock_id, action, quantity, price) VALUES (?, ?, ?, ?)",
                trades
            )

    def get_trade_history(self, stock_id=None, limit=100):
        """Get trade history, optionally filtered by stock_id"""
        with self.get_cursor() as cursor:
            if stock_id:
                cursor.execute(
                    "SELECT * FROM trading_history WHERE stock_id=? ORDER BY timestamp DESC LIMIT ?",
                    (stock_id, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM trading_history ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
            return cursor.fetchall()
        
    def get_last_trade_times(self, stock_id):
        with self.get_cursor() as cursor:
            # Get last BUY time
            cursor.execute("""
                SELECT timestamp FROM trading_history
                WHERE stock_id = ? AND action = 'Buy'
                ORDER BY timestamp DESC
                LIMIT 1
            """, (stock_id,))
            last_buy_row = cursor.fetchone()

            # Get last SELL time
            cursor.execute("""
                SELECT timestamp FROM trading_history
                WHERE stock_id = ? AND action = 'Sell'
                ORDER BY timestamp DESC
                LIMIT 1
            """, (stock_id,))
            last_sell_row = cursor.fetchone()

            # Convert timestamps to seconds since epoch
            last_buy_time = 0
            last_sell_time = 0

            if last_buy_row:
                try:
                    # Parse SQLite timestamp format: YYYY-MM-DD HH:MM:SS
                    dt = datetime.strptime(last_buy_row[0], '%Y-%m-%d %H:%M:%S')
                    last_buy_time = dt.timestamp()
                except Exception as e:
                    logger.error(f"Error parsing last buy time: {e}")

            if last_sell_row:
                try:
                    dt = datetime.strptime(last_sell_row[0], '%Y-%m-%d %H:%M:%S')
                    last_sell_time = dt.timestamp()
                except Exception as e:
                    logger.error(f"Error parsing last sell time: {e}")

            return last_buy_time, last_sell_time

# ==================== CSV MANAGER ====================
class CSVManager:
    def __init__(self, csv_filename="trading_orders_history.csv"):
        self.csv_filename = csv_filename
        self.init_csv()

    def init_csv(self):
        if not os.path.exists(self.csv_filename):
            with open(self.csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Order ID', 'Stock ID', 'Action', 'Quantity', 'Price',
                    'Currency', 'Total Value', 'Timestamp', 'Status', 'Reason'
                ])

    def save_order(self, order_id, stock_id, action, quantity, price, currency="USD", status="Pending", reason=""):
        try:
            total_value = quantity * price
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            reason_text = reason or "Manual"  # fallback if empty
            with open(self.csv_filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    order_id, stock_id, action, quantity, f"{price:.4f}",
                    currency, f"{total_value:.2f}", timestamp, status, reason_text
                ])
        except Exception as e:
            logger.error(f"[CSV ERROR] {e}")

    def update_order_status(self, order_id, status):
        """Update CSV status to FILLED/CANCELLED"""
        try:
            lines = []
            with open(self.csv_filename, 'r') as f:
                lines = f.readlines()
            with open(self.csv_filename, 'w') as f:
                for line in lines:
                    parts = line.strip().split(',')
                    if len(parts) > 0 and parts[0] == str(order_id):
                        parts[-1] = status
                        line = ','.join(parts) + '\n'
                    f.write(line)
        except Exception as e:
            logger.error(f"[CSV UPDATE ERROR] {e}")


# ==================== EXCHANGE RATE ====================
class ExchangeRateManager:
    def __init__(self):
        self.eur_usd_rate = 1.0
        self.last_update = 0
        self.update_interval = 3600

    def get_eur_usd_rate(self):
        now = time.time()
        if now - self.last_update < self.update_interval:
            return self.eur_usd_rate

        def fetch():
            try:
                import requests
                url = "https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X"
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    price = data['chart']['result'][0]['meta']['regularMarketPrice']
                    new_rate = round(float(price), 4)
                    if abs(new_rate - self.eur_usd_rate) > 0.1:  # actually changed
                        self.eur_usd_rate = new_rate
                        self.last_update = time.time()
            except Exception as e:
                pass 

        # ONLY submit fetch if cache expired
        if now - self.last_update >= self.update_interval:
            executor.submit(fetch)
    
        return self.eur_usd_rate

    def eur_to_native(self, eur_amount, currency):
        if currency.upper() == 'EUR':
            return eur_amount
        return eur_amount * self.get_eur_usd_rate()

    def get_currency_symbol(self, currency="USD"):
        """Return $ or € based on currency"""
        if currency.upper() == "EUR":
            return "€"
        return "$"

# ==================== IBKR API ====================
class IBApi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.next_order_id = None
        self.positions = {}
        self.order_status = {}
        self.connected_event = threading.Event()
        self.data_lock = threading.Lock()
        self.order_callbacks = {}
        self.currency_symbol = "$"
        
        # ---- CASH ----
        self.net_liquidation = 0.0
        self.total_cash = 0.0
        self.available_cash = 0.0 
        self.portfolio_value = 0.0  
        self.cash_ready_event = threading.Event()
        self.last_cash_fetch = 0
        self.cash_fetch_interval = 20      # seconds
        self.max_cash_cache_age = 10800

    def nextValidId(self, orderId: int):
        self.next_order_id = orderId
        self.connected_event.set()

    def get_next_order_id(self):
        if self.next_order_id is None:
            raise RuntimeError("Next order ID not received yet. Is TWS/IB Gateway connected?")
        current_id = self.next_order_id
        self.next_order_id += 1  # Increment for next use
        return current_id
    
    def error(self, reqId, errorCode, errorString):
        if errorCode in [2104, 2106, 2158, 502, 504]: return
        logger.error(f"Error {reqId}: {errorCode} - {errorString}")
        
    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
            with self.data_lock:
                if tag == "NetLiquidation":
                    self.net_liquidation = float(value)
                elif tag == "TotalCashValue":
                    self.total_cash = float(value)
                elif tag == "AvailableFunds":
                    self.available_cash = float(value)

    def accountSummaryEnd(self, reqId: int):
        with self.data_lock:
            self.portfolio_value = self.net_liquidation - self.total_cash
        self.cash_ready_event.set()

    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        with self.data_lock:
            key = contract.symbol
            self.positions[key] = {
                'symbol': contract.symbol,
                'position': int(position),
                'avgCost': avgCost,
                'account': account
            }

    def orderStatus(self, orderId: int, status: str, filled: float, remaining: float,
                    avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float,
                    clientId: int, whyHeld: str, mktCapPrice: float):
        with self.data_lock:
            self.order_status[orderId] = {
                'status': status,
                'filled': filled,
                'remaining': remaining,
                'avgFillPrice': avgFillPrice
            }
        if status in ['Filled', 'Cancelled', 'Inactive']:
            logger.info(f"Order {orderId} -> {status}")

            # Notify the bot about order completion
            if hasattr(self, 'order_callbacks') and orderId in self.order_callbacks:
                callback = self.order_callbacks[orderId]
                callback(orderId, status, filled, avgFillPrice)
                del self.order_callbacks[orderId]

# ==================== TRADING BOT ====================
class TradingBot:
    MIN_CASH_FOR_BUY = 500.0
    CASH_BUFFER_MULTIPLIER = 0.95
    STATUS_READY = "Ready"
    STATUS_RUNNING = "Running"
    STATUS_PAUSING = "Pausing"
    STATUS_WAITING_ORDER = "Waiting Order"
    STATUS_MARKET_CLOSED = "Market Closed" 
    PRIORITY_BUY_LIST = {
            "EGLN.L", "ESE.PA"
    }
    
    def __init__(self, ibapi, stock_id, max_amount, profit_target, drop_threshold,
                 db_manager=None, csv_manager=None, exchange_manager=None, app=None):
        self.ibapi = ibapi
        self.stock_id = stock_id
        self.ibkr_symbol = re.sub(r'\..*$', '', stock_id)
        self.max_amount = max_amount
        self.profit_target = profit_target / 100
        self.drop_threshold = drop_threshold / 100
        self.db_manager = db_manager
        self.csv_manager = csv_manager
        self.exchange_manager = exchange_manager
        self.app = app  # Reference to main app

        self.market_value = 0
        self.smart_score = 0
        self.bought_price = 0
        self.current_value = 0
        self.pnl_percent = 0
        self.quantity = 0
        self.last_quantity = 0  # Track for fill detection
        self.is_running = False
        self.is_pausing = False
        self.pending_order_id = None
        self.pending_order_time = None
        self.order_timeout = 300

        self.last_yf_fetch = 0
        self.yf_fetch_interval_open = 20
        self.yf_fetch_interval_closed = 3600  # 1 hour when closed
        
        self.last_indicators_fetch = 0
        self.indicators_interval_open = 300  # 5 min
        self.indicators_interval_closed = 10800  # 30 min

        self.company_name = "Loading..."
        self.fourteen_day_high = 0
        self.fourteen_day_low = 0
        self.cash_left = 0
        self.currency = "USD"
        self.currency_symbol = "$"
        self.exchange_tz_name = None

        self.rsi_value = 0
        self.rsi_signal = ""
        self.ma_signal = ""
        self.macd_signal = ""

        self.next_earnings_date = None
        
        self.last_sell_time = 0          
        self.last_buy_time = 0           
        self.sell_cooldown_hours = 10     # 10 hours no buy after sell
        self.buy_cooldown_hours = 10      # 10 hours between buys
        self.last_cooldown_warning_time = 0
        self.cooldown_warning_interval = 7200  # Log once per hour (in seconds)
        
         # ---- RAPID STOP-LOSS ----
        self.rapid_drop_percent = 6.5  # % drop threshold (customize)
        self.monitor_interval_sec = 60 # Check every 60s (customize)
        self.last_price = None         # For drop calc
        self.monitor_thread = None     # Background monitor

        self.asset_type = "UNKNOWN"
        self.sector = "N/A"

        self.today_volume = 0
        self.avg_volume_14d = 0

        self.create_yf_ticker()

    def create_yf_ticker(self):
        info_dict = self.db_manager.get_company_info(self.stock_id)
        self.company_name = info_dict["company_name"]
        self.asset_type = info_dict["asset_type"]
        self.sector = info_dict["sector"]
        self.currency = info_dict["currency"]
        self.currency_symbol = {"USD": "$", "EUR": "€"}.get(self.currency, "$")
        self.exchange_tz_name = info_dict["exchange_tz_name"]

        cached_price = self.db_manager.get_latest_price(self.stock_id)
        if cached_price:
            self.market_value = cached_price["price"]
            self.last_yf_fetch = cached_price["fetched_at"]
        else:
            self.last_yf_fetch = 0

        cached_ind = self.db_manager.get_cached_indicators(self.stock_id)
        if cached_ind:
            self.fourteen_day_high = cached_ind["high_14d"]
            self.fourteen_day_low = cached_ind["low_14d"]
            self.rsi_value = cached_ind["rsi"]
            self.ma_signal = cached_ind["ma_signal"]
            self.macd_signal = cached_ind["macd_signal"]
            self.next_earnings_date = cached_ind["next_earnings_date"]
            self.today_volume = cached_ind["today_volume"]
            self.avg_volume_14d = cached_ind["avg_volume_14d"]
            self.last_indicators_fetch = cached_ind["fetched_at"]
        else:
            self.last_indicators_fetch = 0
            
        last_buy, last_sell = self.db_manager.get_last_trade_times(self.stock_id)
        self.last_buy_time = last_buy
        self.last_sell_time = last_sell

        if last_buy > 0:
            hours_since_buy = (time.time() - last_buy) / 3600
            logger.info(f"{self.stock_id}: Last BUY was {hours_since_buy:.1f}h ago")

        if last_sell > 0:
            hours_since_sell = (time.time() - last_sell) / 3600
            logger.info(f"{self.stock_id}: Last SELL was {hours_since_sell:.1f}h ago")
            
    def is_market_open(self):
        try:
            tz = ZoneInfo(self.exchange_tz_name)
            now = datetime.now(tz)
            if now.weekday() >= 5:
                return False
            current_time = now.time()

            if 'America/New_York' in self.exchange_tz_name:
                market_open = dtime(9, 30)
                market_close = dtime(16, 0)
            else:
                market_open = dtime(9, 0)
                market_close = dtime(17, 30)

            return market_open <= current_time <= market_close
        except:
            return False

    def calculate_rsi(self, data, period=14):
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if len(rsi) > 0 else 50

    def calculate_technical_indicators(self):
        now = time.time()
        interval = self.indicators_interval_open if self.is_market_open() else self.indicators_interval_closed
        if now - self.last_indicators_fetch < interval:
            return
        def fetch():
            try:
                ticker = yf.Ticker(self.stock_id)
                hist = ticker.history(period="100d")  # Increased to 100d for better MA50/200
                if len(hist) < 60:
                    return

                close = hist['Close']
                high = hist['High']
                low = hist['Low']
                volume = hist['Volume']

                # === 14-day high/low ===
                self.fourteen_day_high = round(high[-14:].max(), 2)
                self.fourteen_day_low = round(low[-14:].min(), 2)

                # === RSI ===
                delta = close.diff()
                gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
                rs = gain / loss.replace(0, np.nan)  # avoid div by zero
                rsi_series = 100 - (100 / (1 + rs))
                self.rsi_value = round(rsi_series.iloc[-1], 0) if not rsi_series.empty else 50

                # === MOVING AVERAGES - 3 STATES ===
                ma20 = close.rolling(20).mean().iloc[-1]
                ma50 = close.rolling(50).mean().iloc[-1]
                ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else ma50

                price = close.iloc[-1]

                # MA Trend: Bull / Neutral / Bear
                if price > ma20 > ma50 > ma200:
                    self.ma_signal = "STRONG_BULL"
                elif price > ma20 and ma20 > ma50:
                    self.ma_signal = "BULL"
                elif price > ma50:
                    self.ma_signal = "NEUTRAL_BULL"
                elif price < ma20 and ma20 < ma50:
                    self.ma_signal = "BEAR"
                elif price < ma50:
                    self.ma_signal = "NEUTRAL_BEAR"
                else:
                    self.ma_signal = "NEUTRAL"

                # === MACD - 3 STATES ===
                exp1 = close.ewm(span=12, adjust=False).mean()
                exp2 = close.ewm(span=26, adjust=False).mean()
                macd_line = exp1 - exp2
                signal_line = macd_line.ewm(span=9, adjust=False).mean()
                histogram = macd_line - signal_line

                macd_current = macd_line.iloc[-1]
                signal_current = signal_line.iloc[-1]
                hist_current = histogram.iloc[-1]

                if macd_current > signal_current and hist_current > 0 and hist_current > histogram.iloc[-2]:
                    self.macd_signal = "STRONG_BULL"     # bullish crossover + rising histogram
                elif macd_current > signal_current:
                    self.macd_signal = "BULL"
                elif abs(macd_current - signal_current) < (close.iloc[-1] * 0.001):  # very close
                    self.macd_signal = "NEUTRAL"
                elif macd_current < signal_current and hist_current < 0 and hist_current < histogram.iloc[-2]:
                    self.macd_signal = "STRONG_BEAR"
                else:
                    self.macd_signal = "BEAR"

                # === Volume ===
                self.today_volume = volume.iloc[-1]
                self.avg_volume_14d = volume[-14:].mean()

                # === Earnings/Dividends ===
                self.next_earnings_date = self.fetch_next_event_date(ticker)

                # Save to DB
                self.db_manager.update_cached_indicators(
                    self.stock_id, self.fourteen_day_high, self.fourteen_day_low,
                    self.rsi_value, self.ma_signal, self.macd_signal,
                    self.next_earnings_date, self.today_volume, self.avg_volume_14d
                )
                self.last_indicators_fetch = time.time()

            except Exception as e:
                logger.error(f"Error fetching indicators for {self.stock_id}: {e}")
        executor.submit(fetch)
        
    def get_ma200(self):
        """
        Get 200-day Simple Moving Average.
        Cached for performance.
        """
        now = time.time()
        if hasattr(self, '_cached_ma200') and now - getattr(self, '_ma200_last_update', 0) < 1800:  # 30 min cache
            return self._cached_ma200

        try:
            ticker = yf.Ticker(self.stock_id)
            hist = ticker.history(period="300d")  # Need 300+ days for MA200
            if len(hist) < 200:
                # Not enough data → use MA50 as proxy
                ma200 = hist['Close'].rolling(50).mean().iloc[-1]
            else:
                ma200 = hist['Close'].rolling(200).mean().iloc[-1]

            self._cached_ma200 = float(ma200)
            self._ma200_last_update = now
            return float(ma200)

        except Exception as e:
            logger.error(f"MA200 fetch failed for {self.stock_id}: {e}")
            return self.market_value  # fallback to current price
        
    def get_atr_14(self):
        """
        Calculate 14-day Average True Range (ATR) in price units.
        Cached for performance — only recalculates when needed.
        """
        now = time.time()
        # Reuse cached value if recent (avoid recalculating every second)
        if hasattr(self, '_cached_atr_14') and now - self._atr_last_update < 300:
            return self._cached_atr_14

        try:
            ticker = yf.Ticker(self.stock_id)
            hist = ticker.history(period="60d")
            if len(hist) < 15:
                atr = 1.0  # fallback
            else:
                high = hist['High']
                low = hist['Low']
                close = hist['Close']

                tr0 = abs(high - low)
                tr1 = abs(high - close.shift())
                tr2 = abs(low - close.shift())
                tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
                atr = tr.rolling(14).mean().iloc[-1]

            # Cache result
            self._cached_atr_14 = float(atr)
            self._atr_last_update = now
            return float(atr)

        except Exception as e:
            logger.error(f"ATR fetch failed for {self.stock_id}: {e}")
            return 1.0  # safe fallback
        
    def fetch_next_event_date(self, ticker):
        # ---- 1. Earnings (only for stocks) --------------------------------
        if self.asset_type == "STOCK":
            try:
                ed = ticker.get_earnings_dates(limit=12)
                if ed is not None and not ed.empty:
                    now = pd.Timestamp.now(tz='UTC')
                    future = ed[ed.index > now]
                    if not future.empty:
                        return future.index.min().strftime("%Y-%m-%d")
            except Exception as e:
                logger.error(f"[EARNINGS] {self.stock_id}: {e}")

        # ---- 2. Dividends (ETFs / ETCs / fallback for stocks) -------------
        try:
            # yfinance returns a DataFrame:  index = ex-dividend date
            div = ticker.dividends
            if div is not None and not div.empty:
                # keep only future dates (today + later)
                now = pd.Timestamp.now(tz='UTC')
                future_div = div[div.index > now]
                if not future_div.empty:
                    # the *ex-dividend* date is the one that matters for the trader
                    return future_div.index.min().strftime("%Y-%m-%d")
        except Exception as e:
            logger.error(f"[DIVIDENDS] {self.stock_id}: {e}")

        # ---- 3. Nothing found --------------------------------------------
        return "No payment"

    def get_market_value(self):
        now = time.time()
        interval = self.yf_fetch_interval_open if self.is_market_open() else self.yf_fetch_interval_closed
        if now - self.last_yf_fetch < interval:
            return self.market_value
        def fetch():
            try:
                ticker = yf.Ticker(self.stock_id)
                hist = ticker.history(period="5d", interval="1m")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
                    with self.ibapi.data_lock:
                        self.market_value = round(price, 2)
                    self.last_yf_fetch = time.time()
                    self.db_manager.update_latest_price(self.stock_id, price)
            except:
                pass
        executor.submit(fetch)
        return self.market_value

    def update_position(self):
        with self.ibapi.data_lock:
            pos = self.ibapi.positions.get(self.ibkr_symbol, {})
            self.quantity = pos.get('position', 0)
            self.bought_price = pos.get('avgCost', 0)
            self.current_value = self.quantity * self.market_value if self.quantity > 0 else 0
            self.pnl_percent = ((self.market_value - self.bought_price) / self.bought_price * 100) if self.bought_price > 0 else 0

        # Calculate invested in EUR for THIS stock only
        if self.quantity > 0 and self.bought_price > 0:
            usd_invested = self.quantity * self.bought_price
            eur_rate = self.exchange_manager.get_eur_usd_rate()
            eur_invested = usd_invested / eur_rate if eur_rate > 0 else usd_invested  # Fallback if rate=0
        else:
            eur_invested = 0.0

        self.cash_left = self.max_amount - eur_invested
        if self.cash_left < 0:
            self.cash_left = 0.0

    def update_parameters(self, max_amount, profit_target, drop_threshold):
        self.max_amount = max_amount
        self.profit_target = profit_target / 100
        self.drop_threshold = drop_threshold / 100

    def has_pending_order(self):
        if not self.pending_order_id:
            return False

        # Timeout after 5 minutes
        if time.time() - self.pending_order_time > 300:
            logger.warning(f"[{self.stock_id}] Order {self.pending_order_id} TIMED OUT")
            self.pending_order_id = None
            return False

        # Check if filled via position change
        old_qty = self.last_quantity
        self.update_position()
        if self.quantity > old_qty:
            logger.info(f"[{self.stock_id}] ORDER FILLED! {old_qty} -> {self.quantity}")
            if self.csv_manager and self.app:
                self.csv_manager.update_order_status(self.pending_order_id, "FILLED")
            self.last_quantity = self.quantity
            self.pending_order_id = None
            return False

        return True
    
    def _on_order_completed(self, order_id, status, action, quantity, price, filled, avg_fill_price, currency, reason):
        logger.info(f"[{self.stock_id}] Order {order_id} completed with status: {status}")

        if status == "Filled":
            # Only log to database if FILLED
            if self.db_manager:
                actual_price = avg_fill_price if avg_fill_price > 0 else price
                self.db_manager.log_trade(self.stock_id, action, int(filled), actual_price)
                logger.info(f"Logged to database: {action} {int(filled)} @ {actual_price:.2f}")

            # Only send email if FILLED
            if self.app:
                actual_price = avg_fill_price if avg_fill_price > 0 else price
                self.app.send_trade_email(
                    symbol=self.stock_id,
                    action=action,
                    quantity=int(filled),
                    price=actual_price,
                    native_currency=currency,
                    reason=reason,
                    bot=self
                )
                logger.info(f"Email sent: {action} {int(filled)} @ {actual_price:.2f}")

            # Update CSV status to FILLED
            if self.csv_manager:
                self.csv_manager.update_order_status(order_id, "FILLED")

            # Update last trade time
            if action == "BUY":
                self.last_buy_time = time.time()
            elif action == "SELL":
                self.last_sell_time = time.time()

        elif status == "Cancelled":
            logger.warning(f"Order {order_id} was cancelled")
            if self.csv_manager:
                self.csv_manager.update_order_status(order_id, "CANCELLED")

        elif status == "Inactive":
            logger.error(f"Order {order_id} rejected/inactive")
            if self.csv_manager:
                self.csv_manager.update_order_status(order_id, "REJECTED")

        # Clear pending order
        if self.pending_order_id == order_id:
            self.pending_order_id = None

    def get_native_currency_and_exchange(self):
        """Return (currency, primaryExchange) based on symbol suffix"""
        symbol = self.stock_id.upper()

        if symbol.endswith(".L"):
            return "EUR", "LSE"          # London
        elif symbol.endswith(".PA"):
            return "EUR", "SBF"          # Paris
        elif symbol.endswith(".AS"):
            return "EUR", "EURONEXT"     # Amsterdam
        elif symbol.endswith(".BR"):
            return "EUR", "EURONEXT"     # Brussels
        elif symbol.endswith(".DE"):
            return "EUR", "IBIS"         # Xetra
        elif symbol.endswith(".TO"):
            return "CAD", "TSE"          # Toronto
        elif symbol.endswith(".HK"):
            return "HKD", "SEHK"         # Hong Kong
        else:
            return "USD", "NASDAQ"       # US stocks (default)
        
    def place_buy_order(self):
        if not self.is_market_open() or self.has_pending_order() or min(self.cash_left,self.ibapi.available_cash) < self.MIN_CASH_FOR_BUY:
            return False
        
        if not self.app.pdt_protector.can_trade():
            logger.warning(f"PDT protection blocked BUY {self.stock_id}")
            return False

        # === 1. DETERMINE NATIVE CURRENCY + EXCHANGE ===
        native_currency, primary_exchange = self.get_native_currency_and_exchange()

        # === 2. GET LATEST PRICE (already in native currency thanks to yfinance + DB) ===
        latest = self.db_manager.get_latest_price(self.stock_id)
        if not latest or time.time() - latest["fetched_at"] > 30:
            logger.warning(f"[{self.stock_id}] No fresh price -> skip buy")
            return False
        price_native = latest["price"]          # e.g. 156.77 USD, 124.50 GBP, 87.32 EUR

        # === 3. CONVERT AVAILABLE CASH TO NATIVE CURRENCY ===
        eur_usd = self.exchange_manager.get_eur_usd_rate()   # e.g. 1.085

        if native_currency == "EUR":
            cash_native = self.cash_left * 0.98
        elif native_currency == "USD":
            cash_native = self.cash_left * 0.98 * eur_usd
        else:
            cash_native = self.cash_left * 0.98 * eur_usd   # fallback

        # === 4. CALCULATE QUANTITY ===
        quantity = int(cash_native / price_native)
        if quantity < 3:
            logger.warning(f"Low Cash €{self.cash_left:,.0f}")
            return False

        # === 5. RESPECT MAX_AMOUNT (in EUR) AND AVAILABLE CASH ===
        total_cost_eur = quantity * price_native
        if native_currency == "USD":
            total_cost_eur = total_cost_eur / eur_usd

        # Use the MINIMUM of max_amount and actual available cash
        effective_limit = min(self.max_amount, self.cash_left, self.ibapi.available_cash) * self.CASH_BUFFER_MULTIPLIER

        if total_cost_eur > effective_limit:
            # Recalculate to stay under BOTH max_amount AND available cash
            max_native = effective_limit
            if native_currency == "USD":
                max_native = max_native * eur_usd

            quantity = int(max_native / price_native)
            if quantity < 3:
                logger.warning(f"Insufficient funds")
                return False

        # === 6. BUILD REASON ===
        drop_pct = (self.fourteen_day_high - self.market_value) / self.fourteen_day_high * 100
        reason = f"Score:{self.smart_score} | Drop:{drop_pct:.1f}% | RSI:{self.rsi_value:.0f} | Vol:{self.today_volume/1e6:.1f}M"
        if self.score_reason:
            reason += f" | {self.score_reason}"
        if self.stock_id in self.PRIORITY_BUY_LIST:
            reason = "PRIORITY BUY - VIP LIST ★ " + reason

        # === 7. BUILD PERFECT CONTRACT ===
        contract = Contract()
        contract.symbol = self.ibkr_symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = native_currency
        contract.primaryExchange = primary_exchange

        # === 8. CREATE ORDER ===
        order = Order()
        order.action = "BUY"
        order.orderType = "MKT"
        order.totalQuantity = quantity
        order.eTradeOnly = ""
        order.firmQuoteOnly = ""
        order.tif = "DAY"
        order.transmit = True

        # === 9. SEND ORDER ===
        oid = self.ibapi.get_next_order_id()
        # Register callback for when order completes
        self.ibapi.order_callbacks[oid] = lambda order_id, status, filled, avg_price: self._on_order_completed(
            order_id=order_id,
            status=status,
            action="BUY",
            quantity=quantity,
            price=price_native,
            filled=filled,
            avg_fill_price=avg_price,
            currency=native_currency,
            reason=reason
        )

        self.ibapi.placeOrder(oid, contract, order)

        self.pending_order_id = oid
        self.pending_order_time = time.time()
        self.last_quantity = self.quantity

        # ONLY save with "Pending" status, no email yet
        if self.csv_manager:
            self.csv_manager.save_order(
                order_id=oid,
                stock_id=self.stock_id,
                action="BUY",
                quantity=quantity,
                price=price_native,
                currency=native_currency,
                status="Pending",  # Changed from "Submitted"
                reason=reason
            )

        logger.info(f"BUY {quantity} {self.stock_id} @ {price_native:.2f} {native_currency} "
              f"(€{total_cost_eur:.0f} used, €{self.cash_left - total_cost_eur:.0f} left)")
        
        self.app.pdt_protector.log_day_trade_if_confirmed(self.stock_id)
        return True

    def place_sell_order(self):
        if not self.is_market_open() or self.has_pending_order() or self.quantity == 0:
            return False
        
        if not self.app.pdt_protector.can_trade():
                logger.warning(f"PDT protection blocked SELL {self.stock_id}")
                return False

        latest = self.db_manager.get_latest_price(self.stock_id)
        if not latest or time.time() - latest["fetched_at"] > 30:
            return False
        price_native = latest["price"]

        native_currency, primary_exchange = self.get_native_currency_and_exchange()

        reason = f"PROFIT +{self.pnl_percent:.1f}% | Score:{self.smart_score} | RSI:{self.rsi_value:.0f}"

        contract = Contract()
        contract.symbol = self.ibkr_symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = native_currency
        contract.primaryExchange = primary_exchange

        order = Order()
        order.action = "SELL"
        order.orderType = "MKT"
        order.totalQuantity = self.quantity
        order.eTradeOnly = ""
        order.firmQuoteOnly = ""
        order.tif = "DAY"
        order.transmit = True

        oid = self.ibapi.get_next_order_id()
        # Register callback
        self.ibapi.order_callbacks[oid] = lambda order_id, status, filled, avg_price: self._on_order_completed(
            order_id=order_id,
            status=status,
            action="SELL",
            quantity=self.quantity,
            price=price_native,
            filled=filled,
            avg_fill_price=avg_price,
            currency=native_currency,
            reason=reason
        )

        self.ibapi.placeOrder(oid, contract, order)

        self.pending_order_id = oid
        self.pending_order_time = time.time()

        # ONLY save with "Pending" status
        if self.csv_manager:
            self.csv_manager.save_order(
                oid, self.stock_id, "SELL", self.quantity,
                price_native, native_currency, "Pending", reason
            )

        logger.info(f"SELL {self.quantity} {self.stock_id} @ {price_native:.2f} {native_currency}")
        
        self.app.pdt_protector.register_day_trade_if_needed(self.stock_id)
        return True
    
    def check_rapid_drop(self):
        """Monitor for rapid price drop and sell if triggered."""
        while self.is_running:
            if self.is_market_open() and self.quantity > 0 and not self.has_pending_order():
                current_price = self.get_market_value()
                if current_price > 0 and self.last_price is not None:
                    drop_pct = ((self.last_price - current_price) / self.last_price) * 100
                    if drop_pct >= self.rapid_drop_percent:
                        logger.warning(f"[RAPID DROP] {self.stock_id}: {drop_pct:.1f}% in {self.monitor_interval_sec}s - Selling!")
                        self.place_sell_order()  # Full sell
                self.last_price = current_price
            time.sleep(self.monitor_interval_sec)
            
    def check_trading_conditions(self):
        self.get_market_value()
        self.update_position()
        self.calculate_technical_indicators()

        # ALWAYS reset score first
        self.smart_score = 0
        self.score_reason = ""
        
        # === 1. EARNINGS SAFETY (applies to everyone) ===
        earnings_ok = True
        if self.next_earnings_date and self.next_earnings_date != "No payment":
            try:
                earn_date = datetime.strptime(self.next_earnings_date, "%Y-%m-%d").date()
                days = (earn_date - datetime.now().date()).days
                if -2 <= days <= 3: # Skip 3 days before, 2 days after
                    earnings_ok = False
                    self.score_reason = "Earnings soon"
            except:
                pass

        if not earnings_ok:
            self.smart_score = 0
            return 'SELL' if self.quantity > 0 and self.pnl_percent >= self.profit_target * 100 else None
        # === 2. ALWAYS CALCULATE SCORE (even if holding) ===
        
        # 1. Drop from 14d high — volatility adjusted
        drop_pct = (self.fourteen_day_high - self.market_value) / self.fourteen_day_high * 100
        atr_drop_multiple = drop_pct * self.market_value / 100 / max(self.get_atr_14(), 0.01)
        drop_score = min(int(atr_drop_multiple), 5)
        if drop_pct >= 15 and self.get_atr_14() < self.market_value * 0.015:
            drop_score += 1

        # 2. RSI — adaptive
        ma200 = self.get_ma200()
        is_bull_market = self.market_value > ma200
        rsi_extreme = 30 if is_bull_market else 20
        rsi_oversold = 45 if is_bull_market else 35

        rsi_score = 0
        if self.rsi_value < rsi_extreme: rsi_score = 4
        elif self.rsi_value < rsi_oversold: rsi_score = 3
        elif self.rsi_value < 50: rsi_score = 2
        elif self.rsi_value < 60: rsi_score = 1

        # 3. Trend alignment
        trend_score = 0
        if "BULL" in self.ma_signal: trend_score += 2
        if "STRONG_BULL" in self.ma_signal: trend_score += 1
        if "BULL" in self.macd_signal: trend_score += 2
        if "STRONG_BULL" in self.macd_signal: trend_score += 1
        
        # 4. Volume surge
        vol_ratio = self.today_volume / (self.avg_volume_14d or 1)
        volume_score = min(int((vol_ratio - 1) * 2), 4) if vol_ratio > 1 else 0

        # Final
        self.smart_score = drop_score + rsi_score + trend_score + volume_score
        self.score_reason = f"D{drop_score} R{rsi_score} T{trend_score//2} V{volume_score}"
            
        # === 3. TRADING DECISIONS ===
        now = time.time()
        
        # === COOLDOWN CHECKS ===
        hours_since_sell = (now - self.last_sell_time) / 3600
        hours_since_buy = (now - self.last_buy_time) / 3600

        if self.last_sell_time > 0 and hours_since_sell < self.sell_cooldown_hours:
            # Only log if enough time has passed since last warning
            if (now - self.last_cooldown_warning_time) > self.cooldown_warning_interval:
                remaining = self.sell_cooldown_hours - hours_since_sell
                logger.warning(f"Buy cooldown: {remaining:.1f}h remaining after sell")
                self.last_cooldown_warning_time = now
            return None
        
        if self.last_buy_time > 0 and hours_since_buy < self.buy_cooldown_hours:
            # Only log if enough time has passed since last warning
            if (now - self.last_cooldown_warning_time) > self.cooldown_warning_interval:
                remaining = self.buy_cooldown_hours - hours_since_buy
                logger.warning(f"Buy cooldown: {remaining:.1f}h remaining")
                self.last_cooldown_warning_time = now
            return None
        
        # SELL logic
        self.trailing_stop_pct = 0.02  # 2% trail from peak
        self.hard_stop_pct = -0.05     # -5% max loss
        self.peak_pnl = 0.0            # Track highest PNL while holding
        
        if self.quantity > 0:
            self.peak_pnl = max(self.peak_pnl, self.pnl_percent)  # Update peak
            if self.pnl_percent >= self.profit_target * 100:
                return 'SELL'
            
            # Trailing stop (maximize profit by holding longer, but protect gains)
            trail_threshold = self.peak_pnl - (self.trailing_stop_pct * 100)
            if self.pnl_percent < trail_threshold:
                self.score_reason = f"Trailing Stop Hit: PNL {self.pnl_percent:.1f}% < {trail_threshold:.1f}%"
                return 'SELL'
    
            # # Hard stop-loss (minimize risk)
            # if self.pnl_percent <= self.hard_stop_pct * 100:
            #     self.score_reason = f"Hard Stop-Loss: PNL {self.pnl_percent:.1f}%"
            #     return 'SELL'
            
            # Optional: Add to winner (only if strong bullish reversal)
            if (self.smart_score >= 9 and 
                self.pnl_percent > 5 and                      # decent profit cushion
                self.rsi_value > 55 and                        # still strong, not weak!
                (self.ma_signal in ["BULL", "STRONG_BULL"] or 
                 self.macd_signal in ["BULL", "STRONG_BULL"])):
                self.score_reason = f"ADD WINNER ↑ Score:{self.smart_score} P&L:+{self.pnl_percent:.1f}% RSI:{self.rsi_value:.0f}"
                return 'BUY'

            # Otherwise: hold or wait
            return None

        # BUY logic (only when flat)
        if not self.is_market_open() or min(self.cash_left,self.ibapi.available_cash) < self.MIN_CASH_FOR_BUY:
            return None

        drop_pct = (self.fourteen_day_high - self.market_value) / self.fourteen_day_high * 100
        if drop_pct < self.drop_threshold * 100:
            return None

        if self.stock_id.upper() in self.PRIORITY_BUY_LIST:
            self.score_reason = f"PRIORITY DROP -{drop_pct:.1f}%"
            return 'BUY'
        
        if "BEAR" in self.ma_signal and "BEAR" in self.macd_signal:
            if "STRONG" in self.ma_signal or "STRONG" in self.macd_signal:
                self.score_reason = "Strong downtrend → NO BUY"
                return None
            # Allow if only mild bear
            trend_ok = False
        else:
            trend_ok = True

        # Prefer strong bullish confirmation
        # strong_bull = ("STRONG_BULL" in self.ma_signal or "STRONG_BULL" in self.macd_signal)
        mild_bull = ("BULL" in self.ma_signal or "BULL" in self.macd_signal)

        if self.smart_score >= 9 and mild_bull:
            return 'BUY'
        elif self.smart_score >= 8 and mild_bull and self.rsi_value < 40:
            return 'BUY'
        elif self.smart_score >= 7 and trend_ok and self.rsi_value < 50:
            return 'BUY'

        return None

    def get_status(self):
        if not self.is_market_open():
            return self.STATUS_MARKET_CLOSED
        if self.has_pending_order():
            return self.STATUS_WAITING_ORDER
        if self.cash_left < 500:
            return f"Low Cash {self.currency_symbol}{self.cash_left:.0f}"
        if self.is_pausing:
            return self.STATUS_PAUSING
        if self.is_running:
            return self.STATUS_RUNNING
        return self.STATUS_READY

class PDTProtector:
    def __init__(self, db_manager):
        self.db = db_manager
        self.day_trades = collections.deque()

    def _cleanup(self):
        cutoff = datetime.now() - timedelta(days=7)
        while self.day_trades and self.day_trades[0] < cutoff:
            self.day_trades.popleft()

    def count_day_trades_5d(self):
        self._cleanup()
        return len(self.day_trades)

    def register_day_trade_if_needed(self, symbol):
        # Call this after every successful SELL
        today = datetime.now().date()
        with self.db.get_cursor() as cur:
            cur.execute("""
                SELECT action FROM trading_history 
                WHERE stock_id = ? AND DATE(timestamp) = DATE('now')
                ORDER BY timestamp
            """, (symbol,))
            trades = [row[0] for row in cur.fetchall()]

        # If we had BUY → SELL same day → it's a day trade
        if len(trades) >= 2 and trades[0] == 'Buy' and trades[-1] == 'Sell':
            if not self.day_trades or self.day_trades[-1].date() != today:
                self.day_trades.append(datetime.now())
                logger.warning(f"DAY TRADE recorded for {symbol} → Total in 5d: {self.count_day_trades_5d()}/3")

    def can_trade(self):
        count = self.count_day_trades_5d()
        if count >= 3:
            logger.error(f"PDT LIMIT REACHED ({count}/3) – ALL TRADES BLOCKED")
            return False
        return True
            
# ==================== MAIN GUI ====================
class TradingApp(QMainWindow):
    instance = None  # <-- ADD THIS
    DEFAULT_SORT_COLUMN = 20
    DEFAULT_SORT_ORDER  = Qt.SortOrder.AscendingOrder
    def __init__(self):
        super().__init__()
        TradingApp.instance = self  # <-- SET INSTANCE
        self.setWindowTitle("pyTrade")
        self.setGeometry(100, 100, 1900, 900)

        self.db_manager = DatabaseManager()
        self.csv_manager = CSVManager()
        self.exchange_manager = ExchangeRateManager()
        self.ibapi = IBApi()
        self.bots = {}
        self.connected = False
        self.auto_trading = False
        self.order_cooldown = {}  # Per-symbol cooldown

        self.sort_column = self.DEFAULT_SORT_COLUMN  # Earning Date
        self.sort_order = self.DEFAULT_SORT_ORDER

        self.init_ui()
        self.load_stocks()
        
        self._default_sort_applied = False
        self._user_clicked_header = False

        self.timer_display = QTimer()
        self.timer_display.timeout.connect(self.update_display)
        self.timer_display.start(5000)
        
        self.pdt_protector = PDTProtector(self.db_manager)
        
        # trigger default sort after GUI is ready
        QTimer.singleShot(100, self._apply_default_sort)
        
        # 2. try auto‑connect (after 500 ms – table is already built)
        QTimer.singleShot(500, self._auto_connect)
        
    def _auto_connect(self):
        # Called once at start‑up – only if the checkbox is checked.
        if not self.auto_connect_cb.isChecked():
            return

        # Force the button into “Connect” mode (in case it was left disconnected)
        self.conn_btn.setText("Connect")
        self.toggle_connection()          # <-- this does the real connect
        
    #  Portfolio composition helpers
    # --------------------------------------------------------------
    def _get_usd_to_eur_rate(self):
        eur_usd = self.exchange_manager.get_eur_usd_rate()
        if eur_usd > 0:
            return 1 / eur_usd
        else:
            logger.warning("[FX WARNING] Bad EURUSD rate; using fallback 0.92")
            return 0.92  # Update based on recent avg; or raise error
        
    def _calc_portfolio_composition(self):
        """Return (stock_pct, etf_pct, etc_pct) – each is 0-100%"""
        total_port = self.ibapi.portfolio_value
        if total_port <= 0:
            return 0.0, 0.0, 0.0

        usd_to_eur = self._get_usd_to_eur_rate()

        stock_val = etf_val = etc_val = 0.0
        for bot in self.bots.values():
            if bot.quantity <= 0:
                continue
            val = bot.current_value  # In bot's local currency (from yf)
            curr = bot.currency.upper()
            if curr == "USD":
                val *= usd_to_eur

            if bot.asset_type == "STOCK":
                stock_val += val
            elif bot.asset_type == "ETF":
                etf_val += val
            elif bot.asset_type == "ETC":
                etc_val += val

        stock_pct = (stock_val / total_port) * 100
        etf_pct   = (etf_val   / total_port) * 100
        etc_pct   = (etc_val   / total_port) * 100
        return round(stock_pct, 1), round(etf_pct, 1), round(etc_pct, 1)
    
    def _apply_default_sort(self):
        if self.table.rowCount() == 0:
            QTimer.singleShot(200, self._apply_default_sort)
            return

        if not self._default_sort_applied:
            self.sort_column = self.DEFAULT_SORT_COLUMN  
            self.sort_order = self.DEFAULT_SORT_ORDER   # Ascending

            header = self.table.horizontalHeader()
            header.blockSignals(True)  # PREVENT RECURSION
            header.setSortIndicator(self.sort_column, self.sort_order)
            header.blockSignals(False)

            self.table.sortItems(self.sort_column, self.sort_order)
            self._default_sort_applied = True

    def on_header_clicked(self, logical_index):
        self.sort_column = logical_index
        self.sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        self._user_clicked_header = True
        self._default_sort_applied = True  # stop forcing default
        
    def refresh_cash(self):
        if not self.connected:
            return
        self.ibapi.cash_ready_event.clear()
        self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds")
        if self.ibapi.cash_ready_event.wait(5):
            self.rate_label.setText(
                f"EUR/USD: {self.exchange_manager.get_eur_usd_rate():.3f}  "
                f"Cash: {self.ibapi.currency_symbol}{self.ibapi.available_cash:,.0f}"
            )
    
    def send_trade_email(self, symbol, action, quantity, price, native_currency, reason="", bot=None):
        try:
            SMTP_SERVER = ENV["SMTP_SERVER"]
            SMTP_PORT = ENV["SMTP_PORT"]
            SENDER_EMAIL = ENV["SENDER_EMAIL"]
            SENDER_PASS = ENV["SENDER_EMAIL_PASS"]            
            RECEIVER_EMAIL = ENV["RECEIVER_EMAIL"]   
            # Get bot data safely
            if bot is None:
                # Fallback if bot not passed
                score = "N/A"
                rsi = "N/A"
                drop = "N/A"
                volume = "N/A"
                ma = "N/A"
                macd = "N/A"
                earnings = "N/A"
            else:
                score = bot.smart_score
                rsi = f"{bot.rsi_value:.1f}"
                drop_pct = ((bot.fourteen_day_high - bot.market_value) / bot.fourteen_day_high * 100) if bot.fourteen_day_high > 0 else 0
                drop = f"{drop_pct:.1f}%"
                volume = f"{bot.today_volume/1e6:.1f}M (vs {bot.avg_volume_14d/1e6:.1f}M)"
                ma = bot.ma_signal
                macd = bot.macd_signal
                earnings = bot.next_earnings_date or "None"
                
            # 1. Currency symbol ($, €, £ …)
            curr_symbol = self.exchange_manager.get_currency_symbol(native_currency)

            subject = f"{action} {symbol} - {quantity} @ {curr_symbol}{price:.2f}"

            body = f"""
            TRADE EXECUTED - pyTrade BOT

            Symbol     : {symbol}
            Action     : {action}
            Quantity   : {quantity}
            Price      : {curr_symbol}{price:.2f}
            Total      : {curr_symbol}{quantity * price:.2f}
            Time       : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (CET)

            REASON:
            {reason}

            TECHNICALS:
            Score      : {score}/22
            RSI        : {rsi}
            14d Drop   : {drop}
            Volume     : {volume}
            MA Signal  : {ma}
            MACD       : {macd}
            Earnings   : {earnings}

            Bot is running — happy trading!
            """.strip()

            msg = MIMEText(body, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASS)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

            logger.info(f"EMAIL SENT -> {action} {symbol} {quantity} @ ${price:.2f}")
        except Exception as e:
            logger.error(f"[EMAIL ERROR] {e}")
        
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        conn_frame = QGroupBox("IBKR Connection")
        conn_layout = QHBoxLayout()
        
        conn_layout.addWidget(QLabel("Host:"))
        self.host_edit = QLineEdit(ENV["IBKR_HOST"])
        self.host_edit.setFixedWidth(80)
        conn_layout.addWidget(self.host_edit)
        
        conn_layout.addWidget(QLabel("Port:"))  
        self.port_edit = QLineEdit(ENV["IBKR_PORT"])   #For real account      
        self.port_edit.setFixedWidth(80)
        conn_layout.addWidget(self.port_edit)
        
        conn_layout.addWidget(QLabel("Client:"))
        self.client_edit = QLineEdit(ENV["IBKR_CLIENT_ID"])
        self.client_edit.setFixedWidth(18)
        conn_layout.addWidget(self.client_edit)
        
        self.auto_connect_cb = QCheckBox("Auto‑connect")
        self.auto_connect_cb.setChecked(True)      # default = ON
        conn_layout.addWidget(self.auto_connect_cb)
    
        self.conn_btn = QPushButton("Connect")
        self.conn_btn.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.conn_btn)
        
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        conn_layout.addWidget(self.status_label)
        
        # Push everything after this to the right
        conn_layout.addStretch()
                
        self.rate_label = QLabel("EUR/USD: --")
        conn_layout.addWidget(self.rate_label)
        
        self.csv_btn = QPushButton("View CSV")
        self.csv_btn.clicked.connect(self.open_csv)
        conn_layout.addWidget(self.csv_btn)
        
        self.trade_btn = QPushButton("Start Trading")
        self.trade_btn.clicked.connect(self.toggle_trading)
        self.trade_btn.setEnabled(False)
        conn_layout.addWidget(self.trade_btn)
        
        self.trade_status_label = QLabel("Manual")
        self.trade_status_label.setStyleSheet("color: red; font-weight: bold;")
        conn_layout.addWidget(self.trade_status_label)

        conn_frame.setLayout(conn_layout)
        layout.addWidget(conn_frame)

        self.table = QTableWidget()
        self.table.setColumnCount(22)
        # enable wrapping for the whole table
        self.table.setWordWrap(True)                 
        headers = [
            "Company", "Symbol", "Type", "Sector",
            "Price", "Score", "14H", "14L", "RSI", "MA", "MACD", "Volume",
            "Qty", "Buy@", "Value", "P&L%", "Left", "Max", "Profit%", "Drop%", "Earn Date", "Status"
        ]

        # --- Headers bold ---
        self.table.setHorizontalHeaderLabels(headers)
        font = QFont()
        font.setBold(True)
        self.table.horizontalHeader().setFont(font)

        #self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)

        # New: Connect to selection changed signal for custom highlighting
        self.table.itemSelectionChanged.connect(self.highlight_selected_row)

        column_widths = [160, 60, 50, 130, 60, 60, 60, 60, 30, 50, 60, 70, 50, 70, 70, 60, 48, 48, 50, 50, 80, 120]
        for i, w in enumerate(column_widths):
            if w:
                self.table.setColumnWidth(i, w)
            else:
                self.table.horizontalHeader().setSectionResizeMode(
                    i, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        input_frame = QGroupBox("Stock Settings")
        input_layout = QHBoxLayout()
        
        input_layout.addWidget(QLabel("Symbol:"))
        self.sym_edit = QLineEdit()
        self.sym_edit.setFixedWidth(80)
        input_layout.addWidget(self.sym_edit)
        
        input_layout.addWidget(QLabel("MaxEUR:"))
        self.max_edit = QLineEdit("0")
        self.max_edit.setFixedWidth(80)
        input_layout.addWidget(self.max_edit)
        
        input_layout.addWidget(QLabel("Profit%:"))
        self.profit_edit = QLineEdit("5")
        self.profit_edit.setFixedWidth(80)
        input_layout.addWidget(self.profit_edit)
        
        input_layout.addWidget(QLabel("Drop%:"))
        self.drop_edit = QLineEdit("5")
        self.drop_edit.setFixedWidth(80)
        input_layout.addWidget(self.drop_edit)
        
        # Push everything after this to the right
        input_layout.addStretch()

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self.add_stock)
        input_layout.addWidget(self.add_btn)
        
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self.apply_changes)
        input_layout.addWidget(self.apply_btn)
        
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self.remove_stock)
        input_layout.addWidget(self.remove_btn)
        
        input_frame.setLayout(input_layout)
        layout.addWidget(input_frame)

    def highlight_selected_row(self):
        # Clear previous highlights (reset all rows to default background)
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QColor("transparent"))  # Or your default color

        # Get selected rows (usually one, since single selection is default)
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            selected_row = selected_rows[0].row()
            # Apply custom highlight to the entire row
            for col in range(self.table.columnCount()):
                item = self.table.item(selected_row, col)
                if item:
                    item.setBackground(QColor("yellow"))  # Customize color here (e.g., QColor(255, 255, 0, 100) for semi-transparent yellow)

    def on_header_clicked(self, logical_index):
        self.sort_column = logical_index
        self.sort_order = self.table.horizontalHeader().sortIndicatorOrder()

    def load_stocks(self):
        stocks = self.db_manager.get_all_stocks()
        self.table.setRowCount(len(stocks))
        for i, (sid, maxa, prof, drop) in enumerate(stocks):
            bot = TradingBot(self.ibapi, sid, maxa, prof, drop,
                             self.db_manager, self.csv_manager, self.exchange_manager, self)
            self.bots[sid] = bot
            bot.create_yf_ticker()

    def update_display(self):
        now = time.time()
        try:
            # ---------- 1. CASH + PORTFOLIO (same cadence as yfinance) ----------
            market_open = any(bot.is_market_open() for bot in self.bots.values())
            interval = self.ibapi.cash_fetch_interval if market_open else self.ibapi.max_cash_cache_age
            if now - self.ibapi.last_cash_fetch >= interval:
                self.ibapi.cash_ready_event.clear()
                self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds")
                if self.ibapi.cash_ready_event.wait(5):
                    self.ibapi.last_cash_fetch = now

            # ---------- 2. EUR/USD ----------
            rate = self.exchange_manager.get_eur_usd_rate()
            self.rate_label.setText(f"EUR/USD: {rate:.3f}")

            # ---------- 3. CONNECTION + CASH + PORTFOLIO + TOTAL ----------
            cash_val   = self.ibapi.available_cash if self.connected else 0.0
            port_val   = self.ibapi.portfolio_value if self.connected else 0.0
            total_val  = cash_val + port_val

            cash_str   = f"{cash_val:,.0f}" if self.connected else "--"
            port_str   = f"{port_val:,.0f}" if self.connected else "--"
            total_str  = f"{total_val:,.0f}" if self.connected else "--"

            # ----- % composition -----
            stock_p, etf_p, etc_p = self._calc_portfolio_composition()
            comp_str = f"{stock_p}% STOCK – {etf_p}% ETF – {etc_p}% ETC"

            conn_text = "Connected" if self.connected else "Disconnected"
            conn_color = "green" if self.connected else "red"

            self.status_label.setText(
                f"{conn_text} – Total: €{total_str} – Cash: €{cash_str} – Portfolio: €{port_str} ({comp_str})"
            )
            self.status_label.setStyleSheet(f"color: {conn_color}; font-weight: bold;")
            # ---------- 4. TABLE ----------
            selected_symbol = None
            selected_items = self.table.selectedItems()
            if selected_items:
                selected_row = selected_items[0].row()
                selected_symbol_item = self.table.item(selected_row, 1)  # Assuming column 1 is Symbol/ID
                if selected_symbol_item:
                    selected_symbol = selected_symbol_item.text()

            v_scroll = self.table.verticalScrollBar().value()
            h_scroll = self.table.horizontalScrollBar().value()

            for row, (sid, bot) in enumerate(self.bots.items()):
                bot.get_market_value()
                bot.update_position()
                bot.calculate_technical_indicators()
                bot.check_trading_conditions()

                status = bot.get_status()
                volume_display = f"{bot.today_volume / 1e6:.2f}"

                items = [
                    bot.company_name[:25], sid, bot.asset_type, bot.sector,
                    f"{bot.currency_symbol}{bot.market_value:.2f}",  # ← Price (col 4)
                    str(bot.smart_score),  # ← Score (col 5)
                    f"{bot.currency_symbol}{bot.fourteen_day_high:.2f}",
                    f"{bot.currency_symbol}{bot.fourteen_day_low:.2f}",
                    f"{bot.rsi_value:.0f}", bot.ma_signal, bot.macd_signal,
                    volume_display,
                    str(bot.quantity),
                    f"{bot.currency_symbol}{bot.bought_price:.2f}",
                    f"{bot.currency_symbol}{bot.current_value:.2f}",
                    f"{bot.pnl_percent:+.1f}%",
                    f"€{bot.cash_left:,.0f}",
                    f"€{bot.max_amount:,.0f}",
                    f"{bot.profit_target*100:.1f}%",
                    f"{bot.drop_threshold*100:.1f}%",
                    bot.next_earnings_date or '--',
                    status
                ]

                for col, text in enumerate(items):
                    item = QTableWidgetItem(text)
                    if col == 8:  # RSI column
                        try:
                            rsi_val = float(text)
                            if rsi_val > 70:
                                item.setForeground(QColor("red"))  # Overbought, good to sell
                            elif rsi_val < 30:
                                item.setForeground(QColor("green"))  # Oversold, good to buy
                        except ValueError:
                            pass
                    elif col == 11:  # Volume column
                        if bot.today_volume > 1.5 * bot.avg_volume_14d:
                            item.setForeground(QColor("green"))
                    elif col == 5:
                        try:
                            score = int(text)
                            if score >= 8:
                                item.setBackground(QColor(0, 180, 0))      # Green
                                item.setForeground(QColor("white"))
                            elif score >= 6:
                                item.setBackground(QColor(255, 220, 0))    # Yellow
                                item.setForeground(QColor("black"))
                            elif score < 6:
                                item.setBackground(QColor(100, 100, 100))    # Orange
                            item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        except:
                            pass
                    elif col == 20:  # Earn Date column (index 18)
                        if text != '--':
                            try:
                                earn_date = datetime.strptime(text, "%Y-%m-%d").date()
                                current_date = datetime.now().date()   # Use provided current date
                                delta = (earn_date - current_date).days
                                if 0 <= delta <= 30:  # Within 30 days (including today)
                                    item.setForeground(QColor("green"))  # Warning color
                            except ValueError:
                                pass  # Invalid date format; skip coloring
                    elif "BUY" in text or "BULL" in text:
                        item.setForeground(QColor("green"))   # Bullish signal, indicating to buy
                    elif "SELL" in text or "BEAR" in text:
                        item.setForeground(QColor("red"))  # Bearish signal, indicating to sell
                    elif "Market Closed" in text:
                        item.setForeground(QColor("orange"))
                    elif col == 2:
                        color = QColor("blue") if "STOCK" in text else QColor("green") if "ETF" in text else QColor("orange") if "ETC" in text else QColor("black")
                        item.setForeground(QBrush(color))
                    self.table.setItem(row, col, item)

            # Sort using current settings
            self.table.sortItems(self.sort_column, self.sort_order)

            # Apply default sort ONCE, only if user hasn't clicked
            if not self._default_sort_applied and self.table.rowCount() > 0:
                self._apply_default_sort()

            # --- Restore selection by unique symbol ---
            if selected_symbol is not None:
                for row in range(self.table.rowCount()):
                    symbol_item = self.table.item(row, 1)
                    if symbol_item and symbol_item.text() == selected_symbol:
                        self.table.selectRow(row)
                        break
            self.table.verticalScrollBar().setValue(v_scroll)
            self.table.horizontalScrollBar().setValue(h_scroll)
        except Exception as e:
            logger.error(f"Error in update_display: {e}")
            raise  # re-raise to see full traceback

    def toggle_connection(self):
        if not hasattr(self, "ibapi"):      # safety net
            return

        if self.connected:
            self.ibapi.disconnect()
            self.connected = False
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: red;")
            self.conn_btn.setText("Connect")
            self.trade_btn.setEnabled(False)
        else:
            # ----- CONNECT -----
            host = self.host_edit.text().strip() or ENV["IBKR_HOST"]
            try:
                port = int(self.port_edit.text())
            except ValueError:
                port = int(ENV["IBKR_PORT"])
            try:
                cid = int(self.client_edit.text())
            except ValueError:
                cid = int(ENV["IBKR_CLIENT_ID"])
            self.ibapi.connect(host, port, clientId=cid)
            threading.Thread(target=self.ibapi.run, daemon=True).start()

            if self.ibapi.connected_event.wait(12):   # a little longer timeout
                self.connected = True
                self.status_label.setText("Connected")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                self.conn_btn.setText("Disconnect")
                self.trade_btn.setEnabled(True)
                self.ibapi.reqPositions()

                # ---- INITIAL CASH ----
                self.ibapi.cash_ready_event.clear()
                self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds")
                if self.ibapi.cash_ready_event.wait(8):
                    self.ibapi.last_cash_fetch = time.time()
            else:
                self.status_label.setText("Conn. failed")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
                self.conn_btn.setText("Connect")

    def toggle_trading(self):
        if self.auto_trading:
            self.auto_trading = False
            self.trade_btn.setText("Start Trading")
            self.trade_status_label.setText("Manual")
            self.trade_status_label.setStyleSheet("color: red; font-weight: bold;")
            for bot in self.bots.values():
                bot.is_running = False
        else:
            if not self.connected:
                QMessageBox.warning(self, "Error", "Connect first!")
                return
            self.auto_trading = True
            self.trade_btn.setText("Stop Trading")
            self.trade_status_label.setText("Running")
            self.trade_status_label.setStyleSheet("color: green; font-weight: bold;")
            for bot in self.bots.values():
                bot.is_running = True
                # ---- START RAPID DROP MONITOR ----
                if bot.monitor_thread is None or not bot.monitor_thread.is_alive():
                    bot.monitor_thread = threading.Thread(target=bot.check_rapid_drop, daemon=True)
                    bot.monitor_thread.start()
            threading.Thread(target=self.trading_loop, daemon=True).start()

    def trading_loop(self):
        while self.auto_trading:
            if self.connected:
                self.ibapi.reqPositions()
                time.sleep(3)

                for sid, bot in self.bots.items():
                    if (bot.is_running and 
                        not bot.has_pending_order() and 
                        bot.is_market_open() and
                        bot.get_market_value() > 0):

                        # 5-minute cooldown per symbol
                        last_order = self.order_cooldown.get(sid, 0)
                        if time.time() - last_order < 300:
                            continue

                        action = bot.check_trading_conditions()
                        if action == 'BUY':
                            if bot.place_buy_order():
                                self.order_cooldown[sid] = time.time()
                                time.sleep(30)
                        elif action == 'SELL':
                            if bot.place_sell_order():
                                self.order_cooldown[sid] = time.time()
                                time.sleep(30)

            time.sleep(15)

    def add_stock(self):
        sid = self.sym_edit.text().upper().strip()
        if not sid or sid in self.bots:
            QMessageBox.warning(self, "Error", "Invalid or duplicate")
            return
        try:
            max_amt = float(self.max_edit.text())
            prof = float(self.profit_edit.text())
            drop = float(self.drop_edit.text())
            self.db_manager.add_stock(sid, max_amt, prof, drop)
            bot = TradingBot(self.ibapi, sid, max_amt, prof, drop,
                             self.db_manager, self.csv_manager, self.exchange_manager, self)
            self.bots[sid] = bot
            bot.create_yf_ticker()
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.sym_edit.clear()
            self.update_display()
        except:
            QMessageBox.warning(self, "Error", "Invalid numbers")

    def apply_changes(self):
        sel = self.table.selectedItems()
        if not sel:
            QMessageBox.warning(self, "Warning", "Select a row!")
            return
        row = sel[0].row()
        sid = self.table.item(row, 1).text()
        try:
            max_amt = float(self.max_edit.text())
            prof = float(self.profit_edit.text())
            drop = float(self.drop_edit.text())
            self.db_manager.update_stock(sid, max_amt, prof, drop)
            self.bots[sid].update_parameters(max_amt, prof, drop)
            self.update_display()
        except:
            QMessageBox.warning(self, "Error", "Invalid input")

    def remove_stock(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        sid = self.table.item(row, 1).text()

        # CORRECTED: Proper QMessageBox usage
        reply = QMessageBox.question(
            self,
            "Remove Stock",
            f"Delete {sid} and all its data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No  # default
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Stop trading for this bot
            bot = self.bots.get(sid)
            if bot:
                bot.is_running = False

            # Remove from DB and bots dict
            self.db_manager.remove_stock(sid)
            if sid in self.bots:
                del self.bots[sid]

            # Remove row from table
            self.table.removeRow(row)

            # Optional: refresh display to avoid index issues
            self.update_display()

    def open_csv(self):
        if os.path.exists("trading_orders_history.csv"):
            os.startfile("trading_orders_history.csv")
        else:
            QMessageBox.information(self, "Info", "No trades yet.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TradingApp()
    window.showMaximized()  # maximized window with title bar visible
    sys.exit(app.exec())