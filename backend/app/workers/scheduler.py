"""
Background scheduler for periodic n8n sync and healing re-checks.

Uses APScheduler with Redis-based distributed locking to ensure only one
instance runs the sync job at a time across multiple Fly.io machines.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from redis import asyncio as aioredis
from sqlalchemy import select, and_

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


async def recheck_stale_healings():
    """
    Re-check healing records that were applied but never verified.

    Finds HealingRecords where deployment_stage is 'staged' or 'promoted',
    validation_status is NULL, and created_at > 1 hour ago. Runs Level 1
    verification (Level 2 if n8n connection is available).

    Uses Redis distributed lock to prevent overlapping runs.
    """
    from app.storage.database import async_session_maker
    from app.storage.models import HealingRecord
    from app.healing.verification import VerificationOrchestrator
    from app.integrations.n8n_client import N8nApiClient

    settings = get_settings()
    lock_key = "mao:healing:recheck_lock"
    recheck_max_age_hours = int(os.getenv("HEALING_RECHECK_MAX_AGE_HOURS", "24"))

    redis = None
    try:
        redis = await aioredis.from_url(settings.redis_url)

        if not await get_sync_lock(redis, lock_key, ttl=600):
            logger.debug("Another instance is running healing recheck, skipping")
            return

        logger.info("Starting stale healing recheck")

        cutoff_recent = datetime.now(timezone.utc) - timedelta(hours=1)
        cutoff_old = datetime.now(timezone.utc) - timedelta(hours=recheck_max_age_hours)

        async with async_session_maker() as db:
            result = await db.execute(
                select(HealingRecord).where(
                    and_(
                        HealingRecord.deployment_stage.in_(["staged", "promoted"]),
                        HealingRecord.validation_status.is_(None),
                        HealingRecord.created_at < cutoff_recent,
                        HealingRecord.created_at > cutoff_old,
                    )
                )
            )
            stale_records = result.scalars().all()

        if not stale_records:
            logger.debug("No stale healings to recheck")
            return

        logger.info(f"Found {len(stale_records)} stale healing records to recheck")

        orchestrator = VerificationOrchestrator()
        verified = 0
        errors = 0

        for record in stale_records:
            try:
                applied_fixes = record.applied_fixes or {}
                original_state = record.original_state or {}
                detection_type = applied_fixes.get("detection_type", "unknown")
                original_confidence = applied_fixes.get("original_confidence", 0.5)

                # Try Level 2 if n8n connection is available
                verification = None
                if record.workflow_id and record.n8n_connection_id:
                    n8n_host = os.getenv("N8N_HOST")
                    n8n_api_key = os.getenv("N8N_API_KEY")
                    if n8n_host and n8n_api_key:
                        try:
                            async with N8nApiClient(n8n_host, n8n_api_key) as client:
                                verification = await asyncio.wait_for(
                                    orchestrator.verify_level2(
                                        detection_type=detection_type,
                                        original_confidence=original_confidence,
                                        original_state=original_state,
                                        applied_fixes=applied_fixes,
                                        n8n_client=client,
                                        workflow_id=record.workflow_id,
                                    ),
                                    timeout=75,
                                )
                        except (asyncio.TimeoutError, Exception) as e:
                            logger.warning(
                                f"Level 2 recheck failed for {record.id}, "
                                f"falling back to Level 1: {e}"
                            )

                # Fall back to Level 1
                if verification is None:
                    verification = await orchestrator.verify_level1(
                        detection_type=detection_type,
                        original_confidence=original_confidence,
                        original_state=original_state,
                        applied_fixes=applied_fixes,
                    )

                # Update the record
                async with async_session_maker() as db:
                    healing = await db.get(HealingRecord, record.id)
                    if healing:
                        healing.validation_status = "passed" if verification.passed else "failed"
                        existing_results = healing.validation_results or {}
                        existing_results["auto_recheck"] = verification.to_dict()
                        healing.validation_results = existing_results
                        await db.commit()

                verified += 1

            except Exception as e:
                logger.warning(f"Recheck failed for healing {record.id}: {e}")
                errors += 1

        logger.info(
            f"Healing recheck completed: {verified} verified, {errors} errors"
        )

    except Exception as e:
        logger.error(f"Healing recheck job failed: {e}")
    finally:
        if redis:
            await release_sync_lock(redis, lock_key)
            await redis.close()


async def check_judge_drift():
    """Periodic job: compute drift reports from recent shadow eval results.

    Queries the shadow_eval_results table, groups by detector, computes
    rolling accuracy, and logs warnings if any detector has drifted below
    its tier threshold.
    """
    lock_key = "mao:shadow_eval:drift_check_lock"
    redis = None

    try:
        redis = await get_redis()
        if not await acquire_sync_lock(redis, lock_key, ttl=300):
            logger.debug("Judge drift check skipped — lock held")
            return

        from app.storage.database import async_session_maker
        from app.storage.models import ShadowEvalResult as ShadowEvalModel
        from app.detection_enterprise.shadow_eval import compute_drift_report, TIER_ACCURACY_THRESHOLDS
        from sqlalchemy import select, desc
        from datetime import datetime, timedelta

        # Detector tier mapping (simplified — production detectors with F1 >= 0.70)
        DETECTOR_TIERS = {
            "loop": "production", "corruption": "production", "persona_drift": "production",
            "hallucination": "production", "coordination": "production",
            "specification": "production", "grounding": "production",
            "decomposition": "production", "context": "production",
            "completion": "production", "context_pressure": "production",
            "withholding": "beta", "overflow": "beta", "retrieval_quality": "beta",
            "communication": "beta", "derailment": "beta", "injection": "beta",
            "workflow": "beta", "convergence": "beta",
        }

        lookback = timedelta(days=7)
        cutoff = datetime.utcnow() - lookback

        async with async_session_maker() as session:
            stmt = (
                select(ShadowEvalModel)
                .where(ShadowEvalModel.created_at >= cutoff)
                .order_by(desc(ShadowEvalModel.created_at))
            )
            rows = (await session.execute(stmt)).scalars().all()

        if not rows:
            logger.info("Judge drift check: no shadow eval results in last 7 days")
            return

        # Group by detector type
        by_detector: dict = {}
        for row in rows:
            by_detector.setdefault(row.detector_type, []).append(row)

        drifted_detectors = []
        for det_type, det_rows in by_detector.items():
            tier = DETECTOR_TIERS.get(det_type, "beta")
            # Convert DB rows to ShadowEvalResult-like objects for the report
            from app.detection_enterprise.shadow_eval import ShadowEvalResult
            results = [
                ShadowEvalResult(
                    detector_type=r.detector_type,
                    golden_entry_id=r.golden_entry_id,
                    expected_detected=r.expected_detected,
                    actual_detected=r.actual_detected,
                    expected_confidence_min=r.expected_confidence_min,
                    expected_confidence_max=r.expected_confidence_max,
                    actual_confidence=r.actual_confidence,
                    match=r.match,
                    error=r.error,
                )
                for r in det_rows
            ]
            report = compute_drift_report(results, detector_tier=tier)
            if report.drifted:
                drifted_detectors.append(report)
                logger.warning(
                    "JUDGE DRIFT DETECTED: %s accuracy %.2f < threshold %.2f (%s tier, %d evals)",
                    det_type, report.accuracy, report.threshold, tier, report.total_evaluations,
                )

        if drifted_detectors:
            logger.warning(
                "Judge drift check: %d/%d detectors drifted",
                len(drifted_detectors), len(by_detector),
            )
        else:
            logger.info(
                "Judge drift check: all %d detectors within thresholds (%d total evals)",
                len(by_detector), len(rows),
            )

    except Exception as e:
        logger.error(f"Judge drift check failed: {e}")
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

    # Add the healing recheck job
    recheck_interval_minutes = int(os.getenv("HEALING_RECHECK_INTERVAL_MINUTES", "30"))
    scheduler.add_job(
        recheck_stale_healings,
        trigger=IntervalTrigger(minutes=recheck_interval_minutes),
        id="healing_recheck",
        name="Healing Recheck",
        replace_existing=True,
        max_instances=1,
    )

    # Add the shadow eval drift check job
    drift_check_hours = int(os.getenv("SHADOW_EVAL_CHECK_HOURS", "6"))
    scheduler.add_job(
        check_judge_drift,
        trigger=IntervalTrigger(hours=drift_check_hours),
        id="judge_drift_check",
        name="Judge Drift Check",
        replace_existing=True,
        max_instances=1,
    )

    logger.info(
        f"Scheduler configured: n8n sync every {sync_interval_minutes} minutes, "
        f"healing recheck every {recheck_interval_minutes} minutes, "
        f"judge drift check every {drift_check_hours} hours"
    )

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
