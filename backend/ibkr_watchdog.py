from config import *
from ib_api import IBApi


class IBKRWatchdogMixin:
    """Mixin quản lý kết nối IBKR TWS/Gateway, tự động kết nối lại (Auto-Reconnect) và Watchdog cảnh báo."""

    def _auto_connect(self):
        # Called once at start‑up – only if the checkbox is checked.
        if not self.auto_connect_cb.isChecked():
            return

        # Force the button into “Connect” mode (in case it was left disconnected)
        self.conn_btn.setText("Connect")
        self.toggle_connection()          # <-- this does the real connect

    def _check_auto_reconnect(self):
        """Monitors IBKR TWS/Gateway connection and automatically reconnects if lost (e.g. midnight reboot)."""
        # 1. Check IBKR connection health watchdog & send alert if logged out for too long
        self._check_ibkr_watchdog()

        if self.is_reconnecting:
            if time.time() - getattr(self, 'last_reconnect_start', 0) > 45:
                logger.warning("⚠️ Auto-reconnect task timed out (>45s). Resetting lock for next retry cycle...")
                self.is_reconnecting = False
            else:
                return

        should_reconnect = self.auto_connect_cb.isChecked() or self.auto_trading
        if not should_reconnect:
            return

        is_connected = False
        if hasattr(self, 'ibapi') and self.ibapi and hasattr(self.ibapi, 'isConnected'):
            try:
                is_connected = self.ibapi.isConnected()
            except Exception:
                is_connected = False

        if not is_connected:
            self.connected = False
            self.status_label.setText("Reconnecting...")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.conn_btn.setText("Connecting...")
            self.conn_btn.setEnabled(False)

            self._trigger_auto_reconnect()
        else:
            # Active IBKR session & account probe every 60s when socket is connected
            now = time.time()
            if now - getattr(self, 'last_ibkr_ping_time', 0) >= 60:
                self.last_ibkr_ping_time = now
                try:
                    self.ibapi.reqCurrentTime()
                except Exception as e:
                    logger.debug(f"Heartbeat reqCurrentTime error: {e}")

                def verify_ibkr_session():
                    if getattr(self, '_verifying_ibkr_session', False):
                        return
                    self._verifying_ibkr_session = True
                    try:
                        self.ibapi.cancelAccountSummary(9001)
                        time.sleep(0.3)
                        self.ibapi.cash_ready_event.clear()
                        self.ibapi.reqAccountSummary(
                            9001, "All",
                            "NetLiquidation,TotalCashValue,AvailableFunds,DailyPnL,UnrealizedPnL,RealizedPnL"
                        )
                        if self.ibapi.cash_ready_event.wait(8):
                            self.ibapi.last_cash_fetch = time.time()
                            self.ibapi.consecutive_ping_failures = 0
                        else:
                            self.ibapi.consecutive_ping_failures = getattr(self.ibapi, 'consecutive_ping_failures', 0) + 1
                            logger.warning(
                                f"⚠️ [IBKR WATCHDOG] Account summary probe timed out "
                                f"({self.ibapi.consecutive_ping_failures} consecutive failures)."
                            )
                            if self.ibapi.consecutive_ping_failures >= 2:
                                self.ibapi.ibkr_backend_connected = False
                                if not getattr(self.ibapi, 'ibkr_backend_issue_reason', ''):
                                    self.ibapi.ibkr_backend_issue_reason = (
                                        "TWS/Gateway vẫn mở nhưng không phản hồi dữ liệu tài khoản "
                                        "(có thể đã đăng nhập IBKR trên thiết bị khác hoặc treo cửa sổ Re-login)"
                                    )
                    except Exception as e:
                        logger.debug(f"Heartbeat session probe error: {e}")
                    finally:
                        self._verifying_ibkr_session = False

                threading.Thread(target=verify_ibkr_session, daemon=True).start()

    def _trigger_auto_reconnect(self):
        if self.is_reconnecting:
            return
        self.is_reconnecting = True
        self.last_reconnect_start = time.time()
        self.reconnect_attempts = getattr(self, 'reconnect_attempts', 0) + 1
        logger.info(f"🔄 [AUTO-RECONNECT] Attempt #{self.reconnect_attempts}: Connecting to IBKR TWS/Gateway...")

        def reconnect_task():
            try:
                host = self.host_edit.text().strip() or ENV["IBKR_HOST"]
                try:
                    port = int(self.port_edit.text())
                except ValueError:
                    port = int(ENV["IBKR_PORT"])
                try:
                    cid = int(self.client_edit.text())
                except ValueError:
                    cid = int(ENV["IBKR_CLIENT_ID"])

                # Clean up old connection instance if any
                if hasattr(self, 'ibapi') and self.ibapi:
                    try:
                        self.ibapi.disconnect()
                    except Exception:
                        pass

                time.sleep(2)
                self.ibapi = IBApi()
                for bot in self.bots.values():
                    bot.ibapi = self.ibapi

                self.ibapi.connect(host, port, clientId=cid)
                threading.Thread(target=self.ibapi.run, daemon=True).start()

                if self.ibapi.connected_event.wait(12):
                    self.connected = True
                    try:
                        self.ibapi.reqPositions()
                    except Exception as e:
                        logger.error(f"Error requesting positions after auto-reconnect: {e}")

                    cash_ok = False
                    try:
                        self.ibapi.cash_ready_event.clear()
                        self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds,DailyPnL,UnrealizedPnL,RealizedPnL")
                        if self.ibapi.cash_ready_event.wait(8):
                            self.ibapi.last_cash_fetch = time.time()
                            cash_ok = True
                    except Exception as e:
                        logger.error(f"Error requesting account summary after auto-reconnect: {e}")

                    if not cash_ok and not getattr(self.ibapi, 'ibkr_backend_issue_reason', ''):
                        self.ibapi.ibkr_backend_connected = False
                        self.ibapi.ibkr_backend_issue_reason = (
                            "Đã kết nối socket TWS/Gateway nhưng không lấy được dữ liệu tài khoản "
                            "(TWS có thể đang ở màn hình Re-login / đăng nhập trên thiết bị khác)"
                        )

                    QTimer.singleShot(0, lambda: self._on_auto_reconnect_success())
                else:
                    QTimer.singleShot(0, lambda: self._on_auto_reconnect_fail())
            except Exception as e:
                logger.error(f"Auto-reconnect task error: {e}")
                QTimer.singleShot(0, lambda: self._on_auto_reconnect_fail())

        threading.Thread(target=reconnect_task, daemon=True).start()

    def _on_auto_reconnect_success(self):
        self.is_reconnecting = False
        self.connected = True
        attempts = getattr(self, 'reconnect_attempts', 1)
        self.reconnect_attempts = 0
        backend_ok = getattr(self.ibapi, 'ibkr_backend_connected', True) and self.ibapi.connected_event.is_set()
        if backend_ok:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            if getattr(self, 'ibkr_alert_sent', False):
                self._on_ibkr_reconnected()
            self.ibkr_disconnected_since = None
        else:
            self.status_label.setText("IBKR Session Lost")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.conn_btn.setText("Disconnect")
        self.conn_btn.setEnabled(True)
        if not self.auto_trading:
            self.trade_btn.setEnabled(True)
        logger.info(f"✅ [AUTO-RECONNECT] Socket connected to IBKR TWS/Gateway after {attempts} attempt(s) (Backend active: {backend_ok})!")

    def _on_auto_reconnect_fail(self):
        self.is_reconnecting = False
        self.connected = False
        attempts = getattr(self, 'reconnect_attempts', 1)
        self.status_label.setText("Reconnecting...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.conn_btn.setText("Connect")
        self.conn_btn.setEnabled(True)
        logger.info(f"⏳ [AUTO-RECONNECT] Attempt #{attempts} failed (TWS rebooting/not ready). Retrying in 15 seconds...")

    def _check_ibkr_watchdog(self):
        """
        Monitors IBKR connection status and sends an alert email if IBKR is logged out,
        session is taken over by another device, or no signal has been received for too long.
        Rule: Excludes Saturday and Sunday.
        """
        now = time.time()
        now_dt = datetime.now()

        # Rule: Exclude Saturday (weekday 5) and Sunday (weekday 6)
        if now_dt.weekday() in (5, 6):
            self.ibkr_alert_sent = False
            self.ibkr_disconnected_since = None
            return

        # Monitor whenever auto_connect, auto_trading, or an active connection is expected
        if not (self.auto_connect_cb.isChecked() or self.auto_trading or self.connected):
            self.ibkr_disconnected_since = None
            return

        try:
            timeout_minutes = int(ENV.get("IBKR_DISCONNECT_ALERT_MINUTES") or 15)
        except (ValueError, TypeError):
            timeout_minutes = 15
        timeout_seconds = timeout_minutes * 60

        is_connected = False
        if hasattr(self, 'ibapi') and self.ibapi and hasattr(self.ibapi, 'isConnected'):
            try:
                is_connected = self.ibapi.isConnected()
            except Exception:
                is_connected = False

        is_backend_active = (
            is_connected
            and getattr(self.ibapi, 'ibkr_backend_connected', True)
            and self.ibapi.connected_event.is_set()
        )

        has_issue = False
        duration_minutes = 0
        issue_reason = ""

        if not is_connected:
            if not self.ibkr_disconnected_since:
                self.ibkr_disconnected_since = now
            elapsed = now - self.ibkr_disconnected_since
            if elapsed >= timeout_seconds:
                has_issue = True
                duration_minutes = int(elapsed // 60)
                issue_reason = f"Mất kết nối Socket tới IBKR TWS/Gateway liên tục trong {duration_minutes} phút"
        elif not is_backend_active:
            # Socket is connected to TWS/Gateway, but TWS lost its session with IBKR server (e.g. logged in on another device)
            self.status_label.setText("IBKR Session Lost")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            if not self.ibkr_disconnected_since:
                self.ibkr_disconnected_since = now
            elapsed = now - self.ibkr_disconnected_since
            if elapsed >= timeout_seconds:
                has_issue = True
                duration_minutes = int(elapsed // 60)
                custom_reason = getattr(self.ibapi, 'ibkr_backend_issue_reason', '')
                issue_reason = custom_reason or (
                    f"Vẫn kết nối TWS/Gateway nhưng IBKR ngừng hoạt động trong {duration_minutes} phút "
                    f"(có thể do đăng nhập IBKR trên thiết bị khác / cần Re-login)"
                )
        else:
            # Both socket and IBKR backend session are marked active; verify data freshness
            if self.status_label.text() == "IBKR Session Lost":
                self.status_label.setText("Connected")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
            last_update = getattr(self.ibapi, 'last_ibkr_update', 0)
            if last_update > 0:
                elapsed = now - last_update
                if elapsed >= timeout_seconds:
                    has_issue = True
                    duration_minutes = int(elapsed // 60)
                    issue_reason = (
                        f"TWS/Gateway vẫn mở nhưng không có phản hồi dữ liệu thực từ IBKR trong {duration_minutes} phút "
                        f"(kiểm tra xem tài khoản có bị đăng nhập trên thiết bị khác không)"
                    )
                else:
                    self.ibkr_disconnected_since = None
                    if getattr(self, 'ibkr_alert_sent', False):
                        self._on_ibkr_reconnected()
            else:
                elapsed = now - getattr(self, 'app_start_time', now)
                if elapsed >= timeout_seconds:
                    has_issue = True
                    duration_minutes = int(elapsed // 60)
                    issue_reason = f"Chưa nhận được dữ liệu tài khoản IBKR ban đầu sau {duration_minutes} phút"

        if has_issue:
            last_alert = getattr(self, 'last_ibkr_alert_time', 0)
            # Send alert if not sent yet, or send a reminder every 60 minutes while still disconnected
            if not getattr(self, 'ibkr_alert_sent', False) or (now - last_alert >= 3600):
                self.ibkr_alert_sent = True
                self.last_ibkr_alert_time = now
                logger.warning(f"🚨 [IBKR WATCHDOG] {issue_reason}. Gửi email cảnh báo...")
                executor.submit(self._send_ibkr_disconnect_email, duration_minutes, issue_reason)

    def _on_ibkr_reconnected(self):
        """Called when IBKR reconnects after an alert was sent."""
        logger.info("✅ [IBKR WATCHDOG] IBKR connection restored.")
        self.ibkr_alert_sent = False
        self.ibkr_disconnected_since = None
        executor.submit(self._send_ibkr_recovery_email)

    def toggle_connection(self):
        if not hasattr(self, "ibapi"):      # safety net
            return

        if self.connected:
            self.ibapi.disconnect()
            self.connected = False
            self.ibkr_disconnected_since = None
            self.ibkr_alert_sent = False
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: red;")
            self.conn_btn.setText("Connect")
            self.trade_btn.setEnabled(False)
        else:
            # ----- CONNECT -----
            host = self.host_edit.text().strip() or ENV["IBKR_HOST"]
            self.status_label.setText("Connecting...")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.conn_btn.setEnabled(False)

            def connect_task():
                try:
                    try:
                        port = int(self.port_edit.text())
                    except ValueError:
                        port = int(ENV["IBKR_PORT"])
                    try:
                        cid = int(self.client_edit.text())
                    except ValueError:
                        cid = int(ENV["IBKR_CLIENT_ID"])

                    self.ibapi.connect(host, port, clientId=cid)
                    threading.Thread(target=self.ibapi.run, daemon=True).start()

                    if self.ibapi.connected_event.wait(12):
                        self.connected = True
                        try:
                            self.ibapi.reqPositions()
                        except Exception as e:
                            logger.error(f"Error requesting positions: {e}")

                        cash_ok = False
                        try:
                            # ---- INITIAL CASH ----
                            self.ibapi.cash_ready_event.clear()
                            self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds,DailyPnL,UnrealizedPnL,RealizedPnL")
                            if self.ibapi.cash_ready_event.wait(8):
                                self.ibapi.last_cash_fetch = time.time()
                                cash_ok = True
                        except Exception as e:
                            logger.error(f"Error requesting account summary: {e}")

                        if not cash_ok and not getattr(self.ibapi, 'ibkr_backend_issue_reason', ''):
                            self.ibapi.ibkr_backend_connected = False
                            self.ibapi.ibkr_backend_issue_reason = (
                                "Đã kết nối socket TWS/Gateway nhưng không lấy được dữ liệu tài khoản "
                                "(TWS có thể đang ở màn hình Re-login / đăng nhập trên thiết bị khác)"
                            )

                        QTimer.singleShot(0, lambda: self._on_connect_success())
                    else:
                        QTimer.singleShot(0, lambda: self._on_connect_fail())
                except Exception as e:
                    logger.error(f"Connection task failed: {e}")
                    self.connected = False
                    QTimer.singleShot(0, lambda: self._on_connect_fail())

            threading.Thread(target=connect_task, daemon=True).start()

    def _on_connect_success(self):
        backend_ok = getattr(self.ibapi, 'ibkr_backend_connected', True) and self.ibapi.connected_event.is_set()
        if backend_ok:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            if getattr(self, 'ibkr_alert_sent', False):
                self._on_ibkr_reconnected()
            self.ibkr_disconnected_since = None
        else:
            self.status_label.setText("IBKR Session Lost")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.conn_btn.setText("Disconnect")
        self.conn_btn.setEnabled(True)
        self.trade_btn.setEnabled(True)

    def _on_connect_fail(self):
        self.status_label.setText("Conn. failed")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.conn_btn.setText("Connect")
        self.conn_btn.setEnabled(True)
