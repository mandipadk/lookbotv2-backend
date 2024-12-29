import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

from app.services.market_data import market_data_service
from app.models.technical import (
    TimeFrame,
    OrderFlowTrade,
    OrderFlowImbalance,
    OrderFlowAnalysis
)
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

class OrderFlowService:
    def __init__(self):
        self.market_data = market_data_service
        self.LARGE_TRADE_PERCENTILE = 90  # Define large trades as top 10%

    async def get_order_flow_analysis(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_time: datetime,
        end_time: datetime
    ) -> OrderFlowAnalysis:
        """Get complete order flow analysis for a symbol."""
        try:
            # Try to get from cache
            cache_key = f"order_flow:{symbol}:{timeframe}:{start_time}:{end_time}"
            cached_data = await redis_client.get_json(cache_key)
            if cached_data:
                return OrderFlowAnalysis(**cached_data)

            # Get trade data
            trades_data = await self.market_data.get_trades(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time
            )

            if trades_data.empty:
                raise ValueError(f"No trade data available for {symbol}")

            # Process trades
            trades = self._process_trades(trades_data)
            
            # Calculate imbalances
            imbalances = self._calculate_imbalances(trades_data)
            
            # Calculate metrics
            metrics = self._calculate_metrics(trades_data)
            
            # Create analysis
            analysis = OrderFlowAnalysis(
                symbol=symbol,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time,
                trades=trades,
                imbalances=imbalances,
                **metrics
            )
            
            # Cache for 1 minute (trade data updates frequently)
            await redis_client.set_json(cache_key, analysis.dict(), 60)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing order flow for {symbol}: {str(e)}")
            raise

    def _process_trades(self, trades_data: pd.DataFrame) -> List[OrderFlowTrade]:
        """Process raw trade data into OrderFlowTrade objects."""
        try:
            trades = []
            
            # Calculate large trade threshold
            volume_threshold = np.percentile(
                trades_data['volume'],
                self.LARGE_TRADE_PERCENTILE
            )
            
            for _, row in trades_data.iterrows():
                trade = OrderFlowTrade(
                    timestamp=row['timestamp'],
                    price=float(row['price']),
                    volume=float(row['volume']),
                    side=row['side'],
                    is_aggressive=row['is_aggressive'],
                    is_block_trade=row['volume'] >= volume_threshold,
                    metadata={
                        "exchange": row.get('exchange'),
                        "trade_id": row.get('trade_id')
                    }
                )
                trades.append(trade)
            
            return trades
            
        except Exception as e:
            logger.error(f"Error processing trades: {str(e)}")
            raise

    def _calculate_imbalances(
        self,
        trades_data: pd.DataFrame
    ) -> List[OrderFlowImbalance]:
        """Calculate order flow imbalances at each price level."""
        try:
            imbalances = []
            
            # Group trades by price level
            grouped = trades_data.groupby('price').agg({
                'volume': ['sum', 'count', 'mean', 'max'],
                'side': list,
                'timestamp': 'last'
            })
            
            for price, row in grouped.iterrows():
                # Calculate volumes by side
                sides = row['side']['list']
                volumes = trades_data[
                    trades_data['price'] == price
                ]['volume'].values
                buy_volume = sum(
                    vol for s, vol in zip(sides, volumes) if s == 'buy'
                )
                sell_volume = sum(
                    vol for s, vol in zip(sides, volumes) if s == 'sell'
                )
                
                # Calculate aggressive volumes
                aggressive_trades = trades_data[
                    (trades_data['price'] == price) &
                    (trades_data['is_aggressive'])
                ]
                aggressive_buy = sum(
                    aggressive_trades[
                        aggressive_trades['side'] == 'buy'
                    ]['volume']
                )
                aggressive_sell = sum(
                    aggressive_trades[
                        aggressive_trades['side'] == 'sell'
                    ]['volume']
                )
                
                imbalance = OrderFlowImbalance(
                    price_level=float(price),
                    buy_volume=float(buy_volume),
                    sell_volume=float(sell_volume),
                    net_volume=float(buy_volume - sell_volume),
                    trade_count=int(row['volume']['count']),
                    avg_trade_size=float(row['volume']['mean']),
                    max_trade_size=float(row['volume']['max']),
                    aggressive_buy_volume=float(aggressive_buy),
                    aggressive_sell_volume=float(aggressive_sell),
                    timestamp=row['timestamp']['last']
                )
                imbalances.append(imbalance)
            
            return sorted(imbalances, key=lambda x: x.price_level)
            
        except Exception as e:
            logger.error(f"Error calculating imbalances: {str(e)}")
            raise

    def _calculate_metrics(self, trades_data: pd.DataFrame) -> Dict:
        """Calculate overall order flow metrics."""
        try:
            # Calculate volume metrics
            total_volume = trades_data['volume'].sum()
            buy_volume = trades_data[
                trades_data['side'] == 'buy'
            ]['volume'].sum()
            sell_volume = trades_data[
                trades_data['side'] == 'sell'
            ]['volume'].sum()
            
            # Calculate aggressive trade metrics
            aggressive_trades = trades_data[trades_data['is_aggressive']]
            aggressive_buy = aggressive_trades[
                aggressive_trades['side'] == 'buy'
            ]['volume'].sum()
            aggressive_sell = aggressive_trades[
                aggressive_trades['side'] == 'sell'
            ]['volume'].sum()
            
            # Calculate block trade metrics
            volume_threshold = np.percentile(
                trades_data['volume'],
                self.LARGE_TRADE_PERCENTILE
            )
            block_trades = trades_data[
                trades_data['volume'] >= volume_threshold
            ]
            
            metrics = {
                "cumulative_volume_delta": float(buy_volume - sell_volume),
                "buy_volume_ratio": float(buy_volume / total_volume),
                "sell_volume_ratio": float(sell_volume / total_volume),
                "large_trade_threshold": float(volume_threshold),
                "block_trade_count": len(block_trades),
                "aggressive_buy_ratio": float(
                    aggressive_buy / buy_volume if buy_volume > 0 else 0
                ),
                "aggressive_sell_ratio": float(
                    aggressive_sell / sell_volume if sell_volume > 0 else 0
                )
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {str(e)}")
            raise

    async def get_real_time_flow(
        self,
        symbol: str,
        window_minutes: int = 5
    ) -> OrderFlowAnalysis:
        """Get real-time order flow analysis for last N minutes."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=window_minutes)
            
            analysis = await self.get_order_flow_analysis(
                symbol=symbol,
                timeframe=TimeFrame.MINUTE,
                start_time=start_time,
                end_time=end_time
            )
            
            return analysis
            
        except Exception as e:
            logger.error(
                f"Error getting real-time order flow for {symbol}: {str(e)}"
            )
            raise

# Global order flow service instance
order_flow_service = OrderFlowService()
