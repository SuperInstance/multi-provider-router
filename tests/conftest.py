"""
Shared fixtures and test configuration for pytest
"""

import pytest
import asyncio
from typing import AsyncGenerator, Dict, Any
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timezone
import time

from multi_provider_router.models import (
    ProviderConfig,
    ProviderType,
    GenerationRequest,
    GenerationResponse,
    ChatMessage,
    PriorityLevel,
    RoutingDecision
)
from multi_provider_router.providers.base import BaseProvider
from multi_provider_router.providers.glm_provider import GLMProvider
from multi_provider_router.providers.openai_provider import OpenAIProvider
from multi_provider_router.providers.deepseek_provider import DeepSeekProvider
from multi_provider_router.providers.claude_provider import ClaudeProvider
from multi_provider_router.providers.deepinfra_provider import DeepInfraProvider


# ============================================================================
# Provider Config Fixtures
# ============================================================================

@pytest.fixture
def glm_config() -> ProviderConfig:
    """Create GLM provider config for testing"""
    return ProviderConfig(
        provider=ProviderType.GLM,
        model_name="glm-4",
        api_key="test-glm-key",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        cost_per_1m_input_tokens=0.25,
        cost_per_1m_output_tokens=0.25,
        max_tokens=8192,
        timeout=30,
        max_retries=3,
        rate_limit_per_minute=60,
        is_active=True,
        health_score=1.0
    )


@pytest.fixture
def openai_config() -> ProviderConfig:
    """Create OpenAI provider config for testing"""
    return ProviderConfig(
        provider=ProviderType.OPENAI,
        model_name="gpt-3.5-turbo",
        api_key="test-openai-key",
        base_url="https://api.openai.com/v1",
        cost_per_1m_input_tokens=0.50,
        cost_per_1m_output_tokens=1.50,
        max_tokens=4096,
        timeout=30,
        max_retries=3,
        rate_limit_per_minute=60,
        is_active=True,
        health_score=1.0
    )


@pytest.fixture
def deepseek_config() -> ProviderConfig:
    """Create DeepSeek provider config for testing"""
    return ProviderConfig(
        provider=ProviderType.DEEPSEEK,
        model_name="deepseek-chat",
        api_key="test-deepseek-key",
        base_url="https://api.deepseek.com/v1",
        cost_per_1m_input_tokens=0.14,
        cost_per_1m_output_tokens=0.28,
        max_tokens=8192,
        timeout=30,
        max_retries=3,
        rate_limit_per_minute=50,
        is_active=True,
        health_score=1.0
    )


@pytest.fixture
def claude_config() -> ProviderConfig:
    """Create Claude provider config for testing"""
    return ProviderConfig(
        provider=ProviderType.CLAUDE,
        model_name="claude-3-haiku-20240307",
        api_key="test-claude-key",
        base_url="https://api.anthropic.com/v1",
        cost_per_1m_input_tokens=0.25,
        cost_per_1m_output_tokens=1.25,
        max_tokens=8192,
        timeout=30,
        max_retries=3,
        rate_limit_per_minute=50,
        is_active=True,
        health_score=1.0
    )


@pytest.fixture
def deepinfra_config() -> ProviderConfig:
    """Create DeepInfra provider config for testing"""
    return ProviderConfig(
        provider=ProviderType.DEEPINFRA,
        model_name="wizardlm-2-8x22b",
        api_key="test-deepinfra-key",
        base_url="https://api.deepinfra.com/v1/openai",
        cost_per_1m_input_tokens=0.07,
        cost_per_1m_output_tokens=0.07,
        max_tokens=8192,
        timeout=30,
        max_retries=3,
        rate_limit_per_minute=30,
        is_active=True,
        health_score=1.0
    )


@pytest.fixture
def all_provider_configs(
    glm_config,
    openai_config,
    deepseek_config,
    claude_config,
    deepinfra_config
) -> Dict[ProviderType, ProviderConfig]:
    """Get all provider configs as a dictionary"""
    return {
        ProviderType.GLM: glm_config,
        ProviderType.OPENAI: openai_config,
        ProviderType.DEEPSEEK: deepseek_config,
        ProviderType.CLAUDE: claude_config,
        ProviderType.DEEPINFRA: deepinfra_config
    }


# ============================================================================
# Request/Response Fixtures
# ============================================================================

@pytest.fixture
def sample_messages() -> list[ChatMessage]:
    """Create sample chat messages"""
    return [
        ChatMessage(role="user", content="Hello, how are you?"),
        ChatMessage(role="assistant", content="I'm doing well, thank you!"),
        ChatMessage(role="user", content="Can you help me write some code?")
    ]


