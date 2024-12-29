from enum import Enum
from pydantic import BaseModel
from typing import Dict, List, Optional, Union
from datetime import datetime


class TimeFrame(str, Enum):
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1M"


class TrendDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"


class SignalStrength(str, Enum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


class Pattern(str, Enum):
    DOJI = "doji"
    HAMMER = "hammer"
    SHOOTING_STAR = "shooting_star"
    ENGULFING = "engulfing"
    MORNING_STAR = "morning_star"
    EVENING_STAR = "evening_star"
    THREE_WHITE_SOLDIERS = "three_white_soldiers"
    THREE_BLACK_CROWS = "three_black_crows"
    DRAGONFLY_DOJI = "dragonfly_doji"
    GRAVESTONE_DOJI = "gravestone_doji"


class TechnicalIndicator(BaseModel):
    symbol: str
    timeframe: TimeFrame
    timestamp: datetime
    indicators: Dict[str, Union[float, Dict[str, float], str]]

    class Config:
        from_attributes = True


class Signal(BaseModel):
    type: str
    direction: TrendDirection
    strength: SignalStrength
    timeframe: TimeFrame
    timestamp: datetime = None
    metadata: Optional[Dict] = None

    class Config:
        from_attributes = True


class PatternSignal(BaseModel):
    symbol: str
    pattern: Pattern
    direction: TrendDirection
    strength: SignalStrength
    timestamp: datetime
    price: float
    volume: Optional[float] = None
    metadata: Optional[Dict] = None

    class Config:
        from_attributes = True


class TrendAnalysis(BaseModel):
    symbol: str
    timeframe: TimeFrame
    direction: TrendDirection
    strength: SignalStrength
    start_timestamp: datetime
    current_timestamp: datetime
    support_levels: List[float]
    resistance_levels: List[float]
    key_levels: List[float]
    metadata: Optional[Dict] = None

    class Config:
        from_attributes = True


class VolumeProfile(BaseModel):
    """Volume Profile Analysis Model."""
    symbol: str
    timeframe: TimeFrame
    timestamp: datetime
    price_levels: List[float]
    volume_at_price: Dict[str, float]  # Price level -> Volume
    value_area_high: float
    value_area_low: float
    point_of_control: float
    metadata: Optional[Dict] = None

    class Config:
        from_attributes = True


class OrderFlowTrade(BaseModel):
    """Individual trade in order flow analysis."""
    timestamp: datetime
    price: float
    volume: float
    side: str  # "buy" or "sell"
    is_aggressive: bool
    is_block_trade: bool = False
    metadata: Optional[Dict] = None


class OrderFlowImbalance(BaseModel):
    """Order flow imbalance at a price level."""
    price_level: float
    buy_volume: float
    sell_volume: float
    net_volume: float
    trade_count: int
    avg_trade_size: float
    max_trade_size: float
    aggressive_buy_volume: float
    aggressive_sell_volume: float
    timestamp: datetime


class OrderFlowAnalysis(BaseModel):
    """Complete order flow analysis for a time period."""
    symbol: str
    timeframe: TimeFrame
    start_time: datetime
    end_time: datetime
    trades: List[OrderFlowTrade]
    imbalances: List[OrderFlowImbalance]
    cumulative_volume_delta: float
    buy_volume_ratio: float
    sell_volume_ratio: float
    large_trade_threshold: float
    block_trade_count: int
    aggressive_buy_ratio: float
    aggressive_sell_ratio: float
    metadata: Optional[Dict] = None

    class Config:
        from_attributes = True


class LiquidityLevel(BaseModel):
    """Represents a significant liquidity level."""
    price: float
    volume: float
    type: str  # "support", "resistance", "cluster"
    strength: float  # 0-1 scale
    age: int  # How long this level has persisted (in periods)
    hits: int  # Number of times price has interacted with this level
    last_test: datetime
    metadata: Optional[Dict] = None


class OrderBookSnapshot(BaseModel):
    """Snapshot of the order book at a point in time."""
    timestamp: datetime
    bids: Dict[float, float]  # price -> volume
    asks: Dict[float, float]  # price -> volume
    bid_depth: float
    ask_depth: float
    spread: float
    mid_price: float
    weighted_mid_price: float
    imbalance_ratio: float


class MarketImpactEstimate(BaseModel):
    """Estimated market impact for different order sizes."""
    size: float
    side: str  # "buy" or "sell"
    estimated_impact: float
    estimated_cost: float
    estimated_slippage: float
    confidence: float  # 0-1 scale


class LiquidityAnalysis(BaseModel):
    """Complete liquidity analysis for a symbol."""
    symbol: str
    timestamp: datetime
    timeframe: TimeFrame
    liquidity_levels: List[LiquidityLevel]
    order_book: OrderBookSnapshot
    market_impact_estimates: List[MarketImpactEstimate]
    avg_daily_volume: float
    relative_spread: float
    depth_imbalance: float
    liquidity_score: float  # 0-100 scale
    volatility_adjusted_spread: float
    resiliency_score: float  # 0-100 scale
    metadata: Optional[Dict] = None

    class Config:
        from_attributes = True


class DarkPoolTrade(BaseModel):
    """Individual dark pool trade."""
    timestamp: datetime
    symbol: str
    price: float
    volume: float
    venue: str
    trade_id: str
    is_block: bool = False
    metadata: Optional[Dict] = None


class DarkPoolVenue(BaseModel):
    """Dark pool venue information."""
    name: str
    volume: float
    trade_count: int
    avg_trade_size: float
    market_share: float  # Percentage of total dark pool volume
    block_ratio: float  # Percentage of block trades
    avg_price: float
    timestamp: datetime


class PriceLevel(BaseModel):
    """Price level with dark pool activity."""
    price: float
    volume: float
    trade_count: int
    last_trade: datetime
    venue_breakdown: Dict[str, float]  # venue -> volume
    is_significant: bool = False


class DarkPoolAnalysis(BaseModel):
    """Complete dark pool analysis for a symbol."""
    symbol: str
    timestamp: datetime
    timeframe: TimeFrame
    total_volume: float
    total_trades: int
    avg_trade_size: float
    block_trade_count: int
    block_volume_ratio: float
    recent_trades: List[DarkPoolTrade]
    venues: List[DarkPoolVenue]
    price_levels: List[PriceLevel]
    significant_levels: List[float]
    volume_distribution: Dict[str, float]  # Time bucket -> volume
    metadata: Optional[Dict] = None

    class Config:
        from_attributes = True


class OptionContract(BaseModel):
    """Individual option contract details."""
    symbol: str
    expiry: datetime
    strike: float
    type: str  # "call" or "put"
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    is_weekly: bool = False
    metadata: Optional[Dict] = None


class OptionFlow(BaseModel):
    """Individual options flow trade."""
    timestamp: datetime
    contract: OptionContract
    side: str  # "buy" or "sell"
    size: int
    premium: float
    is_sweep: bool = False
    is_block: bool = False
    sentiment: str  # "bullish" or "bearish"
    execution_type: str  # "market", "limit", "complex"
    metadata: Optional[Dict] = None


class StrikeAnalysis(BaseModel):
    """Analysis of activity at a strike price."""
    strike: float
    call_volume: int
    put_volume: int
    call_oi: int
    put_oi: int
    pcr_volume: float  # Put-Call Ratio by volume
    pcr_oi: float  # Put-Call Ratio by open interest
    net_premium: float
    implied_move: float
    notable_trades: List[OptionFlow]


class ExpiryAnalysis(BaseModel):
    """Analysis of activity at an expiry date."""
    expiry: datetime
    total_volume: int
    total_oi: int
    call_volume: int
    put_volume: int
    pcr_volume: float
    pcr_oi: float
    implied_move: float
    max_pain: float
    strikes: List[StrikeAnalysis]


class OptionsFlowAnalysis(BaseModel):
    """Complete options flow analysis for a symbol."""
    symbol: str
    timestamp: datetime
    underlying_price: float
    total_volume: int
    total_open_interest: int
    put_call_ratio: float
    implied_volatility_rank: float
    implied_volatility_percentile: float
    recent_flows: List[OptionFlow]
    expiries: List[ExpiryAnalysis]
    unusual_activity: List[OptionFlow]
    bullish_flow_ratio: float
    bearish_flow_ratio: float
    smart_money_indicator: float  # -1 to 1 scale
    gamma_exposure: float
    vanna_exposure: float
    charm_exposure: float
    metadata: Optional[Dict] = None

    class Config:
        from_attributes = True
