import time
from typing import Any

from backend.config import logger


class TradingOrchestrator:
    """Manages autonomous trading cycle: position updates, sell evaluations, buy ranking and order execution."""

    @classmethod
    def run_loop(cls, app: Any) -> None:
        """Executes the continuous trading evaluation loop while app.auto_trading is active."""
        while app.auto_trading:
            if (
                app.connected
                and hasattr(app, "ibapi")
                and app.ibapi
                and getattr(app.ibapi, "isConnected", lambda: False)()
            ):
                try:
                    app.ibapi.reqPositions()
                except Exception as e:
                    logger.warning(f"Error requesting positions in trading loop: {e}")
                time.sleep(3)

                # 1. Evaluate and Execute Sell Orders Immediately (First Priority)
                for sid, bot in app.bots.items():
                    if (
                        bot.is_running
                        and not bot.has_pending_order()
                        and bot.is_market_open()
                        and bot.get_market_value() > 0
                        and bot.quantity > 0
                    ):
                        last_order = app.order_cooldown.get(sid, 0)
                        if time.time() - last_order < 300:
                            continue

                        action = bot.check_trading_conditions()
                        if action == "SELL":
                            if bot.place_sell_order():
                                app.order_cooldown[sid] = time.time()
                                time.sleep(30)

                # 2. Collect Eligible Buy Candidates
                buy_candidates = []
                for sid, bot in app.bots.items():
                    if (
                        bot.is_running
                        and not bot.has_pending_order()
                        and bot.is_market_open()
                        and bot.get_market_value() > 0
                        and bot.cash_left >= getattr(bot, "MIN_CASH_FOR_BUY", 500)
                    ):
                        last_order = app.order_cooldown.get(sid, 0)
                        if time.time() - last_order < 300:
                            continue

                        action = bot.check_trading_conditions()
                        if action == "BUY":
                            buy_candidates.append(bot)

                # 3. Sort Candidates by Smart Score (Tie-break by highest analyst target upside percentage)
                def sort_key(b):
                    return (b.smart_score, getattr(b, "target_upside_pct", 0.0))

                buy_candidates.sort(key=sort_key, reverse=True)

                # 4. Execute Buy Orders Sequentially
                for bot in buy_candidates:
                    usable_cash = bot.ibapi.available_cash - getattr(app, "min_cash", 0.0)
                    if min(bot.cash_left, usable_cash) < bot.MIN_CASH_FOR_BUY:
                        logger.info(
                            f"[{bot.stock_id}] Skipping buy candidate: remaining cash is insufficient (usable cash: €{usable_cash:,.2f})."
                        )
                        continue

                    if bot.place_buy_order():
                        app.order_cooldown[bot.stock_id] = time.time()
                        time.sleep(30)

            time.sleep(15)

