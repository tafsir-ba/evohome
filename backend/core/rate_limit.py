"""
Rate Limiting Module

Redis-backed when REDIS_URL is configured (multi-instance safe).
Falls back to in-memory limiter when Redis is unavailable.
"""

import os
import time
import uuid
import logging
from typing import Dict, Tuple, Optional
from collections import defaultdict
from functools import wraps
from fastapi import Request, HTTPException

try:
    from redis.asyncio import Redis as AsyncRedis
except Exception:  # pragma: no cover - optional dependency
    AsyncRedis = None

logger = logging.getLogger("evohome.ratelimit")
REDIS_URL = os.environ.get("REDIS_URL", "").strip()


class RateLimiter:
    """
    Simple sliding window rate limiter.
    
    Tracks requests per IP/key within a time window.
    Thread-safe for single-process deployment.
    """
    
    def __init__(self):
        # Structure: {key: [(timestamp, count), ...]}
        self._requests: Dict[str, list] = defaultdict(list)
        self._cleanup_interval = 60  # seconds
        self._last_cleanup = time.time()
    
    def _cleanup(self):
        """Remove expired entries periodically."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        cutoff = now - 3600  # Keep 1 hour of data max
        for key in list(self._requests.keys()):
            self._requests[key] = [
                (ts, count) for ts, count in self._requests[key]
                if ts > cutoff
            ]
            if not self._requests[key]:
                del self._requests[key]
        
        self._last_cleanup = now
    
    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            key: Unique identifier (IP, user_id, etc.)
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        
        Returns:
            Tuple of (allowed, remaining, reset_in_seconds)
        """
        self._cleanup()
        
        now = time.time()
        window_start = now - window_seconds
        
        # Count requests in window
        recent = [
            (ts, count) for ts, count in self._requests[key]
            if ts > window_start
        ]
        total = sum(count for _, count in recent)
        
        if total >= max_requests:
            # Calculate reset time
            oldest = min((ts for ts, _ in recent), default=now)
            reset_in = int(oldest + window_seconds - now) + 1
            return False, 0, reset_in
        
        # Record this request
        self._requests[key].append((now, 1))
        remaining = max_requests - total - 1
        
        return True, remaining, window_seconds
    
    def record_request(self, key: str, count: int = 1):
        """Record a request without checking limits."""
        self._requests[key].append((time.time(), count))


# Global rate limiter instance
_limiter = RateLimiter()
_redis_client: Optional["AsyncRedis"] = None
_redis_init_failed = False


# Rate limit configurations per endpoint category
RATE_LIMITS = {
    # Auth endpoints - strict to prevent brute force
    "auth_login": {"max": 5, "window": 60},         # 5 attempts per minute
    "auth_register": {"max": 3, "window": 60},      # 3 registrations per minute
    "auth_password_reset": {"max": 3, "window": 300}, # 3 per 5 minutes
    
    # Expensive operations
    "ai_extraction": {"max": 10, "window": 60},     # 10 extractions per minute
    "document_generation": {"max": 20, "window": 60}, # 20 docs per minute
    "email_send": {"max": 30, "window": 60},        # 30 emails per minute
    
    # File uploads
    "file_upload": {"max": 20, "window": 60},       # 20 uploads per minute
    
    # General API - lenient
    "api_general": {"max": 100, "window": 60},      # 100 requests per minute
}


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check for forwarded header (behind proxy/load balancer)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


async def _get_redis_client() -> Optional["AsyncRedis"]:
    """Create and cache Redis client if configured."""
    global _redis_client, _redis_init_failed

    if _redis_client is not None:
        return _redis_client
    if _redis_init_failed or not REDIS_URL or AsyncRedis is None:
        return None

    try:
        client = AsyncRedis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
        _redis_client = client
        logger.info("Rate limiter using Redis backend")
        return _redis_client
    except Exception as e:
        _redis_init_failed = True
        logger.warning(f"Redis rate limiter unavailable; using in-memory fallback: {e}")
        return None


async def _check_rate_limit_redis(
    key: str,
    max_requests: int,
    window_seconds: int,
) -> Tuple[bool, int, int]:
    """Sliding-window rate limiting in Redis with sorted sets."""
    redis = await _get_redis_client()
    if redis is None:
        return _limiter.is_allowed(key, max_requests, window_seconds)

    now_ms = int(time.time() * 1000)
    window_start_ms = now_ms - (window_seconds * 1000)
    redis_key = f"rate_limit:{key}"
    member = f"{now_ms}-{uuid.uuid4().hex[:8]}"

    try:
        pipe = redis.pipeline(transaction=True)
        pipe.zremrangebyscore(redis_key, 0, window_start_ms)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {member: now_ms})
        pipe.expire(redis_key, max(window_seconds, 60))
        _, current_count, _, _ = await pipe.execute()

        if current_count >= max_requests:
            await redis.zrem(redis_key, member)
            oldest = await redis.zrange(redis_key, 0, 0, withscores=True)
            if oldest:
                oldest_ms = int(oldest[0][1])
                reset_in = max(1, int((oldest_ms + (window_seconds * 1000) - now_ms) / 1000) + 1)
            else:
                reset_in = window_seconds
            return False, 0, reset_in

        remaining = max_requests - current_count - 1
        return True, remaining, window_seconds
    except Exception as e:
        logger.warning(f"Redis rate-limit check failed; using in-memory fallback: {e}")
        return _limiter.is_allowed(key, max_requests, window_seconds)


async def check_rate_limit(
    request: Request,
    category: str,
    key_suffix: str = ""
) -> Tuple[bool, Dict[str, int]]:
    """
    Check rate limit for a request.
    
    Args:
        request: FastAPI request object
        category: Rate limit category from RATE_LIMITS
        key_suffix: Optional suffix to add to key (e.g., user_id)
    
    Returns:
        Tuple of (allowed, headers_dict)
    """
    config = RATE_LIMITS.get(category, RATE_LIMITS["api_general"])
    
    client_ip = get_client_ip(request)
    key = f"{category}:{client_ip}"
    if key_suffix:
        key = f"{key}:{key_suffix}"

    allowed, remaining, reset_in = await _check_rate_limit_redis(
        key, config["max"], config["window"]
    )
    
    headers = {
        "X-RateLimit-Limit": config["max"],
        "X-RateLimit-Remaining": max(0, remaining),
        "X-RateLimit-Reset": reset_in
    }
    
    if not allowed:
        logger.warning(f"Rate limit exceeded: {key} ({category})")
    
    return allowed, headers


def rate_limit(category: str):
    """
    Decorator for rate limiting endpoints.
    
    Usage:
        @rate_limit("auth_login")
        async def login(request: Request, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find request in args or kwargs
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request:
                allowed, headers = await check_rate_limit(request, category)
                
                if not allowed:
                    raise HTTPException(
                        status_code=429,
                        detail="Too many requests. Please try again later.",
                        headers={k: str(v) for k, v in headers.items()}
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def rate_limit_check(request: Request, category: str) -> None:
    """
    Inline rate limit check for use inside endpoints.
    
    Usage:
        rate_limit_check(request, "ai_extraction")
    
    Raises:
        HTTPException: If rate limit exceeded
    """
    allowed, headers = await check_rate_limit(request, category)
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={k: str(v) for k, v in headers.items()}
        )
