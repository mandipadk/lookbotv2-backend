from typing import Dict, List, Optional, Union, Any
import yfinance as yf
import finnhub
import requests
from datetime import datetime, timedelta
import pandas as pd
from app.core.config import get_settings
from app.core.redis import redis_client
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize API clients
finnhub_client = finnhub_client = finnhub.Client(api_key=settings.FINNHUB_API_KEY)
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

class DataSource(Enum):
    """Data source for market data."""
    FINNHUB = "finnhub"
    YAHOO = "yahoo"
    FMP = "fmp"

class TimeFrame(Enum):
    """Timeframe for market data."""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1wk"
    MONTH_1 = "1mo"

@dataclass
class MarketDataConfig:
    cache_times: Dict[str, int] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize default cache times."""
        self.cache_times = {
            "quote": 60,          # 1 minute
            "intraday": 300,      # 5 minutes
            "daily": 3600,        # 1 hour
            "profile": 86400,     # 1 day
            "peers": 86400,       # 1 day
            "indicators": 300,    # 5 minutes
            "news": 300,          # 5 minutes
            "insider": 3600,      # 1 hour
            "institutional": 86400 # 1 day
        }

class MarketDataService:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=10)
        self.config = MarketDataConfig()
    
    async def _fmp_request(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        """Make request to FMP API."""
        try:
            params = params or {}
            params["apikey"] = settings.FMP_API_KEY
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{FMP_BASE_URL}/{endpoint}", params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            logger.error(f"FMP API request error: {str(e)}")
            return None

    async def get_real_time_quote(
        self,
        symbol: str,
        source: DataSource = DataSource.FINNHUB
    ) -> Optional[Dict]:
        """Get real-time quote data from multiple sources."""
        try:
            cache_key = f"quote:{source.value}:{symbol}"
            cached_data = await redis_client.get_market_data(cache_key)
            if cached_data:
                return cached_data

            quote_data = None
            if source == DataSource.FINNHUB:
                loop = asyncio.get_event_loop()
                quote = await loop.run_in_executor(
                    self._executor,
                    finnhub_client.quote,
                    symbol
                )
                if quote:
                    quote_data = {
                        "symbol": symbol,
                        "price": quote["c"],
                        "change": quote["d"],
                        "percent_change": quote["dp"],
                        "high": quote["h"],
                        "low": quote["l"],
                        "open": quote["o"],
                        "previous_close": quote["pc"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
            
            elif source == DataSource.FMP:
                quote = await self._fmp_request(f"quote/{symbol}")
                if quote and quote[0]:
                    q = quote[0]
                    quote_data = {
                        "symbol": symbol,
                        "price": q["price"],
                        "change": q["change"],
                        "percent_change": q["changesPercentage"],
                        "high": q["dayHigh"],
                        "low": q["dayLow"],
                        "open": q["open"],
                        "previous_close": q["previousClose"],
                        "volume": q["volume"],
                        "market_cap": q["marketCap"],
                        "timestamp": datetime.utcnow().isoformat()
                    }

            if quote_data:
                await redis_client.cache_market_data(
                    cache_key,
                    quote_data,
                    self.config.cache_times["quote"]
                )
                return quote_data
            return None

        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {str(e)}")
            return None

    async def get_historical_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        source: DataSource = DataSource.YAHOO,
        limit: int = 100
    ) -> Dict:
        """Get historical price and volume data."""
        try:
            interval = self._convert_timeframe(timeframe)
            period = "1mo"  # Default to 1 month for timeframe-based queries
            
            cache_key = f"historical:{source.value}:{symbol}:{period}:{interval}"
            cached_data = await redis_client.get_market_data(cache_key)
            if cached_data:
                return cached_data

            historical_data = None
            if source == DataSource.YAHOO:
                loop = asyncio.get_event_loop()
                ticker = await loop.run_in_executor(
                    self._executor,
                    lambda: yf.Ticker(symbol)
                )
                
                hist = await loop.run_in_executor(
                    self._executor,
                    lambda: ticker.history(period=period, interval=interval)
                )
                
                if not hist.empty:
                    historical_data = []
                    for index, row in hist.iterrows():
                        data_point = {
                            "timestamp": index.isoformat(),
                            "open": float(row["Open"]),
                            "high": float(row["High"]),
                            "low": float(row["Low"]),
                            "close": float(row["Close"]),
                            "volume": int(row["Volume"])
                        }
                        historical_data.append(data_point)

            elif source == DataSource.FMP:
                # Convert period to FMP format
                if period.endswith('d'):
                    days = int(period[:-1])
                    fmp_period = f"{days}min" if interval.endswith('m') else "1hour"
                    endpoint = f"historical-chart/{fmp_period}/{symbol}"
                else:
                    endpoint = f"historical-price-full/{symbol}"
                
                hist = await self._fmp_request(endpoint)
                if hist and "historical" in hist:
                    historical_data = []
                    for item in hist["historical"]:
                        data_point = {
                            "timestamp": item["date"],
                            "open": float(item["open"]),
                            "high": float(item["high"]),
                            "low": float(item["low"]),
                            "close": float(item["close"]),
                            "volume": int(item["volume"])
                        }
                        historical_data.append(data_point)

            if historical_data:
                cache_time = self.config.cache_times["intraday"] if interval.endswith('m') else self.config.cache_times["daily"]
                await redis_client.cache_market_data(cache_key, historical_data, cache_time)
                return historical_data
            return None

        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {str(e)}")
            raise Exception(f"Failed to get historical data: {str(e)}")

    def _convert_timeframe(self, timeframe: TimeFrame) -> str:
        """Convert TimeFrame enum to yfinance interval string."""
        mapping = {
            TimeFrame.MINUTE_1: "1m",
            TimeFrame.MINUTE_5: "5m",
            TimeFrame.MINUTE_15: "15m",
            TimeFrame.MINUTE_30: "30m",
            TimeFrame.HOUR_1: "1h",
            TimeFrame.HOUR_4: "4h",
            TimeFrame.DAY_1: "1d",
            TimeFrame.WEEK_1: "1wk",
            TimeFrame.MONTH_1: "1mo"
        }
        return mapping.get(timeframe, "1d")

    async def get_trades(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> pd.DataFrame:
        """Get recent trades for a symbol."""
        try:
            trades_data = await self._fmp_request(
                f"historical-price-minute/{symbol}",
                {
                    "from": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "to": end_time.strftime("%Y-%m-%d %H:%M:%S")
                }
            )
            
            if not trades_data:
                return pd.DataFrame()
            
            df = pd.DataFrame(trades_data)
            df['timestamp'] = pd.to_datetime(df['date'])
            df['is_aggressive'] = df['price'] > df['price'].shift(1)
            df['side'] = np.where(df['is_aggressive'], 'buy', 'sell')
            
            return df[['timestamp', 'price', 'volume', 'side', 'is_aggressive']]
            
        except Exception as e:
            logger.error(f"Error getting trades for {symbol}: {str(e)}")
            return pd.DataFrame()

    async def get_last_price(self, symbol: str) -> float:
        """Get last traded price for a symbol."""
        try:
            quote = await self.get_real_time_quote(symbol)
            return quote['price'] if quote else None
        except Exception as e:
            logger.error(f"Error getting last price for {symbol}: {str(e)}")
            return None

# Global market data service instance
market_data_service = MarketDataService()
