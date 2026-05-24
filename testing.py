# from pydoc import text
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
# from locale import currency
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

import requests
from bs4 import BeautifulSoup

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

def clean_company_name(name):
    if not name:
        return ""
    # Remove everything after a comma if it contains Inc, Ltd, Co, plc, LLC, Corp, AG, SA, NV, SE, Group, GmbH
    name = re.sub(r',\s*(inc|ltd|co|plc|llc|corp|ag|sa|nv|se|group|gmbh|n\.v\.|s\.a\.).*$', '', name, flags=re.IGNORECASE)
    # Remove common corporate suffixes at word boundaries
    pattern = r'\b(inc|incorporated|corporation|corp|limited|ltd|llc|plc|co|company|holdings|holding|ag|sa|nv|se|gmbh|n\.v\.|s\.a\.|group)\b\.?'
    name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    # Clean up double spaces or trailing/leading whitespace and commas/punctuation/ampersands
    name = re.sub(r'\s+', ' ', name)
    name = name.strip(' ,.-&')
    return name

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
        with self._lock:
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
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    manual_mode INTEGER DEFAULT 0
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
                    adx INTEGER NOT NULL,
                    bb_upper REAL NOT NULL,
                    bb_middle REAL NOT NULL,
                    bb_lower REAL NOT NULL,
                    ma_signal TEXT NOT NULL,
                    macd_signal TEXT NOT NULL,
                    next_earnings_date TEXT,
                    today_volume REAL NOT NULL,
                    avg_volume_14d REAL NOT NULL,
                    prev_close REAL NOT NULL,
                    target_mean_price REAL DEFAULT 0,
                    number_of_analysts INTEGER DEFAULT 0,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
                   
            # Create indexes for faster queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trading_history_stock_id ON trading_history(stock_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trading_history_timestamp ON trading_history(timestamp)")
            
            # One-time migration: shorten all existing company names in the database
            cursor.execute("SELECT symbol, company_name FROM company_data")
            rows = cursor.fetchall()
            for symbol, company_name in rows:
                if company_name:
                    short_name = clean_company_name(company_name)
                    if short_name != company_name:
                        cursor.execute(
                            "UPDATE company_data SET company_name=? WHERE symbol=?",
                            (short_name, symbol)
                        )
            
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
            company_name = clean_company_name(company_name)

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
            
    def get_cached_bank_note(self, symbol):
        """Retrieves the last saved target to see if we need an update."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute('''
                    SELECT latest_target, latest_source, estimation_date, last_updated 
                    FROM analyst_targets WHERE symbol = ?
                ''', (symbol,))
                return cursor.fetchone()
        except Exception as e:
            return None
    
    def get_last_sell_price(self, stock_id):
        """Get the price of the last SELL action for a specific stock."""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT price FROM trading_history
                WHERE stock_id = ? AND action = 'SELL'
                ORDER BY timestamp DESC
                LIMIT 1
            """, (stock_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_cached_indicators(self, stock_id):
        """Get cached technical indicators"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """SELECT high_14d, low_14d, rsi, adx, ma_signal, macd_signal, next_earnings_date, 
                   today_volume, avg_volume_14d, prev_close, target_mean_price, number_of_analysts, strftime('%s', fetched_at) 
                   FROM cached_indicators WHERE stock_id=?""",
                (stock_id,)
            )
            row = cursor.fetchone()

        if row:
            return {
                "high_14d": row[0],
                "low_14d": row[1],
                "rsi": row[2],
                "adx": row[3],
                "ma_signal": row[4],
                "macd_signal": row[5],
                "next_earnings_date": row[6],
                "today_volume": row[7],
                "avg_volume_14d": row[8],
                "prev_close": row[9],
                "target_mean_price": row[10],
                "number_of_analysts": row[11],
                "fetched_at": int(row[12])
            }
        return None

    def update_cached_indicators(self, stock_id, high_14d, low_14d, rsi, adx,bb_upper, bb_middle, bb_lower,
                                  ma_signal, macd_signal, next_earnings_date,
                                  today_volume, avg_volume_14d, prev_close, target_mean_price,number_of_analysts):
        """Update cached technical indicators"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT OR REPLACE INTO cached_indicators
                   (stock_id, high_14d, low_14d, rsi, adx, bb_upper, bb_middle, bb_lower, ma_signal, macd_signal,
                    next_earnings_date, today_volume, avg_volume_14d, prev_close, target_mean_price, number_of_analysts, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    stock_id,
                    float(high_14d or 0),
                    float(low_14d or 0),
                    float(rsi or 0),
                    int(adx or 0),
                    float(bb_upper or 0),
                    float(bb_middle or 0),
                    float(bb_lower or 0),
                    str(ma_signal or ""),
                    str(macd_signal or ""),
                    str(next_earnings_date or ""),
                    float(today_volume or 0),
                    float(avg_volume_14d or 0),
                    float(prev_close or 0),
                    float(target_mean_price or 0),
                    int(number_of_analysts or 0)
                )
            )
            
    def save_target_to_db(self, symbol, target_price, firm_name, date_str):
        try:
            with self.get_cursor() as cursor:
                # 1. Create table with the new "latest_source" and "estimation_date" columns
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS analyst_targets (
                        symbol TEXT PRIMARY KEY,
                        latest_target REAL,
                        latest_source TEXT,
                        estimation_date TEXT,
                        last_updated TIMESTAMP
                    )
                ''')

                # 2. UPSERT: Save the price, the bank name, and the original estimation date
                cursor.execute('''
                    INSERT INTO analyst_targets (symbol, latest_target, latest_source, estimation_date, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET 
                        latest_target = excluded.latest_target,
                        latest_source = excluded.latest_source,
                        estimation_date = excluded.estimation_date,
                        last_updated = excluded.last_updated
                ''', (symbol, target_price, firm_name, date_str, datetime.now()))
        except Exception as e:
            logger.error(f"Database Error in save_target_to_db: {e}")
        
    def add_stock(self, stock_id, max_amount, profit_target, drop_threshold):
        """Add or update stock in watchlist"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT OR REPLACE INTO stocks (stock_id, max_amount, profit_target, drop_threshold, manual_mode, updated_at)
                   VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP)""",
                (stock_id, max_amount, profit_target, drop_threshold)
            )

    def get_all_stocks(self):
        """Get all stocks in watchlist"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT stock_id, max_amount, profit_target, drop_threshold, manual_mode FROM stocks")
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
            cursor.execute("""
                SELECT timestamp FROM trading_history
                WHERE stock_id = ? AND action = 'BUY'
                ORDER BY timestamp DESC
                LIMIT 1
            """, (stock_id,))
            last_buy_row = cursor.fetchone()

            cursor.execute("""
                SELECT timestamp FROM trading_history
                WHERE stock_id = ? AND action = 'SELL'
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
        self.rates = {
            "USD": 1.08,
            "GBP": 0.85,
            "CAD": 1.48,
            "HKD": 8.50,
            "EUR": 1.0
        }
        self.last_update = 0
        self.update_interval = 3600

    @property
    def eur_usd_rate(self):
        return self.rates.get("USD", 1.08)

    @eur_usd_rate.setter
    def eur_usd_rate(self, value):
        self.rates["USD"] = value

    def get_eur_usd_rate(self):
        return self.get_rate("USD")

    def get_rate(self, currency):
        currency = currency.upper()
        if currency == "EUR":
            return 1.0
        
        now = time.time()
        if now - self.last_update >= self.update_interval:
            self.last_update = now
            def fetch():
                for curr in ["USD", "GBP", "CAD", "HKD"]:
                    try:
                        url = f"https://query1.finance.yahoo.com/v8/finance/chart/EUR{curr}=X"
                        headers = {'User-Agent': 'Mozilla/5.0'}
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            price = data['chart']['result'][0]['meta']['regularMarketPrice']
                            new_rate = float(price)
                            if new_rate > 0:
                                self.rates[curr] = round(new_rate, 4)
                    except Exception as e:
                        pass
            executor.submit(fetch)

        return self.rates.get(currency, 1.0)

    def eur_to_native(self, eur_amount, currency):
        if currency.upper() == 'EUR':
            return eur_amount
        return eur_amount * self.get_rate(currency)

    def get_currency_symbol(self, currency="USD"):
        """Return $, €, £, or HK$ based on currency"""
        currency = currency.upper()
        if currency == "EUR":
            return "€"
        elif currency == "GBP":
            return "£"
        elif currency == "HKD":
            return "HK$"
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
    STATUS_MARKET_CLOSED = "Closed"
    STATUS_HOLDING = "Holding"
    PRIORITY_BUY_LIST = {
            "EGLN.L", "ESE.PA"
    }
    
    def __init__(self, ibapi, stock_id, max_amount, profit_target, drop_threshold,manual_mode=False,
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
        self.score_reason = ""
        self.bought_price = 0
        self.current_value = 0
        self.pnl_percent = 0
        self.quantity = 0
        self.last_quantity = 0  # Track for fill detection
        self.is_running = False
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
        self.adx_value = 0   
        self.ma_signal = ""
        self.macd_signal = ""

        self.next_earnings_date = None
        
        self.last_sell_time = 0          
        self.last_buy_time = 0           
        self.last_cooldown_warning_time = 0
        self.cooldown_warning_interval = 7200  # Log once per hour (in seconds)

        # ---- Dynamic Profit Target ----        
        self.atr_multiplier = 1.18  # Tune this (1-2x for conservative/aggressive)
        self.min_profit_pct = profit_target   # Floor to avoid tiny targets
        self.max_profit_pct = 15.0  # Cap to limit hold time/risk
        self.dynamic_profit_target = self.profit_target  # Start with DB value, override dynamically

        # ---- Dynamic Stop Loss ----     
        self.stop_multiplier = 1.5  # Common ATR multiplier is 1.5 to 3.0
        self.max_stop_loss = -15.0  # Hard floor (maximum loss allowed)
        self.min_stop_loss = -3.0   # Hard ceiling (minimum stop to avoid "noise" exits)
        self.dynamic_stop_loss = self.drop_threshold # Starting default value

        self.asset_type = "UNKNOWN"
        self.sector = "N/A"

        self.today_volume = 0
        self.avg_volume_14d = 0
        
        self.previous_close = 0
        
        self.last_bank_update = None
        
        self.manual_mode = manual_mode  # If True, automated signals are ignored
        
        self.target_price = 0
        self.highest_pnl = 0.0

        self.create_yf_ticker()

    def create_yf_ticker(self):
        info_dict = self.db_manager.get_company_info(self.stock_id)
        self.company_name = info_dict["company_name"]
        self.asset_type = info_dict["asset_type"]
        self.sector = info_dict["sector"]
        self.currency = info_dict["currency"]
        self.currency_symbol = {"USD": "$", "EUR": "€", "GBP": "£", "HKD": "HK$"}.get(self.currency, "$")
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
            self.adx_value = cached_ind.get("adx", 0)
            self.ma_signal = cached_ind["ma_signal"]
            self.macd_signal = cached_ind["macd_signal"]
            self.next_earnings_date = cached_ind["next_earnings_date"]
            self.today_volume = cached_ind["today_volume"]
            self.avg_volume_14d = cached_ind["avg_volume_14d"]
            self.previous_close = cached_ind.get("prev_close")
            self.target_price = cached_ind.get("target_mean_price")
            self.last_indicators_fetch = cached_ind["fetched_at"]
        else:
            self.last_indicators_fetch = 0
            
        last_buy, last_sell = self.db_manager.get_last_trade_times(self.stock_id)
        self.last_buy_time = last_buy
        self.last_sell_time = last_sell
            
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

    def calculate_rsi(close: pd.Series, period: int = 14) -> float:
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        # Wilder's smoothing (EMA with alpha=1/period, adjust=False)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1] if len(rsi) > 0 else 50 

    def calculate_adx(self, high, low, close, period=14):
        """Returns ADX value 0-100. >25 = trending, <20 = choppy."""
        tr = pd.concat([high - low, 
                        (high - close.shift()).abs(), 
                        (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, adjust=False).mean()

        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)

        plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        return adx.iloc[-1]
    
    def get_bank_note(self, run_async=True, force=False):
        fallback = None 
        cached_data = self.db_manager.get_cached_bank_note(self.stock_id)

        if cached_data:
            target, source, est_date, last_upd = cached_data
            try:
                if '.' in last_upd:
                    last_upd_dt = datetime.strptime(last_upd, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    last_upd_dt = datetime.strptime(last_upd, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                last_upd_dt = datetime.min

            if (datetime.now() - last_upd_dt).total_seconds() < 86400 and not force:
                self.latest_bank_target = target
                self.latest_bank_source = source
                self.latest_bank_date = est_date
                return target, source, est_date
            else:
                fallback = (target, source, est_date)

        if run_async:
            if not getattr(self, '_fetching_bank_note', False):
                self._fetching_bank_note = True
                def async_fetch():
                    try:
                        self.fetch_fresh_bank_note(fallback)
                    finally:
                        self._fetching_bank_note = False
                executor.submit(async_fetch)
            
            if fallback:
                self.latest_bank_target = fallback[0]
                self.latest_bank_source = fallback[1]
                self.latest_bank_date = fallback[2]
                return fallback
            return None, "N/A", "--"
        else:
            return self.fetch_fresh_bank_note(fallback)

    def fetch_fresh_bank_note(self, fallback=None):
        logger.info(f"Fetching fresh analyst targets for {self.stock_id}...")
        firms = [
            ("Barclays", self.get_barclays_target),
            ("UBS", self.get_ubs_target),
            ("Morgan Stanley", self.get_morgan_stanley_target)
        ]

        valid_data = []
        for name, fetch_method in firms:
            try:
                result = fetch_method(self.stock_id)
                if result and len(result) == 3 and result[0] is not None:
                    price, _, date_str = result
                    valid_data.append({
                        "price": price, 
                        "name": name,
                        "date_obj": datetime.strptime(date_str, '%Y-%m-%d'),
                        "date_str": date_str
                    })
            except Exception as e:
                logger.error(f"Error fetching from {name}: {e}")

        if valid_data:
            latest = sorted(valid_data, key=lambda x: x['date_obj'], reverse=True)[0]
            self.latest_bank_target = latest['price']
            self.latest_bank_source = latest['name']
            self.latest_bank_date = latest['date_str']

            self.db_manager.save_target_to_db(
                self.stock_id, self.latest_bank_target, 
                self.latest_bank_source, self.latest_bank_date
            )
            return self.latest_bank_target, self.latest_bank_source, self.latest_bank_date

        if fallback:
            logger.info(f"API fetch failed. Using stale fallback for {self.stock_id}.")
            self.latest_bank_target = fallback[0]
            self.latest_bank_source = fallback[1]
            self.latest_bank_date = fallback[2]
            return fallback

        logger.info(f"No analyst data found for {self.stock_id}. Caching 'N/A' for 24h.")
        self.db_manager.save_target_to_db(self.stock_id, 0.0, "--", "--")
        self.latest_bank_target = 0.0
        self.latest_bank_source = "--"
        self.latest_bank_date = "--"
        return None, "N/A", "--"
    
    def calculate_technical_indicators(self, force=False):
        now = time.time()
        market_open = self.is_market_open()
        interval = self.indicators_interval_open if market_open else self.indicators_interval_closed
        
        if force or now - self.last_indicators_fetch >= interval:
            if getattr(self, '_fetching_indicators', False):
                return
            self._fetching_indicators = True
            self.last_indicators_fetch = now

            def fetch_task():
                try:
                    data = yf.download(
                        self.stock_id, 
                        period="1y", 
                        interval="1d", 
                        progress=False,
                        auto_adjust=False,
                        multi_level_index=False
                    )
                    
                    if data.empty or len(data) < 200:
                        logger.warning(f"Insufficient data for {self.stock_id}: {len(data)} rows")
                        return
         
                    if isinstance(data.columns, pd.MultiIndex):
                        try:
                            data.columns = data.columns.droplevel(1) 
                        except:
                            pass
                         
                    close = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
                    high  = data['High'].iloc[:, 0]  if isinstance(data['High'], pd.DataFrame)  else data['High']
                    low   = data['Low'].iloc[:, 0]   if isinstance(data['Low'], pd.DataFrame)   else data['Low']
                    volume= data['Volume'].iloc[:, 0] if isinstance(data['Volume'], pd.DataFrame) else data['Volume']
                    
                    if len(close) >= 2:
                        self.previous_close = float(close.iat[-2])
         
                    self.fourteen_day_high = float(high.rolling(14).max().iat[-1])
                    self.fourteen_day_low  = float(low.rolling(14).min().iat[-1])
                    
                    self.adx_value = self.calculate_adx(high, low, close)
                     
                    delta = close.diff()
                    gain = delta.where(delta > 0, 0)
                    loss = -delta.where(delta < 0, 0)
                    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
                    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
                    rs = avg_gain / avg_loss.replace(0, 0.001)
                    rsi_series = 100 - (100 / (1 + rs))
                    self.rsi_value = float(rsi_series.iat[-1]) if not rsi_series.empty else 50.0
         
                    self.bb_middle = close.rolling(20).mean().iat[-1]
                    ma20 = self.bb_middle
                    ma50 = close.rolling(50).mean().iat[-1]
                    ma200 = close.rolling(200).mean().iat[-1]
                    price = close.iat[-1]

                    self._cached_ma200 = float(ma200)
                    self._ma200_last_update = time.time()
                    self._cached_ma50 = float(ma50)
                    self._ma50_last_update = time.time()

                    tr0 = abs(high - low)
                    tr1 = abs(high - close.shift())
                    tr2 = abs(low - close.shift())
                    tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
                    atr = tr.rolling(14).mean().iat[-1]
                    self._cached_atr_14 = float(atr)
                    self._atr_last_update = time.time()
         
                    if price > ma20 > ma50 > ma200:
                        self.ma_signal = "S_BULL"
                    elif price > ma20 and ma20 > ma50:
                        self.ma_signal = "BULL"
                    elif price > ma50:
                        self.ma_signal = "N_BULL"
                    elif price < ma20 and ma20 < ma50:
                        self.ma_signal = "BEAR"
                    elif price < ma50:
                        self.ma_signal = "N_BEAR"
                    else:
                        self.ma_signal = "NEUTRAL"
         
                    ema12 = close.ewm(span=12, adjust=False).mean()
                    ema26 = close.ewm(span=26, adjust=False).mean()
                    macd_line = ema12 - ema26
                    signal_line = macd_line.ewm(span=9, adjust=False).mean()
                    
                    macd_val = float(macd_line.iat[-1])
                    signal_val = float(signal_line.iat[-1])
         
                    if macd_val > signal_val and macd_val > 0:
                        self.macd_signal = "S_BULL"
                    elif macd_val > signal_val:
                        self.macd_signal = "BULL"
                    elif macd_val < signal_val and macd_val < 0:
                        self.macd_signal = "S_BEAR"
                    elif macd_val < signal_val:
                        self.macd_signal = "BEAR"
                    else:
                        self.macd_signal = "NEUTRAL"
     
                    rolling_std = close.rolling(20).std().iat[-1]
                    self.bb_upper = ma20 + (2 * rolling_std)
                    self.bb_lower = ma20 - (2 * rolling_std)
                    if (self.bb_upper - self.bb_lower) != 0:
                        self.bb_pct_b = (price - self.bb_lower) / (self.bb_upper - self.bb_lower)
                    else:
                        self.bb_pct_b = 0.5
                        
                    self.today_volume = float(volume.iat[-1])
                    self.avg_volume_14d = float(volume.rolling(14).mean().iat[-1])
         
                    ticker_obj = yf.Ticker(self.stock_id)
                    self.next_earnings_date = self.fetch_next_event_date(ticker_obj)
                    
                    self.target_price = ticker_obj.info.get('targetMeanPrice', 0)
                    self.previous_close = ticker_obj.info.get('previousClose', 0)
                    self.num_analysts = ticker_obj.info.get('numberOfAnalystOpinions', 0)
                    
                    self.db_manager.update_cached_indicators(
                        self.stock_id, self.fourteen_day_high, self.fourteen_day_low,
                        self.rsi_value, self.adx_value, self.bb_upper, self.bb_middle, self.bb_lower,
                        self.ma_signal, self.macd_signal,
                        self.next_earnings_date, self.today_volume, self.avg_volume_14d,
                        self.previous_close, self.target_price, self.num_analysts
                    )
                    
                    self.update_analyst_data(run_async=False)
                    
                except Exception as e:
                    logger.error(f"Indicators background error for {self.stock_id}: {e}")
                finally:
                    self._fetching_indicators = False
            
            executor.submit(fetch_task)

    def get_ma200(self):
        """
        Get 200-day Simple Moving Average.
        Cached for performance.
        """
        now = time.time()
        if hasattr(self, '_cached_ma200') and now - getattr(self, '_ma200_last_update', 0) < 1800:  # 30 min cache
            return self._cached_ma200
        return getattr(self, '_cached_ma200', self.market_value)

    def get_ma50(self):
        """
        Get 50-day Simple Moving Average.
        Cached for performance.
        """
        now = time.time()
        if hasattr(self, '_cached_ma50') and now - getattr(self, '_ma50_last_update', 0) < 1800:  # 30 min cache
            return self._cached_ma50
        return getattr(self, '_cached_ma50', self.market_value)
        
    def get_atr_14(self):
        """
        Calculate 14-day Average True Range (ATR) in price units.
        Cached for performance — only recalculates when needed.
        """
        now = time.time()
        if hasattr(self, '_cached_atr_14') and now - getattr(self, '_atr_last_update', 0) < 300:
            return self._cached_atr_14
        return getattr(self, '_cached_atr_14', 1.0)

        
    def fetch_next_event_date(self, ticker):
        # ---- 1. Earnings (only for stocks) --------------------------------
        if self.asset_type == "STOCK":
            # Try get_earnings_dates DataFrame
            try:
                ed = ticker.get_earnings_dates(limit=12)
                if ed is not None and not ed.empty:
                    now = pd.Timestamp.now(tz='UTC')
                    if ed.index.tz is not None:
                        now = pd.Timestamp.now(tz=ed.index.tz)
                    else:
                        now = pd.Timestamp.now()
                    future = ed[ed.index > now]
                    if not future.empty:
                        return future.index.min().strftime("%Y-%m-%d")
            except Exception as e:
                logger.error(f"[EARNINGS df] {self.stock_id}: {e}")

            # Try calendar dict as fallback
            try:
                cal = ticker.calendar
                if cal and 'Earnings Date' in cal:
                    dates = cal['Earnings Date']
                    if isinstance(dates, list) and len(dates) > 0:
                        return dates[0].strftime("%Y-%m-%d")
            except Exception as e:
                logger.error(f"[EARNINGS cal] {self.stock_id}: {e}")

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
        return None

    def get_market_value(self):
        now = time.time()
        interval = self.yf_fetch_interval_open if self.is_market_open() else self.yf_fetch_interval_closed
        if now - self.last_yf_fetch < interval:
            return self.market_value
        
        if getattr(self, '_fetching_market_value', False):
            return self.market_value
        self._fetching_market_value = True
        self.last_yf_fetch = now

        def fetch():
            try:
                ticker = yf.Ticker(self.stock_id)
                hist = ticker.history(period="5d", interval="1m")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
                    with self.ibapi.data_lock:
                        self.market_value = round(price, 2)
                    self.db_manager.update_latest_price(self.stock_id, price)
            except:
                pass
            finally:
                self._fetching_market_value = False
        executor.submit(fetch)
        return self.market_value

    def update_position(self):
        with self.ibapi.data_lock:
            pos = self.ibapi.positions.get(self.ibkr_symbol, {})
            self.quantity = pos.get('position', 0)
            self.bought_price = pos.get('avgCost', 0)
            self.current_value = self.quantity * self.market_value if self.quantity > 0 else 0
            self.pnl_percent = ((self.market_value - self.bought_price) / self.bought_price * 100) if self.bought_price > 0 else 0
            if self.quantity == 0:
                self.highest_pnl = 0.0

        # Calculate invested in EUR for THIS stock only
        if self.quantity > 0 and self.bought_price > 0:
            native_invested = self.quantity * self.bought_price
            native_currency, _ = self.get_native_currency_and_exchange()
            rate = self.exchange_manager.get_rate(native_currency)
            eur_invested = native_invested / rate if rate > 0 else native_invested
        else:
            eur_invested = 0.0

        self.cash_left = self.max_amount - eur_invested
        if self.cash_left < 0:
            self.cash_left = 0.0

    def update_parameters(self, max_amount, profit_target, drop_threshold):
        self.max_amount = max_amount
        self.profit_target = profit_target / 100
        self.min_profit_pct = profit_target
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

            # Update PDT Protector with new trades
            if self.app and hasattr(self.app, 'pdt_protector'):
                self.app.pdt_protector.register_day_trade_if_needed(self.stock_id)

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
            return "GBP", "LSE"          # London (Corrected to GBP)
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
        rate = self.exchange_manager.get_rate(native_currency)
        cash_native = self.cash_left * 0.98 * rate

        # === 4. CALCULATE QUANTITY ===
        quantity = int(cash_native / price_native)
        if quantity < 1:
            logger.warning(f"Low Cash €{self.cash_left:,.0f} (Quantity < 1)")
            return False

        # === 5. RESPECT MAX_AMOUNT (in EUR) AND AVAILABLE CASH ===
        total_cost_eur = quantity * price_native
        if native_currency != "EUR":
            total_cost_eur = total_cost_eur / rate

        # Use the MINIMUM of max_amount and available cash
        effective_limit = min(self.max_amount, self.cash_left, self.ibapi.available_cash) * self.CASH_BUFFER_MULTIPLIER

        if total_cost_eur > effective_limit:
            # Recalculate to stay under BOTH max_amount AND available cash
            max_native = effective_limit * rate
            quantity = int(max_native / price_native)
            if quantity < 1:
                logger.warning(f"Insufficient funds (Quantity < 1)")
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

        return True

    def place_sell_order(self):
        if not self.is_market_open() or self.has_pending_order() or self.quantity == 0:
            return False
        
        latest = self.db_manager.get_latest_price(self.stock_id)
        if not latest or time.time() - latest["fetched_at"] > 30:
            return False
        price_native = latest["price"]

        native_currency, primary_exchange = self.get_native_currency_and_exchange()

        reason = f"PROFIT {self.pnl_percent:.1f}% | Score:{self.smart_score} | RSI:{self.rsi_value:.0f}"

        # === 1. BUILD CONTRACT ===
        contract = Contract()
        contract.symbol = self.ibkr_symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = native_currency
        contract.primaryExchange = primary_exchange

        # === 2. CREATE ORDER ===
        order = Order()
        order.action = "SELL"
        order.orderType = "MKT"
        order.totalQuantity = self.quantity
        order.eTradeOnly = ""
        order.firmQuoteOnly = ""
        order.tif = "DAY"
        order.transmit = True

        # === 3. SEND ORDER ===
        oid = self.ibapi.get_next_order_id()
        # Register callback for when order completes
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
                order_id=oid,
                stock_id=self.stock_id,
                action="SELL",
                quantity=self.quantity,
                price=price_native,
                currency=native_currency,
                status="Pending",
                reason=reason
            )

        logger.info(f"SELL {self.quantity} {self.stock_id} @ {price_native:.2f} {native_currency}")
        
        return True
    
    def update_analyst_data(self, run_async=True):
        # 1. Skip for assets without analyst coverage
        if self.asset_type in ["ETF", "ETC"]:
            self.analyst_data = []
            return

        # 2. Get Bank Data (Tier 1)
        bank_target, bank_source, bank_date = self.get_bank_note(run_async=run_async)

        # 3. Get yfinance Data (Tier 2) + Estimate Date
        try:
            yf_target = getattr(self, 'target_price', 0)
            yf_date = datetime.now().strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Failed to fetch yf target for {self.stock_id}: {e}")
            yf_target = 0
            yf_date = "--"

        # 4. Consolidate
        self.analyst_data = []
        if bank_target:
            self.analyst_data.append({"source": bank_source, "target": bank_target, "date": bank_date, "tier": 1})
        if yf_target:
            self.analyst_data.append({"source": "yfinance", "target": yf_target, "date": yf_date, "tier": 2})
        
    def get_barclays_target(self, symbol):
        ticker = yf.Ticker(symbol)
        df = ticker.upgrades_downgrades

        if df is None or df.empty:
            return None, "No analyst history found.", "N/A"

        # Filter for Barclays
        barclays_names = ['barclays', 'barclays capital', 'barclays plc']
        barclays_data = df[df['Firm'].str.lower().isin(barclays_names)]

        if barclays_data.empty:
            return None, "Barclays does not cover this stock.", "N/A"

        # Get latest entry
        latest_action = barclays_data.sort_index().iloc[-1]

        # --- NEW: Extract the Date ---
        # .name gets the index value (the timestamp)
        date_str = latest_action.name.strftime('%Y-%m-%d') 

        target_val = latest_action.get('currentPriceTarget')

        if pd.notnull(target_val) and target_val != 0:
            return float(target_val), f"Target: ${float(target_val)}", date_str
        else:
            grade = latest_action.get('ToGrade', 'N/A')
            return None, f"Rating: {grade}", date_str

    def get_ubs_target(self, symbol):
        """
        Scrape UBS research page for price target with robust parsing.
        Returns: (target_price, description, date_string) or (None, error_msg, None)
        """
        # Step 1: Try yfinance first (Keep your existing logic)
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.upgrades_downgrades
            if df is not None and not df.empty:
                ubs_names = ['ubs', 'ubs group', 'ubs ag']
                ubs_data = df[df['Firm'].str.lower().isin(ubs_names)]
                if not ubs_data.empty:
                    latest = ubs_data.sort_index().iloc[-1]
                    # Check if this data is recent (e.g., within last 30 days) to prefer it
                    # Otherwise, fall through to scraping for potentially newer data
                    target_val = latest.get('currentPriceTarget')
                    date_str = latest.name.strftime('%Y-%m-%d')
                    if pd.notnull(target_val) and target_val != 0:
                        # If date is very recent, return it. If old, let scraping try.
                        if (datetime.now() - latest.name).days < 30:
                            return float(target_val), f"Target: ${float(target_val)}", date_str
        except Exception as e:
            logger.warning(f"yfinance failed: {e}")

        # Step 2: Web scraping fallback
        logger.info(f"Attempting web scrape for {symbol}...")

        ubs_url_map = {
            'ASML': 'https://research.ibb.ubs.com/openaccess/compliance/107563_1_new.html',
            'GOOG': 'https://research.ibb.ubs.com/openaccess/compliance/680397698365_1_new.html',
            'AMZN': 'https://research.ibb.ubs.com/openaccess/compliance/163268_1_new.html',
            'QCOM': 'https://research.ibb.ubs.com/openaccess/compliance/80649_1_new.html',
            'MRNA': 'https://research.ibb.ubs.com/openaccess/compliance/3483757_1_new.html',
            'NVDA': 'https://research.ibb.ubs.com/openaccess/compliance/194637_1_new.html',
            'MU': 'https://research.ibb.ubs.com/openaccess/compliance/79529_1_new.html',
            'TSLA': 'https://research.ibb.ubs.com/openaccess/compliance/711534_1_new.html',
            'MSFT': 'https://research.ibb.ubs.com/openaccess/compliance/79078_1_new.html',
            'AAPL': 'https://research.ibb.ubs.com/openaccess/compliance/79492_1_new.html',
            'AMD': 'https://research.ibb.ubs.com/openaccess/compliance/76891_1_new.html',
            'ARM': 'https://research.ibb.ubs.com/openaccess/compliance/681579446666_1_new.html',
            'INTC': 'https://research.ibb.ubs.com/openaccess/compliance/79064_1_new.html',
            'BARC.L': 'https://research.ibb.ubs.com/openaccess/compliance/77048_1_new.html',
            'AIR.PA': 'https://research.ibb.ubs.com/openaccess/compliance/330733_1_new.html',
            'HO.PA': 'https://research.ibb.ubs.com/openaccess/compliance/91575_1_new.html',
            'SAF.PA': 'https://research.ibb.ubs.com/openaccess/compliance/90758_1_new.html'
        }

        url = ubs_url_map.get(symbol)
        if not url:
            return None, "No UBS URL mapping", None

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            }

            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code != 200:
                return None, f"HTTP {response.status_code}", None

            soup = BeautifulSoup(response.content, 'html.parser')

            try:
                # 1. Target the table by ID specifically
                table = soup.find('table')
                if not table:
                    return None

                # Get all rows (skipping the header)
                rows = table.find_all('tr')[1:]
                if not rows:
                    return None

                # The latest data is in the last row
                latest_row = rows[-1]
                cols = latest_row.find_all('td')

                # Structure: Date | Price | Target | Rating
                date = cols[0].get_text(strip=True)
                target_price = cols[2].get_text(strip=True)
    
                logger.info(f"[SUCCESS] ASML Target: {target_price} (Date: {date})")
                return float(target_price), f"Target: €{target_price}", date
            
            except Exception as e:
                logger.error(f"Scrape error: {str(e)}")
                return None, "Scrape failure", None
    
        except Exception as e:
            logger.error(f"Error parsing UBS page: {e}")
            return None, f"Parse error: {str(e)}", None

    def get_morgan_stanley_target(self, symbol):
        ticker = yf.Ticker(symbol)
        df = ticker.upgrades_downgrades

        if df is None or df.empty:
            return None, "No analyst history found."

        # Filter for Morgan Stanley
        ms_names = ['morgan stanley', 'morgan stanley & co.']
        ms_data = df[df['Firm'].str.lower().isin(ms_names)]

        if ms_data.empty:
            return None, "Morgan Stanley does not cover this stock."

        # Get latest entry and extract currentPriceTarget
        latest = ms_data.sort_index().iloc[-1]
        target_val = latest.get('currentPriceTarget')
        date_str = latest.name.strftime('%Y-%m-%d') 

        if pd.notnull(target_val) and target_val != 0:
            return float(target_val), f"Target: ${float(target_val)}", date_str
        else:
            grade = latest.get('ToGrade', 'N/A')
            return None, f"Rating: {grade}", date_str
        
    def calculate_analyst_modifier(self):
        """Calculates a score modifier (-2 to +2) based on analyst consensus."""
        if not hasattr(self, 'analyst_data') or not self.analyst_data:
            return 0, "No Data"

        total_weight = 0
        weighted_sum = 0
        now = datetime.now()

        for entry in self.analyst_data:
            # FIX 1: Skip if target is missing or date is invalid ('--' or None)
            if not entry.get('target') or not entry.get('date') or entry['date'] == "--":
                continue

            try:
                # 1. Calculate Recency Weight (30-day decay)
                target_date = datetime.strptime(entry['date'], "%Y-%m-%d")
                days_old = (now - target_date).days
                
                if days_old > 90: # Ignore data older than 3 months
                    continue
                
                recency_multiplier = max(0.1, (90 - days_old) / 90)
                
                # 2. Source Authority Weight
                source_weight = 2.0 if entry.get('tier') == 1 else 1.0
                
                combined_weight = recency_multiplier * source_weight
                weighted_sum += entry['target'] * combined_weight
                total_weight += combined_weight
            except (ValueError, TypeError):
                continue # Skip malformed entries

        if total_weight == 0:
            return 0, "Outdated/No Data"

        weighted_target = weighted_sum / total_weight
        upside_pct = (weighted_target - self.market_value) / self.market_value

        # 3. Score Mapping
        modifier = 0
        note = ""
        
        if upside_pct > 0.20: 
            modifier = 3 if total_weight > 2 else 2 # Extra point if high conviction
            note = "Strong-Upside"
        elif upside_pct > 0.10:
            modifier = 1
            note = "Fair-Upside"
        elif upside_pct < -0.05:
            modifier = -2
            note = "Overvalued"
            
        return modifier, note
        
    def calculate_score(self):
        """
        Calculates the Smart Score (0-12) using multi-factor analysis.
        Updates self.smart_score and self.score_reason.
        """
        if self.fourteen_day_high <= 0 or self.market_value <= 0:
            self.smart_score = 0
            self.score_reason = "Insufficient Data"
            return

        self.score_reason = ""
        ma200 = self.get_ma200()
        
        # --- FACTOR 1: MARKET STRUCTURE (Trend) ---
        # Is the long-term trend healthy?
        trend_score = 0
        if self.market_value > ma200:
            trend_score = 3  # Bullish context
        elif self.market_value > self.previous_close:
            trend_score = 1  # Recovering
        
        # --- STRATEGY A: DIP BUYER (Reversion to Mean) ---
        dip_points = 0
        
        # 1. RSI (Oscillator) - Max 4 points
        if self.rsi_value < 25: dip_points += 4
        elif self.rsi_value < 30: dip_points += 3
        elif self.rsi_value < 40: dip_points += 2
        
        # 2. Bollinger Bands (Volatility) - Max 3 points
        if hasattr(self, 'bb_pct_b'):
            if self.bb_pct_b < 0:      dip_points += 3  # Below Lower Band (Extreme)
            elif self.bb_pct_b < 0.1:  dip_points += 2  # Touching Lower Band
            elif self.bb_pct_b < 0.2:  dip_points += 1  # Near Lower Band
            
        # 3. Context (Trend) - Max 3 points
        dip_points += trend_score  # We prefer buying dips in uptrends
        
        # Total Dip Score = RSI(4) + BB(3) + Trend(3) = 10 max
        
        # --- STRATEGY B: MOMENTUM (Breakout) ---
        mom_points = 0
        
        # 1. MACD & Signal - Max 3 points
        if "S_BULL" in self.macd_signal: mom_points += 3
        elif "BULL" in self.macd_signal: mom_points += 2
        
        # 2. ADX (Trend Strength & Directional Guard) - Max 2 points
        # Only award points if the stock is in an uptrend (price above 50 SMA)
        ma50 = self.get_ma50()
        if self.market_value > ma50:
            if self.adx_value > 25: mom_points += 1
            if self.adx_value > 35: mom_points += 1
        
        # 3. Volume Support - Max 2 points
        if self.today_volume > self.avg_volume_14d:
            mom_points += 1
        if self.today_volume > self.avg_volume_14d * 1.5:
            mom_points += 1
            
        # 4. RSI Sweet Spot (Not too high) - Max 3 points
        if 50 <= self.rsi_value <= 70:
            mom_points += 3
        elif 40 <= self.rsi_value <= 50:
            mom_points += 1 # Weak momentum
            
        # Total Momentum Score = MACD(3) + ADX(2) + Vol(2) + RSI(3) = 10 max

        # --- SELECTION ---
        if dip_points >= mom_points:
            self.base_score = dip_points
            current_strategy = "DIP"
        else:
            self.base_score = mom_points
            current_strategy = "MOMENTUM"
            
        # --- ANALYST MODIFIER (-2 to +2) ---
        analyst_mod, analyst_note = self.calculate_analyst_modifier()
        target_bonus = 0
        
        # 1. Get the High-Tier Bank Target from your DB
        bank_data = self.db_manager.get_cached_bank_note(self.stock_id)
        bank_target = bank_data[0] if bank_data else None

        # Fallback to Yahoo Finance target if no bank note exists
        final_target = bank_target if bank_target else self.target_price

        if final_target and final_target > 0 and self.market_value > 0:
            temp_target = final_target
            # Currency Normalization (Handles GBp vs GBP)
            if self.stock_id.upper().endswith(".L") and self.market_value > temp_target * 10:
                temp_target = temp_target * 100
            elif self.market_value > 10 and temp_target < 10:
                temp_target = temp_target * 100

            # --- COMBINED UNDER/OVERVALUATION LOGIC ---
            
            # CASE A: Price is LOWER than Target (Undervalued)
            if self.market_value <= (temp_target * 0.80):
                target_bonus = 3
                self.score_reason += f" [Bank Target: +3 (20%+ Upside vs {final_target})]"
            elif self.market_value <= (temp_target * 0.90):
                target_bonus = 2
                self.score_reason += f" [Bank Target: +2 (10%+ Upside vs {final_target})]"
            elif self.market_value < temp_target:
                target_bonus = 1
                self.score_reason += " [Bank Target: +1 (Below Target)]"

            # CASE B: Price is HIGHER than Target (Overvalued)
            elif self.market_value >= (temp_target * 1.20):
                target_bonus = -3
                self.score_reason += f" [Bank Target: -3 (20%+ Overvalued vs {final_target})]"
            elif self.market_value >= (temp_target * 1.10):
                target_bonus = -2
                self.score_reason += f" [Bank Target: -2 (10%+ Overvalued vs {final_target})]"
            elif self.market_value > temp_target:
                target_bonus = -1
                self.score_reason += " [Bank Target: -1 (Above Target)]"

        # --- FINAL SCORE CALCULATION ---
        self.smart_score = self.base_score + analyst_mod + target_bonus

        # Cap limits
        self.smart_score = max(0, min(12, int(self.smart_score)))
        
        bonus_reason = self.score_reason
        self.score_reason = f"[{current_strategy}] Base:{self.base_score} {analyst_note}{bonus_reason}".strip()
        return self.smart_score
         
    def check_trading_conditions(self):
        
        self.update_analyst_data(run_async=True)
        if self.manual_mode:
            return None # Skip all automated logic
        
        # Safety guards
        if self.fourteen_day_high <= 0 or self.market_value <= 0:
            return None

        # Update dynamic target
        atr = self.get_atr_14()
        if atr > 0:
            atr_pct = (atr / self.market_value) * 100
            dynamic_target_pct = self.atr_multiplier * atr_pct
            self.dynamic_profit_target = max(self.min_profit_pct, min(dynamic_target_pct, self.max_profit_pct)) / 100
            
            raw_stop_pct = self.stop_multiplier * atr_pct
            self.dynamic_stop_loss = -max(abs(self.min_stop_loss), min(raw_stop_pct, abs(self.max_stop_loss)))        
        
        # Run Score Calculation
        self.calculate_score()

        # -- SELL LOGIC (Exempt from cooldowns, prioritised) --
        if self.quantity > 0:
            if self.pnl_percent > self.highest_pnl:
                self.highest_pnl = self.pnl_percent

            # 1. Trailing Profit Lock
            profit_target_pct = self.dynamic_profit_target * 100
            if self.highest_pnl >= profit_target_pct:
                trail_activation = self.highest_pnl - 1.5
                if self.pnl_percent <= trail_activation:
                    logger.info(f"[{self.stock_id}] Trailing Profit Triggered at {self.pnl_percent:.2f}% (Peak PnL: {self.highest_pnl:.2f}%)")
                    self.highest_pnl = 0.0
                    return 'SELL'
            
            # 2. Dynamic Stop Loss (ATR-based)
            if self.pnl_percent <= self.dynamic_stop_loss:
                logger.info(f"[{self.stock_id}] ATR Stop Loss Triggered at {self.dynamic_stop_loss:.1f}%")
                self.highest_pnl = 0.0
                return 'SELL'
            return None

        # -- BUY LOGIC --
        
        # 1. Cooldown checks for BUY
        now = time.time()
        if now - self.last_buy_time < 172800 or now - self.last_sell_time < 172800:  # 48 hours
            return None

        if self.quantity > 0 and now - self.last_buy_time < 1800:  # Min 30 min hold
            return None

        # 2. Earnings check (skip 3 days before, 2 after)
        earnings_ok = True
        if self.next_earnings_date and self.next_earnings_date != "No payment":
            earn_date = datetime.strptime(self.next_earnings_date, "%Y-%m-%d").date()
            days = (earn_date - datetime.now().date()).days
            if -2 <= days <= 3:
                earnings_ok = False

        if not self.is_market_open() or min(self.cash_left, self.ibapi.available_cash) < self.MIN_CASH_FOR_BUY or not earnings_ok:
            return None
        
        current_strategy = "DIP" if "DIP" in self.score_reason else "MOMENTUM"
        
        # 1. DIP STRATEGY TRIGGER
        if current_strategy == "DIP" and self.smart_score >= 7:
            daily_drop = (self.market_value - self.previous_close) / self.previous_close
            
            # Block if the single-day drop is too extreme (e.g., worse than -7%)
            if daily_drop < -0.07:
                logger.info(f"[{self.stock_id}] Blocked DIP buy: daily drop ({daily_drop*100:.1f}%) exceeds -7% limit.")
                return None
                
            # Block if the drop is moderate but RSI is still high (not oversold enough)
            if daily_drop < -0.03 and self.rsi_value > 30:
                logger.info(f"[{self.stock_id}] Blocked DIP buy: catching a falling knife (RSI: {self.rsi_value:.1f})")
                return None
            
            self.score_reason += " (Dip Entry)"
            return 'BUY'

        # 2. MOMENTUM STRATEGY TRIGGER
        if current_strategy == "MOMENTUM" and self.smart_score >= 8:
            self.score_reason += " (Momentum Entry)"
            return 'BUY'
        return None

    def get_status(self):
        if not self.is_market_open():
            return self.STATUS_MARKET_CLOSED
        if self.manual_mode:
            return self.STATUS_HOLDING
        if self.has_pending_order():
            return self.STATUS_WAITING_ORDER
        if self.cash_left < 500:
            return f"Low Cash {self.currency_symbol}{self.cash_left:.0f}"
        if self.is_running:
            return self.STATUS_RUNNING
        if self.manual_mode:
            return self.STATUS_HOLDING
        return self.STATUS_READY
    
    def stop(self):
        self.is_running = False
            
class PDTProtector:
    def __init__(self, db_manager):
        self.db = db_manager
        self.day_trades = collections.deque()
        self._load_history()

    def _load_history(self):
        self.day_trades.clear()
        cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        try:
            with self.db.get_cursor() as cur:
                cur.execute("""
                    SELECT t1.timestamp FROM trading_history t1
                    WHERE t1.action = 'SELL' AND t1.timestamp >= ?
                    AND t1.stock_id IN (
                        SELECT t2.stock_id FROM trading_history t2
                        WHERE t2.action = 'BUY' AND DATE(t2.timestamp) = DATE(t1.timestamp)
                    )
                    ORDER BY t1.timestamp ASC
                """, (cutoff,))
                rows = cur.fetchall()
                for row in rows:
                    dt = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                    self.day_trades.append(dt)
            logger.info(f"PDT Protector: Loaded {len(self.day_trades)} day trades from the last 7 days.")
        except Exception as e:
            logger.error(f"Failed to load PDT history: {e}")

    def _cleanup(self):
        cutoff = datetime.now() - timedelta(days=7)
        while self.day_trades and self.day_trades[0] < cutoff:
            self.day_trades.popleft()

    def count_day_trades_5d(self):
        self._cleanup()
        return len(self.day_trades)

    def register_day_trade_if_needed(self, symbol=None):
        self._load_history()

    def can_trade(self):
        count = self.count_day_trades_5d()
        if count >= 3:
            logger.error(f"PDT LIMIT REACHED ({count}/3) ALL TRADES BLOCKED")
            return False
        return True

def format_currency_short(val, sym="€"):
    if val is None:
        return "--"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1000:
        val_str = f"{abs_val/1000:.1f}k" if abs_val % 1000 != 0 else f"{abs_val/1000:.0f}k"
        return f"{sign}{sym}{val_str}"
    return f"{sign}{sym}{abs_val:.0f}"

            
# ==================== MAIN GUI ====================
class TradingApp(QMainWindow):
    instance = None  # <-- ADD THIS
    DEFAULT_SORT_COLUMN = 26
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
            if curr != "EUR":
                rate = self.exchange_manager.get_rate(curr)
                if rate > 0:
                    val = val / rate

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

        # Style sheet for standard buttons
        common_button_style = """
            QPushButton {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 5px 12px;
                border: 1px solid #2c3e50;
            }
            QPushButton:hover {
                background-color: #415b76;
            }
            QPushButton:pressed {
                background-color: #2c3e50;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
                color: #bdc3c7;
            }
        """

        conn_frame = QGroupBox("IBKR Connection")
        conn_main_layout = QVBoxLayout()
        
        # Row 1: Connection controls
        conn_row_layout = QHBoxLayout()
        
        conn_row_layout.addWidget(QLabel("Host:"))
        self.host_edit = QLineEdit(ENV["IBKR_HOST"])
        self.host_edit.setFixedWidth(80)
        conn_row_layout.addWidget(self.host_edit)
        
        conn_row_layout.addWidget(QLabel("Port:"))  
        self.port_edit = QLineEdit(ENV["IBKR_PORT"])
        self.port_edit.setFixedWidth(80)
        conn_row_layout.addWidget(self.port_edit)
        
        conn_row_layout.addWidget(QLabel("Client:"))
        self.client_edit = QLineEdit(ENV["IBKR_CLIENT_ID"])
        self.client_edit.setFixedWidth(30)
        conn_row_layout.addWidget(self.client_edit)
        
        self.auto_connect_cb = QCheckBox("Auto‑connect")
        self.auto_connect_cb.setChecked(True)
        conn_row_layout.addWidget(self.auto_connect_cb)
    
        self.conn_btn = QPushButton("Connect")
        self.conn_btn.setStyleSheet(common_button_style)
        self.conn_btn.clicked.connect(self.toggle_connection)
        conn_row_layout.addWidget(self.conn_btn)
        
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        conn_row_layout.addWidget(self.status_label)
        
        conn_row_layout.addSpacing(15)
        
        self.trade_btn = QPushButton("Start Trading")
        self.trade_btn.setStyleSheet(common_button_style)
        self.trade_btn.clicked.connect(self.toggle_trading)
        self.trade_btn.setEnabled(False)
        conn_row_layout.addWidget(self.trade_btn)
        
        self.trade_status_label = QLabel("Manual")
        self.trade_status_label.setStyleSheet("color: red; font-weight: bold;")
        conn_row_layout.addWidget(self.trade_status_label)
        
        conn_row_layout.addSpacing(10)
        
        self.update_btn = QPushButton("Update")
        self.update_btn.setStyleSheet(common_button_style)
        self.update_btn.clicked.connect(self.manual_refresh_data)
        conn_row_layout.addWidget(self.update_btn)
        
        conn_row_layout.addStretch()
                
        self.csv_btn = QPushButton("View CSV")
        self.csv_btn.setStyleSheet(common_button_style)
        self.csv_btn.clicked.connect(self.open_csv)
        conn_row_layout.addWidget(self.csv_btn)
        
        conn_main_layout.addLayout(conn_row_layout)
        
        # Row 2: Portfolio Dashboard Banner
        dash_row_layout = QHBoxLayout()
        
        self.portfolio_label = QLabel("Total Value: €--  |  Cash: €--  |  Portfolio: €--  |  Allocation: --")
        self.portfolio_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #dfdfdf;")
        dash_row_layout.addWidget(self.portfolio_label)
        
        dash_row_layout.addStretch()
        
        self.rate_label = QLabel("EUR/USD: --")
        self.rate_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #3498db;")
        dash_row_layout.addWidget(self.rate_label)
        
        conn_main_layout.addLayout(dash_row_layout)
        conn_frame.setLayout(conn_main_layout)
        layout.addWidget(conn_frame)

        self.table = QTableWidget()
        self.table.setColumnCount(28)
        self.table.setWordWrap(True)                 
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #121212;
                gridline-color: #2c3e50;
                color: #ffffff;
                font-size: 10px;
            }
            QTableWidget::item {
                padding: 1px 3px;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 3px;
                border: 1px solid #1d1d1d;
            }
        """)
        headers = [
            "Company", "Sym", "Type", "Sector",
            "Price", "Chg%", "Target", "Bank Target", "Score", "14H", "14L", "RSI", "ADX", "MA", "MACD", "Vol(M)",
            "Qty", "Buy@", "Value", "P&L%", "Left", "Max", "TP%", "DynTP", "SL%", "DynSL", "Earn", "Status"
        ]

        self.table.setHorizontalHeaderLabels(headers)
        font = QFont()
        font.setBold(True)
        self.table.horizontalHeader().setFont(font)

        # Configure default column visibilities to optimize space on MacBook Air screens
        self.table.setColumnHidden(2, True)   # Hide Type
        self.table.setColumnHidden(3, True)   # Hide Sector
        self.table.setColumnHidden(20, True)  # Hide Left

        # Enable context menu on the horizontal header to show/hide any column they want
        self.table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.table.itemSelectionChanged.connect(self.highlight_selected_row)

        column_widths = [110, 42, 50, 80, 46, 46, 46, 105, 32, 45, 45, 25, 25, 45, 45, 40, 30, 45, 45, 48, 45, 45, 40, 40, 35, 40, 68, 52]
        for i, w in enumerate(column_widths):
            if w:
                self.table.setColumnWidth(i, w)
            else:
                self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        input_frame = QGroupBox("Stock Settings")
        input_main_layout = QVBoxLayout()
        input_main_layout.setContentsMargins(10, 4, 10, 4)
        
        row_layout = QHBoxLayout()
        row_layout.addWidget(QLabel("Symbol:"))
        self.sym_edit = QLineEdit()
        self.sym_edit.setFixedWidth(65)
        self.sym_edit.setPlaceholderText("Sym")
        row_layout.addWidget(self.sym_edit)
        
        row_layout.addWidget(QLabel("MaxEUR:"))
        self.max_edit = QLineEdit("0")
        self.max_edit.setFixedWidth(65)
        self.max_edit.setPlaceholderText("Max")
        row_layout.addWidget(self.max_edit)
        
        row_layout.addWidget(QLabel("Profit%: "))
        self.profit_edit = QLineEdit("5")
        self.profit_edit.setFixedWidth(35)
        self.profit_edit.setPlaceholderText("%")
        row_layout.addWidget(self.profit_edit)
        
        row_layout.addWidget(QLabel("Drop%: "))
        self.drop_edit = QLineEdit("5")
        self.drop_edit.setFixedWidth(35)
        self.drop_edit.setPlaceholderText("%")
        row_layout.addWidget(self.drop_edit)
        
        row_layout.addSpacing(10)
        
        self.add_btn = QPushButton("Add Stock")
        self.add_btn.setStyleSheet(common_button_style)
        self.add_btn.clicked.connect(self.add_stock)
        row_layout.addWidget(self.add_btn)
        
        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.setStyleSheet(common_button_style)
        self.apply_btn.clicked.connect(self.apply_changes)
        row_layout.addWidget(self.apply_btn)
        
        self.remove_btn = QPushButton("Remove Stock")
        self.remove_btn.setStyleSheet(common_button_style)
        self.remove_btn.clicked.connect(self.remove_stock)
        row_layout.addWidget(self.remove_btn)
        
        row_layout.addStretch()
        
        self.buy_btn = QPushButton("Buy")
        self.buy_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        self.buy_btn.clicked.connect(self.handle_manual_buy)
        row_layout.addWidget(self.buy_btn)

        self.sell_btn = QPushButton("Sell")
        self.sell_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #922b21;
            }
        """)
        self.sell_btn.clicked.connect(self.handle_manual_sell)
        row_layout.addWidget(self.sell_btn)

        self.hold_btn = QPushButton("Hold")
        self.hold_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1c40f;
                color: black;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #f39c12;
            }
            QPushButton:pressed {
                background-color: #d68910;
            }
        """)
        self.hold_btn.clicked.connect(self.handle_manual_hold)
        row_layout.addWidget(self.hold_btn)

        input_main_layout.addLayout(row_layout)
        input_frame.setLayout(input_main_layout)
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
            
            # Toggle selection: if user clicked the same row again, clear selection to deselect it
            if hasattr(self, "_prev_selected_row") and self._prev_selected_row == selected_row:
                self.table.clearSelection()
                self._prev_selected_row = -1
                return
                
            self._prev_selected_row = selected_row
            # Apply premium slate-blue highlight to the entire row (transparent-friendly)
            for col in range(self.table.columnCount()):
                item = self.table.item(selected_row, col)
                if item:
                    item.setBackground(QColor("#2a4365"))
        else:
            self._prev_selected_row = -1

    def keyPressEvent(self, event):
        # Clear selection on Escape key press
        if event.key() == Qt.Key.Key_Escape:
            self.table.clearSelection()
            event.accept()
        else:
            super().keyPressEvent(event)

    def on_header_clicked(self, logical_index):
        self.sort_column = logical_index
        self.sort_order = self.table.horizontalHeader().sortIndicatorOrder()

    def show_header_context_menu(self, pos):
        menu = QMenu(self)
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        
        for i, header_text in enumerate(headers):
            action = QAction(header_text, self)
            action.setCheckable(True)
            action.setChecked(not self.table.isColumnHidden(i))
            action.triggered.connect(lambda checked, idx=i: (
                self.table.setColumnHidden(idx, not checked),
                self.table.resizeColumnsToContents()
            ))
            menu.addAction(action)
            
        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    def load_stocks(self):
        # 1. Get all stocks from the DB
        stocks = self.db_manager.get_all_stocks()
        self.table.setRowCount(len(stocks))

        for i, row in enumerate(stocks):
            sid = row[0]
            maxa = row[1]
            prof = row[2]
            drop = row[3]
            m_mode = bool(row[-1])
            
            # 3. Create the bot with the saved manual_mode state
            bot = TradingBot(
                self.ibapi, sid, maxa, prof, drop, m_mode,
                self.db_manager, self.csv_manager, self.exchange_manager, self
            )
            
            self.bots[sid] = bot
            bot.create_yf_ticker()

    def update_display(self):
        now = time.time()
        try:
            # ---------- 1. CASH + PORTFOLIO (same cadence as yfinance) ----------
            market_open = any(bot.is_market_open() for bot in self.bots.values())
            interval = self.ibapi.cash_fetch_interval if market_open else self.ibapi.max_cash_cache_age
            if now - self.ibapi.last_cash_fetch >= interval:
                self.ibapi.last_cash_fetch = now
                def fetch_cash():
                    try:
                        self.ibapi.cancelAccountSummary(9001)
                        time.sleep(0.5)
                        self.ibapi.cash_ready_event.clear()
                        self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds")
                        self.ibapi.cash_ready_event.wait(15)
                    except Exception as e:
                        logger.error(f"Error fetching cash summary in background: {e}")
                executor.submit(fetch_cash)

            # ---------- 2. EUR/USD ----------
            rate = self.exchange_manager.get_eur_usd_rate()
            self.rate_label.setText(f"EUR/USD: {rate:.3f}")

            # ---------- 3. CONNECTION + CASH + PORTFOLIO + TOTAL ----------
            if self.ibapi and hasattr(self.ibapi, 'isConnected'):
                self.connected = self.ibapi.isConnected()

            # Synchronize connection controls and trade button status based on actual connection status
            if self.connected:
                self.conn_btn.setText("Disconnect")
                self.conn_btn.setEnabled(True)
                if not self.auto_trading:
                    self.trade_btn.setEnabled(True)
            else:
                self.conn_btn.setText("Connect")
                if self.status_label.text() != "Connecting...":
                    self.conn_btn.setEnabled(True)
                self.trade_btn.setEnabled(False)

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

            self.status_label.setText(conn_text)
            self.status_label.setStyleSheet(f"color: {conn_color}; font-weight: bold;")

            if self.connected:
                self.portfolio_label.setText(
                    f"Total Value: <b>€{total_str}</b>  |  Cash: <b>€{cash_str}</b>  |  "
                    f"Portfolio: <b>€{port_str}</b>  |  Allocation: <b>{comp_str}</b>"
                )
            else:
                self.portfolio_label.setText("Total Value: €--  |  Cash: €--  |  Portfolio: €--  |  Allocation: --")
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
                bot.calculate_score()
                
                status = bot.get_status()
                volume_display = f"{bot.today_volume / 1e6:.1f}"
                # 1. Format the TPrice string with the warning emoji
                if bot.target_price > 0:
                    t_price_display = f"{bot.currency_symbol}{bot.target_price:.2f}"
                else:
                    t_price_display = "--"
                
                # --- ONE COLUMN: Latest Bank Target (Price + Name + Date) ---
                # Retrieve data from the bot
                bank_target_long = getattr(bot, 'latest_bank_target', 0)
                                
                # 1. Determine Currency Symbol
                currency_sym = "$" 
                if ".L" in bot.stock_id: currency_sym = "£"
                if ".PA" in bot.stock_id or ".DE" in bot.stock_id: currency_sym = "€"

                # 2. Format the Price: remove .00
                bank_target = f"{bank_target_long:g}" if bank_target_long else ""
                
                bank_name_long = getattr(bot, 'latest_bank_source', "--")
                abbr_map = {
                    "Morgan Stanley": "MS",
                    "JPMorgan Chase & Co.": "JPM",
                    "Goldman Sachs": "GS",
                    "Barclays": "BCS",
                    "Deutsche Bank": "DB",
                    "Bank of America": "BofA",
                    "Citigroup": "Citi",
                    "Credit Suisse": "CS",
                    "HSBC": "HSBC",
                    "RBC Capital Markets": "RBC",
                    "KeyBanc": "Key",
                    "Berenberg": "BER",
                    "Jefferies": "JEF",
                    "Wells Fargo": "WFC",
                    "Piper Sandler": "PIP",
                    "Truist Securities": "TUI",
                    "Bernstein": "AB",
                    "Mizuho": "MIZ",
                    "Nomura": "NOM",
                    "Susquehanna": "SUS",
                    "Evercore ISI": "EVR",
                    "Raymond James": "RJ",
                    "Canaccord Genuity": "CG",
                    "Stifel": "SF",
                    "BMO Capital Markets": "BMO",
                    "Oppenheimer": "OPP",
                    "Wedbush": "WED",
                    "Cowen": "COW",
                    "Needham": "NDM",
                    "Craig-Hallum": "CH",
                    "Roth Capital": "ROTH",
                    "Northland": "NLD",
                    "Loop Capital": "LOOP",
                    "Guggenheim": "GUG",
                    "Rosenblatt": "ROS",
                    "Benchmark": "BNC",
                    "Colliers Securities": "COL",
                }
                bank_name = abbr_map.get(bank_name_long, bank_name_long)

                bank_date = getattr(bot, 'latest_bank_date', "")

                short_date = bank_date
                if len(bank_date) == 10 and bank_date[4] == '-' and bank_date[7] == '-':
                    short_date = bank_date[5:]  # Get "MM-DD"

                # Create the consolidated string
                if bank_target and short_date and short_date != "--":
                    bank_note = f"{currency_sym}{bank_target} {bank_name} ({short_date})"
                elif bank_target:
                    bank_note = f"{currency_sym}{bank_target} {bank_name}"
                else:
                    bank_note = bank_name

                # Calcul de la variation journalière
                if bot.previous_close > 0:
                    price_pct = ((bot.market_value - bot.previous_close) / bot.previous_close) * 100
                else:
                    price_pct = 0.0
                    
                if bot.manual_mode:
                    status = "Hold"

                earn_display = bot.next_earnings_date
                if not earn_display or earn_display == "No payment":
                    earn_display = '--'
                elif len(earn_display) == 10 and earn_display[4] == '-' and earn_display[7] == '-':
                    earn_display = earn_display[5:]

                comp_name_display = bot.company_name[:12] + ".." if len(bot.company_name) > 14 else bot.company_name

                items = [
                    comp_name_display, sid, bot.asset_type, bot.sector,
                    f"{bot.currency_symbol}{bot.market_value:.2f}",  
                    f"{price_pct:+.2f}%",
                    t_price_display,
                    bank_note,
                    str(bot.smart_score), 
                    f"{bot.currency_symbol}{bot.fourteen_day_high:.2f}",
                    f"{bot.currency_symbol}{bot.fourteen_day_low:.2f}",
                    f"{bot.rsi_value:.0f}", 
                    f"{bot.adx_value:.0f}",
                    bot.ma_signal, 
                    bot.macd_signal,
                    volume_display,
                    str(bot.quantity),
                    f"{bot.currency_symbol}{bot.bought_price:.2f}",
                    f"{bot.currency_symbol}{bot.current_value:.0f}",
                    f"{bot.pnl_percent:+.1f}%",
                    format_currency_short(bot.cash_left, "€"),
                    format_currency_short(bot.max_amount, "€"),
                    f"{bot.profit_target*100:.1f}%",
                    f"{bot.dynamic_profit_target*100:.1f}%",
                    f"{bot.drop_threshold*100:.1f}%",
                    f"{bot.dynamic_stop_loss:.1f}%",
                    earn_display,
                    status
                ]

                for col, text in enumerate(items):
                    item = QTableWidgetItem(text)
                    if col == 11:  # RSI column
                        try:
                            rsi_val = float(text)
                            if rsi_val > 70:
                                item.setForeground(QColor("red"))  # Overbought, good to sell
                            elif rsi_val < 30:
                                item.setForeground(QColor("green"))  # Oversold, good to buy
                        except ValueError:
                            pass
                    elif col == 12:  # ADX column
                        try:
                            adx_val = float(text)
                            if adx_val >= 25:
                                item.setForeground(QColor("green"))  # Strong trend
                            else:
                                item.setForeground(QColor("orange"))  # Choppy
                        except ValueError:
                            pass
                    elif col == 15:  # Volume column
                        if bot.today_volume > 1.5 * bot.avg_volume_14d:
                            item.setForeground(QColor("green"))
                    elif col == 5: # Price%
                        if price_pct > 0:
                            item.setForeground(QColor("green"))
                        elif price_pct < 0:
                            item.setForeground(QColor("red"))
                    elif col == 8:
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
                    elif col == 6 and bot.target_price > 0:
                        if bot.market_value < bot.target_price:
                        # Undervalued (Good for Buy) -> Green
                            item.setForeground(QColor("green"))
                        elif bot.market_value > bot.target_price:
                            # Overvalued (Above Analyst Target) -> Red
                            item.setForeground(QColor("red"))
                    elif col == 7 and bank_target_long > 0:
                        if bot.market_value < bank_target_long:
                        # Undervalued (Good for Buy) -> Green
                            item.setForeground(QColor("green"))
                        elif bot.market_value > bank_target_long:
                            # Overvalued (Above Analyst Target) -> Red
                            item.setForeground(QColor("red"))
                    elif col == 19: # PnL%
                        if bot.pnl_percent > 0:
                            item.setForeground(QColor("green"))
                        elif bot.pnl_percent < 0:
                            item.setForeground(QColor("red"))
                    elif col == 26:  # Earnings column
                        if bot.next_earnings_date:
                            try:
                                earn_date = datetime.strptime(bot.next_earnings_date, "%Y-%m-%d").date()
                                current_date = datetime.now().date()
                                delta = (earn_date - current_date).days
                                if 0 <= delta <= 30:  # Within 30 days (including today)
                                    item.setForeground(QColor("green"))  # Warning color
                            except ValueError:
                                pass  # Invalid date format; skip coloring
                    elif "BUY" in text or "BULL" in text:
                        item.setForeground(QColor("green"))   # Bullish signal, indicating to buy
                    elif "SELL" in text or "BEAR" in text:
                        item.setForeground(QColor("red"))  # Bearish signal, indicating to sell
                    elif "Closed" in text:
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

            # Automatically and dynamically resize all columns to prevent text truncation
            self.table.resizeColumnsToContents()

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
            self.status_label.setText("Connecting...")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.conn_btn.setEnabled(False)
            
            def connect_task():
                try:
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

                    if self.ibapi.connected_event.wait(12):
                        self.connected = True
                        try:
                            self.ibapi.reqPositions()
                        except Exception as e:
                            logger.error(f"Error requesting positions: {e}")
                        
                        try:
                            # ---- INITIAL CASH ----
                            self.ibapi.cash_ready_event.clear()
                            self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds")
                            if self.ibapi.cash_ready_event.wait(8):
                                self.ibapi.last_cash_fetch = time.time()
                        except Exception as e:
                            logger.error(f"Error requesting account summary: {e}")
                        
                        QTimer.singleShot(0, lambda: self._on_connect_success())
                    else:
                        QTimer.singleShot(0, lambda: self._on_connect_fail())
                except Exception as e:
                    logger.error(f"Connection task failed: {e}")
                    self.connected = False
                    QTimer.singleShot(0, lambda: self._on_connect_fail())
                    
            threading.Thread(target=connect_task, daemon=True).start()

    def _on_connect_success(self):
        self.status_label.setText("Connected")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        self.conn_btn.setText("Disconnect")
        self.conn_btn.setEnabled(True)
        self.trade_btn.setEnabled(True)

    def _on_connect_fail(self):
        self.status_label.setText("Conn. failed")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.conn_btn.setText("Connect")
        self.conn_btn.setEnabled(True)

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
            threading.Thread(target=self.trading_loop, daemon=True).start()

    def manual_refresh_data(self):
        # 1. Disable the update button and change text for visual feedback
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Updating...")

        # 2. Reset indicator caches and trigger manual fetches
        for sid, bot in self.bots.items():
            bot.last_yf_fetch = 0
            bot.last_indicators_fetch = 0
            bot.calculate_technical_indicators(force=True)
            bot.get_market_value()
            bot.get_bank_note(run_async=True, force=True)

        # 3. Request fresh values from IBKR if connected
        if self.connected and self.ibapi:
            try:
                self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,AvailableFunds")
                self.ibapi.reqPositions()
            except Exception as e:
                logger.error(f"Error requesting manual update from IBKR: {e}")

        # 4. Trigger a GUI table refresh immediately
        self.update_display()

        # 5. Restore the button state after 1.5 seconds
        QTimer.singleShot(1500, self.reset_update_btn)

    def reset_update_btn(self):
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Update")

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
            
            bot = TradingBot(
                self.ibapi, sid, max_amt, prof, drop,
                manual_mode=False,                 
                db_manager=self.db_manager,         
                csv_manager=self.csv_manager,
                exchange_manager=self.exchange_manager,
                app=self
            )
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
            
    def get_selected_bot(self):
        """Helper to identify which stock is selected in the table."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Required", "Please select a stock from the table first.")
            return None
        
        # Get the row index of the selection
        row = selected_items[0].row()
        # Symbol is in the second column (index 1)
        symbol = self.table.item(row, 1).text()
        return self.bots.get(symbol)

    def handle_manual_buy(self):
        bot = self.get_selected_bot()
        if bot:
            reply = QMessageBox.question(self, 'Confirm', f"Execute manual BUY for {bot.stock_id}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                logger.info(f"User triggered manual BUY for {bot.stock_id}")
                bot.place_buy_order()

    def handle_manual_sell(self):
        bot = self.get_selected_bot()
        if bot:
            if bot.quantity <= 0:
                QMessageBox.warning(self, "Error", "You don't own any shares to sell!")
                return
            reply = QMessageBox.question(self, 'Confirm', f"Execute manual SELL for {bot.stock_id}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                logger.info(f"User triggered manual SELL for {bot.stock_id}")
                bot.place_sell_order()

    def handle_manual_hold(self):
        bot = self.get_selected_bot()
        if bot:
            bot.manual_mode = not bot.manual_mode

            # Save the new state to the database
            with self.db_manager.get_cursor() as cursor:
                cursor.execute(
                    "UPDATE stocks SET manual_mode = ? WHERE stock_id = ?", # Fixed column name
                    (1 if bot.manual_mode else 0, bot.stock_id)
                )

            state = "MANUAL/HOLD" if bot.manual_mode else "AUTOMATED"
            logger.info(f"Bot {bot.stock_id} is now in {state} mode (Saved to DB).")
            self.update_display()
            
    def open_csv(self):
        if os.path.exists("trading_orders_history.csv"):
            os.startfile("trading_orders_history.csv")
        else:
            QMessageBox.information(self, "Info", "No trades yet.")
    
    def closeEvent(self, event):
        logger.info("Shutting down application...")
    
        #   1. Stop all bots
        self.auto_trading = False
        for bot in self.bots.values():
            bot.stop()
        
        # 2. Disconnect IBKR
        if self.connected:
            self.ibapi.disconnect()
        
        # 3. Shutdown Executor (Global)
        executor.shutdown(wait=False) # Prevent new tasks
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TradingApp()
    window.showMaximized()  # maximized window with title bar visible
    sys.exit(app.exec())