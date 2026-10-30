from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import QTableWidget

from backend.config import format_currency_short
from frontend.components.table_items import NumericTableWidgetItem

ABBR_MAP = {
    "Morgan Stanley": "MS",
    "JPMorgan Chase & Co.": "JPM",
    "Goldman Sachs": "GS",
    "Barclays": "BCS",
    "Deutsche Bank": "DB",
    "Bank of America": "BofA",
    "Citigroup": "Citi",
    "Credit Suisse": "CS",
    "HSBC": "HSBC",
    "RBC Capital Markets": "RBC",
    "KeyBanc": "Key",
    "Berenberg": "BER",
    "Jefferies": "JEF",
    "Wells Fargo": "WFC",
    "Piper Sandler": "PIP",
    "Truist Securities": "TUI",
    "Bernstein": "AB",
    "Mizuho": "MIZ",
    "Nomura": "NOM",
    "Susquehanna": "SUS",
    "Evercore ISI": "EVR",
    "Raymond James": "RJ",
    "Canaccord Genuity": "CG",
    "Stifel": "SF",
    "BMO Capital Markets": "BMO",
    "Oppenheimer": "OPP",
    "Wedbush": "WED",
    "Cowen": "COW",
    "Needham": "NDM",
    "Craig-Hallum": "CH",
    "Roth Capital": "ROTH",
    "Northland": "NLD",
    "Loop Capital": "LOOP",
    "Guggenheim": "GUG",
    "Rosenblatt": "ROS",
    "Benchmark": "BNC",
    "Colliers Securities": "COL",
}


