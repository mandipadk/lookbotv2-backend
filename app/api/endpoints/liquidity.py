from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime
from typing import Dict, List

from app.models.technical import TimeFrame, LiquidityAnalysis, LiquidityLevel
from app.services.liquidity import liquidity_service
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/liquidity", tags=["Liquidity Analysis"])

@router.get("/{symbol}/analysis", response_model=LiquidityAnalysis)
async def get_liquidity_analysis(
    symbol: str,
    timeframe: TimeFrame = TimeFrame.MINUTE,
    current_user=Depends(get_current_user)
):
    """Get complete liquidity analysis for a symbol."""
    try:
        analysis = await liquidity_service.get_liquidity_analysis(
            symbol=symbol,
            timeframe=timeframe
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting liquidity analysis: {str(e)}"
        )

@router.get("/{symbol}/levels", response_model=List[LiquidityLevel])
async def get_liquidity_levels(
    symbol: str,
    min_strength: float = Query(default=0.7, ge=0.0, le=1.0),
    current_user=Depends(get_current_user)
):
    """Get significant liquidity levels for a symbol."""
    try:
        analysis = await liquidity_service.get_liquidity_analysis(
            symbol=symbol
        )
        
        levels = [
            level for level in analysis.liquidity_levels
            if level.strength >= min_strength
        ]
        
        return sorted(levels, key=lambda x: x.price)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting liquidity levels: {str(e)}"
        )
