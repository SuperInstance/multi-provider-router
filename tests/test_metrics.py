"""
Tests for Prometheus metrics collection
"""

import pytest
import time
from datetime import datetime, timezone

from multi_provider_router.models import ProviderType
from multi_provider_router.utils.metrics import MetricsCollector, RequestMetrics


# ============================================================================
# Metrics Collector Tests
# ============================================================================

class TestMetricsCollector:
    """Test metrics collector"""

    @pytest.fixture
    def metrics_collector(self):
        """Create a metrics collector instance"""
        return MetricsCollector()

    def test_initialization(self, metrics_collector):
        """Test metrics collector initialization"""
        assert metrics_collector.requests_total is not None
        assert metrics_collector.response_time_histogram is not None
        assert metrics_collector.cost_total is not None
        assert metrics_collector.tokens_total is not None

    def test_start_request(self, metrics_collector):
        """Test starting request tracking"""
        request_id = "test-req-123"

        metrics_collector.start_request(request_id, ProviderType.GLM, "glm-4")

        assert request_id in metrics_collector._request_metrics
        assert metrics_collector._request_metrics[request_id].provider == ProviderType.GLM
        assert metrics_collector._request_metrics[request_id].start_time > 0

    def test_complete_request(self, metrics_collector):
        """Test completing request tracking"""
        request_id = "test-req-456"
        metrics_collector.start_request(request_id, ProviderType.OPENAI, "gpt-3.5-turbo")

        metrics_collector.complete_request(
            request_id=request_id,
            input_tokens=100,
            output_tokens=200,
            cost_usd=0.001,
            success=True
        )

        # Check provider stats updated
        stats = metrics_collector.get_provider_stats(ProviderType.OPENAI)
        assert stats['total_requests'] == 1
        assert stats['successful_requests'] == 1
        assert stats['total_tokens'] == 300
        assert stats['total_cost_usd'] == 0.001

    def test_complete_request_failure(self, metrics_collector):
        """Test completing failed request"""
        request_id = "test-req-789"
        metrics_collector.start_request(request_id, ProviderType.GLM, "glm-4")

        metrics_collector.complete_request(
            request_id=request_id,
            input_tokens=50,
            output_tokens=0,
            cost_usd=0.0,
            success=False,
            error_type="timeout"
        )

        stats = metrics_collector.get_provider_stats(ProviderType.GLM)
        assert stats['failed_requests'] == 1
        assert stats['successful_requests'] == 0

    def test_get_provider_stats(self, metrics_collector):
        """Test getting provider statistics"""
        # Add some requests
        for i in range(5):
            request_id = f"req-{i}"
            metrics_collector.start_request(request_id, ProviderType.DEEPSEEK, "deepseek-chat")
            metrics_collector.complete_request(
                request_id=request_id,
                input_tokens=100,
                output_tokens=200,
                cost_usd=0.001,
                success=True
            )

        stats = metrics_collector.get_provider_stats(ProviderType.DEEPSEEK)

        assert stats['total_requests'] == 5
        assert stats['successful_requests'] == 5
        assert stats['average_response_time_ms'] >= 0
        assert stats['success_rate'] == 1.0
        assert stats['error_rate'] == 0.0
        assert stats['average_cost_per_request'] == 0.001

    def test_get_cost_summary(self, metrics_collector):
        """Test getting cost summary"""
        # Add some costs
        for i in range(3):
            request_id = f"cost-req-{i}"
            metrics_collector.start_request(request_id, ProviderType.CLAUDE, "claude-3")
            metrics_collector.complete_request(
                request_id=request_id,
                input_tokens=100,
                output_tokens=200,
                cost_usd=0.01,
                success=True
            )

        summary = metrics_collector.get_cost_summary(hours=24)

        assert 'total_cost_usd' in summary
        assert 'period_hours' in summary
        assert summary['total_cost_usd'] == 0.03

    def test_get_response_time_stats(self, metrics_collector):
        """Test getting response time statistics"""
        # Add some requests with specific response times
        for i, response_time in enumerate([100, 200, 300, 400, 500]):
            request_id = f"rt-req-{i}"
            metrics_collector.start_request(request_id, ProviderType.GLM, "glm-4")

            # Manually set end_time to control response time
            metrics_collector._request_metrics[request_id].end_time = \
                metrics_collector._request_metrics[request_id].start_time + (response_time / 1000.0)

            metrics_collector.complete_request(
                request_id=request_id,
                input_tokens=50,
                output_tokens=100,
                cost_usd=0.001,
                success=True
            )

        stats = metrics_collector.get_response_time_stats(window='5m')

        assert 'count' in stats
        assert 'average_ms' in stats
        assert 'min_ms' in stats
        assert 'max_ms' in stats
        assert stats['count'] == 5

    def test_update_provider_health(self, metrics_collector):
        """Test updating provider health score"""
        metrics_collector.update_provider_health(ProviderType.GLM, "glm-4", 0.95)

        # Health metric should be set (check via Prometheus)
        assert metrics_collector.provider_health is not None

    def test_update_budget_usage(self, metrics_collector):
        """Test updating budget usage"""
        metrics_collector.update_budget_usage(75.5)

        # Budget usage metric should be set
        assert metrics_collector.budget_usage is not None

    def test_get_prometheus_metrics(self, metrics_collector):
        """Test getting Prometheus metrics output"""
        # Add some data
        request_id = "prom-req-1"
        metrics_collector.start_request(request_id, ProviderType.GLM, "glm-4")
        metrics_collector.complete_request(
            request_id=request_id,
            input_tokens=100,
            output_tokens=200,
            cost_usd=0.001,
            success=True
        )

        metrics_output = metrics_collector.get_prometheus_metrics()

        assert isinstance(metrics_output, str)
        assert len(metrics_output) > 0
        assert "luciddreamer" in metrics_output.lower()

    def test_reset_metrics(self, metrics_collector):
        """Test resetting all metrics"""
        # Add some data
        request_id = "reset-req-1"
        metrics_collector.start_request(request_id, ProviderType.GLM, "glm-4")
        metrics_collector.complete_request(
            request_id=request_id,
            input_tokens=100,
            output_tokens=200,
            cost_usd=0.001,
            success=True
        )

        # Reset
        metrics_collector.reset_metrics()

        # Should be cleared
        assert len(metrics_collector._request_metrics) == 0


