from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from uuid import UUID, uuid4

class AlertType(str, Enum):
    PRICE = "price"
    VOLUME = "volume"
    NEWS = "news"
    TECHNICAL = "technical"
    FILING = "filing"
    SOCIAL = "social"
    CUSTOM = "custom"

class AlertCondition(str, Enum):
    ABOVE = "above"
    BELOW = "below"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    PERCENT_CHANGE = "percent_change"
    VOLUME_SPIKE = "volume_spike"
    SENTIMENT = "sentiment"
    TOPIC = "topic"
    FILING_TYPE = "filing_type"
    SOCIAL_VOLUME = "social_volume"
    CUSTOM = "custom"

class AlertPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class WatchlistType(str, Enum):
    TICKER = "ticker"
    TOPIC = "topic"
    SECTOR = "sector"
    INDUSTRY = "industry"
    CUSTOM = "custom"

class AlertBase(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: AlertType
    condition: AlertCondition
    value: float | str
    priority: AlertPriority = AlertPriority.MEDIUM
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    cooldown_minutes: int = 60
    
    class Config:
        use_enum_values = True

class AlertCreate(AlertBase):
    pass

class Alert(AlertBase):
    watchlist_id: UUID

class WatchlistItemBase(BaseModel):
    symbol: str
    notes: Optional[str] = None
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('symbol')
    def validate_symbol(cls, v):
        return v.upper()

class WatchlistItemCreate(WatchlistItemBase):
    pass

class WatchlistItem(WatchlistItemBase):
    id: UUID = Field(default_factory=uuid4)
    watchlist_id: UUID
    alerts: List[Alert] = []

class WatchlistBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: WatchlistType = WatchlistType.TICKER
    is_public: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class WatchlistCreate(WatchlistBase):
    pass

class Watchlist(WatchlistBase):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    items: List[WatchlistItem] = []
    alerts: List[Alert] = []

    class Config:
        use_enum_values = True

# Response Models
class WatchlistResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    type: WatchlistType
    is_public: bool
    created_at: datetime
    updated_at: datetime
    items_count: int
    alerts_count: int

class WatchlistDetailResponse(Watchlist):
    items: List[WatchlistItem]
    alerts: List[Alert]

class WatchlistItemResponse(WatchlistItem):
    current_price: Optional[float]
    price_change_24h: Optional[float]
    volume_24h: Optional[float]
    market_cap: Optional[float]
    alerts: List[Alert]

# Database Models
from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class DBAlert(Base):
    __tablename__ = "alerts"

    id = Column(PGUUID, primary_key=True, default=uuid4)
    type = Column(Enum(AlertType))
    condition = Column(Enum(AlertCondition))
    value = Column(String)
    priority = Column(Enum(AlertPriority))
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_triggered = Column(DateTime, nullable=True)
    trigger_count = Column(Float, default=0)
    cooldown_minutes = Column(Float, default=60)
    watchlist_id = Column(PGUUID, ForeignKey("watchlists.id"))
    
    watchlist = relationship("DBWatchlist", back_populates="alerts")

class DBWatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(PGUUID, primary_key=True, default=uuid4)
    symbol = Column(String, index=True)
    notes = Column(Text, nullable=True)
    price_target = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    watchlist_id = Column(PGUUID, ForeignKey("watchlists.id"))
    
    watchlist = relationship("DBWatchlist", back_populates="items")
    alerts = relationship("DBAlert", secondary="watchlist_item_alerts")

class DBWatchlist(Base):
    __tablename__ = "watchlists"

    id = Column(PGUUID, primary_key=True, default=uuid4)
    name = Column(String)
    description = Column(Text, nullable=True)
    type = Column(Enum(WatchlistType))
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(PGUUID, ForeignKey("users.id"))
    
    user = relationship("DBUser", back_populates="watchlists")
    items = relationship("DBWatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")
    alerts = relationship("DBAlert", back_populates="watchlist", cascade="all, delete-orphan")
