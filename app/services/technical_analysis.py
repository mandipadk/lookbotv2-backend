from typing import List, Dict, Optional, Union, Tuple
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import talib
import logging
from uuid import UUID

from app.services.market_data import market_data_service
from app.core.redis import redis_client
from app.models.technical import (
    TechnicalIndicator,
    Pattern,
    Signal,
    SignalStrength,
    TimeFrame,
    TrendDirection
)

logger = logging.getLogger(__name__)

class TechnicalAnalysisService:
    def __init__(self):
        self._pattern_functions = {
            Pattern.DOJI: talib.CDLDOJI,
            Pattern.HAMMER: talib.CDLHAMMER,
            Pattern.SHOOTING_STAR: talib.CDLSHOOTINGSTAR,
            Pattern.ENGULFING: talib.CDLENGULFING,
            Pattern.MORNING_STAR: talib.CDLMORNINGSTAR,
            Pattern.EVENING_STAR: talib.CDLEVENINGSTAR,
            Pattern.THREE_WHITE_SOLDIERS: talib.CDL3WHITESOLDIERS,
            Pattern.THREE_BLACK_CROWS: talib.CDL3BLACKCROWS,
            Pattern.DRAGONFLY_DOJI: talib.CDLDRAGONFLYDOJI,
            Pattern.GRAVESTONE_DOJI: talib.CDLGRAVESTONEDOJI
        }

    async def get_technical_indicators(
        self,
        symbol: str,
        timeframe: TimeFrame = TimeFrame.DAILY,
        lookback_periods: int = 100
    ) -> Dict[str, Union[float, str]]:
        """Calculate technical indicators for a symbol."""
        try:
            # Get historical data
            data = await self._get_historical_data(symbol, timeframe, lookback_periods)
            if data.empty:
                return {}

            # Calculate indicators
            indicators = {
                # Trend Indicators
                "sma_20": self._calculate_sma(data, 20),
                "sma_50": self._calculate_sma(data, 50),
                "sma_200": self._calculate_sma(data, 200),
                "ema_12": self._calculate_ema(data, 12),
                "ema_26": self._calculate_ema(data, 26),
                "macd": self._calculate_macd(data),
                "adx": self._calculate_adx(data),
                
                # Momentum Indicators
                "rsi": self._calculate_rsi(data),
                "stoch": self._calculate_stochastic(data),
                "cci": self._calculate_cci(data),
                "williams_r": self._calculate_williams_r(data),
                
                # Volume Indicators
                "obv": self._calculate_obv(data),
                "mfi": self._calculate_mfi(data),
                "vwap": self._calculate_vwap(data),
                
                # Volatility Indicators
                "bollinger_bands": self._calculate_bollinger_bands(data),
                "atr": self._calculate_atr(data),
                
                # Trend Direction
                "trend": self._determine_trend(data),
                
                # Support/Resistance
                "support_resistance": self._calculate_support_resistance(data)
            }
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators for {symbol}: {str(e)}")
            return {}

    async def get_patterns(
        self,
        symbol: str,
        timeframe: TimeFrame = TimeFrame.DAILY,
        lookback_periods: int = 100
    ) -> List[Dict[str, Union[str, datetime, float]]]:
        """Detect candlestick patterns."""
        try:
            # Get historical data
            data = await self._get_historical_data(symbol, timeframe, lookback_periods)
            if data.empty:
                return []

            patterns = []
            for pattern_name, pattern_func in self._pattern_functions.items():
                # Calculate pattern
                pattern_values = pattern_func(
                    data['open'].values,
                    data['high'].values,
                    data['low'].values,
                    data['close'].values
                )
                
                # Find where pattern occurs
                pattern_dates = data.index[pattern_values != 0]
                pattern_signals = pattern_values[pattern_values != 0]
                
                for date, signal in zip(pattern_dates, pattern_signals):
                    patterns.append({
                        "pattern": pattern_name,
                        "date": date,
                        "signal": "bullish" if signal > 0 else "bearish",
                        "strength": abs(signal)
                    })
            
            return sorted(patterns, key=lambda x: x['date'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error detecting patterns for {symbol}: {str(e)}")
            return []

    async def get_signals(
        self,
        symbol: str,
        timeframe: TimeFrame = TimeFrame.DAILY
    ) -> List[Signal]:
        """Generate trading signals based on technical analysis."""
        try:
            # Get indicators
            indicators = await self.get_technical_indicators(symbol, timeframe)
            if not indicators:
                return []

            signals = []
            
            # Trend Signals
            if self._is_golden_cross(indicators):
                signals.append(Signal(
                    type="GOLDEN_CROSS",
                    direction=TrendDirection.BULLISH,
                    strength=SignalStrength.STRONG,
                    timeframe=timeframe
                ))
                
            if self._is_death_cross(indicators):
                signals.append(Signal(
                    type="DEATH_CROSS",
                    direction=TrendDirection.BEARISH,
                    strength=SignalStrength.STRONG,
                    timeframe=timeframe
                ))

            # Momentum Signals
            if self._is_oversold(indicators):
                signals.append(Signal(
                    type="OVERSOLD",
                    direction=TrendDirection.BULLISH,
                    strength=SignalStrength.MEDIUM,
                    timeframe=timeframe
                ))
                
            if self._is_overbought(indicators):
                signals.append(Signal(
                    type="OVERBOUGHT",
                    direction=TrendDirection.BEARISH,
                    strength=SignalStrength.MEDIUM,
                    timeframe=timeframe
                ))

            # MACD Signals
            macd_signal = self._get_macd_signal(indicators)
            if macd_signal:
                signals.append(macd_signal)

            # Volume Signals
            volume_signal = self._get_volume_signal(indicators)
            if volume_signal:
                signals.append(volume_signal)

            # Bollinger Band Signals
            bb_signal = self._get_bollinger_signal(indicators)
            if bb_signal:
                signals.append(bb_signal)

            return signals
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {str(e)}")
            return []

    async def _get_historical_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        lookback_periods: int
    ) -> pd.DataFrame:
        """Get historical price data for technical analysis."""
        try:
            # Try to get from cache
            cache_key = f"ta_data:{symbol}:{timeframe}:{lookback_periods}"
            cached_data = await redis_client.get_json(cache_key)
            if cached_data:
                return pd.DataFrame(cached_data)

            # Get from market data service
            data = await market_data_service.get_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                limit=lookback_periods
            )
            
            # Cache for 5 minutes
            await redis_client.set_json(cache_key, data.to_dict(), 300)
            
            return data
            
        except Exception as e:
            logger.error(f"Error getting historical data: {str(e)}")
            return pd.DataFrame()

    def _calculate_sma(self, data: pd.DataFrame, period: int) -> float:
        """Calculate Simple Moving Average."""
        try:
            return talib.SMA(data['close'].values, timeperiod=period)[-1]
        except:
            return 0.0

    def _calculate_ema(self, data: pd.DataFrame, period: int) -> float:
        """Calculate Exponential Moving Average."""
        try:
            return talib.EMA(data['close'].values, timeperiod=period)[-1]
        except:
            return 0.0

    def _calculate_macd(
        self,
        data: pd.DataFrame,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, float]:
        """Calculate MACD indicator."""
        try:
            macd, signal, hist = talib.MACD(
                data['close'].values,
                fastperiod=fast_period,
                slowperiod=slow_period,
                signalperiod=signal_period
            )
            return {
                "macd": macd[-1],
                "signal": signal[-1],
                "histogram": hist[-1]
            }
        except:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

    def _calculate_rsi(
        self,
        data: pd.DataFrame,
        period: int = 14
    ) -> float:
        """Calculate Relative Strength Index."""
        try:
            return talib.RSI(data['close'].values, timeperiod=period)[-1]
        except:
            return 0.0

    def _calculate_stochastic(
        self,
        data: pd.DataFrame,
        k_period: int = 14,
        d_period: int = 3,
        slowing: int = 3
    ) -> Dict[str, float]:
        """Calculate Stochastic Oscillator."""
        try:
            k, d = talib.STOCH(
                data['high'].values,
                data['low'].values,
                data['close'].values,
                fastk_period=k_period,
                slowk_period=slowing,
                slowk_matype=0,
                slowd_period=d_period,
                slowd_matype=0
            )
            return {"k": k[-1], "d": d[-1]}
        except:
            return {"k": 0.0, "d": 0.0}

    def _calculate_cci(
        self,
        data: pd.DataFrame,
        period: int = 20
    ) -> float:
        """Calculate Commodity Channel Index."""
        try:
            return talib.CCI(
                data['high'].values,
                data['low'].values,
                data['close'].values,
                timeperiod=period
            )[-1]
        except:
            return 0.0

    def _calculate_williams_r(
        self,
        data: pd.DataFrame,
        period: int = 14
    ) -> float:
        """Calculate Williams %R."""
        try:
            return talib.WILLR(
                data['high'].values,
                data['low'].values,
                data['close'].values,
                timeperiod=period
            )[-1]
        except:
            return 0.0

    def _calculate_obv(self, data: pd.DataFrame) -> float:
        """Calculate On Balance Volume."""
        try:
            return talib.OBV(
                data['close'].values,
                data['volume'].values
            )[-1]
        except:
            return 0.0

    def _calculate_mfi(
        self,
        data: pd.DataFrame,
        period: int = 14
    ) -> float:
        """Calculate Money Flow Index."""
        try:
            return talib.MFI(
                data['high'].values,
                data['low'].values,
                data['close'].values,
                data['volume'].values,
                timeperiod=period
            )[-1]
        except:
            return 0.0

    def _calculate_vwap(self, data: pd.DataFrame) -> float:
        """Calculate Volume Weighted Average Price."""
        try:
            typical_price = (data['high'] + data['low'] + data['close']) / 3
            return (typical_price * data['volume']).sum() / data['volume'].sum()
        except:
            return 0.0

    def _calculate_bollinger_bands(
        self,
        data: pd.DataFrame,
        period: int = 20,
        num_std: float = 2.0
    ) -> Dict[str, float]:
        """Calculate Bollinger Bands."""
        try:
            upper, middle, lower = talib.BBANDS(
                data['close'].values,
                timeperiod=period,
                nbdevup=num_std,
                nbdevdn=num_std,
                matype=0
            )
            return {
                "upper": upper[-1],
                "middle": middle[-1],
                "lower": lower[-1]
            }
        except:
            return {"upper": 0.0, "middle": 0.0, "lower": 0.0}

    def _calculate_atr(
        self,
        data: pd.DataFrame,
        period: int = 14
    ) -> float:
        """Calculate Average True Range."""
        try:
            return talib.ATR(
                data['high'].values,
                data['low'].values,
                data['close'].values,
                timeperiod=period
            )[-1]
        except:
            return 0.0

    def _determine_trend(
        self,
        data: pd.DataFrame,
        short_period: int = 20,
        long_period: int = 50
    ) -> str:
        """Determine trend direction."""
        try:
            sma_short = self._calculate_sma(data, short_period)
            sma_long = self._calculate_sma(data, long_period)
            current_price = data['close'].iloc[-1]
            
            if current_price > sma_short > sma_long:
                return TrendDirection.BULLISH
            elif current_price < sma_short < sma_long:
                return TrendDirection.BEARISH
            else:
                return TrendDirection.SIDEWAYS
        except:
            return TrendDirection.SIDEWAYS

    def _calculate_support_resistance(
        self,
        data: pd.DataFrame,
        window: int = 20
    ) -> Dict[str, float]:
        """Calculate support and resistance levels."""
        try:
            window_data = data.tail(window)
            
            support = window_data['low'].min()
            resistance = window_data['high'].max()
            
            return {
                "support": support,
                "resistance": resistance
            }
        except:
            return {"support": 0.0, "resistance": 0.0}

    def _is_golden_cross(self, indicators: Dict) -> bool:
        """Check for golden cross pattern."""
        try:
            return (
                indicators['sma_50'] > indicators['sma_200'] and
                indicators['sma_20'] > indicators['sma_50']
            )
        except:
            return False

    def _is_death_cross(self, indicators: Dict) -> bool:
        """Check for death cross pattern."""
        try:
            return (
                indicators['sma_50'] < indicators['sma_200'] and
                indicators['sma_20'] < indicators['sma_50']
            )
        except:
            return False

    def _is_oversold(self, indicators: Dict) -> bool:
        """Check if asset is oversold."""
        try:
            return (
                indicators['rsi'] < 30 or
                indicators['stoch']['k'] < 20 or
                indicators['williams_r'] < -80
            )
        except:
            return False

    def _is_overbought(self, indicators: Dict) -> bool:
        """Check if asset is overbought."""
        try:
            return (
                indicators['rsi'] > 70 or
                indicators['stoch']['k'] > 80 or
                indicators['williams_r'] > -20
            )
        except:
            return False

    def _get_macd_signal(self, indicators: Dict) -> Optional[Signal]:
        """Generate MACD-based signal."""
        try:
            macd = indicators['macd']
            if macd['histogram'] > 0 and macd['macd'] > macd['signal']:
                return Signal(
                    type="MACD_BULLISH",
                    direction=TrendDirection.BULLISH,
                    strength=SignalStrength.MEDIUM,
                    timeframe=TimeFrame.DAILY
                )
            elif macd['histogram'] < 0 and macd['macd'] < macd['signal']:
                return Signal(
                    type="MACD_BEARISH",
                    direction=TrendDirection.BEARISH,
                    strength=SignalStrength.MEDIUM,
                    timeframe=TimeFrame.DAILY
                )
            return None
        except:
            return None

    def _get_volume_signal(self, indicators: Dict) -> Optional[Signal]:
        """Generate volume-based signal."""
        try:
            if indicators['mfi'] < 20:
                return Signal(
                    type="VOLUME_BULLISH",
                    direction=TrendDirection.BULLISH,
                    strength=SignalStrength.STRONG,
                    timeframe=TimeFrame.DAILY
                )
            elif indicators['mfi'] > 80:
                return Signal(
                    type="VOLUME_BEARISH",
                    direction=TrendDirection.BEARISH,
                    strength=SignalStrength.STRONG,
                    timeframe=TimeFrame.DAILY
                )
            return None
        except:
            return None

    def _get_bollinger_signal(self, indicators: Dict) -> Optional[Signal]:
        """Generate Bollinger Bands-based signal."""
        try:
            bb = indicators['bollinger_bands']
            current_price = indicators.get('close', 0)
            
            if current_price < bb['lower']:
                return Signal(
                    type="BB_OVERSOLD",
                    direction=TrendDirection.BULLISH,
                    strength=SignalStrength.MEDIUM,
                    timeframe=TimeFrame.DAILY
                )
            elif current_price > bb['upper']:
                return Signal(
                    type="BB_OVERBOUGHT",
                    direction=TrendDirection.BEARISH,
                    strength=SignalStrength.MEDIUM,
                    timeframe=TimeFrame.DAILY
                )
            return None
        except:
            return None

# Global technical analysis service instance
technical_analysis_service = TechnicalAnalysisService()
