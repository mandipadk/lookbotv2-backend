from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Dict, List

from app.models.technical import TimeFrame, VolumeProfile
from app.services.volume_analysis import volume_analysis_service
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/volume", tags=["Volume Analysis"])

@router.get("/{symbol}/profile", response_model=VolumeProfile)
async def get_volume_profile(
    symbol: str,
    timeframe: TimeFrame = TimeFrame.DAILY,
    lookback_days: int = Query(default=30, ge=1, le=365),
    num_bins: int = Query(default=50, ge=10, le=200),
    value_area_pct: float = Query(default=0.68, ge=0.1, le=1.0),
    current_user=Depends(get_current_user)
):
    """Get volume profile for a symbol."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)
        
        profile = await volume_analysis_service.get_volume_profile(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            num_bins=num_bins,
            value_area_pct=value_area_pct
        )
        
        return profile
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting volume profile: {str(e)}"
        )

@router.get("/{symbol}/analysis", response_model=Dict)
async def get_volume_analysis(
    symbol: str,
    timeframe: TimeFrame = TimeFrame.DAILY,
    lookback_periods: int = Query(default=100, ge=1, le=1000),
    current_user=Depends(get_current_user)
):
    """Get comprehensive volume analysis for a symbol."""
    try:
        analysis = await volume_analysis_service.get_volume_analysis(
            symbol=symbol,
            timeframe=timeframe,
            lookback_periods=lookback_periods
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting volume analysis: {str(e)}"
        )
