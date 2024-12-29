from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime, timedelta
from typing import Dict, List

from app.models.technical import TimeFrame, OrderFlowAnalysis
from app.services.order_flow import order_flow_service
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/order-flow", tags=["Order Flow Analysis"])

@router.get("/{symbol}/analysis", response_model=OrderFlowAnalysis)
async def get_order_flow_analysis(
    symbol: str,
    timeframe: TimeFrame = TimeFrame.MINUTE,
    lookback_minutes: int = Query(default=60, ge=1, le=1440),
    current_user=Depends(get_current_user)
):
    """Get order flow analysis for a symbol."""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=lookback_minutes)
        
        analysis = await order_flow_service.get_order_flow_analysis(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting order flow analysis: {str(e)}"
        )

@router.get("/{symbol}/real-time", response_model=OrderFlowAnalysis)
async def get_real_time_flow(
    symbol: str,
    window_minutes: int = Query(default=5, ge=1, le=60),
    current_user=Depends(get_current_user)
):
    """Get real-time order flow analysis."""
    try:
        analysis = await order_flow_service.get_real_time_flow(
            symbol=symbol,
            window_minutes=window_minutes
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting real-time order flow: {str(e)}"
        )
