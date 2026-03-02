"""Shared webhook handler utilities for all provider integrations.

Extracts duplicated patterns from n8n.py, openclaw.py, and dify.py into
reusable functions:
- API key verification and tenant lookup
- Nonce replay protection
- Webhook signature verification (when entity has a secret)
- Trace + State record creation
- SSE event streaming
"""

import json
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.core.webhook_security import verify_webhook_signature
from app.core.redis_pubsub import subscribe_events
from app.storage.database import set_tenant_context
from app.storage.models import Tenant, Trace, State, WebhookNonce

logger = logging.getLogger(__name__)


async def verify_api_key_and_get_tenant(
    api_key: str,
    db: AsyncSession,
) -> Tenant:
    """Validate an MAO API key and return the associated tenant.

    Raises HTTPException 401 on invalid key format, unknown key, or revoked key.
    Also sets the tenant context on the database session.
    """
    from app.core.auth import verify_api_key
    from app.storage.models import ApiKey

    if not api_key.startswith("mao_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    key_prefix = api_key[:12]

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == key_prefix,
            ApiKey.revoked_at.is_(None),
        )
    )
    api_key_record = result.scalar_one_or_none()

    tenant = None
    if api_key_record and verify_api_key(api_key, api_key_record.key_hash):
        result = await db.execute(
            select(Tenant).where(Tenant.id == api_key_record.tenant_id)
        )
        tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")

    await set_tenant_context(db, str(tenant.id))
    return tenant


async def verify_nonce(nonce: str, timestamp: int, db: AsyncSession) -> bool:
    """Check nonce uniqueness for replay protection.

    Raises HTTPException 401 if the nonce has already been seen.
    """
    result = await db.execute(
        select(WebhookNonce).where(WebhookNonce.nonce == nonce)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=401, detail="Replay attack detected")

    await db.execute(
        insert(WebhookNonce).values(nonce=nonce, timestamp=timestamp)
    )
    return True


async def verify_webhook_if_configured(
    request_body: bytes,
    webhook_secret: Optional[str],
    signature: Optional[str],
    timestamp: Optional[str],
    nonce: Optional[str],
    db: AsyncSession,
) -> None:
    """Verify webhook signature and nonce if the entity has a secret configured.

    Args:
        request_body: Raw request body bytes (from ``await request.body()``)
        webhook_secret: The entity's stored webhook secret (None = skip verification)
        signature: X-MAO-Signature header value
        timestamp: X-MAO-Timestamp header value
        nonce: X-MAO-Nonce header value
        db: Database session (for nonce storage)
    """
    if not webhook_secret:
        return

    if not signature or not timestamp:
        raise HTTPException(
            status_code=401,
            detail="Webhook signature required for registered entities",
        )

    verify_webhook_signature(request_body, signature, webhook_secret, timestamp)

    if nonce:
        await verify_nonce(nonce, int(timestamp), db)


async def create_trace_and_states(
    tenant: Tenant,
    session_id: str,
    framework: str,
    status: str,
    created_at,
    completed_at,
    states: list,
    db: AsyncSession,
) -> Trace:
    """Create a Trace and its associated State records.

    Args:
        tenant: The tenant owning this trace.
        session_id: Provider-specific execution/session/run ID.
        framework: Provider name ("n8n", "openclaw", "dify").
        status: Normalized status ("completed" or "error").
        created_at: Trace start time.
        completed_at: Trace end time (or None).
        states: List of parsed state dataclass instances (must have
                sequence_num, agent_id, state_delta, state_hash,
                token_count, latency_ms attributes).
        db: Database session.

    Returns:
        The created Trace (already flushed, has an ``id``).
    """
    trace = Trace(
        tenant_id=tenant.id,
        session_id=session_id,
        framework=framework,
        status=status,
        created_at=created_at,
        completed_at=completed_at,
    )
    db.add(trace)
    await db.flush()

    for state in states:
        db_state = State(
            trace_id=trace.id,
            tenant_id=tenant.id,
            sequence_num=state.sequence_num,
            agent_id=state.agent_id,
            state_delta=state.state_delta,
            state_hash=state.state_hash,
            token_count=state.token_count,
            latency_ms=state.latency_ms,
        )
        db.add(db_state)

    return trace


async def capture_golden_candidates(
    tenant_id: str,
    trace_id: str,
    states: list,
    source_id: str,
    framework: str,
):
    """Background task: create golden dataset candidate entries from trace states.

    Runs for any integration when the ``golden_auto_capture`` feature flag is
    enabled.  Stores each state as an unverified golden entry for later human
    review.

    Args:
        tenant_id: Tenant UUID string.
        trace_id: Trace UUID string.
        states: List of parsed state dataclass instances.
        source_id: Provider-specific ID (workflow_id, app_id, session_id, etc.).
        framework: Provider name ("n8n", "dify", "openclaw").
    """
    try:
        from app.storage.database import async_session_maker
        from app.storage.models import GoldenDatasetEntryModel
        from app.storage.golden_dataset_repo import GoldenDatasetRepository
        import uuid as uuid_mod

        async with async_session_maker() as session:
            repo = GoldenDatasetRepository(session)

            for state in states:
                state_data = state if isinstance(state, dict) else {
                    "agent_id": getattr(state, "agent_id", "unknown"),
                    "content": getattr(state, "content", ""),
                    "role": getattr(state, "role", "assistant"),
                }

                entry = GoldenDatasetEntryModel(
                    id=uuid_mod.uuid4(),
                    tenant_id=UUID(tenant_id),
                    entry_key=f"{framework}_auto_{trace_id[:8]}_{uuid_mod.uuid4().hex[:6]}",
                    detection_type="unknown",
                    input_data=state_data,
                    expected_detected=False,
                    source=f"{framework}_ingestion",
                    tags=[framework, "auto_captured", "unverified"],
                    difficulty="unknown",
                    split="unverified",
                    source_trace_id=trace_id,
                    source_workflow_id=source_id,
                    human_verified=False,
                )
                session.add(entry)

            await session.commit()
            logger.info(
                "Auto-captured %d golden candidates from %s trace %s",
                len(states), framework, trace_id,
            )
    except Exception as exc:
        logger.warning("Failed to auto-capture golden candidates: %s", exc)


def create_sse_response(tenant_id: str, provider_name: str = "provider") -> StreamingResponse:
    """Create a Server-Sent Events streaming response for real-time updates.

    Subscribes to the tenant's Redis pub/sub channel and streams events.
    """
    async def event_generator():
        try:
            async for event in subscribe_events(f"execution:{tenant_id}"):
                yield event
        except Exception as e:
            logger.error(f"Error in {provider_name} SSE stream: {e}")
            error_data = json.dumps(
                {"type": "error", "message": "Stream interrupted"}
            )
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
