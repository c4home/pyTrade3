import io
import time
from PyQt6.QtCore import QThread, pyqtSignal


class MaintenanceRoutineThread(QThread):
    progress = pyqtSignal(int, str)
    finished_data = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, db_manager, pause_callback=None):
        super().__init__()
        self.db_manager = db_manager
        self.pause_callback = pause_callback

    def run(self):
        try:
            import yfinance as yf
            import pandas as pd
            import requests
            from trading_bot import TradingBot

            self.progress.emit(0, "Fetching S&P 500 list from Wikipedia...")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=headers)
            response.raise_for_status()
            tables = pd.read_html(io.StringIO(response.text))
            df = tables[0]
            tickers = df["Symbol"].tolist()
            tickers = [t.replace(".", "-") for t in tickers]

            ignored_stocks = self.db_manager.get_ignored_stocks()

            results = []
            total = len(tickers)
            for i, symbol in enumerate(tickers):
                if self.isInterruptionRequested():
                    return
                if self.pause_callback:
                    while self.pause_callback() and not self.isInterruptionRequested():
                        time.sleep(1.0)
                if symbol in ignored_stocks:
                    continue
                self.progress.emit(int((i / total) * 100), f"Fetching {symbol} ({i+1}/{total})")
                try:
                    # Use TradingBot's native fetch so the logic perfectly matches the UI
                    bot = TradingBot(None, symbol, 1000, 5, 0.5, manual_mode=True, db_manager=self.db_manager, gui=None)
                    target, source, date = bot.fetch_fresh_bank_note()

                    if target and isinstance(target, (int, float)) and target > 0:
                        is_stale = False
                        if date and isinstance(date, str) and len(date) >= 10:
                            try:
                                from datetime import datetime
                                d = datetime.strptime(date[:10], "%Y-%m-%d")
                                if (datetime.now() - d).days > 90:
                                    is_stale = True
                            except Exception:
                                pass

                        if is_stale:
                            continue

                        info = yf.Ticker(symbol).info
                        current = info.get("currentPrice") or info.get("previousClose")
                        if current and current > 0:
                            upside = (target - current) / current
                            results.append({"symbol": symbol, "upside": upside})
                except Exception:
                    pass

                # Sleep to prevent hitting yfinance and bank target rate limits
                time.sleep(1.0)

            self.progress.emit(95, "Filtering top candidates by MA200 & Backtest PF >= 1.2...")
            results.sort(key=lambda x: x["upside"], reverse=True)
            top_10 = []
            from backtest.core_backtest_engine import compute_indicators, run_backtest_with_params
            bt_params = {
                "atr_mul": 1.5,
                "stop_mul": 2.3,
                "max_stop": -12.0,
                "rsi_exit": 80,
                "prot_act": 5.0,
                "prot_drop": 0.25,
                "dip_th": 7,
                "mom_th": 8,
            }
            for cand in results:
                if len(top_10) >= 10 or self.isInterruptionRequested():
                    break
                sym = cand["symbol"]
                try:
                    hist_df = yf.Ticker(sym).history(period="2y", interval="1d", auto_adjust=False, actions=False)
                    if hist_df is None or len(hist_df) < 205:
                        continue
                    if isinstance(hist_df.columns, pd.MultiIndex):
                        hist_df.columns = hist_df.columns.droplevel(1)
                    ind_df = compute_indicators(hist_df)
                    last_row = ind_df.iloc[-1]
                    if last_row["Close"] < last_row.get("MA200", last_row["Close"]):
                        continue
                    bt_trades = run_backtest_with_params(
                        sym,
                        {"max_amount": 1000, "profit_target": 5.0, "is_auto_watchlist": True},
                        ind_df,
                        bt_params,
                    )
                    gross_win = sum(t["pnl_eur"] for t in bt_trades if t["pnl_eur"] > 0)
                    gross_loss = abs(sum(t["pnl_eur"] for t in bt_trades if t["pnl_eur"] <= 0))
                    pf = (gross_win / gross_loss) if gross_loss > 0 else (99.9 if gross_win > 0 else 0.0)
                    if pf >= 1.2:
                        top_10.append(cand)
                except Exception:
                    continue
            self.progress.emit(100, "Sorting results...")
            self.finished_data.emit(top_10)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))

