# ==============================================================================
# pyTrade3 — PortfolioConstruction Service (portfolio_sizing.py)
# Stage 3 in Lean Architecture: Currency Management, Sizing & Asset Allocation
# Consolidates ExchangeRateManager & Portfolio Metrics
# ==============================================================================

import time
import requests
from typing import Tuple, Dict, Any, Optional
from config import logger, executor

# ==================== EXCHANGE RATE MANAGER ====================
class ExchangeRateManager:
    """Manages real-time FX currency conversions (EUR, USD, GBP, CAD, HKD)."""
    def __init__(self):
        self.rates = {
            "USD": 1.08,
            "GBP": 0.85,
            "CAD": 1.48,
            "HKD": 8.50,
            "EUR": 1.0
        }
        self.last_update = 0
        self.update_interval = 3600

    @property
    def eur_usd_rate(self) -> float:
        return self.rates.get("USD", 1.08)

    @eur_usd_rate.setter
    def eur_usd_rate(self, value: float):
        self.rates["USD"] = value

    def get_eur_usd_rate(self) -> float:
        return self.get_rate("USD")

    def get_rate(self, currency: str) -> float:
        currency = currency.upper()
        if currency == "EUR":
            return 1.0

        now = time.time()
        if now - self.last_update >= self.update_interval:
            self.last_update = now
            def fetch():
                for curr in ["USD", "GBP", "CAD", "HKD"]:
                    try:
                        url = f"https://query1.finance.yahoo.com/v8/finance/chart/EUR{curr}=X"
                        headers = {'User-Agent': 'Mozilla/5.0'}
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            price = data['chart']['result'][0]['meta']['regularMarketPrice']
                            new_rate = float(price)
                            if new_rate > 0:
                                self.rates[curr] = round(new_rate, 4)
                    except Exception:
                        pass
            executor.submit(fetch)

        return self.rates.get(currency, 1.0)

    def eur_to_native(self, eur_amount: float, currency: str) -> float:
        if currency.upper() == 'EUR':
            return eur_amount
        return eur_amount * self.get_rate(currency)

    def get_currency_symbol(self, currency: str = "USD") -> str:
        currency = currency.upper()
        if currency == "EUR":
            return "€"
        elif currency in ("GBP", "GBP"):
            return "£"
        elif currency == "HKD":
            return "HK$"
        return "$"


# ==================== PORTFOLIO METRICS HELPERS ====================
def get_usd_to_eur_rate(exchange_manager: ExchangeRateManager) -> float:
    eur_usd = exchange_manager.get_eur_usd_rate()
    if eur_usd > 0:
        return 1.0 / eur_usd
    logger.warning("[FX WARNING] Bad EURUSD rate; using fallback 0.92")
    return 0.92


def calc_portfolio_composition(bots: Dict[str, Any], ibapi: Any, exchange_manager: ExchangeRateManager) -> Tuple[float, float, float]:
    """Return (stock_pct, etf_pct, etc_pct) – each is 0-100%."""
    total_port = ibapi.portfolio_value
    if total_port <= 0:
        return 0.0, 0.0, 0.0

    stock_val = etf_val = etc_val = 0.0
    for bot in bots.values():
        if bot.quantity <= 0:
            continue
        val = bot.current_value
        curr = bot.currency.upper()
        if curr != "EUR":
            rate = exchange_manager.get_rate(curr)
            if rate > 0:
                val = val / rate

        if bot.asset_type == "STOCK":
            stock_val += val
        elif bot.asset_type == "ETF":
            etf_val += val
        elif bot.asset_type == "ETC":
            etc_val += val

    stock_pct = (stock_val / total_port) * 100
    etf_pct = (etf_val / total_port) * 100
    etc_pct = (etc_val / total_port) * 100
    return round(stock_pct, 1), round(etf_pct, 1), round(etc_pct, 1)


def calc_total_positions_pnl_eur(bots: Dict[str, Any], exchange_manager: ExchangeRateManager) -> float:
    """Calculate total unrealized P&L in EUR across all active positions in bots."""
    total_pnl_eur = 0.0
    usd_to_eur = get_usd_to_eur_rate(exchange_manager)

    for bot in bots.values():
        if bot.quantity <= 0 or bot.bought_price <= 0:
            continue
        price = bot.market_value
        if price <= 0:
            continue

        bought = bot.bought_price
        if bot.currency == "GBp":
            bought_comp = bought * 100.0
            bot_pnl = (price - bought_comp) * bot.quantity / 100.0
        else:
            bot_pnl = (price - bought) * bot.quantity

        curr = bot.currency.upper()
        if curr == "EUR":
            pnl_eur = bot_pnl
        else:
            rate = exchange_manager.get_rate(curr)
            pnl_eur = (bot_pnl / rate) if rate > 0 else (bot_pnl * usd_to_eur)

        total_pnl_eur += pnl_eur

    return total_pnl_eur


