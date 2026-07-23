from config import *
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
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    stock_id TEXT PRIMARY KEY,
                    max_amount REAL NOT NULL,
                    profit_target REAL NOT NULL,
                    drop_threshold REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    manual_mode INTEGER DEFAULT 0,
                    last_rejection_time REAL DEFAULT 0,
                    is_auto_watchlist INTEGER DEFAULT 0
                )
            """)
            try:
                cursor.execute("ALTER TABLE stocks ADD COLUMN last_rejection_time REAL DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # column already exists

            try:
                cursor.execute("ALTER TABLE stocks ADD COLUMN is_auto_watchlist INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # column already exists

            try:
                cursor.execute("ALTER TABLE stocks ADD COLUMN highest_pnl REAL DEFAULT 0.0")
            except sqlite3.OperationalError:
                pass

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
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ignored_stocks (
                    stock_id TEXT PRIMARY KEY
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
            
    def get_setting(self, key, default=None):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return default

    def set_setting(self, key, value):
        with self.get_cursor() as cursor:
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            
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
        
    def add_stock(self, stock_id, max_amount, profit_target, drop_threshold, manual_mode=0, is_auto_watchlist=0):
        """Add or update stock in watchlist"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT OR REPLACE INTO stocks (stock_id, max_amount, profit_target, drop_threshold, manual_mode, last_rejection_time, highest_pnl, is_auto_watchlist, updated_at)
                   VALUES (?, ?, ?, ?, ?, 0, 0.0, ?, CURRENT_TIMESTAMP)""",
                (stock_id, max_amount, profit_target, drop_threshold, manual_mode, is_auto_watchlist)
            )

    def get_all_stocks(self):
        """Get all stocks in watchlist"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT stock_id, max_amount, profit_target, drop_threshold, manual_mode, last_rejection_time, highest_pnl, is_auto_watchlist FROM stocks")
            return cursor.fetchall()

    def update_highest_pnl(self, stock_id, pnl):
        """Update highest PnL for trailing stop lock"""
        with self.get_cursor() as cursor:
            cursor.execute(
                "UPDATE stocks SET highest_pnl = ? WHERE stock_id = ?",
                (pnl, stock_id)
            )

    def update_last_rejection_time(self, stock_id, timestamp):
        """Update last rejection time for a stock"""
        with self.get_cursor() as cursor:
            cursor.execute(
                "UPDATE stocks SET last_rejection_time = ? WHERE stock_id = ?",
                (timestamp, stock_id)
            )

    def remove_stock(self, stock_id):
        """Remove stock from watchlist"""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM stocks WHERE stock_id = ?", (stock_id,))

    def add_ignored_stock(self, stock_id: str):
        with self.get_cursor() as cursor:
            cursor.execute("INSERT OR IGNORE INTO ignored_stocks (stock_id) VALUES (?)", (stock_id,))
            
    def remove_ignored_stock(self, stock_id: str):
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM ignored_stocks WHERE stock_id = ?", (stock_id,))
            
    def get_ignored_stocks(self) -> set:
        with self.get_cursor() as cursor:
            cursor.execute("SELECT stock_id FROM ignored_stocks")
            return {row[0] for row in cursor.fetchall()}

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

    def get_setting(self, key, default=None):
        """Get a global setting value from the database"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
                row = cursor.fetchone()
                return row[0] if row else default
        except Exception as e:
            logger.error(f"Error getting setting {key}: {e}")
            return default

    def set_setting(self, key, value):
        """Set or update a global setting value in the database"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")

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


