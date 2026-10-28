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
        self.last_socket_ping = 0
        self.ibkr_backend_connected = False
        self.ibkr_backend_issue_reason = ""
        self.broken_farms = set()
        self.consecutive_ping_failures = 0

    def managedAccounts(self, accountsList: str):
        with self.data_lock:
            if self.ibkr_backend_connected:
                self.last_ibkr_update = time.time()
            if accountsList:
                self.account_id = accountsList.split(',')[0]
                logger.info(f"Connected IBKR Account: {self.account_id}")
                try:
                    self.reqPnL(7001, self.account_id, "")
                    self.reqAccountUpdates(True, self.account_id)
                except Exception as e:
                    logger.warning(f"Could not request IBKR PnL stream: {e}")

    def currentTime(self, time_val: int):
        with self.data_lock:
            # Note: Do NOT update self.last_ibkr_update here because reqCurrentTime()
            # responds from local TWS clock even when IBKR session is logged out / competing session.
            self.last_socket_ping = time.time()

    def nextValidId(self, orderId: int):
        self.next_order_id = orderId
        self.ibkr_backend_connected = True
        self.ibkr_backend_issue_reason = ""
        self.broken_farms.clear()
        self.consecutive_ping_failures = 0
        self.connected_event.set()

    def get_next_order_id(self):
        if self.next_order_id is None:
            raise RuntimeError("Next order ID not received yet. Is TWS/IB Gateway connected?")
        current_id = self.next_order_id
        self.next_order_id += 1  # Increment for next use
        return current_id
    
    def connectionClosed(self):
        logger.warning("🚨 IBKR TWS/Gateway socket connection was closed by host.")
        self.ibkr_backend_connected = False
        self.ibkr_backend_issue_reason = "TWS/Gateway đã đóng kết nối socket"
        self.connected_event.clear()
        self.cash_ready_event.clear()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson="", *args, **kwargs):
        err_lower = (errorString or "").lower()
        is_competing_or_session_lost = any(
            kw in err_lower for kw in (
                "competing",
                "existing session",
                "connectivity between ib",
                "connectivity between trader workstation",
                "re-login",
                "not connected",
                "session is broken",
            )
        )

        # 1. Explicit IBKR server connectivity restored (1101, 1102)
        if errorCode in [1101, 1102]:
            logger.info(f"✅ IBKR Server Connectivity Restored {reqId}: [{errorCode}] {errorString}")
            with self.data_lock:
                self.ibkr_backend_connected = True
                self.ibkr_backend_issue_reason = ""
                self.broken_farms.clear()
                self.consecutive_ping_failures = 0
                self.last_ibkr_update = time.time()
            self.connected_event.set()
            return

        # 2. Explicit connection / backend session lost or competing login (502, 504, 1100, 1300, 2100, 2110, 10197)
        if errorCode in [502, 504, 1100, 1300, 2100, 2110, 10197] or is_competing_or_session_lost:
            logger.warning(f"⚠️ IBKR Connection/Session Event {reqId}: [{errorCode}] {errorString}")
            with self.data_lock:
                self.ibkr_backend_connected = False
                self.ibkr_backend_issue_reason = (
                    f"Vẫn kết nối TWS/Gateway nhưng mất phiên làm việc với máy chủ IBKR "
                    f"(nghi ngờ đăng nhập trên thiết bị khác / cần Re-login) [{errorCode}: {errorString}]"
                )
            if errorCode in [502, 504, 1100, 1300]:
                self.connected_event.clear()
                self.cash_ready_event.clear()
            return

        # 3. Data farm broken (2103: Market data, 2105: HMDS, 2157: Sec-def)
        if errorCode in [2103, 2105, 2157]:
            logger.warning(f"⚠️ IBKR Data Farm Broken {reqId}: [{errorCode}] {errorString}")
            with self.data_lock:
                self.broken_farms.add(errorCode)
                # Market data (2103) or Sec-def (2157) breaking typically happens when another device takes over the session
                if errorCode in [2103, 2157]:
                    self.ibkr_backend_connected = False
                    self.ibkr_backend_issue_reason = (
                        f"Ngắt kết nối dữ liệu với máy chủ IBKR (có thể do đăng nhập trên thiết bị khác) "
                        f"[{errorCode}: {errorString}]"
                    )
            return

        # 4. Data farm restored (2104 -> 2103, 2106 -> 2105, 2158 -> 2157)
        if errorCode in [2104, 2106, 2158]:
            farm_map = {2104: 2103, 2106: 2105, 2158: 2157}
            with self.data_lock:
                self.broken_farms.discard(farm_map.get(errorCode))
                if not self.broken_farms and self.next_order_id is not None:
                    self.ibkr_backend_connected = True
                    self.ibkr_backend_issue_reason = ""
                    self.consecutive_ping_failures = 0
                    self.last_ibkr_update = time.time()
                    self.connected_event.set()
            return

        # Ignore minor order cancellation acknowledgment codes
        if errorCode in [10147, 202]:
            if hasattr(self, 'order_callbacks'):
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
            if self.ibkr_backend_connected:
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
            if self.ibkr_backend_connected:
                self.last_ibkr_update = time.time()
            if dailyPnL is not None and not math.isnan(dailyPnL):
                self.daily_pnl = float(dailyPnL)
            if unrealizedPnL is not None and not math.isnan(unrealizedPnL):
                self.unrealized_pnl = float(unrealizedPnL)
            if realizedPnL is not None and not math.isnan(realizedPnL):
                self.realized_pnl = float(realizedPnL)

    def accountSummaryEnd(self, reqId: int):
        with self.data_lock:
            if self.ibkr_backend_connected:
                self.last_ibkr_update = time.time()
            self.portfolio_value = self.net_liquidation - self.total_cash
        self.cash_ready_event.set()

    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        with self.data_lock:
            if self.ibkr_backend_connected:
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
            if self.ibkr_backend_connected:
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
            if self.ibkr_backend_connected:
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

