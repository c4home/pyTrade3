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

        # ---- MARKET DATA STREAMING (US Non-Consolidated & EU BATS/Chi-X) ----
        self.mkt_data = {}  # stock_id -> {price, bid, ask, last, high, low, volume, prev_close, open, last_update}
        self.req_id_to_stock_id = {}
        self.stock_id_to_req_id = {}
        self.next_mkt_req_id = 50000

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
        try:
            self.reqMarketDataType(1)  # 1 = Real-time streaming (Non-Consolidated & BATS/Chi-X)
            logger.info("📡 IBKR MarketDataType set to 1 (Real-Time Streaming)")
        except Exception as e:
            logger.warning(f"Could not set MarketDataType to 1: {e}")
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
        with self.data_lock:
            self.req_id_to_stock_id.clear()
            self.stock_id_to_req_id.clear()
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

        # Market data informational notices (10167, 10089: delayed data available, 354: not subscribed, 300: can't find EId)
        if errorCode in [10167, 10089, 354, 300]:
            logger.info(f"ℹ️ IBKR Market Data Notice {reqId}: [{errorCode}] {errorString}")
            return

        logger.error(f"Error {reqId}: {errorCode} - {errorString}")
        
        # Automatically cancel order if an error/warning occurs for an active order we placed
        if hasattr(self, 'order_callbacks') and reqId in self.order_callbacks:
            # Pop callback FIRST before cancelOrder to prevent recursive infinite loops
            self.order_callbacks.pop(reqId, None)
            logger.warning(f"Automatically cancelling order {reqId} due to error/warning {errorCode}: {errorString}")
            try:
                try:
                    self.cancelOrder(reqId, "")  # newer ibapi requires manualCancelOrderTime
                except TypeError:
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

    # ==================== MARKET DATA STREAMING ====================
    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        if price is None or price <= 0 or math.isnan(price):
            return
        with self.data_lock:
            stock_id = self.req_id_to_stock_id.get(reqId)
            if not stock_id:
                return
            if stock_id not in self.mkt_data:
                self.mkt_data[stock_id] = {
                    'price': 0.0, 'bid': 0.0, 'ask': 0.0, 'last': 0.0,
                    'high': 0.0, 'low': 0.0, 'volume': 0.0, 'prev_close': 0.0,
                    'open': 0.0, 'last_update': 0
                }
            entry = self.mkt_data[stock_id]
            entry['last_update'] = time.time()
            if self.ibkr_backend_connected:
                self.last_ibkr_update = time.time()

            if tickType == 1:       # Bid
                entry['bid'] = price
            elif tickType == 2:     # Ask
                entry['ask'] = price
            elif tickType == 4:     # Last Price
                entry['last'] = price
                entry['price'] = price
            elif tickType == 6:     # High
                entry['high'] = price
            elif tickType == 7:     # Low
                entry['low'] = price
            elif tickType == 9:     # Close (Prev Close)
                entry['prev_close'] = price
            elif tickType == 14:    # Open
                entry['open'] = price

            # Fallback for 'price' if Last is not yet available
            if entry['price'] <= 0:
                if entry.get('last', 0) > 0:
                    entry['price'] = entry['last']
                elif entry.get('bid', 0) > 0 and entry.get('ask', 0) > 0:
                    entry['price'] = round((entry['bid'] + entry['ask']) / 2.0, 2)
                elif tickType in (1, 2, 4) and price > 0:
                    entry['price'] = price

    def tickSize(self, reqId: int, tickType: int, size: float):
        if size is None or size < 0 or math.isnan(size):
            return
        with self.data_lock:
            stock_id = self.req_id_to_stock_id.get(reqId)
            if not stock_id:
                return
            if stock_id not in self.mkt_data:
                self.mkt_data[stock_id] = {
                    'price': 0.0, 'bid': 0.0, 'ask': 0.0, 'last': 0.0,
                    'high': 0.0, 'low': 0.0, 'volume': 0.0, 'prev_close': 0.0,
                    'open': 0.0, 'last_update': 0
                }
            if tickType == 8:       # Volume
                self.mkt_data[stock_id]['volume'] = float(size)
                self.mkt_data[stock_id]['last_update'] = time.time()

    def tickGeneric(self, reqId: int, tickType: int, value: float):
        pass

    def tickString(self, reqId: int, tickType: int, value: str):
        pass

    def subscribe_mkt_data(self, stock_id: str, contract: Contract) -> Optional[int]:
        """Subscribes to live streaming market data for a given stock/contract."""
        if not self.isConnected() or not self.ibkr_backend_connected:
            return None
        with self.data_lock:
            if stock_id in self.stock_id_to_req_id:
                return self.stock_id_to_req_id[stock_id]
            req_id = self.next_mkt_req_id
            self.next_mkt_req_id += 1
            self.stock_id_to_req_id[stock_id] = req_id
            self.req_id_to_stock_id[req_id] = stock_id

        try:
            logger.info(
                f"📡 Subscribing IBKR live market data: {stock_id} "
                f"(reqId={req_id}, symbol={contract.symbol}, exchange={contract.exchange})"
            )
            self.reqMktData(req_id, contract, "", False, False, [])
            return req_id
        except Exception as e:
            logger.error(f"Failed to subscribe market data for {stock_id}: {e}")
            return None

    def cancel_mkt_data(self, stock_id: str):
        """Cancels market data subscription for a stock."""
        with self.data_lock:
            req_id = self.stock_id_to_req_id.pop(stock_id, None)
            if req_id is not None:
                self.req_id_to_stock_id.pop(req_id, None)
                try:
                    self.cancelMktData(req_id)
                    logger.info(f"🛑 Cancelled IBKR market data for {stock_id} (reqId={req_id})")
                except Exception as e:
                    logger.warning(f"Error cancelling market data for {stock_id}: {e}")

    def is_subscribed_mkt_data(self, stock_id: str) -> bool:
        with self.data_lock:
            return stock_id in self.stock_id_to_req_id

    def get_live_price(self, stock_id: str) -> Optional[float]:
        """Returns the latest streaming price from IBKR if available."""
        with self.data_lock:
            entry = self.mkt_data.get(stock_id)
            if entry and entry.get('price', 0) > 0:
                return entry['price']
        return None

    def get_live_mkt_data(self, stock_id: str) -> Optional[dict]:
        """Returns a snapshot copy of streaming market data dict."""
        with self.data_lock:
            entry = self.mkt_data.get(stock_id)
            if entry:
                return entry.copy()
        return None


