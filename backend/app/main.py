from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.config import get_settings
from app.core.rate_limit import rate_limiter

# ICP (Startup) routers - always loaded
from app.api.v1 import (
    traces,
    detections,
    auth,
    analytics,
    health,
    import_jobs,
    webhooks,
    n8n,
    security,
    metrics,
    claude_code,
    conversations,
    benchmarks,
    feedback,
)

settings = get_settings()

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
    # Embedding model is lazy-loaded on first use to speed up startup
    yield
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
    allow_headers=["Authorization", "Content-Type", "Accept", "Accept-Language", "Content-Language", "X-Requested-With", "X-MAO-API-Key", "X-MAO-Signature", "X-MAO-Timestamp", "X-MAO-Nonce"],
    max_age=3600,
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path in ["/health", "/api/v1/health", "/"]:
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
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ICP (Startup) routers - always included
app.include_router(auth.router, prefix="/api/v1")
app.include_router(traces.router, prefix="/api/v1/tenants/{tenant_id}")
app.include_router(detections.router, prefix="/api/v1/tenants/{tenant_id}")
app.include_router(analytics.router, prefix="/api/v1/tenants/{tenant_id}")
app.include_router(import_jobs.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(n8n.router, prefix="/api/v1")
app.include_router(security.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(benchmarks.router, prefix="/api/v1")  # Benchmark results
app.include_router(claude_code.router, prefix="/api/v1")  # Claude Code trace ingestion
app.include_router(conversations.router, prefix="/api/v1/tenants/{tenant_id}")  # Conversation traces
app.include_router(feedback.router, prefix="/api/v1/tenants/{tenant_id}")  # Detection feedback

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

FastAPIInstrumentor.instrument_app(app)


@app.get("/")
async def root():
    return {"name": settings.app_name, "version": "0.1.0"}


@app.get("/health")
async def root_health():
    return {"status": "healthy"}
