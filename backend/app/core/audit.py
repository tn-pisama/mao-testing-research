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
    event_type: str,
    client_ip: Optional[str],
    user_agent: Optional[str],
    success: bool,
    failure_reason: Optional[str],
):
    """Write an auth event to the database. Fails silently."""
    try:
        audit = AuthAudit(
            tenant_id=UUID(tenant_id) if tenant_id else None,
            user_id=UUID(user_id) if user_id else None,
            event_type=event_type,
            client_ip=client_ip,
            user_agent=user_agent[:500] if user_agent else None,
            success=success,
            failure_reason=failure_reason,
        )
        db.add(audit)
        await db.commit()
    except Exception:
        logger.warning("Failed to write auth audit log", exc_info=False)
        try:
            await db.rollback()
        except Exception:
            pass


class APIAuditMiddleware(BaseHTTPMiddleware):
    """Logs POST/PUT/DELETE API requests to the api_audit table.

    IMPORTANT: This middleware must NEVER crash the response pipeline.
    All audit operations are fire-and-forget. If audit fails, the
    request still succeeds normally.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only audit mutations — skip GETs entirely
        if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
            return await call_next(request)

        path = request.url.path
        if _SKIP_PATHS.match(path):
            return await call_next(request)

        start = time.monotonic()

        # ALWAYS call the next handler and return its response.
        # Audit is secondary — if it fails, the response still goes through.
        try:
            response = await call_next(request)
        except Exception:
            # If the handler itself crashes, re-raise — that's not our problem
            raise

        duration_ms = (time.monotonic() - start) * 1000

        # Fire-and-forget audit write — wrapped in try/except so it NEVER
        # affects the response that's already been generated
        try:
            tenant_id = None
            m = _TENANT_RE.search(path)
            if m:
                tenant_id = m.group(1)

            user_id = None
            if hasattr(request.state, "auth_context"):
                auth_ctx = request.state.auth_context
                user_id = getattr(auth_ctx, "user_id", None)

            correlation_id = get_correlation_id()
            ip_address = request.client.host if request.client else None

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
            # Audit failed — log a warning, but NEVER affect the response
            logger.warning(
                "Failed to write API audit log for %s %s",
                request.method, path,
                exc_info=False,
            )

        return response
