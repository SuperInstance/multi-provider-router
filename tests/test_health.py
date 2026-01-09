"""
Tests for health monitoring system
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from multi_provider_router.models import ProviderType, HealthCheck, ProviderConfig
from multi_provider_router.utils.health_checker import HealthChecker


# ============================================================================
# Health Checker Tests
# ============================================================================

class TestHealthChecker:
    """Test health checker"""

    @pytest.fixture
    def health_checker(self):
        """Create a health checker instance"""
        return HealthChecker()

    def test_register_provider(self, health_checker, glm_config):
        """Test registering a provider"""
        health_checker.register_provider(glm_config)

        assert ProviderType.GLM in health_checker._provider_configs
        assert ProviderType.GLM in health_checker._health_status

        health_status = health_checker._health_status[ProviderType.GLM]
        assert health_status.provider == ProviderType.GLM
        assert health_status.is_healthy == False  # Initially unhealthy until checked

    def test_get_health_status(self, health_checker, glm_config):
        """Test getting health status for a provider"""
        health_checker.register_provider(glm_config)

        status = health_checker.get_health_status(ProviderType.GLM)

        assert isinstance(status, HealthCheck)
        assert status.provider == ProviderType.GLM

    def test_get_all_health_status(self, health_checker, glm_config, openai_config):
        """Test getting all health statuses"""
        health_checker.register_provider(glm_config)
        health_checker.register_provider(openai_config)

        all_status = health_checker.get_all_health_status()

        assert len(all_status) == 2
        assert ProviderType.GLM in all_status
        assert ProviderType.OPENAI in all_status

    def test_is_healthy(self, health_checker, glm_config):
        """Test checking if provider is healthy"""
        health_checker.register_provider(glm_config)

        # Initially unhealthy (no health check performed)
        assert health_checker.is_healthy(ProviderType.GLM) == False

        # Set healthy status
        health_checker._health_status[ProviderType.GLM] = HealthCheck(
            provider=ProviderType.GLM,
            model="glm-4",
            is_healthy=True,
            response_time_ms=500,
            timestamp=datetime.now(timezone.utc)
        )

        assert health_checker.is_healthy(ProviderType.GLM) == True

    def test_get_healthy_providers(self, health_checker, glm_config, openai_config):
        """Test getting list of healthy providers"""
        health_checker.register_provider(glm_config)
        health_checker.register_provider(openai_config)

        # Set GLM as healthy, OpenAI as unhealthy
        health_checker._health_status[ProviderType.GLM] = HealthCheck(
            provider=ProviderType.GLM,
            model="glm-4",
            is_healthy=True,
            response_time_ms=500,
            timestamp=datetime.now(timezone.utc)
        )

        health_checker._health_status[ProviderType.OPENAI] = HealthCheck(
            provider=ProviderType.OPENAI,
            model="gpt-3.5-turbo",
            is_healthy=False,
            response_time_ms=0,
            timestamp=datetime.now(timezone.utc)
        )

        healthy = health_checker.get_healthy_providers()

        assert ProviderType.GLM in healthy
        assert ProviderType.OPENAI not in healthy

    def test_get_provider_health_score(self, health_checker, glm_config):
        """Test getting provider health score"""
        health_checker.register_provider(glm_config)

        # Set healthy status with good response time
        health_checker._health_status[ProviderType.GLM] = HealthCheck(
            provider=ProviderType.GLM,
            model="glm-4",
            is_healthy=True,
            response_time_ms=300,
            timestamp=datetime.now(timezone.utc)
        )

        score = health_checker.get_provider_health_score(ProviderType.GLM)

        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be good score

    def test_get_provider_health_score_unhealthy(self, health_checker, glm_config):
        """Test health score for unhealthy provider"""
        health_checker.register_provider(glm_config)

        # Set unhealthy status
        health_checker._health_status[ProviderType.GLM] = HealthCheck(
            provider=ProviderType.GLM,
            model="glm-4",
            is_healthy=False,
            response_time_ms=0,
            timestamp=datetime.now(timezone.utc)
        )

        score = health_checker.get_provider_health_score(ProviderType.GLM)

        assert score == 0.0

    def test_get_health_summary(self, health_checker, glm_config, openai_config):
        """Test getting health summary"""
        health_checker.register_provider(glm_config)
        health_checker.register_provider(openai_config)

        # Set health statuses
        now = datetime.now(timezone.utc)
        health_checker._health_status[ProviderType.GLM] = HealthCheck(
            provider=ProviderType.GLM,
            model="glm-4",
            is_healthy=True,
            response_time_ms=500,
            timestamp=now
        )

        health_checker._health_status[ProviderType.OPENAI] = HealthCheck(
            provider=ProviderType.OPENAI,
            model="gpt-3.5-turbo",
            is_healthy=False,
            response_time_ms=0,
            error_message="Connection error",
            timestamp=now
        )

        summary = health_checker.get_health_summary()

        assert "total_providers" in summary
        assert "healthy_providers" in summary
        assert "health_percentage" in summary
        assert "providers" in summary

        assert summary["total_providers"] == 2
        assert summary["healthy_providers"] == 1
        assert summary["health_percentage"] == 50.0

    @pytest.mark.asyncio
    async def test_manual_health_check(self, health_checker, glm_config):
        """Test manual health check"""
        health_checker.register_provider(glm_config)

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "test",
                "choices": [{"message": {"content": "OK"}}],
                "usage": {"total_tokens": 10}
            }
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await health_checker.manual_health_check(ProviderType.GLM)

            assert result.is_healthy == True
            assert result.response_time_ms >= 0

    def test_create_test_request(self, health_checker, glm_config):
        """Test creating test requests for different providers"""
        glm_request = health_checker._create_test_request(glm_config)

        assert "model" in glm_request
        assert "messages" in glm_request
        assert glm_request["model"] == "glm-4"

    def test_get_endpoint_url(self, health_checker, glm_config, claude_config):
        """Test getting endpoint URLs for different providers"""
        glm_url = health_checker._get_endpoint_url(glm_config)
        assert glm_url.endswith("/chat/completions")

        claude_url = health_checker._get_endpoint_url(claude_config)
        assert claude_url.endswith("/v1/messages")

    def test_get_headers(self, health_checker, glm_config, claude_config):
        """Test getting headers for different providers"""
        glm_headers = health_checker._get_headers(glm_config)
        assert "Authorization" in glm_headers
        assert glm_headers["Authorization"] == f"Bearer {glm_config.api_key}"

        claude_headers = health_checker._get_headers(claude_config)
        assert "x-api-key" in claude_headers
        assert claude_headers["x-api-key"] == claude_config.api_key


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
