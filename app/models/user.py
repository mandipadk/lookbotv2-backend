from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID


class NotificationPreferences(BaseModel):
    email_enabled: bool = True
    sms_enabled: bool = True
    push_enabled: bool = True
    webhook_enabled: bool = True
    email_address: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    push_tokens: Optional[List[str]] = []
    webhook_urls: Optional[List[str]] = []
    alert_types: Dict[str, bool] = {
        "price": True,
        "volume": True,
        "news": True,
        "technical": True,
        "filings": True,
        "social": True
    }
    quiet_hours: Optional[Dict[str, str]] = {
        "start": "22:00",
        "end": "08:00"
    }
    priority_threshold: str = "medium"  # low, medium, high, critical

    @validator('phone_number')
    def validate_phone(cls, v):
        if v:
            # Remove any non-digit characters
            cleaned = ''.join(filter(str.isdigit, v))
            # Add country code if missing
            if len(cleaned) == 10:  # US number without country code
                cleaned = f"+1{cleaned}"
            elif not cleaned.startswith('+'):
                cleaned = f"+{cleaned}"
            return cleaned
        return v


class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str  # 32-bit key
    email: EmailStr
    notification_preferences: Optional[NotificationPreferences] = None


class User(UserBase):
    id: UUID
    is_active: bool = True
    created_at: datetime
    notification_preferences: NotificationPreferences = NotificationPreferences()

    class Config:
        from_attributes = True


class UserInDB(User):
    hashed_password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    notification_preferences: Optional[NotificationPreferences] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[UUID] = None
