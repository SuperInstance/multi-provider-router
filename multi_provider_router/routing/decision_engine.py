"""
Routing decision engine for intelligent provider selection
"""

import time
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import asyncio

from ..models import (
    ProviderType,
    GenerationRequest,
    RoutingDecision,
    PriorityLevel,
    SpecialtyModel
)
from ..providers.base import BaseProvider
from ..utils.logger import get_logger, log_routing_decision
from ..utils.metrics import metrics
from ..utils.health_checker import health_checker
from ..utils.rate_limiter import rate_limiter
from ..config import get_settings

settings = get_settings()
logger = get_logger("routing_decision")


@dataclass
class ProviderScore:
    """Provider scoring for routing decisions"""
    provider: ProviderType
    score: float
    cost_estimate: float
    quality_estimate: float
    availability_score: float
    performance_score: float
    reasoning: List[str]


class RoutingDecisionEngine:
    """Intelligent routing decision engine"""

    def __init__(self):
        self.providers: Dict[ProviderType, BaseProvider] = {}
        self.cost_sensitivity = settings.routing.cost_sensitivity_factor
        self.quality_weight = settings.routing.quality_weight
        self.glm_primary_weight = settings.routing.glm_primary_weight

        # Performance tracking
        self._provider_success_rates: Dict[ProviderType, float] = {}
        self._provider_response_times: Dict[ProviderType, float] = {}
        self._last_update = datetime.now(timezone.utc)

    def register_provider(self, provider: BaseProvider) -> None:
        """Register a provider for routing"""
        self.providers[provider.provider_type] = provider
        self._provider_success_rates[provider.provider_type] = 1.0
        self._provider_response_times[provider.provider_type] = 1000.0  # Default 1 second

    async def select_provider(
        self,
        request: GenerationRequest,
        budget_remaining: float = float('inf')
    ) -> RoutingDecision:
        """Select the best provider for a request"""
        start_time = time.time()

        # Analyze request characteristics
        request_analysis = self._analyze_request(request)

        # Get candidate providers
        candidates = await self._get_candidate_providers(request, request_analysis, budget_remaining)

        if not candidates:
            raise ValueError("No suitable providers available")

        # Score each candidate
        scored_providers = await self._score_providers(candidates, request, request_analysis)

        # Select the best provider
        best_provider = max(scored_providers, key=lambda x: x.score)

        # Create fallback chain
        fallback_chain = [p.provider for p in sorted(scored_providers, key=lambda x: x.score, reverse=True)[1:4]]

        # Create routing decision
        decision = RoutingDecision(
            request_id=str(uuid.uuid4()),  # Will be overridden by caller
            selected_provider=best_provider.provider,
            selected_model=self._get_model_for_provider(best_provider.provider, request),
            routing_score=best_provider.score,
            reasoning="; ".join(best_provider.reasoning),
            cost_estimate_usd=best_provider.cost_estimate,
            quality_estimate=best_provider.quality_estimate,
            fallback_chain=fallback_chain,
            routing_time_ms=int((time.time() - start_time) * 1000)
        )

        # Log the decision
        log_routing_decision(
            request_id=decision.request_id,
            selected_provider=best_provider.provider.value,
            reasoning=decision.reasoning,
            cost_estimate=decision.cost_estimate_usd,
            request_type=request_analysis.get("type", "unknown"),
            complexity=request_analysis.get("complexity", 0.0)
        )

        # Update metrics
        metrics.log_routing_decision(
            request_id=decision.request_id,
            selected_provider=best_provider.provider.value,
            reasoning=decision.reasoning,
            cost_estimate=decision.cost_estimate_usd
        )

        return decision

    def _analyze_request(self, request: GenerationRequest) -> Dict[str, any]:
        """Analyze request characteristics for routing decisions"""
        content = " ".join(msg.content for msg in request.messages)
        estimated_tokens = len(content) // 4  # Rough estimation

        # Determine request type
        request_type = self._classify_request_type(content)

        # Calculate complexity
        complexity = self._calculate_complexity(content, estimated_tokens)

        # Check for specialty requirements
        needs_specialty = self._needs_specialty_model(content, request)

        return {
            "type": request_type,
            "complexity": complexity,
            "estimated_tokens": estimated_tokens,
            "content_length": len(content),
            "needs_specialty": needs_specialty,
            "priority": request.priority,
            "has_specialty_request": request.force_specialty_model is not None,
            "preferred_provider": request.preferred_provider
        }

    def _classify_request_type(self, content: str) -> str:
        """Classify the type of request"""
        content_lower = content.lower()

        type_indicators = {
            "conversation": ["hello", "hi", "how are", "what do you", "tell me", "chat"],
            "coding": ["code", "programming", "function", "debug", "algorithm", "```"],
            "creative": ["story", "write", "create", "imagine", "poem", "creative"],
            "analysis": ["analyze", "analysis", "evaluate", "compare", "review"],
            "summarization": ["summarize", "summary", "key points", "brief", "concise"],
            "technical": ["technical", "api", "integration", "architecture", "system"],
            "reasoning": ["reason", "logic", "explain why", "how does", "mechanism"],
            "math": ["calculate", "math", "equation", "formula", "statistics"]
        }

        type_scores = {}
        for request_type, indicators in type_indicators.items():
            score = sum(1 for indicator in indicators if indicator in content_lower)
            type_scores[request_type] = score

        if max(type_scores.values()) == 0:
            return "general"

        return max(type_scores.items(), key=lambda x: x[1])[0]

    def _calculate_complexity(self, content: str, estimated_tokens: int) -> float:
        """Calculate request complexity score (0.0 to 1.0)"""
        complexity_score = 0.0

        # Token-based complexity
        if estimated_tokens > 2000:
            complexity_score += 0.3
        elif estimated_tokens > 1000:
            complexity_score += 0.15

        # Content-based complexity
        complex_words = [
            "analyze", "comprehensive", "intricate", "sophisticated",
            "complex", "detailed", "thorough", "extensive"
        ]
        complex_word_count = sum(1 for word in complex_words if word in content.lower())
        complexity_score += min(0.4, complex_word_count * 0.1)

        # Structure-based complexity
        if "step by step" in content.lower():
            complexity_score += 0.1
        if "```" in content:  # Code blocks
            complexity_score += 0.1
        if "?" in content and content.count("?") > 3:  # Multiple questions
            complexity_score += 0.1

        return min(1.0, complexity_score)

    def _needs_specialty_model(self, content: str, request: GenerationRequest) -> bool:
        """Check if request needs a specialty model"""
        if request.force_specialty_model:
            return True

        specialty_indicators = [
            "complex reasoning", "deep analysis", "comprehensive study",
            "creative writing", "narrative", "fiction",
            "heavy computation", "intensive analysis",
            "research", "investigation", "thesis"
        ]

        return any(indicator in content.lower() for indicator in specialty_indicators)

    async def _get_candidate_providers(
        self,
        request: GenerationRequest,
        analysis: Dict[str, any],
        budget_remaining: float
    ) -> List[ProviderType]:
        """Get list of candidate providers for the request"""
        candidates = []

        # Check for forced specialty model
        if analysis["needs_specialty"] and ProviderType.DEEPINFRA in self.providers:
            candidates.append(ProviderType.DEEPINFRA)

        # Check for preferred provider
        if analysis["preferred_provider"] and analysis["preferred_provider"] in self.providers:
            candidates.append(analysis["preferred_provider"])

        # Add GLM-4 as primary (95% weight)
        if ProviderType.GLM in self.providers:
            if random.random() < self.glm_primary_weight:
                candidates.insert(0, ProviderType.GLM)
            else:
                candidates.append(ProviderType.GLM)

        # Add other providers based on request type
        request_type = analysis["type"]
        complexity = analysis["complexity"]

        if request_type == "coding" and ProviderType.DEEPSEEK in self.providers:
            candidates.append(ProviderType.DEEPSEEK)
        elif request_type in ["conversation", "summarization", "analysis"] and ProviderType.CLAUDE in self.providers:
            candidates.append(ProviderType.CLAUDE)
        elif complexity > 0.7 and ProviderType.DEEPINFRA in self.providers:
            candidates.append(ProviderType.DEEPINFRA)

        # Add OpenAI as fallback
        if ProviderType.OPENAI in self.providers:
            candidates.append(ProviderType.OPENAI)

        # Remove duplicates and filter by availability
        unique_candidates = list(dict.fromkeys(candidates))  # Preserve order, remove duplicates

        available_candidates = []
        for provider_type in unique_candidates:
            provider = self.providers.get(provider_type)
            if not provider:
                continue

            # Check health
            if not health_checker.is_healthy(provider_type):
                continue

            # Check rate limits
            can_proceed, _ = await rate_limiter.check_rate_limit(provider_type, request.user_id)
            if not can_proceed:
                continue

            # Check budget
            estimated_cost = provider.estimate_request_cost(request)
            if estimated_cost > budget_remaining:
                continue

            available_candidates.append(provider_type)

        return available_candidates

    async def _score_providers(
        self,
        providers: List[ProviderType],
        request: GenerationRequest,
        analysis: Dict[str, any]
    ) -> List[ProviderScore]:
        """Score each provider for the request"""
        scored_providers = []

        for provider_type in providers:
            provider = self.providers[provider_type]
            score_data = await self._calculate_provider_score(provider, request, analysis)
            scored_providers.append(score_data)

        return scored_providers

    async def _calculate_provider_score(
        self,
        provider: BaseProvider,
        request: GenerationRequest,
        analysis: Dict[str, any]
    ) -> ProviderScore:
        """Calculate comprehensive score for a provider"""
        # Cost score (lower cost = higher score)
        cost_estimate = provider.estimate_request_cost(request)
        cost_score = max(0.0, 1.0 - (cost_estimate / 0.10))  # Normalize against $0.10

        # Quality score
        quality_score = provider.get_quality_score()

        # Availability score (health and rate limits)
        health_score = health_checker.get_provider_health_score(provider.provider_type)
        can_proceed, rate_limit_remaining = await rate_limiter.check_rate_limit(
            provider.provider_type, request.user_id
        )
        rate_limit_score = 1.0 if can_proceed else 0.0
        availability_score = (health_score * 0.7) + (rate_limit_score * 0.3)

        # Performance score (response time and success rate)
        success_rate = self._provider_success_rates.get(provider.provider_type, 1.0)
        response_time = self._provider_response_times.get(provider.provider_type, 1000.0)
        performance_score = (success_rate * 0.6) + max(0.0, 1.0 - (response_time / 5000.0)) * 0.4

        # Suitability score for request type
        suitability_score = 0.5  # Default
        if provider.is_cost_effective_for(request):
            suitability_score += 0.3
        if analysis.get("type"):
            suitability_score += self._get_type_suitability_score(provider.provider_type, analysis["type"])

        # Final weighted score
        final_score = (
            cost_score * (1.0 - self.cost_sensitivity) * 0.3 +
            quality_score * self.quality_weight * 0.25 +
            availability_score * 0.2 +
            performance_score * 0.15 +
            suitability_score * 0.1
        )

        # Generate reasoning
        reasoning = []
        if cost_score > 0.8:
            reasoning.append("Cost-effective")
        if quality_score > 0.85:
            reasoning.append("High quality")
        if health_score > 0.9:
            reasoning.append("Excellent health")
        if performance_score > 0.8:
            reasoning.append("Good performance")
        if provider.is_cost_effective_for(request):
            reasoning.append("Well-suited for request type")

        return ProviderScore(
            provider=provider.provider_type,
            score=final_score,
            cost_estimate=cost_estimate,
            quality_estimate=quality_score,
            availability_score=availability_score,
            performance_score=performance_score,
            reasoning=reasoning
        )

    def _get_type_suitability_score(self, provider_type: ProviderType, request_type: str) -> float:
        """Get suitability score for provider type and request type"""
        suitability_matrix = {
            ProviderType.GLM: {
                "general": 0.9, "conversation": 0.85, "coding": 0.8,
                "analysis": 0.75, "creative": 0.7, "summarization": 0.8
            },
            ProviderType.DEEPSEEK: {
                "coding": 0.95, "math": 0.9, "reasoning": 0.85,
                "technical": 0.8, "general": 0.7
            },
            ProviderType.CLAUDE: {
                "conversation": 0.95, "summarization": 0.9, "analysis": 0.85,
                "creative": 0.8, "general": 0.8
            },
            ProviderType.OPENAI: {
                "general": 0.85, "technical": 0.8, "coding": 0.75,
                "structured": 0.9, "api": 0.85
            },
            ProviderType.DEEPINFRA: {
                "reasoning": 0.95, "creative": 0.9, "analysis": 0.85,
                "complex": 0.95, "research": 0.9
            }
        }

        return suitability_matrix.get(provider_type, {}).get(request_type, 0.5)

    def _get_model_for_provider(self, provider_type: ProviderType, request: GenerationRequest) -> str:
        """Get the appropriate model for a provider"""
        provider = self.providers.get(provider_type)
        if not provider:
            return "unknown"

        # For DeepInfra, let the provider select the model
        if provider_type == ProviderType.DEEPINFRA:
            if hasattr(provider, '_select_model'):
                return provider._select_model(request)

        return provider.model_name

    def update_provider_performance(
        self,
        provider_type: ProviderType,
        success: bool,
        response_time_ms: int
    ) -> None:
        """Update provider performance metrics"""
        # Update success rate with exponential moving average
        current_rate = self._provider_success_rates.get(provider_type, 1.0)
        alpha = 0.1  # Learning rate
        new_rate = (alpha * (1.0 if success else 0.0)) + ((1 - alpha) * current_rate)
        self._provider_success_rates[provider_type] = new_rate

        # Update response time with exponential moving average
        current_time = self._provider_response_times.get(provider_type, 1000.0)
        new_time = (alpha * response_time_ms) + ((1 - alpha) * current_time)
        self._provider_response_times[provider_type] = new_time

        self._last_update = datetime.now(timezone.utc)

    def get_routing_statistics(self) -> Dict[str, any]:
        """Get routing statistics"""
        return {
            "registered_providers": list(self.providers.keys()),
            "provider_success_rates": self._provider_success_rates.copy(),
            "provider_response_times": self._provider_response_times.copy(),
            "last_update": self._last_update.isoformat(),
            "cost_sensitivity": self.cost_sensitivity,
            "quality_weight": self.quality_weight,
            "glm_primary_weight": self.glm_primary_weight
        }