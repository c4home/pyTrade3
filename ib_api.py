import math
from config import *
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
        
        # ---- CASH & PNL ----
        self.net_liquidation = 0.0
        self.total_cash = 0.0
        self.available_cash = 0.0 
        self.portfolio_value = 0.0
        self.daily_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.realized_pnl = 0.0
        self.account_id = ""
        self.cash_ready_event = threading.Event()
        self.last_cash_fetch = 0
        self.cash_fetch_interval = 20      # seconds
        self.max_cash_cache_age = 10800
        self.last_ibkr_update = 0

    def managedAccounts(self, accountsList: str):
        with self.data_lock:
            self.last_ibkr_update = time.time()
            if accountsList:
                self.account_id = accountsList.split(',')[0]
                logger.info(f"Connected IBKR Account: {self.account_id}")
                try:
                    self.reqPnL(7001, self.account_id, "")
                    self.reqAccountUpdates(True, self.account_id)
                except Exception as e:
                    logger.warning(f"Could not request IBKR PnL stream: {e}")

    def nextValidId(self, orderId: int):
        self.next_order_id = orderId
        self.connected_event.set()

    def get_next_order_id(self):
        if self.next_order_id is None:
            raise RuntimeError("Next order ID not received yet. Is TWS/IB Gateway connected?")
        current_id = self.next_order_id
        self.next_order_id += 1  # Increment for next use
        return current_id
    
    def connectionClosed(self):
        logger.warning("🚨 IBKR TWS/Gateway socket connection was closed by host.")
        self.connected_event.clear()
        self.cash_ready_event.clear()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson="", *args, **kwargs):
        # Explicit connection status codes (e.g. 502, 504, 1100 connection lost/restored)
        if errorCode in [502, 504, 1100, 1101, 1102]:
            logger.warning(f"⚠️ IBKR Connection Event {reqId}: [{errorCode}] {errorString}")
            if errorCode in [502, 504, 1100]:
                self.connected_event.clear()
                self.cash_ready_event.clear()
            return

        # Ignore minor informational notification codes and order cancellation acknowledgment
        if errorCode in [2104, 2106, 2158, 10147, 202]:
            if errorCode in [10147, 202] and hasattr(self, 'order_callbacks'):
                self.order_callbacks.pop(reqId, None)
            return

        logger.error(f"Error {reqId}: {errorCode} - {errorString}")
        
        # Automatically cancel order if an error/warning occurs for an active order we placed
        if hasattr(self, 'order_callbacks') and reqId in self.order_callbacks:
            # Pop callback FIRST before cancelOrder to prevent recursive infinite loops
            self.order_callbacks.pop(reqId, None)
            logger.warning(f"Automatically cancelling order {reqId} due to error/warning {errorCode}: {errorString}")
            try:
                self.cancelOrder(reqId)
            except Exception as e:
                logger.error(f"Failed to send cancel request for order {reqId}: {e}")
        
    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        with self.data_lock:
            self.last_ibkr_update = time.time()
            self.account_id = account
            try:
                val = float(value)
            except ValueError:
                val = 0.0
            if tag == "NetLiquidation":
                self.net_liquidation = val
            elif tag == "TotalCashValue":
                self.total_cash = val
            elif tag == "AvailableFunds":
                self.available_cash = val
            elif tag == "DailyPnL":
                self.daily_pnl = val
            elif tag == "UnrealizedPnL":
                self.unrealized_pnl = val
            elif tag == "RealizedPnL":
                self.realized_pnl = val

    def pnl(self, reqId: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float):
        with self.data_lock:
            self.last_ibkr_update = time.time()
            if dailyPnL is not None and not math.isnan(dailyPnL):
                self.daily_pnl = float(dailyPnL)
            if unrealizedPnL is not None and not math.isnan(unrealizedPnL):
                self.unrealized_pnl = float(unrealizedPnL)
            if realizedPnL is not None and not math.isnan(realizedPnL):
                self.realized_pnl = float(realizedPnL)

    def accountSummaryEnd(self, reqId: int):
        with self.data_lock:
            self.last_ibkr_update = time.time()
            self.portfolio_value = self.net_liquidation - self.total_cash
        self.cash_ready_event.set()

    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        with self.data_lock:
            self.last_ibkr_update = time.time()
            key = contract.symbol
            if key not in self.positions:
                self.positions[key] = {}
            self.positions[key].update({
                'symbol': contract.symbol,
                'position': int(position),
                'avgCost': avgCost,
                'account': account
            })

    def updatePortfolio(self, contract: Contract, position: float, marketPrice: float,
                        marketValue: float, averageCost: float, unrealizedPNL: float,
                        realizedPNL: float, accountName: str):
        with self.data_lock:
            self.last_ibkr_update = time.time()
            key = contract.symbol
            if key not in self.positions:
                self.positions[key] = {}
            
            self.positions[key].update({
                'symbol': contract.symbol,
                'position': int(position),
                'avgCost': averageCost,
                'marketPrice': marketPrice,
                'marketValue': marketValue,
                'unrealizedPNL': unrealizedPNL,
                'realizedPNL': realizedPNL,
                'account': accountName
            })

    def orderStatus(self, orderId: int, status: str, filled: float, remaining: float,
                    avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float,
                    clientId: int, whyHeld: str, mktCapPrice: float):
        with self.data_lock:
            self.last_ibkr_update = time.time()
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

