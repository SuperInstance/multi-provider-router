"""
Main application entry point for LucidDreamer Multi-Provider Router
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .models import (
    GenerationRequest,
    GenerationResponse,
    APIResponse,
    ProviderType,
    PriorityLevel,
    SpecialtyModel
)
from .routing.router import router
from .utils.logger import get_logger, setup_logging
from .utils.metrics import metrics
from .config import get_settings

settings = get_settings()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting LucidDreamer Router")
    setup_logging(settings.monitoring.log_level)

    # Initialize router
    await router.initialize()

    # Start health checks
    from .utils.health_checker import health_checker
    asyncio.create_task(health_checker.start_health_checks())

    # Initialize cache
    from .utils.cache import cache
    await cache.connect()

    # Initialize rate limiter
    from .utils.rate_limiter import rate_limiter
    await rate_limiter.connect()

    logger.info("LucidDreamer Router started successfully")

    yield

    # Shutdown
    logger.info("Shutting down LucidDreamer Router")
    await router.shutdown()
    await health_checker.stop_health_checks()
    logger.info("LucidDreamer Router shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="LucidDreamer Multi-Provider Router",
    description="Cost-optimized AI model routing across multiple providers",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "LucidDreamer Multi-Provider Router",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        health_status = await router.health_check()
        return APIResponse(
            success=True,
            data=health_status
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/generate")
async def generate_text(request: GenerationRequest):
    """Generate text completion"""
    try:
        # Add request ID if not present
        if not hasattr(request, 'request_id'):
            request.request_id = str(uuid.uuid4())

        response = await router.generate(request)
        return APIResponse(
            success=True,
            data=response,
            request_id=request.request_id
        )
    except Exception as e:
        logger.error("Generation failed", request_id=getattr(request, 'request_id', 'unknown'), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/stream")
async def generate_text_stream(request: GenerationRequest):
    """Generate text completion with streaming"""
    try:
        # Add request ID if not present
        if not hasattr(request, 'request_id'):
            request.request_id = str(uuid.uuid4())

        async def stream_response():
            try:
                async for chunk in router.generate_stream(request):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error("Streaming failed", request_id=request.request_id, error=str(e))
                yield f"data: ERROR: {str(e)}\n\n"

        return StreamingResponse(
            stream_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request.request_id
            }
        )
    except Exception as e:
        logger.error("Stream generation failed", request_id=getattr(request, 'request_id', 'unknown'), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/providers")
async def get_providers():
    """Get information about available providers"""
    try:
        provider_info = router.get_provider_info()
        return APIResponse(
            success=True,
            data=provider_info
        )
    except Exception as e:
        logger.error("Failed to get provider info", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/costs")
async def get_cost_analytics(hours: int = 24):
    """Get cost analytics"""
    try:
        if hours > 168:  # Limit to 1 week
            raise HTTPException(status_code=400, detail="Hours parameter cannot exceed 168")

        cost_analysis = await router.get_cost_analysis(hours)
        return APIResponse(
            success=True,
            data=cost_analysis
        )
    except Exception as e:
        logger.error("Failed to get cost analytics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/metrics")
async def get_metrics():
    """Get Prometheus metrics"""
    try:
        metrics_data = metrics.get_prometheus_metrics()
        return StreamingResponse(
            iter([metrics_data]),
            media_type="text/plain"
        )
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/routing/stats")
async def get_routing_statistics():
    """Get routing statistics"""
    try:
        routing_stats = router.decision_engine.get_routing_statistics()
        return APIResponse(
            success=True,
            data=routing_stats
        )
    except Exception as e:
        logger.error("Failed to get routing stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/reset-failures")
async def reset_failure_tracking(provider: Optional[str] = None):
    """Reset failure tracking (admin endpoint)"""
    try:
        from .routing.fallback_manager import FailureManager
        provider_type = ProviderType(provider) if provider else None
        router.fallback_manager.reset_failure_tracking(provider_type)

        return APIResponse(
            success=True,
            data={"message": f"Failure tracking reset for {provider or 'all providers'}"}
        )
    except Exception as e:
        logger.error("Failed to reset failures", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/load-balancer/stats")
async def get_load_balancer_statistics():
    """Get load balancer statistics"""
    try:
        load_stats = router.load_balancer.get_load_statistics()
        return APIResponse(
            success=True,
            data=load_stats
        )
    except Exception as e:
        logger.error("Failed to get load balancer stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/load-balancer/rebalance")
async def rebalance_load_balancer(background_tasks: BackgroundTasks):
    """Trigger load balancer rebalancing"""
    try:
        background_tasks.add_task(router.load_balancer.rebalance_weights)
        return APIResponse(
            success=True,
            data={"message": "Load balancer rebalancing started"}
        )
    except Exception as e:
        logger.error("Failed to rebalance load balancer", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/fallback/stats")
async def get_fallback_statistics():
    """Get fallback manager statistics"""
    try:
        fallback_stats = router.fallback_manager.get_failure_statistics()
        return APIResponse(
            success=True,
            data=fallback_stats
        )
    except Exception as e:
        logger.error("Failed to get fallback stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.monitoring.log_level.lower()
    )