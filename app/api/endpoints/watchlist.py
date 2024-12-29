from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.db import get_db
from app.models.watchlist import (
    Alert, AlertCreate,
    WatchlistItem, WatchlistItemCreate,
    Watchlist, WatchlistCreate, WatchlistType,
    WatchlistResponse, WatchlistDetailResponse, WatchlistItemResponse
)
from app.services.watchlist import watchlist_service
from app.services.market_data import market_data_service

router = APIRouter()

@router.post("/watchlists", response_model=WatchlistResponse)
async def create_watchlist(
    watchlist: WatchlistCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new watchlist."""
    db_watchlist = await watchlist_service.create_watchlist(
        db=db,
        user_id=current_user["id"],
        watchlist=watchlist
    )
    
    return WatchlistResponse(
        **db_watchlist.dict(),
        items_count=len(db_watchlist.items),
        alerts_count=len(db_watchlist.alerts)
    )

@router.get("/watchlists", response_model=List[WatchlistResponse])
async def get_watchlists(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    type: Optional[WatchlistType] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all watchlists for the current user."""
    watchlists = await watchlist_service.get_watchlists(
        db=db,
        user_id=current_user["id"],
        skip=skip,
        limit=limit
    )
    
    if type:
        watchlists = [w for w in watchlists if w.type == type]
    
    return [
        WatchlistResponse(
            **w.dict(),
            items_count=len(w.items),
            alerts_count=len(w.alerts)
        )
        for w in watchlists
    ]

@router.get("/watchlists/{watchlist_id}", response_model=WatchlistDetailResponse)
async def get_watchlist(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific watchlist by ID."""
    watchlist = await watchlist_service.get_watchlist(
        db=db,
        watchlist_id=watchlist_id,
        user_id=current_user["id"]
    )
    
    if not watchlist:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found"
        )
    
    return watchlist

@router.put("/watchlists/{watchlist_id}", response_model=WatchlistDetailResponse)
async def update_watchlist(
    watchlist_id: UUID,
    updates: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a watchlist."""
    watchlist = await watchlist_service.update_watchlist(
        db=db,
        watchlist_id=watchlist_id,
        user_id=current_user["id"],
        updates=updates
    )
    
    if not watchlist:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found"
        )
    
    return watchlist

@router.delete("/watchlists/{watchlist_id}")
async def delete_watchlist(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a watchlist."""
    success = await watchlist_service.delete_watchlist(
        db=db,
        watchlist_id=watchlist_id,
        user_id=current_user["id"]
    )
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found"
        )
    
    return {"message": "Watchlist deleted successfully"}

@router.post("/watchlists/{watchlist_id}/items", response_model=WatchlistItemResponse)
async def add_watchlist_item(
    watchlist_id: UUID,
    item: WatchlistItemCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Add an item to a watchlist."""
    db_item = await watchlist_service.add_watchlist_item(
        db=db,
        watchlist_id=watchlist_id,
        user_id=current_user["id"],
        item=item
    )
    
    if not db_item:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found"
        )
    
    # Get current market data
    market_data = await market_data_service.get_quote(db_item.symbol)
    
    return WatchlistItemResponse(
        **db_item.dict(),
        current_price=market_data.get("price"),
        price_change_24h=market_data.get("price_change_24h"),
        volume_24h=market_data.get("volume_24h"),
        market_cap=market_data.get("market_cap")
    )

@router.delete("/watchlists/{watchlist_id}/items/{item_id}")
async def remove_watchlist_item(
    watchlist_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Remove an item from a watchlist."""
    success = await watchlist_service.remove_watchlist_item(
        db=db,
        watchlist_id=watchlist_id,
        user_id=current_user["id"],
        item_id=item_id
    )
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Watchlist item not found"
        )
    
    return {"message": "Watchlist item removed successfully"}

@router.post("/watchlists/{watchlist_id}/alerts", response_model=Alert)
async def add_alert(
    watchlist_id: UUID,
    alert: AlertCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Add an alert to a watchlist."""
    db_alert = await watchlist_service.add_alert(
        db=db,
        watchlist_id=watchlist_id,
        user_id=current_user["id"],
        alert=alert
    )
    
    if not db_alert:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found"
        )
    
    return db_alert

@router.delete("/watchlists/{watchlist_id}/alerts/{alert_id}")
async def remove_alert(
    watchlist_id: UUID,
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Remove an alert from a watchlist."""
    success = await watchlist_service.remove_alert(
        db=db,
        watchlist_id=watchlist_id,
        user_id=current_user["id"],
        alert_id=alert_id
    )
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Alert not found"
        )
    
    return {"message": "Alert removed successfully"}

@router.get("/watchlists/{watchlist_id}/items", response_model=List[WatchlistItemResponse])
async def get_watchlist_items(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all items in a watchlist with current market data."""
    watchlist = await watchlist_service.get_watchlist(
        db=db,
        watchlist_id=watchlist_id,
        user_id=current_user["id"]
    )
    
    if not watchlist:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found"
        )
    
    items_with_data = []
    for item in watchlist.items:
        market_data = await market_data_service.get_quote(item.symbol)
        items_with_data.append(
            WatchlistItemResponse(
                **item.dict(),
                current_price=market_data.get("price"),
                price_change_24h=market_data.get("price_change_24h"),
                volume_24h=market_data.get("volume_24h"),
                market_cap=market_data.get("market_cap")
            )
        )
    
    return items_with_data

@router.get("/watchlists/{watchlist_id}/alerts", response_model=List[Alert])
async def get_watchlist_alerts(
    watchlist_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all alerts for a watchlist."""
    watchlist = await watchlist_service.get_watchlist(
        db=db,
        watchlist_id=watchlist_id,
        user_id=current_user["id"]
    )
    
    if not watchlist:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found"
        )
    
    return watchlist.alerts
