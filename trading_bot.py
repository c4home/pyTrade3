from config import *
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
    
    # Class-level macro guard variables
    _macro_cache = {'time': 0, 'drop_pct': 0.0, 'status': 'GREEN'}
    _macro_lock = threading.Lock()
    MACRO_TICKER = "^GSPC"  # S&P 500 Index
    MACRO_DROP_LIMIT = -0.015  # -1.5% drop blocks DIP buys
    
    def __init__(self, ibapi, stock_id, max_amount, profit_target, drop_threshold,manual_mode=False,
                 db_manager=None, csv_manager=None, exchange_manager=None, gui=None, is_auto_watchlist=False):
        self.ibapi = ibapi
        self.stock_id = stock_id
        self.ibkr_symbol = re.sub(r'\..*$', '', stock_id)
        self.max_amount = max_amount
        self.profit_target = profit_target / 100
        self.drop_threshold = drop_threshold / 100
        self.db_manager = db_manager
        self.csv_manager = csv_manager
        self.exchange_manager = exchange_manager
        self.app = gui  # Reference to main app

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
        self.prev_macd_signal = ""  # Track MACD transitions for crossover detection
        self.prev_ma_signal = ""    # Track MA transitions

        self.next_earnings_date = None
        
        self.last_sell_time = 0          
        self.last_buy_time = 0           
        self.last_cooldown_warning_time = 0
        self.cooldown_warning_interval = 7200  # Log once per hour (in seconds)

        # ---- Dynamic Profit Target ----        
        self.atr_multiplier = 1.5  # Tune this (1-2x for conservative/aggressive)
        self.min_profit_pct = profit_target   # Floor to avoid tiny targets
        self.max_profit_pct = 15.0  # Cap to limit hold time/risk
        self.dynamic_profit_target = self.profit_target  # Start with DB value, override dynamically

        # ---- Dynamic Stop Loss ----     
        self.stop_multiplier = 2.3  # Optimized from 2.5
        self.max_stop_loss = -12.0  # Optimized from -15.0
        self.min_stop_loss = -3.0   # Hard ceiling (minimum stop to avoid "noise" exits)
        self.dynamic_stop_loss = self.drop_threshold # Starting default value

        self.asset_type = "UNKNOWN"
        self.sector = "N/A"

        self.today_volume = 0
        self.avg_volume_14d = 0
        
        self.previous_close = 0
        self.close_3d_ago = 0.0
        
        self.last_bank_update = None
        
        self.manual_mode = manual_mode  # If True, automated signals are ignored
        self.is_auto_watchlist = is_auto_watchlist
        
        self.target_price = 0
        self.highest_pnl = 0.0
        self.last_rejection_time = 0
        self._last_sell_log = {}  # Throttle sell-condition log messages {reason_key: timestamp}

        self.create_yf_ticker()

    @property
    def min_cash(self):
        """Get the global minimum cash setting from the main app."""
        if self.app:
            return getattr(self.app, 'min_cash', 0.0)
        return 0.0

    def create_yf_ticker(self):
        info_dict = self.db_manager.get_company_info(self.stock_id)
        self.company_name = info_dict["company_name"]
        self.asset_type = info_dict["asset_type"]
        self.sector = info_dict["sector"]
        self.currency = info_dict["currency"]
        self.currency_symbol = {"USD": "$", "EUR": "€", "GBP": "£", "GBp": "£", "HKD": "HK$"}.get(self.currency, "$")
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
            self.previous_close = cached_ind.get("prev_close") or 0.0
            self.day_before_yesterday_close = cached_ind.get("day_before_yesterday_close") or 0.0
            self.target_price = cached_ind.get("target_mean_price") or 0.0
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

    def is_market_cooling_down(self, cooldown_minutes=15):
        """Returns True if the market just opened and is within the cooldown period."""
        try:
            tz = ZoneInfo(self.exchange_tz_name)
            now = datetime.now(tz)
            if now.weekday() >= 5:
                return False
            current_time = now.time()

            if 'America/New_York' in self.exchange_tz_name:
                market_open = dtime(9, 30)
                cooldown_end = dtime(9, 30 + cooldown_minutes)
            else:
                market_open = dtime(9, 0)
                cooldown_end = dtime(9, cooldown_minutes)

            return market_open <= current_time < cooldown_end
        except:
            return False
            
    def get_projected_volume(self):
        """Estimates the final daily volume based on how much time has passed since market open."""
        if self.today_volume <= 0:
            return 0
            
        try:
            tz = ZoneInfo(self.exchange_tz_name)
            now = datetime.now(tz)
            
            if now.weekday() >= 5:
                return self.today_volume
                
            current_time = now.time()
            if 'America/New_York' in self.exchange_tz_name:
                market_open = dtime(9, 30)
                market_close = dtime(16, 0)
            else:
                market_open = dtime(9, 0)
                market_close = dtime(17, 30)

            # If market hasn't opened yet, or has already closed, use today_volume directly
            if current_time < market_open or current_time > market_close:
                return self.today_volume
                
            total_minutes = (market_close.hour * 60 + market_close.minute) - (market_open.hour * 60 + market_open.minute)
            elapsed_minutes = (current_time.hour * 60 + current_time.minute) - (market_open.hour * 60 + market_open.minute)
            
            if elapsed_minutes <= 0:
                return self.today_volume
                
            # Floor to 30 mins to avoid crazy spikes right at 9:31 AM
            effective_elapsed = max(30, elapsed_minutes)
            return self.today_volume * (total_minutes / effective_elapsed)
        except:
            return self.today_volume

    @staticmethod
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
                def async_fetch(_force=force):
                    try:
                        self.fetch_fresh_bank_note(fallback, force=_force)
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
            return self.fetch_fresh_bank_note(fallback, force=force)

    def fetch_fresh_bank_note(self, fallback=None, max_age_hours=24, force=False):
        # 1. Check if we have recent cached data to avoid redundant API requests
        # Skip this check if force=True (e.g. user clicked the Update button)
        if self.db_manager and not force:
            cached_data = self.db_manager.get_cached_bank_note(self.stock_id)
            if cached_data:
                price, source, date_str, last_updated = cached_data
                if last_updated:
                    try:
                        if isinstance(last_updated, str):
                            if "." in last_updated:
                                last_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S.%f")
                            else:
                                last_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
                        else:
                            last_dt = last_updated
                            
                        if (datetime.now() - last_dt).total_seconds() < (max_age_hours * 3600):
                            logger.info(f"Using cached analyst targets for {self.stock_id} (fetched < {max_age_hours}h ago)")
                            self.latest_bank_target = price
                            self.latest_bank_source = source
                            self.latest_bank_date = date_str
                            return price, source, date_str
                    except Exception as e:
                        logger.warning(f"Error parsing cache date for {self.stock_id}: {e}")

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
                    ticker_obj = yf.Ticker(self.stock_id)
                    data = ticker_obj.history(
                        period="1y", 
                        interval="1d", 
                        auto_adjust=False,
                        actions=False
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
                    
                    close = close.dropna()
                    high = high.dropna()
                    low = low.dropna()
                    volume = volume.dropna()
                    
                    if len(close) >= 2:
                        last_date = close.index[-1].date()
                        today = pd.Timestamp.now(tz=close.index.tz).date()
                        self.is_last_date_today = (last_date == today)
                        idx = -2 if self.is_last_date_today else -1
                        
                        self.previous_close = float(close.iat[idx])
                        
                        if len(close) >= abs(idx) + 1:
                            self.day_before_yesterday_close = float(close.iat[idx - 1])
                        else:
                            self.day_before_yesterday_close = self.previous_close
                            
                        if len(close) >= abs(idx) + 3:
                            self.close_3d_ago = float(close.iat[idx - 3])
                        else:
                            self.close_3d_ago = self.previous_close
         
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
         
                    new_ma_signal = ""
                    if price > ma20 > ma50 > ma200:
                        new_ma_signal = "S_BULL"
                    elif price > ma20 and ma20 > ma50:
                        new_ma_signal = "BULL"
                    elif price > ma50:
                        new_ma_signal = "N_BULL"
                    elif price < ma20 and ma20 < ma50:
                        new_ma_signal = "BEAR"
                    elif price < ma50:
                        new_ma_signal = "N_BEAR"
                    else:
                        new_ma_signal = "NEUTRAL"
                        
                    # Track actual transitions for email notifications
                    if getattr(self, 'ma_signal', '') and self.ma_signal != new_ma_signal:
                        self.prev_ma_signal = self.ma_signal
                    self.ma_signal = new_ma_signal
         
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
         
                    # Reusing ticker_obj defined above
                    self.next_earnings_date = self.fetch_next_event_date(ticker_obj)
                    
                    try:
                        # Only fetch .info (which is heavily rate limited) once per 24h or if target is missing
                        now_time = time.time()
                        last_info = getattr(self, '_last_info_fetch', 0)
                        if (now_time - last_info > 86400) or getattr(self, 'target_price', 0) <= 0:
                            self.target_price = ticker_obj.info.get('targetMeanPrice', 0)
                            self.num_analysts = ticker_obj.info.get('numberOfAnalystOpinions', 0)
                            self._last_info_fetch = now_time
                    except Exception as info_err:
                        logger.warning(f"Failed to fetch yfinance .info for {self.stock_id}: {info_err}")
                    
                    self.db_manager.update_cached_indicators(
                        self.stock_id, self.fourteen_day_high, self.fourteen_day_low,
                        self.rsi_value, self.adx_value, self.bb_upper, self.bb_middle, self.bb_lower,
                        self.ma_signal, self.macd_signal,
                        self.next_earnings_date, self.today_volume, self.avg_volume_14d,
                        self.previous_close, self.target_price, self.num_analysts,
                        getattr(self, 'day_before_yesterday_close', 0.0)
                    )
                    
                    self.update_analyst_data(run_async=False)
                    self.last_indicators_fetch = time.time()
                    
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
                    if self.ibapi and hasattr(self.ibapi, 'data_lock'):
                        with self.ibapi.data_lock:
                            self.market_value = round(price, 2)
                    else:
                        self.market_value = round(price, 2)
                    self.db_manager.update_latest_price(self.stock_id, price)
            except:
                pass
            finally:
                self._fetching_market_value = False
        executor.submit(fetch)
        return self.market_value

    def _calculate_dynamic_max_amount(self):
        if not getattr(self, 'db_manager', None):
            return self.max_amount
            
        global_acc_str = self.db_manager.get_setting("global_account_value", "14000")
        risk_pct_str = self.db_manager.get_setting("risk_per_trade_pct", "1.0")
        
        try:
            global_acc = float(global_acc_str)
            risk_pct = float(risk_pct_str)
        except ValueError:
            global_acc = 14000.0
            risk_pct = 1.0
            
        if risk_pct <= 0:
            return self.max_amount
            
        risk_euro = global_acc * (risk_pct / 100.0)
        
        stop_loss_dist = abs(self.dynamic_stop_loss) / 100.0
        if stop_loss_dist < 0.01:
            stop_loss_dist = 0.01
            
        dynamic_max = risk_euro / stop_loss_dist
        
        # Ensure we can always afford at least 1 share
        if hasattr(self, 'get_native_currency_and_exchange') and self.market_value > 0:
            try:
                native_currency, _ = self.get_native_currency_and_exchange()
                rate = self.exchange_manager.get_rate(native_currency)
                market_val_eur = self.market_value / rate if rate > 0 else self.market_value
                if dynamic_max < market_val_eur:
                    dynamic_max = market_val_eur
            except Exception:
                pass
        
        # Different caps based on asset type
        if hasattr(self, 'asset_type') and self.asset_type.upper() in ["ETF", "ETC"]:
            max_cap_pct = 0.35
        else:
            max_cap_pct = 0.18
            
        cap_limit = global_acc * max_cap_pct
        if dynamic_max > cap_limit:
            dynamic_max = cap_limit
            
        return dynamic_max

    def update_position(self):
        with self.ibapi.data_lock:
            pos = self.ibapi.positions.get(self.ibkr_symbol, {})
            self.quantity = pos.get('position', 0)
            self.bought_price = pos.get('avgCost', 0)
            # Use native IBKR portfolio data if available
            ib_market_price = pos.get('marketPrice')
            ib_market_value = pos.get('marketValue')
            
            if ib_market_price is not None and ib_market_price > 0:
                self.current_value = ib_market_value if ib_market_value is not None else (self.quantity * ib_market_price)
                self.pnl_percent = ((ib_market_price - self.bought_price) / self.bought_price * 100) if self.bought_price > 0 else 0
            else:
                # Fallback to Yahoo Finance calculation
                comp_bought_price = self.bought_price
                if self.currency == "GBp":
                    comp_bought_price = self.bought_price * 100.0
                self.current_value = self.quantity * self.market_value if self.quantity > 0 else 0
                if self.currency == "GBp":
                    self.current_value = self.current_value / 100.0
                self.pnl_percent = ((self.market_value - comp_bought_price) / comp_bought_price * 100) if comp_bought_price > 0 else 0
            if self.quantity == 0:
                if self.highest_pnl != 0.0:
                    self.highest_pnl = 0.0
                    if self.db_manager:
                        self.db_manager.update_highest_pnl(self.stock_id, 0.0)

        # Calculate invested in EUR for THIS stock only
        if self.quantity > 0 and self.bought_price > 0:
            native_invested = self.quantity * self.bought_price
            native_currency, _ = self.get_native_currency_and_exchange()
            rate = self.exchange_manager.get_rate(native_currency)
            eur_invested = native_invested / rate if rate > 0 else native_invested
        else:
            eur_invested = 0.0

        self.current_max_investment = self._calculate_dynamic_max_amount()
        self.cash_left = self.current_max_investment - eur_invested
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
                email_success = self.app.send_trade_email(
                    symbol=self.stock_id,
                    action=action,
                    quantity=int(filled),
                    price=actual_price,
                    native_currency=currency,
                    reason=reason,
                    bot=self
                )
                if email_success:
                    logger.info(f"Email sent: {action} {int(filled)} @ {actual_price:.2f}")
                else:
                    logger.warning(f"Email failed to send: {action} {int(filled)} @ {actual_price:.2f}")

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
            self.last_rejection_time = time.time()
            if self.db_manager:
                self.db_manager.update_last_rejection_time(self.stock_id, self.last_rejection_time)
            if self.csv_manager:
                self.csv_manager.update_order_status(order_id, "CANCELLED")

        elif status == "Inactive":
            logger.error(f"Order {order_id} rejected/inactive")
            self.last_rejection_time = time.time()
            if self.db_manager:
                self.db_manager.update_last_rejection_time(self.stock_id, self.last_rejection_time)
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
        usable_cash = self.ibapi.available_cash - self.min_cash
        if not self.is_market_open() or self.has_pending_order() or min(self.cash_left, usable_cash) < self.MIN_CASH_FOR_BUY:
            return False
        
        # PDT check removed from buys to allow overnight positions

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

        # Use the MINIMUM of max_amount, cash_left, and usable cash
        usable_cash_clamped = max(0.0, usable_cash)
        effective_limit = min(self.max_amount, self.cash_left, usable_cash_clamped) * self.CASH_BUFFER_MULTIPLIER

        if total_cost_eur > effective_limit:
            # Recalculate to stay under BOTH max_amount AND available cash
            max_native = effective_limit * rate
            quantity = int(max_native / price_native)
            if quantity < 1:
                logger.warning(f"Insufficient funds (Quantity < 1)")
                return False

        # === 6. BUILD REASON ===
        if hasattr(self, 'last_trade_reason') and self.last_trade_reason:
            reason = self.last_trade_reason
        else:
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
        order.algoStrategy = "Adaptive"
        order.algoParams = []
        order.algoParams.append(TagValue("adaptivePriority", "Normal"))
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

        if hasattr(self, 'last_trade_reason') and self.last_trade_reason:
            reason = self.last_trade_reason
        else:
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
        order.algoStrategy = "Adaptive"
        order.algoParams = []
        order.algoParams.append(TagValue("adaptivePriority", "Normal"))
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
        Step 1: Try yfinance upgrades/downgrades (fast, cached).
        Step 2: Fall back to UBS research web scraping if yfinance is missing/stale.
        Returns: (target_price, description, date_string) or (None, error_msg, None)
        """
        # Step 1: Try yfinance first
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.upgrades_downgrades
            if df is not None and not df.empty:
                ubs_names = ['ubs', 'ubs group', 'ubs ag']
                ubs_data = df[df['Firm'].str.lower().isin(ubs_names)]
                if not ubs_data.empty:
                    latest = ubs_data.sort_index().iloc[-1]
                    target_val = latest.get('currentPriceTarget')
                    date_str = latest.name.strftime('%Y-%m-%d')
                    if pd.notnull(target_val) and target_val != 0:
                        days_old = (datetime.now() - latest.name.to_pydatetime().replace(tzinfo=None)).days
                        if days_old <= 30:
                            logger.info(f"[UBS yfinance] {symbol} target ${target_val} is fresh ({days_old}d old). Using it.")
                            return float(target_val), f"Target: ${float(target_val)}", date_str
                        else:
                            logger.info(f"[UBS yfinance] {symbol} target is stale ({days_old}d old). Trying web scrape for fresher data...")
        except Exception as e:
            logger.warning(f"yfinance UBS lookup failed for {symbol}: {e}")

        # Step 2: Web scraping fallback for stocks with known UBS research URLs
        logger.info(f"Attempting UBS web scrape for {symbol}...")

        # Load UBS URL map from ubs_links.json (edit that file to add new stocks)
        _ubs_links_path = os.path.join(os.path.dirname(__file__), 'ubs_links.json')
        try:
            import json
            with open(_ubs_links_path, 'r') as _f:
                ubs_url_map = {k: v for k, v in json.load(_f).items() if not k.startswith('_')}
        except Exception as _e:
            logger.warning(f"Could not load ubs_links.json: {_e}")
            ubs_url_map = {}

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
            table = soup.find('table')
            if not table:
                return None, "No table found on UBS page", None

            rows = table.find_all('tr')[1:]  # Skip header
            if not rows:
                return None, "No data rows on UBS page", None

            # Latest data is in the last row; structure: Date | Price | Target | Rating
            latest_row = rows[-1]
            cols = latest_row.find_all('td')
            if len(cols) < 3:
                return None, "Unexpected UBS table structure", None

            date = cols[0].get_text(strip=True)
            target_price_str = cols[2].get_text(strip=True).replace(',', '').replace('€', '').replace('$', '').strip()

            target_price = float(target_price_str)
            logger.info(f"[UBS Scrape] {symbol} Target: {target_price} (Date: {date})")
            return target_price, f"Target: {target_price}", date

        except (ValueError, IndexError) as e:
            logger.error(f"UBS scrape parse error for {symbol}: {e}")
            return None, "Scrape parse failure", None
        except Exception as e:
            logger.error(f"UBS scrape request error for {symbol}: {e}")
            return None, f"Scrape error: {e}", None

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
            return 0, ""

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
            return 0, ""

        weighted_target = weighted_sum / total_weight
        upside_pct = (weighted_target - self.market_value) / self.market_value

        # 3. Score Mapping
        modifier = 0
        note = ""
        
        if upside_pct > 0.20: 
            modifier = 3 if total_weight > 2 else 2 # Extra point if high conviction
            note = f", Analyst: {modifier:+d} (Strong-Upside)"
        elif upside_pct > 0.10:
            modifier = 1
            note = f", Analyst: +1 (Fair-Upside)"
        elif upside_pct < -0.05:
            modifier = -2
            note = f", Analyst: -2 (Overvalued)"
            
        return modifier, note
        
    def calculate_score(self):
        """
        Calculates the Smart Score (0-12) using multi-factor analysis.
        Updates self.smart_score and self.score_reason.
        """
        if self.fourteen_day_high <= 0 or self.market_value <= 0:
            self.smart_score = 0
            self.score_reason = "Insufficient Data"
            self.target_upside_pct = 0.0
            return

        self.score_reason = ""
        self.target_upside_pct = 0.0
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
        dip_details = []
        
        # 1. RSI (Oscillator) - Max 4 points
        if self.rsi_value < 25: 
            dip_points += 4
            dip_details.append("RSI<25: +4")
        elif self.rsi_value < 30: 
            dip_points += 3
            dip_details.append("RSI<30: +3")
        elif self.rsi_value < 40: 
            dip_points += 2
            dip_details.append("RSI<40: +2")
        
        # 2. Bollinger Bands (Volatility) - Max 3 points
        if hasattr(self, 'bb_pct_b'):
            if self.bb_pct_b < 0:      
                dip_points += 3
                dip_details.append("BB<0: +3")
            elif self.bb_pct_b < 0.1:  
                dip_points += 2
                dip_details.append("BB<0.1: +2")
            elif self.bb_pct_b < 0.2:  
                dip_points += 1
                dip_details.append("BB<0.2: +1")
            
        # 3. Context (Trend) - Max 3 points
        dip_points += trend_score  
        if trend_score > 0:
            dip_details.append(f"Trend: +{trend_score}")
        
        # Total Dip Score = RSI(4) + BB(3) + Trend(3) = 10 max
        
        # --- STRATEGY B: MOMENTUM (Breakout) ---
        mom_points = 0
        mom_details = []
        
        # 1. MACD & Signal - Max 3 points
        if "S_BULL" in self.macd_signal: 
            mom_points += 3
            mom_details.append("MACD(S_BULL): +3")
        elif "BULL" in self.macd_signal: 
            mom_points += 2
            mom_details.append("MACD(BULL): +2")
        
        # 2. ADX (Trend Strength & Directional Guard) - Max 2 points
        # Only award points if the stock is in an uptrend (price above 50 SMA)
        ma50 = self.get_ma50()
        if self.market_value > ma50:
            if self.adx_value > 35: 
                mom_points += 2
                mom_details.append("ADX>35: +2")
            elif self.adx_value > 25: 
                mom_points += 1
                mom_details.append("ADX>25: +1")
        
        # 3. Volume Support - Max 2 points
        projected_vol = self.get_projected_volume()
        
        if projected_vol > self.avg_volume_14d * 1.5:
            mom_points += 2
            mom_details.append("ProjVol>1.5x: +2")
        elif projected_vol > self.avg_volume_14d:
            mom_points += 1
            mom_details.append("ProjVol>Avg: +1")
            
        # 4. RSI Sweet Spot (Not too high) - Max 3 points
        if 50 <= self.rsi_value <= 70:
            mom_points += 3
            mom_details.append("RSI(50-70): +3")
        elif 40 <= self.rsi_value <= 50:
            mom_points += 1 # Weak momentum
            mom_details.append("RSI(40-50): +1")
            
        # Total Momentum Score = MACD(3) + ADX(2) + Vol(2) + RSI(3) = 10 max

        # --- SELECTION ---
        if dip_points >= mom_points:
            self.base_score = dip_points
            current_strategy = "DIP"
            self.current_strategy = "DIP"
            base_details = ", ".join(dip_details)
        else:
            self.base_score = mom_points
            current_strategy = "MOMENTUM"
            self.current_strategy = "MOMENTUM"
            base_details = ", ".join(mom_details)
            
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

            self.target_upside_pct = (temp_target - self.market_value) / self.market_value

            # --- COMBINED UNDER/OVERVALUATION LOGIC ---
            
            # CASE A: Price is LOWER than Target (Undervalued)
            if self.market_value <= (temp_target * 0.80):
                target_bonus = 3
                self.score_reason += f", Bank Target: +3 (20%+ Upside vs {final_target})"
            elif self.market_value <= (temp_target * 0.90):
                target_bonus = 2
                self.score_reason += f", Bank Target: +2 (10%+ Upside vs {final_target})"
            elif self.market_value < temp_target:
                target_bonus = 1
                self.score_reason += ", Bank Target: +1 (Below Target)"

            # CASE B: Price is HIGHER than Target (Overvalued)
            elif self.market_value >= (temp_target * 1.20):
                target_bonus = -3
                self.score_reason += f", Bank Target: -3 (20%+ Overvalued vs {final_target})"
            elif self.market_value >= (temp_target * 1.10):
                target_bonus = -2
                self.score_reason += f", Bank Target: -2 (10%+ Overvalued vs {final_target})"
            elif self.market_value > temp_target:
                target_bonus = -1
                self.score_reason += ", Bank Target: -1 (Above Target)"

        # --- FINAL SCORE CALCULATION ---
        self.smart_score = self.base_score + analyst_mod + target_bonus

        # Boost ETF/ETC score to offset lack of volatility and analyst targets
        if hasattr(self, 'asset_type') and self.asset_type in ["ETF", "ETC"]:
            self.smart_score += 6
            self.score_reason += ", ETF/ETC Baseline: +6"

        # Cap limits
        self.smart_score = max(0, min(12, int(self.smart_score)))
        
        bonus_reason = self.score_reason
        base_breakdown = f"{base_details}" if base_details else ""
        self.score_reason = f"[{current_strategy}] Score: {self.smart_score}/12 {{{base_breakdown}{analyst_note}{bonus_reason}}}".strip()
        return self.smart_score

    @classmethod
    def check_macro_guard(cls):
        """Fetches S&P 500 drop % with a 5-minute cache to prevent API spam."""
        now = time.time()
        with cls._macro_lock:
            if now - cls._macro_cache['time'] > 300: # 5 minutes cache
                try:
                    ticker = yf.Ticker(cls.MACRO_TICKER)
                    hist = ticker.history(period="2d")
                    if len(hist) >= 2:
                        prev_close = hist['Close'].iloc[-2]
                        current_price = hist['Close'].iloc[-1]
                        drop_pct = (current_price - prev_close) / prev_close
                        cls._macro_cache['drop_pct'] = drop_pct
                        if drop_pct <= cls.MACRO_DROP_LIMIT:
                            cls._macro_cache['status'] = f"RED ({drop_pct*100:.2f}%)"
                        else:
                            cls._macro_cache['status'] = f"GREEN ({drop_pct*100:.2f}%)"
                except Exception as e:
                    logger.error(f"Error fetching Macro status: {e}")
                cls._macro_cache['time'] = now
        return cls._macro_cache
         
    def check_trading_conditions(self):
        # Skip automated trading if an order was rejected/inactive recently (1 hour cooldown)
        last_rej = getattr(self, 'last_rejection_time', 0) or 0
        if last_rej > 0:
            if time.time() - last_rej < 3600:
                return None

        self.update_analyst_data(run_async=True)
            
        # If background data fetches are still running, skip trading logic this tick to avoid blocking the UI
        if (getattr(self, '_fetching_market_value', False) or 
            getattr(self, '_fetching_indicators', False) or 
            getattr(self, '_fetching_bank_note', False)):
            return None
        
        # Safety guards
        if self.fourteen_day_high <= 0 or self.market_value <= 0:
            return None

        # Run Score Calculation first to determine active strategy regime (DIP or MOMENTUM)
        self.calculate_score()

        # Update dynamic target & strategy-specific dynamic stop loss
        atr = self.get_atr_14()
        if atr > 0:
            atr_pct = (atr / self.market_value) * 100
            dynamic_target_pct = self.atr_multiplier * atr_pct
            self.dynamic_profit_target = max(self.min_profit_pct, min(dynamic_target_pct, self.max_profit_pct)) / 100
            
            raw_stop_pct = self.stop_multiplier * atr_pct
            # Strategy-Specific Stop Caps: DIP = -7.0% (fast bounce required), MOMENTUM = -9.0% (more room for breakouts)
            max_stop_cap = 7.0 if getattr(self, 'current_strategy', 'DIP') == 'DIP' else 9.0
            self.dynamic_stop_loss = -max(abs(self.min_stop_loss), min(raw_stop_pct, max_stop_cap))
        
        if self.manual_mode:
            return None # Skip all automated buy/sell logic

        # -- SELL LOGIC (Exempt from cooldowns, prioritised) --
        def _throttled_sell_log(key, msg, interval=300):
            """Log sell condition at most once per `interval` seconds per key."""
            now = time.time()
            if now - self._last_sell_log.get(key, 0) >= interval:
                logger.info(msg)
                self._last_sell_log[key] = now
                
        # 0. Market Cooldown Check (Wait 15 mins after open to avoid volatility traps)
        if self.is_market_cooling_down():
            _throttled_sell_log("market_cooldown", f"[{self.stock_id}] Market Open Cooldown (15m): Pausing automated sells.", interval=60)
            return None

        if self.quantity > 0:
            if self.pnl_percent > self.highest_pnl:
                self.highest_pnl = self.pnl_percent
                if getattr(self, 'db_manager', None):
                    self.db_manager.update_highest_pnl(self.stock_id, self.highest_pnl)

            # ----- PDT SELL PROTECTION -----
            is_day_trade = False
            if self.last_buy_time > 0:
                last_buy_date = datetime.fromtimestamp(self.last_buy_time).date()
                if last_buy_date == datetime.now().date():
                    is_day_trade = True

            if is_day_trade and self.app and hasattr(self.app, 'pdt_protector'):
                if not self.app.pdt_protector.can_trade():
                    # Check if we should log (only log once per minute to avoid spam)
                    _throttled_sell_log("pdt_block", f"[{self.stock_id}] PDT LIMIT: Holding day-trade SELL to avoid 90-day lock.")
                    
                    # Still update MACD tracker before returning None
                    if self.macd_signal != self.prev_macd_signal:
                        self.prev_macd_signal = self.macd_signal
                    return None

            # 1. Dynamic ATR Trailing Profit Lock
            profit_target_pct = self.dynamic_profit_target * 100
            current_atr_pct = (self.get_atr_14() / self.market_value) * 100 if self.market_value > 0 else 0
            dynamic_trail_drop = max(1.0, min(current_atr_pct * 1.0, 3.0))

            if self.highest_pnl >= profit_target_pct:
                trail_activation = self.highest_pnl - dynamic_trail_drop
                if self.pnl_percent <= trail_activation:
                    reason_msg = f"Trailing Profit Triggered at {self.pnl_percent:.2f}% (Peak: {self.highest_pnl:.2f}%, Trail: {dynamic_trail_drop:.2f}%)"
                    _throttled_sell_log("trailing_profit", f"[{self.stock_id}] {reason_msg}")
                    self.last_trade_reason = reason_msg
                    return 'SELL'
                    
            # 1.5 Proportional Protective Trailing Stop (lock in gains once > 5%)
            elif self.highest_pnl >= 5.0:
                # Give back at most 50% of peak gains (e.g. peak 4% → sell at 2%, peak 6% → sell at 3%)
                protective_trail_drop = self.highest_pnl * 0.5
                protective_floor = self.highest_pnl - protective_trail_drop
                if self.pnl_percent <= protective_floor:
                    reason_msg = f"Protective Stop Triggered at {self.pnl_percent:.2f}% (Peak: {self.highest_pnl:.2f}%, Trail: {protective_trail_drop:.2f}%)"
                    _throttled_sell_log("protective_stop", f"[{self.stock_id}] {reason_msg}")
                    self.last_trade_reason = reason_msg
                    return 'SELL'
            
            # 2. Dynamic Stop Loss (ATR-based)
            if self.pnl_percent <= self.dynamic_stop_loss:
                reason_msg = f"ATR Stop Loss Triggered at {self.dynamic_stop_loss:.1f}%"
                _throttled_sell_log("atr_stop_loss", f"[{self.stock_id}] {reason_msg}")
                self.last_trade_reason = reason_msg
                return 'SELL'

            # 3. RSI Overbought Exit (only sell when in profit to avoid false signals)
            if self.rsi_value >= 80 and self.pnl_percent > 1.0:
                reason_msg = f"RSI Overbought Exit at RSI {self.rsi_value:.0f} (PnL: {self.pnl_percent:.2f}%)"
                _throttled_sell_log("rsi_overbought", f"[{self.stock_id}] {reason_msg}")
                self.last_trade_reason = reason_msg
                return 'SELL'

            # 4. MACD Bearish Crossover (only on fresh bullish → bearish transition)
            if (self.macd_signal in ("S_BEAR", "BEAR") and
                    self.prev_macd_signal in ("S_BULL", "BULL") and
                    self.pnl_percent > 1.0):
                reason_msg = f"MACD Bearish Crossover Exit ({self.prev_macd_signal} → {self.macd_signal}, PnL: {self.pnl_percent:.2f}%)"
                _throttled_sell_log("macd_crossover", f"[{self.stock_id}] {reason_msg}")
                self.prev_macd_signal = self.macd_signal
                self.last_trade_reason = reason_msg
                return 'SELL'

            # 5. Analyst Downgrade / Target Cut Below Current Price
            if self.pnl_percent > 0.5:
                analyst_target = None
                bank_data = self.db_manager.get_cached_bank_note(self.stock_id) if self.db_manager else None
                if bank_data and bank_data[0] and bank_data[0] > 0:
                    analyst_target = bank_data[0]
                elif self.target_price and self.target_price > 0:
                    analyst_target = self.target_price

                if analyst_target and self.market_value > 0:
                    # Normalize GBp targets if needed
                    temp_target = analyst_target
                    if self.stock_id.upper().endswith(".L") and self.market_value > temp_target * 10:
                        temp_target = temp_target * 100
                    elif self.market_value > 10 and temp_target < 10:
                        temp_target = temp_target * 100

                    if self.market_value >= temp_target * 1.10:  # Price is 10%+ above analyst target
                        reason_msg = f"Analyst Target Exit: price {self.market_value:.2f} is 10%+ above target {temp_target:.2f} (PnL: {self.pnl_percent:.2f}%)"
                        _throttled_sell_log("analyst_target", f"[{self.stock_id}] {reason_msg}")
                        self.last_trade_reason = reason_msg
                        return 'SELL'



            # Update MACD transition tracker
            if self.macd_signal != self.prev_macd_signal:
                self.prev_macd_signal = self.macd_signal
            return None

        # -- BUY LOGIC --
        
        # 1. Cooldown checks for BUY
        now = time.time()
        if now - self.last_buy_time < 86400 or now - self.last_sell_time < 86400:  # 24 hours (1 trading day)
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

        usable_cash = self.ibapi.available_cash - self.min_cash
        if not self.is_market_open() or min(self.cash_left, usable_cash) < self.MIN_CASH_FOR_BUY or not earnings_ok:
            return None
            
        if self.is_market_cooling_down():
            logger.info(f"[{self.stock_id}] Market Open Cooldown (15m): Pausing automated buys.")
            return None

        # 3. Daily growth check (block buy if stock rose more than 5% today)
        if self.previous_close > 0:
            daily_change = (self.market_value - self.previous_close) / self.previous_close
            if daily_change > 0.05:
                logger.info(f"[{self.stock_id}] Blocked buy: daily rise ({daily_change*100:.1f}%) exceeds 5% limit.")
                return None

        # 4. RSI Overbought check (block buy if stock is overbought)
        if self.rsi_value >= 70:
            logger.info(f"[{self.stock_id}] Blocked buy: RSI ({self.rsi_value:.1f}) is in the overbought zone (>= 70).")
            return None

        # 5. Cumulative 3-day rise check (block buy if stock rose more than 15% in 3 days)
        if getattr(self, 'close_3d_ago', 0) > 0:
            three_day_change = (self.market_value - self.close_3d_ago) / self.close_3d_ago
            if three_day_change > 0.15:
                logger.info(f"[{self.stock_id}] Blocked buy: 3-day cumulative rise ({three_day_change*100:.1f}%) exceeds 15% limit.")
                return None
                
        # Check if we are the highest score in the portfolio among available stocks
        if hasattr(self, 'gui') and self.gui and hasattr(self.gui, 'bots'):
            highest_score = max([b.smart_score for b in self.gui.bots.values() if b.cash_left >= getattr(b, 'MIN_CASH_FOR_BUY', 500)], default=0)
            
            if self.smart_score < highest_score:
                # Do not log continuously to avoid spam, just return None silently
                return None
                
            # User Feature Request: If we have the highest score, but another stock tied for the highest
            # score has a closed market, we must WAIT for it to open before buying, to give it priority.
            if self.smart_score == highest_score and self.is_market_open():
                for b in self.gui.bots.values():
                    if b.cash_left >= getattr(b, 'MIN_CASH_FOR_BUY', 500) and b.smart_score == highest_score and not b.is_market_open():
                        # Another top-scoring stock is closed. Wait for it to open.
                        return None
        
        current_strategy = "DIP" if "DIP" in self.score_reason else "MOMENTUM"
        
        # 1. DIP STRATEGY TRIGGER
        if current_strategy == "DIP" and self.smart_score >= 7:
            # Macro Market Guard
            macro_status = self.check_macro_guard()
            if macro_status['drop_pct'] <= self.MACRO_DROP_LIMIT:
                logger.info(f"[{self.stock_id}] Blocked DIP buy: Macro Market Guard Active ({macro_status['status']})")
                return None
                
            daily_drop = (self.market_value - self.previous_close) / self.previous_close
            
            # Block if the single-day drop is too extreme (e.g., worse than -7%)
            if daily_drop < -0.07:
                logger.info(f"[{self.stock_id}] Blocked DIP buy: daily drop ({daily_drop*100:.1f}%) exceeds -7% limit.")
                return None
                
            # Block if the drop is moderate but RSI is still high (not oversold enough)
            if daily_drop < -0.03 and self.rsi_value > 45:
                logger.info(f"[{self.stock_id}] Blocked DIP buy: catching a falling knife (RSI: {self.rsi_value:.1f})")
                return None
            
            self.last_trade_reason = self.score_reason
            return 'BUY'

    def get_buy_block_reason(self):
        """Returns the specific technical or safety reason blocking a BUY for this stock."""
        now = time.time()
        if now - self.last_buy_time < 86400 or now - self.last_sell_time < 86400:
            return "buy/sell 24h cooldown active"

        if self.next_earnings_date and self.next_earnings_date != "No payment":
            try:
                earn_date = datetime.strptime(self.next_earnings_date, "%Y-%m-%d").date()
                days = (earn_date - datetime.now().date()).days
                if -2 <= days <= 3:
                    return f"earnings report in {days} days"
            except ValueError:
                pass

        if self.is_market_cooling_down():
            return "market open 15m cooldown active"

        # Check cash availability
        usable_cash = getattr(self.ibapi, 'available_cash', 0) - self.min_cash
        effective_cash = min(self.cash_left, usable_cash)
        if effective_cash < self.MIN_CASH_FOR_BUY:
            return f"insufficient cash (available: €{effective_cash:.0f}, min required: €{self.MIN_CASH_FOR_BUY:.0f})"

        if self.previous_close > 0:
            daily_change = (self.market_value - self.previous_close) / self.previous_close
            if daily_change > 0.05:
                return f"daily rise ({daily_change*100:.1f}%) exceeds 5% limit"

        if self.rsi_value >= 70:
            return f"overbought zone (RSI {self.rsi_value:.1f} >= 70)"

        if getattr(self, 'close_3d_ago', 0) > 0:
            three_day_change = (self.market_value - self.close_3d_ago) / self.close_3d_ago
            if three_day_change > 0.15:
                return f"3-day cumulative rise ({three_day_change*100:.1f}%) exceeds 15% limit"

        # Portfolio priority check
        if hasattr(self, 'gui') and self.gui and hasattr(self.gui, 'bots'):
            highest_score = max(
                [b.smart_score for b in self.gui.bots.values() if b.cash_left >= getattr(b, 'MIN_CASH_FOR_BUY', 500)],
                default=0
            )
            if self.smart_score < highest_score:
                top_stock = next(
                    (b.stock_id for b in self.gui.bots.values()
                     if b.smart_score == highest_score and b.cash_left >= getattr(b, 'MIN_CASH_FOR_BUY', 500)),
                    "another stock"
                )
                return f"lower portfolio priority (score {self.smart_score}/12 vs {top_stock} at {highest_score}/12)"

            if self.smart_score == highest_score and self.is_market_open():
                for b in self.gui.bots.values():
                    if (b.cash_left >= getattr(b, 'MIN_CASH_FOR_BUY', 500)
                            and b.smart_score == highest_score
                            and not b.is_market_open()):
                        return f"waiting for tied top-scorer {b.stock_id} (score {highest_score}/12) market to open"

        current_strategy = "DIP" if "DIP" in self.score_reason else "MOMENTUM"

        if current_strategy == "DIP":
            if self.smart_score < 7:
                return f"DIP score ({self.smart_score}/12) below threshold 7"

            macro_status = self.check_macro_guard()
            if macro_status['drop_pct'] <= self.MACRO_DROP_LIMIT:
                return f"Macro Market Guard Active ({macro_status['status']})"

            if self.previous_close > 0:
                daily_drop = (self.market_value - self.previous_close) / self.previous_close
                if daily_drop < -0.07:
                    return f"daily drop ({daily_drop*100:.1f}%) exceeds -7% falling knife limit"
                if daily_drop < -0.03 and self.rsi_value > 45:
                    return f"falling knife guard (drop {daily_drop*100:.1f}% with RSI {self.rsi_value:.1f} > 45, not oversold enough)"

        else:  # MOMENTUM
            if self.smart_score < 8:
                return f"MOMENTUM score ({self.smart_score}/12) below threshold 8"

            # ATR-based fast-rising check
            if self.previous_close > 0:
                daily_change = (self.market_value - self.previous_close) / self.previous_close
                yesterday_change = 0
                if getattr(self, 'day_before_yesterday_close', 0) > 0:
                    yesterday_change = (self.previous_close - self.day_before_yesterday_close) / self.day_before_yesterday_close

                atr = getattr(self, '_cached_atr_14', 0)
                atr_pct = (atr / self.previous_close) if self.previous_close > 0 else 0.025
                daily_threshold = min(0.08, max(0.03, atr_pct * 2.0))
                yesterday_threshold = min(0.08, max(0.05, atr_pct * 2.5))

                if daily_change > daily_threshold:
                    return f"MOMENTUM blocked: parabolic rise today ({daily_change*100:.1f}% > ATR threshold {daily_threshold*100:.1f}%)"
                if yesterday_change > yesterday_threshold:
                    return f"MOMENTUM blocked: parabolic rise yesterday ({yesterday_change*100:.1f}% > ATR threshold {yesterday_threshold*100:.1f}%)"

        return f"score qualifies ({self.smart_score}/12) but {current_strategy} entry conditions not satisfied (RSI: {self.rsi_value:.1f}, daily change: {((self.market_value - self.previous_close)/self.previous_close*100) if self.previous_close > 0 else 0:.1f}%)"


    def get_status(self):
        if not self.is_market_open():
            return self.STATUS_MARKET_CLOSED
        if self.manual_mode:
            return self.STATUS_HOLDING
        if self.has_pending_order():
            return self.STATUS_WAITING_ORDER
        native_currency, _ = self.get_native_currency_and_exchange()
        rate = self.exchange_manager.get_rate(native_currency)
        market_val_eur = self.market_value / rate if rate > 0 else self.market_value

        if self.cash_left < market_val_eur:
            if self.quantity > 0:
                return "Full capacity"
            else:
                return "Budget too low"
        if self.cash_left < 500:
            return f"Low Cash {self.currency_symbol}{self.cash_left:.0f}"
        if self.is_running:
            return self.STATUS_RUNNING
        if self.manual_mode:
            return self.STATUS_HOLDING
        return self.STATUS_READY
    
    def stop(self):
        self.is_running = False
            
