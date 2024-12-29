import redis.asyncio as redis
from typing import Optional, Any
import json
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class RedisClient:
    """Redis client wrapper."""
    def __init__(self):
        self._redis = None
        self._connect()

    def _connect(self):
        """Connect to Redis."""
        try:
            if not self._redis:
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
        except Exception as e:
            logger.error(f"Redis connection error: {str(e)}")
            # Create a mock Redis client for testing
            if settings.ENVIRONMENT == "test":
                self._redis = MockRedis()
            else:
                raise

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        try:
            if not self._redis:
                self._connect()
            value = await self._redis.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Redis get error: {str(e)}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        expire: int = 3600
    ) -> bool:
        """Set value in Redis with expiration."""
        try:
            if not self._redis:
                self._connect()
            await self._redis.setex(
                key,
                expire,
                json.dumps(value)
            )
            return True
        except Exception as e:
            logger.error(f"Redis set error: {str(e)}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        try:
            if not self._redis:
                self._connect()
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {str(e)}")
            return False

    async def increment(self, key: str) -> Optional[int]:
        """Increment counter in Redis."""
        try:
            if not self._redis:
                self._connect()
            async with self._redis.pipeline() as pipe:
                await pipe.incr(key)
                await pipe.expire(key, 3600)  # 1 hour expiry
                result = await pipe.execute()
                return result[0]
        except Exception as e:
            logger.error(f"Redis increment error: {str(e)}")
            return None

    async def get_keys(self, pattern: str) -> list:
        """Get keys matching pattern."""
        try:
            if not self._redis:
                self._connect()
            return await self._redis.keys(pattern)
        except Exception as e:
            logger.error(f"Redis get_keys error: {str(e)}")
            return []

    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value from Redis."""
        return await self.get(key)

    async def set_json(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Set JSON value in Redis."""
        return await self.set(key, value, expire)

    # Rate Limiting Methods
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int
    ) -> tuple[bool, int]:
        """
        Check if rate limit is exceeded.
        Returns (is_allowed, current_count).
        """
        try:
            current = await self.increment(key)
            if current == 1:  # First request in window
                await self._redis.expire(key, window)
            
            is_allowed = current <= limit
            return is_allowed, current
        except Exception as e:
            logger.error(f"Rate limit check error: {str(e)}")
            return True, 0  # Fail open to allow requests if Redis is down

    # Cache Methods
    async def cache_get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        return await self.get(f"cache:{key}")

    async def cache_set(
        self,
        key: str,
        value: Any,
        expire: int = 300
    ) -> bool:
        """Set value in cache with expiration (default 5 minutes)."""
        return await self.set(f"cache:{key}", value, expire)

    # Market Data Cache Methods
    async def cache_market_data(
        self,
        symbol: str,
        data: dict,
        expire: int = 60
    ) -> bool:
        """Cache market data for a symbol (default 1 minute)."""
        return await self.cache_set(f"market:{symbol}", data, expire)

    async def get_market_data(self, symbol: str) -> Optional[dict]:
        """Get cached market data for a symbol."""
        return await self.cache_get(f"market:{symbol}")

    # News Cache Methods
    async def cache_news(
        self,
        key: str,
        news_data: list,
        expire: int = 300
    ) -> bool:
        """Cache news data (default 5 minutes)."""
        return await self.cache_set(f"news:{key}", news_data, expire)

    async def get_cached_news(self, key: str) -> Optional[list]:
        """Get cached news data."""
        return await self.cache_get(f"news:{key}")

class MockRedis:
    """Mock Redis for testing."""
    def __init__(self):
        self.data = {}

    async def get(self, key: str) -> Optional[str]:
        return self.data.get(key)

    async def setex(self, key: str, expire: int, value: str):
        self.data[key] = value

    async def delete(self, key: str):
        self.data.pop(key, None)

    async def incr(self, key: str) -> int:
        value = int(self.data.get(key, 0)) + 1
        self.data[key] = str(value)
        return value

    async def expire(self, key: str, seconds: int):
        pass

    async def execute(self):
        pass

    def pipeline(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def keys(self, pattern: str) -> list:
        import fnmatch
        return [k for k in self.data.keys() if fnmatch.fnmatch(k, pattern)]

redis_client = RedisClient()
