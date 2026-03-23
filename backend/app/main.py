from contextlib import asynccontextmanager
import logging
import os
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

try:
    import sentry_sdk
    if os.environ.get("SENTRY_DSN"):
        sentry_sdk.init(
            dsn=os.environ["SENTRY_DSN"],
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            environment=os.environ.get("ENVIRONMENT", "production"),
        )
except ImportError:
    pass

from app.core.logging_config import setup_logging
from app.core.correlation import CorrelationIdMiddleware, get_correlation_id
from app.core.audit import APIAuditMiddleware

setup_logging()
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

from app.config import get_settings
from app.core.rate_limit import rate_limiter, check_tenant_rate_limit, RateLimitResult
from app.core.dependencies import AuthContext, get_current_user_or_tenant
from app.storage.database import get_db

# ICP (Startup) routers - always loaded
from app.api.v1 import (
    traces,
    detections,
    auth,
    analytics,
    agents,
    health,
    import_jobs,
    webhooks,
    n8n,
    openclaw,
    dify,
    langgraph,
    security,
    metrics,
    claude_code,
    conversations,
    benchmarks,
    feedback,
    healing,
    settings as settings_router,
    billing,
    workflow_groups,
    diagnostics,
    marketplace,
    onboarding,
    admin,
    dashboard,
)

settings = get_settings()

# Quality routers - always loaded (no feature flag)
quality_routers_loaded = False
try:
    from app.api.enterprise import quality, quality_healing
    quality_routers_loaded = True
except ImportError as e:
    import logging
    logging.warning(f"Quality routers not available: {e}")

# Enterprise routers - conditionally loaded based on feature flags
enterprise_routers_loaded = False
if settings.features.enterprise_enabled:
    try:
        from app.api.enterprise import evals, chaos, testing, replay, regression, diagnose
        enterprise_routers_loaded = True
    except ImportError as e:
        import logging
        logging.warning(f"Enterprise routers not available: {e}")


def validate_cors_origins(origins: list[str], allow_credentials: bool) -> list[str]:
    if allow_credentials:
        for origin in origins:
            if "*" in origin:
                raise ValueError("Cannot use wildcard origins with credentials enabled")
    return origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio as _asyncio

    # Validate configuration early — fail fast on bad config
    get_settings()

    # Start background scheduler for n8n sync
    from app.workers.scheduler import start_scheduler, stop_scheduler
    await start_scheduler()

    # AWS Marketplace: RegisterUsage on startup + periodic metering
    _metering_task = None
    if settings.aws_marketplace_enabled:
        try:
            from app.billing.marketplace import get_marketplace_service
            _mp_service = get_marketplace_service()

            # RegisterUsage — required on each container start for SaaS contracts
            try:
                await _mp_service.register_usage()
                _logger.info("AWS Marketplace RegisterUsage succeeded")
            except Exception as e:
                _logger.warning("AWS Marketplace RegisterUsage failed (non-fatal): %s", e)

            # Periodic usage reporting
            async def _metering_loop():
                interval = _mp_service.config.metering_interval_minutes * 60
                while True:
                    await _asyncio.sleep(interval)
                    try:
                        stats = await _mp_service.report_usage()
                        _logger.info("Marketplace metering report: %s", stats)
                    except Exception as e:
                        _logger.error("Marketplace metering report failed: %s", e)

            _metering_task = _asyncio.create_task(_metering_loop())
            _logger.info("AWS Marketplace metering scheduler started (every %d min)",
                         _mp_service.config.metering_interval_minutes)
        except Exception as e:
            _logger.warning("Failed to initialize Marketplace metering: %s", e)

    # Embedding model is lazy-loaded on first use to speed up startup
    from app.api.v1.health import mark_startup_complete
    mark_startup_complete()

    yield

    # Cleanup
    if _metering_task and not _metering_task.done():
        _metering_task.cancel()
        try:
            await _metering_task
        except _asyncio.CancelledError:
            pass
    await stop_scheduler()
    await rate_limiter.close()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

cors_origins = validate_cors_origins(
    [o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Accept-Language", "Content-Language", "X-Requested-With", "X-MAO-API-Key", "X-MAO-Signature", "X-MAO-Timestamp", "X-MAO-Nonce", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    max_age=3600,
)

app.add_middleware(APIAuditMiddleware)
app.add_middleware(CorrelationIdMiddleware)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path in ["/health", "/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready", "/api/v1/health/startup", "/"]:
        return await call_next(request)
    
    client_ip = request.client.host if request.client else "unknown"
    key = f"rate_limit:ip:{client_ip}"
    
    allowed = await rate_limiter.check_rate_limit(key, limit=1000, window=60)
    if not allowed:
        origin = request.headers.get("origin", "")
        headers = {"Retry-After": "60"}
        if origin in cors_origins:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests"},
            headers=headers
        )
    
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def add_rate_limit_headers(request: Request, call_next):
    """Add X-RateLimit-* headers to responses for tenant-scoped requests."""
    response = await call_next(request)
    if hasattr(request.state, "rate_limit_result"):
        rl: RateLimitResult = request.state.rate_limit_result
        response.headers["X-RateLimit-Limit"] = str(rl.limit)
        response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
        response.headers["X-RateLimit-Reset"] = str(rl.reset_at)
    return response