@pytest.fixture
def simple_request() -> GenerationRequest:
    """Create a simple generation request"""
    return GenerationRequest(
        messages=[
            ChatMessage(role="user", content="Hello, how are you?")
        ],
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        stream=False,
        user_id="test-user-123",
        session_id="test-session-456",
        priority=PriorityLevel.NORMAL
    )


@pytest.fixture
def complex_request() -> GenerationRequest:
    """Create a complex generation request"""
    return GenerationRequest(
        messages=[
            ChatMessage(role="system", content="You are a helpful coding assistant."),
            ChatMessage(role="user", content="Write a Python function to calculate fibonacci numbers"),
            ChatMessage(role="assistant", content="I'll help you with that."),
            ChatMessage(role="user", content="Please include error handling and docstrings")
        ],
        temperature=0.5,
        max_tokens=500,
        top_p=0.9,
        stream=False,
        user_id="test-user-123",
        session_id="test-session-789",
        priority=PriorityLevel.HIGH,
        metadata={"request_type": "coding", "language": "python"}
    )


@pytest.fixture
def streaming_request() -> GenerationRequest:
    """Create a streaming generation request"""
    return GenerationRequest(
        messages=[
            ChatMessage(role="user", content="Tell me a story")
        ],
        temperature=0.8,
        max_tokens=200,
        stream=True,
        user_id="test-user-456"
    )


@pytest.fixture
def sample_response() -> GenerationResponse:
    """Create a sample generation response"""
    return GenerationResponse(
        request_id="test-request-123",
        content="This is a test response",
        provider_used=ProviderType.GLM,
        model_used="glm-4",
        input_tokens=10,
        output_tokens=20,
        cost_usd=0.00001,
        processing_time_ms=500,
        cached=False,
        metadata={
            "temperature": 0.7,
            "max_tokens": 100
        }
    )


# ============================================================================
# Mock Provider Fixtures
# ============================================================================

@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient"""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "test-id",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "test-model",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Test response"
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }
    mock_response.raise_for_status = Mock()
    mock_client.post.return_value = mock_response
    mock_client.stream.return_value.__aenter__.return_value.aiter_lines.return_value = iter([
        'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{"content":" world"},"finish_reason":"stop"}]}',
        'data: [DONE]'
    ])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock()

    return mock_client


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock()
    redis_mock.keys = AsyncMock(return_value=[])
    redis_mock.delete = AsyncMock(return_value=0)
    redis_mock.info = AsyncMock(return_value={
        'used_memory': 1000000,
        'used_memory_human': '1B',
        'db': {'db0': 100}
    })
    redis_mock.ttl = AsyncMock(return_value=3600)
    redis_mock.expire = AsyncMock()
    redis_mock.pipeline = MagicMock()
    redis_mock.pipeline.return_value.__aenter__.return_value.execute = AsyncMock(return_value=[0, 0, 0, 0, 0, 0])
    redis_mock.zremrangebyscore = AsyncMock()
    redis_mock.zcard = AsyncMock(return_value=0)
    redis_mock.zadd = AsyncMock()
    return redis_mock


# ============================================================================
# Async Event Loop Fixture
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Provider Instance Fixtures
# ============================================================================

@pytest.fixture
async def glm_provider(glm_config, mock_httpx_client):
    """Create GLM provider with mocked httpx"""
    import httpx
    with pytest.mock.patch('httpx.AsyncClient', return_value=mock_httpx_client):
        provider = GLMProvider(glm_config)
        yield provider


@pytest.fixture
async def openai_provider(openai_config, mock_httpx_client):
    """Create OpenAI provider with mocked httpx"""
    import httpx
    with pytest.mock.patch('httpx.AsyncClient', return_value=mock_httpx_client):
        provider = OpenAIProvider(openai_config)
        yield provider


# ============================================================================
# Test Data Helper Functions
# ============================================================================

def create_mock_api_response(content: str, input_tokens: int = 10, output_tokens: int = 20) -> Dict[str, Any]:
    """Helper to create mock API response"""
    return {
        "id": "test-id",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "test-model",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": content
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }
    }


def create_mock_stream_chunk(content: str, finish_reason: str = None) -> str:
    """Helper to create mock streaming chunk"""
    chunk = {
        "choices": [{
            "delta": {"content": content},
            "finish_reason": finish_reason
        }]
    }
    return f'data: {chunk}'
