"""
Configuration settings for Multi-Provider Router system
"""

from pydantic_settings import BaseSettings
from typing import Optional, Dict, List
import os


class ProviderSettings(BaseSettings):
    """Base settings for API providers"""
    api_key: str
    base_url: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    rate_limit_per_minute: int = 60


class GLMSettings(ProviderSettings):
    """GLM-4 provider settings"""
    base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    cost_per_1m_tokens: float = 0.25  # Input tokens
    cost_per_1m_output_tokens: float = 1.0  # Output tokens
    max_tokens: int = 8192
    model_name: str = "glm-4-flash"


class DeepSeekSettings(ProviderSettings):
    """DeepSeek provider settings"""
    base_url: str = "https://api.deepseek.com"
    cost_per_1m_tokens: float = 0.14  # Input tokens
    cost_per_1m_output_tokens: float = 0.28  # Output tokens
    max_tokens: int = 4096
    model_name: str = "deepseek-chat"


class ClaudeSettings(ProviderSettings):
    """Claude Haiku provider settings"""
    base_url: str = "https://api.anthropic.com"
    cost_per_1m_tokens: float = 0.25  # Input tokens
    cost_per_1m_output_tokens: float = 1.25  # Output tokens
    max_tokens: int = 8192
    model_name: str = "claude-3-5-haiku-20241022"


class OpenAISettings(ProviderSettings):
    """OpenAI provider settings"""
    base_url: str = "https://api.openai.com/v1"
    cost_per_1m_tokens: float = 0.15  # GPT-3.5-turbo input
    cost_per_1m_output_tokens: float = 0.6  # GPT-3.5-turbo output
    max_tokens: int = 4096
    model_name: str = "gpt-3.5-turbo"


class DeepInfraSettings(ProviderSettings):
    """DeepInfra provider settings"""
    base_url: str = "https://api.deepinfra.com/v1/openai"
    # Cost varies by model - will be configured per model
    specialty_models: Dict[str, Dict] = {
        "wizardlm-2-8x22b": {
            "cost_per_1m_input": 0.5,
            "cost_per_1m_output": 2.0,
            "max_tokens": 8192,
            "use_case": "complex_reasoning"
        },
        "nemotron-4-340b": {
            "cost_per_1m_input": 0.8,
            "cost_per_1m_output": 3.2,
            "max_tokens": 4096,
            "use_case": "creative_writing"
        },
        "hermes-3-405b": {
            "cost_per_1m_input": 1.0,
            "cost_per_1m_output": 4.0,
            "max_tokens": 8192,
            "use_case": "heavy_lifting"
        }
    }


class DatabaseSettings(BaseSettings):
    """Database configuration"""
    url: str = "postgresql://user:password@localhost/multi_provider_router"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30


class RedisSettings(BaseSettings):
    """Redis configuration"""
    url: str = "redis://localhost:6379/0"
    max_connections: int = 10


class BudgetSettings(BaseSettings):
    """Budget management settings"""
    daily_budget_usd: float = 100.0
    warning_threshold_percentage: float = 80.0
    hard_limit_percentage: float = 95.0
    cost_check_interval_seconds: int = 60


class RoutingSettings(BaseSettings):
    """Routing algorithm settings"""
    glm_primary_weight: float = 0.95  # 95% of requests to GLM-4
    cost_sensitivity_factor: float = 0.7  # How much cost influences routing
    quality_weight: float = 0.3  # Quality vs cost tradeoff
    fallback_enabled: bool = True
    health_check_interval_seconds: int = 30


class MonitoringSettings(BaseSettings):
    """Monitoring and analytics settings"""
    metrics_port: int = 9090
    log_level: str = "INFO"
    enable_tracing: bool = True
    performance_tracking_enabled: bool = True


class Settings(BaseSettings):
    """Main application settings"""

    # Environment
    environment: str = "development"
    debug: bool = False
    secret_key: str = "your-secret-key-here"

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Provider configurations
    glm: GLMSettings = GLMSettings(api_key="")
    deepseek: DeepSeekSettings = DeepSeekSettings(api_key="")
    claude: ClaudeSettings = ClaudeSettings(api_key="")
    openai: OpenAISettings = OpenAISettings(api_key="")
    deepinfra: DeepInfraSettings = DeepInfraSettings(api_key="")

    # System configurations
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    budget: BudgetSettings = BudgetSettings()
    routing: RoutingSettings = RoutingSettings()
    monitoring: MonitoringSettings = MonitoringSettings()

    # Queue settings
    max_queue_size: int = 1000
    queue_timeout_seconds: int = 300

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings"""
    return settings


# Development overrides
if os.getenv("ENVIRONMENT") == "development":
    settings.debug = True
    settings.monitoring.log_level = "DEBUG"
    settings.database.url = "sqlite:///./multi_provider_router_dev.db"