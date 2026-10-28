# ==============================================================================
# pyTrade3 — TradingBot Facade Coordinator (trading_bot.py)
# Lean 5-Stage Architecture: Orchestrates DataFeed, Alpha, Portfolio, Risk & Execution
# ==============================================================================

import time
import re
import threading
from datetime import datetime
from typing import Optional
import pandas as pd
from config import logger
from analyst_scraper import AnalystDataMixin

from services.models import MarketSnapshot, AlphaSignal, RiskDecision
from services.data_feed import DataFeedService
from services.alpha_engine import AlphaEngine
from services.portfolio_sizing import PortfolioSizingService
from services.risk_manager import RiskManagementEngine
from services.execution import ExecutionService

class TradingBot(AnalystDataMixin):
    """
    Facade Coordinator orchestrating 5 dedicated Lean services.
    Retains 100% backward compatibility for PyQt6 GUI and Backtest benchmarks.
    """
    MIN_CASH_FOR_BUY = 500.0
    CASH_BUFFER_MULTIPLIER = 0.95
    STATUS_READY = "Ready"
    STATUS_RUNNING = "Running"
    STATUS_PAUSING = "Pausing"
    STATUS_WAITING_ORDER = "Waiting Order"
    STATUS_MARKET_CLOSED = "Closed"
    STATUS_HOLDING = "Holding"
    PRIORITY_BUY_LIST = {"EGLN.L", "ESE.PA"}

    # Class-level macro guard variables
    _macro_cache = {'time': 0, 'drop_pct': 0.0, 'status': 'GREEN'}
    _macro_lock = threading.Lock()
    MACRO_TICKER = "^GSPC"        # S&P 500 Index
    MACRO_DROP_LIMIT = -0.015     # -1.5% drop blocks DIP buys
    TIME_STOP_DAYS = 25           # Stagnation Time-Stop threshold (days held)
    TIME_STOP_MAX_PNL = -0.5      # Exit stagnant positions held >= 25d if PnL <= -0.5%
    MAX_SECTOR_POSITIONS = 6      # Max concurrent open positions per sector (non-ETF)

    def __init__(
        self,
        ibapi,
        stock_id: str,
        max_amount: float,
        profit_target: float,
        drop_threshold: float,
        manual_mode: bool = False,
        db_manager=None,
        csv_manager=None,
        exchange_manager=None,
        gui=None,
        is_auto_watchlist: bool = False
    ):
        self.ibapi = ibapi
        self.stock_id = stock_id
        self.ibkr_symbol = re.sub(r'\..*$', '', stock_id)
        self.max_amount = max_amount
        self.profit_target = profit_target / 100.0
        self.drop_threshold = drop_threshold / 100.0
        self.db_manager = db_manager
        self.csv_manager = csv_manager
        self.exchange_manager = exchange_manager
        self.app = gui
        self.gui = gui
        self.manual_mode = manual_mode
        self.is_auto_watchlist = is_auto_watchlist

        # Initialize 5 dedicated Lean services
        self.data_feed = DataFeedService(stock_id, db_manager, exchange_manager, ibapi)
        self.alpha_engine = AlphaEngine()
        self.portfolio_sizer = PortfolioSizingService(exchange_manager, db_manager)
        self.risk_manager = RiskManagementEngine(db_manager, gui)
        self.execution = ExecutionService(ibapi, db_manager, csv_manager, gui)

        # Internal Trading State
        self.smart_score = 0
        self.base_score = 0
        self.score_reason = ""
        self.target_upside_pct = 0.0
        self.current_strategy = "DIP"
        self.bought_strategy = None
        self.last_trade_reason = ""

        self.bought_price = 0.0
        self.current_value = 0.0
        self.pnl_percent = 0.0
        self.quantity = 0
        self.last_quantity = 0
        self.cash_left = 0.0
        self.current_max_investment = max_amount
        self.highest_pnl = 0.0

        self.is_running = False
        self.pending_order_id = None
        self.pending_order_time = None
        self.order_timeout = 300

        self.last_buy_time = 0.0
        self.last_sell_time = 0.0
        self.last_rejection_time = 0.0
        self.last_cooldown_warning_time = 0.0
        self.cooldown_warning_interval = 7200

        # Dynamic Stop & Profit targets
        self.atr_multiplier = 1.5
        self.min_profit_pct = profit_target
        self.max_profit_pct = 15.0
        self.dynamic_profit_target = self.profit_target

        self.stop_multiplier = 2.3
        self.max_stop_loss = -12.0
        self.min_stop_loss = -3.0
        self.dynamic_stop_loss = self.drop_threshold

        # Load historical trade times from DB
        if self.db_manager:
            last_buy, last_sell = self.db_manager.get_last_trade_times(self.stock_id)
            self.last_buy_time = last_buy
            self.last_sell_time = last_sell

    # ==================== DELEGATED PROPERTIES ====================
    @property
    def market_value(self) -> float:
        return self.data_feed.market_value

    @market_value.setter
    def market_value(self, val: float):
        self.data_feed.market_value = val

    @property
    def rsi_value(self) -> float:
        return self.data_feed.rsi_value

    @rsi_value.setter
    def rsi_value(self, val: float):
        self.data_feed.rsi_value = val

    @property
    def adx_value(self) -> float:
        return self.data_feed.adx_value

    @adx_value.setter
    def adx_value(self, val: float):
        self.data_feed.adx_value = val

    @property
    def ma_signal(self) -> str:
        return self.data_feed.ma_signal

    @ma_signal.setter
    def ma_signal(self, val: str):
        self.data_feed.ma_signal = val

    @property
    def prev_ma_signal(self) -> str:
        return self.data_feed.prev_ma_signal

    @prev_ma_signal.setter
    def prev_ma_signal(self, val: str):
        self.data_feed.prev_ma_signal = val

    @property
    def macd_signal(self) -> str:
        return self.data_feed.macd_signal

    @macd_signal.setter
    def macd_signal(self, val: str):
        self.data_feed.macd_signal = val

    @property
    def prev_macd_signal(self) -> str:
        return self.data_feed.prev_macd_signal

    @prev_macd_signal.setter
    def prev_macd_signal(self, val: str):
        self.data_feed.prev_macd_signal = val

    @property
    def previous_close(self) -> float:
        return self.data_feed.previous_close

    @previous_close.setter
    def previous_close(self, val: float):
        self.data_feed.previous_close = val

    @property
    def day_before_yesterday_close(self) -> float:
        return self.data_feed.day_before_yesterday_close

    @day_before_yesterday_close.setter
    def day_before_yesterday_close(self, val: float):
        self.data_feed.day_before_yesterday_close = val

    @property
    def close_3d_ago(self) -> float:
        return self.data_feed.close_3d_ago

    @close_3d_ago.setter
    def close_3d_ago(self, val: float):
        self.data_feed.close_3d_ago = val

    @property
    def fourteen_day_high(self) -> float:
        return self.data_feed.fourteen_day_high

    @fourteen_day_high.setter
    def fourteen_day_high(self, val: float):
        self.data_feed.fourteen_day_high = val

    @property
    def fourteen_day_low(self) -> float:
        return self.data_feed.fourteen_day_low

    @fourteen_day_low.setter
    def fourteen_day_low(self, val: float):
        self.data_feed.fourteen_day_low = val

    @property
    def today_volume(self) -> float:
        return self.data_feed.today_volume

    @today_volume.setter
    def today_volume(self, val: float):
        self.data_feed.today_volume = val

    @property
    def avg_volume_14d(self) -> float:
        return self.data_feed.avg_volume_14d

    @avg_volume_14d.setter
    def avg_volume_14d(self, val: float):
        self.data_feed.avg_volume_14d = val

    @property
    def next_earnings_date(self) -> Optional[str]:
        return self.data_feed.next_earnings_date

    @next_earnings_date.setter
    def next_earnings_date(self, val: Optional[str]):
        self.data_feed.next_earnings_date = val

    @property
    def target_price(self) -> float:
        return self.data_feed.target_price

    @target_price.setter
    def target_price(self, val: float):
        self.data_feed.target_price = val

    @property
    def num_analysts(self) -> int:
        return self.data_feed.num_analysts

    @num_analysts.setter
    def num_analysts(self, val: int):
        self.data_feed.num_analysts = val

    @property
    def company_name(self) -> str:
        return self.data_feed.company_name

    @property
    def asset_type(self) -> str:
        return self.data_feed.asset_type

    @property
    def sector(self) -> str:
        return self.data_feed.sector

    @property
    def currency(self) -> str:
        return self.data_feed.currency

    @property
    def currency_symbol(self) -> str:
        return self.data_feed.currency_symbol

    @property
    def exchange_tz_name(self) -> Optional[str]:
        return self.data_feed.exchange_tz_name

    @property
    def bb_pct_b(self) -> float:
        return self.data_feed.bb_pct_b

    @property
    def min_cash(self) -> float:
        if self.app:
            return getattr(self.app, 'min_cash', 0.0)
        return 0.0

    # ==================== DELEGATED METHODS ====================
    def create_yf_ticker(self):
        self.data_feed._load_initial_metadata()

    def is_market_open(self) -> bool:
        return self.data_feed.is_market_open()

    def is_market_cooling_down(self, cooldown_minutes: int = 30) -> bool:
        return self.data_feed.is_market_cooling_down(cooldown_minutes)

    def get_projected_volume(self) -> float:
        return self.data_feed.get_projected_volume()

    @staticmethod
    def calculate_rsi(close: pd.Series, period: int = 14) -> float:
        return DataFeedService.calculate_rsi(close, period)

    def calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        if hasattr(self, 'data_feed'):
            return self.data_feed.calculate_adx(high, low, close, period)
        return DataFeedService(self.stock_id if hasattr(self, 'stock_id') else "").calculate_adx(high, low, close, period)

    def calculate_technical_indicators(self, force: bool = False):
        self.data_feed.calculate_technical_indicators(force=force)

    def get_ma200(self) -> float:
        return self.data_feed.get_ma200()

    def get_ma50(self) -> float:
        return self.data_feed.get_ma50()

    def get_atr_14(self) -> float:
        return self.data_feed.get_atr_14()

    def get_market_value(self) -> float:
        return self.data_feed.get_market_value()

    @classmethod
    def check_macro_guard(cls):
        return RiskManagementEngine.check_macro_guard()

    def calculate_analyst_modifier(self):
        analyst_data = getattr(self, 'analyst_data', None)
        return AlphaEngine.calculate_analyst_modifier(analyst_data, self.market_value)

    def calculate_score(self) -> int:
        snapshot = self.data_feed.get_snapshot()
        analyst_data = getattr(self, 'analyst_data', None)
        bank_data = self.db_manager.get_cached_bank_note(self.stock_id) if self.db_manager else None

        signal = self.alpha_engine.calculate_score(snapshot, analyst_data, bank_data)
        self.smart_score = signal.smart_score
        self.base_score = signal.base_score
        self.current_strategy = signal.strategy
        self.score_reason = signal.score_reason
        self.target_upside_pct = signal.target_upside_pct
        return self.smart_score

    def _calculate_dynamic_max_amount(self) -> float:
        native_currency, _ = self.get_native_currency_and_exchange()
        return self.portfolio_sizer.calculate_dynamic_max_amount(
            stock_id=self.stock_id,
            market_value=self.market_value,
            dynamic_stop_loss=self.dynamic_stop_loss,
            asset_type=self.asset_type,
            native_currency=native_currency,
            default_max_amount=self.max_amount
        )

    def update_position(self):
        with self.ibapi.data_lock:
            pos = self.ibapi.positions.get(self.ibkr_symbol, {})
            self.quantity = pos.get('position', 0)
            self.bought_price = pos.get('avgCost', 0)
            ib_market_price = pos.get('marketPrice')
            ib_market_value = pos.get('marketValue')

            if ib_market_price is not None and ib_market_price > 0:
                self.current_value = ib_market_value if ib_market_value is not None else (self.quantity * ib_market_price)
                self.pnl_percent = ((ib_market_price - self.bought_price) / self.bought_price * 100) if self.bought_price > 0 else 0
            else:
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
                if self.bought_strategy is not None:
                    self.bought_strategy = None
                    if self.db_manager and hasattr(self.db_manager, 'update_bought_strategy'):
                        self.db_manager.update_bought_strategy(self.stock_id, None)

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
        self.profit_target = profit_target / 100.0
        self.min_profit_pct = profit_target
        self.drop_threshold = drop_threshold / 100.0

    def has_pending_order(self) -> bool:
        if not self.pending_order_id:
            return False

        if time.time() - self.pending_order_time > self.order_timeout:
            logger.warning(f"[{self.stock_id}] Order {self.pending_order_id} TIMED OUT")
            self.pending_order_id = None
            return False

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

    def get_native_currency_and_exchange(self):
        return ExecutionService.get_native_currency_and_exchange(self.stock_id)

    def _on_order_completed(self, order_id, status, action, quantity, price, filled, avg_fill_price, currency, reason):
        logger.info(f"[{self.stock_id}] Order {order_id} completed with status: {status}")

        if status == "Filled":
            if self.db_manager:
                actual_price = avg_fill_price if avg_fill_price > 0 else price
                self.db_manager.log_trade(self.stock_id, action, int(filled), actual_price)
                logger.info(f"Logged to database: {action} {int(filled)} @ {actual_price:.2f}")

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

            if self.csv_manager:
                self.csv_manager.update_order_status(order_id, "FILLED")

            if self.app and hasattr(self.app, 'pdt_protector'):
                self.app.pdt_protector.register_day_trade_if_needed(self.stock_id)

            if action == "BUY":
                self.last_buy_time = time.time()
                if self.db_manager and hasattr(self.db_manager, 'update_bought_strategy') and self.bought_strategy:
                    self.db_manager.update_bought_strategy(self.stock_id, self.bought_strategy)
            elif action == "SELL":
                self.last_sell_time = time.time()
                self.bought_strategy = None
                if self.db_manager and hasattr(self.db_manager, 'update_bought_strategy'):
                    self.db_manager.update_bought_strategy(self.stock_id, None)

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

        if self.pending_order_id == order_id:
            self.pending_order_id = None

    def check_trading_conditions(self, readonly=False):
        last_rej = getattr(self, 'last_rejection_time', 0) or 0
        if last_rej > 0 and not readonly:
            if time.time() - last_rej < 3600:
                return None

        self.update_analyst_data(run_async=True)

        if (getattr(self.data_feed, '_fetching_market_value', False) or
                getattr(self.data_feed, '_fetching_indicators', False) or
                getattr(self, '_fetching_bank_note', False)):
            return None

        if self.fourteen_day_high <= 0 or self.market_value <= 0:
            return None

        # Step 1: Calculate Score
        self.calculate_score()

        # Step 2: Dynamic Profit Target & Dynamic Stop Loss (ATR-based)
        atr = self.get_atr_14()
        if atr > 0:
            atr_pct = (atr / self.market_value) * 100.0
            dynamic_target_pct = self.atr_multiplier * atr_pct
            self.dynamic_profit_target = max(self.min_profit_pct, min(dynamic_target_pct, self.max_profit_pct)) / 100.0

            raw_stop_pct = self.stop_multiplier * atr_pct
            active_strat = self.bought_strategy or self.current_strategy
            max_stop_cap = 7.0 if active_strat == 'DIP' else 9.0
            self.dynamic_stop_loss = -max(abs(self.min_stop_loss), min(raw_stop_pct, max_stop_cap))

        if self.quantity > 0 and self.pnl_percent > self.highest_pnl:
            self.highest_pnl = self.pnl_percent
            if self.db_manager:
                self.db_manager.update_highest_pnl(self.stock_id, self.highest_pnl)

        if readonly or self.manual_mode:
            return None

        # Step 3: Evaluate Exit (Sell has priority)
        snapshot = self.data_feed.get_snapshot()
        exit_result = self.risk_manager.evaluate_exit(
            snapshot=snapshot,
            quantity=self.quantity,
            pnl_percent=self.pnl_percent,
            highest_pnl=self.highest_pnl,
            bought_price=self.bought_price,
            last_buy_time=self.last_buy_time,
            dynamic_profit_target=self.dynamic_profit_target,
            dynamic_stop_loss=self.dynamic_stop_loss,
            is_market_cooling_down=self.is_market_cooling_down(),
            prev_macd_signal=self.prev_macd_signal
        )

        if exit_result:
            action, reason = exit_result
            self.last_trade_reason = reason
            return action

        if self.quantity > 0:
            if self.macd_signal != self.prev_macd_signal:
                self.prev_macd_signal = self.macd_signal
            return None

        # Step 4: Evaluate Buy
        usable_cash = self.ibapi.available_cash - self.min_cash
        alpha_signal = AlphaSignal(
            strategy=self.current_strategy,
            smart_score=self.smart_score,
            base_score=self.base_score,
            score_reason=self.score_reason
        )

        decision = self.risk_manager.validate_buy(
            snapshot=snapshot,
            alpha_signal=alpha_signal,
            cash_left=self.cash_left,
            usable_cash=usable_cash,
            last_buy_time=self.last_buy_time,
            last_sell_time=self.last_sell_time,
            is_market_open=self.is_market_open(),
            is_market_cooling_down=self.is_market_cooling_down(),
            is_auto_watchlist=self.is_auto_watchlist
        )

        if not decision.allowed:
            return None

        self.bought_strategy = self.current_strategy
        if self.db_manager and hasattr(self.db_manager, 'update_bought_strategy'):
            self.db_manager.update_bought_strategy(self.stock_id, self.bought_strategy)
        self.last_trade_reason = self.score_reason
        return 'BUY'

    def place_buy_order(self) -> bool:
        usable_cash = self.ibapi.available_cash - self.min_cash
        if not self.is_market_open() or self.has_pending_order() or min(self.cash_left, usable_cash) < self.MIN_CASH_FOR_BUY:
            return False

        native_currency, primary_exchange = self.get_native_currency_and_exchange()
        latest = self.db_manager.get_latest_price(self.stock_id) if self.db_manager else None
        if not latest or time.time() - latest["fetched_at"] > 30:
            logger.warning(f"[{self.stock_id}] No fresh price -> skip buy")
            return False
        price_native = latest["price"]

        dynamic_max = getattr(self, 'current_max_investment', 0) or self._calculate_dynamic_max_amount()
        quantity, total_cost_eur, effective_limit = self.portfolio_sizer.calculate_order_sizing(
            cash_left=self.cash_left,
            usable_cash=usable_cash,
            price_native=price_native,
            native_currency=native_currency,
            dynamic_max=dynamic_max
        )

        if quantity < 1:
            logger.warning(f"Insufficient funds or Low Cash €{self.cash_left:,.0f} (Quantity < 1)")
            return False

        if hasattr(self, 'last_trade_reason') and self.last_trade_reason:
            reason = self.last_trade_reason
        else:
            drop_pct = (self.fourteen_day_high - self.market_value) / self.fourteen_day_high * 100 if self.fourteen_day_high > 0 else 0
            reason = f"Score:{self.smart_score} | Drop:{drop_pct:.1f}% | RSI:{self.rsi_value:.0f} | Vol:{self.today_volume/1e6:.1f}M"
            if self.score_reason:
                reason += f" | {self.score_reason}"
            if self.stock_id in self.PRIORITY_BUY_LIST:
                reason = "PRIORITY BUY - VIP LIST ★ " + reason

        oid = self.execution.place_buy_order(
            stock_id=self.stock_id,
            quantity=quantity,
            price_native=price_native,
            native_currency=native_currency,
            primary_exchange=primary_exchange,
            reason=reason,
            total_cost_eur=total_cost_eur,
            cash_left=self.cash_left,
            on_completed_cb=self._on_order_completed
        )

        if oid:
            self.pending_order_id = oid
            self.pending_order_time = time.time()
            self.last_quantity = self.quantity
            return True
        return False

    def place_sell_order(self) -> bool:
        if not self.is_market_open() or self.has_pending_order() or self.quantity == 0:
            return False

        latest = self.db_manager.get_latest_price(self.stock_id) if self.db_manager else None
        if not latest or time.time() - latest["fetched_at"] > 30:
            return False
        price_native = latest["price"]
        native_currency, primary_exchange = self.get_native_currency_and_exchange()

        reason = getattr(self, 'last_trade_reason', None) or f"PROFIT {self.pnl_percent:.1f}% | Score:{self.smart_score} | RSI:{self.rsi_value:.0f}"

        oid = self.execution.place_sell_order(
            stock_id=self.stock_id,
            quantity=self.quantity,
            price_native=price_native,
            native_currency=native_currency,
            primary_exchange=primary_exchange,
            reason=reason,
            on_completed_cb=self._on_order_completed
        )

        if oid:
            self.pending_order_id = oid
            self.pending_order_time = time.time()
            return True
        return False

    def get_buy_block_reason(self) -> str:
        snapshot = self.data_feed.get_snapshot()
        usable_cash = getattr(self.ibapi, 'available_cash', 0) - self.min_cash
        alpha_signal = AlphaSignal(
            strategy=self.current_strategy,
            smart_score=self.smart_score,
            base_score=self.base_score,
            score_reason=self.score_reason
        )
        decision = self.risk_manager.validate_buy(
            snapshot=snapshot,
            alpha_signal=alpha_signal,
            cash_left=self.cash_left,
            usable_cash=usable_cash,
            last_buy_time=self.last_buy_time,
            last_sell_time=self.last_sell_time,
            is_market_open=self.is_market_open(),
            is_market_cooling_down=self.is_market_cooling_down(),
            is_auto_watchlist=self.is_auto_watchlist
        )
        if not decision.allowed:
            return decision.reason
        return f"score qualifies ({self.smart_score}/12) but {self.current_strategy} entry conditions not satisfied"

    def get_status(self) -> str:
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
