"""
Load balancer for distributing requests across providers
"""

import time
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from collections import defaultdict, deque
import random

from ..models import ProviderType, PriorityLevel
from ..providers.base import BaseProvider
from ..utils.logger import get_logger
from ..utils.metrics import metrics

logger = get_logger("load_balancer")


@dataclass
class ProviderLoad:
    """Load tracking for a provider"""
    provider: ProviderType
    active_requests: int
    total_requests_today: int
    average_response_time_ms: float
    success_rate: float
    last_used: datetime
    cost_efficiency_score: float


class LoadBalancer:
    """Load balancer for distributing requests across providers"""

    def __init__(self):
        self.providers: Dict[ProviderType, BaseProvider] = {}
        self.provider_loads: Dict[ProviderType, ProviderLoad] = {}
        self.request_history: Dict[ProviderType, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.load_balancing_strategy = "weighted_round_robin"  # Options: round_robin, weighted, least_connections, adaptive

        # Round-robin state
        self.round_robin_counters: Dict[ProviderType, int] = defaultdict(int)

        # Load balancing weights
        self.provider_weights: Dict[ProviderType, float] = {}

    async def initialize(self, providers: Dict[ProviderType, BaseProvider]) -> None:
        """Initialize load balancer with providers"""
        self.providers = providers
        current_time = datetime.now(timezone.utc)

        for provider_type, provider in providers.items():
            self.provider_loads[provider_type] = ProviderLoad(
                provider=provider_type,
                active_requests=0,
                total_requests_today=0,
                average_response_time_ms=1000.0,
                success_rate=1.0,
                last_used=current_time,
                cost_efficiency_score=self._calculate_cost_efficiency(provider)
            )

            # Initialize weights based on provider characteristics
            self.provider_weights[provider_type] = self._calculate_initial_weight(provider)

        logger.info(f"Load balancer initialized with {len(providers)} providers")

    async def select_provider(
        self,
        available_providers: List[ProviderType],
        priority: PriorityLevel = PriorityLevel.NORMAL,
        user_id: Optional[str] = None
    ) -> ProviderType:
        """Select the best provider based on load balancing strategy"""
        if not available_providers:
            raise ValueError("No available providers for load balancing")

        # Filter out providers that are at capacity
        available_providers = [
            p for p in available_providers
            if not self._is_provider_at_capacity(p)
        ]

        if not available_providers:
            raise ValueError("All available providers are at capacity")

        # Select based on strategy
        if self.load_balancing_strategy == "round_robin":
            return self._round_robin_selection(available_providers)
        elif self.load_balancing_strategy == "weighted":
            return self._weighted_selection(available_providers)
        elif self.load_balancing_strategy == "least_connections":
            return self._least_connections_selection(available_providers)
        elif self.load_balancing_strategy == "adaptive":
            return self._adaptive_selection(available_providers, priority)
        else:
            # Default to weighted
            return self._weighted_selection(available_providers)

    def _is_provider_at_capacity(self, provider_type: ProviderType) -> bool:
        """Check if a provider is at capacity"""
        load = self.provider_loads.get(provider_type)
        if not load:
            return False

        # Capacity thresholds
        max_active_requests = 50  # Configurable per provider
        max_success_rate_drop = 0.7  # Don't use if success rate drops below 70%
        max_response_time_increase = 3000  # Don't use if response time > 3 seconds

        return (
            load.active_requests >= max_active_requests or
            load.success_rate < max_success_rate_drop or
            load.average_response_time_ms > max_response_time_increase
        )

    def _round_robin_selection(self, available_providers: List[ProviderType]) -> ProviderType:
        """Round-robin provider selection"""
        if not available_providers:
            raise ValueError("No providers available")

        # Find provider with lowest round-robin counter
        selected_provider = min(
            available_providers,
            key=lambda p: self.round_robin_counters[p]
        )

        # Increment counter
        self.round_robin_counters[selected_provider] += 1

        return selected_provider

    def _weighted_selection(self, available_providers: List[ProviderType]) -> ProviderType:
        """Weighted random selection based on provider weights"""
        if not available_providers:
            raise ValueError("No providers available")

        # Get weights for available providers
        weights = [self.provider_weights.get(p, 1.0) for p in available_providers]

        # Weighted random selection
        selected_index = random.choices(
            range(len(available_providers)),
            weights=weights,
            k=1
        )[0]

        return available_providers[selected_index]

    def _least_connections_selection(self, available_providers: List[ProviderType]) -> ProviderType:
        """Select provider with least active connections"""
        if not available_providers:
            raise ValueError("No providers available")

        selected_provider = min(
            available_providers,
            key=lambda p: self.provider_loads[p].active_requests
        )

        return selected_provider

    def _adaptive_selection(
        self,
        available_providers: List[ProviderType],
        priority: PriorityLevel
    ) -> ProviderType:
        """Adaptive selection based on current conditions and priority"""
        if not available_providers:
            raise ValueError("No providers available")

        # Score each provider based on multiple factors
        scored_providers = []
        for provider_type in available_providers:
            load = self.provider_loads[provider_type]
            score = self._calculate_adaptive_score(load, priority)
            scored_providers.append((provider_type, score))

        # Select provider with highest score
        selected_provider = max(scored_providers, key=lambda x: x[1])[0]

        return selected_provider

    def _calculate_adaptive_score(
        self,
        load: ProviderLoad,
        priority: PriorityLevel
    ) -> float:
        """Calculate adaptive score for provider selection"""
        score = 0.0

        # Base score from cost efficiency
        score += load.cost_efficiency_score * 0.3

        # Success rate score
        score += load.success_rate * 0.25

        # Response time score (lower is better)
        response_time_score = max(0.0, 1.0 - (load.average_response_time_ms / 2000.0))
        score += response_time_score * 0.2

        # Load score (fewer active requests is better)
        load_score = max(0.0, 1.0 - (load.active_requests / 50.0))
        score += load_score * 0.15

        # Recency score (recently used providers might be warmed up)
        time_since_last_use = (datetime.now(timezone.utc) - load.last_used).total_seconds()
        recency_score = max(0.0, 1.0 - (time_since_last_use / 300.0))  # 5 minute window
        score += recency_score * 0.1

        # Priority adjustment
        if priority == PriorityLevel.CRITICAL:
            # Prioritize success rate and response time for critical requests
            score = (score * 0.7) + (load.success_rate * 0.2) + (response_time_score * 0.1)
        elif priority == PriorityLevel.HIGH:
            # Balance between performance and cost
            score = (score * 0.8) + (load.cost_efficiency_score * 0.2)

        return score

    def _calculate_cost_efficiency(self, provider: BaseProvider) -> float:
        """Calculate cost efficiency score for a provider"""
        # Base score from cost tier
        if hasattr(provider, 'get_performance_characteristics'):
            perf_chars = provider.get_performance_characteristics()
            cost_tier = perf_chars.get('cost_tier', 'moderate')

            cost_tier_scores = {
                'ultra_low': 1.0,
                'very_low': 0.9,
                'low': 0.8,
                'moderate': 0.6,
                'high': 0.4,
                'very_high': 0.2
            }

            base_score = cost_tier_scores.get(cost_tier, 0.5)
        else:
            # Estimate from pricing if performance characteristics not available
            estimated_cost_per_1m = (provider.config.cost_per_1m_input_tokens +
                                    provider.config.cost_per_1m_output_tokens) / 2
            base_score = max(0.0, 1.0 - (estimated_cost_per_1m / 2.0))

        # Adjust for quality
        quality_score = provider.get_quality_score()
        return (base_score * 0.7) + (quality_score * 0.3)

    def _calculate_initial_weight(self, provider: BaseProvider) -> float:
        """Calculate initial weight for a provider"""
        # Weight based on cost efficiency, quality, and performance
        cost_efficiency = self._calculate_cost_efficiency(provider)
        quality = provider.get_quality_score()

        # Base weight
        weight = (cost_efficiency * 0.5) + (quality * 0.3)

        # Add performance characteristics if available
        if hasattr(provider, 'get_performance_characteristics'):
            perf_chars = provider.get_performance_characteristics()
            speed_score = perf_chars.get('average_response_time_ms', 1000) / 1000.0
            weight += max(0.0, 1.0 - speed_score) * 0.2

        return max(0.1, weight)  # Minimum weight of 0.1

    def start_request(self, provider_type: ProviderType, request_id: str) -> None:
        """Track the start of a request for a provider"""
        if provider_type in self.provider_loads:
            self.provider_loads[provider_type].active_requests += 1
            self.provider_loads[provider_type].total_requests_today += 1
            self.provider_loads[provider_type].last_used = datetime.now(timezone.utc)

        # Add to request history
        self.request_history[provider_type].append({
            'request_id': request_id,
            'start_time': time.time(),
            'status': 'active'
        })

    def end_request(
        self,
        provider_type: ProviderType,
        request_id: str,
        success: bool,
        response_time_ms: int
    ) -> None:
        """Track the end of a request for a provider"""
        if provider_type in self.provider_loads:
            load = self.provider_loads[provider_type]
            load.active_requests = max(0, load.active_requests - 1)

            # Update response time (exponential moving average)
            alpha = 0.1
            load.average_response_time_ms = (
                alpha * response_time_ms +
                (1 - alpha) * load.average_response_time_ms
            )

            # Update success rate (exponential moving average)
            load.success_rate = (
                alpha * (1.0 if success else 0.0) +
                (1 - alpha) * load.success_rate
            )

        # Update request history
        for i, req in enumerate(self.request_history[provider_type]):
            if req['request_id'] == request_id:
                self.request_history[provider_type][i]['status'] = 'completed' if success else 'failed'
                self.request_history[provider_type][i]['response_time_ms'] = response_time_ms
                break

        # Update metrics
        metrics.log_request_metrics(request_id, provider_type.value, response_time_ms, success)

    def get_load_statistics(self) -> Dict[str, any]:
        """Get load balancing statistics"""
        stats = {
            "total_providers": len(self.providers),
            "strategy": self.load_balancing_strategy,
            "providers": {}
        }

        total_active_requests = 0
        total_requests_today = 0

        for provider_type, load in self.provider_loads.items():
            total_active_requests += load.active_requests
            total_requests_today += load.total_requests_today

            stats["providers"][provider_type.value] = {
                "active_requests": load.active_requests,
                "total_requests_today": load.total_requests_today,
                "average_response_time_ms": round(load.average_response_time_ms, 2),
                "success_rate": round(load.success_rate, 3),
                "cost_efficiency_score": round(load.cost_efficiency_score, 3),
                "weight": round(self.provider_weights.get(provider_type, 0.0), 3),
                "last_used": load.last_used.isoformat(),
                "requests_per_minute": len(self.request_history[provider_type])
            }

        stats["total_active_requests"] = total_active_requests
        stats["total_requests_today"] = total_requests_today
        stats["timestamp"] = datetime.now(timezone.utc).isoformat()

        return stats

    def set_load_balancing_strategy(self, strategy: str) -> None:
        """Set load balancing strategy"""
        valid_strategies = ["round_robin", "weighted", "least_connections", "adaptive"]
        if strategy not in valid_strategies:
            raise ValueError(f"Invalid strategy. Must be one of: {valid_strategies}")

        self.load_balancing_strategy = strategy
        logger.info(f"Load balancing strategy changed to: {strategy}")

    def update_provider_weight(self, provider_type: ProviderType, weight: float) -> None:
        """Update weight for a provider"""
        if weight < 0.1:
            weight = 0.1  # Minimum weight

        self.provider_weights[provider_type] = weight
        logger.info(f"Provider weight updated", provider=provider_type.value, weight=weight)

    def rebalance_weights(self) -> None:
        """Automatically rebalance provider weights based on performance"""
        for provider_type, load in self.provider_loads.items():
            # Calculate new weight based on current performance
            performance_score = (
                load.success_rate * 0.4 +
                max(0.0, 1.0 - (load.average_response_time_ms / 2000.0)) * 0.3 +
                load.cost_efficiency_score * 0.3
            )

            # Update weight with smoothing
            current_weight = self.provider_weights.get(provider_type, 1.0)
            new_weight = (current_weight * 0.8) + (performance_score * 0.2)
            self.provider_weights[provider_type] = max(0.1, new_weight)

        logger.info("Provider weights rebalanced based on performance")

    def get_provider_recommendations(self) -> List[Dict[str, any]]:
        """Get recommendations for provider optimization"""
        recommendations = []

        for provider_type, load in self.provider_loads.items():
            provider_recs = []

            # High response time
            if load.average_response_time_ms > 2000:
                provider_recs.append("High response time detected")

            # Low success rate
            if load.success_rate < 0.8:
                provider_recs.append("Low success rate - investigate issues")

            # Low cost efficiency
            if load.cost_efficiency_score < 0.5:
                provider_recs.append("Low cost efficiency - consider alternative")

            # High load
            if load.active_requests > 30:
                provider_recs.append("High load - consider scaling or load redistribution")

            # Underutilized
            if load.active_requests == 0 and load.total_requests_today < 10:
                provider_recs.append("Underutilized - consider increasing weight")

            if provider_recs:
                recommendations.append({
                    "provider": provider_type.value,
                    "issues": provider_recs,
                    "current_weight": self.provider_weights.get(provider_type, 0.0),
                    "success_rate": load.success_rate,
                    "avg_response_time_ms": load.average_response_time_ms
                })

        return recommendations