import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from collections import defaultdict

from app.services.market_data import market_data_service
from app.models.technical import (
    TimeFrame,
    DarkPoolTrade,
    DarkPoolVenue,
    PriceLevel,
    DarkPoolAnalysis
)
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

class DarkPoolService:
    def __init__(self):
        self.market_data = market_data_service
        self.BLOCK_TRADE_THRESHOLD = 10000  # Minimum size for block trades
        self.SIGNIFICANT_LEVEL_THRESHOLD = 0.1  # 10% of total volume
        self.MAX_PRICE_LEVELS = 20  # Maximum number of price levels to track

    async def get_dark_pool_analysis(
        self,
        symbol: str,
        timeframe: TimeFrame,
        lookback_minutes: int = 60
    ) -> DarkPoolAnalysis:
        """Get complete dark pool analysis for a symbol."""
        try:
            # Try to get from cache
            cache_key = f"dark_pool:{symbol}:{timeframe}:{lookback_minutes}"
            cached_data = await redis_client.get_json(cache_key)
            if cached_data:
                return DarkPoolAnalysis(**cached_data)

            # Get dark pool trades
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=lookback_minutes)
            
            trades = await self._get_dark_pool_trades(
                symbol,
                start_time,
                end_time
            )
            
            if not trades:
                raise ValueError(f"No dark pool trades found for {symbol}")
            
            # Process trades into DataFrame for analysis
            df = pd.DataFrame([t.dict() for t in trades])
            
            # Calculate venue statistics
            venues = self._analyze_venues(df)
            
            # Analyze price levels
            price_levels, significant_levels = self._analyze_price_levels(df)
            
            # Calculate volume distribution
            volume_dist = self._calculate_volume_distribution(
                df,
                timeframe
            )
            
            # Calculate overall metrics
            total_volume = df['volume'].sum()
            total_trades = len(df)
            avg_trade_size = total_volume / total_trades if total_trades > 0 else 0
            block_trades = df[df['is_block']]
            block_count = len(block_trades)
            block_ratio = (
                block_trades['volume'].sum() / total_volume
                if total_volume > 0 else 0
            )
            
            # Create analysis
            analysis = DarkPoolAnalysis(
                symbol=symbol,
                timestamp=end_time,
                timeframe=timeframe,
                total_volume=float(total_volume),
                total_trades=int(total_trades),
                avg_trade_size=float(avg_trade_size),
                block_trade_count=int(block_count),
                block_volume_ratio=float(block_ratio),
                recent_trades=sorted(
                    trades,
                    key=lambda x: x.timestamp,
                    reverse=True
                )[:100],  # Last 100 trades
                venues=venues,
                price_levels=price_levels,
                significant_levels=significant_levels,
                volume_distribution=volume_dist,
                metadata={
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "lookback_minutes": lookback_minutes
                }
            )
            
            # Cache for 30 seconds
            await redis_client.set_json(cache_key, analysis.dict(), 30)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing dark pool data for {symbol}: {str(e)}")
            raise

    async def _get_dark_pool_trades(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[DarkPoolTrade]:
        """Get dark pool trades from various venues."""
        try:
            trades = []
            
            # Get trades from each dark pool venue
            venues = ["IEX", "SIGMA X", "UBS MTF", "LIQUIDNET"]  # Example venues
            
            for venue in venues:
                venue_trades = await self.market_data.get_dark_pool_trades(
                    symbol=symbol,
                    venue=venue,
                    start_time=start_time,
                    end_time=end_time
                )
                
                for trade in venue_trades:
                    dark_trade = DarkPoolTrade(
                        timestamp=trade['timestamp'],
                        symbol=symbol,
                        price=float(trade['price']),
                        volume=float(trade['volume']),
                        venue=venue,
                        trade_id=trade['id'],
                        is_block=trade['volume'] >= self.BLOCK_TRADE_THRESHOLD,
                        metadata={
                            "condition": trade.get('condition'),
                            "flags": trade.get('flags')
                        }
                    )
                    trades.append(dark_trade)
            
            return sorted(trades, key=lambda x: x.timestamp)
            
        except Exception as e:
            logger.error(f"Error getting dark pool trades: {str(e)}")
            raise

    def _analyze_venues(self, trades_df: pd.DataFrame) -> List[DarkPoolVenue]:
        """Analyze trading activity by venue."""
        try:
            venues = []
            total_volume = trades_df['volume'].sum()
            
            grouped = trades_df.groupby('venue').agg({
                'volume': ['sum', 'count', 'mean'],
                'price': 'mean',
                'is_block': 'sum'
            })
            
            for venue, stats in grouped.iterrows():
                venue_volume = stats['volume']['sum']
                trade_count = stats['volume']['count']
                block_count = stats['is_block']['sum']
                
                venue_info = DarkPoolVenue(
                    name=venue,
                    volume=float(venue_volume),
                    trade_count=int(trade_count),
                    avg_trade_size=float(stats['volume']['mean']),
                    market_share=float(venue_volume / total_volume),
                    block_ratio=float(block_count / trade_count),
                    avg_price=float(stats['price']['mean']),
                    timestamp=datetime.utcnow()
                )
                venues.append(venue_info)
            
            return sorted(
                venues,
                key=lambda x: x.volume,
                reverse=True
            )
            
        except Exception as e:
            logger.error(f"Error analyzing venues: {str(e)}")
            raise

    def _analyze_price_levels(
        self,
        trades_df: pd.DataFrame
    ) -> Tuple[List[PriceLevel], List[float]]:
        """Analyze trading activity at different price levels."""
        try:
            levels = []
            total_volume = trades_df['volume'].sum()
            
            # Group trades by price
            grouped = trades_df.groupby('price').agg({
                'volume': ['sum', 'count'],
                'timestamp': 'max',
                'venue': list
            })
            
            for price, stats in grouped.iterrows():
                volume = stats['volume']['sum']
                
                # Calculate venue breakdown
                venues = stats['venue']['list']
                venue_volumes = defaultdict(float)
                for venue, vol in zip(venues, trades_df[
                    trades_df['price'] == price
                ]['volume']):
                    venue_volumes[venue] += vol
                
                is_significant = volume >= (
                    total_volume * self.SIGNIFICANT_LEVEL_THRESHOLD
                )
                
                level = PriceLevel(
                    price=float(price),
                    volume=float(volume),
                    trade_count=int(stats['volume']['count']),
                    last_trade=stats['timestamp']['max'],
                    venue_breakdown={
                        k: float(v) for k, v in venue_volumes.items()
                    },
                    is_significant=is_significant
                )
                levels.append(level)
            
            # Sort by volume and keep top levels
            levels = sorted(
                levels,
                key=lambda x: x.volume,
                reverse=True
            )[:self.MAX_PRICE_LEVELS]
            
            # Get significant price levels
            significant_levels = [
                level.price for level in levels
                if level.is_significant
            ]
            
            return levels, significant_levels
            
        except Exception as e:
            logger.error(f"Error analyzing price levels: {str(e)}")
            raise

    def _calculate_volume_distribution(
        self,
        trades_df: pd.DataFrame,
        timeframe: TimeFrame
    ) -> Dict[str, float]:
        """Calculate volume distribution over time."""
        try:
            if trades_df.empty:
                return {}
            
            # Set time bucket based on timeframe
            if timeframe == TimeFrame.MINUTE:
                bucket = '1min'
            elif timeframe == TimeFrame.FIVE_MINUTES:
                bucket = '5min'
            elif timeframe == TimeFrame.FIFTEEN_MINUTES:
                bucket = '15min'
            elif timeframe == TimeFrame.HOUR:
                bucket = '1H'
            else:
                bucket = '1D'
            
            # Resample and calculate volume
            volume_series = trades_df.set_index('timestamp')['volume'].resample(
                bucket
            ).sum()
            
            # Convert to dictionary
            return {
                k.isoformat(): float(v)
                for k, v in volume_series.items()
                if pd.notna(v)
            }
            
        except Exception as e:
            logger.error(f"Error calculating volume distribution: {str(e)}")
            raise

    async def get_real_time_dark_pool(
        self,
        symbol: str,
        window_minutes: int = 5
    ) -> DarkPoolAnalysis:
        """Get real-time dark pool analysis for last N minutes."""
        try:
            analysis = await self.get_dark_pool_analysis(
                symbol=symbol,
                timeframe=TimeFrame.MINUTE,
                lookback_minutes=window_minutes
            )
            
            return analysis
            
        except Exception as e:
            logger.error(
                f"Error getting real-time dark pool data for {symbol}: {str(e)}"
            )
            raise

# Global dark pool service instance
dark_pool_service = DarkPoolService()
