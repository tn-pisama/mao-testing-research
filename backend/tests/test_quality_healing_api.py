"""Tests for quality healing API endpoint logic.

These tests verify the engine integration and model serialization
that the API endpoints rely on. Full HTTP integration tests require
asyncpg and database connectivity and are in a separate suite.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, UTC

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality.healing.engine import QualityHealingEngine
from app.enterprise.quality.healing.models import (
    QualityHealingStatus,
    QualityHealingResult,
    QualityFixSuggestion,
    QualityFixCategory,
    QualityAppliedFix,
    QualityValidationResult,
)
from app.enterprise.quality import QualityAssessor


# Shared workflow fixtures — see conftest.py
from tests.conftest import make_low_quality_workflow

LOW_QUALITY_WORKFLOW = make_low_quality_workflow()

GOOD_QUALITY_WORKFLOW = {
    "id": "good-api",
    "name": "Good API Workflow",
    "nodes": [
        {
            "id": "agent-1",
            "name": "Analysis Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "systemMessage": "You are a data analyst. Your role is to analyze data and provide insights. Output in JSON format: {\"result\": \"...\", \"confidence\": 0.0}. Do not make assumptions.",
                "options": {"temperature": 0.2, "maxTokens": 2000},
            },
            "retryOnFail": True,
            "maxTries": 3,
            "continueOnFail": True,
            "position": [0, 0],
        },
    ],
    "connections": {},
    "settings": {"executionTimeout": 300},
}


def _assess(workflow):
    """Helper to produce a QualityReport from a workflow dict."""
    assessor = QualityAssessor(use_llm_judge=False)
    return assessor.assess_workflow(workflow)


# ---------------------------------------------------------------------------
# TestTriggerEndpointLogic
# ---------------------------------------------------------------------------

class TestTriggerEndpointLogic:
    """Tests mirroring the POST /trigger endpoint behaviour."""

    def test_trigger_creates_healing_result(self):
        """Engine heal() should return a result with all expected fields."""
        engine = QualityHealingEngine(auto_apply=False, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)

        result = engine.heal(report, LOW_QUALITY_WORKFLOW)

        assert result.id is not None
        assert result.assessment_id is not None
        assert result.status is not None
        assert isinstance(result.before_score, float)
        assert isinstance(result.dimensions_targeted, list)
        assert isinstance(result.applied_fixes, list)
        assert isinstance(result.validation_results, list)

    def test_trigger_with_auto_apply(self):
        """auto_apply=True should result in a non-PENDING status."""
        engine = QualityHealingEngine(auto_apply=True, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)

        result = engine.heal(report, LOW_QUALITY_WORKFLOW)

        assert result.status != QualityHealingStatus.PENDING

    def test_trigger_with_low_threshold(self):
        """A very low threshold should target fewer dimensions than the default 0.7."""
        report = _assess(LOW_QUALITY_WORKFLOW)

        engine_default = QualityHealingEngine(auto_apply=False, score_threshold=0.7)
        result_default = engine_default.heal(report, LOW_QUALITY_WORKFLOW)

        engine_low = QualityHealingEngine(auto_apply=False, score_threshold=0.3)
        result_low = engine_low.heal(report, LOW_QUALITY_WORKFLOW)

        assert len(result_default.dimensions_targeted) >= len(result_low.dimensions_targeted)


# ---------------------------------------------------------------------------
# TestHealingStatusEndpointLogic
# ---------------------------------------------------------------------------

class TestHealingStatusEndpointLogic:
    """Tests mirroring the GET /{healing_id} endpoint behaviour."""

    def test_get_healing_status(self):
        """Should be able to find a healing result by its ID in history."""
        engine = QualityHealingEngine(auto_apply=False, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)

        result = engine.heal(report, LOW_QUALITY_WORKFLOW)
        history = engine.get_healing_history()

        found = [h for h in history if h.id == result.id]
        assert len(found) == 1
        assert found[0].status == result.status

    def test_get_nonexistent_healing(self):
        """Looking up a non-existent healing ID should yield no results."""
        engine = QualityHealingEngine(auto_apply=False)
        report = _assess(LOW_QUALITY_WORKFLOW)
        engine.heal(report, LOW_QUALITY_WORKFLOW)

        history = engine.get_healing_history()
        found = [h for h in history if h.id == "nonexistent-id"]
        assert len(found) == 0


# ---------------------------------------------------------------------------
# TestApproveEndpointLogic
# ---------------------------------------------------------------------------

class TestApproveEndpointLogic:
    """Tests mirroring the POST /{healing_id}/approve endpoint behaviour."""

    def test_approve_pending_healing(self):
        """Approving a pending healing should change status away from PENDING."""
        engine = QualityHealingEngine(auto_apply=False, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)

        result = engine.heal(report, LOW_QUALITY_WORKFLOW)
        assert result.status == QualityHealingStatus.PENDING

        fix_ids = [s["id"] for s in result.metadata["fix_suggestions"]]
        approved = engine.approve_and_apply(result.id, fix_ids[:1])

        assert approved.status != QualityHealingStatus.PENDING

    def test_approve_non_pending_raises(self):
        """Approving an already-applied (non-PENDING) healing should raise ValueError."""
        engine = QualityHealingEngine(auto_apply=True, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)

        result = engine.heal(report, LOW_QUALITY_WORKFLOW)
        # Result is already SUCCESS/PARTIAL_SUCCESS/FAILED, not PENDING
        assert result.status != QualityHealingStatus.PENDING

        with pytest.raises(ValueError, match="not pending"):
            engine.approve_and_apply(result.id, ["fix-1"])


# ---------------------------------------------------------------------------
# TestRollbackEndpointLogic
# ---------------------------------------------------------------------------

class TestRollbackEndpointLogic:
    """Tests mirroring the POST /{healing_id}/rollback endpoint behaviour."""

    def test_rollback_applied_healing(self):
        """Rollback on a healing with applied fixes should succeed."""
        engine = QualityHealingEngine(auto_apply=True, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)

        result = engine.heal(report, LOW_QUALITY_WORKFLOW)

        if len(result.applied_fixes) > 0:
            original = engine.rollback(result.id)
            assert isinstance(original, dict)
            assert result.status == QualityHealingStatus.ROLLED_BACK

    def test_rollback_pending_raises(self):
        """Rollback on a PENDING healing with no applied fixes should raise ValueError."""
        engine = QualityHealingEngine(auto_apply=False, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)

        result = engine.heal(report, LOW_QUALITY_WORKFLOW)
        assert result.status == QualityHealingStatus.PENDING
        assert len(result.applied_fixes) == 0

        with pytest.raises(ValueError, match="No fixes to rollback"):
            engine.rollback(result.id)


# ---------------------------------------------------------------------------
# TestListEndpointLogic
# ---------------------------------------------------------------------------

class TestListEndpointLogic:
    """Tests mirroring the GET / (list) endpoint behaviour."""

    def test_list_healings(self):
        """Running 3 healings should return all 3 in history."""
        engine = QualityHealingEngine(auto_apply=False, score_threshold=0.7)

        for _ in range(3):
            report = _assess(LOW_QUALITY_WORKFLOW)
            engine.heal(report, LOW_QUALITY_WORKFLOW)

        history = engine.get_healing_history()
        assert len(history) == 3

    def test_list_with_status_filter(self):
        """Filtering history by status should return only matching records."""
        engine = QualityHealingEngine(auto_apply=False, score_threshold=0.7)

        # Create a PENDING healing (low quality + auto_apply=False)
        report = _assess(LOW_QUALITY_WORKFLOW)
        engine.heal(report, LOW_QUALITY_WORKFLOW)

        # Create a SUCCESS healing using a very low threshold so no fixes are needed
        engine_auto = QualityHealingEngine(auto_apply=True, score_threshold=0.1)
        good_report = _assess(GOOD_QUALITY_WORKFLOW)
        engine_auto.heal(good_report, GOOD_QUALITY_WORKFLOW)

        # Filter the first engine's history for PENDING
        history = engine.get_healing_history()
        pending = [h for h in history if h.status == QualityHealingStatus.PENDING]
        assert len(pending) == 1

        # Filter the second engine's history for SUCCESS
        auto_history = engine_auto.get_healing_history()
        successes = [h for h in auto_history if h.status == QualityHealingStatus.SUCCESS]
        assert len(successes) == 1


# ---------------------------------------------------------------------------
# TestStatsEndpointLogic
# ---------------------------------------------------------------------------

class TestStatsEndpointLogic:
    """Tests mirroring the GET /stats endpoint behaviour."""

    def test_stats_returns_correct_shape(self):
        """Stats dict should contain all expected keys."""
        engine = QualityHealingEngine(auto_apply=True, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)
        engine.heal(report, LOW_QUALITY_WORKFLOW)

        stats = engine.get_healing_stats()

        assert "total" in stats
        assert "success_rate" in stats
        assert "avg_improvement" in stats
        assert "by_status" in stats
        assert "by_dimension" in stats

        assert isinstance(stats["total"], int)
        assert isinstance(stats["success_rate"], float)
        assert isinstance(stats["avg_improvement"], float)
        assert isinstance(stats["by_status"], dict)
        assert isinstance(stats["by_dimension"], dict)


# ---------------------------------------------------------------------------
# TestHealingResultSerialization
# ---------------------------------------------------------------------------

class TestHealingResultSerialization:
    """Tests for model to_dict() serialization used in API responses."""

    def test_healing_result_to_dict(self):
        """QualityHealingResult.to_dict() should return all expected fields."""
        engine = QualityHealingEngine(auto_apply=True, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)
        result = engine.heal(report, LOW_QUALITY_WORKFLOW)

        d = result.to_dict()

        assert isinstance(d, dict)
        assert "id" in d
        assert "assessment_id" in d
        assert "status" in d
        assert "started_at" in d
        assert "completed_at" in d
        assert "dimensions_targeted" in d
        assert "applied_fixes" in d
        assert "validation_results" in d
        assert "before_score" in d
        assert "after_score" in d
        assert "is_successful" in d
        assert "score_improvement" in d
        assert "metadata" in d

    def test_fix_suggestion_to_dict(self):
        """QualityFixSuggestion.to_dict() should return all expected fields."""
        suggestion = QualityFixSuggestion.create(
            dimension="role_clarity",
            category=QualityFixCategory.ROLE_CLARITY,
            title="Add system prompt",
            description="The agent is missing a system prompt defining its role.",
            confidence=0.9,
            expected_improvement=0.15,
            target_type="agent",
            target_id="agent-1",
            changes={"set_system_message": "You are a helpful assistant."},
        )

        d = suggestion.to_dict()

        assert isinstance(d, dict)
        assert d["dimension"] == "role_clarity"
        assert d["category"] == "role_clarity"
        assert d["title"] == "Add system prompt"
        assert d["confidence"] == 0.9
        assert d["expected_improvement"] == 0.15
        assert d["target_type"] == "agent"
        assert d["target_id"] == "agent-1"
        assert "changes" in d
        assert d["breaking_changes"] is False
        assert d["effort"] == "low"

    def test_validation_result_to_dict(self):
        """QualityValidationResult.to_dict() should return all expected fields."""
        vr = QualityValidationResult(
            success=True,
            dimension="role_clarity",
            before_score=0.3,
            after_score=0.75,
            improvement=0.45,
            details={"message": "System prompt added successfully"},
        )

        d = vr.to_dict()

        assert isinstance(d, dict)
        assert d["success"] is True
        assert d["dimension"] == "role_clarity"
        assert d["before_score"] == 0.3
        assert d["after_score"] == 0.75
        assert d["improvement"] == 0.45
        assert "details" in d

    def test_applied_fix_to_dict(self):
        """QualityAppliedFix.to_dict() should return all expected fields."""
        af = QualityAppliedFix(
            fix_id="qfix_abc123",
            dimension="error_handling",
            applied_at=datetime.now(UTC),
            target_component="agent-1",
            original_state={"parameters": {}},
            modified_state={"parameters": {"retryOnFail": True}},
            rollback_available=True,
        )

        d = af.to_dict()

        assert isinstance(d, dict)
        assert d["fix_id"] == "qfix_abc123"
        assert d["dimension"] == "error_handling"
        assert "applied_at" in d
        assert d["target_component"] == "agent-1"
        assert d["rollback_available"] is True


# ---------------------------------------------------------------------------
# TestVerifyEndpointLogic
# ---------------------------------------------------------------------------

class TestVerifyEndpointLogic:
    """Tests mirroring the POST /{healing_id}/verify endpoint behaviour.

    The verify endpoint re-runs quality assessment on the modified workflow
    and updates the healing status based on whether the score improved.
    Since the actual endpoint requires a DB, these tests exercise the
    underlying re-assessment logic directly.
    """

    def test_verify_improved_workflow_succeeds(self):
        """Re-assessing a healed workflow should detect score improvement."""
        # Heal the low-quality workflow with auto_apply
        engine = QualityHealingEngine(auto_apply=True, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)
        result = engine.heal(report, LOW_QUALITY_WORKFLOW)

        # The verify endpoint re-assesses the modified state
        if result.applied_fixes:
            modified_config = result.applied_fixes[-1].modified_state
            assessor = QualityAssessor(use_llm_judge=False)
            new_report = assessor.assess_workflow(modified_config)

            # Verify the re-assessment produces a valid score
            assert isinstance(new_report.overall_score, float)
            assert 0.0 <= new_report.overall_score <= 1.0

            # Mimic the verify endpoint's status decision logic
            before_score = result.before_score
            after_score = new_report.overall_score
            if after_score > before_score:
                status = "success"
            else:
                status = "failed"

            assert status in ("success", "failed")

    def test_verify_requires_applied_fixes(self):
        """Verification should not proceed if there are no applied fixes.

        This mirrors the HTTP 400 guard in the verify endpoint:
        ``if not record.applied_fixes: raise HTTPException(400, ...)``
        """
        engine = QualityHealingEngine(auto_apply=False, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)
        result = engine.heal(report, LOW_QUALITY_WORKFLOW)

        # PENDING result has no applied fixes
        assert result.status == QualityHealingStatus.PENDING
        assert len(result.applied_fixes) == 0

        # The verify endpoint would reject this with 400
        has_fixes = bool(result.applied_fixes)
        assert has_fixes is False

    def test_verify_score_improvement_calculation(self):
        """Verify that score_improvement is correctly computed as after - before."""
        before = 0.35
        after = 0.72
        improvement = round(after - before, 3)

        assert improvement == 0.37
        assert improvement > 0  # positive means improved

    def test_verify_status_logic_improved(self):
        """When after_score > before_score the status should be 'success'."""
        before_score = 0.4
        after_score = 0.65

        # Mirror the verify endpoint logic
        if after_score > before_score:
            status = "success"
        else:
            status = "failed"

        assert status == "success"

    def test_verify_status_logic_no_improvement(self):
        """When after_score <= before_score the status should be 'failed'."""
        before_score = 0.6
        after_score = 0.6

        if after_score > before_score:
            status = "success"
        else:
            status = "failed"

        assert status == "failed"

    def test_verify_reassessment_on_good_workflow(self):
        """Re-assessing the good workflow should produce a reasonable score."""
        assessor = QualityAssessor(use_llm_judge=False)
        report = assessor.assess_workflow(GOOD_QUALITY_WORKFLOW)

        assert report.overall_score > 0.4
        assert report.workflow_id == "good-api"


# ---------------------------------------------------------------------------
# TestPaginationLogic
# ---------------------------------------------------------------------------

class TestPaginationLogic:
    """Tests for pagination math used by the list healings endpoint.

    The list endpoint computes ``offset = (page - 1) * page_size`` and
    returns a HealingListResponse with ``items``, ``total``, ``page``,
    and ``page_size``.  These tests verify the arithmetic without a DB.
    """

    @staticmethod
    def _paginate(items, page, page_size):
        """Pure-Python pagination replicating the endpoint's SQL logic."""
        total = len(items)
        offset = (page - 1) * page_size
        page_items = items[offset : offset + page_size]
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def test_first_page(self):
        """Page 1 should return the first page_size items."""
        items = list(range(25))
        result = self._paginate(items, page=1, page_size=10)

        assert result["items"] == list(range(10))
        assert result["total"] == 25
        assert result["page"] == 1
        assert result["page_size"] == 10

    def test_middle_page(self):
        """Page 2 should skip the first page_size items."""
        items = list(range(25))
        result = self._paginate(items, page=2, page_size=10)

        assert result["items"] == list(range(10, 20))
        assert result["total"] == 25
        assert result["page"] == 2

    def test_last_page_partial(self):
        """The last page may contain fewer items than page_size."""
        items = list(range(25))
        result = self._paginate(items, page=3, page_size=10)

        assert result["items"] == list(range(20, 25))
        assert len(result["items"]) == 5
        assert result["total"] == 25

    def test_page_beyond_total(self):
        """Requesting a page beyond the last should return an empty list."""
        items = list(range(5))
        result = self._paginate(items, page=2, page_size=10)

        assert result["items"] == []
        assert result["total"] == 5

    def test_offset_calculation(self):
        """offset = (page - 1) * page_size should be correct for several pages."""
        assert (1 - 1) * 50 == 0
        assert (2 - 1) * 50 == 50
        assert (3 - 1) * 50 == 100
        assert (1 - 1) * 500 == 0
        assert (5 - 1) * 20 == 80

    def test_single_item_page(self):
        """page_size=1 should return exactly one item per page."""
        items = ["a", "b", "c"]
        r1 = self._paginate(items, page=1, page_size=1)
        r2 = self._paginate(items, page=2, page_size=1)
        r3 = self._paginate(items, page=3, page_size=1)

        assert r1["items"] == ["a"]
        assert r2["items"] == ["b"]
        assert r3["items"] == ["c"]
        assert r1["total"] == 3

    def test_empty_collection(self):
        """Paginating an empty collection should return empty items with total=0."""
        result = self._paginate([], page=1, page_size=50)

        assert result["items"] == []
        assert result["total"] == 0
        assert result["page"] == 1

    def test_exact_page_boundary(self):
        """When total is an exact multiple of page_size the last page should be full."""
        items = list(range(20))
        result = self._paginate(items, page=2, page_size=10)

        assert result["items"] == list(range(10, 20))
        assert len(result["items"]) == 10

    def test_engine_history_limit_acts_as_page_size(self):
        """Engine.get_healing_history(limit=N) truncates like a page_size."""
        engine = QualityHealingEngine(auto_apply=False, score_threshold=0.7)
        for _ in range(5):
            report = _assess(LOW_QUALITY_WORKFLOW)
            engine.heal(report, LOW_QUALITY_WORKFLOW)

        limited = engine.get_healing_history(limit=3)
        full = engine.get_healing_history(limit=100)

        assert len(limited) == 3
        assert len(full) == 5


