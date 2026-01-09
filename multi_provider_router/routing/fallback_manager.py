"""
Fallback manager for handling provider failures and redundancy
"""

import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum

from ..models import ProviderType, GenerationRequest, GenerationResponse
from ..providers.base import BaseProvider
from ..utils.logger import get_logger
from ..utils.health_checker import health_checker
from ..utils.metrics import metrics

logger = get_logger("fallback_manager")


class FailureType(str, Enum):
    """Types of provider failures"""
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"
    HEALTH_CHECK = "health_check"
    NETWORK_ERROR = "network_error"
    AUTHENTICATION = "authentication"
    QUOTA_EXCEEDED = "quota_exceeded"


@dataclass
class FailureRecord:
    """Record of a provider failure"""
    provider: ProviderType
    failure_type: FailureType
    timestamp: datetime
    error_message: str
    request_context: Optional[Dict] = None


class FallbackManager:
    """Manages fallback strategies and provider redundancy"""

    def __init__(self):
        self.providers: Dict[ProviderType, BaseProvider] = {}
        self.failure_history: Dict[ProviderType, List[FailureRecord]] = {}
        self.circuit_breaker_state: Dict[ProviderType, bool] = {}
        self.blacklisted_providers: Set[ProviderType] = set()
        self.recovery_attempts: Dict[ProviderType, int] = {}

        # Configuration
        self.max_failures_before_blacklist = 5
        self.blacklist_duration_minutes = 10
        self.circuit_breaker_threshold = 3
        self.circuit_breaker_timeout_seconds = 60

    async def initialize(self, providers: Dict[ProviderType, BaseProvider]) -> None:
        """Initialize with available providers"""
        self.providers = providers
        for provider_type in providers:
            self.failure_history[provider_type] = []
            self.circuit_breaker_state[provider_type] = False
            self.recovery_attempts[provider_type] = 0

        logger.info(f"Fallback manager initialized with {len(providers)} providers")

    async def get_fallback_chain(
        self,
        primary_provider: ProviderType,
        request: GenerationRequest
    ) -> List[ProviderType]:
        """Get ordered list of fallback providers"""
        fallback_chain = []

        # Get all available providers except the primary
        available_providers = [
            p for p in self.providers.keys()
            if p != primary_provider and self.is_provider_available(p)
        ]

        # Sort by priority (cost, quality, health)
        scored_providers = []
        for provider_type in available_providers:
            score = await self._calculate_fallback_score(provider_type, request)
            scored_providers.append((provider_type, score))

        # Sort by score (highest first)
        scored_providers.sort(key=lambda x: x[1], reverse=True)

        # Create fallback chain
        fallback_chain = [provider for provider, _ in scored_providers]

        return fallback_chain

    async def _calculate_fallback_score(self, provider_type: ProviderType, request: GenerationRequest) -> float:
        """Calculate fallback score for a provider"""
        provider = self.providers[provider_type]
        score = 0.0

        # Health score (40% weight)
        health_score = health_checker.get_provider_health_score(provider_type)
        score += health_score * 0.4

        # Recent failure rate (30% weight)
        recent_failures = self._get_recent_failures(provider_type, minutes=5)
        failure_rate = min(1.0, len(recent_failures) / 10.0)
        score += (1.0 - failure_rate) * 0.3

        # Cost-effectiveness (20% weight)
        if provider.is_cost_effective_for(request):
            score += 0.2
        else:
            # Still give some points for availability
            score += 0.1

        # Rate limit availability (10% weight)
        from ..utils.rate_limiter import rate_limiter
        can_proceed, _ = await rate_limiter.check_rate_limit(provider_type, request.user_id)
        if can_proceed:
            score += 0.1

        return score

    def record_failure(
        self,
        provider_type: ProviderType,
        failure_type: FailureType,
        error_message: str,
        request_context: Optional[Dict] = None
    ) -> None:
        """Record a provider failure"""
        failure_record = FailureRecord(
            provider=provider_type,
            failure_type=failure_type,
            timestamp=datetime.now(timezone.utc),
            error_message=error_message,
            request_context=request_context
        )

        self.failure_history[provider_type].append(failure_record)

        # Keep only recent failures (last hour)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
        self.failure_history[provider_type] = [
            f for f in self.failure_history[provider_type]
            if f.timestamp > cutoff_time
        ]

        # Check if we need to blacklist the provider
        recent_failures = self._get_recent_failures(provider_type, minutes=5)
        if len(recent_failures) >= self.max_failures_before_blacklist:
            self._blacklist_provider(provider_type)

        # Check circuit breaker
        if len(recent_failures) >= self.circuit_breaker_threshold:
            self._trigger_circuit_breaker(provider_type)

        logger.warning(
            "Provider failure recorded",
            provider=provider_type.value,
            failure_type=failure_type.value,
            error=error_message,
            recent_failures=len(recent_failures)
        )

    def is_provider_available(self, provider_type: ProviderType) -> bool:
        """Check if a provider is available for fallback"""
        # Check if provider exists
        if provider_type not in self.providers:
            return False

        # Check if blacklisted
        if provider_type in self.blacklisted_providers:
            return False

        # Check circuit breaker
        if self.circuit_breaker_state.get(provider_type, False):
            return False

        # Check health
        if not health_checker.is_healthy(provider_type):
            return False

        return True

    def _blacklist_provider(self, provider_type: ProviderType) -> None:
        """Blacklist a provider temporarily"""
        self.blacklisted_providers.add(provider_type)
        logger.warning(
            "Provider blacklisted",
            provider=provider_type.value,
            duration_minutes=self.blacklist_duration_minutes
        )

        # Schedule recovery
        import asyncio
        asyncio.create_task(self._schedule_provider_recovery(provider_type))

    def _trigger_circuit_breaker(self, provider_type: ProviderType) -> None:
        """Trigger circuit breaker for a provider"""
        self.circuit_breaker_state[provider_type] = True
        logger.warning(
            "Circuit breaker triggered",
            provider=provider_type.value,
            timeout_seconds=self.circuit_breaker_timeout_seconds
        )

        # Schedule recovery
        import asyncio
        asyncio.create_task(self._schedule_circuit_breaker_recovery(provider_type))

    async def _schedule_provider_recovery(self, provider_type: ProviderType) -> None:
        """Schedule provider recovery from blacklist"""
        await asyncio.sleep(self.blacklist_duration_minutes * 60)

        if provider_type in self.blacklisted_providers:
            self.blacklisted_providers.remove(provider_type)
            self.recovery_attempts[provider_type] += 1

            logger.info(
                "Provider removed from blacklist",
                provider=provider_type.value,
                recovery_attempt=self.recovery_attempts[provider_type]
            )

            # Test the provider with a health check
            try:
                await health_checker.manual_health_check(provider_type)
                logger.info(
                    "Provider recovery successful",
                    provider=provider_type.value
                )
            except Exception as e:
                logger.warning(
                    "Provider recovery failed, re-blacklisting",
                    provider=provider_type.value,
                    error=str(e)
                )
                self._blacklist_provider(provider_type)

    async def _schedule_circuit_breaker_recovery(self, provider_type: ProviderType) -> None:
        """Schedule circuit breaker recovery"""
        await asyncio.sleep(self.circuit_breaker_timeout_seconds)

        if self.circuit_breaker_state.get(provider_type, False):
            self.circuit_breaker_state[provider_type] = False

            logger.info(
                "Circuit breaker recovered",
                provider=provider_type.value
            )

    def _get_recent_failures(
        self,
        provider_type: ProviderType,
        minutes: int = 5
    ) -> List[FailureRecord]:
        """Get recent failures for a provider"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return [
            f for f in self.failure_history.get(provider_type, [])
            if f.timestamp > cutoff_time
        ]

    def get_failure_statistics(self) -> Dict[str, any]:
        """Get failure statistics for all providers"""
        stats = {}

        for provider_type in self.providers:
            recent_failures = self._get_recent_failures(provider_type, minutes=60)
            failure_types = {}

            for failure in recent_failures:
                failure_type = failure.failure_type.value
                failure_types[failure_type] = failure_types.get(failure_type, 0) + 1

            stats[provider_type.value] = {
                "total_failures_last_hour": len(recent_failures),
                "failure_types": failure_types,
                "is_blacklisted": provider_type in self.blacklisted_providers,
                "circuit_breaker_active": self.circuit_breaker_state.get(provider_type, False),
                "recovery_attempts": self.recovery_attempts.get(provider_type, 0),
                "last_failure": recent_failures[-1].timestamp.isoformat() if recent_failures else None
            }

        return {
            "providers": stats,
            "total_blacklisted": len(self.blacklisted_providers),
            "total_circuit_breakers_active": sum(1 for v in self.circuit_breaker_state.values() if v),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def test_provider_recovery(self, provider_type: ProviderType) -> bool:
        """Test if a provider has recovered"""
        try:
            # Perform a simple health check
            health_result = await health_checker.manual_health_check(provider_type)
            return health_result.get("status") == "healthy"
        except Exception as e:
            logger.warning(
                "Provider recovery test failed",
                provider=provider_type.value,
                error=str(e)
            )
            return False

    def reset_failure_tracking(self, provider_type: Optional[ProviderType] = None) -> None:
        """Reset failure tracking for a provider or all providers"""
        if provider_type:
            self.failure_history[provider_type] = []
            self.circuit_breaker_state[provider_type] = False
            if provider_type in self.blacklisted_providers:
                self.blacklisted_providers.remove(provider_type)
            logger.info(f"Failure tracking reset for {provider_type.value}")
        else:
            # Reset all providers
            for p in self.providers:
                self.failure_history[p] = []
                self.circuit_breaker_state[p] = False
            self.blacklisted_providers.clear()
            logger.info("Failure tracking reset for all providers")

    def get_provider_health_summary(self) -> Dict[str, any]:
        """Get comprehensive health summary"""
        summary = {
            "total_providers": len(self.providers),
            "available_providers": 0,
            "unavailable_providers": 0,
            "blacklisted_providers": len(self.blacklisted_providers),
            "circuit_breakers_active": sum(1 for v in self.circuit_breaker_state.values() if v),
            "providers": {}
        }

        for provider_type in self.providers:
            is_available = self.is_provider_available(provider_type)
            if is_available:
                summary["available_providers"] += 1
            else:
                summary["unavailable_providers"] += 1

            recent_failures = self._get_recent_failures(provider_type, minutes=10)
            summary["providers"][provider_type.value] = {
                "available": is_available,
                "blacklisted": provider_type in self.blacklisted_providers,
                "circuit_breaker": self.circuit_breaker_state.get(provider_type, False),
                "recent_failures": len(recent_failures),
                "health_score": health_checker.get_provider_health_score(provider_type),
                "last_failure": recent_failures[-1].timestamp.isoformat() if recent_failures else None
            }

        return summary