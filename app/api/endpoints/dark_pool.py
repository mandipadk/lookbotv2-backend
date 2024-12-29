from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime
from typing import Dict, List

from app.models.technical import (
    TimeFrame,
    DarkPoolAnalysis,
    DarkPoolVenue,
    PriceLevel
)
from app.services.dark_pool import dark_pool_service
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/dark-pool", tags=["Dark Pool Analysis"])

@router.get("/{symbol}/analysis", response_model=DarkPoolAnalysis)
async def get_dark_pool_analysis(
    symbol: str,
    timeframe: TimeFrame = TimeFrame.MINUTE,
    lookback_minutes: int = Query(default=60, ge=1, le=1440),
    current_user=Depends(get_current_user)
):
    """Get complete dark pool analysis for a symbol."""
    try:
        analysis = await dark_pool_service.get_dark_pool_analysis(
            symbol=symbol,
            timeframe=timeframe,
            lookback_minutes=lookback_minutes
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting dark pool analysis: {str(e)}"
        )

@router.get("/{symbol}/real-time", response_model=DarkPoolAnalysis)
async def get_real_time_dark_pool(
    symbol: str,
    window_minutes: int = Query(default=5, ge=1, le=60),
    current_user=Depends(get_current_user)
):
    """Get real-time dark pool analysis."""
    try:
        analysis = await dark_pool_service.get_real_time_dark_pool(
            symbol=symbol,
            window_minutes=window_minutes
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting real-time dark pool data: {str(e)}"
        )

@router.get("/{symbol}/venues", response_model=List[DarkPoolVenue])
async def get_dark_pool_venues(
    symbol: str,
    lookback_minutes: int = Query(default=60, ge=1, le=1440),
    current_user=Depends(get_current_user)
):
    """Get dark pool venue statistics."""
    try:
        analysis = await dark_pool_service.get_dark_pool_analysis(
            symbol=symbol,
            timeframe=TimeFrame.MINUTE,
            lookback_minutes=lookback_minutes
        )
        
        return sorted(
            analysis.venues,
            key=lambda x: x.volume,
            reverse=True
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting dark pool venues: {str(e)}"
        )

@router.get("/{symbol}/levels", response_model=List[PriceLevel])
async def get_dark_pool_levels(
    symbol: str,
    significant_only: bool = Query(default=False),
    lookback_minutes: int = Query(default=60, ge=1, le=1440),
    current_user=Depends(get_current_user)
):
    """Get dark pool price levels."""
    try:
        analysis = await dark_pool_service.get_dark_pool_analysis(
            symbol=symbol,
            timeframe=TimeFrame.MINUTE,
            lookback_minutes=lookback_minutes
        )
        
        levels = analysis.price_levels
        if significant_only:
            levels = [level for level in levels if level.is_significant]
        
        return sorted(levels, key=lambda x: x.price)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting dark pool levels: {str(e)}"
        )
