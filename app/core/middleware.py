from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from typing import Callable
import logging
from app.core.redis import redis_client
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = (time.time() - start_time) * 1000
        formatted_process_time = '{0:.2f}'.format(process_time)
        
        logger.info(
            f"path={request.url.path} "
            f"method={request.method} "
            f"status_code={response.status_code} "
            f"duration={formatted_process_time}ms"
        )
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for certain paths
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)

        # Get client identifier (IP or user ID if authenticated)
        client_id = "test_client"
        if request.client and request.client.host:
            client_id = request.client.host
        elif "authorization" in request.headers:
            # TODO: Extract user ID from JWT token
            client_id = request.headers["authorization"]
            pass

        # Create rate limit key
        rate_key = f"rate_limit:{client_id}:{request.url.path}"
        
        # Check rate limit
        is_allowed, current_count = await redis_client.check_rate_limit(
            rate_key,
            settings.RATE_LIMIT_PER_SECOND,
            1  # 1 second window
        )
        
        if not is_allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many requests"
            )
        
        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_PER_SECOND)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, settings.RATE_LIMIT_PER_SECOND - current_count)
        )
        
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response
