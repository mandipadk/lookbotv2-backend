from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.db.base_class import Base

class NotificationType(str, Enum):
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    PUSH = "push"

class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED = "skipped"

class NotificationBase(BaseModel):
    type: NotificationType
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    priority: NotificationPriority = NotificationPriority.MEDIUM
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    read: bool = False
    read_at: Optional[datetime] = None

    class Config:
        use_enum_values = True

class NotificationCreate(NotificationBase):
    pass

class Notification(NotificationBase):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    status: NotificationStatus
    error: Optional[str] = None

class NotificationResponse(BaseModel):
    id: UUID
    type: NotificationType
    title: str
    message: str
    data: Optional[Dict[str, Any]]
    priority: NotificationPriority
    status: NotificationStatus
    created_at: datetime
    read: bool
    read_at: Optional[datetime]

class NotificationPreferences(BaseModel):
    email: bool = True
    webhook: bool = True
    sms: bool = True
    push: bool = True
    email_address: Optional[str] = None
    webhook_url: Optional[str] = None
    phone_number: Optional[str] = None
    push_tokens: Optional[Dict[str, str]] = None

# Database Models
class DBNotification(Base):
    __tablename__ = "notifications"

    id = Column(PGUUID, primary_key=True, default=uuid4)
    user_id = Column(PGUUID, index=True)
    type = Column(SQLEnum(NotificationType))
    title = Column(String)
    message = Column(Text)
    data = Column(JSON, nullable=True)
    priority = Column(SQLEnum(NotificationPriority))
    status = Column(SQLEnum(NotificationStatus))
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

    def to_response(self) -> NotificationResponse:
        return NotificationResponse(
            id=self.id,
            type=self.type,
            title=self.title,
            message=self.message,
            data=self.data,
            priority=self.priority,
            status=self.status,
            created_at=self.created_at,
            read=self.read,
            read_at=self.read_at
        )
