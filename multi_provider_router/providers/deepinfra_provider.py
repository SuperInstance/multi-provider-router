"""
DeepInfra API provider implementation with specialty model support
"""

import json
import time
from typing import Dict, Any, AsyncGenerator, Optional
import httpx

from .base import BaseProvider
from ..models import (
    GenerationRequest,
    GenerationResponse,
    ChatMessage,
    ProviderConfig,
    SpecialtyModel
)
from ..utils.logger import logger


class DeepInfraProvider(BaseProvider):
    """DeepInfra API provider - Specialty models for heavy lifting tasks"""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.base_url.rstrip('/')
        self.api_key = config.api_key
        self.timeout = config.timeout
        self.max_retries = config.max_retries
        self.specialty_models = config.specialty_models

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text completion using DeepInfra API"""
        self.validate_request(request)

        # Determine which model to use
        model_name = self._select_model(request)

        async def api_call():
            request_data = self._prepare_request_data(request, model_name)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=request_data
                )
                response.raise_for_status()

                response_data = response.json()
                response_time_ms = int((time.time() - start_time) * 1000)

                return response_data, response_time_ms

        start_time = time.time()
        response = await self._make_request_with_tracking(request, api_call)
        response.model_used = model_name  # Override with actual model used
        return response

    async def generate_stream(
        self, request: GenerationRequest
    ) -> AsyncGenerator[str, None]:
        """Generate text completion with streaming using DeepInfra API"""
        self.validate_request(request)

        model_name = self._select_model(request)
        request_data = self._prepare_request_data(request, model_name)
        request_data["stream"] = True

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=request_data
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix

                            if data == "[DONE]":
                                break

                            try:
                                chunk_data = json.loads(data)
                                if "choices" in chunk_data and chunk_data["choices"]:
                                    delta = chunk_data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                continue

            except Exception as e:
                logger.error(f"DeepInfra streaming error: {str(e)}")
                raise

    def _select_model(self, request: GenerationRequest) -> str:
        """Select the best specialty model for the request"""
        # If a specific model is forced, use it
        if request.force_specialty_model:
            return request.force_specialty_model.value

        # Analyze request to determine best model
        content = " ".join(msg.content for msg in request.messages).lower()
        estimated_tokens = self._count_messages_tokens(content)

        # Determine use case based on content analysis
        if self._is_complex_reasoning(content, estimated_tokens):
            return SpecialtyModel.WIZARDLM.value
        elif self._is_creative_writing(content):
            return SpecialtyModel.NEMOTRON.value
        elif self._is_heavy_lifting_task(content, estimated_tokens):
            return SpecialtyModel.HERMES.value
        else:
            # Default to WizardLM for general complex tasks
            return SpecialtyModel.WIZARDLM.value

    def _is_complex_reasoning(self, content: str, estimated_tokens: int) -> bool:
        """Check if request requires complex reasoning"""
        reasoning_indicators = [
            "reason", "analyze", "evaluate", "compare", "logic",
            "algorithm", "complex", "intricate", "sophisticated",
            "problem solving", "critical thinking", "step by step",
            "explain why", "how does", "mechanism", "process"
        ]

        score = sum(1 for indicator in reasoning_indicators if indicator in content)
        return score >= 2 or estimated_tokens > 3000

    def _is_creative_writing(self, content: str) -> bool:
        """Check if request is for creative writing"""
        creative_indicators = [
            "story", "poem", "creative", "write", "narrative",
            "fiction", "novel", "character", "dialogue",
            "imagine", "create", "compose", "literary"
        ]

        score = sum(1 for indicator in creative_indicators if indicator in content)
        return score >= 2

    def _is_heavy_lifting_task(self, content: str, estimated_tokens: int) -> bool:
        """Check if request requires heavy computational lifting"""
        heavy_indicators = [
            "comprehensive", "detailed", "extensive", "thorough",
            "complete guide", "full analysis", "in-depth",
            "research", "investigation", "study"
        ]

        score = sum(1 for indicator in heavy_indicators if indicator in content)
        return score >= 1 or estimated_tokens > 5000

    def _prepare_request_data(self, request: GenerationRequest, model_name: str) -> Dict[str, Any]:
        """Prepare request data for DeepInfra API"""
        messages = [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in request.messages
        ]

        request_data = {
            "model": model_name,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": False
        }

        # Add max_tokens if specified
        if request.max_tokens:
            request_data["max_tokens"] = request.max_tokens
        else:
            # Set default max_tokens based on model
            model_config = self.specialty_models.get(model_name, {})
            request_data["max_tokens"] = model_config.get("max_tokens", 4096)

        # Model-specific parameters
        if model_name == SpecialtyModel.WIZARDLM.value:
            request_data["repetition_penalty"] = 1.1
        elif model_name == SpecialtyModel.NEMOTRON.value:
            request_data["repetition_penalty"] = 1.05
        elif model_name == SpecialtyModel.HERMES.value:
            request_data["repetition_penalty"] = 1.15

        return request_data

    def _parse_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse DeepInfra API response"""
        if "choices" not in response_data or not response_data["choices"]:
            raise ValueError("Invalid response format: missing choices")

        choice = response_data["choices"][0]
        if "message" not in choice:
            raise ValueError("Invalid response format: missing message")

        return {
            "content": choice["message"].get("content", ""),
            "usage": response_data.get("usage", {}),
            "finish_reason": choice.get("finish_reason"),
            "model": response_data.get("model"),
            "id": response_data.get("id"),
            "created": response_data.get("created")
        }

    def _extract_content(self, response_data: Dict[str, Any]) -> str:
        """Extract generated content from DeepInfra response"""
        if "choices" in response_data and response_data["choices"]:
            choice = response_data["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "")
        return ""

    def _extract_input_tokens(self, request: GenerationRequest, response_data: Dict[str, Any]) -> int:
        """Extract input token count from DeepInfra response"""
        if "usage" in response_data and "prompt_tokens" in response_data["usage"]:
            return response_data["usage"]["prompt_tokens"]
        return self._count_messages_tokens(request.messages)

    def _extract_output_tokens(self, response_data: Dict[str, Any]) -> int:
        """Extract output token count from DeepInfra response"""
        if "usage" in response_data and "completion_tokens" in response_data["usage"]:
            return response_data["usage"]["completion_tokens"]

        content = self._extract_content(response_data)
        return self._count_tokens(content)

    def calculate_cost(self, input_tokens: int, output_tokens: int, model_name: Optional[str] = None) -> float:
        """Calculate cost for DeepInfra usage"""
        if not model_name:
            model_name = self.model_name

        model_config = self.specialty_models.get(model_name, {})
        input_cost_per_m = model_config.get("cost_per_1m_input", 1.0)
        output_cost_per_m = model_config.get("cost_per_1m_output", 4.0)

        input_cost = (input_tokens / 1_000_000) * input_cost_per_m
        output_cost = (output_tokens / 1_000_000) * output_cost_per_m
        return input_cost + output_cost

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers for DeepInfra API"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "LucidDreamer-Router/1.0"
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on DeepInfra API"""
        start_time = time.time()

        try:
            # Test with WizardLM (default specialty model)
            test_request = GenerationRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                max_tokens=5,
                temperature=0.1,
                force_specialty_model=SpecialtyModel.WIZARDLM
            )

            model_name = self._select_model(test_request)
            request_data = self._prepare_request_data(test_request, model_name)

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=request_data
                )

                response_time_ms = int((time.time() - start_time) * 1000)

                if response.status_code == 200:
                    response_data = response.json()
                    usage = response_data.get("usage", {})

                    return {
                        "status": "healthy",
                        "response_time_ms": response_time_ms,
                        "model": model_name,
                        "test_tokens": usage.get("total_tokens", 0),
                        "timestamp": time.time()
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}: {response.text[:200]}",
                        "response_time_ms": response_time_ms,
                        "timestamp": time.time()
                    }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": int((time.time() - start_time) * 1000),
                "timestamp": time.time()
            }

    def supports_streaming(self) -> bool:
        """DeepInfra supports streaming"""
        return True

    def supports_function_calling(self) -> bool:
        """DeepInfra supports function calling on some models"""
        return True

    def get_rate_limits(self) -> Dict[str, int]:
        """Get DeepInfra rate limits"""
        return {
            "requests_per_minute": self.config.rate_limit_per_minute,
            "tokens_per_minute": 400_000,  # DeepInfra typical limit
            "max_concurrent_requests": 8
        }

    def estimate_request_cost(self, request: GenerationRequest) -> float:
        """Estimate cost for a request before making it"""
        model_name = self._select_model(request)
        input_tokens = self._count_messages_tokens(request.messages)
        estimated_output_tokens = request.max_tokens or 1024  # Default estimate for larger models

        return self.calculate_cost(input_tokens, estimated_output_tokens, model_name)

    def is_cost_effective_for(self, request: GenerationRequest) -> bool:
        """Determine if DeepInfra is cost-effective for this request type"""
        # DeepInfra is cost-effective for:
        # - Complex reasoning tasks
        # - Creative writing
        # - Heavy computational tasks
        # - When other providers can't handle the complexity

        # Check if specialty model is explicitly requested
        if request.force_specialty_model:
            return True

        content = " ".join(msg.content for msg in request.messages).lower()

        # Check for complex tasks that warrant specialty models
        complex_indicators = [
            "complex reasoning", "deep analysis", "comprehensive",
            "sophisticated", "intricate", "nuanced", "multi-step",
            "research", "investigation", "study", "thesis",
            "creative writing", "story", "narrative", "fiction",
            "heavy lifting", "intensive", "comprehensive guide"
        ]

        has_complex_content = any(indicator in content for indicator in complex_indicators)

        # Check for large content that might need special handling
        estimated_tokens = self._count_messages_tokens(content)
        is_large_content = estimated_tokens > 4000

        return has_complex_content or is_large_content

    def get_quality_score(self) -> float:
        """Get DeepInfra quality score (0.0 to 1.0)"""
        # DeepInfra models provide very high quality for specialized tasks
        return 0.92  # Very high quality for specialty models

    def get_performance_characteristics(self) -> Dict[str, Any]:
        """Get DeepInfra performance characteristics"""
        return {
            "average_response_time_ms": 1500,  # Slower but higher quality
            "throughput_tokens_per_second": 80,
            "context_window": 8192,
            "supported_languages": ["en", "es", "fr", "de", "ja", "ko", "zh", "pt", "it", "ru"],
            "specialties": [
                "complex_reasoning",
                "creative_writing",
                "heavy_computation",
                "research_analysis",
                "large_content_processing"
            ],
            "cost_tier": "high",  # Specialty models are more expensive
            "quality_tier": "very_high",
            "use_case": "specialty_tasks",
            "models": {
                SpecialtyModel.WIZARDLM.value: {
                    "strength": "Complex reasoning and problem solving",
                    "cost_per_1m_input": 0.5,
                    "cost_per_1m_output": 2.0,
                    "max_tokens": 8192
                },
                SpecialtyModel.NEMOTRON.value: {
                    "strength": "Creative writing and content generation",
                    "cost_per_1m_input": 0.8,
                    "cost_per_1m_output": 3.2,
                    "max_tokens": 4096
                },
                SpecialtyModel.HERMES.value: {
                    "strength": "Heavy lifting and comprehensive analysis",
                    "cost_per_1m_input": 1.0,
                    "cost_per_1m_output": 4.0,
                    "max_tokens": 8192
                }
            }
        }

    def get_model_recommendations(self, request: GenerationRequest) -> Dict[str, Any]:
        """Get model recommendations for the request"""
        content = " ".join(msg.content for msg in request.messages).lower()
        estimated_tokens = self._count_messages_tokens(content)

        recommendations = []
        reasoning_scores = {}

        # Score each model for this request
        wizardlm_score = 0.0
        nemotron_score = 0.0
        hermes_score = 0.0

        # WizardLM scoring
        if self._is_complex_reasoning(content, estimated_tokens):
            wizardlm_score += 0.8
        if "step by step" in content or "explain" in content:
            wizardlm_score += 0.3
        if "algorithm" in content or "logic" in content:
            wizardlm_score += 0.2

        # Nemotron scoring
        if self._is_creative_writing(content):
            nemotron_score += 0.8
        if "story" in content or "character" in content:
            nemotron_score += 0.3
        if "creative" in content or "imagine" in content:
            nemotron_score += 0.2

        # Hermes scoring
        if self._is_heavy_lifting_task(content, estimated_tokens):
            hermes_score += 0.8
        if estimated_tokens > 5000:
            hermes_score += 0.3
        if "comprehensive" in content or "detailed" in content:
            hermes_score += 0.2

        reasoning_scores = {
            SpecialtyModel.WIZARDLM.value: wizardlm_score,
            SpecialtyModel.NEMOTRON.value: nemotron_score,
            SpecialtyModel.HERMES.value: hermes_score
        }

        # Generate recommendations
        best_model = max(reasoning_scores.items(), key=lambda x: x[1])

        if best_model[1] > 0.5:
            recommendations.append({
                "model": best_model[0],
                "reason": self._get_model_reasoning(best_model[0], content),
                "confidence": best_model[1],
                "estimated_cost": self.estimate_request_cost(request)
            })

        return {
            "primary_recommendation": recommendations[0] if recommendations else None,
            "all_scores": reasoning_scores,
            "analysis": {
                "content_length": estimated_tokens,
                "is_complex_reasoning": self._is_complex_reasoning(content, estimated_tokens),
                "is_creative_writing": self._is_creative_writing(content),
                "is_heavy_lifting": self._is_heavy_lifting_task(content, estimated_tokens)
            }
        }

    def _get_model_reasoning(self, model_name: str, content: str) -> str:
        """Get reasoning for model selection"""
        if model_name == SpecialtyModel.WIZARDLM.value:
            return "Best for complex reasoning and step-by-step problem solving"
        elif model_name == SpecialtyModel.NEMOTRON.value:
            return "Optimal for creative writing and narrative generation"
        elif model_name == SpecialtyModel.HERMES.value:
            return "Ideal for comprehensive analysis and heavy computational tasks"
        else:
            return "Specialized model for advanced AI tasks"

    def get_fallback_priority(self) -> int:
        """Get fallback priority (lower number = higher priority)"""
        return 5  # Used for specialty tasks, not general fallback