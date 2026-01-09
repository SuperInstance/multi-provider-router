"""
End-to-end integration tests for the multi-provider router
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import time

from multi_provider_router.models import (
    ProviderType,
    GenerationRequest,
    GenerationResponse,
    ChatMessage,
    PriorityLevel
)
from multi_provider_router.routing.router import Router
from multi_provider_router.routing.decision_engine import RoutingDecisionEngine
from multi_provider_router.routing.load_balancer import LoadBalancer
from multi_provider_router.routing.fallback_manager import FallbackManager
from multi_provider_router.providers.glm_provider import GLMProvider
from multi_provider_router.providers.openai_provider import OpenAIProvider


# ============================================================================
# End-to-End Workflow Tests
# ============================================================================

class TestEndToEndWorkflows:
    """Test complete request workflows"""

    @pytest.mark.asyncio
    async def test_complete_request_flow(self, glm_config, simple_request):
        """Test complete request flow from start to finish"""
        # Create provider
        provider = GLMProvider(glm_config)

        # Mock HTTP client
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "test-id",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "glm-4",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Test response"
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                }
            }
            mock_response.raise_for_status = Mock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # Generate response
            response = await provider.generate(simple_request)

            assert isinstance(response, GenerationResponse)
            assert response.content == "Test response"
            assert response.provider_used == ProviderType.GLM
            assert response.input_tokens == 10
            assert response.output_tokens == 20
            assert response.cost_usd > 0

    @pytest.mark.asyncio
    async def test_routing_and_generation_workflow(self, glm_config, openai_config, simple_request):
        """Test workflow combining routing and generation"""
        # Setup
        decision_engine = RoutingDecisionEngine()
        load_balancer = LoadBalancer()

        providers = {
            ProviderType.GLM: GLMProvider(glm_config),
            ProviderType.OPENAI: OpenAIProvider(openai_config)
        }

        # Register providers
        for provider in providers.values():
            decision_engine.register_provider(provider)

        await load_balancer.initialize(providers)

        with patch('multi_provider_router.routing.decision_engine.health_checker') as mock_health, \
             patch('multi_provider_router.routing.decision_engine.rate_limiter') as mock_rate, \
             patch('httpx.AsyncClient') as mock_httpx:

            # Mock health and rate limiting
            mock_health.is_healthy.return_value = True
            mock_health.get_provider_health_score.return_value = 1.0
            mock_rate.check_rate_limit = AsyncMock(return_value=(True, {'minute': 60}))

            # Mock HTTP response
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "test-id",
                "model": "glm-4",
                "choices": [{
                    "message": {"content": "Routing test response"}
                }],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                }
            }
            mock_response.raise_for_status = Mock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_httpx.return_value = mock_client

            # Get routing decision
            decision = await decision_engine.select_provider(simple_request)

            # Generate using selected provider
            selected_provider = providers[decision.selected_provider]
            response = await selected_provider.generate(simple_request)

            assert response.content == "Routing test response"
            assert response.provider_used == decision.selected_provider

    @pytest.mark.asyncio
    async def test_fallback_workflow(self, glm_config, openai_config, simple_request):
        """Test fallback workflow when primary fails"""
        providers = {
            ProviderType.GLM: GLMProvider(glm_config),
            ProviderType.OPENAI: OpenAIProvider(openai_config)
        }

        fallback_manager = FallbackManager()
        await fallback_manager.initialize(providers)

        # Simulate GLM failures
        for _ in range(5):
            fallback_manager.record_failure(
                ProviderType.GLM,
                "api_error",
                "GLM API error"
            )

        # Get fallback chain
        with patch('multi_provider_router.routing.fallback_manager.health_checker') as mock_health, \
             patch('multi_provider_router.routing.fallback_manager.rate_limiter') as mock_rate:

            mock_health.is_healthy.return_value = True
            mock_health.get_provider_health_score.return_value = 1.0
            mock_rate.check_rate_limit = AsyncMock(return_value=(True, {}))

            chain = await fallback_manager.get_fallback_chain(ProviderType.GLM, simple_request)

            # Should fallback to OpenAI
            assert ProviderType.OPENAI in chain
            assert ProviderType.GLM not in chain

    @pytest.mark.asyncio
    async def test_cached_response_workflow(self, glm_config, simple_request, mock_redis):
        """Test workflow with cached responses"""
        from multi_provider_router.utils.cache import CacheManager

        cache_manager = CacheManager()
        cache_manager._redis = mock_redis

        # First call - cache miss
        mock_redis.get.return_value = None
        cached = await cache_manager.get_cached_response(simple_request)
        assert cached is None

        # Cache a response
        response = GenerationResponse(
            request_id="cached-req-1",
            content="Cached response",
            provider_used=ProviderType.GLM,
            model_used="glm-4",
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.001,
            processing_time_ms=500,
            cached=True
        )

        await cache_manager.cache_response(simple_request, response)

        # Second call - cache hit (mock)
        import json
        mock_redis.get.return_value = json.dumps({
            "request_id": response.request_id,
            "content": response.content,
            "provider_used": response.provider_used.value,
            "model_used": response.model_used,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost_usd": response.cost_usd,
            "processing_time_ms": response.processing_time_ms,
            "cached": True
        })

        cached = await cache_manager.get_cached_response(simple_request)
        assert cached is not None
        assert cached.content == "Cached response"


# ============================================================================
# Performance Tracking Integration
# ============================================================================

class TestPerformanceTrackingIntegration:
    """Test performance tracking across components"""

    @pytest.mark.asyncio
    async def test_metrics_tracking_workflow(self, glm_config, simple_request):
        """Test metrics tracking throughout request lifecycle"""
        from multi_provider_router.utils.metrics import metrics
        from multi_provider_router.routing.load_balancer import LoadBalancer, ProviderLoad

        metrics.reset_metrics()  # Start fresh

        # Create provider and load balancer
        provider = GLMProvider(glm_config)
        load_balancer = LoadBalancer()

        load_balancer.providers = {ProviderType.GLM: provider}
        load_balancer.provider_loads[ProviderType.GLM] = ProviderLoad(
            provider=ProviderType.GLM,
            active_requests=0,
            total_requests_today=0,
            average_response_time_ms=1000.0,
            success_rate=1.0,
            last_used=datetime.now(timezone.utc),
            cost_efficiency_score=0.8
        )

        # Simulate request
        request_id = "metrics-req-123"

        # Start tracking
        metrics.start_request(request_id, ProviderType.GLM, "glm-4")
        load_balancer.start_request(ProviderType.GLM, request_id)

        # Complete request
        metrics.complete_request(
            request_id=request_id,
            input_tokens=100,
            output_tokens=200,
            cost_usd=0.001,
            success=True
        )
        load_balancer.end_request(ProviderType.GLM, request_id, success=True, response_time_ms=500)

        # Check metrics
        stats = metrics.get_provider_stats(ProviderType.GLM)
        assert stats['total_requests'] == 1
        assert stats['successful_requests'] == 1
        assert stats['total_cost_usd'] == 0.001

        # Check load balancer stats
        load_stats = load_balancer.get_load_statistics()
        assert load_stats['total_requests_today'] == 1


# ============================================================================
# Error Handling Integration
# ============================================================================

class TestErrorHandlingIntegration:
    """Test error handling across components"""

    @pytest.mark.asyncio
    async def test_provider_failure_handling(self, glm_config, simple_request):
        """Test handling provider failure gracefully"""
        from multi_provider_router.routing.fallback_manager import FallbackManager

        provider = GLMProvider(glm_config)
        fallback_manager = FallbackManager()
        fallback_manager.providers = {ProviderType.GLM: provider}
        fallback_manager.failure_history[ProviderType.GLM] = []
        fallback_manager.circuit_breaker_state[ProviderType.GLM] = False

        # Simulate API failure
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.raise_for_status = Mock(side_effect=Exception("API Error"))
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # Attempt generation (should fail)
            with pytest.raises(Exception):
                await provider.generate(simple_request)

            # Record failure
            fallback_manager.record_failure(
                ProviderType.GLM,
                "api_error",
                "API Error"
            )

            # Check failure was recorded
            assert len(fallback_manager.failure_history[ProviderType.GLM]) == 1


# ============================================================================
# Concurrent Request Handling
# ============================================================================

class TestConcurrentRequests:
    """Test handling concurrent requests"""

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self, glm_config):
        """Test handling multiple concurrent requests"""
        import asyncio

        provider = GLMProvider(glm_config)

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "test-id",
                "model": "glm-4",
                "choices": [{"message": {"content": "Response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
            }
            mock_response.raise_for_status = Mock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # Create multiple requests
            requests = [
                GenerationRequest(
                    messages=[ChatMessage(role="user", content=f"Request {i}")],
                    temperature=0.7
                )
                for i in range(5)
            ]

            # Execute concurrently
            tasks = [provider.generate(req) for req in requests]
            responses = await asyncio.gather(*tasks)

            assert len(responses) == 5
            assert all(isinstance(r, GenerationResponse) for r in responses)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