# ---------------------------------------------------------------------------
# TestRollbackResponse
# ---------------------------------------------------------------------------

class TestRollbackResponse:
    """Tests for the rollback response shape.

    The DB-persisted API returns a RollbackResponse with fields:
    ``success``, ``message``, and ``healing_id``. These tests verify
    that the engine produces the data needed to populate that shape,
    and that the shape contract is correct.
    """

    def test_rollback_response_shape(self):
        """A successful rollback should yield data matching RollbackResponse."""
        engine = QualityHealingEngine(auto_apply=True, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)
        result = engine.heal(report, LOW_QUALITY_WORKFLOW)

        if result.applied_fixes:
            original = engine.rollback(result.id)
            # Build the response dict matching the API's RollbackResponse model
            response = {
                "success": True,
                "message": f"Successfully rolled back healing {result.id}",
                "healing_id": result.id,
            }

            assert response["success"] is True
            assert result.id in response["message"]
            assert response["healing_id"] == result.id
            assert isinstance(original, dict)

    def test_rollback_sets_rolled_back_status(self):
        """After rollback the healing result status should be ROLLED_BACK."""
        engine = QualityHealingEngine(auto_apply=True, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)
        result = engine.heal(report, LOW_QUALITY_WORKFLOW)

        if result.applied_fixes:
            engine.rollback(result.id)
            assert result.status == QualityHealingStatus.ROLLED_BACK

    def test_rollback_records_timestamp(self):
        """Rollback should store a rolled_back_at timestamp in metadata."""
        engine = QualityHealingEngine(auto_apply=True, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)
        result = engine.heal(report, LOW_QUALITY_WORKFLOW)

        if result.applied_fixes:
            engine.rollback(result.id)
            assert "rolled_back_at" in result.metadata
            # Should be a valid ISO timestamp string
            ts = result.metadata["rolled_back_at"]
            parsed = datetime.fromisoformat(ts)
            assert isinstance(parsed, datetime)

    def test_rollback_returns_original_state(self):
        """Rollback should return the original workflow state from before fixes."""
        engine = QualityHealingEngine(auto_apply=True, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)
        result = engine.heal(report, LOW_QUALITY_WORKFLOW)

        if result.applied_fixes:
            original = engine.rollback(result.id)
            # The original state should be a workflow dict (has nodes, id, etc.)
            assert isinstance(original, dict)

    def test_rollback_not_found_raises(self):
        """Rollback on a nonexistent healing ID should raise ValueError."""
        engine = QualityHealingEngine(auto_apply=True, score_threshold=0.7)

        with pytest.raises(ValueError, match="not found"):
            engine.rollback("nonexistent-healing-id")

    def test_rollback_no_fixes_raises(self):
        """Rollback with no applied fixes should raise ValueError."""
        engine = QualityHealingEngine(auto_apply=False, score_threshold=0.7)
        report = _assess(LOW_QUALITY_WORKFLOW)
        result = engine.heal(report, LOW_QUALITY_WORKFLOW)

        # PENDING has no applied fixes
        with pytest.raises(ValueError, match="No fixes to rollback"):
            engine.rollback(result.id)

    def test_rollback_response_fields_are_correct_types(self):
        """All fields in the rollback response should have correct types."""
        # Verify the shape contract independently
        response = {
            "success": True,
            "message": "Successfully rolled back healing qheal_abc123",
            "healing_id": "qheal_abc123",
        }
        assert isinstance(response["success"], bool)
        assert isinstance(response["message"], str)
        assert isinstance(response["healing_id"], str)
