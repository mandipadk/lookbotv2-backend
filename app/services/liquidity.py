import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

from app.services.market_data import market_data_service
from app.services.order_flow import order_flow_service
from app.models.technical import (
    TimeFrame,
    LiquidityLevel,
    OrderBookSnapshot,
    MarketImpactEstimate,
    LiquidityAnalysis
)
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

class LiquidityService:
    def __init__(self):
        self.market_data = market_data_service
        self.order_flow = order_flow_service
        self.LIQUIDITY_LEVEL_THRESHOLD = 0.7  # Minimum strength for significant levels
        self.IMPACT_SIZES = [1000, 5000, 10000, 50000, 100000]  # Standard sizes for impact estimation

    async def get_liquidity_analysis(
        self,
        symbol: str,
        timeframe: TimeFrame = TimeFrame.MINUTE
    ) -> LiquidityAnalysis:
        """Get complete liquidity analysis for a symbol."""
        try:
            # Try to get from cache
            cache_key = f"liquidity:{symbol}:{timeframe}"
            cached_data = await redis_client.get_json(cache_key)
            if cached_data:
                return LiquidityAnalysis(**cached_data)

            # Get order book data
            order_book = await self._get_order_book_snapshot(symbol)
            
            # Get historical data for liquidity levels
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=30)  # Look back 30 days
            historical_data = await self.market_data.get_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_time,
                end_date=end_time
            )
            
            # Calculate components
            liquidity_levels = await self._find_liquidity_levels(
                symbol,
                historical_data
            )
            impact_estimates = self._estimate_market_impact(
                symbol,
                order_book
            )
            metrics = self._calculate_liquidity_metrics(
                historical_data,
                order_book
            )
            
            # Create analysis
            analysis = LiquidityAnalysis(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                timeframe=timeframe,
                liquidity_levels=liquidity_levels,
                order_book=order_book,
                market_impact_estimates=impact_estimates,
                **metrics
            )
            
            # Cache for 1 minute
            await redis_client.set_json(cache_key, analysis.dict(), 60)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing liquidity for {symbol}: {str(e)}")
            raise

    async def _get_order_book_snapshot(self, symbol: str) -> OrderBookSnapshot:
        """Get current order book snapshot."""
        try:
            order_book = await self.market_data.get_order_book(symbol)
            
            # Calculate metrics
            bids = {float(k): float(v) for k, v in order_book['bids'].items()}
            asks = {float(k): float(v) for k, v in order_book['asks'].items()}
            
            bid_prices = list(bids.keys())
            ask_prices = list(asks.keys())
            best_bid = max(bid_prices)
            best_ask = min(ask_prices)
            
            spread = best_ask - best_bid
            mid_price = (best_ask + best_bid) / 2
            
            # Calculate weighted mid price
            total_bid_volume = sum(bids.values())
            total_ask_volume = sum(asks.values())
            weighted_mid = (
                (best_bid * total_ask_volume + best_ask * total_bid_volume) /
                (total_bid_volume + total_ask_volume)
            )
            
            # Calculate depth and imbalance
            bid_depth = sum(
                vol for price, vol in bids.items()
                if price >= best_bid * 0.99  # Within 1% of best bid
            )
            ask_depth = sum(
                vol for price, vol in asks.items()
                if price <= best_ask * 1.01  # Within 1% of best ask
            )
            
            imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth)
            
            return OrderBookSnapshot(
                timestamp=datetime.utcnow(),
                bids=bids,
                asks=asks,
                bid_depth=float(bid_depth),
                ask_depth=float(ask_depth),
                spread=float(spread),
                mid_price=float(mid_price),
                weighted_mid_price=float(weighted_mid),
                imbalance_ratio=float(imbalance)
            )
            
        except Exception as e:
            logger.error(f"Error getting order book snapshot: {str(e)}")
            raise

    async def _find_liquidity_levels(
        self,
        symbol: str,
        historical_data: pd.DataFrame
    ) -> List[LiquidityLevel]:
        """Find significant liquidity levels."""
        try:
            levels = []
            
            # Get order flow data
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=30)
            order_flow = await self.order_flow.get_order_flow_analysis(
                symbol=symbol,
                timeframe=TimeFrame.DAILY,
                start_time=start_time,
                end_time=end_time
            )
            
            # Combine price levels from different sources
            price_levels = set()
            
            # Add levels from historical highs/lows
            price_levels.update(historical_data['high'].unique())
            price_levels.update(historical_data['low'].unique())
            
            # Add levels from volume profile
            for imbalance in order_flow.imbalances:
                if abs(imbalance.net_volume) > 0:
                    price_levels.add(imbalance.price_level)
            
            # Analyze each level
            for price in sorted(price_levels):
                # Calculate strength based on multiple factors
                volume_at_level = sum(
                    imb.net_volume
                    for imb in order_flow.imbalances
                    if abs(imb.price_level - price) < 0.01
                )
                
                hits = len(
                    historical_data[
                        (historical_data['high'] >= price * 0.99) &
                        (historical_data['low'] <= price * 1.01)
                    ]
                )
                
                # Calculate age in periods
                first_hit = historical_data[
                    (historical_data['high'] >= price * 0.99) &
                    (historical_data['low'] <= price * 1.01)
                ]['timestamp'].min()
                age = (end_time - first_hit).days if pd.notna(first_hit) else 0
                
                # Calculate strength (0-1)
                strength = min(1.0, (
                    0.4 * (hits / len(historical_data)) +
                    0.3 * (age / 30) +
                    0.3 * (abs(volume_at_level) / order_flow.trades[0].volume)
                ))
                
                if strength >= self.LIQUIDITY_LEVEL_THRESHOLD:
                    # Determine level type
                    recent_price = historical_data['close'].iloc[-1]
                    level_type = (
                        "support" if price < recent_price
                        else "resistance" if price > recent_price
                        else "cluster"
                    )
                    
                    last_test = historical_data[
                        (historical_data['high'] >= price * 0.99) &
                        (historical_data['low'] <= price * 1.01)
                    ]['timestamp'].max()
                    
                    level = LiquidityLevel(
                        price=float(price),
                        volume=float(abs(volume_at_level)),
                        type=level_type,
                        strength=float(strength),
                        age=int(age),
                        hits=int(hits),
                        last_test=last_test,
                        metadata={
                            "avg_bounce_size": float(
                                historical_data[
                                    (historical_data['high'] >= price * 0.99) &
                                    (historical_data['low'] <= price * 1.01)
                                ]['high'].mean() -
                                historical_data[
                                    (historical_data['high'] >= price * 0.99) &
                                    (historical_data['low'] <= price * 1.01)
                                ]['low'].mean()
                            )
                        }
                    )
                    levels.append(level)
            
            return sorted(levels, key=lambda x: x.price)
            
        except Exception as e:
            logger.error(f"Error finding liquidity levels: {str(e)}")
            raise

    def _estimate_market_impact(
        self,
        symbol: str,
        order_book: OrderBookSnapshot
    ) -> List[MarketImpactEstimate]:
        """Estimate market impact for different order sizes."""
        try:
            estimates = []
            
            for size in self.IMPACT_SIZES:
                for side in ["buy", "sell"]:
                    book_side = (
                        order_book.asks if side == "buy"
                        else order_book.bids
                    )
                    
                    # Calculate impact through order book walking
                    remaining_size = size
                    total_cost = 0
                    max_price = 0
                    
                    for price in (
                        sorted(book_side.keys())
                        if side == "buy"
                        else sorted(book_side.keys(), reverse=True)
                    ):
                        available = book_side[price]
                        taken = min(remaining_size, available)
                        total_cost += taken * price
                        remaining_size -= taken
                        max_price = price
                        
                        if remaining_size <= 0:
                            break
                    
                    # Calculate metrics
                    avg_price = total_cost / size
                    slippage = abs(avg_price - order_book.mid_price) / order_book.mid_price
                    impact = abs(max_price - order_book.mid_price) / order_book.mid_price
                    
                    # Calculate confidence based on order book depth
                    confidence = 1.0
                    if remaining_size > 0:
                        confidence = (size - remaining_size) / size
                    
                    estimate = MarketImpactEstimate(
                        size=float(size),
                        side=side,
                        estimated_impact=float(impact),
                        estimated_cost=float(total_cost),
                        estimated_slippage=float(slippage),
                        confidence=float(confidence)
                    )
                    estimates.append(estimate)
            
            return estimates
            
        except Exception as e:
            logger.error(f"Error estimating market impact: {str(e)}")
            raise

    def _calculate_liquidity_metrics(
        self,
        historical_data: pd.DataFrame,
        order_book: OrderBookSnapshot
    ) -> Dict:
        """Calculate overall liquidity metrics."""
        try:
            # Calculate average daily volume
            daily_volumes = historical_data.resample('D')['volume'].sum()
            avg_daily_volume = float(daily_volumes.mean())
            
            # Calculate relative spread
            relative_spread = float(
                order_book.spread / order_book.mid_price
            )
            
            # Calculate depth imbalance
            depth_imbalance = float(
                (order_book.bid_depth - order_book.ask_depth) /
                (order_book.bid_depth + order_book.ask_depth)
            )
            
            # Calculate volatility
            returns = historical_data['close'].pct_change()
            volatility = float(returns.std())
            
            # Calculate volatility-adjusted spread
            volatility_adjusted_spread = float(
                relative_spread / volatility
            )
            
            # Calculate resiliency score
            price_impact = [
                est.estimated_impact
                for est in self._estimate_market_impact(
                    None,
                    order_book
                )
                if est.size == self.IMPACT_SIZES[0]  # Use smallest size
            ]
            avg_impact = sum(price_impact) / len(price_impact)
            resiliency = 1 / (1 + avg_impact)
            resiliency_score = float(resiliency * 100)
            
            # Calculate overall liquidity score
            liquidity_score = float(
                0.3 * (1 - relative_spread) * 100 +
                0.3 * (avg_daily_volume / 1e6) * 100 +  # Normalize to millions
                0.2 * (1 - abs(depth_imbalance)) * 100 +
                0.2 * resiliency_score
            )
            
            return {
                "avg_daily_volume": avg_daily_volume,
                "relative_spread": relative_spread,
                "depth_imbalance": depth_imbalance,
                "liquidity_score": liquidity_score,
                "volatility_adjusted_spread": volatility_adjusted_spread,
                "resiliency_score": resiliency_score
            }
            
        except Exception as e:
            logger.error(f"Error calculating liquidity metrics: {str(e)}")
            raise

# Global liquidity service instance
liquidity_service = LiquidityService()
