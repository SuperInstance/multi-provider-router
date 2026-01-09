"""
DeepSeek API provider implementation
"""

import json
import time
from typing import Dict, Any, AsyncGenerator
import httpx

from .base import BaseProvider
from ..models import GenerationRequest, GenerationResponse, ChatMessage
from ..utils.logger import logger


class DeepSeekProvider(BaseProvider):
    """DeepSeek API provider - Cost-effective alternative with strong coding capabilities"""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.base_url.rstrip('/')
        self.api_key = config.api_key
        self.timeout = config.timeout
        self.max_retries = config.max_retries

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text completion using DeepSeek API"""
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
        """Generate text completion with streaming using DeepSeek API"""
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
                logger.error(f"DeepSeek streaming error: {str(e)}")
                raise

    def _prepare_request_data(self, request: GenerationRequest) -> Dict[str, Any]:
        """Prepare request data for DeepSeek API"""
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

        # DeepSeek-specific parameters
        request_data["frequency_penalty"] = 0.0
        request_data["presence_penalty"] = 0.0

        return request_data

    def _parse_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse DeepSeek API response"""
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
        """Extract generated content from DeepSeek response"""
        if "choices" in response_data and response_data["choices"]:
            choice = response_data["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "")
        return ""

    def _extract_input_tokens(self, request: GenerationRequest, response_data: Dict[str, Any]) -> int:
        """Extract input token count from DeepSeek response"""
        if "usage" in response_data and "prompt_tokens" in response_data["usage"]:
            return response_data["usage"]["prompt_tokens"]
        return self._count_messages_tokens(request.messages)

    def _extract_output_tokens(self, response_data: Dict[str, Any]) -> int:
        """Extract output token count from DeepSeek response"""
        if "usage" in response_data and "completion_tokens" in response_data["usage"]:
            return response_data["usage"]["completion_tokens"]

        content = self._extract_content(response_data)
        return self._count_tokens(content)

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for DeepSeek usage"""
        input_cost = (input_tokens / 1_000_000) * self.config.cost_per_1m_input_tokens
        output_cost = (output_tokens / 1_000_000) * self.config.cost_per_1m_output_tokens
        return input_cost + output_cost

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers for DeepSeek API"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "LucidDreamer-Router/1.0"
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on DeepSeek API"""
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
        """DeepSeek supports streaming"""
        return True

    def supports_function_calling(self) -> bool:
        """DeepSeek supports function calling"""
        return True

    def get_rate_limits(self) -> Dict[str, int]:
        """Get DeepSeek rate limits"""
        return {
            "requests_per_minute": self.config.rate_limit_per_minute,
            "tokens_per_minute": 800_000,  # DeepSeek typical limit
            "max_concurrent_requests": 15
        }

    def estimate_request_cost(self, request: GenerationRequest) -> float:
        """Estimate cost for a request before making it"""
        input_tokens = self._count_messages_tokens(request.messages)
        estimated_output_tokens = request.max_tokens or 512  # Default estimate

        return self.calculate_cost(input_tokens, estimated_output_tokens)

    def is_cost_effective_for(self, request: GenerationRequest) -> bool:
        """Determine if DeepSeek is cost-effective for this request type"""
        # DeepSeek is particularly good for:
        # - Code generation and programming tasks
        # - Mathematical reasoning
        # - Technical documentation
        # - Logical reasoning

        content = " ".join(msg.content for msg in request.messages).lower()

        # Check for code-related content
        code_indicators = [
            "code", "programming", "function", "algorithm", "debug",
            "python", "javascript", "java", "cpp", "sql",
            "```", "def ", "class ", "import ", "function("
        ]

        has_code_content = any(indicator in content for indicator in code_indicators)

        # Check for math/reasoning content
        math_indicators = [
            "calculate", "solve", "equation", "formula", "mathematics",
            "probability", "statistics", "logic", "reasoning"
        ]

        has_math_content = any(indicator in content for indicator in math_indicators)

        return has_code_content or has_math_content

    def get_quality_score(self) -> float:
        """Get DeepSeek quality score (0.0 to 1.0)"""
        # DeepSeek provides excellent quality for coding tasks
        return 0.88  # Very high quality, especially for technical tasks

    def get_performance_characteristics(self) -> Dict[str, Any]:
        """Get DeepSeek performance characteristics"""
        return {
            "average_response_time_ms": 750,  # Typical response time
            "throughput_tokens_per_second": 180,
            "context_window": 4096,
            "supported_languages": ["en", "zh", "es", "fr", "de", "ja", "ko", "python", "javascript", "java", "cpp"],
            "specialties": [
                "code_generation",
                "mathematical_reasoning",
                "technical_writing",
                "logical_problem_solving",
                "debugging",
                "algorithm_design"
            ],
            "cost_tier": "very_low",  # $0.14/1M input tokens
            "quality_tier": "very_high",
            "strengths": [
                "Exceptional coding abilities",
                "Strong mathematical reasoning",
                "Cost-effective for technical tasks",
                "Good at debugging and optimization"
            ]
        }

    def get_optimal_temperature_range(self) -> Dict[str, float]:
        """Get optimal temperature range for DeepSeek"""
        return {
            "creative": 0.8,
            "balanced": 0.6,
            "precise": 0.2,
            "coding": 0.1  # Lower temperature for more consistent code
        }

    def analyze_request_complexity(self, request: GenerationRequest) -> Dict[str, Any]:
        """Analyze request complexity for routing decisions"""
        content = " ".join(msg.content for msg in request.messages)
        estimated_tokens = self._count_messages_tokens(content)

        # Analyze content characteristics
        complexity_indicators = {
            "has_code_blocks": "```" in content,
            "has_function_calls": any(word in content for word in ["def ", "function", "class "]),
            "has_math_expressions": any(char in content for char in ["∑", "∫", "√", "±", "≈"]),
            "has_technical_terms": len([word for word in ["algorithm", "data structure", "api", "database"] if word in content]),
            "estimated_token_count": estimated_tokens
        }

        # Calculate complexity score
        complexity_score = 0.0
        if complexity_indicators["has_code_blocks"]:
            complexity_score += 0.3
        if complexity_indicators["has_function_calls"]:
            complexity_score += 0.2
        if complexity_indicators["has_math_expressions"]:
            complexity_score += 0.2
        if complexity_indicators["has_technical_terms"] > 0:
            complexity_score += min(0.3, complexity_indicators["has_technical_terms"] * 0.1)

        return {
            "complexity_score": min(1.0, complexity_score),
            "indicators": complexity_indicators,
            "recommended": complexity_score > 0.3  # Recommend DeepSeek for complex technical content
        }