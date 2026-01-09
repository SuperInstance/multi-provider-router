"""
Tests for rate limiting system (token bucket algorithm)
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
import time

from multi_provider_router.models import ProviderType
from multi_provider_router.utils.rate_limiter import RateLimiter, RateLimitRule


# ============================================================================
# Rate Limiter Tests
# ============================================================================

class TestRateLimiter:
    """Test rate limiter"""

    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter instance"""
        return RateLimiter()

    def test_initialization(self, rate_limiter):
        """Test rate limiter initialization"""
        assert ProviderType.GLM in rate_limiter._rules
        assert ProviderType.OPENAI in rate_limiter._rules

        glm_rule = rate_limiter._rules[ProviderType.GLM]
        assert glm_rule.requests_per_minute == 60
        assert glm_rule.requests_per_hour == 3000
        assert glm_rule.requests_per_day == 50000

    def test_get_rate_limit_rule(self, rate_limiter):
        """Test getting rate limit rule"""
        rule = rate_limiter.get_rate_limit_rule(ProviderType.GLM)

        assert isinstance(rule, RateLimitRule)
        assert rule.requests_per_minute == 60

    def test_set_user_rate_limit(self, rate_limiter):
        """Test setting custom user rate limit"""
        custom_rule = RateLimitRule(
            requests_per_minute=10,
            requests_per_hour=100,
            requests_per_day=1000
        )

        rate_limiter.set_user_rate_limit("test-user", custom_rule)

        assert "test-user" in rate_limiter._user_limits
        assert rate_limiter._user_limits["test-user"].requests_per_minute == 10

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter):
        """Test rate limit check when allowed"""
        can_proceed, remaining = await rate_limiter.check_rate_limit(ProviderType.GLM)

        assert can_proceed == True
        assert "minute" in remaining
        assert "hour" in remaining
        assert "day" in remaining

    @pytest.mark.asyncio
    async def test_check_rate_limit_with_user(self, rate_limiter):
        """Test rate limit check with user-specific limits"""
        custom_rule = RateLimitRule(
            requests_per_minute=5,
            requests_per_hour=50,
            requests_per_day=500
        )
        rate_limiter.set_user_rate_limit("test-user-123", custom_rule)

        can_proceed, remaining = await rate_limiter.check_rate_limit(
            ProviderType.GLM,
            user_id="test-user-123"
        )

        assert can_proceed == True
        assert remaining["minute"] <= 5

    @pytest.mark.asyncio
    async def test_check_local_rate_limit(self, rate_limiter):
        """Test local rate limiting (without Redis)"""
        # Make multiple requests
        for _ in range(10):
            can_proceed, remaining = await rate_limiter._check_local_rate_limit(
                ProviderType.GLM,
                None,
                rate_limiter._rules[ProviderType.GLM]
            )
            assert can_proceed == True

        # Should have tracked requests
        counters = rate_limiter._local_counters[ProviderType.GLM]
        assert len(counters['minute']) >= 10

    @pytest.mark.asyncio
    async def test_wait_if_needed(self, rate_limiter):
        """Test waiting if rate limited"""
        # Should proceed immediately if not limited
        result = await rate_limiter.wait_if_needed(
            ProviderType.GLM,
            max_wait_seconds=1
        )

        assert result == True

    @pytest.mark.asyncio
    async def test_get_rate_limit_status(self, rate_limiter):
        """Test getting rate limit status"""
        status = await rate_limiter.get_rate_limit_status(ProviderType.GLM)

        assert "provider" in status
        assert "limits" in status
        assert "current" in status
        assert "remaining" in status
        assert "is_limited" in status

        assert status["provider"] == "glm"
        assert status["limits"]["minute"] == 60

    @pytest.mark.asyncio
    async def test_reset_rate_limits(self, rate_limiter):
        """Test resetting rate limits"""
        # Add some requests
        for _ in range(5):
            await rate_limiter._check_local_rate_limit(
                ProviderType.GLM,
                None,
                rate_limiter._rules[ProviderType.GLM]
            )

        # Reset
        await rate_limiter.reset_rate_limits(ProviderType.GLM)

        # Counters should be empty
        counters = rate_limiter._local_counters[ProviderType.GLM]
        assert len(counters['minute']) == 0
        assert len(counters['hour']) == 0
        assert len(counters['day']) == 0


# ============================================================================
# Rate Limit Rule Tests
# ============================================================================

class TestRateLimitRule:
    """Test rate limit rule dataclass"""

    def test_rate_limit_rule_creation(self):
        """Test creating a rate limit rule"""
        rule = RateLimitRule(
            requests_per_minute=60,
            requests_per_hour=3000,
            requests_per_day=50000,
            burst_capacity=20
        )

        assert rule.requests_per_minute == 60
        assert rule.requests_per_hour == 3000
        assert rule.requests_per_day == 50000
        assert rule.burst_capacity == 20


# ============================================================================
# Provider-Specific Rate Limits
# ============================================================================

class TestProviderRateLimits:
    """Test rate limits for different providers"""

    def test_glm_rate_limits(self, rate_limiter):
        """Test GLM rate limits"""
        rule = rate_limiter._rules[ProviderType.GLM]

        assert rule.requests_per_minute == 60
        assert rule.requests_per_hour == 3000
        assert rule.requests_per_day == 50000
        assert rule.burst_capacity == 20

    def test_openai_rate_limits(self, rate_limiter):
        """Test OpenAI rate limits"""
        rule = rate_limiter._rules[ProviderType.OPENAI]

        assert rule.requests_per_minute == 60
        assert rule.requests_per_hour == 3500
        assert rule.requests_per_day == 100000

    def test_deepseek_rate_limits(self, rate_limiter):
        """Test DeepSeek rate limits"""
        rule = rate_limiter._rules[ProviderType.DEEPSEEK]

        assert rule.requests_per_minute == 50
        assert rule.requests_per_hour == 2000
        assert rule.requests_per_day == 40000

    def test_claude_rate_limits(self, rate_limiter):
        """Test Claude rate limits"""
        rule = rate_limiter._rules[ProviderType.CLAUDE]

        assert rule.requests_per_minute == 50
        assert rule.requests_per_hour == 2000
        assert rule.requests_per_day == 30000

    def test_deepinfra_rate_limits(self, rate_limiter):
        """Test DeepInfra rate limits"""
        rule = rate_limiter._rules[ProviderType.DEEPINFRA]

        assert rule.requests_per_minute == 30
        assert rule.requests_per_hour == 1000
        assert rule.requests_per_day == 20000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
