from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime
from typing import Dict, List

from app.models.technical import (
    OptionFlow,
    ExpiryAnalysis,
    StrikeAnalysis,
    OptionsFlowAnalysis
)
from app.services.options_flow import options_flow_service
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/options-flow", tags=["Options Flow Analysis"])

@router.get("/{symbol}/analysis", response_model=OptionsFlowAnalysis)
async def get_options_flow_analysis(
    symbol: str,
    lookback_minutes: int = Query(default=60, ge=1, le=1440),
    current_user=Depends(get_current_user)
):
    """Get complete options flow analysis for a symbol."""
    try:
        analysis = await options_flow_service.get_options_flow_analysis(
            symbol=symbol,
            lookback_minutes=lookback_minutes
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting options flow analysis: {str(e)}"
        )

@router.get("/{symbol}/real-time", response_model=OptionsFlowAnalysis)
async def get_real_time_flow(
    symbol: str,
    window_minutes: int = Query(default=5, ge=1, le=60),
    current_user=Depends(get_current_user)
):
    """Get real-time options flow analysis."""
    try:
        analysis = await options_flow_service.get_real_time_flow(
            symbol=symbol,
            window_minutes=window_minutes
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting real-time options flow: {str(e)}"
        )

@router.get("/{symbol}/expiries", response_model=List[ExpiryAnalysis])
async def get_expiry_analysis(
    symbol: str,
    lookback_minutes: int = Query(default=60, ge=1, le=1440),
    current_user=Depends(get_current_user)
):
    """Get options analysis by expiry date."""
    try:
        analysis = await options_flow_service.get_options_flow_analysis(
            symbol=symbol,
            lookback_minutes=lookback_minutes
        )
        
        return sorted(
            analysis.expiries,
            key=lambda x: x.expiry
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting expiry analysis: {str(e)}"
        )

@router.get("/{symbol}/unusual", response_model=List[OptionFlow])
async def get_unusual_activity(
    symbol: str,
    lookback_minutes: int = Query(default=60, ge=1, le=1440),
    current_user=Depends(get_current_user)
):
    """Get unusual options activity."""
    try:
        analysis = await options_flow_service.get_options_flow_analysis(
            symbol=symbol,
            lookback_minutes=lookback_minutes
        )
        
        return sorted(
            analysis.unusual_activity,
            key=lambda x: x.premium,
            reverse=True
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting unusual activity: {str(e)}"
        )
