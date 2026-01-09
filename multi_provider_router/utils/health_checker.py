"""
Health checking system for API providers
"""

import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import asdict
from datetime import datetime, timezone, timedelta

import httpx
from ..models import ProviderType, HealthCheck, ProviderConfig
from ..utils.logger import get_logger
from ..config import get_settings

settings = get_settings()
logger = get_logger("health_checker")


class HealthChecker:
    """Health checking system for API providers"""

    def __init__(self):
        self._health_status: Dict[ProviderType, HealthCheck] = {}
        self._provider_configs: Dict[ProviderType, ProviderConfig] = {}
        self._running = False
        self._check_interval = settings.routing.health_check_interval_seconds
        self._timeout = 10  # Health check timeout

    def register_provider(self, config: ProviderConfig) -> None:
        """Register a provider for health checking"""
        self._provider_configs[config.provider] = config
        # Initialize with unknown status
        self._health_status[config.provider] = HealthCheck(
            provider=config.provider,
            model=config.model_name,
            is_healthy=False,
            response_time_ms=0,
            error_message="Not checked yet"
        )

    async def start_health_checks(self) -> None:
        """Start periodic health checks"""
        if self._running:
            return

        self._running = True
        logger.info("Starting health checks", interval_seconds=self._check_interval)

        while self._running:
            try:
                await self._check_all_providers()
                await asyncio.sleep(self._check_interval)
            except Exception as e:
                logger.error("Health check error", error=str(e))
                await asyncio.sleep(self._check_interval)

    async def stop_health_checks(self) -> None:
        """Stop health checks"""
        self._running = False
        logger.info("Stopped health checks")

    async def _check_all_providers(self) -> None:
        """Check health of all registered providers"""
        tasks = []
        for provider_type, config in self._provider_configs.items():
            if config.is_active:
                tasks.append(self._check_provider_health(config))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_provider_health(self, config: ProviderConfig) -> None:
        """Check health of a specific provider"""
        start_time = time.time()
        is_healthy = False
        error_message = None

        try:
            # Create a minimal test request
            test_request = await self._create_test_request(config)

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._get_endpoint_url(config),
                    headers=self._get_headers(config),
                    json=test_request
                )

                response_time_ms = int((time.time() - start_time) * 1000)

                if response.status_code == 200:
                    is_healthy = True
                    logger.debug(
                        "Provider health check passed",
                        provider=config.provider.value,
                        response_time_ms=response_time_ms
                    )
                else:
                    error_message = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(
                        "Provider health check failed",
                        provider=config.provider.value,
                        status_code=response.status_code,
                        error=error_message
                    )

        except asyncio.TimeoutError:
            error_message = "Health check timeout"
            logger.warning(
                "Provider health check timeout",
                provider=config.provider.value,
                timeout_seconds=self._timeout
            )

        except Exception as e:
            error_message = str(e)[:200]
            logger.warning(
                "Provider health check error",
                provider=config.provider.value,
                error=error_message
            )

        response_time_ms = int((time.time() - start_time) * 1000)

        # Update health status
        health_check = HealthCheck(
            provider=config.provider,
            model=config.model_name,
            is_healthy=is_healthy,
            response_time_ms=response_time_ms,
            error_message=error_message,
            timestamp=datetime.now(timezone.utc)
        )

        self._health_status[config.provider] = health_check

    async def _create_test_request(self, config: ProviderConfig) -> Dict:
        """Create a minimal test request for the provider"""
        base_request = {
            "max_tokens": 10,
            "temperature": 0.1
        }

        if config.provider == ProviderType.GLM:
            return {
                **base_request,
                "model": config.model_name,
                "messages": [
                    {"role": "user", "content": "Hi"}
                ]
            }

        elif config.provider == ProviderType.DEEPSEEK:
            return {
                **base_request,
                "model": config.model_name,
                "messages": [
                    {"role": "user", "content": "Hi"}
                ]
            }

        elif config.provider == ProviderType.CLAUDE:
            return {
                **base_request,
                "model": config.model_name,
                "max_tokens": 10,
                "messages": [
                    {"role": "user", "content": "Hi"}
                ]
            }

        elif config.provider == ProviderType.OPENAI:
            return {
                **base_request,
                "model": config.model_name,
                "messages": [
                    {"role": "user", "content": "Hi"}
                ]
            }

        elif config.provider == ProviderType.DEEPINFRA:
            return {
                **base_request,
                "model": config.model_name,
                "messages": [
                    {"role": "user", "content": "Hi"}
                ]
            }

        else:
            raise ValueError(f"Unknown provider: {config.provider}")

    def _get_endpoint_url(self, config: ProviderConfig) -> str:
        """Get the API endpoint URL for the provider"""
        if config.provider == ProviderType.CLAUDE:
            return f"{config.base_url}/v1/messages"
        else:
            return f"{config.base_url}/chat/completions"

    def _get_headers(self, config: ProviderConfig) -> Dict[str, str]:
        """Get request headers for the provider"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LucidDreamer-Router/1.0"
        }

        if config.provider == ProviderType.CLAUDE:
            headers["x-api-key"] = config.api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {config.api_key}"

        return headers

    def get_health_status(self, provider: ProviderType) -> Optional[HealthCheck]:
        """Get health status for a specific provider"""
        return self._health_status.get(provider)

    def get_all_health_status(self) -> Dict[ProviderType, HealthCheck]:
        """Get health status for all providers"""
        return self._health_status.copy()

    def is_healthy(self, provider: ProviderType) -> bool:
        """Check if a provider is healthy"""
        health_check = self._health_status.get(provider)
        if not health_check:
            return False

        # Consider provider healthy if last check was within 2 * check_interval
        now = datetime.now(timezone.utc)
        time_since_check = (now - health_check.timestamp).total_seconds()

        if time_since_check > 2 * self._check_interval:
            return False

        return health_check.is_healthy

    def get_healthy_providers(self) -> List[ProviderType]:
        """Get list of healthy providers"""
        return [
            provider for provider in self._provider_configs.keys()
            if self.is_healthy(provider)
        ]

    def get_provider_health_score(self, provider: ProviderType) -> float:
        """Get health score for a provider (0.0 to 1.0)"""
        health_check = self._health_status.get(provider)
        if not health_check:
            return 0.0

        if not health_check.is_healthy:
            return 0.0

        # Calculate score based on response time and reliability
        # Lower response time = higher score
        if health_check.response_time_ms == 0:
            return 0.0

        # Normalize response time (0-1000ms range, inverted)
        response_score = max(0.0, 1.0 - (health_check.response_time_ms / 1000.0))

        # Consider recent health history
        # (this could be expanded to track success rate over time)
        reliability_score = 1.0 if health_check.is_healthy else 0.0

        # Weight the scores
        return (response_score * 0.6) + (reliability_score * 0.4)

    async def manual_health_check(self, provider: ProviderType) -> HealthCheck:
        """Perform an immediate health check for a provider"""
        config = self._provider_configs.get(provider)
        if not config:
            raise ValueError(f"Provider {provider} not registered")

        await self._check_provider_health(config)
        return self._health_status[provider]

    def get_health_summary(self) -> Dict[str, any]:
        """Get overall health summary"""
        total_providers = len(self._provider_configs)
        healthy_providers = len(self.get_healthy_providers())

        if total_providers == 0:
            health_percentage = 0.0
        else:
            health_percentage = (healthy_providers / total_providers) * 100

        provider_details = {}
        for provider, health_check in self._health_status.items():
            provider_details[provider.value] = {
                'is_healthy': health_check.is_healthy,
                'response_time_ms': health_check.response_time_ms,
                'last_check': health_check.timestamp.isoformat(),
                'error_message': health_check.error_message
            }

        return {
            'total_providers': total_providers,
            'healthy_providers': healthy_providers,
            'health_percentage': health_percentage,
            'last_check': max(
                (hc.timestamp for hc in self._health_status.values()),
                default=datetime.now(timezone.utc)
            ).isoformat(),
            'providers': provider_details
        }


# Global health checker instance
health_checker = HealthChecker()