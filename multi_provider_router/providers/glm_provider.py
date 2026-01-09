"""
GLM-4 API provider implementation
"""

import json
import time
from typing import Dict, Any, AsyncGenerator
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseProvider
from ..models import GenerationRequest, GenerationResponse, ChatMessage
from ..utils.logger import logger


class GLMProvider(BaseProvider):
    """GLM-4 API provider - Primary cost-optimized provider ($0.25/1M tokens)"""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.base_url.rstrip('/')
        self.api_key = config.api_key
        self.timeout = config.timeout
        self.max_retries = config.max_retries

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text completion using GLM-4 API"""
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
        """Generate text completion with streaming using GLM-4 API"""
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
                logger.error(f"GLM-4 streaming error: {str(e)}")
                raise

    def _prepare_request_data(self, request: GenerationRequest) -> Dict[str, Any]:
        """Prepare request data for GLM-4 API"""
        messages = [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in request.messages
        ]

        request_data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": False
        }

        # Add max_tokens if specified
        if request.max_tokens:
            request_data["max_tokens"] = request.max_tokens

        # Add user identification if available
        if request.user_id:
            request_data["user"] = request.user_id

        return request_data

    def _parse_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse GLM-4 API response"""
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
        """Extract generated content from GLM-4 response"""
        if "choices" in response_data and response_data["choices"]:
            choice = response_data["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "")
        return ""

    def _extract_input_tokens(self, request: GenerationRequest, response_data: Dict[str, Any]) -> int:
        """Extract input token count from GLM-4 response"""
        if "usage" in response_data and "prompt_tokens" in response_data["usage"]:
            return response_data["usage"]["prompt_tokens"]
        return self._count_messages_tokens(request.messages)

    def _extract_output_tokens(self, response_data: Dict[str, Any]) -> int:
        """Extract output token count from GLM-4 response"""
        if "usage" in response_data and "completion_tokens" in response_data["usage"]:
            return response_data["usage"]["completion_tokens"]

        content = self._extract_content(response_data)
        return self._count_tokens(content)

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for GLM-4 usage"""
        input_cost = (input_tokens / 1_000_000) * self.config.cost_per_1m_input_tokens
        output_cost = (output_tokens / 1_000_000) * self.config.cost_per_1m_output_tokens
        return input_cost + output_cost

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers for GLM-4 API"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "LucidDreamer-Router/1.0"
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on GLM-4 API"""
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
        """GLM-4 supports streaming"""
        return True

    def supports_function_calling(self) -> bool:
        """GLM-4 supports function calling"""
        return True

    def get_rate_limits(self) -> Dict[str, int]:
        """Get GLM-4 rate limits"""
        return {
            "requests_per_minute": self.config.rate_limit_per_minute,
            "tokens_per_minute": 1_000_000,  # GLM-4 typical limit
            "max_concurrent_requests": 20
        }

    def estimate_request_cost(self, request: GenerationRequest) -> float:
        """Estimate cost for a request before making it"""
        input_tokens = self._count_messages_tokens(request.messages)
        estimated_output_tokens = request.max_tokens or 512  # Default estimate

        return self.calculate_cost(input_tokens, estimated_output_tokens)

    def is_cost_effective_for(self, request: GenerationRequest) -> bool:
        """Determine if GLM-4 is cost-effective for this request type"""
        # GLM-4 is cost-effective for:
        # - General conversation
        # - Code generation
        # - Text processing
        # - Most standard use cases

        estimated_tokens = self._count_messages_tokens(request.messages)

        # Very large context might be better handled by specialized models
        if estimated_tokens > 6000:
            return False

        # GLM-4 is excellent for most use cases
        return True

    def get_quality_score(self) -> float:
        """Get GLM-4 quality score (0.0 to 1.0)"""
        # GLM-4 provides good quality for the cost
        return 0.85  # High quality for cost-effective model

    def get_performance_characteristics(self) -> Dict[str, Any]:
        """Get GLM-4 performance characteristics"""
        return {
            "average_response_time_ms": 800,  # Typical response time
            "throughput_tokens_per_second": 150,
            "context_window": 8192,
            "supported_languages": ["en", "zh", "es", "fr", "de", "ja", "ko"],
            "specialties": [
                "general_conversation",
                "code_generation",
                "text_processing",
                "reasoning",
                "multilingual_support"
            ],
            "cost_tier": "ultra_low",  # $0.25/1M input tokens
            "quality_tier": "high"
        }