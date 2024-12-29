from functools import wraps
from typing import Any, Callable
import hashlib
import json
from app.core.redis import redis_client
import logging

logger = logging.getLogger(__name__)

def cache_response(expire: int = 300):
    """
    Cache decorator for API responses.
    
    Args:
        expire: Cache expiration time in seconds (default: 5 minutes)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate cache key from function name and arguments
            key_parts = [func.__name__]
            
            # Add args to key
            for arg in args:
                if hasattr(arg, '__dict__'):
                    # For objects like Request, only use relevant attributes
                    key_parts.append(str(getattr(arg, 'url', arg)))
                else:
                    key_parts.append(str(arg))
            
            # Add kwargs to key
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}:{v}")
            
            # Create deterministic cache key
            key_str = ":".join(key_parts)
            cache_key = hashlib.sha256(key_str.encode()).hexdigest()
            
            # Try to get from cache
            cached_value = await redis_client.cache_get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_value
            
            # If not in cache, execute function
            logger.debug(f"Cache miss for key: {cache_key}")
            result = await func(*args, **kwargs)
            
            # Cache the result
            await redis_client.cache_set(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator

def invalidate_cache(pattern: str) -> None:
    """
    Invalidate cache entries matching a pattern.
    
    Args:
        pattern: Redis key pattern to match (e.g., "market:*")
    """
    async def _invalidate():
        try:
            keys = await redis_client._redis.keys(f"cache:{pattern}")
            if keys:
                await redis_client._redis.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries matching pattern: {pattern}")
        except Exception as e:
            logger.error(f"Cache invalidation error: {str(e)}")
    
    return _invalidate
