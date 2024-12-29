from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import List, Optional
from app.services.market_data import market_data_service
from app.models.technical import TimeFrame
from app.api.dependencies.auth import get_current_user

router = APIRouter()

@router.get("/{symbol}/price")
async def get_stock_price(
    symbol: str = Path(..., min_length=1),
    current_user = Depends(get_current_user)
):
    """Get current stock price."""
    try:
        data = await market_data_service.get_current_price(symbol)
        if not data:
            raise HTTPException(status_code=404, detail="Price data not found")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{symbol}/indicators")
async def get_technical_indicators(
    symbol: str = Path(..., min_length=1),
    timeframe: TimeFrame = TimeFrame.DAILY,
    current_user = Depends(get_current_user)
):
    """Get technical indicators for a stock."""
    try:
        data = await market_data_service.get_technical_indicators(symbol, timeframe)
        if not data:
            raise HTTPException(status_code=404, detail="Technical data not found")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{symbol}/financials/{statement_type}")
async def get_financial_statements(
    symbol: str = Path(..., min_length=1),
    statement_type: str = Path(..., regex="^(income|balance|cash)$"),
    current_user = Depends(get_current_user)
):
    """Get financial statements for a stock."""
    try:
        data = await market_data_service.get_financial_statements(symbol, statement_type)
        if not data:
            raise HTTPException(status_code=404, detail="Financial data not found")
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{symbol}/news")
async def get_stock_news(
    symbol: str,
    limit: int = Query(10, ge=1, le=100),
    current_user = Depends(get_current_user)
):
    """Get news for a stock."""
    try:
        data = await market_data_service.get_stock_news(symbol, limit)
        if not data:
            raise HTTPException(status_code=404, detail="News data not found")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/watchlist")
async def get_watchlist(
    current_user = Depends(get_current_user)
):
    """Get user's watchlist."""
    try:
        data = await market_data_service.get_watchlist(current_user.id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/watchlist/{symbol}")
async def add_to_watchlist(
    symbol: str = Path(..., min_length=1),
    current_user = Depends(get_current_user)
):
    """Add symbol to watchlist."""
    try:
        success = await market_data_service.add_to_watchlist(current_user.id, symbol)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add to watchlist")
        return {"message": "Added to watchlist"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(
    symbol: str = Path(..., min_length=1),
    current_user = Depends(get_current_user)
):
    """Remove symbol from watchlist."""
    try:
        success = await market_data_service.remove_from_watchlist(current_user.id, symbol)
        if not success:
            raise HTTPException(status_code=404, detail="Symbol not found in watchlist")
        return {"message": "Removed from watchlist"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
