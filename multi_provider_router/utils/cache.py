"""
Caching system for request deduplication and response caching
"""

import json
import hashlib
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import redis.asyncio as redis
from dataclasses import asdict

from ..models import GenerationRequest, GenerationResponse, ChatMessage
from ..config import get_settings

settings = get_settings()


class CacheManager:
    """Manages caching of requests and responses"""

    def __init__(self):
        self.redis_url = settings.redis.url
        self.max_connections = settings.redis.max_connections
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Connect to Redis"""
        self._redis = redis.from_url(
            self.redis_url,
            max_connections=self.max_connections,
            decode_responses=True
        )

    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self._redis:
            await self._redis.close()

    def _generate_cache_key(self, request: GenerationRequest) -> str:
        """Generate a cache key for a request"""
        # Create a normalized representation of the request
        cache_data = {
            'messages': [
                {'role': msg.role, 'content': msg.content}
                for msg in request.messages
            ],
            'temperature': request.temperature,
            'top_p': request.top_p,
            'max_tokens': request.max_tokens
        }

        # Create hash
        cache_str = json.dumps(cache_data, sort_keys=True)
        return f"luciddreamer:cache:{hashlib.sha256(cache_str.encode()).hexdigest()}"

    async def get_cached_response(self, request: GenerationRequest) -> Optional[GenerationResponse]:
        """Get cached response for a request"""
        if not self._redis:
            return None

        cache_key = self._generate_cache_key(request)
        try:
            cached_data = await self._redis.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                return GenerationResponse(**data)
        except Exception:
            # Cache errors should not break the system
            pass

        return None

    async def cache_response(
        self,
        request: GenerationRequest,
        response: GenerationResponse,
        ttl_seconds: int = 3600
    ) -> None:
        """Cache a response"""
        if not self._redis:
            return

        cache_key = self._generate_cache_key(request)
        try:
            # Serialize response
            response_data = asdict(response)
            cached_data = json.dumps(response_data)

            # Store with TTL
            await self._redis.setex(cache_key, ttl_seconds, cached_data)

            # Also store cache metadata
            metadata_key = f"{cache_key}:meta"
            metadata = {
                'request_id': request.request_id,
                'provider_used': response.provider_used,
                'cached_at': datetime.now(timezone.utc).isoformat(),
                'ttl_seconds': ttl_seconds
            }
            await self._redis.setex(metadata_key, ttl_seconds, json.dumps(metadata))

        except Exception:
            # Cache errors should not break the system
            pass

    async def invalidate_cache(self, pattern: str = "*") -> int:
        """Invalidate cache entries matching pattern"""
        if not self._redis:
            return 0

        try:
            keys = await self._redis.keys(pattern)
            if keys:
                return await self._redis.delete(*keys)
        except Exception:
            pass

        return 0

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self._redis:
            return {}

        try:
            info = await self._redis.info('memory')
            keyspace = await self._redis.info('keyspace')

            # Count cache keys
            cache_keys = await self._redis.keys("luciddreamer:cache:*")
            cache_count = len([k for k in cache_keys if not k.endswith(":meta")])

            return {
                'memory_used_bytes': info.get('used_memory', 0),
                'memory_human': info.get('used_memory_human', '0B'),
                'cached_responses': cache_count,
                'total_keys': sum(info.get('db', {}).values()),
                'hit_rate': 0.0  # Would need to track hits/misses separately
            }
        except Exception:
            return {}

    async def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries"""
        if not self._redis:
            return 0

        try:
            # Redis automatically handles TTL expiration
            # This method can be used for manual cleanup if needed
            cache_keys = await self._redis.keys("luciddreamer:cache:*")
            expired_count = 0

            for key in cache_keys:
                ttl = await self._redis.ttl(key)
                if ttl == -1:  # No TTL set
                    # Set a default TTL for keys without expiration
                    await self._redis.expire(key, 3600)
                    expired_count += 1

            return expired_count
        except Exception:
            return 0

    async def cache_request_metrics(
        self,
        request_id: str,
        provider: str,
        response_time_ms: int,
        cost_usd: float,
        ttl_seconds: int = 86400  # 24 hours
    ) -> None:
        """Cache request metrics for analytics"""
        if not self._redis:
            return

        try:
            key = f"luciddreamer:metrics:{request_id}"
            metrics_data = {
                'request_id': request_id,
                'provider': provider,
                'response_time_ms': response_time_ms,
                'cost_usd': cost_usd,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            await self._redis.setex(key, ttl_seconds, json.dumps(metrics_data))
        except Exception:
            pass

    async def get_metrics_for_period(
        self,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get cached metrics for a time period"""
        if not self._redis:
            return []

        try:
            pattern = "luciddreamer:metrics:*"
            keys = await self._redis.keys(pattern)

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            metrics = []

            for key in keys:
                data = await self._redis.get(key)
                if data:
                    metric_data = json.loads(data)
                    timestamp = datetime.fromisoformat(metric_data['timestamp'])
                    if timestamp >= cutoff_time:
                        metrics.append(metric_data)

            return metrics
        except Exception:
            return []


# Global cache manager instance
cache = CacheManager()