class TableRenderer:
    """Encapsulates row generation, column calculations, and cell formatting for the 30-column stock table."""

    @classmethod
    def render_row(cls, table: QTableWidget, row: int, sid: str, bot: Any) -> None:
        """Computes technicals and renders all 30 columns for a single stock row."""
        bot.get_market_value()
        bot.update_position()
        bot.calculate_technical_indicators()
        bot.check_trading_conditions(readonly=True)

        status = bot.get_status()
        volume_display = f"{bot.today_volume / 1e6:.1f}"

        # 1. Format the TPrice string
        if bot.target_price > 0:
            t_price_display = f"{bot.currency_symbol}{bot.target_price:.2f}"
        else:
            t_price_display = "--"

        # --- Latest Bank Target ---
        bank_target_long = getattr(bot, "latest_bank_target", 0)

        currency_sym = "$"
        if ".L" in bot.stock_id:
            currency_sym = "£"
        if ".PA" in bot.stock_id or ".DE" in bot.stock_id:
            currency_sym = "€"

        bank_target = f"{bank_target_long:g}" if bank_target_long else ""
        bank_name_long = getattr(bot, "latest_bank_source", "--")
        bank_name = ABBR_MAP.get(bank_name_long, bank_name_long)

        bank_date = getattr(bot, "latest_bank_date", "")
        short_date = bank_date
        if len(bank_date) == 10 and bank_date[4] == "-" and bank_date[7] == "-":
            short_date = bank_date[5:]

        if bank_target and short_date and short_date != "--":
            bank_note = f"{currency_sym}{bank_target} {bank_name} ({short_date})"
        elif bank_target:
            bank_note = f"{currency_sym}{bank_target} {bank_name}"
        else:
            bank_note = bank_name

        # Daily price variation
        if bot.previous_close > 0:
            price_pct = ((bot.market_value - bot.previous_close) / bot.previous_close) * 100
            if getattr(bot, "is_market_open", None) and not bot.is_market_open():
                if not getattr(bot, "is_last_date_today", True) or abs(price_pct) < 0.0001:
                    db_close = getattr(bot, "day_before_yesterday_close", 0)
                    if db_close > 0:
                        price_pct = ((bot.previous_close - db_close) / db_close) * 100
        else:
            price_pct = 0.0

        if bot.manual_mode:
            if getattr(bot, "is_auto_watchlist", False):
                status = "Watchlist"
            else:
                status = "Hold"

        earn_display = bot.next_earnings_date
        if not earn_display or earn_display == "No payment":
            earn_display = "--"
        elif len(earn_display) == 10 and earn_display[4] == "-" and earn_display[7] == "-":
            earn_display = earn_display[5:]

        comp_name_display = bot.company_name[:12] + ".." if len(bot.company_name) > 14 else bot.company_name

        strategy_arrow = " ↘" if getattr(bot, "current_strategy", "") == "DIP" else (
            " ↗" if getattr(bot, "current_strategy", "") == "MOMENTUM" else ""
        )

        if bot.smart_score == 0 and "Insufficient Data" in bot.score_reason:
            score_display = "⚠️ Data"
        else:
            score_display = f"{bot.smart_score}{strategy_arrow}"

        # Trailing sell price
        peak_pnl = max(getattr(bot, "pnl_percent", 0.0), getattr(bot, "highest_pnl", 0.0))
        target_pnl_pct = bot.dynamic_profit_target * 100

        if bot.quantity > 0 and bot.bought_price > 0 and peak_pnl >= target_pnl_pct:
            _atr_pct = (bot.get_atr_14() / bot.market_value) * 100 if bot.market_value > 0 else 0
            _trail_drop = max(0.5, min(_atr_pct * 0.5, 1.5))
            _trail_activation = peak_pnl - _trail_drop
            trail_sell_price = bot.bought_price * (1 + _trail_activation / 100)
            _sign = "+" if _trail_activation > 0 else ""
            trail_sell_display = f"{bot.currency_symbol}{trail_sell_price:.2f} ({_sign}{_trail_activation:.2f}%)"
            trail_sell_sort = trail_sell_price
        elif bot.quantity > 0 and bot.bought_price > 0 and peak_pnl >= 5.0:
            _trail_drop = peak_pnl * 0.25
            _trail_activation = peak_pnl - _trail_drop
            trail_sell_price = bot.bought_price * (1 + _trail_activation / 100)
            _sign = "+" if _trail_activation > 0 else ""
            trail_sell_display = f"{bot.currency_symbol}{trail_sell_price:.2f} ({_sign}{_trail_activation:.2f}%)"
            trail_sell_sort = trail_sell_price
        else:
            trail_sell_display = "--"
            trail_sell_sort = 0.0

        items = [
            comp_name_display,
            sid,
            bot.asset_type,
            bot.sector,
            f"{bot.currency_symbol}{bot.market_value:.2f}",
            f"{price_pct:+.2f}%",
            t_price_display,
            bank_note,
            score_display,
            f"{bot.currency_symbol}{bot.fourteen_day_high:.2f}",
            f"{bot.currency_symbol}{bot.fourteen_day_low:.2f}",
            f"{bot.rsi_value:.0f}",
            f"{bot.adx_value:.0f}",
            bot.ma_signal,
            bot.macd_signal,
            volume_display,
            str(bot.quantity),
            f"{bot.currency_symbol}{bot.bought_price:.2f}",
            f"{bot.currency_symbol}{bot.current_value:.0f}",
            f"{bot.pnl_percent:+.1f}%",
            format_currency_short(bot.cash_left, "€"),
            format_currency_short(bot.max_amount, "€"),
            format_currency_short(getattr(bot, "current_max_investment", bot.max_amount), "€"),
            f"{bot.profit_target*100:.1f}%",
            f"{bot.dynamic_profit_target*100:.1f}%",
            trail_sell_display,
            f"{bot.drop_threshold*100:.1f}%",
            f"{bot.dynamic_stop_loss:.1f}%",
            earn_display,
            status,
        ]

        sort_values = [
            comp_name_display,
            sid,
            bot.asset_type,
            bot.sector,
            bot.market_value,
            price_pct,
            bot.target_price,
            bank_target_long,
            bot.smart_score,
            bot.fourteen_day_high,
            bot.fourteen_day_low,
            bot.rsi_value,
            bot.adx_value,
            bot.ma_signal,
            bot.macd_signal,
            bot.today_volume,
            bot.quantity,
            bot.bought_price,
            (bot.current_value, bot.smart_score, getattr(bot, "target_upside_pct", 0.0)),
            bot.pnl_percent,
            bot.cash_left,
            bot.max_amount,
            getattr(bot, "current_max_investment", bot.max_amount),
            bot.profit_target,
            bot.dynamic_profit_target,
            trail_sell_sort,
            bot.drop_threshold,
            bot.dynamic_stop_loss,
            earn_display,
            status,
        ]

        for col, text in enumerate(items):
            item = NumericTableWidgetItem(text, sort_values[col])
            cls._apply_cell_styling(
                item=item,
                col=col,
                text=text,
                bot=bot,
                price_pct=price_pct,
                bank_target_long=bank_target_long,
                trail_sell_sort=trail_sell_sort,
                trail_sell_display=trail_sell_display,
                peak_pnl=peak_pnl,
            )
            table.setItem(row, col, item)

    @classmethod
    def _apply_cell_styling(
        cls,
        item: NumericTableWidgetItem,
        col: int,
        text: str,
        bot: Any,
        price_pct: float,
        bank_target_long: float,
        trail_sell_sort: float,
        trail_sell_display: str,
        peak_pnl: float,
    ) -> None:
        """Applies conditional colors, fonts, alignments and tooltips to individual table items."""
        if col == 4:  # Price Column (Highlight in Green based on BUY score condition)
            current_strat = getattr(bot, "current_strategy", "DIP")
            base_score = getattr(bot, "base_score", 0)
            smart_score = getattr(bot, "smart_score", 0)

            qualifies_dip = (current_strat == "DIP" and smart_score >= 7 and base_score >= 5)
            qualifies_mom = (current_strat == "MOMENTUM" and smart_score >= 8 and base_score >= 6)

            if qualifies_dip or qualifies_mom:
                item.setForeground(QColor("green"))
                item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                item.setToolTip(f"🟢 BUY TRIGGER SCORE MET: {current_strat} Score: {smart_score}/12 (Base: {base_score}/10)")

        elif col == 11:  # RSI column
            try:
                rsi_val = float(text)
                if rsi_val > 70:
                    item.setForeground(QColor("red"))
                elif rsi_val < 30:
                    item.setForeground(QColor("green"))
            except ValueError:
                pass
        elif col == 12:  # ADX column
            try:
                adx_val = float(text)
                if adx_val >= 25:
                    item.setForeground(QColor("green"))
                else:
                    item.setForeground(QColor("orange"))
            except ValueError:
                pass
        elif col == 15:  # Volume column
            if bot.today_volume > 1.5 * bot.avg_volume_14d:
                item.setForeground(QColor("green"))
        elif col == 5:  # Price%
            if price_pct > 0:
                item.setForeground(QColor("green"))
            elif price_pct < 0:
                item.setForeground(QColor("red"))
        elif col == 8:
            try:
                score = bot.smart_score
                if score == 0 and "Insufficient Data" in getattr(bot, "score_reason", ""):
                    item.setBackground(QColor(180, 0, 0))
                    item.setForeground(QColor("white"))
                elif score >= 8:
                    item.setBackground(QColor(0, 180, 0))
                    item.setForeground(QColor("white"))
                elif score >= 6:
                    item.setBackground(QColor(255, 220, 0))
                    item.setForeground(QColor("black"))
                elif score < 6:
                    item.setBackground(QColor(100, 100, 100))
                item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            except Exception:
                pass
        elif col == 6 and bot.target_price > 0:
            if bot.market_value < bot.target_price:
                item.setForeground(QColor("green"))
            elif bot.market_value > bot.target_price:
                item.setForeground(QColor("red"))
        elif col == 7 and bank_target_long > 0:
            is_stale = False
            bank_date_str = getattr(bot, "latest_bank_date", "")
            if bank_date_str and len(bank_date_str) >= 10:
                try:
                    d = datetime.strptime(bank_date_str[:10], "%Y-%m-%d")
                    if (datetime.now() - d).days > 90:
                        is_stale = True
                except ValueError:
                    pass

            if is_stale:
                item.setForeground(QColor("#ff8c00"))
                item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                item.setToolTip(f"Stale Bank Target (>90 days old: {bank_date_str}). Manual review advised.")
            elif bot.market_value > bank_target_long:
                item.setForeground(QColor("red"))
        elif col == 19:  # PnL%
            if bot.pnl_percent > 0:
                item.setForeground(QColor("green"))
            elif bot.pnl_percent < 0:
                item.setForeground(QColor("red"))
        elif col in (22, 24, 27):  # ~Max, ~TP and ~SL
            current_strat = getattr(bot, "bought_strategy", None) or getattr(bot, "current_strategy", "DIP")
            stop_cap = -7.0 if current_strat == "DIP" else -9.0
            atr = bot.get_atr_14()
            atr_pct = (atr / bot.market_value * 100) if (atr > 0 and bot.market_value > 0) else 0

            if bot.dynamic_stop_loss <= stop_cap or atr_pct >= 3.0:
                item.setForeground(QColor("red"))
                item.setToolTip(f"High Volatility Stock (ATR: {atr_pct:.1f}%, Max Stop: {stop_cap:.1f}%)")
        elif col == 25:  # Trail$ column
            if trail_sell_sort > 0:
                item.setForeground(QColor("#f39c12"))
                item.setToolTip(f"Trailing sell triggers if price drops to {trail_sell_display} (Peak PnL: {peak_pnl:.1f}%)")
        elif col == 28:  # Earnings column
            if bot.next_earnings_date:
                try:
                    earn_date = datetime.strptime(bot.next_earnings_date, "%Y-%m-%d").date()
                    current_date = datetime.now().date()
                    delta = (earn_date - current_date).days
                    if 0 <= delta <= 30:
                        item.setForeground(QColor("green"))
                except ValueError:
                    pass
        elif col == 29:  # Status column
            if text == "Hold":
                item.setForeground(QColor("red"))
            elif text == "Watchlist":
                item.setForeground(QColor("magenta"))
            elif text == "Full capacity":
                item.setForeground(QColor("green"))
            elif text == "Budget too low":
                item.setForeground(QColor("red"))
            elif "Low Cash" in text:
                item.setForeground(QColor("orange"))
            elif "Closed" in text:
                item.setForeground(QColor("orange"))
            elif "Ready" in text:
                item.setForeground(QColor("green"))
        elif "BUY" in text or "BULL" in text:
            item.setForeground(QColor("green"))
        elif "SELL" in text or "BEAR" in text:
            item.setForeground(QColor("red"))
        elif col == 2:
            color = (
                QColor("blue")
                if "STOCK" in text
                else QColor("green")
                if "ETF" in text
                else QColor("orange")
                if "ETC" in text
                else QColor("black")
            )
            item.setForeground(QBrush(color))

