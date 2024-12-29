from enum import Enum
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Union
from datetime import datetime
from uuid import UUID, uuid4

from app.models.technical import TimeFrame, TrendDirection, SignalStrength


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class PositionType(str, Enum):
    LONG = "long"
    SHORT = "short"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class BacktestOrder(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    type: OrderType
    side: OrderSide
    quantity: float
    price: Optional[float] = None  # For limit and stop orders
    stop_price: Optional[float] = None  # For stop and stop-limit orders
    timestamp: datetime
    status: OrderStatus = OrderStatus.PENDING
    fill_price: Optional[float] = None
    fill_timestamp: Optional[datetime] = None
    commission: float = 0.0
    slippage: float = 0.0

    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v

    @validator('price')
    def validate_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Price must be positive")
        return v


class Position(BaseModel):
    symbol: str
    type: PositionType
    quantity: float
    entry_price: float
    entry_timestamp: datetime
    current_price: float
    current_timestamp: datetime
    unrealized_pnl: float
    realized_pnl: float = 0.0
    commission_paid: float = 0.0


class TradeStats(BaseModel):
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    total_pnl: float = 0.0
    total_commission: float = 0.0
    total_slippage: float = 0.0


class BacktestConfig(BaseModel):
    start_date: datetime
    end_date: datetime
    initial_capital: float
    symbols: List[str]
    timeframe: TimeFrame
    commission_rate: float = 0.001  # 0.1%
    slippage_rate: float = 0.0001  # 0.01%
    enable_shorting: bool = False
    max_positions: int = 5
    position_size: float = 0.2  # 20% of capital per position
    stop_loss: Optional[float] = None  # Percentage
    take_profit: Optional[float] = None  # Percentage
    use_fractional_shares: bool = True
    min_trade_amount: float = 100.0
    max_trade_amount: Optional[float] = None

    @validator('initial_capital', 'commission_rate', 'slippage_rate', 'position_size')
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Value must be positive")
        return v

    @validator('position_size')
    def validate_position_size(cls, v):
        if v <= 0 or v > 1:
            raise ValueError("Position size must be between 0 and 1")
        return v


class BacktestResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    config: BacktestConfig
    stats: TradeStats
    equity_curve: List[Dict[str, Union[datetime, float]]]
    trades: List[Dict[str, Union[str, float, datetime]]]
    positions: List[Dict[str, Union[str, float, datetime]]]
    orders: List[BacktestOrder]
    metrics: Dict[str, float]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class BacktestSignal(BaseModel):
    symbol: str
    timestamp: datetime
    type: str
    direction: TrendDirection
    strength: SignalStrength
    price: float
    metadata: Optional[Dict] = None


class StrategyConfig(BaseModel):
    name: str
    description: str
    indicators: Dict[str, Dict[str, Union[str, int, float]]]
    entry_conditions: List[Dict[str, Union[str, float]]]
    exit_conditions: List[Dict[str, Union[str, float]]]
    risk_management: Dict[str, Union[float, bool]] = {
        "use_stop_loss": True,
        "stop_loss_pct": 0.02,  # 2%
        "use_trailing_stop": False,
        "trailing_stop_pct": 0.01,  # 1%
        "use_take_profit": True,
        "take_profit_pct": 0.05,  # 5%
        "max_loss_per_trade": 0.01,  # 1% of account
        "max_loss_per_day": 0.03  # 3% of account
    }
    position_sizing: Dict[str, Union[float, str]] = {
        "method": "fixed_pct",  # fixed_pct, fixed_usd, risk_based
        "size": 0.02,  # 2% of account per trade
        "max_positions": 5
    }
    timeframes: List[TimeFrame] = [TimeFrame.DAILY]
    metadata: Optional[Dict] = None


class BacktestStrategy(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    name: str
    description: str
    config: StrategyConfig
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    is_public: bool = False
    performance: Optional[Dict[str, float]] = None
    metadata: Optional[Dict] = None

    class Config:
        from_attributes = True


from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from app.db.base import Base


# SQLAlchemy Models
class BacktestStrategyDB(Base):
    __tablename__ = "backtest_strategies"

    id = Column(PGUUID, primary_key=True, default=uuid4)
    user_id = Column(PGUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    config = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_active = Column(Boolean, nullable=False, default=True)
    is_public = Column(Boolean, nullable=False, default=False)
    performance = Column(JSONB)
    metadata = Column(JSONB)

    __table_args__ = (
        Index("ix_backtest_strategies_user_id", "user_id"),
        Index("ix_backtest_strategies_is_public", "is_public")
    )

    @classmethod
    async def get_by_id(cls, strategy_id: UUID) -> Optional["BacktestStrategyDB"]:
        """Get strategy by ID."""
        query = cls.__table__.select().where(cls.id == strategy_id)
        result = await cls._db.fetch_one(query)
        return cls(**result) if result else None

    @classmethod
    async def get_by_user(cls, user_id: UUID) -> List["BacktestStrategyDB"]:
        """Get all strategies for a user."""
        query = cls.__table__.select().where(cls.user_id == user_id)
        results = await cls._db.fetch_all(query)
        return [cls(**row) for row in results]

    @classmethod
    async def get_public(cls) -> List["BacktestStrategyDB"]:
        """Get all public strategies."""
        query = cls.__table__.select().where(cls.is_public == True)
        results = await cls._db.fetch_all(query)
        return [cls(**row) for row in results]

    async def save(self) -> None:
        """Save strategy to database."""
        if not self.id:
            query = self.__table__.insert().values(
                **{
                    k: v
                    for k, v in self.__dict__.items()
                    if not k.startswith("_")
                }
            )
            await self._db.execute(query)
        else:
            self.updated_at = datetime.utcnow()
            query = (
                self.__table__.update()
                .where(self.__table__.c.id == self.id)
                .values(
                    **{
                        k: v
                        for k, v in self.__dict__.items()
                        if not k.startswith("_")
                    }
                )
            )
            await self._db.execute(query)

    async def delete(self) -> None:
        """Delete strategy from database."""
        query = self.__table__.delete().where(self.__table__.c.id == self.id)
        await self._db.execute(query)


class BacktestResultDB(Base):
    __tablename__ = "backtest_results"

    id = Column(PGUUID, primary_key=True, default=uuid4)
    strategy_id = Column(PGUUID, ForeignKey("backtest_strategies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PGUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    config = Column(JSONB, nullable=False)
    stats = Column(JSONB, nullable=False)
    equity_curve = Column(JSONB, nullable=False)
    trades = Column(JSONB, nullable=False)
    positions = Column(JSONB, nullable=False)
    orders = Column(JSONB, nullable=False)
    metrics = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_backtest_results_strategy_id", "strategy_id"),
        Index("ix_backtest_results_user_id", "user_id")
    )

    @classmethod
    async def get_by_id(cls, result_id: UUID) -> Optional["BacktestResultDB"]:
        """Get result by ID."""
        query = cls.__table__.select().where(cls.id == result_id)
        result = await cls._db.fetch_one(query)
        return cls(**result) if result else None

    @classmethod
    async def get_by_strategy(cls, strategy_id: UUID) -> List["BacktestResultDB"]:
        """Get all results for a strategy."""
        query = cls.__table__.select().where(cls.strategy_id == strategy_id)
        results = await cls._db.fetch_all(query)
        return [cls(**row) for row in results]

    @classmethod
    async def get_by_user(cls, user_id: UUID) -> List["BacktestResultDB"]:
        """Get all results for a user."""
        query = cls.__table__.select().where(cls.user_id == user_id)
        results = await cls._db.fetch_all(query)
        return [cls(**row) for row in results]

    async def save(self) -> None:
        """Save result to database."""
        if not self.id:
            query = self.__table__.insert().values(
                **{
                    k: v
                    for k, v in self.__dict__.items()
                    if not k.startswith("_")
                }
            )
            await self._db.execute(query)

    async def delete(self) -> None:
        """Delete result from database."""
        query = self.__table__.delete().where(self.__table__.c.id == self.id)
        await self._db.execute(query)
