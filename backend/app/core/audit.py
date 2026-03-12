import logging
import time
import re
from typing import Optional
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import AuthAudit, ApiAudit
from app.core.correlation import get_correlation_id

logger = logging.getLogger(__name__)

# Paths to skip (health checks, static, OPTIONS)
_SKIP_PATHS = re.compile(
    r"^/(health|api/v1/health|docs|openapi\.json|redoc|favicon\.ico)"
)

# Regex to extract tenant_id from path like /api/v1/tenants/{uuid}/...
_TENANT_RE = re.compile(
    r"/tenants/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


async def log_auth_event(
    db: AsyncSession,
    tenant_id: Optional[str],
    user_id: Optional[str],
    action: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    success: bool,
    error_code: Optional[str] = None,
):
    audit = AuthAudit(
        tenant_id=UUID(tenant_id) if tenant_id else None,
        user_id=UUID(user_id) if user_id else None,
        action=action,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
        success=success,
        error_code=error_code,
    )
    db.add(audit)
    await db.commit()


class APIAuditMiddleware(BaseHTTPMiddleware):
    """Logs POST/PUT/DELETE API requests to the api_audit table."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only audit mutations
        if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
            return await call_next(request)

        path = request.url.path
        if _SKIP_PATHS.match(path):
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        # Extract tenant_id from path
        tenant_id = None
        m = _TENANT_RE.search(path)
        if m:
            tenant_id = m.group(1)

        # Extract user_id from request state (set by auth dependency)
        user_id = None
        if hasattr(request.state, "auth_context"):
            auth_ctx = request.state.auth_context
            user_id = getattr(auth_ctx, "user_id", None)

        correlation_id = get_correlation_id()
        ip_address = request.client.host if request.client else None

        try:
            from app.storage.database import async_session_maker

            async with async_session_maker() as db:
                audit = ApiAudit(
                    tenant_id=UUID(tenant_id) if tenant_id else None,
                    user_id=UUID(user_id) if user_id else None,
                    method=request.method,
                    path=path[:500],
                    status_code=response.status_code,
                    correlation_id=correlation_id[:64] if correlation_id else None,
                    ip_address=ip_address,
                    duration_ms=round(duration_ms, 2),
                )
                db.add(audit)
                await db.commit()
        except Exception:
            logger.warning("Failed to write API audit log", exc_info=True)

        return response
