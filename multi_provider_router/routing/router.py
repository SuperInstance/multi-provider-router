"""
Main cost-optimized router for handling AI requests
"""

import uuid
import time
import asyncio
from typing import Dict, List, Optional, AsyncGenerator
from datetime import datetime, timezone

from ..models import (
    GenerationRequest,
    GenerationResponse,
    RoutingDecision,
    RequestStatus,
    ProviderType,
    APIResponse
)
from ..providers.base import BaseProvider
from ..providers.glm_provider import GLMProvider
from ..providers.deepseek_provider import DeepSeekProvider
from ..providers.claude_provider import ClaudeProvider
from ..providers.openai_provider import OpenAIProvider
from ..providers.deepinfra_provider import DeepInfraProvider
from ..routing.decision_engine import RoutingDecisionEngine
from ..routing.fallback_manager import FallbackManager
from ..routing.load_balancer import LoadBalancer
from ..utils.logger import get_logger
from ..utils.metrics import metrics
from ..utils.cache import cache
from ..utils.rate_limiter import rate_limiter
from ..config import get_settings

settings = get_settings()
logger = get_logger("router")


class CostOptimizedRouter:
    """Main router for cost-optimized AI request handling"""

    def __init__(self):
        self.decision_engine = RoutingDecisionEngine()
        self.fallback_manager = FallbackManager()
        self.load_balancer = LoadBalancer()
        self.providers: Dict[ProviderType, BaseProvider] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the router with all providers"""
        if self._initialized:
            return

        logger.info("Initializing cost-optimized router")

        # Initialize providers
        await self._initialize_providers()

        # Initialize sub-systems
        await self._initialize_subsystems()

        self._initialized = True
        logger.info("Router initialization complete")

    async def _initialize_providers(self) -> None:
        """Initialize all providers"""
        from ..models import ProviderConfig

        # GLM-4 Provider
        if settings.glm.api_key:
            glm_config = ProviderConfig(
                provider=ProviderType.GLM,
                model_name=settings.glm.model_name,
                api_key=settings.glm.api_key,
                base_url=settings.glm.base_url,
                cost_per_1m_input_tokens=settings.glm.cost_per_1m_tokens,
                cost_per_1m_output_tokens=settings.glm.cost_per_1m_output_tokens,
                max_tokens=settings.glm.max_tokens,
                timeout=settings.glm.timeout,
                max_retries=settings.glm.max_retries,
                rate_limit_per_minute=settings.glm.rate_limit_per_minute
            )
            glm_provider = GLMProvider(glm_config)
            self.providers[ProviderType.GLM] = glm_provider
            self.decision_engine.register_provider(glm_provider)
            logger.info("GLM-4 provider initialized")

        # DeepSeek Provider
        if settings.deepseek.api_key:
            deepseek_config = ProviderConfig(
                provider=ProviderType.DEEPSEEK,
                model_name=settings.deepseek.model_name,
                api_key=settings.deepseek.api_key,
                base_url=settings.deepseek.base_url,
                cost_per_1m_input_tokens=settings.deepseek.cost_per_1m_tokens,
                cost_per_1m_output_tokens=settings.deepseek.cost_per_1m_output_tokens,
                max_tokens=settings.deepseek.max_tokens,
                timeout=settings.deepseek.timeout,
                max_retries=settings.deepseek.max_retries,
                rate_limit_per_minute=settings.deepseek.rate_limit_per_minute
            )
            deepseek_provider = DeepSeekProvider(deepseek_config)
            self.providers[ProviderType.DEEPSEEK] = deepseek_provider
            self.decision_engine.register_provider(deepseek_provider)
            logger.info("DeepSeek provider initialized")

        # Claude Provider
        if settings.claude.api_key:
            claude_config = ProviderConfig(
                provider=ProviderType.CLAUDE,
                model_name=settings.claude.model_name,
                api_key=settings.claude.api_key,
                base_url=settings.claude.base_url,
                cost_per_1m_input_tokens=settings.claude.cost_per_1m_tokens,
                cost_per_1m_output_tokens=settings.claude.cost_per_1m_output_tokens,
                max_tokens=settings.claude.max_tokens,
                timeout=settings.claude.timeout,
                max_retries=settings.claude.max_retries,
                rate_limit_per_minute=settings.claude.rate_limit_per_minute
            )
            claude_provider = ClaudeProvider(claude_config)
            self.providers[ProviderType.CLAUDE] = claude_provider
            self.decision_engine.register_provider(claude_provider)
            logger.info("Claude Haiku provider initialized")

        # OpenAI Provider
        if settings.openai.api_key:
            openai_config = ProviderConfig(
                provider=ProviderType.OPENAI,
                model_name=settings.openai.model_name,
                api_key=settings.openai.api_key,
                base_url=settings.openai.base_url,
                cost_per_1m_input_tokens=settings.openai.cost_per_1m_tokens,
                cost_per_1m_output_tokens=settings.openai.cost_per_1m_output_tokens,
                max_tokens=settings.openai.max_tokens,
                timeout=settings.openai.timeout,
                max_retries=settings.openai.max_retries,
                rate_limit_per_minute=settings.openai.rate_limit_per_minute
            )
            openai_provider = OpenAIProvider(openai_config)
            self.providers[ProviderType.OPENAI] = openai_provider
            self.decision_engine.register_provider(openai_provider)
            logger.info("OpenAI provider initialized")

        # DeepInfra Provider
        if settings.deepinfra.api_key:
            deepinfra_config = ProviderConfig(
                provider=ProviderType.DEEPINFRA,
                model_name="wizardlm-2-8x22b",  # Default model
                api_key=settings.deepinfra.api_key,
                base_url=settings.deepinfra.base_url,
                cost_per_1m_input_tokens=0.5,  # Will be overridden per model
                cost_per_1m_output_tokens=2.0,
                max_tokens=8192,
                timeout=settings.deepinfra.timeout,
                max_retries=settings.deepinfra.max_retries,
                rate_limit_per_minute=settings.deepinfra.rate_limit_per_minute,
                specialty_models=settings.deepinfra.specialty_models
            )
            deepinfra_provider = DeepInfraProvider(deepinfra_config)
            self.providers[ProviderType.DEEPINFRA] = deepinfra_provider
            self.decision_engine.register_provider(deepinfra_provider)
            logger.info("DeepInfra provider initialized")

        logger.info(f"Initialized {len(self.providers)} providers")

    async def _initialize_subsystems(self) -> None:
        """Initialize router sub-systems"""
        # Initialize fallback manager
        await self.fallback_manager.initialize(self.providers)

        # Initialize load balancer
        await self.load_balancer.initialize(self.providers)

        logger.info("Router sub-systems initialized")

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text completion with cost optimization"""
        if not self._initialized:
            await self.initialize()

        request_id = str(uuid.uuid4())

        # Check cache first
        if not request.stream:
            cached_response = await cache.get_cached_response(request)
            if cached_response:
                logger.info("Cache hit", request_id=request_id)
                cached_response.request_id = request_id
                cached_response.cached = True
                return cached_response

        # Get routing decision
        routing_decision = await self.decision_engine.select_provider(
            request, budget_remaining=float('inf')  # TODO: Get from budget manager
        )

        # Start metrics tracking
        metrics.start_request(request_id, routing_decision.selected_provider, routing_decision.selected_model)

        try:
            # Generate response with fallback
            response = await self._generate_with_fallback(request, routing_decision, request_id)

            # Cache response
            if not request.stream:
                await cache.cache_response(request, response)

            # Complete metrics tracking
            metrics.complete_request(
                request_id=request_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_usd=response.cost_usd,
                success=True
            )

            # Update provider performance
            self.decision_engine.update_provider_performance(
                routing_decision.selected_provider,
                True,
                response.processing_time_ms
            )

            return response

        except Exception as e:
            # Log error and update metrics
            metrics.complete_request(
                request_id=request_id,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                success=False
            )

            # Update provider performance
            self.decision_engine.update_provider_performance(
                routing_decision.selected_provider,
                False,
                0
            )

            logger.error(f"Generation failed", request_id=request_id, error=str(e))
            raise

    async def generate_stream(
        self, request: GenerationRequest
    ) -> AsyncGenerator[str, None]:
        """Generate text completion with streaming"""
        if not self._initialized:
            await self.initialize()

        request_id = str(uuid.uuid4())

        # Get routing decision
        routing_decision = await self.decision_engine.select_provider(
            request, budget_remaining=float('inf')  # TODO: Get from budget manager
        )

        # Start metrics tracking
        metrics.start_request(request_id, routing_decision.selected_provider, routing_decision.selected_model)

        try:
            # Get provider
            provider = self.providers[routing_decision.selected_provider]

            # Stream response
            start_time = time.time()
            content_chunks = []

            async for chunk in provider.generate_stream(request):
                content_chunks.append(chunk)
                yield chunk

            # Calculate metrics
            processing_time_ms = int((time.time() - start_time) * 1000)
            total_content = "".join(content_chunks)

            # Estimate tokens (rough approximation)
            input_tokens = provider._count_messages_tokens(request.messages)
            output_tokens = provider._count_tokens(total_content)
            cost = provider.calculate_cost(input_tokens, output_tokens)

            # Complete metrics tracking
            metrics.complete_request(
                request_id=request_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                success=True
            )

            # Update provider performance
            self.decision_engine.update_provider_performance(
                routing_decision.selected_provider,
                True,
                processing_time_ms
            )

        except Exception as e:
            # Log error and update metrics
            metrics.complete_request(
                request_id=request_id,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                success=False
            )

            # Update provider performance
            self.decision_engine.update_provider_performance(
                routing_decision.selected_provider,
                False,
                0
            )

            logger.error(f"Streaming generation failed", request_id=request_id, error=str(e))
            raise

    async def _generate_with_fallback(
        self,
        request: GenerationRequest,
        routing_decision: RoutingDecision,
        request_id: str
    ) -> GenerationResponse:
        """Generate response with fallback chain"""
        providers_to_try = [routing_decision.selected_provider] + routing_decision.fallback_chain

        last_error = None

        for i, provider_type in enumerate(providers_to_try):
            try:
                provider = self.providers[provider_type]

                # Wait for rate limit if needed
                can_proceed = await rate_limiter.wait_if_needed(
                    provider_type, request.user_id, max_wait_seconds=30
                )

                if not can_proceed:
                    raise Exception(f"Rate limit exceeded for {provider_type.value}")

                # Generate response
                response = await provider.generate(request)
                response.request_id = request_id

                if i > 0:  # Fallback was used
                    logger.info(
                        "Fallback successful",
                        request_id=request_id,
                        original_provider=routing_decision.selected_provider.value,
                        fallback_provider=provider_type.value,
                        fallback_attempt=i
                    )

                return response

            except Exception as e:
                last_error = e
                logger.warning(
                    "Provider failed, trying fallback",
                    request_id=request_id,
                    provider=provider_type.value,
                    error=str(e),
                    attempt=i + 1
                )

                # Update provider performance
                self.decision_engine.update_provider_performance(
                    provider_type,
                    False,
                    0
                )

                continue

        # All providers failed
        raise Exception(f"All providers failed. Last error: {str(last_error)}")

    async def health_check(self) -> Dict[str, any]:
        """Perform health check on all providers"""
        if not self._initialized:
            await self.initialize()

        health_results = {}
        overall_healthy = True

        for provider_type, provider in self.providers.items():
            try:
                health_result = await provider.health_check()
                health_results[provider_type.value] = health_result
                if health_result.get("status") != "healthy":
                    overall_healthy = False
            except Exception as e:
                health_results[provider_type.value] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                overall_healthy = False

        return {
            "router_healthy": overall_healthy,
            "providers": health_results,
            "total_providers": len(self.providers),
            "healthy_providers": sum(1 for r in health_results.values() if r.get("status") == "healthy"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_provider_info(self) -> Dict[str, any]:
        """Get information about all registered providers"""
        if not self._initialized:
            return {"initialized": False, "providers": []}

        provider_info = {}
        for provider_type, provider in self.providers.items():
            provider_info[provider_type.value] = provider.get_provider_info()

        return {
            "initialized": True,
            "providers": provider_info,
            "total_providers": len(self.providers),
            "routing_stats": self.decision_engine.get_routing_statistics()
        }

    async def get_cost_analysis(self, hours: int = 24) -> Dict[str, any]:
        """Get cost analysis for the specified period"""
        cost_summary = metrics.get_cost_summary(hours)
        provider_stats = {}

        for provider_type in self.providers:
            provider_stats[provider_type.value] = metrics.get_provider_stats(provider_type)

        return {
            "period_hours": hours,
            "cost_summary": cost_summary,
            "provider_stats": provider_stats,
            "total_cost": cost_summary["total_cost_usd"],
            "average_cost_per_hour": cost_summary["average_cost_per_hour"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def shutdown(self) -> None:
        """Shutdown the router"""
        logger.info("Shutting down router")

        # Disconnect from cache
        await cache.disconnect()

        # Disconnect from rate limiter
        await rate_limiter.disconnect()

        self._initialized = False
        logger.info("Router shutdown complete")


# Global router instance
router = CostOptimizedRouter()