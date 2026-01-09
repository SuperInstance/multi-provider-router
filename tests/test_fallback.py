"""
Tests for fallback manager, circuit breaker, and failover logic
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
import asyncio

from multi_provider_router.models import ProviderType, GenerationRequest, ChatMessage
from multi_provider_router.routing.fallback_manager import (
    FallbackManager,
    FailureType,
    FailureRecord
)
from multi_provider_router.providers.glm_provider import GLMProvider
from multi_provider_router.providers.openai_provider import OpenAIProvider


# ============================================================================
# Fallback Manager Tests
# ============================================================================

class TestFallbackManager:
    """Test fallback manager"""

    @pytest.fixture
    def fallback_manager(self):
        """Create a fallback manager instance"""
        return FallbackManager()

    @pytest.fixture
    def mock_providers(self, glm_config, openai_config):
        """Create mock providers"""
        return {
            ProviderType.GLM: GLMProvider(glm_config),
            ProviderType.OPENAI: OpenAIProvider(openai_config)
        }

    @pytest.mark.asyncio
    async def test_initialize(self, fallback_manager, mock_providers):
        """Test fallback manager initialization"""
        await fallback_manager.initialize(mock_providers)

        assert len(fallback_manager.providers) == 2
        assert ProviderType.GLM in fallback_manager.failure_history
        assert ProviderType.OPENAI in fallback_manager.circuit_breaker_state

    @pytest.mark.asyncio
    async def test_get_fallback_chain(self, fallback_manager, mock_providers, simple_request):
        """Test getting fallback chain"""
        await fallback_manager.initialize(mock_providers)

        with patch('multi_provider_router.routing.fallback_manager.health_checker') as mock_health, \
             patch('multi_provider_router.routing.fallback_manager.rate_limiter') as mock_rate:

            mock_health.is_healthy.return_value = True
            mock_health.get_provider_health_score.return_value = 1.0
            mock_rate.check_rate_limit = AsyncMock(return_value=(True, {}))

            chain = await fallback_manager.get_fallback_chain(ProviderType.GLM, simple_request)

            assert isinstance(chain, list)
            assert ProviderType.GLM not in chain  # Primary should not be in fallback
            # OpenAI should be in chain
            assert ProviderType.OPENAI in chain

    def test_record_failure(self, fallback_manager, mock_providers):
        """Test recording provider failures"""
        fallback_manager.providers = mock_providers
        fallback_manager.failure_history[ProviderType.GLM] = []
        fallback_manager.circuit_breaker_state[ProviderType.GLM] = False

        # Record a failure
        fallback_manager.record_failure(
            ProviderType.GLM,
            FailureType.API_ERROR,
            "Test error"
        )

        assert len(fallback_manager.failure_history[ProviderType.GLM]) == 1
        assert fallback_manager.failure_history[ProviderType.GLM][0].error_message == "Test error"

    def test_is_provider_available(self, fallback_manager, mock_providers):
        """Test checking provider availability"""
        fallback_manager.providers = mock_providers
        fallback_manager.blacklisted_providers = set()
        fallback_manager.circuit_breaker_state = {ProviderType.GLM: False, ProviderType.OPENAI: False}

        with patch('multi_provider_router.routing.fallback_manager.health_checker') as mock_health:
            mock_health.is_healthy.return_value = True

            assert fallback_manager.is_provider_available(ProviderType.GLM) == True

            # Blacklist the provider
            fallback_manager.blacklisted_providers.add(ProviderType.GLM)
            assert fallback_manager.is_provider_available(ProviderType.GLM) == False

    def test_circuit_breaker_trigger(self, fallback_manager, mock_providers):
        """Test circuit breaker triggering"""
        fallback_manager.providers = mock_providers
        fallback_manager.failure_history[ProviderType.GLM] = []
        fallback_manager.circuit_breaker_state[ProviderType.GLM] = False

        # Record multiple failures to trigger circuit breaker
        for _ in range(3):
            fallback_manager.record_failure(
                ProviderType.GLM,
                FailureType.TIMEOUT,
                "Timeout error"
            )

        # Circuit breaker should be triggered
        assert fallback_manager.circuit_breaker_state[ProviderType.GLM] == True

    def test_blacklist_provider(self, fallback_manager, mock_providers):
        """Test provider blacklisting"""
        fallback_manager.providers = mock_providers
        fallback_manager.blacklisted_providers = set()

        # Record 5 failures to trigger blacklist
        for _ in range(5):
            fallback_manager.record_failure(
                ProviderType.GLM,
                FailureType.API_ERROR,
                "API error"
            )

        # Provider should be blacklisted
        assert ProviderType.GLM in fallback_manager.blacklisted_providers

    def test_get_recent_failures(self, fallback_manager):
        """Test getting recent failures"""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(minutes=10)

        # Create failure records
        old_failure = FailureRecord(
            provider=ProviderType.GLM,
            failure_type=FailureType.API_ERROR,
            timestamp=old_time,
            error_message="Old error"
        )

        recent_failure = FailureRecord(
            provider=ProviderType.GLM,
            failure_type=FailureType.TIMEOUT,
            timestamp=now,
            error_message="Recent error"
        )

        fallback_manager.failure_history[ProviderType.GLM] = [old_failure, recent_failure]

        # Get recent failures (last 5 minutes)
        recent = fallback_manager._get_recent_failures(ProviderType.GLM, minutes=5)

        assert len(recent) == 1
        assert recent[0].error_message == "Recent error"

    def test_get_failure_statistics(self, fallback_manager, mock_providers):
        """Test getting failure statistics"""
        fallback_manager.providers = mock_providers

        # Add some failures
        fallback_manager.failure_history[ProviderType.GLM] = [
            FailureRecord(
                provider=ProviderType.GLM,
                failure_type=FailureType.API_ERROR,
                timestamp=datetime.now(timezone.utc),
                error_message="Error 1"
            ),
            FailureRecord(
                provider=ProviderType.GLM,
                failure_type=FailureType.TIMEOUT,
                timestamp=datetime.now(timezone.utc),
                error_message="Error 2"
            )
        ]

        stats = fallback_manager.get_failure_statistics()

        assert "providers" in stats
        assert "total_blacklisted" in stats
        assert "glm" in stats["providers"]
        assert stats["providers"]["glm"]["total_failures_last_hour"] == 2

    def test_reset_failure_tracking(self, fallback_manager, mock_providers):
        """Test resetting failure tracking"""
        fallback_manager.providers = mock_providers
        fallback_manager.failure_history[ProviderType.GLM] = [
            FailureRecord(
                provider=ProviderType.GLM,
                failure_type=FailureType.API_ERROR,
                timestamp=datetime.now(timezone.utc),
                error_message="Error"
            )
        ]
        fallback_manager.circuit_breaker_state[ProviderType.GLM] = True
        fallback_manager.blacklisted_providers.add(ProviderType.GLM)

        # Reset specific provider
        fallback_manager.reset_failure_tracking(ProviderType.GLM)

        assert len(fallback_manager.failure_history[ProviderType.GLM]) == 0
        assert fallback_manager.circuit_breaker_state[ProviderType.GLM] == False
        assert ProviderType.GLM not in fallback_manager.blacklisted_providers

    def test_get_provider_health_summary(self, fallback_manager, mock_providers):
        """Test getting provider health summary"""
        await fallback_manager.initialize(mock_providers)

        with patch('multi_provider_router.routing.fallback_manager.health_checker') as mock_health:
            mock_health.is_healthy.return_value = True
            mock_health.get_provider_health_score.return_value = 1.0

            summary = fallback_manager.get_provider_health_summary()

            assert "total_providers" in summary
            assert "available_providers" in summary
            assert "unavailable_providers" in summary
            assert summary["total_providers"] == 2

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, fallback_manager, mock_providers):
        """Test circuit breaker automatic recovery"""
        fallback_manager.providers = mock_providers
        fallback_manager.circuit_breaker_state[ProviderType.GLM] = True

        # Schedule recovery (very short timeout for testing)
        fallback_manager.circuit_breaker_timeout_seconds = 0.1

        await fallback_manager._schedule_circuit_breaker_recovery(ProviderType.GLM)

        # Wait for recovery
        await asyncio.sleep(0.2)

        assert fallback_manager.circuit_breaker_state[ProviderType.GLM] == False


# ============================================================================
# Failure Type Tests
# ============================================================================

class TestFailureTypes:
    """Test different failure types"""

    @pytest.mark.asyncio
    async def test_timeout_failure(self, fallback_manager, glm_config):
        """Test timeout failure handling"""
        provider = GLMProvider(glm_config)
        fallback_manager.providers = {ProviderType.GLM: provider}
        fallback_manager.failure_history[ProviderType.GLM] = []
        fallback_manager.circuit_breaker_state[ProviderType.GLM] = False

        fallback_manager.record_failure(
            ProviderType.GLM,
            FailureType.TIMEOUT,
            "Request timed out after 30 seconds"
        )

        assert len(fallback_manager.failure_history[ProviderType.GLM]) == 1
        assert fallback_manager.failure_history[ProviderType.GLM][0].failure_type == FailureType.TIMEOUT

    @pytest.mark.asyncio
    async def test_rate_limit_failure(self, fallback_manager, glm_config):
        """Test rate limit failure handling"""
        provider = GLMProvider(glm_config)
        fallback_manager.providers = {ProviderType.GLM: provider}
        fallback_manager.failure_history[ProviderType.GLM] = []

        fallback_manager.record_failure(
            ProviderType.GLM,
            FailureType.RATE_LIMIT,
            "Rate limit exceeded: 429"
        )

        failure = fallback_manager.failure_history[ProviderType.GLM][0]
        assert failure.failure_type == FailureType.RATE_LIMIT

    @pytest.mark.asyncio
    async def test_authentication_failure(self, fallback_manager, glm_config):
        """Test authentication failure handling"""
        provider = GLMProvider(glm_config)
        fallback_manager.providers = {ProviderType.GLM: provider}
        fallback_manager.failure_history[ProviderType.GLM] = []

        fallback_manager.record_failure(
            ProviderType.GLM,
            FailureType.AUTHENTICATION,
            "Invalid API key"
        )

        failure = fallback_manager.failure_history[ProviderType.GLM][0]
        assert failure.failure_type == FailureType.AUTHENTICATION


# ============================================================================
# Integration Tests
# ============================================================================

class TestFallbackIntegration:
    """Integration tests for fallback functionality"""

    @pytest.mark.asyncio
    async def test_complete_failover_workflow(
        self,
        fallback_manager,
        mock_providers,
        simple_request
    ):
        """Test complete failover workflow"""
        await fallback_manager.initialize(mock_providers)

        with patch('multi_provider_router.routing.fallback_manager.health_checker') as mock_health, \
             patch('multi_provider_router.routing.fallback_manager.rate_limiter') as mock_rate:

            mock_health.is_healthy.return_value = True
            mock_health.get_provider_health_score.return_value = 1.0
            mock_rate.check_rate_limit = AsyncMock(return_value=(True, {}))

            # GLM fails repeatedly
            for _ in range(5):
                fallback_manager.record_failure(
                    ProviderType.GLM,
                    FailureType.API_ERROR,
                    "API Error"
                )

            # GLM should be blacklisted
            assert ProviderType.GLM in fallback_manager.blacklisted_providers

            # Get fallback chain - should not include GLM
            chain = await fallback_manager.get_fallback_chain(ProviderType.OPENAI, simple_request)

            assert ProviderType.GLM not in chain


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
