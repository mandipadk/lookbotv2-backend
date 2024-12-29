import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

from app.services.market_data import market_data_service
from app.models.technical import TimeFrame, VolumeProfile
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

class VolumeAnalysisService:
    def __init__(self):
        self.market_data = market_data_service

    async def get_volume_profile(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        num_bins: int = 50,
        value_area_pct: float = 0.68  # 68% for 1 standard deviation
    ) -> VolumeProfile:
        """Calculate volume profile for a given symbol and time range."""
        try:
            # Try to get from cache
            cache_key = f"volume_profile:{symbol}:{timeframe}:{start_date}:{end_date}:{num_bins}"
            cached_data = await redis_client.get_json(cache_key)
            if cached_data:
                return VolumeProfile(**cached_data)

            # Get historical data
            data = await self.market_data.get_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            if data.empty:
                raise ValueError(f"No data available for {symbol}")

            # Calculate price levels and volume distribution
            price_levels, volume_at_price = self._calculate_volume_distribution(
                data=data,
                num_bins=num_bins
            )
            
            # Calculate value area
            vah, val, poc = self._calculate_value_area(
                price_levels=price_levels,
                volume_at_price=volume_at_price,
                value_area_pct=value_area_pct
            )
            
            # Create volume profile
            profile = VolumeProfile(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=end_date,
                price_levels=price_levels.tolist(),
                volume_at_price={str(k): float(v) for k, v in volume_at_price.items()},
                value_area_high=float(vah),
                value_area_low=float(val),
                point_of_control=float(poc),
                metadata={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "num_bins": num_bins,
                    "value_area_pct": value_area_pct
                }
            )
            
            # Cache for 5 minutes
            await redis_client.set_json(cache_key, profile.dict(), 300)
            
            return profile
            
        except Exception as e:
            logger.error(f"Error calculating volume profile for {symbol}: {str(e)}")
            raise

    def _calculate_volume_distribution(
        self,
        data: pd.DataFrame,
        num_bins: int
    ) -> Tuple[np.ndarray, Dict[float, float]]:
        """Calculate volume distribution across price levels."""
        try:
            # Calculate price levels
            price_range = data['high'].max() - data['low'].min()
            bin_size = price_range / num_bins
            price_levels = np.linspace(
                data['low'].min(),
                data['high'].max(),
                num_bins
            )
            
            # Initialize volume distribution
            volume_at_price = {}
            
            # Calculate volume for each price level
            for i in range(len(data)):
                row = data.iloc[i]
                price_range_in_bar = np.arange(
                    row['low'],
                    row['high'] + bin_size,
                    bin_size
                )
                volume_per_level = row['volume'] / len(price_range_in_bar)
                
                for price in price_range_in_bar:
                    rounded_price = round(price, 4)
                    if rounded_price in volume_at_price:
                        volume_at_price[rounded_price] += volume_per_level
                    else:
                        volume_at_price[rounded_price] = volume_per_level
            
            return price_levels, volume_at_price
            
        except Exception as e:
            logger.error(f"Error calculating volume distribution: {str(e)}")
            raise

    def _calculate_value_area(
        self,
        price_levels: np.ndarray,
        volume_at_price: Dict[float, float],
        value_area_pct: float
    ) -> Tuple[float, float, float]:
        """Calculate Value Area High, Value Area Low, and Point of Control."""
        try:
            # Find Point of Control (price level with highest volume)
            poc = max(volume_at_price.keys(), key=lambda k: volume_at_price[k])
            
            # Calculate total volume
            total_volume = sum(volume_at_price.values())
            target_volume = total_volume * value_area_pct
            
            # Initialize value area
            cumulative_volume = volume_at_price[poc]
            vah = poc
            val = poc
            
            # Expand value area until target volume is reached
            while cumulative_volume < target_volume:
                # Get next prices above and below current value area
                prices_above = [p for p in price_levels if p > vah]
                prices_below = [p for p in price_levels if p < val]
                
                if not prices_above and not prices_below:
                    break
                
                # Get volumes at next levels
                vol_above = volume_at_price.get(
                    min(prices_above, default=vah),
                    0
                )
                vol_below = volume_at_price.get(
                    max(prices_below, default=val),
                    0
                )
                
                # Add level with higher volume to value area
                if vol_above > vol_below and prices_above:
                    vah = min(prices_above)
                    cumulative_volume += vol_above
                elif prices_below:
                    val = max(prices_below)
                    cumulative_volume += vol_below
                else:
                    break
            
            return vah, val, poc
            
        except Exception as e:
            logger.error(f"Error calculating value area: {str(e)}")
            raise

    async def get_volume_analysis(
        self,
        symbol: str,
        timeframe: TimeFrame,
        lookback_periods: int = 100
    ) -> Dict:
        """Get comprehensive volume analysis."""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=lookback_periods)
            
            # Get volume profile
            profile = await self.get_volume_profile(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            # Get historical data
            data = await self.market_data.get_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            # Calculate volume metrics
            metrics = {
                "avg_volume": float(data['volume'].mean()),
                "std_volume": float(data['volume'].std()),
                "volume_trend": self._calculate_volume_trend(data),
                "relative_volume": float(
                    data['volume'].iloc[-1] / data['volume'].mean()
                ),
                "volume_profile": profile.dict(),
                "price_volume_correlation": float(
                    data['close'].corr(data['volume'])
                )
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting volume analysis for {symbol}: {str(e)}")
            raise

    def _calculate_volume_trend(self, data: pd.DataFrame) -> str:
        """Calculate volume trend using linear regression."""
        try:
            # Calculate volume moving average
            volume_ma = data['volume'].rolling(window=20).mean()
            
            # Calculate linear regression
            x = np.arange(len(volume_ma.dropna()))
            y = volume_ma.dropna().values
            slope, _ = np.polyfit(x, y, 1)
            
            # Determine trend
            if slope > 0:
                return "increasing"
            elif slope < 0:
                return "decreasing"
            else:
                return "neutral"
                
        except Exception as e:
            logger.error(f"Error calculating volume trend: {str(e)}")
            raise

# Global volume analysis service instance
volume_analysis_service = VolumeAnalysisService()
