from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "LookBot v2"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    
    # Security
    JWT_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_ALGORITHM: str = "HS256"

    # Database
    SUPABASE_URL: str
    SUPABASE_KEY: str
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str]
    
    # API Keys
    ALPHA_VANTAGE_API_KEY: str
    FINNHUB_API_KEY: str
    FMP_API_KEY: str
    SEC_API_KEY: str
    
    # Rate Limiting
    RATE_LIMIT_PER_SECOND: int = 10
    
    # SMTP Settings
    SMTP_HOST: str
    SMTP_PORT: str
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SMTP_FROM_EMAIL: str

    # User Agent
    USER_AGENT: str

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
