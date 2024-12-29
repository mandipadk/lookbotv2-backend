from dataclasses import dataclass
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

from app.models.technical import (
    TimeFrame,
    VolumeProfile,
    OrderFlowTrade,
    OrderFlowImbalance,
    OrderFlowAnalysis,
    LiquidityAnalysis,
    DarkPoolAnalysis,
    DarkPoolTrade,
    OptionsFlowAnalysis,
    OptionFlow,
    TrendAnalysis,
    TrendDirection,
    SignalStrength
)
from app.services.market_data import market_data_service

@dataclass
class TechnicalService:
    """Service for technical analysis."""
    
    async def get_volume_profile(
        self,
        symbol: str,
        timeframe: TimeFrame
    ) -> VolumeProfile:
        """Get volume profile analysis."""
        data = await market_data_service.get_historical_data(
            symbol=symbol,
            timeframe=timeframe
        )
        
        if not data:
            raise ValueError(f"No historical data available for {symbol}")
        
        # Extract prices and volumes from historical data
        prices = [d['close'] for d in data]
        volumes = [d['volume'] for d in data]
        
        # Calculate volume profile
        hist, bin_edges = np.histogram(
            prices,
            bins=50,
            weights=volumes
        )
        
        # Find value area (70% of volume)
        total_volume = sum(volumes)
        value_area_volume = 0.7 * total_volume
        
        # Calculate value area high and low
        cumsum = np.cumsum(hist)
        value_area_idx = np.where(cumsum >= value_area_volume)[0][0]
        value_area_high = bin_edges[value_area_idx + 1]
        value_area_low = bin_edges[max(0, value_area_idx - 1)]
        
        return VolumeProfile(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=datetime.now(),
            price_levels=bin_edges[:-1].tolist(),  # Remove last edge
            volume_at_price={
                str(price): vol for price, vol in zip(bin_edges[:-1], hist)
            },
            value_area_high=value_area_high,
            value_area_low=value_area_low,
            point_of_control=bin_edges[np.argmax(hist)]
        )
    
    async def get_order_flow_analysis(
        self,
        symbol: str,
        timeframe: TimeFrame
    ) -> OrderFlowAnalysis:
        """Get order flow analysis."""
        trades = await market_data_service.get_trades(
            symbol=symbol,
            timeframe=timeframe
        )
        
        # Calculate buy/sell volumes
        buy_volume = sum(t['volume'] for t in trades if t['side'] == 'buy')
        sell_volume = sum(t['volume'] for t in trades if t['side'] == 'sell')
        total_volume = buy_volume + sell_volume
        
        return OrderFlowAnalysis(
            symbol=symbol,
            trades=[
                OrderFlowTrade(
                    price=t['price'],
                    volume=t['volume'],
                    timestamp=t['timestamp'],
                    side=t['side']
                )
                for t in trades
            ],
            imbalances=[],  # Calculate imbalances
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            net_flow_ratio=(buy_volume - sell_volume) / total_volume
            if total_volume > 0 else 0
        )
    
    async def get_liquidity_analysis(
        self,
        symbol: str,
        timeframe: TimeFrame
    ) -> LiquidityAnalysis:
        """Get liquidity analysis."""
        order_book = await market_data_service.get_order_book(symbol)
        
        total_bid_volume = sum(vol for _, vol in order_book['bids'])
        total_ask_volume = sum(vol for _, vol in order_book['asks'])
        total_liquidity = total_bid_volume + total_ask_volume
        
        # Calculate depth imbalance
        depth_imbalance = (total_bid_volume - total_ask_volume) / total_liquidity if total_liquidity > 0 else 0
        
        # Calculate liquidity score (0-100)
        # Based on total liquidity and spread
        spread = order_book['asks'][0][0] - order_book['bids'][0][0]
        normalized_spread = min(1.0, spread / order_book['bids'][0][0])  # Normalize spread as percentage
        liquidity_score = (1 - normalized_spread) * 100 * (total_liquidity / 1000000)  # Scale by volume
        liquidity_score = max(0, min(100, liquidity_score))  # Clamp between 0-100
        
        # Calculate resiliency score (0-100)
        # Based on order book depth and balance
        resiliency_score = (1 - abs(depth_imbalance)) * 100  # Higher score for balanced books
        
        return LiquidityAnalysis(
            symbol=symbol,
            timestamp=datetime.now(),
            timeframe=timeframe,
            liquidity_levels=[],  # Calculate liquidity levels
            total_liquidity=total_liquidity,
            bid_ask_spread=spread,
            depth_imbalance=depth_imbalance,
            liquidity_score=liquidity_score,
            resiliency_score=resiliency_score
        )
    
    async def get_dark_pool_analysis(
        self,
        symbol: str,
        timeframe: TimeFrame
    ) -> DarkPoolAnalysis:
        """Get dark pool analysis."""
        trades = await market_data_service.get_dark_pool_trades(
            symbol=symbol,
            timeframe=timeframe
        )
        
        total_volume = sum(t['volume'] for t in trades)
        block_volume = sum(
            t['volume'] for t in trades
            if t['volume'] >= 10000  # Block trade threshold
        )
        
        # Convert trades to DarkPoolTrade objects
        recent_trades = [
            DarkPoolTrade(
                timestamp=t['timestamp'],
                symbol=symbol,
                price=t['price'],
                volume=t['volume'],
                venue=t['venue'],
                trade_id=t.get('trade_id', ''),
                is_block=t['volume'] >= 10000
            )
            for t in trades
        ]
        
        return DarkPoolAnalysis(
            symbol=symbol,
            timestamp=datetime.now(),
            timeframe=timeframe,
            total_volume=total_volume,
            total_trades=len(trades),
            recent_trades=recent_trades,
            block_volume_ratio=block_volume / total_volume if total_volume > 0 else 0,
            venues=[],  # Calculate venue statistics
            price_levels=[]  # Calculate price levels
        )
    
    async def get_options_flow_analysis(
        self,
        symbol: str,
        timeframe: TimeFrame
    ) -> OptionsFlowAnalysis:
        """Get options flow analysis."""
        flows = await market_data_service.get_options_flow(
            symbol=symbol,
            timeframe=timeframe
        )
        
        total_volume = sum(f['volume'] for f in flows)
        bullish_volume = sum(
            f['volume'] for f in flows
            if f['type'] in ['call_buy', 'put_sell']
        )
        bearish_volume = sum(
            f['volume'] for f in flows
            if f['type'] in ['call_sell', 'put_buy']
        )
        
        # Calculate ratios
        bullish_flow_ratio = bullish_volume / total_volume if total_volume > 0 else 0
        bearish_flow_ratio = bearish_volume / total_volume if total_volume > 0 else 0
        
        # Calculate smart money indicator (-1 to 1)
        # Positive values indicate smart money is bullish
        smart_money_indicator = (bullish_flow_ratio - bearish_flow_ratio)
        
        # Convert flows to OptionFlow objects
        recent_flows = [
            OptionFlow(
                timestamp=f['timestamp'],
                contract=f['contract'],
                side=f['side'],
                size=f['volume'],
                premium=f['premium'],
                is_sweep=f.get('is_sweep', False),
                is_block=f['volume'] >= 100,  # Block trade threshold for options
                sentiment='bullish' if f['type'] in ['call_buy', 'put_sell'] else 'bearish',
                execution_type='sweep' if f.get('is_sweep', False) else 'regular'
            )
            for f in flows
        ]
        
        return OptionsFlowAnalysis(
            symbol=symbol,
            timestamp=datetime.now(),
            underlying_price=await market_data_service.get_current_price(symbol),
            total_volume=total_volume,
            total_open_interest=sum(f.get('open_interest', 0) for f in flows),
            put_call_ratio=sum(f['volume'] for f in flows if f['type'].startswith('put')) / 
                         (sum(f['volume'] for f in flows if f['type'].startswith('call')) or 1),
            recent_flows=recent_flows,
            bullish_flow_ratio=bullish_flow_ratio,
            bearish_flow_ratio=bearish_flow_ratio,
            smart_money_indicator=smart_money_indicator,
            unusual_activity=[],  # Calculate unusual activity
            expiries=[]  # Calculate expiry analysis
        )

    async def calculate_sma(
        self,
        symbol: str,
        timeframe: TimeFrame,
        period: int
    ) -> List[float]:
        """Calculate Simple Moving Average."""
        data = await market_data_service.get_historical_data(
            symbol=symbol,
            timeframe=timeframe
        )
        
        prices = pd.Series([d['close'] for d in data])
        return prices.rolling(window=period).mean().tolist()
    
    async def calculate_rsi(
        self,
        symbol: str,
        timeframe: TimeFrame,
        period: int = 14
    ) -> float:
        """Calculate Relative Strength Index."""
        data = await market_data_service.get_historical_data(
            symbol=symbol,
            timeframe=timeframe
        )
        
        if not data:
            raise ValueError(f"No historical data available for {symbol}")
        
        # Convert to pandas Series
        prices = pd.Series([d['close'] for d in data])
        
        # Calculate price changes
        price_change = prices.diff()
        
        # Get gains and losses
        gains = price_change.copy()
        losses = price_change.copy()
        gains[gains < 0] = 0
        losses[losses > 0] = 0
        losses = abs(losses)
        
        # Calculate average gains and losses
        avg_gains = gains.rolling(window=period).mean()
        avg_losses = losses.rolling(window=period).mean()
        
        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]  # Return latest RSI value

    async def calculate_macd(
        self,
        symbol: str,
        timeframe: TimeFrame,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, List[float]]:
        """Calculate MACD."""
        data = await market_data_service.get_historical_data(
            symbol=symbol,
            timeframe=timeframe
        )
        
        prices = pd.Series([d['close'] for d in data])
        
        # Calculate MACD
        exp1 = prices.ewm(span=fast_period, adjust=False).mean()
        exp2 = prices.ewm(span=slow_period, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=signal_period, adjust=False).mean()
        histogram = macd - signal
        
        return {
            'macd': macd.tolist(),
            'signal': signal.tolist(),
            'histogram': histogram.tolist()
        }
    
    async def detect_patterns(
        self,
        symbol: str,
        timeframe: TimeFrame
    ) -> List[Dict]:
        """Detect chart patterns."""
        data = await market_data_service.get_historical_data(
            symbol=symbol,
            timeframe=timeframe
        )
        
        # Implement pattern detection logic
        patterns = []
        
        return patterns
    
    async def analyze_trend(
        self,
        symbol: str,
        timeframe: TimeFrame
    ) -> TrendAnalysis:
        """Analyze price trend."""
        data = await market_data_service.get_historical_data(
            symbol=symbol,
            timeframe=timeframe
        )
        
        if not data:
            raise ValueError(f"No historical data available for {symbol}")
        
        # Convert data to pandas Series
        prices = pd.Series([d['close'] for d in data])
        timestamps = [datetime.fromisoformat(d['timestamp']) for d in data]
        
        # Calculate trend direction using SMA crossover
        sma_short = prices.rolling(window=10).mean()
        sma_long = prices.rolling(window=20).mean()
        
        if sma_short.iloc[-1] > sma_long.iloc[-1] and sma_short.iloc[-2] <= sma_long.iloc[-2]:
            direction = TrendDirection.BULLISH
        elif sma_short.iloc[-1] < sma_long.iloc[-1] and sma_short.iloc[-2] >= sma_long.iloc[-2]:
            direction = TrendDirection.BEARISH
        else:
            direction = TrendDirection.SIDEWAYS
        
        # Calculate trend strength using ADX
        high_prices = pd.Series([d['high'] for d in data])
        low_prices = pd.Series([d['low'] for d in data])
        
        # Calculate True Range
        tr1 = high_prices - low_prices
        tr2 = abs(high_prices - prices.shift(1))
        tr3 = abs(low_prices - prices.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        
        # Calculate trend strength based on ATR
        price_range = prices.max() - prices.min()
        strength_ratio = (atr.iloc[-1] / price_range) * 100
        
        if strength_ratio > 5:
            strength = SignalStrength.STRONG
        elif strength_ratio > 2:
            strength = SignalStrength.MEDIUM
        else:
            strength = SignalStrength.WEAK
        
        # Find support and resistance levels using local min/max
        window = 5  # Window size for local min/max
        support_levels = []
        resistance_levels = []
        
        for i in range(window, len(prices) - window):
            if all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
               all(prices[i] <= prices[i+j] for j in range(1, window+1)):
                support_levels.append(prices[i])
            elif all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
                 all(prices[i] >= prices[i+j] for j in range(1, window+1)):
                resistance_levels.append(prices[i])
        
        return TrendAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            strength=strength,
            start_timestamp=timestamps[0],
            current_timestamp=timestamps[-1],
            support_levels=sorted(set(support_levels))[-3:],  # Last 3 support levels
            resistance_levels=sorted(set(resistance_levels))[:3],  # First 3 resistance levels
            key_levels=sorted(set(support_levels + resistance_levels))
        )
    
    async def generate_signals(
        self,
        symbol: str,
        timeframe: TimeFrame
    ) -> List[Dict]:
        """Generate trading signals."""
        # Get technical indicators
        rsi = await self.calculate_rsi(symbol, timeframe)
        macd = await self.calculate_macd(symbol, timeframe)
        trend = await self.analyze_trend(symbol, timeframe)
        
        signals = []
        
        # Generate signals based on indicators
        if rsi < 30 and trend.direction == TrendDirection.BULLISH:
            signals.append({
                'type': 'buy',
                'confidence': 0.8,
                'price': 0.0,  # Set current price
                'stop_loss': 0.0,  # Calculate stop loss
                'take_profit': 0.0  # Calculate take profit
            })
        elif rsi > 70 and trend.direction == TrendDirection.BEARISH:
            signals.append({
                'type': 'sell',
                'confidence': 0.8,
                'price': 0.0,  # Set current price
                'stop_loss': 0.0,  # Calculate stop loss
                'take_profit': 0.0  # Calculate take profit
            })
        
        return signals
    
    async def get_technical_indicators(
        self,
        symbol: str,
        timeframe: TimeFrame
    ) -> Dict:
        """Get comprehensive technical indicators."""
        try:
            # Get historical data
            data = await market_data_service.get_historical_data(
                symbol=symbol,
                timeframe=timeframe
            )
            
            if not data:
                raise ValueError(f"No historical data available for {symbol}")
            
            # Convert to pandas Series
            prices = pd.Series([d['close'] for d in data])
            high_prices = pd.Series([d['high'] for d in data])
            low_prices = pd.Series([d['low'] for d in data])
            volumes = pd.Series([d['volume'] for d in data])
            
            # Calculate various technical indicators
            sma_20 = prices.rolling(window=20).mean().iloc[-1]
            sma_50 = prices.rolling(window=50).mean().iloc[-1]
            sma_200 = prices.rolling(window=200).mean().iloc[-1]
            
            ema_12 = prices.ewm(span=12, adjust=False).mean().iloc[-1]
            ema_26 = prices.ewm(span=26, adjust=False).mean().iloc[-1]
            
            # MACD
            macd_line = ema_12 - ema_26
            signal_line = pd.Series(macd_line).ewm(span=9, adjust=False).mean().iloc[-1]
            macd_histogram = macd_line - signal_line
            
            # RSI
            rsi = await self.calculate_rsi(symbol, timeframe)
            
            # Bollinger Bands
            bb_period = 20
            bb_std = 2
            bb_middle = prices.rolling(window=bb_period).mean()
            bb_std_dev = prices.rolling(window=bb_period).std()
            bb_upper = bb_middle + (bb_std * bb_std_dev)
            bb_lower = bb_middle - (bb_std * bb_std_dev)
            
            # Stochastic Oscillator
            stoch_period = 14
            low_min = low_prices.rolling(window=stoch_period).min()
            high_max = high_prices.rolling(window=stoch_period).max()
            k = 100 * (prices - low_min) / (high_max - low_min)
            d = k.rolling(window=3).mean()
            
            # Average True Range
            tr1 = high_prices - low_prices
            tr2 = abs(high_prices - prices.shift(1))
            tr3 = abs(low_prices - prices.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            
            # Volume indicators
            obv = (volumes * np.where(prices > prices.shift(1), 1, -1)).cumsum()
            vwap = (prices * volumes).cumsum() / volumes.cumsum()
            
            return {
                "moving_averages": {
                    "sma_20": sma_20,
                    "sma_50": sma_50,
                    "sma_200": sma_200,
                    "ema_12": ema_12,
                    "ema_26": ema_26
                },
                "momentum_indicators": {
                    "rsi": rsi,
                    "macd": {
                        "macd_line": macd_line,
                        "signal_line": signal_line,
                        "histogram": macd_histogram
                    },
                    "stochastic": {
                        "k": k.iloc[-1],
                        "d": d.iloc[-1]
                    }
                },
                "volatility_indicators": {
                    "bollinger_bands": {
                        "upper": bb_upper.iloc[-1],
                        "middle": bb_middle.iloc[-1],
                        "lower": bb_lower.iloc[-1]
                    },
                    "atr": atr
                },
                "volume_indicators": {
                    "obv": obv.iloc[-1],
                    "vwap": vwap.iloc[-1]
                }
            }
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {str(e)}")
            raise

    def _calculate_atr(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate Average True Range."""
        high = prices.rolling(window=2).max()
        low = prices.rolling(window=2).min()
        tr = high - low
        atr = tr.rolling(window=period).mean()
        return atr.iloc[-1]

# Create singleton instance
technical_service = TechnicalService()