def calc_total_daily_pnl_eur(bots: Dict[str, Any], exchange_manager: ExchangeRateManager) -> float:
    """Calculate total Daily P&L (since prior close) in EUR across all active positions."""
    total_daily_pnl_eur = 0.0
    usd_to_eur = get_usd_to_eur_rate(exchange_manager)

    for bot in bots.values():
        if bot.quantity <= 0:
            continue

        price_pct = 0.0
        if bot.previous_close > 0:
            price_pct = ((bot.market_value - bot.previous_close) / bot.previous_close) * 100
            if getattr(bot, 'is_market_open', None) and not bot.is_market_open():
                if not getattr(bot, 'is_last_date_today', True) or abs(price_pct) < 0.0001:
                    db_close = getattr(bot, 'day_before_yesterday_close', 0)
                    if db_close > 0:
                        price_pct = ((bot.previous_close - db_close) / db_close) * 100

        if abs(price_pct) < 0.000001:
            continue

        val = bot.current_value
        if val <= 0:
            val = bot.quantity * bot.market_value
            if bot.currency == "GBp":
                val = val / 100.0

        curr = bot.currency.upper()
        if curr == "EUR":
            val_eur = val
        else:
            rate = exchange_manager.get_rate(curr)
            val_eur = (val / rate) if rate > 0 else (val * usd_to_eur)

        total_daily_pnl_eur += val_eur * (price_pct / 100.0)

    return total_daily_pnl_eur


# ==================== PORTFOLIO SIZING SERVICE ====================
class PortfolioSizingService:
    """
    Manages account-level position sizing, FX conversions,
    and allocation ceilings (ETF vs Stock).
    """
    CASH_BUFFER_MULTIPLIER = 0.95

    def __init__(self, exchange_manager: Optional[ExchangeRateManager] = None, db_manager=None):
        self.exchange_manager = exchange_manager or ExchangeRateManager()
        self.db_manager = db_manager

    def calculate_dynamic_max_amount(
        self,
        stock_id: str,
        market_value: float,
        dynamic_stop_loss: float,
        asset_type: str = "UNKNOWN",
        native_currency: str = "USD",
        default_max_amount: float = 1000.0
    ) -> float:
        """Dynamically calculates max investment in EUR based on account risk per trade."""
        if not self.db_manager:
            return default_max_amount

        global_acc_str = self.db_manager.get_setting("global_account_value", "14000")
        risk_pct_str = self.db_manager.get_setting("risk_per_trade_pct", "1.0")

        try:
            global_acc = float(global_acc_str)
            risk_pct = float(risk_pct_str)
        except ValueError:
            global_acc = 14000.0
            risk_pct = 1.0

        if risk_pct <= 0:
            return default_max_amount

        risk_euro = global_acc * (risk_pct / 100.0)
        stop_loss_dist = abs(dynamic_stop_loss) / 100.0
        if stop_loss_dist < 0.01:
            stop_loss_dist = 0.01

        dynamic_max = risk_euro / stop_loss_dist

        if market_value > 0:
            try:
                rate = self.exchange_manager.get_rate(native_currency)
                market_val_eur = market_value / rate if rate > 0 else market_value
                if dynamic_max < market_val_eur:
                    dynamic_max = market_val_eur
            except Exception:
                pass

        if asset_type.upper() in ["ETF", "ETC"]:
            max_cap_pct = 0.35
        else:
            max_cap_pct = 0.18

        cap_limit = global_acc * max_cap_pct
        if dynamic_max > cap_limit:
            dynamic_max = cap_limit

        return dynamic_max

    def calculate_order_sizing(
        self,
        cash_left: float,
        usable_cash: float,
        price_native: float,
        native_currency: str,
        dynamic_max: float
    ) -> Tuple[int, float, float]:
        """Computes target quantity and total EUR cost."""
        rate = self.exchange_manager.get_rate(native_currency)
        cash_native = cash_left * 0.98 * rate

        if price_native <= 0:
            return 0, 0.0, 0.0

        quantity = int(cash_native / price_native)
        if quantity < 1:
            return 0, 0.0, 0.0

        total_cost_eur = quantity * price_native
        if native_currency != "EUR":
            total_cost_eur = total_cost_eur / rate if rate > 0 else total_cost_eur

        usable_cash_clamped = max(0.0, usable_cash)
        effective_limit = min(dynamic_max, cash_left, usable_cash_clamped) * self.CASH_BUFFER_MULTIPLIER

        if total_cost_eur > effective_limit:
            max_native = effective_limit * rate
            quantity = int(max_native / price_native)
            if quantity < 1:
                return 0, 0.0, effective_limit
            total_cost_eur = (quantity * price_native) / rate if native_currency != "EUR" and rate > 0 else (quantity * price_native)

        return quantity, total_cost_eur, effective_limit

