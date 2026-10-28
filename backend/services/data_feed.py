# ==============================================================================
# pyTrade3 — DataFeed Service (data_feed.py)
# Stage 1 in Lean Architecture: Market Data, Technical Indicators & Caching
# ==============================================================================

import time
import threading
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf
from config import logger, executor
from analyst_scraper import AnalystDataMixin
from .models import MarketSnapshot

class DataFeedService(AnalystDataMixin):
    """
    Handles market data retrieval, technical indicator calculation,
    and two-tier caching (RAM + SQLite).
    """
    def __init__(self, stock_id: str, db_manager=None, exchange_manager=None, ibapi=None):
        self.stock_id = stock_id
        self.db_manager = db_manager
        self.exchange_manager = exchange_manager
        self.ibapi = ibapi

        self.market_value = 0.0
        self.last_yf_fetch = 0
        self.yf_fetch_interval_open = 20
        self.yf_fetch_interval_closed = 3600

        self.last_indicators_fetch = 0
        self.indicators_interval_open = 300       # 5 min
        self.indicators_interval_closed = 10800   # 3 hours

        self.company_name = "Loading..."
        self.asset_type = "UNKNOWN"
        self.sector = "N/A"
        self.currency = "USD"
        self.currency_symbol = "$"
        self.exchange_tz_name = None

        self.previous_close = 0.0
        self.day_before_yesterday_close = 0.0
        self.close_3d_ago = 0.0
        self.is_last_date_today = False

        self.fourteen_day_high = 0.0
        self.fourteen_day_low = 0.0
        self.rsi_value = 50.0
        self.adx_value = 0.0

        self.bb_upper = 0.0
        self.bb_middle = 0.0
        self.bb_lower = 0.0
        self.bb_pct_b = 0.5

        self.ma_signal = "NEUTRAL"
        self.prev_ma_signal = ""
        self.macd_signal = "NEUTRAL"
        self.prev_macd_signal = ""

        self.today_volume = 0.0
        self.avg_volume_14d = 0.0
        self.next_earnings_date = None
        self.target_price = 0.0
        self.num_analysts = 0

        self._cached_ma200 = 0.0
        self._ma200_last_update = 0
        self._cached_ma50 = 0.0
        self._ma50_last_update = 0
        self._cached_atr_14 = 1.0
        self._atr_last_update = 0

        self._fetching_indicators = False
        self._fetching_market_value = False
        self._last_info_fetch = 0

        self._load_initial_metadata()

    def _load_initial_metadata(self):
        """Loads static metadata and cached indicators from SQLite."""
        if not self.db_manager:
            return

        info_dict = self.db_manager.get_company_info(self.stock_id)
        self.company_name = info_dict.get("company_name", "Loading...")
        self.asset_type = info_dict.get("asset_type", "UNKNOWN")
        self.sector = info_dict.get("sector", "N/A")
        self.currency = info_dict.get("currency", "USD")
        self.currency_symbol = {"USD": "$", "EUR": "€", "GBP": "£", "GBp": "£", "HKD": "HK$"}.get(self.currency, "$")
        self.exchange_tz_name = info_dict.get("exchange_tz_name")

        cached_price = self.db_manager.get_latest_price(self.stock_id)
        if cached_price:
            self.market_value = cached_price["price"]
            self.last_yf_fetch = cached_price["fetched_at"]

        cached_ind = self.db_manager.get_cached_indicators(self.stock_id)
        if cached_ind:
            self.fourteen_day_high = cached_ind.get("high_14d", 0.0)
            self.fourteen_day_low = cached_ind.get("low_14d", 0.0)
            self.rsi_value = cached_ind.get("rsi", 50.0)
            self.adx_value = cached_ind.get("adx", 0.0)
            self.bb_upper = cached_ind.get("bb_upper", 0.0)
            self.bb_middle = cached_ind.get("bb_middle", 0.0)
            self.bb_lower = cached_ind.get("bb_lower", 0.0)
            if (self.bb_upper - self.bb_lower) > 0 and self.market_value > 0:
                self.bb_pct_b = (self.market_value - self.bb_lower) / (self.bb_upper - self.bb_lower)
            self.ma_signal = cached_ind.get("ma_signal", "NEUTRAL")
            self.macd_signal = cached_ind.get("macd_signal", "NEUTRAL")
            self.next_earnings_date = cached_ind.get("next_earnings_date")
            self.today_volume = cached_ind.get("today_volume", 0.0)
            self.avg_volume_14d = cached_ind.get("avg_volume_14d", 0.0)
            self.previous_close = cached_ind.get("prev_close") or 0.0
            self.day_before_yesterday_close = cached_ind.get("day_before_yesterday_close") or 0.0
            self.target_price = cached_ind.get("target_mean_price") or 0.0
            self.last_indicators_fetch = cached_ind.get("fetched_at", 0)

    def is_market_open(self) -> bool:
        """Determines if the exchange for this asset is actively in trading hours."""
        try:
            if not self.exchange_tz_name:
                return False
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
        except Exception:
            return False

    def is_market_cooling_down(self, cooldown_minutes: int = 30) -> bool:
        """Hard Guard 1: First 30 minutes after market open."""
        try:
            if not self.exchange_tz_name:
                return False
            tz = ZoneInfo(self.exchange_tz_name)
            now = datetime.now(tz)
            if now.weekday() >= 5:
                return False
            current_time = now.time()

            if 'America/New_York' in self.exchange_tz_name:
                market_open = dtime(9, 30)
                end_min = 30 + cooldown_minutes
                end_hour = 9 + (end_min // 60)
                end_min = end_min % 60
                cooldown_end = dtime(end_hour, end_min)
            else:
                market_open = dtime(9, 0)
                end_min = cooldown_minutes
                end_hour = 9 + (end_min // 60)
                end_min = end_min % 60
                cooldown_end = dtime(end_hour, end_min)

            return market_open <= current_time < cooldown_end
        except Exception:
            return False

    def get_projected_volume(self) -> float:
        """Estimates full-day volume based on elapsed market time."""
        if self.today_volume <= 0:
            return 0.0
        try:
            if not self.exchange_tz_name:
                return self.today_volume
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

            if current_time < market_open or current_time > market_close:
                return self.today_volume

            total_minutes = (market_close.hour * 60 + market_close.minute) - (market_open.hour * 60 + market_open.minute)
            elapsed_minutes = (current_time.hour * 60 + current_time.minute) - (market_open.hour * 60 + market_open.minute)
            if elapsed_minutes <= 0:
                return self.today_volume

            effective_elapsed = max(30, elapsed_minutes)
            return self.today_volume * (total_minutes / effective_elapsed)
        except Exception:
            return self.today_volume

    @staticmethod
    def calculate_rsi(close: pd.Series, period: int = 14) -> float:
        """Wilder's RSI matching core_backtest_engine.py."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()

        rs = gain / loss.replace(0, 0.001)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iat[-1]) if len(rsi) > 0 and pd.notnull(rsi.iat[-1]) else 50.0

    def calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """14-period ADX (0-100) synced with backtest engine."""
        tr = pd.concat([
            (high - low).abs(),
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)

        plus_dm = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        plus_dm = plus_dm.where(plus_dm >= minus_dm, 0)
        minus_dm = minus_dm.where(minus_dm > plus_dm, 0)

        atr_smooth = tr.rolling(period).mean().replace(0, 0.001)
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr_smooth)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr_smooth)
        denom = (plus_di + minus_di).replace(0, 0.001)
        dx = 100 * (plus_di - minus_di).abs() / denom
        adx = dx.rolling(period).mean()
        return float(adx.iat[-1]) if len(adx) > 0 and pd.notnull(adx.iat[-1]) else 0.0

    def calculate_technical_indicators(self, force: bool = False):
        """Asynchronously updates technical indicators via Yahoo Finance."""
        now = time.time()
        market_open = self.is_market_open()
        interval = self.indicators_interval_open if market_open else self.indicators_interval_closed

        if force or now - self.last_indicators_fetch >= interval:
            if self._fetching_indicators:
                return
            self._fetching_indicators = True
            self.last_indicators_fetch = now

            def fetch_task():
                try:
                    ticker_obj = yf.Ticker(self.stock_id)
                    data = ticker_obj.history(period="1y", interval="1d", auto_adjust=False, actions=False)
                    if data.empty or len(data) < 200:
                        logger.warning(f"Insufficient data for {self.stock_id}: {len(data)} rows")
                        return

                    if isinstance(data.columns, pd.MultiIndex):
                        try:
                            data.columns = data.columns.droplevel(1)
                        except Exception:
                            pass

                    close = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
                    high = data['High'].iloc[:, 0] if isinstance(data['High'], pd.DataFrame) else data['High']
                    low = data['Low'].iloc[:, 0] if isinstance(data['Low'], pd.DataFrame) else data['Low']
                    volume = data['Volume'].iloc[:, 0] if isinstance(data['Volume'], pd.DataFrame) else data['Volume']

                    close = close.dropna()
                    high = high.dropna()
                    low = low.dropna()
                    volume = volume.dropna()

                    if len(close) >= 2:
                        info_prev = 0
                        try:
                            info_prev = ticker_obj.info.get('previousClose') or ticker_obj.info.get('regularMarketPreviousClose') or 0
                        except Exception:
                            pass

                        if info_prev and float(info_prev) > 0:
                            self.previous_close = float(info_prev)
                            self.is_last_date_today = True
                            self.day_before_yesterday_close = float(close.iat[-2]) if len(close) >= 2 else self.previous_close
                            self.close_3d_ago = float(close.iat[-4]) if len(close) >= 4 else self.previous_close
                        else:
                            last_date = close.index[-1].date()
                            today = pd.Timestamp.now(tz=close.index.tz).date()
                            self.is_last_date_today = (last_date == today)
                            idx = -2 if self.is_last_date_today else -1
                            self.previous_close = float(close.iat[idx])
                            self.day_before_yesterday_close = float(close.iat[idx - 1]) if len(close) >= abs(idx) + 1 else self.previous_close
                            self.close_3d_ago = float(close.iat[idx - 3]) if len(close) >= abs(idx) + 3 else self.previous_close

                    self.fourteen_day_high = float(high.rolling(14).max().iat[-1])
                    self.fourteen_day_low = float(low.rolling(14).min().iat[-1])
                    self.adx_value = self.calculate_adx(high, low, close)
                    self.rsi_value = self.calculate_rsi(close)

                    self.bb_middle = float(close.rolling(20).mean().iat[-1])
                    ma20 = self.bb_middle
                    ma50 = float(close.rolling(50).mean().iat[-1])
                    ma200 = float(close.rolling(200).mean().iat[-1])
                    price = float(close.iat[-1])

                    self._cached_ma200 = ma200
                    self._ma200_last_update = time.time()
                    self._cached_ma50 = ma50
                    self._ma50_last_update = time.time()

                    tr0 = abs(high - low)
                    tr1 = abs(high - close.shift())
                    tr2 = abs(low - close.shift())
                    tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
                    atr = float(tr.rolling(14).mean().iat[-1])
                    self._cached_atr_14 = atr
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

                    if self.ma_signal and self.ma_signal != new_ma_signal:
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

                    rolling_std = float(close.rolling(20).std().iat[-1])
                    self.bb_upper = ma20 + (2 * rolling_std)
                    self.bb_lower = ma20 - (2 * rolling_std)
                    if (self.bb_upper - self.bb_lower) != 0:
                        self.bb_pct_b = (price - self.bb_lower) / (self.bb_upper - self.bb_lower)
                    else:
                        self.bb_pct_b = 0.5

                    self.today_volume = float(volume.iat[-1])
                    self.avg_volume_14d = float(volume.rolling(14).mean().iat[-1])

                    self.next_earnings_date = self.fetch_next_event_date(ticker_obj)

                    try:
                        now_time = time.time()
                        if (now_time - self._last_info_fetch > 86400) or self.target_price <= 0:
                            self.target_price = ticker_obj.info.get('targetMeanPrice', 0) or 0.0
                            self.num_analysts = ticker_obj.info.get('numberOfAnalystOpinions', 0) or 0
                            self._last_info_fetch = now_time
                    except Exception as info_err:
                        logger.warning(f"Failed to fetch yfinance .info for {self.stock_id}: {info_err}")

                    if self.db_manager:
                        self.db_manager.update_cached_indicators(
                            self.stock_id, self.fourteen_day_high, self.fourteen_day_low,
                            self.rsi_value, self.adx_value, self.bb_upper, self.bb_middle, self.bb_lower,
                            self.ma_signal, self.macd_signal,
                            self.next_earnings_date, self.today_volume, self.avg_volume_14d,
                            self.previous_close, self.target_price, self.num_analysts,
                            self.day_before_yesterday_close
                        )

                    self.update_analyst_data(run_async=False)
                    self.last_indicators_fetch = time.time()
                except Exception as e:
                    logger.error(f"Indicators background error for {self.stock_id}: {e}")
                finally:
                    self._fetching_indicators = False

            executor.submit(fetch_task)

    def get_ma200(self) -> float:
        now = time.time()
        if hasattr(self, '_cached_ma200') and now - self._ma200_last_update < 1800:
            return self._cached_ma200
        return self._cached_ma200 if self._cached_ma200 > 0 else self.market_value

    def get_ma50(self) -> float:
        now = time.time()
        if hasattr(self, '_cached_ma50') and now - self._ma50_last_update < 1800:
            return self._cached_ma50
        return self._cached_ma50 if self._cached_ma50 > 0 else self.market_value

    def get_atr_14(self) -> float:
        now = time.time()
        if hasattr(self, '_cached_atr_14') and now - self._atr_last_update < 300:
            return self._cached_atr_14
        return self._cached_atr_14 if self._cached_atr_14 > 0 else 1.0

    def get_market_value(self) -> float:
        now = time.time()
        interval = self.yf_fetch_interval_open if self.is_market_open() else self.yf_fetch_interval_closed
        if now - self.last_yf_fetch < interval:
            return self.market_value

        if self._fetching_market_value:
            return self.market_value
        self._fetching_market_value = True
        self.last_yf_fetch = now

        def fetch():
            try:
                ticker = yf.Ticker(self.stock_id)
                hist = ticker.history(period="5d", interval="1m")
                if not hist.empty:
                    price = float(hist['Close'].iloc[-1])
                    if self.ibapi and hasattr(self.ibapi, 'data_lock'):
                        with self.ibapi.data_lock:
                            self.market_value = round(price, 2)
                    else:
                        self.market_value = round(price, 2)
                    if self.db_manager:
                        self.db_manager.update_latest_price(self.stock_id, price)
            except Exception:
                pass
            finally:
                self._fetching_market_value = False

        executor.submit(fetch)
        return self.market_value

    def get_snapshot(self) -> MarketSnapshot:
        """Returns an immutable snapshot representing current market conditions."""
        return MarketSnapshot(
            stock_id=self.stock_id,
            market_price=self.market_value,
            previous_close=self.previous_close,
            day_before_yesterday_close=self.day_before_yesterday_close,
            close_3d_ago=self.close_3d_ago,
            high_14d=self.fourteen_day_high,
            low_14d=self.fourteen_day_low,
            rsi=self.rsi_value,
            adx=self.adx_value,
            ma50=self.get_ma50(),
            ma200=self.get_ma200(),
            atr14=self.get_atr_14(),
            ma_signal=self.ma_signal,
            macd_signal=self.macd_signal,
            prev_macd_signal=self.prev_macd_signal,
            bb_upper=self.bb_upper,
            bb_middle=self.bb_middle,
            bb_lower=self.bb_lower,
            bb_pct_b=self.bb_pct_b,
            today_volume=self.today_volume,
            avg_volume_14d=self.avg_volume_14d,
            projected_volume=self.get_projected_volume(),
            next_earnings_date=self.next_earnings_date,
            target_price=self.target_price,
            num_analysts=self.num_analysts,
            asset_type=self.asset_type,
            sector=self.sector,
            currency=self.currency,
            currency_symbol=self.currency_symbol,
            exchange_tz_name=self.exchange_tz_name
        )

