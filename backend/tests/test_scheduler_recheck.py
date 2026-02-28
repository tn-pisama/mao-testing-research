"""Tests for scheduled healing re-check job.

Sprint 8 Task 3: Verifies that stale healings are automatically re-checked.

Note: The scheduler module has heavy external dependencies (apscheduler, redis,
asyncpg), so we mock them via sys.modules before importing.
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Pre-mock heavy dependencies before any scheduler import
# ---------------------------------------------------------------------------
_saved = {}
for mod_name in [
    "apscheduler", "apscheduler.schedulers", "apscheduler.schedulers.asyncio",
    "apscheduler.triggers", "apscheduler.triggers.interval",
    "redis", "redis.asyncio",
]:
    if mod_name not in sys.modules:
        _saved[mod_name] = None
        sys.modules[mod_name] = MagicMock()

# Import the scheduler module (safe now that deps are mocked)
import app.workers.scheduler as scheduler_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stale_record(
    *,
    deployment_stage="staged",
    validation_status=None,
    hours_ago=2,
    workflow_id="wf-123",
    n8n_connection_id=None,
):
    """Create a mock HealingRecord that looks stale."""
    record = MagicMock()
    record.id = uuid.uuid4()
    record.deployment_stage = deployment_stage
    record.validation_status = validation_status
    record.created_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    record.workflow_id = workflow_id
    record.n8n_connection_id = n8n_connection_id or uuid.uuid4()
    record.applied_fixes = {
        "detection_type": "infinite_loop",
        "original_confidence": 0.85,
        "fix_applied": {"type": "retry_limit", "maxIterations": 10},
    }
    record.original_state = {"nodes": []}
    record.validation_results = {}
    return record


def _mock_verification(passed=True, level=1):
    """Create a mock VerificationResult."""
    result = MagicMock()
    result.passed = passed
    result.level = level
    result.to_dict.return_value = {
        "passed": passed,
        "level": level,
        "before_confidence": 0.85,
        "after_confidence": 0.1 if passed else 0.85,
    }
    return result


def _mock_session(records):
    """Create a mock async session that returns records on execute and allows get/commit."""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = records

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    session.get = AsyncMock(side_effect=lambda cls, rid: next(
        (r for r in records if r.id == rid), None
    ))
    session.commit = AsyncMock()
    return session


def _mock_session_maker(session):
    """Create a mock async_session_maker that yields the mock session."""
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    maker = MagicMock(return_value=ctx)
    return maker


def _mock_redis(lock_acquired=True):
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True if lock_acquired else None)
    redis.delete = AsyncMock()
    redis.close = AsyncMock()
    return redis


# ---------------------------------------------------------------------------
# Core test runner
# ---------------------------------------------------------------------------

async def _run_recheck(records, orch, *, lock_acquired=True, n8n_env=None):
    """Run recheck_stale_healings with all dependencies mocked.

    Patches the lazy imports (app.storage.database, app.storage.models, etc.)
    in sys.modules so the function's `from X import Y` resolves to mocks.
    """
    session = _mock_session(records)
    session_maker = _mock_session_maker(session)
    redis = _mock_redis(lock_acquired=lock_acquired)

    # Build mock modules for the lazy imports
    mock_db_module = MagicMock()
    mock_db_module.async_session_maker = session_maker

    mock_models_module = MagicMock()

    # MagicMock.__lt__ returns NotImplemented, which fails with datetime comparisons.
    # Use a real class that supports comparison operators for column mocks.
    class MockColumn:
        """Mimics a SQLAlchemy column for .in_(), .is_(), <, > operations."""
        def in_(self, values): return MagicMock()
        def is_(self, val): return MagicMock()
        def __lt__(self, other): return MagicMock()
        def __gt__(self, other): return MagicMock()
        def __le__(self, other): return MagicMock()
        def __ge__(self, other): return MagicMock()

    hr_mock = MagicMock()
    hr_mock.deployment_stage = MockColumn()
    hr_mock.validation_status = MockColumn()
    hr_mock.created_at = MockColumn()
    mock_models_module.HealingRecord = hr_mock

    mock_verification_module = MagicMock()
    mock_verification_module.VerificationOrchestrator = MagicMock(return_value=orch)

    mock_n8n_module = MagicMock()
    mock_n8n_client_cls = MagicMock()
    mock_n8n_module.N8nApiClient = mock_n8n_client_cls

    # N8nApiClient as context manager that raises (simulate n8n down) unless overridden
    n8n_ctx = AsyncMock()
    n8n_ctx.__aenter__ = AsyncMock(side_effect=ConnectionError("n8n unavailable"))
    n8n_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_n8n_client_cls.return_value = n8n_ctx

    saved_modules = {}
    mock_modules = {
        "app.storage.database": mock_db_module,
        "app.storage.models": mock_models_module,
        "app.healing.verification": mock_verification_module,
        "app.integrations.n8n_client": mock_n8n_module,
    }

    # Temporarily replace sys.modules entries
    for name, mock_mod in mock_modules.items():
        saved_modules[name] = sys.modules.get(name)
        sys.modules[name] = mock_mod

    env = n8n_env or {}

    # Also mock sqlalchemy select/and_ at module level in the scheduler
    mock_select = MagicMock()
    mock_select.return_value.where.return_value = "mocked_query"

    try:
        with patch.object(scheduler_mod, "get_settings", return_value=MagicMock(redis_url="redis://localhost")), \
             patch.object(scheduler_mod, "aioredis") as mock_aioredis, \
             patch.object(scheduler_mod, "get_sync_lock", AsyncMock(return_value=lock_acquired)), \
             patch.object(scheduler_mod, "release_sync_lock", AsyncMock()), \
             patch.object(scheduler_mod, "select", mock_select), \
             patch.object(scheduler_mod, "and_", MagicMock(return_value="mocked_and")), \
             patch.dict("os.environ", env):

            mock_aioredis.from_url = AsyncMock(return_value=redis)

            await scheduler_mod.recheck_stale_healings()
    finally:
        # Restore sys.modules
        for name, orig in saved_modules.items():
            if orig is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = orig

    return session, orch


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecheckStaleHealings:
    """Tests for recheck_stale_healings() scheduler job."""

    @pytest.mark.asyncio
    async def test_recheck_finds_stale_healings(self):
        """Two stale healings are found and verified."""
        records = [_make_stale_record(), _make_stale_record()]
        verification = _mock_verification(passed=True, level=1)

        mock_orch = AsyncMock()
        mock_orch.verify_level1 = AsyncMock(return_value=verification)

        session, _ = await _run_recheck(records, mock_orch)

        assert mock_orch.verify_level1.call_count == 2
        assert session.commit.call_count >= 2

    @pytest.mark.asyncio
    async def test_recheck_skips_verified(self):
        """Records with validation_status already set are not re-checked."""
        mock_orch = AsyncMock()

        await _run_recheck([], mock_orch)

        mock_orch.verify_level1.assert_not_called()
        mock_orch.verify_level2.assert_not_called()

    @pytest.mark.asyncio
    async def test_recheck_level2_fallback(self):
        """When n8n Level 2 fails, falls back to Level 1."""
        record = _make_stale_record(workflow_id="wf-456")
        verification_l1 = _mock_verification(passed=True, level=1)

        mock_orch = AsyncMock()
        mock_orch.verify_level2 = AsyncMock(side_effect=ConnectionError("n8n down"))
        mock_orch.verify_level1 = AsyncMock(return_value=verification_l1)

        session, _ = await _run_recheck(
            [record], mock_orch,
            n8n_env={"N8N_HOST": "http://n8n:5678", "N8N_API_KEY": "key"},
        )

        # Level 1 should have been called as fallback
        mock_orch.verify_level1.assert_called_once()
        assert record.validation_status == "passed"

    @pytest.mark.asyncio
    async def test_recheck_lock_acquired(self):
        """Redis lock prevents concurrent recheck runs."""
        mock_orch = AsyncMock()

        # Lock not acquired — function should return early
        session, _ = await _run_recheck(
            [_make_stale_record()], mock_orch, lock_acquired=False,
        )

        # No verification should have happened
        mock_orch.verify_level1.assert_not_called()
        mock_orch.verify_level2.assert_not_called()
