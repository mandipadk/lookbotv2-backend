from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from app.api.dependencies.auth import get_current_user
from app.models.backtest import (
    BacktestConfig,
    BacktestResult,
    BacktestStrategy,
    StrategyConfig,
    TimeFrame
)
from app.services.backtest import backtest_service
from app.models.user import User

router = APIRouter()

@router.post("/backtest/run", response_model=BacktestResult)
async def run_backtest(
    config: BacktestConfig,
    strategy_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """Run a backtest with the given configuration and strategy."""
    try:
        # Get strategy
        strategy = await BacktestStrategy.get_by_id(strategy_id)
        if not strategy:
            raise HTTPException(
                status_code=404,
                detail="Strategy not found"
            )
            
        if strategy.user_id != current_user.id and not strategy.is_public:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to use this strategy"
            )
        
        # Run backtest
        result = await backtest_service.run_backtest(
            strategy=strategy,
            config=config
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.post("/backtest/strategy", response_model=BacktestStrategy)
async def create_strategy(
    strategy: StrategyConfig,
    current_user: User = Depends(get_current_user)
):
    """Create a new backtest strategy."""
    try:
        new_strategy = BacktestStrategy(
            user_id=current_user.id,
            name=strategy.name,
            description=strategy.description,
            config=strategy,
            is_public=False
        )
        
        # Save to database
        await new_strategy.save()
        
        return new_strategy
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/backtest/strategy/{strategy_id}", response_model=BacktestStrategy)
async def get_strategy(
    strategy_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """Get a backtest strategy by ID."""
    strategy = await BacktestStrategy.get_by_id(strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=404,
            detail="Strategy not found"
        )
        
    if strategy.user_id != current_user.id and not strategy.is_public:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view this strategy"
        )
        
    return strategy

@router.get("/backtest/strategy", response_model=List[BacktestStrategy])
async def list_strategies(
    current_user: User = Depends(get_current_user),
    include_public: bool = False
):
    """List all strategies owned by the user."""
    strategies = await BacktestStrategy.get_by_user(current_user.id)
    
    if include_public:
        public_strategies = await BacktestStrategy.get_public()
        strategies.extend([s for s in public_strategies if s.user_id != current_user.id])
        
    return strategies

@router.put("/backtest/strategy/{strategy_id}", response_model=BacktestStrategy)
async def update_strategy(
    strategy_id: UUID,
    strategy: StrategyConfig,
    current_user: User = Depends(get_current_user)
):
    """Update a backtest strategy."""
    existing_strategy = await BacktestStrategy.get_by_id(strategy_id)
    if not existing_strategy:
        raise HTTPException(
            status_code=404,
            detail="Strategy not found"
        )
        
    if existing_strategy.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this strategy"
        )
        
    # Update strategy
    existing_strategy.name = strategy.name
    existing_strategy.description = strategy.description
    existing_strategy.config = strategy
    existing_strategy.updated_at = datetime.utcnow()
    
    # Save to database
    await existing_strategy.save()
    
    return existing_strategy

@router.delete("/backtest/strategy/{strategy_id}")
async def delete_strategy(
    strategy_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """Delete a backtest strategy."""
    strategy = await BacktestStrategy.get_by_id(strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=404,
            detail="Strategy not found"
        )
        
    if strategy.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this strategy"
        )
        
    # Delete from database
    await strategy.delete()
    
    return {"message": "Strategy deleted successfully"}

@router.post("/backtest/strategy/{strategy_id}/share")
async def share_strategy(
    strategy_id: UUID,
    is_public: bool,
    current_user: User = Depends(get_current_user)
):
    """Make a strategy public or private."""
    strategy = await BacktestStrategy.get_by_id(strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=404,
            detail="Strategy not found"
        )
        
    if strategy.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to share this strategy"
        )
        
    # Update visibility
    strategy.is_public = is_public
    strategy.updated_at = datetime.utcnow()
    
    # Save to database
    await strategy.save()
    
    return {"message": f"Strategy is now {'public' if is_public else 'private'}"}
