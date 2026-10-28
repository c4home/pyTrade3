from config import *


class EmailNotifier:
    """Dịch vụ gửi thông báo Email (Trade Execution, IBKR Disconnect & Recovery)."""

    @staticmethod
    def send_ibkr_disconnect_email(app, duration_minutes, reason):
        try:
            SMTP_SERVER = ENV.get("SMTP_SERVER")
            SMTP_PORT = ENV.get("SMTP_PORT")
            SENDER_EMAIL = ENV.get("SENDER_EMAIL")
            SENDER_PASS = ENV.get("SENDER_EMAIL_PASS")
            RECEIVER_EMAIL = ENV.get("RECEIVER_EMAIL")

            if not (SMTP_SERVER and SENDER_EMAIL and SENDER_PASS and RECEIVER_EMAIL):
                logger.warning("Cannot send IBKR alert email: SMTP settings not configured.")
                return False

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            last_signal_str = "--"
            if hasattr(app, 'ibapi') and getattr(app.ibapi, 'last_ibkr_update', 0) > 0:
                last_signal_str = datetime.fromtimestamp(app.ibapi.last_ibkr_update).strftime("%Y-%m-%d %H:%M:%S")

            subject = f"⚠️ [CẢNH BÁO] IBKR Log Out / Mất kết nối quá {duration_minutes} phút - pyTrade3"
            body = f"""
CẢNH BÁO KẾT NỐI IBKR - pyTrade3 BOT

Hệ thống phát hiện tài khoản IBKR đã mất kết nối hoặc không nhận được tín hiệu.

Chi tiết:
- Trạng thái        : {reason}
- Thời gian gián đoạn: ~{duration_minutes} phút
- Thời điểm phát hiện: {now_str} (CET)
- Tín hiệu cuối IBKR : {last_signal_str}
- Chế độ Bot        : {"Đang bật Auto-Trading" if app.auto_trading else "Chế độ Standby / Manual"}

HÀNH ĐỘNG CẦN THIẾT:
Vui lòng đăng nhập lại vào IBKR (TWS hoặc IB Gateway) và xác thực 2FA để bot có thể tiếp tục tự động theo dõi và khớp lệnh!

pyTrade3 Watchdog System
""".strip()

            msg = MIMEText(body, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL

            with smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT), timeout=10) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASS)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

            logger.info(f"IBKR disconnect alert email sent successfully to {RECEIVER_EMAIL}.")
            return True
        except Exception as e:
            logger.error(f"[EMAIL ERROR] Failed to send IBKR disconnect alert: {e}")
            return False

    @staticmethod
    def send_ibkr_recovery_email(app):
        try:
            SMTP_SERVER = ENV.get("SMTP_SERVER")
            SMTP_PORT = ENV.get("SMTP_PORT")
            SENDER_EMAIL = ENV.get("SENDER_EMAIL")
            SENDER_PASS = ENV.get("SENDER_EMAIL_PASS")
            RECEIVER_EMAIL = ENV.get("RECEIVER_EMAIL")

            if not (SMTP_SERVER and SENDER_EMAIL and SENDER_PASS and RECEIVER_EMAIL):
                return False

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            subject = "✅ [THÔNG BÁO] Đã kết nối lại IBKR thành công - pyTrade3"
            body = f"""
KẾT NỐI IBKR ĐÃ ĐƯỢC KHÔI PHỤC - pyTrade3 BOT

Hệ thống đã kết nối lại thành công với IBKR TWS/Gateway.

- Thời điểm khôi phục : {now_str} (CET)
- Tài khoản IBKR      : {getattr(app.ibapi, 'account_id', 'N/A')}
- Chế độ Bot          : {"Đang bật Auto-Trading" if app.auto_trading else "Chế độ Standby / Manual"}

Bot đã sẵn sàng giao dịch bình thường!

pyTrade3 Watchdog System
""".strip()

            msg = MIMEText(body, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL

            with smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT), timeout=10) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASS)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

            logger.info("IBKR recovery email sent successfully.")
            return True
        except Exception as e:
            logger.error(f"[EMAIL ERROR] Failed to send IBKR recovery email: {e}")
            return False

    @staticmethod
    def send_trade_email(app, symbol, action, quantity, price, native_currency, reason="", bot=None):
        try:
            SMTP_SERVER = ENV["SMTP_SERVER"]
            SMTP_PORT = ENV["SMTP_PORT"]
            SENDER_EMAIL = ENV["SENDER_EMAIL"]
            SENDER_PASS = ENV["SENDER_EMAIL_PASS"]
            RECEIVER_EMAIL = ENV["RECEIVER_EMAIL"]
            # Get bot data safely
            if bot is None:
                # Fallback if bot not passed
                score = "N/A"
                rsi = "N/A"
                drop = "N/A"
                volume = "N/A"
                ma = "N/A"
                macd = "N/A"
                earnings = "N/A"
                company_name = ""
            else:
                score = bot.smart_score
                rsi = f"{bot.rsi_value:.1f}"
                drop_pct = ((bot.fourteen_day_high - bot.market_value) / bot.fourteen_day_high * 100) if bot.fourteen_day_high > 0 else 0
                drop = f"{drop_pct:.1f}%"

                projected_vol = bot.get_projected_volume()
                volume = f"Proj {projected_vol/1e6:.1f}M (Act: {bot.today_volume/1e6:.1f}M vs Avg: {bot.avg_volume_14d/1e6:.1f}M)"

                prev_ma = getattr(bot, 'prev_ma_signal', '')
                ma = f"{prev_ma} → {bot.ma_signal}" if prev_ma and prev_ma != bot.ma_signal else bot.ma_signal

                prev_macd = getattr(bot, 'prev_macd_signal', '')
                macd = f"{prev_macd} → {bot.macd_signal}" if prev_macd and prev_macd != bot.macd_signal else bot.macd_signal

                earnings = bot.next_earnings_date or "None"
                company_name = getattr(bot, 'company_name', '')

            if not company_name or company_name == "Loading...":
                if hasattr(app, 'db_manager') and app.db_manager:
                    try:
                        c_info = app.db_manager.get_company_info(symbol)
                        if c_info and c_info.get("company_name"):
                            company_name = c_info["company_name"]
                    except Exception:
                        pass
            if not company_name:
                company_name = symbol

            # 1. Currency symbol ($, €, £ …)
            curr_symbol = app.exchange_manager.get_currency_symbol(native_currency)

            pnl_info = ""
            if action == "SELL" and bot and getattr(bot, 'bought_price', 0) > 0:
                comp_bought = bot.bought_price
                if bot.currency == "GBp":
                    comp_bought = bot.bought_price * 100.0

                pnl_amount = (price - comp_bought) * quantity
                if bot.currency == "GBp":
                    pnl_amount = pnl_amount / 100.0

                pnl_info = f"Realised P/L : {curr_symbol}{pnl_amount:+.2f} ({bot.pnl_percent:+.2f}%)\n            "

            skipped_text = ""
            if action == "BUY" and bot:
                skipped_list = []
                my_score = bot.smart_score
                my_upside = getattr(bot, 'target_upside_pct', 0.0)

                def sort_func(b):
                    return (b.smart_score, getattr(b, 'target_upside_pct', 0.0))
                all_bots = sorted(app.bots.values(), key=sort_func, reverse=True)

                for other in all_bots:
                    if other.stock_id == symbol:
                        continue

                    other_score = other.smart_score
                    other_upside = getattr(other, 'target_upside_pct', 0.0)

                    if other_score > my_score or (other_score == my_score and other_upside > my_upside):
                        skip_reason = "unknown"
                        if other.quantity > 0:
                            skip_reason = "already in position"
                        elif getattr(other, 'cash_left', 0) < getattr(other, 'market_value', 100000):
                            skip_reason = "budget too low for this stock"
                        elif not other.is_running:
                            skip_reason = "bot is paused"
                        elif not getattr(other, 'is_market_open', lambda: False)():
                            skip_reason = "market is closed"
                        elif other.has_pending_order():
                            skip_reason = "pending order exists"
                        else:
                            skip_reason = getattr(other, 'get_buy_block_reason', lambda: "technical conditions not met for BUY")()

                        skipped_list.append(f"- {other.stock_id} (Score: {other_score}/12): Skipped because {skip_reason}")

                    elif other_score == my_score and other_upside < my_upside:
                        if other.quantity == 0 and other.is_running:
                            skip_reason = f"bank target upside is lower ({other_upside:.1f}% vs {symbol} at {my_upside:.1f}%)"
                            skipped_list.append(f"- {other.stock_id} (Score: {other_score}/12): Skipped because {skip_reason}")

                    if len(skipped_list) >= 10:
                        break

                if skipped_list:
                    skipped_text = "\n            SKIPPED ALTERNATIVES:\n            " + "\n            ".join(skipped_list) + "\n"

            # Format the primary reason block to be multi-line (splitting by |)
            formatted_reason = reason
            if "|" in formatted_reason:
                parts = [p.strip() for p in formatted_reason.split("|") if p.strip()]
                for i, p in enumerate(parts):
                    if p.startswith("[") and "Score:" in p and "{" in p:
                        p = p.replace(" {", "\n              ")
                        p = p.replace(", ", ",\n              ")
                        p = p.replace("}", "")
                        parts[i] = p
                formatted_reason = "\n            - ".join(parts)
                if not formatted_reason.startswith("\n"):
                    formatted_reason = "- " + formatted_reason

            clean_name = clean_company_name(company_name) or company_name
            name_display = f" ({clean_name.strip()})" if clean_name and clean_name.strip() and clean_name.strip().upper() != symbol.strip().upper() else ""
            subject = f"{action} {symbol}{name_display} - {quantity} @ {curr_symbol}{price:.2f}"

            body = f"""
            TRADE EXECUTED - pyTrade BOT

            Symbol     : {symbol}
            Company    : {company_name}
            Action     : {action}
            Quantity   : {quantity}
            Price      : {curr_symbol}{price:.2f}
            Total      : {curr_symbol}{quantity * price:.2f}
            {pnl_info}Time       : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (CET)

            REASON:
            {formatted_reason}
            {skipped_text}
            TECHNICALS:
            Score      : {score}/12
            RSI        : {rsi}
            14d Drop   : {drop}
            Volume     : {volume}
            MA Signal  : {ma}
            MACD       : {macd}
            Earnings   : {earnings}

            Bot is running — happy trading!
            """.strip()

            msg = MIMEText(body, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASS)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

            logger.info(f"EMAIL SENT -> {action} {symbol} {quantity} @ ${price:.2f}")
            return True
        except Exception as e:
            logger.error(f"[EMAIL ERROR] {e}")
            return False
