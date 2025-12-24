from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.config import get_settings
from app.api.v1 import traces, detections, auth, analytics, health
from app.core.rate_limit import rate_limiter

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await rate_limiter.close()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.mao-testing.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(traces.router, prefix="/api/v1/tenants/{tenant_id}")
app.include_router(detections.router, prefix="/api/v1/tenants/{tenant_id}")
app.include_router(analytics.router, prefix="/api/v1/tenants/{tenant_id}")
app.include_router(health.router, prefix="/api/v1")

FastAPIInstrumentor.instrument_app(app)


@app.get("/")
async def root():
    return {"name": settings.app_name, "version": "0.1.0"}
