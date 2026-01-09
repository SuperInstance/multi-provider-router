"""
OpenAI API provider implementation
"""

import json
import time
from typing import Dict, Any, AsyncGenerator
import httpx

from .base import BaseProvider
from ..models import GenerationRequest, GenerationResponse, ChatMessage
from ..utils.logger import logger


class OpenAIProvider(BaseProvider):
    """OpenAI API provider - Reliable and versatile GPT models"""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.base_url.rstrip('/')
        self.api_key = config.api_key
        self.timeout = config.timeout
        self.max_retries = config.max_retries

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text completion using OpenAI API"""
        self.validate_request(request)

        async def api_call():
            request_data = self._prepare_request_data(request)

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
        return await self._make_request_with_tracking(request, api_call)

    async def generate_stream(
        self, request: GenerationRequest
    ) -> AsyncGenerator[str, None]:
        """Generate text completion with streaming using OpenAI API"""
        self.validate_request(request)

        request_data = self._prepare_request_data(request)
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
                logger.error(f"OpenAI streaming error: {str(e)}")
                raise

    def _prepare_request_data(self, request: GenerationRequest) -> Dict[str, Any]:
        """Prepare request data for OpenAI API"""
        messages = [
            {
                "role": msg.role,
                "content": msg.content,
                "name": msg.name
            }
            for msg in request.messages
            if msg.content.strip()  # Filter out empty messages
        ]

        request_data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": False,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }

        # Add max_tokens if specified
        if request.max_tokens:
            request_data["max_tokens"] = request.max_tokens

        # Add logit_bias if needed (can be extended)
        request_data["logit_bias"] = {}

        return request_data

    def _parse_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OpenAI API response"""
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
        """Extract generated content from OpenAI response"""
        if "choices" in response_data and response_data["choices"]:
            choice = response_data["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "")
        return ""

    def _extract_input_tokens(self, request: GenerationRequest, response_data: Dict[str, Any]) -> int:
        """Extract input token count from OpenAI response"""
        if "usage" in response_data and "prompt_tokens" in response_data["usage"]:
            return response_data["usage"]["prompt_tokens"]
        return self._count_messages_tokens(request.messages)

    def _extract_output_tokens(self, response_data: Dict[str, Any]) -> int:
        """Extract output token count from OpenAI response"""
        if "usage" in response_data and "completion_tokens" in response_data["usage"]:
            return response_data["usage"]["completion_tokens"]

        content = self._extract_content(response_data)
        return self._count_tokens(content)

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for OpenAI usage"""
        input_cost = (input_tokens / 1_000_000) * self.config.cost_per_1m_input_tokens
        output_cost = (output_tokens / 1_000_000) * self.config.cost_per_1m_output_tokens
        return input_cost + output_cost

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers for OpenAI API"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "LucidDreamer-Router/1.0"
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on OpenAI API"""
        start_time = time.time()

        try:
            # Create minimal test request
            test_request = GenerationRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                max_tokens=5,
                temperature=0.1
            )

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=self._prepare_request_data(test_request)
                )

                response_time_ms = int((time.time() - start_time) * 1000)

                if response.status_code == 200:
                    response_data = response.json()
                    usage = response_data.get("usage", {})

                    return {
                        "status": "healthy",
                        "response_time_ms": response_time_ms,
                        "model": self.model_name,
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
        """OpenAI supports streaming"""
        return True

    def supports_function_calling(self) -> bool:
        """OpenAI supports function calling"""
        return True

    def get_rate_limits(self) -> Dict[str, int]:
        """Get OpenAI rate limits"""
        return {
            "requests_per_minute": self.config.rate_limit_per_minute,
            "tokens_per_minute": 900_000,  # GPT-3.5-turbo typical limit
            "max_concurrent_requests": 20
        }

    def estimate_request_cost(self, request: GenerationRequest) -> float:
        """Estimate cost for a request before making it"""
        input_tokens = self._count_messages_tokens(request.messages)
        estimated_output_tokens = request.max_tokens or 512  # Default estimate

        return self.calculate_cost(input_tokens, estimated_output_tokens)

    def is_cost_effective_for(self, request: GenerationRequest) -> bool:
        """Determine if OpenAI is cost-effective for this request type"""
        # OpenAI GPT-3.5-turbo is good for:
        # - General conversation
        # - Code generation (moderate)
        # - Structured data processing
        # - When other providers are unavailable

        # Since OpenAI is typically more expensive than GLM-4 or DeepSeek,
        # only use it when specifically requested or as fallback

        if request.preferred_provider and request.preferred_provider.value == "openai":
            return True

        # Check if this is a fallback scenario
        content = " ".join(msg.content for msg in request.messages).lower()

        # OpenAI excels at certain specialized tasks
        specialized_indicators = [
            "openai", "gpt", "chatgpt",  # Explicit requests for OpenAI
            "json", "format", "structure",  # Structured output
            "api", "endpoint", "integration"  # Technical tasks
        ]

        return any(indicator in content for indicator in specialized_indicators)

    def get_quality_score(self) -> float:
        """Get OpenAI quality score (0.0 to 1.0)"""
        # GPT-3.5-turbo provides good quality but at higher cost
        return 0.82  # Good quality but more expensive

    def get_performance_characteristics(self) -> Dict[str, Any]:
        """Get OpenAI performance characteristics"""
        return {
            "average_response_time_ms": 900,  # Typical response time
            "throughput_tokens_per_second": 140,
            "context_window": 4096,
            "supported_languages": ["en", "es", "fr", "de", "ja", "ko", "zh", "pt", "it", "ru"],
            "specialties": [
                "general_conversation",
                "code_generation",
                "structured_output",
                "api_integration",
                "reliable_performance"
            ],
            "cost_tier": "moderate",  # $0.15/1M input tokens
            "quality_tier": "high",
            "reliability_tier": "very_high",
            "strengths": [
                "Highly reliable infrastructure",
                "Consistent performance",
                "Good balance of speed and quality",
                "Excellent documentation and community support",
                "Strong ecosystem and tooling"
            ]
        }

    def get_optimal_temperature_range(self) -> Dict[str, float]:
        """Get optimal temperature range for OpenAI"""
        return {
            "creative": 0.8,
            "balanced": 0.7,
            "precise": 0.2,
            "coding": 0.1
        }

    def analyze_request_complexity(self, request: GenerationRequest) -> Dict[str, Any]:
        """Analyze request complexity for routing decisions"""
        content = " ".join(msg.content for msg in request.messages)
        estimated_tokens = self._count_messages_tokens(content)

        # Analyze content characteristics
        complexity_indicators = {
            "has_structured_output_request": any(word in content.lower() for word in ["json", "xml", "format", "structure"]),
            "has_api_content": any(word in content.lower() for word in ["api", "endpoint", "request", "response"]),
            "has_code_blocks": "```" in content,
            "has_technical_terminology": len([word for word in ["integration", "implementation", "architecture"] if word in content]),
            "content_length": estimated_tokens,
            "requires_high_reliability": any(word in content.lower() for word in ["critical", "important", "production"])
        }

        # Calculate complexity score
        complexity_score = 0.0
        if complexity_indicators["has_structured_output_request"]:
            complexity_score += 0.3
        if complexity_indicators["has_api_content"]:
            complexity_score += 0.2
        if complexity_indicators["has_code_blocks"]:
            complexity_score += 0.2
        if complexity_indicators["requires_high_reliability"]:
            complexity_score += 0.3
        if complexity_indicators["has_technical_terminology"] > 0:
            complexity_score += min(0.2, complexity_indicators["has_technical_terminology"] * 0.1)

        return {
            "complexity_score": min(1.0, complexity_score),
            "indicators": complexity_indicators,
            "recommended_for_openai": complexity_score > 0.4 or complexity_indicators["requires_high_reliability"]
        }

    def get_fallback_priority(self) -> int:
        """Get fallback priority (lower number = higher priority)"""
        return 3  # Good fallback option after GLM-4, DeepSeek, Claude

    def supports_json_mode(self) -> bool:
        """Check if provider supports JSON mode"""
        return True  # GPT-3.5-turbo supports JSON mode

    def prepare_json_mode_request(self, request: GenerationRequest) -> Dict[str, Any]:
        """Prepare request with JSON mode if needed"""
        request_data = self._prepare_request_data(request)

        # Add JSON mode parameters if requested
        if request.metadata.get("json_mode", False):
            request_data["response_format"] = {"type": "json_object"}

        return request_data