async def tenant_rate_limit_dependency(
    request: Request,
    auth: AuthContext = Depends(get_current_user_or_tenant),
    db=Depends(get_db),
) -> RateLimitResult:
    """FastAPI dependency: enforce per-tenant rate limits based on subscription tier."""
    result = await check_tenant_rate_limit(auth.tenant_id, db)
    request.state.rate_limit_result = result
    return result


_logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    _logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in cors_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    correlation_id = get_correlation_id()
    if correlation_id:
        headers["X-Request-ID"] = correlation_id
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": correlation_id},
        headers=headers,
    )


# Per-tenant rate limit dependency for tenant-scoped routers
_tenant_rate_deps = [Depends(tenant_rate_limit_dependency)]

# ICP (Startup) routers - always included
app.include_router(auth.router, prefix="/api/v1")
app.include_router(traces.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)
app.include_router(agents.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)
app.include_router(detections.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)
app.include_router(analytics.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)
app.include_router(dashboard.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)
app.include_router(import_jobs.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(n8n.router, prefix="/api/v1")
app.include_router(openclaw.router, prefix="/api/v1")  # OpenClaw agent monitoring
app.include_router(dify.router, prefix="/api/v1")  # Dify workflow monitoring
app.include_router(langgraph.router, prefix="/api/v1")  # LangGraph graph monitoring
app.include_router(security.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(benchmarks.router, prefix="/api/v1")  # Benchmark results
app.include_router(claude_code.router, prefix="/api/v1")  # Claude Code trace ingestion
app.include_router(conversations.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)  # Conversation traces
app.include_router(feedback.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)  # Detection feedback
app.include_router(healing.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)  # Self-healing operations
app.include_router(settings_router.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)  # Tenant settings
app.include_router(billing.router, prefix="/api/v1")  # Stripe billing
app.include_router(workflow_groups.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)  # Workflow grouping
app.include_router(diagnostics.router, prefix="/api/v1")  # Detector diagnostics
app.include_router(marketplace.router, prefix="/api/v1")  # AWS Marketplace integration
app.include_router(onboarding.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)  # Onboarding wizard
app.include_router(admin.router, prefix="/api/v1/tenants/{tenant_id}", dependencies=_tenant_rate_deps)  # Admin audit log

# AWS Marketplace usage tracking middleware (only when enabled)
if settings.aws_marketplace_enabled:
    try:
        from app.billing.marketplace import get_marketplace_service
        from app.billing.marketplace_middleware import UsageTrackingMiddleware

        _marketplace_service = get_marketplace_service()
        app.add_middleware(UsageTrackingMiddleware, metering_service=_marketplace_service)
        logging.getLogger(__name__).info("AWS Marketplace usage tracking middleware enabled")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to initialize Marketplace middleware: {e}")

# Enterprise routers - conditionally included based on feature flags
if enterprise_routers_loaded:
    if settings.features.is_enabled("advanced_evals"):
        app.include_router(evals.router, prefix="/api/v1", tags=["enterprise"])
    if settings.features.is_enabled("chaos_engineering"):
        app.include_router(chaos.router, prefix="/api/v1", tags=["enterprise"])
    if settings.features.is_enabled("regression_testing"):
        app.include_router(testing.router, prefix="/api/v1/tenants/{tenant_id}", tags=["enterprise"])
        app.include_router(regression.router, prefix="/api/v1/tenants/{tenant_id}", tags=["enterprise"])
    if settings.features.is_enabled("trace_replay"):
        app.include_router(replay.router, prefix="/api/v1/tenants/{tenant_id}", tags=["enterprise"])
    if settings.features.is_enabled("ml_detection"):
        app.include_router(diagnose.router, prefix="/api/v1", tags=["enterprise"])  # Agent Forensics
    pass  # enterprise features registered below

# Quality assessment — always enabled (no feature flag)
if quality_routers_loaded:
    app.include_router(quality.router, prefix="/api/v1", tags=["quality"])
    app.include_router(quality_healing.router, prefix="/api/v1", tags=["quality"])

if _OTEL_AVAILABLE:
    FastAPIInstrumentor.instrument_app(app)


@app.get("/")
async def root():
    return {"name": settings.app_name, "version": "0.1.0"}


@app.get("/health")
async def root_health():
    return {"status": "healthy"}
