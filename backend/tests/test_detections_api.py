"""Tests for the detections API endpoint filtering and pagination.

Sprint 6 Task 3: Verify list_detections endpoint query construction.

Tests the endpoint function directly with mocked DB, bypassing
the deep import chain (asyncpg, jose, etc.) by pre-mocking modules.
"""

import sys
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

# Pre-mock modules that aren't installed in test environment
for mod_name in [
    "asyncpg",
    "clerk_backend_api", "clerk_backend_api.jwks",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Mock database module to avoid asyncpg engine creation
_mock_db = MagicMock()
_mock_db.get_db = MagicMock()
_mock_db.set_tenant_context = AsyncMock()
sys.modules["app.storage.database"] = _mock_db

from app.api.v1.detections import list_detections, detection_to_response


def _make_mock_detection(confidence=85, detection_type="loop"):
    det = MagicMock()
    det.id = uuid4()
    det.trace_id = uuid4()
    det.state_id = None
    det.detection_type = detection_type
    det.confidence = confidence
    det.method = "hash"
    det.details = {}
    det.validated = False
    det.false_positive = None
    det.created_at = datetime.now(timezone.utc)
    return det


# ============================================================================
# Tests for detection_to_response helper
# ============================================================================

class TestDetectionToResponse:
    """Tests for confidence tier mapping."""

    def test_confidence_tier_high(self):
        response = detection_to_response(_make_mock_detection(confidence=85))
        assert response.confidence_tier == "HIGH"

    def test_confidence_tier_likely(self):
        response = detection_to_response(_make_mock_detection(confidence=65))
        assert response.confidence_tier == "LIKELY"

    def test_confidence_tier_possible(self):
        response = detection_to_response(_make_mock_detection(confidence=45))
        assert response.confidence_tier == "POSSIBLE"

    def test_confidence_tier_low(self):
        response = detection_to_response(_make_mock_detection(confidence=25))
        assert response.confidence_tier == "LOW"

    def test_zero_confidence(self):
        response = detection_to_response(_make_mock_detection(confidence=0))
        assert response.confidence_tier == "LOW"

    def test_max_confidence(self):
        response = detection_to_response(_make_mock_detection(confidence=100))
        assert response.confidence_tier == "HIGH"


# ============================================================================
# Tests for list_detections endpoint
# ============================================================================

class TestListDetectionsFiltering:
    """Tests for list_detections endpoint filter and pagination logic."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[count_result, data_result])
        return db

    @pytest.mark.asyncio
    async def test_pagination_defaults(self, mock_db):
        result = await list_detections(
            page=1, per_page=20,
            detection_type=None, validated=None,
            confidence_min=None, confidence_max=None,
            trace_id=None, date_from=None, date_to=None,
            tenant_id=str(uuid4()), db=mock_db,
        )
        assert result.page == 1
        assert result.per_page == 20
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_empty_result_structure(self, mock_db):
        result = await list_detections(
            page=1, per_page=10,
            detection_type="injection", validated=None,
            confidence_min=60, confidence_max=90,
            trace_id=None, date_from=None, date_to=None,
            tenant_id=str(uuid4()), db=mock_db,
        )
        assert result.items == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_total_reflects_filtered_count(self):
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 42
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[count_result, data_result])

        result = await list_detections(
            page=1, per_page=20,
            detection_type="injection", validated=None,
            confidence_min=80, confidence_max=100,
            trace_id=None, date_from=None, date_to=None,
            tenant_id=str(uuid4()), db=mock_db,
        )
        assert result.total == 42

    @pytest.mark.asyncio
    async def test_pagination_page_2(self, mock_db):
        result = await list_detections(
            page=2, per_page=10,
            detection_type=None, validated=None,
            confidence_min=None, confidence_max=None,
            trace_id=None, date_from=None, date_to=None,
            tenant_id=str(uuid4()), db=mock_db,
        )
        assert result.page == 2
        assert result.per_page == 10
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_with_results(self):
        mock_db = AsyncMock()
        detection = _make_mock_detection(confidence=85, detection_type="loop")
        detection.validated = True
        detection.false_positive = False

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [detection]
        mock_db.execute = AsyncMock(side_effect=[count_result, data_result])

        result = await list_detections(
            page=1, per_page=20,
            detection_type=None, validated=None,
            confidence_min=None, confidence_max=None,
            trace_id=None, date_from=None, date_to=None,
            tenant_id=str(uuid4()), db=mock_db,
        )
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].detection_type == "loop"
        assert result.items[0].confidence_tier == "HIGH"

    @pytest.mark.asyncio
    async def test_trace_id_filter(self, mock_db):
        result = await list_detections(
            page=1, per_page=20,
            detection_type=None, validated=None,
            confidence_min=None, confidence_max=None,
            trace_id=uuid4(), date_from=None, date_to=None,
            tenant_id=str(uuid4()), db=mock_db,
        )
        assert result.total == 0
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_date_range_filter(self, mock_db):
        result = await list_detections(
            page=1, per_page=20,
            detection_type=None, validated=None,
            confidence_min=None, confidence_max=None,
            trace_id=None,
            date_from=datetime.now(timezone.utc) - timedelta(days=7),
            date_to=datetime.now(timezone.utc),
            tenant_id=str(uuid4()), db=mock_db,
        )
        assert result.total == 0
        assert mock_db.execute.call_count == 2
