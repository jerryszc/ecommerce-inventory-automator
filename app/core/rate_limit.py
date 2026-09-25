import redis
import time
from app.core.config import settings
from app.core.aws import get_redis_client as _get_redis_client

_redis_client = None


def get_redis_client() -> "redis.Redis":
    global _redis_client
    if _redis_client is None:
        from app.core.aws import get_redis_client as _get_redis
        _redis_client = _get_redis()
    return _redis_client


class DistributedRateLimiter:
    """Rate limiter distribuido usando Redis (LocalStack/ElastiCache)."""

    def __init__(self, limit: int = 100, window: int = 60):
        self.limit = limit
        self.window = window
        self.redis = get_redis_client()

    def is_allowed(self, key: str) -> tuple[bool, dict]:
        """
        Returns (allowed, headers_dict).
        Headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
        """
        now = int(time.time())
        window_start = now - self.window

        # Sliding window log algorithm
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, self.window)
        results = pipe.execute()

        current_count = results[1]
        allowed = current_count < self.limit

        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.limit - current_count)),
            "X-RateLimit-Reset": str(now + self.window),
        }

        return allowed, headers


_distributed_limiter = DistributedRateLimiter(
    limit=settings.rate_limit_requests,
    window=settings.rate_limit_window
)


def distributed_rate_limit(key: str) -> tuple[bool, dict]:
    """Dependency para FastAPI."""
    return _distributed_limiter.is_allowed(key)