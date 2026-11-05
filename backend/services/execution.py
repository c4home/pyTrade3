# ==============================================================================
# pyTrade3 — Execution Service (execution.py)
# Stage 5 in Lean Architecture: Broker Interaction (IBKR), Order Lifecycle & CSV/DB Audits
# ==============================================================================

import time
import re
from typing import Tuple, Optional, Callable
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.tag_value import TagValue
from config import logger

class ExecutionService:
    """
    Directly interfaces with Interactive Brokers (IBKR TWS / Gateway API).
    Manages order creation, execution callbacks, timeouts, and audit logging.
    """
    def __init__(self, ibapi, db_manager=None, csv_manager=None, app=None):
        self.ibapi = ibapi
        self.db_manager = db_manager
        self.csv_manager = csv_manager
        self.app = app
        self.order_timeout = 300  # 5 minutes

    @staticmethod
    def get_native_currency_and_exchange(stock_id: str) -> Tuple[str, str]:
        """Resolves primary exchange and currency from symbol ticker."""
        symbol = stock_id.upper()
        if symbol.endswith(".L"):
            return "GBP", "LSE"
        elif symbol.endswith(".PA"):
            return "EUR", "SBF"
        elif symbol.endswith(".AS"):
            return "EUR", "EURONEXT"
        elif symbol.endswith(".BR"):
            return "EUR", "EURONEXT"
        elif symbol.endswith(".DE"):
            return "EUR", "IBIS"
        elif symbol.endswith(".TO"):
            return "CAD", "TSE"
        elif symbol.endswith(".HK"):
            return "HKD", "SEHK"
        else:
            return "USD", "NASDAQ"

    def has_pending_order(self, pending_order_id: Optional[int], pending_order_time: Optional[float]) -> bool:
        """Checks if there is an active pending order that has not timed out."""
        if not pending_order_id:
            return False
        if pending_order_time and time.time() - pending_order_time > self.order_timeout:
            return False
        return True

    def place_buy_order(
        self,
        stock_id: str,
        quantity: int,
        price_native: float,
        native_currency: str,
        primary_exchange: str,
        reason: str,
        total_cost_eur: float,
        cash_left: float,
        on_completed_cb: Callable
    ) -> Optional[int]:
        """Places adaptive market BUY order via IBKR socket."""
        if quantity < 1 or price_native <= 0 or not self.ibapi:
            return None

        ibkr_symbol = re.sub(r'\..*$', '', stock_id)
        contract = Contract()
        contract.symbol = ibkr_symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = native_currency
        contract.primaryExchange = primary_exchange

        order = Order()
        order.action = "BUY"
        order.orderType = "MKT"
        order.totalQuantity = quantity
        if native_currency == "USD":  # Adaptive algo is rejected (error 442) on many EU exchanges
            order.algoStrategy = "Adaptive"
            setattr(order, "algoParams", [TagValue("adaptivePriority", "Normal")])
        order.eTradeOnly = False
        order.firmQuoteOnly = False
        order.tif = "DAY"
        order.transmit = True

        oid = self.ibapi.get_next_order_id()
        self.ibapi.order_callbacks[oid] = lambda order_id, status, filled, avg_price: on_completed_cb(
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

        if self.csv_manager:
            self.csv_manager.save_order(
                order_id=oid,
                stock_id=stock_id,
                action="BUY",
                quantity=quantity,
                price=price_native,
                currency=native_currency,
                status="Pending",
                reason=reason
            )

        logger.info(f"BUY {quantity} {stock_id} @ {price_native:.2f} {native_currency} "
                    f"(€{total_cost_eur:.0f} used, €{cash_left - total_cost_eur:.0f} left)")
        return oid

    def place_sell_order(
        self,
        stock_id: str,
        quantity: int,
        price_native: float,
        native_currency: str,
        primary_exchange: str,
        reason: str,
        on_completed_cb: Callable
    ) -> Optional[int]:
        """Places adaptive market SELL order via IBKR socket."""
        if quantity <= 0 or price_native <= 0 or not self.ibapi:
            return None

        ibkr_symbol = re.sub(r'\..*$', '', stock_id)
        contract = Contract()
        contract.symbol = ibkr_symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = native_currency
        contract.primaryExchange = primary_exchange

        order = Order()
        order.action = "SELL"
        order.orderType = "MKT"
        order.totalQuantity = quantity
        if native_currency == "USD":  # Adaptive algo is rejected (error 442) on many EU exchanges
            order.algoStrategy = "Adaptive"
            setattr(order, "algoParams", [TagValue("adaptivePriority", "Normal")])
        order.eTradeOnly = False
        order.firmQuoteOnly = False
        order.tif = "DAY"
        order.transmit = True

        oid = self.ibapi.get_next_order_id()
        self.ibapi.order_callbacks[oid] = lambda order_id, status, filled, avg_price: on_completed_cb(
            order_id=order_id,
            status=status,
            action="SELL",
            quantity=quantity,
            price=price_native,
            filled=filled,
            avg_fill_price=avg_price,
            currency=native_currency,
            reason=reason
        )

        self.ibapi.placeOrder(oid, contract, order)

        if self.csv_manager:
            self.csv_manager.save_order(
                order_id=oid,
                stock_id=stock_id,
                action="SELL",
                quantity=quantity,
                price=price_native,
                currency=native_currency,
                status="Pending",
                reason=reason
            )

        logger.info(f"SELL {quantity} {stock_id} @ {price_native:.2f} {native_currency}")
        return oid

