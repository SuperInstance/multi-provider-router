"""
Metrics collection for monitoring and analytics
"""

import time
from typing import Dict, Any, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import threading

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from ..models import ProviderType


@dataclass
class RequestMetrics:
    """Individual request metrics"""
    provider: ProviderType
    model: str
    start_time: float
    end_time: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    success: bool = False
    error_type: Optional[str] = None


class MetricsCollector:
    """Collects and manages system metrics"""

    def __init__(self):
        # In-memory metrics storage
        self._request_metrics: Dict[str, RequestMetrics] = {}
        self._provider_stats = defaultdict(lambda: {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens': 0,
            'total_cost_usd': 0.0,
            'response_times': deque(maxlen=1000),  # Keep last 1000 response times
            'errors': defaultdict(int)
        })

        # Prometheus metrics
        self._setup_prometheus_metrics()

        # Thread safety
        self._lock = threading.RLock()

        # Cost tracking
        self._hourly_costs = defaultdict(float)
        self._daily_costs = defaultdict(float)

        # Performance tracking
        self._response_time_windows = {
            '1m': deque(maxlen=60),  # Last 60 seconds
            '5m': deque(maxlen=300),  # Last 5 minutes
            '1h': deque(maxlen=3600)  # Last hour
        }

    def _setup_prometheus_metrics(self):
        """Setup Prometheus metrics"""
        # Request counters
        self.requests_total = Counter(
            'luciddreamer_requests_total',
            'Total number of requests',
            ['provider', 'model', 'status']
        )

        # Response time histogram
        self.response_time_histogram = Histogram(
            'luciddreamer_response_time_seconds',
            'Response time in seconds',
            ['provider', 'model'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0]
        )

        # Cost tracking
        self.cost_total = Counter(
            'luciddreamer_cost_total_usd',
            'Total cost in USD',
            ['provider', 'model']
        )

        # Token usage
        self.tokens_total = Counter(
            'luciddreamer_tokens_total',
            'Total tokens used',
            ['provider', 'model', 'type']  # input/output
        )

        # Active requests gauge
        self.active_requests = Gauge(
            'luciddreamer_active_requests',
            'Number of currently active requests'
        )

        # Provider health gauge
        self.provider_health = Gauge(
            'luciddreamer_provider_health',
            'Provider health score',
            ['provider', 'model']
        )

        # Budget usage gauge
        self.budget_usage = Gauge(
            'luciddreamer_budget_usage_percentage',
            'Budget usage percentage'
        )

    def start_request(self, request_id: str, provider: ProviderType, model: str) -> None:
        """Start tracking a new request"""
        with self._lock:
            self._request_metrics[request_id] = RequestMetrics(
                provider=provider,
                model=model,
                start_time=time.time()
            )
            self.active_requests.inc()

    def complete_request(
        self,
        request_id: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        success: bool = True,
        error_type: Optional[str] = None
    ) -> None:
        """Complete request tracking"""
        with self._lock:
            if request_id not in self._request_metrics:
                return

            metrics = self._request_metrics[request_id]
            metrics.end_time = time.time()
            metrics.input_tokens = input_tokens
            metrics.output_tokens = output_tokens
            metrics.cost_usd = cost_usd
            metrics.success = success
            metrics.error_type = error_type

            # Calculate duration
            duration_ms = int((metrics.end_time - metrics.start_time) * 1000)

            # Update provider stats
            provider_stats = self._provider_stats[metrics.provider]
            provider_stats['total_requests'] += 1
            provider_stats['response_times'].append(duration_ms)

            if success:
                provider_stats['successful_requests'] += 1
                self.requests_total.labels(
                    provider=metrics.provider.value,
                    model=metrics.model,
                    status='success'
                ).inc()
            else:
                provider_stats['failed_requests'] += 1
                provider_stats['errors'][error_type or 'unknown'] += 1
                self.requests_total.labels(
                    provider=metrics.provider.value,
                    model=metrics.model,
                    status='error'
                ).inc()

            # Update token and cost metrics
            provider_stats['total_tokens'] += input_tokens + output_tokens
            provider_stats['total_cost_usd'] += cost_usd

            # Update Prometheus metrics
            self.response_time_histogram.labels(
                provider=metrics.provider.value,
                model=metrics.model
            ).observe(duration_ms / 1000.0)

            self.cost_total.labels(
                provider=metrics.provider.value,
                model=metrics.model
            ).inc(cost_usd)

            self.tokens_total.labels(
                provider=metrics.provider.value,
                model=metrics.model,
                type='input'
            ).inc(input_tokens)

            self.tokens_total.labels(
                provider=metrics.provider.value,
                model=metrics.model,
                type='output'
            ).inc(output_tokens)

            # Update time windows
            for window in self._response_time_windows.values():
                window.append(duration_ms)

            # Update cost tracking
            now = datetime.now(timezone.utc)
            hour_key = now.strftime('%Y-%m-%d-%H')
            day_key = now.strftime('%Y-%m-%d')

            self._hourly_costs[hour_key] += cost_usd
            self._daily_costs[day_key] += cost_usd

            self.active_requests.dec()

    def update_provider_health(self, provider: ProviderType, model: str, health_score: float) -> None:
        """Update provider health score"""
        self.provider_health.labels(
            provider=provider.value,
            model=model
        ).set(health_score)

    def update_budget_usage(self, percentage: float) -> None:
        """Update budget usage percentage"""
        self.budget_usage.set(percentage)

    def get_provider_stats(self, provider: ProviderType) -> Dict[str, Any]:
        """Get statistics for a specific provider"""
        with self._lock:
            stats = self._provider_stats[provider].copy()

            if stats['response_times']:
                stats['average_response_time_ms'] = sum(stats['response_times']) / len(stats['response_times'])
                stats['min_response_time_ms'] = min(stats['response_times'])
                stats['max_response_time_ms'] = max(stats['response_times'])
            else:
                stats['average_response_time_ms'] = 0
                stats['min_response_time_ms'] = 0
                stats['max_response_time_ms'] = 0

            # Calculate success rate
            if stats['total_requests'] > 0:
                stats['success_rate'] = stats['successful_requests'] / stats['total_requests']
                stats['error_rate'] = stats['failed_requests'] / stats['total_requests']
            else:
                stats['success_rate'] = 0
                stats['error_rate'] = 0

            # Calculate average cost per request
            if stats['total_requests'] > 0:
                stats['average_cost_per_request'] = stats['total_cost_usd'] / stats['total_requests']
                stats['average_tokens_per_request'] = stats['total_tokens'] / stats['total_requests']
            else:
                stats['average_cost_per_request'] = 0
                stats['average_tokens_per_request'] = 0

            return stats

    def get_cost_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get cost summary for the last N hours"""
        with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=hours)

            total_cost = 0.0
            hourly_breakdown = {}

            for hour_key, cost in self._hourly_costs.items():
                hour_datetime = datetime.strptime(hour_key, '%Y-%m-%d-%H').replace(tzinfo=timezone.utc)
                if hour_datetime >= cutoff:
                    total_cost += cost
                    hourly_breakdown[hour_key] = cost

            return {
                'total_cost_usd': total_cost,
                'period_hours': hours,
                'hourly_breakdown': hourly_breakdown,
                'average_cost_per_hour': total_cost / hours if hours > 0 else 0
            }

    def get_response_time_stats(self, window: str = '5m') -> Dict[str, float]:
        """Get response time statistics for a time window"""
        with self._lock:
            if window not in self._response_time_windows:
                window = '5m'

            times = list(self._response_time_windows[window])
            if not times:
                return {
                    'count': 0,
                    'average_ms': 0,
                    'min_ms': 0,
                    'max_ms': 0,
                    'p50_ms': 0,
                    'p95_ms': 0,
                    'p99_ms': 0
                }

            times.sort()
            count = len(times)

            return {
                'count': count,
                'average_ms': sum(times) / count,
                'min_ms': times[0],
                'max_ms': times[-1],
                'p50_ms': times[count // 2],
                'p95_ms': times[int(count * 0.95)],
                'p99_ms': times[int(count * 0.99)]
            }

    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics output"""
        return generate_latest().decode('utf-8')

    def reset_metrics(self) -> None:
        """Reset all metrics (for testing)"""
        with self._lock:
            self._request_metrics.clear()
            self._provider_stats.clear()
            self._hourly_costs.clear()
            self._daily_costs.clear()
            for window in self._response_time_windows.values():
                window.clear()


# Global metrics collector instance
metrics = MetricsCollector()