# ============================================================================
# Request Metrics Tests
# ============================================================================

class TestRequestMetrics:
    """Test request metrics dataclass"""

    def test_request_metrics_creation(self):
        """Test creating request metrics"""
        metrics = RequestMetrics(
            provider=ProviderType.OPENAI,
            model="gpt-3.5-turbo",
            start_time=time.time()
        )

        assert metrics.provider == ProviderType.OPENAI
        assert metrics.model == "gpt-3.5-turbo"
        assert metrics.start_time > 0
        assert metrics.success == False  # Default


# ============================================================================
# Provider Metrics Comparison
# ============================================================================

class TestProviderMetricsComparison:
    """Test comparing metrics across providers"""

    def test_compare_provider_metrics(self, metrics_collector):
        """Test comparing metrics between providers"""
        # Add requests to different providers
        providers = [
            (ProviderType.GLM, "glm-4", 0.001),
            (ProviderType.OPENAI, "gpt-3.5-turbo", 0.002),
            (ProviderType.DEEPSEEK, "deepseek-chat", 0.0005)
        ]

        for provider, model, cost in providers:
            request_id = f"{provider.value}-req"
            metrics_collector.start_request(request_id, provider, model)
            metrics_collector.complete_request(
                request_id=request_id,
                input_tokens=100,
                output_tokens=200,
                cost_usd=cost,
                success=True
            )

        # Compare costs
        glm_stats = metrics_collector.get_provider_stats(ProviderType.GLM)
        openai_stats = metrics_collector.get_provider_stats(ProviderType.OPENAI)
        deepseek_stats = metrics_collector.get_provider_stats(ProviderType.DEEPSEEK)

        assert glm_stats['total_cost_usd'] == 0.001
        assert openai_stats['total_cost_usd'] == 0.002
        assert deepseek_stats['total_cost_usd'] == 0.0005

        # DeepSeek should be cheapest
        assert deepseek_stats['total_cost_usd'] < glm_stats['total_cost_usd']
        assert glm_stats['total_cost_usd'] < openai_stats['total_cost_usd']


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
