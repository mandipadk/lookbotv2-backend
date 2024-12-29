from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.market_data import market_data_service, DataSource
from app.api.dependencies.auth import get_current_user
from typing import Dict, List, Optional
from datetime import datetime
import logging
from enum import Enum

logger = logging.getLogger(__name__)
router = APIRouter()

class PeriodEnum(str, Enum):
    ONE_DAY = "1d"
    FIVE_DAYS = "5d"
    ONE_MONTH = "1mo"
    THREE_MONTHS = "3mo"
    SIX_MONTHS = "6mo"
    ONE_YEAR = "1y"
    TWO_YEARS = "2y"
    FIVE_YEARS = "5y"
    MAX = "max"

class IntervalEnum(str, Enum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    ONE_WEEK = "1wk"
    ONE_MONTH = "1mo"

@router.get("/quote/{symbol}")
async def get_quote(
    symbol: str,
    source: Optional[DataSource] = Query(DataSource.FINNHUB, description="Data source"),
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Get real-time quote for a symbol.
    
    - **symbol**: Stock symbol (e.g., AAPL)
    - **source**: Data source (finnhub, yahoo, or fmp)
    """
    quote = await market_data_service.get_real_time_quote(symbol.upper(), source)
    if not quote:
        raise HTTPException(
            status_code=404,
            detail=f"Quote not found for symbol: {symbol}"
        )
    return quote

@router.get("/historical/{symbol}")
async def get_historical_data(
    symbol: str,
    period: PeriodEnum = Query(PeriodEnum.ONE_DAY, description="Time period"),
    interval: IntervalEnum = Query(IntervalEnum.ONE_MINUTE, description="Time interval"),
    source: Optional[DataSource] = Query(DataSource.YAHOO, description="Data source"),
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get historical price data.
    
    - **symbol**: Stock symbol (e.g., AAPL)
    - **period**: Time period (1d, 5d, 1mo, etc.)
    - **interval**: Time interval (1m, 5m, 1h, etc.)
    - **source**: Data source (finnhub, yahoo, or fmp)
    """
    data = await market_data_service.get_historical_data(
        symbol.upper(),
        period=period.value,
        interval=interval.value,
        source=source
    )
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Historical data not found for symbol: {symbol}"
        )
    return data

@router.get("/profile/{symbol}")
async def get_company_profile(
    symbol: str,
    source: Optional[DataSource] = Query(DataSource.FMP, description="Data source"),
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Get comprehensive company profile information.
    
    - **symbol**: Stock symbol (e.g., AAPL)
    - **source**: Data source (finnhub or fmp)
    """
    profile = await market_data_service.get_company_profile(symbol.upper(), source)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Company profile not found for symbol: {symbol}"
        )
    return profile

@router.get("/insider/{symbol}")
async def get_insider_trading(
    symbol: str,
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get insider trading information.
    
    - **symbol**: Stock symbol (e.g., AAPL)
    """
    data = await market_data_service.get_insider_trading(symbol.upper())
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Insider trading data not found for symbol: {symbol}"
        )
    return data

@router.get("/institutional/{symbol}")
async def get_institutional_holders(
    symbol: str,
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get institutional holders information.
    
    - **symbol**: Stock symbol (e.g., AAPL)
    """
    data = await market_data_service.get_institutional_holders(symbol.upper())
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Institutional holders data not found for symbol: {symbol}"
        )
    return data

@router.get("/ratios/{symbol}")
async def get_financial_ratios(
    symbol: str,
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Get key financial ratios.
    
    - **symbol**: Stock symbol (e.g., AAPL)
    """
    data = await market_data_service.get_financial_ratios(symbol.upper())
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Financial ratios not found for symbol: {symbol}"
        )
    return data

@router.get("/indicators/{symbol}")
async def get_technical_indicators(
    symbol: str,
    resolution: str = Query("D", regex="^[1-9][0-9]*[DMW]$|^D$", description="Time resolution"),
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Get comprehensive technical indicators.
    
    - **symbol**: Stock symbol (e.g., AAPL)
    - **resolution**: Time resolution (D for daily, W for weekly, M for monthly)
    
    Returns:
    - Moving Averages (SMA 20/50, EMA 12/26)
    - RSI (14-period)
    - MACD (12,26,9)
    - Bollinger Bands (20,2)
    """
    indicators = await market_data_service.get_technical_indicators(
        symbol.upper(),
        resolution=resolution
    )
    if not indicators:
        raise HTTPException(
            status_code=404,
            detail=f"Technical indicators not found for symbol: {symbol}"
        )
    return indicators
