"""
Tests for Redis caching system
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
from datetime import datetime, timezone

from multi_provider_router.models import GenerationRequest, GenerationResponse, ProviderType, ChatMessage
from multi_provider_router.utils.cache import CacheManager


# ============================================================================
# Cache Manager Tests
# ============================================================================

class TestCacheManager:
    """Test cache manager"""

    @pytest.fixture
    def cache_manager(self):
        """Create a cache manager instance"""
        return CacheManager()

    def test_generate_cache_key(self, cache_manager, simple_request):
        """Test cache key generation"""
        key1 = cache_manager._generate_cache_key(simple_request)
        key2 = cache_manager._generate_cache_key(simple_request)

        # Same request should generate same key
        assert key1 == key2
        assert key1.startswith("luciddreamer:cache:")

        # Different request should generate different key
        different_request = GenerationRequest(
            messages=[ChatMessage(role="user", content="Different message")],
            temperature=0.5
        )
        key3 = cache_manager._generate_cache_key(different_request)

        assert key1 != key3

    @pytest.mark.asyncio
    async def test_get_cached_response_miss(self, cache_manager, simple_request, mock_redis):
        """Test cache miss"""
        cache_manager._redis = mock_redis
        mock_redis.get.return_value = None

        result = await cache_manager.get_cached_response(simple_request)

        assert result is None
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cached_response_hit(self, cache_manager, simple_request, sample_response, mock_redis):
        """Test cache hit"""
        cache_manager._redis = mock_redis

        # Mock cached response data
        cached_data = {
            "request_id": sample_response.request_id,
            "content": sample_response.content,
            "provider_used": sample_response.provider_used.value,
            "model_used": sample_response.model_used,
            "input_tokens": sample_response.input_tokens,
            "output_tokens": sample_response.output_tokens,
            "cost_usd": sample_response.cost_usd,
            "processing_time_ms": sample_response.processing_time_ms,
            "cached": True
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        result = await cache_manager.get_cached_response(simple_request)

        assert result is not None
        assert result.content == sample_response.content
        assert result.cached == True

    @pytest.mark.asyncio
    async def test_cache_response(self, cache_manager, simple_request, sample_response, mock_redis):
        """Test caching a response"""
        cache_manager._redis = mock_redis

        await cache_manager.cache_response(simple_request, sample_response, ttl_seconds=3600)

        # Verify setex was called
        assert mock_redis.setex.called or mock_redis.pipeline.called

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, cache_manager, mock_redis):
        """Test cache invalidation"""
        cache_manager._redis = mock_redis
        mock_redis.keys.return_value = ["key1", "key2", "key3"]
        mock_redis.delete.return_value = 3

        count = await cache_manager.invalidate_cache("luciddreamer:cache:*")

        assert count == 3
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, cache_manager, mock_redis):
        """Test getting cache statistics"""
        cache_manager._redis = mock_redis
        mock_redis.info.side_effect = [
            {'used_memory': 1000000, 'used_memory_human': '1MB'},
            {'db': {'db0': 100}}
        ]
        mock_redis.keys.return_value = ["key1", "key2", "key1:meta"]

        stats = await cache_manager.get_cache_stats()

        assert "memory_used_bytes" in stats
        assert "cached_responses" in stats
        assert stats["cached_responses"] == 2  # Excludes :meta keys

    @pytest.mark.asyncio
    async def test_cache_request_metrics(self, cache_manager, mock_redis):
        """Test caching request metrics"""
        cache_manager._redis = mock_redis

        await cache_manager.cache_request_metrics(
            request_id="test-req-123",
            provider="glm",
            response_time_ms=500,
            cost_usd=0.001
        )

        # Verify metrics were cached
        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_get_metrics_for_period(self, cache_manager, mock_redis):
        """Test getting metrics for a time period"""
        cache_manager._redis = mock_redis

        # Mock metric data
        metric_data = {
            'request_id': 'test-req-123',
            'provider': 'glm',
            'response_time_ms': 500,
            'cost_usd': 0.001,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        mock_redis.keys.return_value = ["key1", "key2"]
        mock_redis.get.side_effect = [
            json.dumps(metric_data),
            json.dumps(metric_data)
        ]

        metrics = await cache_manager.get_metrics_for_period(hours=24)

        assert isinstance(metrics, list)
        assert len(metrics) == 2

    @pytest.mark.asyncio
    async def test_cleanup_expired_cache(self, cache_manager, mock_redis):
        """Test cleaning up expired cache entries"""
        cache_manager._redis = mock_redis
        mock_redis.keys.return_value = ["key1", "key2"]
        mock_redis.ttl.return_value = -1  # No TTL set
        mock_redis.expire.return_value = True

        count = await cache_manager.cleanup_expired_cache()

        assert count >= 0

    @pytest.mark.asyncio
    async def test_cache_error_handling(self, cache_manager, simple_request):
        """Test cache error handling"""
        # Mock Redis that raises exceptions
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis error")
        cache_manager._redis = mock_redis

        # Should not raise exception, just return None
        result = await cache_manager.get_cached_response(simple_request)

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
