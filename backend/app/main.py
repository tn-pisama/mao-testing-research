from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.config import get_settings
from app.api.v1 import traces, detections, auth, analytics, health, import_jobs, webhooks, n8n, security, evals, metrics
from app.core.rate_limit import rate_limiter

settings = get_settings()


def validate_cors_origins(origins: list[str], allow_credentials: bool) -> list[str]:
    if allow_credentials:
        for origin in origins:
            if "*" in origin:
                raise ValueError("Cannot use wildcard origins with credentials enabled")
    return origins


@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.include_router(auth.router, prefix="/api/v1")
app.include_router(traces.router, prefix="/api/v1/tenants/{tenant_id}")
app.include_router(detections.router, prefix="/api/v1/tenants/{tenant_id}")
app.include_router(analytics.router, prefix="/api/v1/tenants/{tenant_id}")
app.include_router(import_jobs.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(n8n.router, prefix="/api/v1")
app.include_router(security.router, prefix="/api/v1")
app.include_router(evals.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")

FastAPIInstrumentor.instrument_app(app)


@app.get("/")
async def root():
    return {"name": settings.app_name, "version": "0.1.0"}


@app.get("/health")
async def root_health():
    return {"status": "healthy"}
