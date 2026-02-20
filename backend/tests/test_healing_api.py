"""Tests for healing API endpoints."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from app.api.v1.healing import VALID_TRANSITIONS, _check_transition
from fastapi import HTTPException


# --- Unit tests for transition guard ---


class TestTransitionGuard:
    """Tests for the status transition state machine."""

    def test_valid_transition_pending_to_in_progress(self):
        """pending → in_progress is allowed."""
        _check_transition("pending", "in_progress", "h-1")

    def test_valid_transition_staged_to_applied(self):
        """staged → applied is allowed (promote)."""
        _check_transition("staged", "applied", "h-2")

    def test_valid_transition_staged_to_rejected(self):
        """staged → rejected is allowed."""
        _check_transition("staged", "rejected", "h-3")

    def test_valid_transition_applied_to_rolled_back(self):
        """applied → rolled_back is allowed."""
        _check_transition("applied", "rolled_back", "h-4")

    def test_invalid_transition_failed_to_applied(self):
        """failed → applied is not allowed."""
        with pytest.raises(HTTPException) as exc_info:
            _check_transition("failed", "applied", "h-5")
        assert exc_info.value.status_code == 400
        assert "Cannot transition" in exc_info.value.detail

    def test_invalid_transition_rolled_back_to_anything(self):
        """rolled_back is a terminal state."""
        with pytest.raises(HTTPException) as exc_info:
            _check_transition("rolled_back", "in_progress", "h-6")
        assert exc_info.value.status_code == 400

    def test_invalid_transition_rejected_to_anything(self):
        """rejected is a terminal state."""
        with pytest.raises(HTTPException) as exc_info:
            _check_transition("rejected", "staged", "h-7")
        assert exc_info.value.status_code == 400

    def test_all_terminal_states_have_empty_transitions(self):
        """Terminal states (failed, rolled_back, rejected) have no outgoing transitions."""
        for state in ("failed", "rolled_back", "rejected"):
            assert VALID_TRANSITIONS[state] == set(), f"{state} should be terminal"

    def test_all_states_are_defined(self):
        """Every state mentioned in transitions is also a key."""
        all_targets = set()
        for targets in VALID_TRANSITIONS.values():
            all_targets |= targets
        for t in all_targets:
            assert t in VALID_TRANSITIONS, f"Target state '{t}' is not defined as a key"


# --- API Endpoint Tests ---


class TestTriggerHealingEndpoint:
    """Tests for POST /healing/trigger/{detection_id}."""

    @pytest.mark.asyncio
    async def test_trigger_healing_success(self, client, db_session, test_tenant):
        """Triggering healing for a valid detection creates a healing record."""
        detection_id = uuid4()

        # Mock detection lookup
        mock_detection = MagicMock()
        mock_detection.id = detection_id
        mock_detection.tenant_id = test_tenant.id
        mock_detection.detection_type = "infinite_loop"
        mock_detection.method = "structural"
        mock_detection.details = {"iterations": 50}
        mock_detection.confidence = 0.85
        mock_detection.validated = False
        mock_detection.false_positive = False
        mock_detection.trace_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        db_session.execute.return_value = mock_result

        response = await client.post(
            f"/api/v1/healing/trigger/{detection_id}",
            json={"approval_required": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["detection_id"] == str(detection_id)
        assert data["status"] in ("pending", "in_progress")
        assert data["fix_type"] != ""

    @pytest.mark.asyncio
    async def test_trigger_healing_detection_not_found(self, client, db_session):
        """Triggering healing for a non-existent detection returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db_session.execute.return_value = mock_result

        response = await client.post(
            f"/api/v1/healing/trigger/{uuid4()}",
            json={},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_trigger_healing_null_details(self, client, db_session, test_tenant):
        """Triggering healing handles null detection details gracefully."""
        detection_id = uuid4()

        mock_detection = MagicMock()
        mock_detection.id = detection_id
        mock_detection.tenant_id = test_tenant.id
        mock_detection.detection_type = "infinite_loop"
        mock_detection.method = None
        mock_detection.details = None
        mock_detection.confidence = None
        mock_detection.validated = False
        mock_detection.false_positive = False
        mock_detection.trace_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        db_session.execute.return_value = mock_result

        response = await client.post(
            f"/api/v1/healing/trigger/{detection_id}",
            json={},
        )
        # Should not crash — either succeeds or returns a proper error
        assert response.status_code in (200, 400)


class TestHealingStatusEndpoint:
    """Tests for GET /healing/{healing_id}."""

    @pytest.mark.asyncio
    async def test_get_healing_status(self, client, db_session, test_tenant):
        """Getting healing status returns all expected fields."""
        healing_id = uuid4()

        mock_healing = MagicMock()
        mock_healing.id = healing_id
        mock_healing.tenant_id = test_tenant.id
        mock_healing.detection_id = uuid4()
        mock_healing.status = "staged"
        mock_healing.fix_type = "circuit_breaker"
        mock_healing.fix_id = "fix-1"
        mock_healing.fix_suggestions = [{"id": "fix-1", "type": "circuit_breaker"}]
        mock_healing.applied_fixes = {"fix_applied": {"id": "fix-1"}}
        mock_healing.original_state = {"nodes": []}
        mock_healing.rollback_available = True
        mock_healing.validation_status = "passed"
        mock_healing.validation_results = {"level": 1, "passed": True}
        mock_healing.approval_required = False
        mock_healing.approved_by = None
        mock_healing.approved_at = None
        mock_healing.started_at = datetime.now(timezone.utc)
        mock_healing.completed_at = None
        mock_healing.rolled_back_at = None
        mock_healing.created_at = datetime.now(timezone.utc)
        mock_healing.error_message = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_healing
        db_session.execute.return_value = mock_result

        response = await client.get(f"/api/v1/healing/{healing_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "staged"
        assert data["fix_type"] == "circuit_breaker"
        assert data["rollback_available"] is True
        assert data["validation_status"] == "passed"

    @pytest.mark.asyncio
    async def test_get_healing_not_found(self, client, db_session):
        """Getting non-existent healing returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db_session.execute.return_value = mock_result

        response = await client.get(f"/api/v1/healing/{uuid4()}")
        assert response.status_code == 404


class TestHealingListEndpoint:
    """Tests for GET /healing/list."""

    @pytest.mark.asyncio
    async def test_list_healings_pagination(self, client, db_session):
        """Listing healings returns paginated results."""
        # Mock empty result
        mock_count_result = MagicMock()
        mock_count_result.scalar_one_or_none.return_value = 0

        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = []

        db_session.execute.side_effect = [mock_count_result, mock_list_result]

        response = await client.get("/api/v1/healing/list?page=1&per_page=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["page"] == 1
        assert data["per_page"] == 10
