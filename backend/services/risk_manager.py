# ==============================================================================
# pyTrade3 — RiskManagement Engine (risk_manager.py)
# Stage 4 in Lean Architecture: Hard Guards, Portfolio Vetoes & Multi-Tier Exits
# Consolidates PDTProtector
# ==============================================================================

import time
import threading
import collections
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, Any
import yfinance as yf
from config import logger
from .models import MarketSnapshot, AlphaSignal, RiskDecision

# ==================== PDT PROTECTOR ====================
class PDTProtector:
    """Enforces IBKR Pattern Day Trader regulation (max 3 day trades per rolling 5 business days)."""
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

    def count_day_trades_5d(self) -> int:
        self._cleanup()
        return len(self.day_trades)

    def register_day_trade_if_needed(self, symbol: Optional[str] = None):
        self._load_history()

    def can_trade(self) -> bool:
        return self.count_day_trades_5d() < 3


# ==================== RISK MANAGEMENT ENGINE ====================
class RiskManagementEngine:
    """
    Enforces all 13 Hard Buy Safeguards and 7 Exit Triggers defined in AGENTS.md.
    Acts as the iron gatekeeper with veto power over any trade intention.
    """
    MIN_CASH_FOR_BUY = 500.0
    TIME_STOP_DAYS = 25
    TIME_STOP_MAX_PNL = -0.5
    MAX_SECTOR_POSITIONS = 6

    # Class-level Macro Market Guard
    _macro_cache = {'time': 0, 'drop_pct': 0.0, 'status': 'GREEN'}
    _macro_lock = threading.Lock()
    MACRO_TICKER = "^GSPC"        # S&P 500 Index
    MACRO_DROP_LIMIT = -0.015     # -1.5% drop blocks DIP buys

    def __init__(self, db_manager=None, app=None):
        self.db_manager = db_manager
        self.app = app
        self._last_sell_log: Dict[str, float] = {}

    @classmethod
    def check_macro_guard(cls) -> Dict[str, Any]:
        """Fetches S&P 500 drop % with a 5-minute cache to prevent API spam."""
        now = time.time()
        with cls._macro_lock:
            if now - cls._macro_cache['time'] > 300:
                try:
                    ticker = yf.Ticker(cls.MACRO_TICKER)
                    hist = ticker.history(period="2d")
                    if len(hist) >= 2:
                        prev_close = float(hist['Close'].iloc[-2])
                        current_price = float(hist['Close'].iloc[-1])
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

    def throttled_sell_log(self, key: str, msg: str, interval: int = 300):
        """Logs sell warnings at most once per interval per key."""
        now = time.time()
        if now - self._last_sell_log.get(key, 0) >= interval:
            logger.info(msg)
            self._last_sell_log[key] = now

    def evaluate_exit(
        self,
        snapshot: MarketSnapshot,
        quantity: int,
        pnl_percent: float,
        highest_pnl: float,
        bought_price: float,
        last_buy_time: float,
        dynamic_profit_target: float,
        dynamic_stop_loss: float,
        is_market_cooling_down: bool,
        prev_macd_signal: str
    ) -> Optional[Tuple[str, str]]:
        """Evaluates the 7 Sell/Exit Triggers in exact priority order from AGENTS.md."""
        if quantity <= 0:
            return None

        # 0. Market Open Cooldown (Wait 30 mins)
        if is_market_cooling_down:
            self.throttled_sell_log("market_cooldown", f"[{snapshot.stock_id}] Market Open Cooldown (30m): Pausing automated sells.", interval=60)
            return None

        # PDT Day-Trade Protection
        is_day_trade = False
        if last_buy_time > 0:
            last_buy_date = datetime.fromtimestamp(last_buy_time).date()
            if last_buy_date == datetime.now().date():
                is_day_trade = True

        if is_day_trade and self.app and hasattr(self.app, 'pdt_protector'):
            if not self.app.pdt_protector.can_trade():
                self.throttled_sell_log("pdt_block", f"[{snapshot.stock_id}] PDT LIMIT: Holding day-trade SELL to avoid 90-day lock.")
                return None

        # 1. Dynamic ATR Trailing Profit Lock
        profit_target_pct = dynamic_profit_target * 100.0
        current_atr_pct = (snapshot.atr14 / snapshot.market_price) * 100.0 if snapshot.market_price > 0 else 0.0
        dynamic_trail_drop = max(0.5, min(current_atr_pct * 0.5, 1.5))

        if highest_pnl >= profit_target_pct:
            trail_activation = highest_pnl - dynamic_trail_drop
            if pnl_percent <= trail_activation:
                reason = f"Trailing Profit Triggered at {pnl_percent:.2f}% (Peak: {highest_pnl:.2f}%, Trail: {dynamic_trail_drop:.2f}%)"
                self.throttled_sell_log("trailing_profit", f"[{snapshot.stock_id}] {reason}")
                return 'SELL', reason

        # 2. Proportional Protective Trailing Stop (75% floor once peak >= 5%)
        elif highest_pnl >= 5.0:
            protective_trail_drop = highest_pnl * 0.25
            protective_floor = highest_pnl - protective_trail_drop
            if pnl_percent <= protective_floor:
                reason = f"Protective Stop Triggered at {pnl_percent:.2f}% (Peak: {highest_pnl:.2f}%, Trail: {protective_trail_drop:.2f}%)"
                self.throttled_sell_log("protective_stop", f"[{snapshot.stock_id}] {reason}")
                return 'SELL', reason

        # 3. Dynamic ATR Stop Loss
        if pnl_percent <= dynamic_stop_loss:
            reason = f"ATR Stop Loss Triggered at {dynamic_stop_loss:.1f}%"
            self.throttled_sell_log("atr_stop_loss", f"[{snapshot.stock_id}] {reason}")
            return 'SELL', reason

        # 4. RSI Overbought Exit (>= 80 and pnl > +1%)
        if snapshot.rsi >= 80 and pnl_percent > 1.0:
            reason = f"RSI Overbought Exit at RSI {snapshot.rsi:.0f} (PnL: {pnl_percent:.2f}%)"
            self.throttled_sell_log("rsi_overbought", f"[{snapshot.stock_id}] {reason}")
            return 'SELL', reason

        # 5. MACD Bearish Reversal Exit (only on transition from Bullish to Bearish)
        if (snapshot.macd_signal in ("S_BEAR", "BEAR") and
                prev_macd_signal in ("S_BULL", "BULL") and
                pnl_percent > 1.0):
            reason = f"MACD Bearish Crossover Exit ({prev_macd_signal} → {snapshot.macd_signal}, PnL: {pnl_percent:.2f}%)"
            self.throttled_sell_log("macd_crossover", f"[{snapshot.stock_id}] {reason}")
            return 'SELL', reason

        # 6. Analyst Target Override (Price is 10%+ above analyst target and pnl > +0.5%)
        if pnl_percent > 0.5:
            analyst_target = None
            bank_data = self.db_manager.get_cached_bank_note(snapshot.stock_id) if self.db_manager else None
            if bank_data and bank_data[0] and bank_data[0] > 0:
                analyst_target = bank_data[0]
            elif snapshot.target_price and snapshot.target_price > 0:
                analyst_target = snapshot.target_price

            if analyst_target and snapshot.market_price > 0:
                temp_target = analyst_target
                if snapshot.stock_id.upper().endswith(".L") and snapshot.market_price > temp_target * 10:
                    temp_target = temp_target * 100
                elif snapshot.market_price > 10 and temp_target < 10:
                    temp_target = temp_target * 100

                if snapshot.market_price >= temp_target * 1.10:
                    reason = f"Analyst Target Exit: price {snapshot.market_price:.2f} is 10%+ above target {temp_target:.2f} (PnL: {pnl_percent:.2f}%)"
                    self.throttled_sell_log("analyst_target", f"[{snapshot.stock_id}] {reason}")
                    return 'SELL', reason

        # 7. Time-Stop Stagnation Exit (held >= 25d and pnl <= -0.5%)
        if last_buy_time > 0:
            held_days = (time.time() - last_buy_time) / 86400.0
            if held_days >= self.TIME_STOP_DAYS and pnl_percent <= self.TIME_STOP_MAX_PNL:
                reason = f"Time-Stop Stagnation Exit after {held_days:.0f}d held (PnL: {pnl_percent:.2f}% <= {self.TIME_STOP_MAX_PNL:.1f}%)"
                self.throttled_sell_log("time_stop", f"[{snapshot.stock_id}] {reason}")
                return 'SELL', reason

        return None

    def validate_buy(
        self,
        snapshot: MarketSnapshot,
        alpha_signal: AlphaSignal,
        cash_left: float,
        usable_cash: float,
        last_buy_time: float,
        last_sell_time: float,
        is_market_open: bool,
        is_market_cooling_down: bool,
        is_auto_watchlist: bool = False
    ) -> RiskDecision:
        """Validates all 13 Hard Buy Safeguards before permitting a BUY order."""
        now = time.time()

        # Guard 1 & 2: 24h Cooldown
        if now - last_buy_time < 86400 or now - last_sell_time < 86400:
            return RiskDecision(allowed=False, reason="buy/sell 24h cooldown active")

        # Guard 3: Earnings Blackout (-3 days to +2 days)
        if snapshot.next_earnings_date and snapshot.next_earnings_date != "No payment":
            try:
                earn_date = datetime.strptime(snapshot.next_earnings_date, "%Y-%m-%d").date()
                days = (earn_date - datetime.now().date()).days
                if -2 <= days <= 3:
                    return RiskDecision(allowed=False, reason=f"earnings report in {days} days")
            except ValueError:
                pass

        # Guard 4: Usable Cash & Market Open
        effective_cash = min(cash_left, usable_cash)
        if not is_market_open:
            return RiskDecision(allowed=False, reason="market closed")
        if effective_cash < self.MIN_CASH_FOR_BUY:
            return RiskDecision(allowed=False, reason=f"insufficient cash (available: €{effective_cash:.0f}, min: €{self.MIN_CASH_FOR_BUY:.0f})")

        # Guard 5: Market Open Cooldown (30m)
        if is_market_cooling_down:
            return RiskDecision(allowed=False, reason="market open 30m cooldown active")

        # Guard 6: Daily Rise Cap (+5.0%)
        if snapshot.previous_close > 0:
            daily_change = (snapshot.market_price - snapshot.previous_close) / snapshot.previous_close
            if daily_change > 0.05:
                return RiskDecision(allowed=False, reason=f"daily rise ({daily_change*100:.1f}%) exceeds 5% limit")

        # Guard 7: RSI Overbought Filter (RSI >= 70)
        if snapshot.rsi >= 70:
            return RiskDecision(allowed=False, reason=f"overbought zone (RSI {snapshot.rsi:.1f} >= 70)")

        # Guard 8: 3-Day Cumulative Rise Cap (+15.0%)
        if snapshot.close_3d_ago > 0:
            three_day_change = (snapshot.market_price - snapshot.close_3d_ago) / snapshot.close_3d_ago
            if three_day_change > 0.15:
                return RiskDecision(allowed=False, reason=f"3-day cumulative rise ({three_day_change*100:.1f}%) exceeds 15% limit")

        # Guard 9: Auto-Watchlist Downtrend Guard (Price >= MA200)
        if is_auto_watchlist:
            if snapshot.ma200 > 0 and snapshot.market_price < snapshot.ma200:
                return RiskDecision(allowed=False, reason=f"Auto-Watchlist downtrend guard (price {snapshot.market_price:.2f} < MA200 {snapshot.ma200:.2f})")

        # Guard 10: Sector Exposure Cap (<= 6 positions per sector)
        if (snapshot.asset_type.upper() not in ("ETF", "ETC") and
                snapshot.sector not in ("N/A", "Unknown", "", None) and
                self.app and hasattr(self.app, 'bots')):
            sector_open_count = sum(
                1 for b in self.app.bots.values()
                if b.stock_id != snapshot.stock_id
                and (b.quantity > 0 or b.has_pending_order())
                and getattr(b, 'sector', 'N/A') == snapshot.sector
            )
            if sector_open_count >= self.MAX_SECTOR_POSITIONS:
                return RiskDecision(allowed=False, reason=f"sector exposure cap reached ({sector_open_count}/{self.MAX_SECTOR_POSITIONS} open in {snapshot.sector})")

        # Guard 11: Portfolio Score Priority
        if self.app and hasattr(self.app, 'bots'):
            highest_score = max(
                [b.smart_score for b in self.app.bots.values() if b.cash_left >= getattr(b, 'MIN_CASH_FOR_BUY', 500)],
                default=0
            )
            if alpha_signal.smart_score < highest_score:
                top_stock = next(
                    (b.stock_id for b in self.app.bots.values()
                     if b.smart_score == highest_score and b.cash_left >= getattr(b, 'MIN_CASH_FOR_BUY', 500)),
                    "another stock"
                )
                return RiskDecision(allowed=False, reason=f"lower portfolio priority (score {alpha_signal.smart_score}/12 vs {top_stock} at {highest_score}/12)")

            if alpha_signal.smart_score == highest_score and is_market_open:
                for b in self.app.bots.values():
                    if (b.cash_left >= getattr(b, 'MIN_CASH_FOR_BUY', 500)
                            and b.smart_score == highest_score
                            and not b.is_market_open()):
                        return RiskDecision(allowed=False, reason=f"waiting for tied top-scorer {b.stock_id} (score {highest_score}/12) market to open")

        # Guard 12 & 13: Strategy Entry & Falling Knife Guards
        if alpha_signal.strategy == "DIP":
            if alpha_signal.smart_score < 7:
                return RiskDecision(allowed=False, reason=f"DIP score ({alpha_signal.smart_score}/12) below threshold 7")
            if alpha_signal.base_score < 5:
                return RiskDecision(allowed=False, reason=f"DIP base technical score too weak (base={alpha_signal.base_score}/10, need >= 5)")

            macro_status = self.check_macro_guard()
            if macro_status['drop_pct'] <= self.MACRO_DROP_LIMIT:
                return RiskDecision(allowed=False, reason=f"Macro Market Guard Active ({macro_status['status']})")

            if snapshot.previous_close > 0:
                daily_drop = (snapshot.market_price - snapshot.previous_close) / snapshot.previous_close
                if daily_drop < -0.07:
                    return RiskDecision(allowed=False, reason=f"daily drop ({daily_drop*100:.1f}%) exceeds -7% falling knife limit")
                if daily_drop < -0.03 and snapshot.rsi > 45:
                    return RiskDecision(allowed=False, reason=f"falling knife guard (drop {daily_drop*100:.1f}% with RSI {snapshot.rsi:.1f} > 45)")

        elif alpha_signal.strategy == "MOMENTUM":
            if alpha_signal.smart_score < 8:
                return RiskDecision(allowed=False, reason=f"MOMENTUM score ({alpha_signal.smart_score}/12) below threshold 8")
            if alpha_signal.base_score < 6:
                return RiskDecision(allowed=False, reason=f"MOMENTUM base technical score too weak (base={alpha_signal.base_score}/10, need >= 6)")

            if snapshot.previous_close > 0:
                daily_change = (snapshot.market_price - snapshot.previous_close) / snapshot.previous_close
                yesterday_change = 0.0
                if snapshot.day_before_yesterday_close > 0:
                    yesterday_change = (snapshot.previous_close - snapshot.day_before_yesterday_close) / snapshot.day_before_yesterday_close

                atr = snapshot.atr14
                atr_pct = (atr / snapshot.previous_close) if snapshot.previous_close > 0 else 0.025
                daily_threshold = min(0.08, max(0.03, atr_pct * 2.0))
                yesterday_threshold = min(0.08, max(0.05, atr_pct * 2.5))

                if daily_change > daily_threshold:
                    return RiskDecision(allowed=False, reason=f"MOMENTUM blocked: parabolic rise today ({daily_change*100:.1f}% > {daily_threshold*100:.1f}%)")
                if yesterday_change > yesterday_threshold:
                    return RiskDecision(allowed=False, reason=f"MOMENTUM blocked: parabolic rise yesterday ({yesterday_change*100:.1f}% > {yesterday_threshold*100:.1f}%)")

            if snapshot.rsi > 70:
                return RiskDecision(allowed=False, reason=f"MOMENTUM blocked: RSI overbought ({snapshot.rsi:.1f})")

        return RiskDecision(allowed=True, action="BUY", reason=alpha_signal.score_reason)

