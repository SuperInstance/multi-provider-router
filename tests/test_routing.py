"""
Comprehensive tests for routing engine and load balancer
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import time

from multi_provider_router.models import (
    ProviderType,
    GenerationRequest,
    ChatMessage,
    PriorityLevel,
    RoutingDecision
)
from multi_provider_router.routing.decision_engine import RoutingDecisionEngine, ProviderScore
from multi_provider_router.routing.load_balancer import LoadBalancer, ProviderLoad
from multi_provider_router.providers.glm_provider import GLMProvider
from multi_provider_router.providers.openai_provider import OpenAIProvider


# ============================================================================
# Decision Engine Tests
# ============================================================================

class TestRoutingDecisionEngine:
    """Test routing decision engine"""

    @pytest.fixture
    def decision_engine(self):
        """Create a decision engine instance"""
        return RoutingDecisionEngine()

    @pytest.fixture
    def mock_providers(self, glm_config, openai_config):
        """Create mock providers"""
        glm = GLMProvider(glm_config)
        openai = OpenAIProvider(openai_config)
        return {
            ProviderType.GLM: glm,
            ProviderType.OPENAI: openai
        }

    def test_engine_initialization(self, decision_engine):
        """Test engine initializes correctly"""
        assert decision_engine.providers == {}
        assert decision_engine.cost_sensitivity >= 0
        assert decision_engine.quality_weight >= 0

    def test_register_provider(self, decision_engine, glm_config):
        """Test provider registration"""
        provider = GLMProvider(glm_config)
        decision_engine.register_provider(provider)

        assert ProviderType.GLM in decision_engine.providers
        assert ProviderType.GLM in decision_engine._provider_success_rates
        assert decision_engine._provider_success_rates[ProviderType.GLM] == 1.0

    def test_analyze_request(self, decision_engine, simple_request):
        """Test request analysis"""
        analysis = decision_engine._analyze_request(simple_request)

        assert "type" in analysis
        assert "complexity" in analysis
        assert "estimated_tokens" in analysis
        assert 0.0 <= analysis["complexity"] <= 1.0

    def test_classify_request_type(self, decision_engine):
        """Test request type classification"""
        # Coding request
        coding_request = GenerationRequest(
            messages=[ChatMessage(role="user", content="Write a Python function")]
        )
        assert decision_engine._classify_request_type("Write a Python function") in ["coding", "general"]

        # Conversation request
        conv_request = GenerationRequest(
            messages=[ChatMessage(role="user", content="Hello, how are you?")]
        )
        assert decision_engine._classify_request_type("Hello, how are you?") in ["conversation", "general"]

    def test_calculate_complexity(self, decision_engine):
        """Test complexity calculation"""
        # Simple request
        simple = "Hello"
        complexity = decision_engine._calculate_complexity(simple, 10)
        assert 0.0 <= complexity <= 0.5

        # Complex request
        complex_text = "Analyze this in comprehensive detail step by step. ```code``` complex reasoning"
        complexity = decision_engine._calculate_complexity(complex_text, 5000)
        assert complexity > 0.3

    @pytest.mark.asyncio
    async def test_select_provider_basic(self, decision_engine, mock_providers, simple_request):
        """Test basic provider selection"""
        for provider in mock_providers.values():
            decision_engine.register_provider(provider)

        with patch('multi_provider_router.routing.decision_engine.health_checker') as mock_health, \
             patch('multi_provider_router.routing.decision_engine.rate_limiter') as mock_rate:

            mock_health.is_healthy.return_value = True
            mock_health.get_provider_health_score.return_value = 1.0
            mock_rate.check_rate_limit = AsyncMock(return_value=(True, {'minute': 60, 'hour': 3000, 'day': 50000}))

            decision = await decision_engine.select_provider(simple_request)

            assert isinstance(decision, RoutingDecision)
            assert decision.selected_provider in mock_providers
            assert decision.routing_score >= 0.0
            assert len(decision.reasoning) > 0

    @pytest.mark.asyncio
    async def test_select_provider_with_budget(self, decision_engine, mock_providers, simple_request):
        """Test provider selection with budget constraint"""
        for provider in mock_providers.values():
            decision_engine.register_provider(provider)

        with patch('multi_provider_router.routing.decision_engine.health_checker') as mock_health, \
             patch('multi_provider_router.routing.decision_engine.rate_limiter') as mock_rate:

            mock_health.is_healthy.return_value = True
            mock_health.get_provider_health_score.return_value = 1.0
            mock_rate.check_rate_limit = AsyncMock(return_value=(True, {'minute': 60, 'hour': 3000, 'day': 50000}))

            # Very low budget
            decision = await decision_engine.select_provider(simple_request, budget_remaining=0.0001)

            assert decision.selected_provider in mock_providers
            assert decision.cost_estimate_usd <= 0.0001

    @pytest.mark.asyncio
    async def test_select_provider_no_candidates(self, decision_engine, simple_request):
        """Test provider selection when no candidates available"""
        with patch('multi_provider_router.routing.decision_engine.health_checker') as mock_health, \
             patch('multi_provider_router.routing.decision_engine.rate_limiter') as mock_rate:

            mock_health.is_healthy.return_value = False
            mock_rate.check_rate_limit = AsyncMock(return_value=(False, {}))

            with pytest.raises(ValueError, match="No suitable providers available"):
                await decision_engine.select_provider(simple_request)

    @pytest.mark.asyncio
    async def test_calculate_provider_score(self, decision_engine, mock_providers, simple_request):
        """Test provider scoring"""
        glm = mock_providers[ProviderType.GLM]
        decision_engine.register_provider(glm)

        with patch('multi_provider_router.routing.decision_engine.health_checker') as mock_health, \
             patch('multi_provider_router.routing.decision_engine.rate_limiter') as mock_rate:

            mock_health.is_healthy.return_value = True
            mock_health.get_provider_health_score.return_value = 0.9
            mock_rate.check_rate_limit = AsyncMock(return_value=(True, {'minute': 60}))

            score_data = await decision_engine._calculate_provider_score(
                glm,
                simple_request,
                decision_engine._analyze_request(simple_request)
            )

            assert isinstance(score_data, ProviderScore)
            assert 0.0 <= score_data.score <= 1.0
            assert score_data.provider == ProviderType.GLM
            assert score_data.cost_estimate >= 0
            assert len(score_data.reasoning) > 0

    def test_update_provider_performance(self, decision_engine, glm_config):
        """Test provider performance tracking"""
        provider = GLMProvider(glm_config)
        decision_engine.register_provider(provider)

        # Update with successful request
        decision_engine.update_provider_performance(
            ProviderType.GLM,
            success=True,
            response_time_ms=500
        )

        assert ProviderType.GLM in decision_engine._provider_success_rates
        assert ProviderType.GLM in decision_engine._provider_response_times
        assert decision_engine._provider_response_times[ProviderType.GLM] < 1000.0

        # Update with failed request
        decision_engine.update_provider_performance(
            ProviderType.GLM,
            success=False,
            response_time_ms=2000
        )

        assert decision_engine._provider_success_rates[ProviderType.GLM] < 1.0

    def test_get_routing_statistics(self, decision_engine, glm_config):
        """Test getting routing statistics"""
        provider = GLMProvider(glm_config)
        decision_engine.register_provider(provider)

        stats = decision_engine.get_routing_statistics()

        assert "registered_providers" in stats
        assert "provider_success_rates" in stats
        assert "provider_response_times" in stats
        assert ProviderType.GLM in stats["registered_providers"]


# ============================================================================
# Load Balancer Tests
# ============================================================================

class TestLoadBalancer:
    """Test load balancer"""

    @pytest.fixture
    def load_balancer(self):
        """Create a load balancer instance"""
        return LoadBalancer()

    @pytest.fixture
    def mock_providers(self, glm_config, openai_config):
        """Create mock providers"""
        return {
            ProviderType.GLM: GLMProvider(glm_config),
            ProviderType.OPENAI: OpenAIProvider(openai_config)
        }

    @pytest.mark.asyncio
    async def test_initialize(self, load_balancer, mock_providers):
        """Test load balancer initialization"""
        await load_balancer.initialize(mock_providers)

        assert len(load_balancer.providers) == 2
        assert ProviderType.GLM in load_balancer.provider_loads
        assert ProviderType.OPENAI in load_balancer.provider_loads

        # Check initial load state
        glm_load = load_balancer.provider_loads[ProviderType.GLM]
        assert glm_load.active_requests == 0
        assert glm_load.total_requests_today == 0
        assert glm_load.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_select_provider_round_robin(self, load_balancer, mock_providers):
        """Test round-robin provider selection"""
        await load_balancer.initialize(mock_providers)
        load_balancer.set_load_balancing_strategy("round_robin")

        available = list(mock_providers.keys())

        # First selection
        selected1 = await load_balancer.select_provider(available)
        assert selected1 in available

        # Second selection (should be different)
        selected2 = await load_balancer.select_provider(available)
        assert selected2 in available

    @pytest.mark.asyncio
    async def test_select_provider_weighted(self, load_balancer, mock_providers):
        """Test weighted provider selection"""
        await load_balancer.initialize(mock_providers)
        load_balancer.set_load_balancing_strategy("weighted")

        available = list(mock_providers.keys())

        # Select multiple times and check distribution
        selections = []
        for _ in range(10):
            selected = await load_balancer.select_provider(available)
            selections.append(selected)

        assert all(s in available for s in selections)

    @pytest.mark.asyncio
    async def test_select_provider_least_connections(self, load_balancer, mock_providers):
        """Test least connections provider selection"""
        await load_balancer.initialize(mock_providers)
        load_balancer.set_load_balancing_strategy("least_connections")

        available = list(mock_providers.keys())

        # Start some requests on GLM
        load_balancer.start_request(ProviderType.GLM, "req1")
        load_balancer.start_request(ProviderType.GLM, "req2")

        # Should select OpenAI (fewer connections)
        selected = await load_balancer.select_provider(available)
        assert selected == ProviderType.OPENAI

    @pytest.mark.asyncio
    async def test_select_provider_adaptive(self, load_balancer, mock_providers):
        """Test adaptive provider selection"""
        await load_balancer.initialize(mock_providers)
        load_balancer.set_load_balancing_strategy("adaptive")

        available = list(mock_providers.keys())

        # Select for critical priority
        selected = await load_balancer.select_provider(
            available,
            priority=PriorityLevel.CRITICAL
        )

        assert selected in available

    def test_is_provider_at_capacity(self, load_balancer, glm_config):
        """Test provider capacity checking"""
        provider = GLMProvider(glm_config)

        load = ProviderLoad(
            provider=ProviderType.GLM,
            active_requests=100,  # Over capacity
            total_requests_today=1000,
            average_response_time_ms=500.0,
            success_rate=1.0,
            last_used=datetime.now(timezone.utc),
            cost_efficiency_score=0.8
        )

        load_balancer.provider_loads[ProviderType.GLM] = load

        assert load_balancer._is_provider_at_capacity(ProviderType.GLM) == True

    def test_start_request(self, load_balancer, glm_config):
        """Test starting request tracking"""
        provider = GLMProvider(glm_config)
        load_balancer.providers[ProviderType.GLM] = provider

        load = ProviderLoad(
            provider=ProviderType.GLM,
            active_requests=0,
            total_requests_today=0,
            average_response_time_ms=1000.0,
            success_rate=1.0,
            last_used=datetime.now(timezone.utc),
            cost_efficiency_score=0.8
        )
        load_balancer.provider_loads[ProviderType.GLM] = load

        load_balancer.start_request(ProviderType.GLM, "test-request-123")

        assert load_balancer.provider_loads[ProviderType.GLM].active_requests == 1
        assert load_balancer.provider_loads[ProviderType.GLM].total_requests_today == 1

    def test_end_request(self, load_balancer, glm_config):
        """Test ending request tracking"""
        provider = GLMProvider(glm_config)
        load_balancer.providers[ProviderType.GLM] = provider

        load = ProviderLoad(
            provider=ProviderType.GLM,
            active_requests=1,
            total_requests_today=1,
            average_response_time_ms=1000.0,
            success_rate=1.0,
            last_used=datetime.now(timezone.utc),
            cost_efficiency_score=0.8
        )
        load_balancer.provider_loads[ProviderType.GLM] = load

        load_balancer.end_request(
            ProviderType.GLM,
            "test-request-123",
            success=True,
            response_time_ms=500
        )

        assert load_balancer.provider_loads[ProviderType.GLM].active_requests == 0
        # Response time should be updated (moving average)
        assert load_balancer.provider_loads[ProviderType.GLM].average_response_time_ms < 1000.0

    def test_get_load_statistics(self, load_balancer, mock_providers):
        """Test getting load statistics"""
        # Initialize with providers
        load_balancer.providers = mock_providers
        load_balancer.provider_loads[ProviderType.GLM] = ProviderLoad(
            provider=ProviderType.GLM,
            active_requests=5,
            total_requests_today=100,
            average_response_time_ms=800.0,
            success_rate=0.95,
            last_used=datetime.now(timezone.utc),
            cost_efficiency_score=0.9
        )

        stats = load_balancer.get_load_statistics()

        assert "total_providers" in stats
        assert "strategy" in stats
        assert "total_active_requests" in stats
        assert stats["total_active_requests"] == 5
        assert "glm" in stats["providers"]

    def test_set_load_balancing_strategy(self, load_balancer):
        """Test setting load balancing strategy"""
        # Valid strategy
        load_balancer.set_load_balancing_strategy("weighted")
        assert load_balancer.load_balancing_strategy == "weighted"

        # Invalid strategy
        with pytest.raises(ValueError, match="Invalid strategy"):
            load_balancer.set_load_balancing_strategy("invalid_strategy")

    def test_update_provider_weight(self, load_balancer):
        """Test updating provider weight"""
        load_balancer.provider_weights[ProviderType.GLM] = 1.0

        load_balancer.update_provider_weight(ProviderType.GLM, 0.5)

        assert load_balancer.provider_weights[ProviderType.GLM] == 0.5

        # Test minimum weight
        load_balancer.update_provider_weight(ProviderType.GLM, 0.05)

        assert load_balancer.provider_weights[ProviderType.GLM] == 0.1

    def test_rebalance_weights(self, load_balancer, glm_config):
        """Test automatic weight rebalancing"""
        provider = GLMProvider(glm_config)

        load_balancer.providers[ProviderType.GLM] = provider
        load_balancer.provider_weights[ProviderType.GLM] = 1.0

        load = ProviderLoad(
            provider=ProviderType.GLM,
            active_requests=0,
            total_requests_today=100,
            average_response_time_ms=500.0,
            success_rate=1.0,
            last_used=datetime.now(timezone.utc),
            cost_efficiency_score=0.9
        )
        load_balancer.provider_loads[ProviderType.GLM] = load

        load_balancer.rebalance_weights()

        # Weight should be adjusted based on performance
        # (high success rate and good response time should maintain/increase weight)
        assert load_balancer.provider_weights[ProviderType.GLM] >= 0.1

    def test_get_provider_recommendations(self, load_balancer, glm_config):
        """Test getting provider optimization recommendations"""
        provider = GLMProvider(glm_config)

        load_balancer.providers[ProviderType.GLM] = provider

        # Create a problematic load
        load = ProviderLoad(
            provider=ProviderType.GLM,
            active_requests=40,
            total_requests_today=5,
            average_response_time_ms=2500.0,
            success_rate=0.75,
            last_used=datetime.now(timezone.utc),
            cost_efficiency_score=0.4
        )
        load_balancer.provider_loads[ProviderType.GLM] = load

        recommendations = load_balancer.get_provider_recommendations()

        assert isinstance(recommendations, list)
        if recommendations:
            assert "provider" in recommendations[0]
            assert "issues" in recommendations[0]


# ============================================================================
# Integration Tests
# ============================================================================

class TestRoutingIntegration:
    """Integration tests for routing components"""

    @pytest.mark.asyncio
    async def test_decision_engine_with_load_balancer(
        self,
        decision_engine,
        load_balancer,
        mock_providers,
        simple_request
    ):
        """Test decision engine and load balancer working together"""
        # Register providers
        for provider in mock_providers.values():
            decision_engine.register_provider(provider)

        await load_balancer.initialize(mock_providers)

        with patch('multi_provider_router.routing.decision_engine.health_checker') as mock_health, \
             patch('multi_provider_router.routing.decision_engine.rate_limiter') as mock_rate:

            mock_health.is_healthy.return_value = True
            mock_health.get_provider_health_score.return_value = 1.0
            mock_rate.check_rate_limit = AsyncMock(return_value=(True, {'minute': 60}))

            # Get routing decision
            decision = await decision_engine.select_provider(simple_request)

            # Use load balancer to select provider
            available = [decision.selected_provider]
            selected = await load_balancer.select_provider(available)

            assert selected == decision.selected_provider

    @pytest.mark.asyncio
    async def test_performance_tracking_integration(
        self,
        decision_engine,
        load_balancer,
        glm_config,
        simple_request
    ):
        """Test performance tracking across routing and load balancing"""
        provider = GLMProvider(glm_config)

        decision_engine.register_provider(provider)
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
        request_id = "test-req-123"
        load_balancer.start_request(ProviderType.GLM, request_id)
        load_balancer.end_request(ProviderType.GLM, request_id, success=True, response_time_ms=500)
        decision_engine.update_provider_performance(ProviderType.GLM, success=True, response_time_ms=500)

        # Check both systems updated
        load_stats = load_balancer.get_load_statistics()
        routing_stats = decision_engine.get_routing_statistics()

        assert load_stats["total_active_requests"] == 0
        assert ProviderType.GLM in routing_stats["provider_success_rates"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
