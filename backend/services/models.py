# ==============================================================================
# pyTrade3 — Core Data Contracts & Models (models.py)
# Standard DTOs for Lean 5-Stage Architecture
# ==============================================================================

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

@dataclass
class MarketSnapshot:
    """Standardized snapshot of market data and indicators for a single asset."""
    stock_id: str
    market_price: float = 0.0
    previous_close: float = 0.0
    day_before_yesterday_close: float = 0.0
    close_3d_ago: float = 0.0
    high_14d: float = 0.0
    low_14d: float = 0.0
    rsi: float = 50.0
    adx: float = 0.0
    ma50: float = 0.0
    ma200: float = 0.0
    atr14: float = 1.0
    ma_signal: str = "NEUTRAL"
    macd_signal: str = "NEUTRAL"
    prev_macd_signal: str = "NEUTRAL"
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_pct_b: float = 0.5
    today_volume: float = 0.0
    avg_volume_14d: float = 0.0
    projected_volume: float = 0.0
    next_earnings_date: Optional[str] = None
    target_price: float = 0.0
    num_analysts: int = 0
    asset_type: str = "UNKNOWN"
    sector: str = "N/A"
    currency: str = "USD"
    currency_symbol: str = "$"
    exchange_tz_name: Optional[str] = None

@dataclass
class AlphaSignal:
    """Quantitative scoring output produced by AlphaEngine."""
    strategy: str = "DIP"            # 'DIP' or 'MOMENTUM'
    smart_score: int = 0             # 0 to 12 points
    base_score: int = 0              # 0 to 10 points
    target_upside_pct: float = 0.0
    score_reason: str = ""
    qualifies: bool = False          # Meets strategy threshold

@dataclass
class RiskDecision:
    """Safety veto or approval from RiskManagementEngine."""
    allowed: bool = False
    action: Optional[str] = None     # 'BUY', 'SELL', or None
    reason: str = ""
    is_throttled: bool = False
    dynamic_stop_loss: float = -5.0
    dynamic_profit_target: float = 0.05

@dataclass
class OrderIntent:
    """Fully parameterized order ready for execution."""
    stock_id: str
    action: str                      # 'BUY' or 'SELL'
    quantity: int = 0
    price_native: float = 0.0
    currency: str = "USD"
    primary_exchange: str = "NASDAQ"
    total_cost_eur: float = 0.0
    reason: str = ""

