import threading
from datetime import datetime
from typing import Any, Tuple


class SummaryFormatter:
    """Formats top summary header bar, connection indicators, PnL metrics, and timestamp labels."""

    @staticmethod
    def get_connection_status(connected: bool, is_reconnecting: bool, current_status_text: str) -> Tuple[str, str]:
        """Returns (conn_text, conn_color)."""
        if is_reconnecting or current_status_text in ("Connecting...", "Reconnecting..."):
            conn_text = "Reconnecting..." if not connected else "Connected"
            conn_color = "orange" if not connected else "green"
        else:
            conn_text = "Connected" if connected else "Disconnected"
            conn_color = "green" if connected else "red"
        return conn_text, conn_color

    @staticmethod
    def format_daily_pnl_display(raw_daily_pnl: float, total_val: float) -> str:
        daily_sign = "+" if raw_daily_pnl > 0 else ""
        daily_pct = (raw_daily_pnl / total_val * 100) if total_val > 0 else 0.0
        daily_color = "#2ecc71" if raw_daily_pnl > 0 else ("#e74c3c" if raw_daily_pnl < 0 else "#aaaaaa")
        return f"Daily: <span style='color: {daily_color}; font-weight: bold;'>{daily_sign}€{raw_daily_pnl:,.2f} ({daily_sign}{daily_pct:.2f}%)</span>"

    @staticmethod
    def format_unrealized_pnl_display(raw_unreal_pnl: float, total_val: float) -> str:
        unreal_sign = "+" if raw_unreal_pnl > 0 else ""
        unreal_pct = (raw_unreal_pnl / total_val * 100) if total_val > 0 else 0.0
        unreal_color = "#2ecc71" if raw_unreal_pnl > 0 else ("#e74c3c" if raw_unreal_pnl < 0 else "#aaaaaa")
        return f"Unrealized: <span style='color: {unreal_color}; font-weight: bold;'>{unreal_sign}€{raw_unreal_pnl:,.2f} ({unreal_sign}{unreal_pct:.2f}%)</span>"

    @classmethod
    def format_portfolio_summary_text(
        cls,
        connected: bool,
        cash_val: float,
        port_val: float,
        min_cash: float,
        raw_daily_pnl: float,
        raw_unreal_pnl: float,
        comp_str: str,
    ) -> str:
        if not connected:
            return "Total: €--  |  Daily: €--  |  Unrealized: €--  |  Cash: €--  |  Port: €--  |  Alloc: --"

        total_val = cash_val + port_val
        cash_str = f"{cash_val:,.0f}"
        port_str = f"{port_val:,.0f}"
        total_str = f"{total_val:,.0f}"

        daily_pnl_display = cls.format_daily_pnl_display(raw_daily_pnl, total_val)
        unreal_pnl_display = cls.format_unrealized_pnl_display(raw_unreal_pnl, total_val)

        if min_cash > 0:
            usable_val = max(0.0, cash_val - min_cash)
            usable_str = f"{usable_val:,.0f}"
            cash_display = f"Cash: <b>€{cash_str}</b> (Usable: <b>€{usable_str}</b>)"
        else:
            cash_display = f"Cash: <b>€{cash_str}</b>"

        return (
            f"Total: <b>€{total_str}</b>  |  {daily_pnl_display}  |  {unreal_pnl_display}  |  {cash_display}  |  "
            f"Port: <b>€{port_str}</b>  |  Alloc: <b>{comp_str}</b>"
        )

    @staticmethod
    def format_last_fetch_html(bots: Any, connected: bool, last_ibkr_update: float) -> str:
        last_yf_times = [bot.last_yf_fetch for bot in bots.values() if bot.last_yf_fetch > 0]
        yf_time_str = (
            datetime.fromtimestamp(max(last_yf_times)).strftime("%H:%M:%S %d/%m/%Y") if last_yf_times else "--"
        )
        ibkr_time_str = (
            datetime.fromtimestamp(last_ibkr_update).strftime("%H:%M:%S %d/%m/%Y")
            if (connected and last_ibkr_update > 0)
            else "--"
        )

        return f"Last Fetch<br/>YF  : {yf_time_str}<br/>IBKR: {ibkr_time_str}"

