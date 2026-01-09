"""
Logging configuration for the routing system
"""

import structlog
import logging
import sys
from typing import Any, Dict
from datetime import datetime

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration"""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger"""
    return structlog.get_logger(name)


def log_request_start(request_id: str, provider: str, model: str, **kwargs) -> None:
    """Log the start of a request"""
    logger = get_logger("request")
    logger.info(
        "Request started",
        request_id=request_id,
        provider=provider,
        model=model,
        **kwargs
    )


def log_request_complete(
    request_id: str,
    provider: str,
    model: str,
    duration_ms: int,
    tokens: int,
    cost: float,
    **kwargs
) -> None:
    """Log the completion of a request"""
    logger = get_logger("request")
    logger.info(
        "Request completed",
        request_id=request_id,
        provider=provider,
        model=model,
        duration_ms=duration_ms,
        tokens=tokens,
        cost_usd=cost,
        **kwargs
    )


def log_request_error(request_id: str, provider: str, error: str, **kwargs) -> None:
    """Log a request error"""
    logger = get_logger("request")
    logger.error(
        "Request failed",
        request_id=request_id,
        provider=provider,
        error=error,
        **kwargs
    )


def log_routing_decision(
    request_id: str,
    selected_provider: str,
    reasoning: str,
    cost_estimate: float,
    **kwargs
) -> None:
    """Log a routing decision"""
    logger = get_logger("routing")
    logger.info(
        "Routing decision made",
        request_id=request_id,
        selected_provider=selected_provider,
        reasoning=reasoning,
        cost_estimate_usd=cost_estimate,
        **kwargs
    )


def log_budget_alert(
    spent_usd: float,
    budget_usd: float,
    percentage: float,
    alert_type: str,
    **kwargs
) -> None:
    """Log a budget alert"""
    logger = get_logger("budget")
    logger.warning(
        "Budget alert",
        spent_usd=spent_usd,
        budget_usd=budget_usd,
        percentage_used=percentage,
        alert_type=alert_type,
        **kwargs
    )


def log_provider_health_check(
    provider: str,
    is_healthy: bool,
    response_time_ms: int,
    **kwargs
) -> None:
    """Log a provider health check"""
    logger = get_logger("health")
    logger.info(
        "Provider health check",
        provider=provider,
        is_healthy=is_healthy,
        response_time_ms=response_time_ms,
        **kwargs
    )


def log_system_event(event_type: str, message: str, **kwargs) -> None:
    """Log a general system event"""
    logger = get_logger("system")
    logger.info(
        message,
        event_type=event_type,
        timestamp=datetime.utcnow().isoformat(),
        **kwargs
    )