"""
Comprehensive tests for all provider implementations
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import time
import json

from multi_provider_router.models import (
    ProviderConfig,
    ProviderType,
    GenerationRequest,
    GenerationResponse,
    ChatMessage
)
from multi_provider_router.providers.glm_provider import GLMProvider
from multi_provider_router.providers.openai_provider import OpenAIProvider
from multi_provider_router.providers.deepseek_provider import DeepSeekProvider
from multi_provider_router.providers.claude_provider import ClaudeProvider
from multi_provider_router.providers.deepinfra_provider import DeepInfraProvider
from conftest import create_mock_api_response


# ============================================================================
# Base Provider Tests
# ============================================================================

class TestBaseProvider:
    """Test base provider functionality"""

    def test_provider_initialization(self, glm_config):
        """Test provider initializes correctly"""
        provider = GLMProvider(glm_config)
        assert provider.provider_type == ProviderType.GLM
        assert provider.model_name == "glm-4"
        assert provider.config == glm_config

    def test_token_counting(self, glm_provider):
        """Test token counting approximation"""
        text = "Hello world! " * 20  # ~240 chars
        tokens = glm_provider._count_tokens(text)
        assert tokens == 60  # 240 / 4

    def test_messages_token_counting(self, glm_provider):
        """Test counting tokens in messages"""
        messages = [
            ChatMessage(role="user", content="Hello" * 20),
            ChatMessage(role="assistant", content="Hi there" * 20)
        ]
        tokens = glm_provider._count_messages_tokens(messages)
        assert tokens > 0

    def test_request_validation_valid(self, glm_provider, simple_request):
        """Test validation passes for valid request"""
        # Should not raise
        glm_provider.validate_request(simple_request)

    def test_request_validation_empty_messages(self, glm_provider):
        """Test validation fails for empty messages"""
        request = GenerationRequest(messages=[])
        with pytest.raises(ValueError, match="Messages cannot be empty"):
            glm_provider.validate_request(request)

    def test_request_validation_invalid_temperature(self, glm_provider, simple_request):
        """Test validation fails for invalid temperature"""
        simple_request.temperature = 3.0  # Invalid
        with pytest.raises(ValueError, match="Temperature must be between 0 and 2"):
            glm_provider.validate_request(request=simple_request)

    def test_request_validation_invalid_top_p(self, glm_provider, simple_request):
        """Test validation fails for invalid top_p"""
        simple_request.top_p = 1.5  # Invalid
        with pytest.raises(ValueError, match="Top_p must be between 0 and 1"):
            glm_provider.validate_request(request=simple_request)

    def test_request_validation_token_limit(self, glm_provider, simple_request):
        """Test validation fails for token limit exceeded"""
        simple_request.max_tokens = 100000
        with pytest.raises(ValueError, match="Token limit exceeded"):
            glm_provider.validate_request(simple_request)

    def test_get_provider_info(self, glm_provider):
        """Test getting provider information"""
        info = glm_provider.get_provider_info()
        assert info["provider"] == "glm"
        assert info["model"] == "glm-4"
        assert "supports_streaming" in info
        assert "is_active" in info

    def test_get_rate_limit_info(self, glm_provider):
        """Test getting rate limit information"""
        info = glm_provider.get_rate_limit_info()
        assert info["provider"] == "glm"
        assert "rate_limit_per_minute" in info
        assert "timeout" in info


# ============================================================================
# GLM Provider Tests
# ============================================================================

class TestGLMProvider:
    """Test GLM-4 provider implementation"""

    @pytest.mark.asyncio
    async def test_generate_success(self, glm_provider, simple_request, mock_httpx_client):
        """Test successful text generation"""
        # Mock the API call
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = create_mock_api_response("Test response")
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response

        response = await glm_provider.generate(simple_request)

        assert isinstance(response, GenerationResponse)
        assert response.content == "Test response"
        assert response.provider_used == ProviderType.GLM
        assert response.input_tokens > 0
        assert response.output_tokens > 0
        assert response.cost_usd >= 0

    @pytest.mark.asyncio
    async def test_generate_api_error(self, glm_provider, simple_request, mock_httpx_client):
        """Test API error handling"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status = Mock(side_effect=Exception("API Error"))
        mock_httpx_client.post.return_value = mock_response

        with pytest.raises(Exception, match="GLM API error"):
            await glm_provider.generate(simple_request)

    def test_prepare_request_data(self, glm_provider, simple_request):
        """Test request data preparation"""
        request_data = glm_provider._prepare_request_data(simple_request)

        assert request_data["model"] == "glm-4"
        assert "messages" in request_data
        assert request_data["temperature"] == 0.7
        assert request_data["top_p"] == 1.0
        assert len(request_data["messages"]) == len(simple_request.messages)

    def test_extract_content(self, glm_provider):
        """Test content extraction from response"""
        response_data = create_mock_api_response("Test content")
        content = glm_provider._extract_content(response_data)
        assert content == "Test content"

    def test_calculate_cost(self, glm_provider):
        """Test cost calculation"""
        cost = glm_provider.calculate_cost(1000, 500)
        expected = (1000 / 1_000_000) * 0.25 + (500 / 1_000_000) * 0.25
        assert abs(cost - expected) < 0.0001

    def test_estimate_request_cost(self, glm_provider, simple_request):
        """Test request cost estimation"""
        cost = glm_provider.estimate_request_cost(simple_request)
        assert cost >= 0

    def test_supports_streaming(self, glm_provider):
        """Test streaming support"""
        assert glm_provider.supports_streaming() == True

    def test_supports_function_calling(self, glm_provider):
        """Test function calling support"""
        assert glm_provider.supports_function_calling() == True

    def test_get_quality_score(self, glm_provider):
        """Test quality score"""
        score = glm_provider.get_quality_score()
        assert 0.0 <= score <= 1.0
        assert score == 0.85

    def test_get_performance_characteristics(self, glm_provider):
        """Test performance characteristics"""
        chars = glm_provider.get_performance_characteristics()
        assert "average_response_time_ms" in chars
        assert "cost_tier" in chars
        assert "specialties" in chars
        assert chars["cost_tier"] == "ultra_low"

    def test_is_cost_effective_for(self, glm_provider, simple_request):
        """Test cost effectiveness check"""
        assert glm_provider.is_cost_effective_for(simple_request) == True

    @pytest.mark.asyncio
    async def test_health_check_success(self, glm_provider, mock_httpx_client):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = create_mock_api_response("OK", 5, 5)
        mock_httpx_client.post.return_value = mock_response

        with patch('httpx.AsyncClient', return_value=mock_httpx_client):
            result = await glm_provider.health_check()
            assert result["status"] == "healthy"
            assert "response_time_ms" in result

    @pytest.mark.asyncio
    async def test_health_check_failure(self, glm_provider, mock_httpx_client):
        """Test failed health check"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_httpx_client.post.return_value = mock_response

        with patch('httpx.AsyncClient', return_value=mock_httpx_client):
            result = await glm_provider.health_check()
            assert result["status"] == "unhealthy"
            assert "error" in result


# ============================================================================
# OpenAI Provider Tests
# ============================================================================

class TestOpenAIProvider:
    """Test OpenAI provider implementation"""

    def test_provider_initialization(self, openai_provider):
        """Test OpenAI provider initialization"""
        assert openai_provider.provider_type == ProviderType.OPENAI
        assert openai_provider.model_name == "gpt-3.5-turbo"

    def test_prepare_request_data(self, openai_provider, simple_request):
        """Test OpenAI request data preparation"""
        request_data = openai_provider._prepare_request_data(simple_request)

        assert request_data["model"] == "gpt-3.5-turbo"
        assert "frequency_penalty" in request_data
        assert "presence_penalty" in request_data
        assert request_data["frequency_penalty"] == 0.0

    def test_calculate_cost(self, openai_provider):
        """Test OpenAI cost calculation"""
        cost = openai_provider.calculate_cost(1000, 500)
        expected = (1000 / 1_000_000) * 0.50 + (500 / 1_000_000) * 1.50
        assert abs(cost - expected) < 0.0001

    def test_supports_json_mode(self, openai_provider):
        """Test JSON mode support"""
        assert openai_provider.supports_json_mode() == True

    def test_analyze_request_complexity(self, openai_provider, simple_request):
        """Test request complexity analysis"""
        analysis = openai_provider.analyze_request_complexity(simple_request)
        assert "complexity_score" in analysis
        assert "indicators" in analysis
        assert 0.0 <= analysis["complexity_score"] <= 1.0

    def test_is_cost_effective_for_with_preference(self, openai_provider, simple_request):
        """Test cost effectiveness with preferred provider"""
        simple_request.preferred_provider = ProviderType.OPENAI
        assert openai_provider.is_cost_effective_for(simple_request) == True

    def test_get_fallback_priority(self, openai_provider):
        """Test fallback priority"""
        priority = openai_provider.get_fallback_priority()
        assert priority == 3


# ============================================================================
# DeepSeek Provider Tests
# ============================================================================

class TestDeepSeekProvider:
    """Test DeepSeek provider implementation"""

    def test_provider_initialization(self, deepseek_config):
        """Test DeepSeek provider initialization"""
        provider = DeepSeekProvider(deepseek_config)
        assert provider.provider_type == ProviderType.DEEPSEEK
        assert provider.model_name == "deepseek-chat"

    def test_calculate_cost(self, deepseek_config):
        """Test DeepSeek cost calculation"""
        provider = DeepSeekProvider(deepseek_config)
        cost = provider.calculate_cost(1000, 500)
        expected = (1000 / 1_000_000) * 0.14 + (500 / 1_000_000) * 0.28
        assert abs(cost - expected) < 0.0001


# ============================================================================
# Claude Provider Tests
# ============================================================================

class TestClaudeProvider:
    """Test Claude provider implementation"""

    def test_provider_initialization(self, claude_config):
        """Test Claude provider initialization"""
        provider = ClaudeProvider(claude_config)
        assert provider.provider_type == ProviderType.CLAUDE
        assert provider.model_name == "claude-3-haiku-20240307"

    def test_calculate_cost(self, claude_config):
        """Test Claude cost calculation"""
        provider = ClaudeProvider(claude_config)
        cost = provider.calculate_cost(1000, 500)
        expected = (1000 / 1_000_000) * 0.25 + (500 / 1_000_000) * 1.25
        assert abs(cost - expected) < 0.0001


# ============================================================================
# DeepInfra Provider Tests
# ============================================================================

class TestDeepInfraProvider:
    """Test DeepInfra provider implementation"""

    def test_provider_initialization(self, deepinfra_config):
        """Test DeepInfra provider initialization"""
        provider = DeepInfraProvider(deepinfra_config)
        assert provider.provider_type == ProviderType.DEEPINFRA
        assert provider.model_name == "wizardlm-2-8x22b"

    def test_calculate_cost(self, deepinfra_config):
        """Test DeepInfra cost calculation"""
        provider = DeepInfraProvider(deepinfra_config)
        cost = provider.calculate_cost(1000, 500)
        expected = (1000 / 1_000_000) * 0.07 + (500 / 1_000_000) * 0.07
        assert abs(cost - expected) < 0.0001


# ============================================================================
# Provider Comparison Tests
# ============================================================================

class TestProviderComparison:
    """Test cost and performance comparison across providers"""

    def test_cost_comparison_all_providers(
        self,
        glm_config,
        openai_config,
        deepseek_config,
        claude_config,
        deepinfra_config
    ):
        """Compare costs across all providers"""
        providers = {
            "GLM": GLMProvider(glm_config),
            "OpenAI": OpenAIProvider(openai_config),
            "DeepSeek": DeepSeekProvider(deepseek_config),
            "Claude": ClaudeProvider(claude_config),
            "DeepInfra": DeepInfraProvider(deepinfra_config)
        }

        costs = {}
        for name, provider in providers.items():
            cost = provider.calculate_cost(1000, 500)
            costs[name] = cost

        # DeepInfra should be cheapest
        assert costs["DeepInfra"] < costs["GLM"]
        # GLM should be cheaper than OpenAI
        assert costs["GLM"] < costs["OpenAI"]

    def test_quality_scores(self, glm_config, openai_config, deepseek_config):
        """Test quality scores across providers"""
        providers = {
            "GLM": GLMProvider(glm_config),
            "OpenAI": OpenAIProvider(openai_config),
            "DeepSeek": DeepSeekProvider(deepseek_config)
        }

        scores = {name: p.get_quality_score() for name, p in providers.items()}

        # All scores should be between 0 and 1
        for score in scores.values():
            assert 0.0 <= score <= 1.0

    def test_performance_characteristics(self, glm_config, openai_config):
        """Test performance characteristics"""
        glm = GLMProvider(glm_config)
        openai = OpenAIProvider(openai_config)

        glm_chars = glm.get_performance_characteristics()
        openai_chars = openai.get_performance_characteristics()

        assert "cost_tier" in glm_chars
        assert "cost_tier" in openai_chars
        assert "specialties" in glm_chars
        assert "specialties" in openai_chars


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestProviderErrorHandling:
    """Test error handling in providers"""

    @pytest.mark.asyncio
    async def test_timeout_error(self, glm_provider, simple_request):
        """Test timeout error handling"""
        import httpx

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception):
                await glm_provider.generate(simple_request)

    @pytest.mark.asyncio
    async def test_malformed_response(self, glm_provider, simple_request, mock_httpx_client):
        """Test handling of malformed API response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "response"}
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response

        with pytest.raises(ValueError, match="Invalid response format"):
            await glm_provider.generate(simple_request)

    def test_empty_response_content(self, glm_provider):
        """Test handling of empty response content"""
        response_data = {
            "choices": [{
                "message": {"content": ""}
            }]
        }
        content = glm_provider._extract_content(response_data)
        assert content == ""

    @pytest.mark.asyncio
    async def test_streaming_error(self, glm_provider, streaming_request):
        """Test streaming error handling"""
        import httpx

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.stream = Mock(side_effect=Exception("Stream error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception):
                async for _ in glm_provider.generate_stream(streaming_request):
                    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
