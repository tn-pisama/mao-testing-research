"""
Background scheduler for periodic n8n sync.

Uses APScheduler with Redis-based distributed locking to ensure only one
instance runs the sync job at a time across multiple Fly.io machines.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from redis import asyncio as aioredis
from sqlalchemy import select

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


async def get_sync_lock(redis: aioredis.Redis, lock_key: str, ttl: int = 300) -> bool:
    """
    Acquire a distributed lock using Redis SET NX.

    Args:
        redis: Redis client
        lock_key: Key for the lock
        ttl: Lock TTL in seconds (default 5 minutes)

    Returns:
        True if lock acquired, False otherwise
    """
    result = await redis.set(lock_key, "1", nx=True, ex=ttl)
    return result is not None


async def release_sync_lock(redis: aioredis.Redis, lock_key: str):
    """Release the distributed lock."""
    await redis.delete(lock_key)


async def sync_tenant_executions(
    tenant_id: str,
    n8n_host: str,
    n8n_api_key: str,
    limit: int = 20
) -> int:
    """
    Sync n8n executions for a specific tenant.

    Args:
        tenant_id: Tenant UUID
        n8n_host: n8n instance URL
        n8n_api_key: n8n API key
        limit: Max executions to fetch

    Returns:
        Number of new executions synced
    """
    from app.integrations.n8n_client import N8nApiClient, N8nApiError
    from app.storage.database import async_session_maker, set_tenant_context
    from app.storage.models import Trace, State

    synced_count = 0

    try:
        async with N8nApiClient(n8n_host, n8n_api_key) as client:
            executions = await client.get_executions(limit=limit)

            async with async_session_maker() as db:
                await set_tenant_context(db, tenant_id)

                for execution in executions:
                    exec_id = execution.get("id", "")

                    # Check if already imported
                    existing = await db.execute(
                        select(Trace).where(
                            Trace.tenant_id == UUID(tenant_id),
                            Trace.session_id == str(exec_id),
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    # Parse and create trace
                    started_at = execution.get("startedAt")
                    finished_at = execution.get("stoppedAt")
                    status = execution.get("status", "unknown")

                    trace = Trace(
                        tenant_id=UUID(tenant_id),
                        session_id=str(exec_id),
                        framework="n8n",
                        status="completed" if status == "success" else "error",
                        created_at=datetime.fromisoformat(started_at.replace("Z", "+00:00")) if started_at else datetime.utcnow(),
                        completed_at=datetime.fromisoformat(finished_at.replace("Z", "+00:00")) if finished_at else None,
                    )
                    db.add(trace)
                    await db.flush()

                    # Parse states from run data
                    exec_data = execution.get("data", {})
                    result_data = exec_data.get("resultData", {})
                    run_data = result_data.get("runData", {})

                    seq = 0
                    for node_name, node_runs in run_data.items():
                        for run in node_runs:
                            state = State(
                                trace_id=trace.id,
                                tenant_id=UUID(tenant_id),
                                sequence_num=seq,
                                agent_id=node_name,
                                state_delta={
                                    "node": node_name,
                                    "startTime": run.get("startTime"),
                                    "executionTime": run.get("executionTime"),
                                },
                                state_hash=f"{exec_id}_{node_name}_{seq}",
                                latency_ms=run.get("executionTime", 0),
                            )
                            db.add(state)
                            seq += 1

                    synced_count += 1

                await db.commit()
    except Exception as e:
        logger.warning(f"Failed to sync executions for tenant {tenant_id}: {e}")

    return synced_count


async def sync_all_tenants():
    """
    Sync n8n executions for all active tenants.

    This job runs periodically and syncs executions for each tenant
    that has n8n integration enabled.
    """
    from app.storage.database import async_session_maker
    from app.storage.models import Tenant

    settings = get_settings()
    lock_key = "mao:n8n:sync_lock"

    # Check if n8n is configured globally
    n8n_host = os.getenv("N8N_HOST")
    n8n_api_key = os.getenv("N8N_API_KEY")

    if not n8n_host or not n8n_api_key:
        logger.debug("n8n not configured, skipping auto-sync")
        return

    redis = None
    try:
        # Connect to Redis and acquire lock
        redis = await aioredis.from_url(settings.redis_url)

        if not await get_sync_lock(redis, lock_key):
            logger.debug("Another instance is running sync, skipping")
            return

        logger.info("Starting n8n auto-sync for all tenants")

        # Get all active tenants
        async with async_session_maker() as db:
            result = await db.execute(select(Tenant))
            tenants = result.scalars().all()

        total_synced = 0
        total_errors = 0

        for tenant in tenants:
            try:
                # Check if tenant has sync disabled in settings
                tenant_settings = tenant.settings or {}
                if tenant_settings.get("n8n_auto_sync_enabled") is False:
                    continue

                # Sync for this tenant
                synced = await sync_tenant_executions(
                    tenant_id=str(tenant.id),
                    n8n_host=n8n_host,
                    n8n_api_key=n8n_api_key,
                    limit=tenant_settings.get("n8n_sync_limit", 20)
                )
                total_synced += synced

            except Exception as e:
                logger.warning(f"Failed to sync tenant {tenant.id}: {e}")
                total_errors += 1

        logger.info(f"n8n auto-sync completed: {total_synced} executions synced, {total_errors} tenant errors")

    except Exception as e:
        logger.error(f"n8n auto-sync failed: {e}")
    finally:
        if redis:
            await release_sync_lock(redis, lock_key)
            await redis.close()


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    global scheduler

    # Get sync interval from environment (default: 5 minutes)
    sync_interval_minutes = int(os.getenv("N8N_SYNC_INTERVAL_MINUTES", "5"))

    scheduler = AsyncIOScheduler()

    # Add the sync job
    scheduler.add_job(
        sync_all_tenants,
        trigger=IntervalTrigger(minutes=sync_interval_minutes),
        id="n8n_auto_sync",
        name="n8n Auto-Sync",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping runs
    )

    logger.info(f"Scheduler configured: n8n sync every {sync_interval_minutes} minutes")

    return scheduler


async def start_scheduler():
    """Start the background scheduler."""
    global scheduler

    # Only start if n8n is configured
    n8n_host = os.getenv("N8N_HOST")
    n8n_api_key = os.getenv("N8N_API_KEY")

    if not n8n_host or not n8n_api_key:
        logger.info("n8n not configured, scheduler not started")
        return

    if scheduler is None:
        scheduler = create_scheduler()

    if not scheduler.running:
        scheduler.start()
        logger.info("Background scheduler started")


async def stop_scheduler():
    """Stop the background scheduler gracefully."""
    global scheduler

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Background scheduler stopped")
