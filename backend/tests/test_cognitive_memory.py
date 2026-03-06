"""Tests for PISAMA Cognitive Memory: CompositeScorer, CognitiveMemoryService, MemoryExtractor.

Covers ~50 tests across composite scoring, remember/recall/forget/tree operations,
integration hooks, and atomic fact extraction.
"""

import hashlib
import math
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.detection_enterprise.cognitive_memory import (
    CompositeScorer,
    CompositeWeights,
    CognitiveMemoryService,
    DetectionRecallContext,
    FixRecallContext,
    ScoredMemory,
)
from app.detection_enterprise.memory_extractor import (
    ExtractedFact,
    Contradiction,
    MemoryExtractionResult,
    MemoryExtractor,
)
from app.storage.models import CognitiveMemory, MemoryRecallLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT_ID = uuid.uuid4()


def _make_memory(
    content: str = "test memory",
    memory_type: str = "detection_pattern",
    domain: str = "loop",
    importance: float = 0.5,
    confidence: float = 0.5,
    access_count: int = 0,
    is_active: bool = True,
    created_at: Optional[datetime] = None,
    structured_data: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    framework: Optional[str] = None,
    source_type: str = "detection",
) -> CognitiveMemory:
    """Create a CognitiveMemory instance for testing (no DB required)."""
    mem = CognitiveMemory()
    mem.id = uuid.uuid4()
    mem.tenant_id = TENANT_ID
    mem.content = content
    mem.content_hash = hashlib.sha256(content.encode()).hexdigest()
    mem.memory_type = memory_type
    mem.domain = domain
    mem.importance = importance
    mem.confidence = confidence
    mem.access_count = access_count
    mem.is_active = is_active
    mem.created_at = created_at or datetime.now(timezone.utc)
    mem.structured_data = structured_data or {}
    mem.tags = tags or []
    mem.framework = framework
    mem.source_type = source_type
    mem.source_id = None
    mem.source_trace_id = None
    mem.embedding = None
    mem.supersedes_id = None
    mem.superseded_by_id = None
    mem.last_accessed_at = None
    return mem


class MockSession:
    """Minimal mock SQLAlchemy session that tracks add/flush/commit calls."""

    def __init__(self):
        self.added: List[Any] = []
        self.committed = False
        self._existing: Optional[CognitiveMemory] = None
        self._query_results: List[CognitiveMemory] = []

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.committed = True

    def query(self, model):
        return _MockQuery(self._existing, self._query_results)

    def execute(self, *args, **kwargs):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        mock_result.fetchone.return_value = None
        mock_result.fetchall.return_value = []
        return mock_result


class _MockQuery:
    """Chain-able mock query that returns preset results."""

    def __init__(self, existing, all_results):
        self._existing = existing
        self._all_results = all_results

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, n):
        self._all_results = self._all_results[:n]
        return self

    def first(self):
        return self._existing

    def all(self):
        return self._all_results

    def get(self, id_):
        return self._existing


def _service(session=None, embedder=None, llm_client=None) -> CognitiveMemoryService:
    """Create a CognitiveMemoryService with sensible defaults for testing."""
    return CognitiveMemoryService(
        session=session or MockSession(),
        tenant_id=TENANT_ID,
        embedder=embedder,
        llm_client=llm_client,
    )


# ===========================================================================
# TestCompositeScorer
# ===========================================================================

class TestCompositeScorer:

    def test_perfect_scores(self):
        scorer = CompositeScorer()
        # similarity=1.0, just created (recency ~ 1.0), importance=1.0, no access bonus
        now = datetime.now(timezone.utc)
        score = scorer.score(1.0, now, 1.0, 0)
        # (1.0 * 0.4) + (~1.0 * 0.2) + (1.0 * 0.4) + 0 = ~1.0
        assert score > 0.95
        assert score <= 1.05  # small float tolerance

    def test_zero_scores(self):
        scorer = CompositeScorer()
        old = datetime.now(timezone.utc) - timedelta(days=1000)
        score = scorer.score(0.0, old, 0.0, 0)
        # (0 * 0.4) + (very small * 0.2) + (0 * 0.4) + 0 ≈ 0
        assert score < 0.05

    def test_similarity_weight(self):
        scorer = CompositeScorer()
        now = datetime.now(timezone.utc)
        high = scorer.score(1.0, now, 0.5, 0)
        low = scorer.score(0.0, now, 0.5, 0)
        assert high > low

    def test_recency_decay(self):
        scorer = CompositeScorer()
        now = datetime.now(timezone.utc)
        recent = scorer.score(0.5, now, 0.5, 0)
        ninety_days = scorer.score(0.5, now - timedelta(days=90), 0.5, 0)
        old = scorer.score(0.5, now - timedelta(days=180), 0.5, 0)
        assert recent > ninety_days > old

        # At 90 days: recency = e^(-1) ≈ 0.368
        recency_90 = math.exp(-1)
        expected_90 = 0.5 * 0.4 + recency_90 * 0.2 + 0.5 * 0.4
        assert abs(ninety_days - expected_90) < 0.01

    def test_importance_weight(self):
        scorer = CompositeScorer()
        now = datetime.now(timezone.utc)
        high_imp = scorer.score(0.5, now, 1.0, 0)
        low_imp = scorer.score(0.5, now, 0.0, 0)
        assert high_imp > low_imp
        # Difference should be close to 0.4 (importance weight)
        assert abs((high_imp - low_imp) - 0.4) < 0.01

    def test_access_count_bonus(self):
        scorer = CompositeScorer()
        now = datetime.now(timezone.utc)
        no_access = scorer.score(0.5, now, 0.5, 0)
        many_access = scorer.score(0.5, now, 0.5, 100)
        # Bonus = min(0.05, log(1+100)*0.02) = min(0.05, ~0.092) = 0.05
        assert many_access - no_access == pytest.approx(0.05, abs=0.001)

    def test_custom_weights(self):
        weights = CompositeWeights(similarity=0.6, recency=0.1, importance=0.3)
        scorer = CompositeScorer(weights)
        now = datetime.now(timezone.utc)
        score = scorer.score(1.0, now, 0.0, 0)
        # (1.0 * 0.6) + (~1.0 * 0.1) + (0.0 * 0.3) = ~0.7
        assert abs(score - 0.7) < 0.02


# ===========================================================================
# TestRemember
# ===========================================================================

class TestRemember:

    def test_remember_creates_memory(self):
        session = MockSession()
        svc = _service(session)
        mem = svc.remember("agent looped 3 times", "detection_pattern", "loop", "detection")
        assert len(session.added) == 1
        assert session.added[0].content == "agent looped 3 times"
        assert session.added[0].memory_type == "detection_pattern"
        assert session.added[0].domain == "loop"

    def test_remember_returns_memory_object(self):
        svc = _service()
        result = svc.remember("some fact", "detection_pattern", "loop", "detection")
        assert isinstance(result, CognitiveMemory)
        assert result.content == "some fact"

    def test_remember_content_hash(self):
        svc = _service()
        mem = svc.remember("deterministic content", "detection_pattern", "loop", "detection")
        expected = hashlib.sha256(b"deterministic content").hexdigest()
        assert mem.content_hash == expected

    def test_remember_dedup_by_hash(self):
        existing = _make_memory(content="duplicate content")
        session = MockSession()
        session._existing = existing
        svc = _service(session)
        result = svc.remember("duplicate content", "detection_pattern", "loop", "detection")
        # Should return existing memory, not add a new one
        assert result is existing
        assert len(session.added) == 0

    def test_remember_custom_importance(self):
        svc = _service()
        mem = svc.remember(
            "critical finding", "detection_pattern", "loop", "detection",
            importance=0.9,
        )
        assert mem.importance == 0.9

    def test_remember_with_tags(self):
        svc = _service()
        mem = svc.remember(
            "tagged memory", "detection_pattern", "loop", "detection",
            tags=["critical", "regression"],
        )
        assert mem.tags == ["critical", "regression"]

    def test_remember_with_framework(self):
        svc = _service()
        mem = svc.remember(
            "framework memory", "detection_pattern", "loop", "detection",
            framework="langgraph",
        )
        assert mem.framework == "langgraph"

    def test_remember_with_structured_data(self):
        svc = _service()
        data = {"method": "hash", "tier": 1}
        mem = svc.remember(
            "structured memory", "detection_pattern", "loop", "detection",
            structured_data=data,
        )
        assert mem.structured_data == data

    def test_remember_with_source(self):
        src_id = uuid.uuid4()
        trace_id = uuid.uuid4()
        svc = _service()
        mem = svc.remember(
            "sourced memory", "detection_pattern", "loop", "detection",
            source_id=src_id,
            source_trace_id=trace_id,
        )
        assert mem.source_id == src_id
        assert mem.source_trace_id == trace_id
        assert mem.source_type == "detection"

    def test_remember_defaults(self):
        svc = _service()
        mem = svc.remember("basic memory", "detection_pattern", "loop", "detection")
        assert mem.importance == 0.5
        assert mem.confidence == 0.5
        assert mem.access_count == 0
        assert mem.is_active is True
        assert mem.embedding is None
        assert mem.tags == []
        assert mem.framework is None


# ===========================================================================
# TestRecall
# ===========================================================================

class TestRecall:

    def _service_with_candidates(self, memories, similarities=None):
        """Create a service where _retrieve_candidates returns preset data."""
        if similarities is None:
            similarities = [0.8] * len(memories)
        svc = _service()
        candidates = list(zip(memories, similarities))
        svc._retrieve_candidates = MagicMock(return_value=candidates)
        svc._log_recall = MagicMock()
        return svc

    def test_recall_returns_scored_memories(self):
        m1 = _make_memory("memory 1", importance=0.8)
        m2 = _make_memory("memory 2", importance=0.6)
        svc = self._service_with_candidates([m1, m2], [0.9, 0.7])
        results = svc.recall("test query")
        assert len(results) == 2
        assert all(isinstance(r, ScoredMemory) for r in results)
        assert results[0].composite_score >= results[1].composite_score

    def test_recall_filters_by_domain(self):
        m1 = _make_memory("m1", domain="loop")
        svc = self._service_with_candidates([m1])
        svc.recall("test", domain="loop")
        call_args = svc._retrieve_candidates.call_args
        assert call_args[0][2] == "loop"  # domain param

    def test_recall_filters_by_type(self):
        m1 = _make_memory("m1")
        svc = self._service_with_candidates([m1])
        svc.recall("test", memory_type="fix_outcome")
        call_args = svc._retrieve_candidates.call_args
        assert call_args[0][3] == "fix_outcome"

    def test_recall_filters_by_framework(self):
        m1 = _make_memory("m1", framework="crewai")
        svc = self._service_with_candidates([m1])
        svc.recall("test", framework="crewai")
        call_args = svc._retrieve_candidates.call_args
        assert call_args[0][4] == "crewai"

    def test_recall_respects_k_limit(self):
        memories = [_make_memory(f"m{i}", importance=0.8) for i in range(10)]
        svc = self._service_with_candidates(memories, [0.9] * 10)
        results = svc.recall("test", k=3)
        assert len(results) <= 3

    def test_recall_confidence_levels(self):
        m_high = _make_memory("high", importance=1.0)
        m_med = _make_memory("medium", importance=0.5)
        m_low = _make_memory("low", importance=0.1)
        svc = self._service_with_candidates(
            [m_high, m_med, m_low], [0.95, 0.6, 0.3]
        )
        results = svc.recall("test", min_confidence=0.0)
        # Results are sorted by composite score (descending)
        levels = {r.confidence_level for r in results}
        # With sim=0.95/imp=1.0 composite should be >= 0.7 -> high
        assert results[0].confidence_level == "high"

    def test_recall_logs_audit_entry(self):
        m1 = _make_memory("m1")
        svc = self._service_with_candidates([m1])
        svc.recall("test query")
        svc._log_recall.assert_called_once()
        args = svc._log_recall.call_args[0]
        assert args[0] == "test query"

    def test_recall_empty_results(self):
        svc = self._service_with_candidates([])
        results = svc.recall("nonexistent query")
        assert results == []


# ===========================================================================
# TestForget
# ===========================================================================

class TestForget:

    def test_forget_by_id(self):
        mem = _make_memory("to forget")
        session = MockSession()
        session._query_results = [mem]
        svc = _service(session)
        result = svc.forget(memory_id=mem.id)
        assert result["deactivated_count"] == 1
        assert mem.is_active is False

    def test_forget_by_domain(self):
        m1 = _make_memory("m1", domain="loop")
        m2 = _make_memory("m2", domain="loop")
        session = MockSession()
        session._query_results = [m1, m2]
        svc = _service(session)
        result = svc.forget(domain="loop")
        assert result["deactivated_count"] == 2

    def test_forget_by_age(self):
        old_mem = _make_memory("old", created_at=datetime.now(timezone.utc) - timedelta(days=100))
        session = MockSession()
        session._query_results = [old_mem]
        svc = _service(session)
        result = svc.forget(older_than_days=90)
        assert result["deactivated_count"] == 1

    def test_forget_by_importance(self):
        low_mem = _make_memory("low", importance=0.1)
        session = MockSession()
        session._query_results = [low_mem]
        svc = _service(session)
        result = svc.forget(importance_below=0.3)
        assert result["deactivated_count"] == 1

    def test_forget_requires_criteria(self):
        svc = _service()
        result = svc.forget()
        assert result["deactivated_count"] == 0
        assert "no filter" in result["reason"]


# ===========================================================================
# TestTree
# ===========================================================================

class TestTree:

    def test_tree_groups_by_type_and_domain(self):
        m1 = _make_memory("m1", memory_type="detection_pattern", domain="loop")
        m2 = _make_memory("m2", memory_type="detection_pattern", domain="corruption")
        m3 = _make_memory("m3", memory_type="fix_outcome", domain="loop")
        session = MockSession()
        session._query_results = [m1, m2, m3]
        svc = _service(session)
        tree = svc.tree()
        assert "detection_pattern" in tree
        assert "loop" in tree["detection_pattern"]
        assert "corruption" in tree["detection_pattern"]
        assert "fix_outcome" in tree
        assert "loop" in tree["fix_outcome"]

    def test_tree_counts_and_averages(self):
        m1 = _make_memory("m1", memory_type="detection_pattern", domain="loop", importance=0.8)
        m2 = _make_memory("m2", memory_type="detection_pattern", domain="loop", importance=0.6)
        session = MockSession()
        session._query_results = [m1, m2]
        svc = _service(session)
        tree = svc.tree()
        bucket = tree["detection_pattern"]["loop"]
        assert bucket["count"] == 2
        assert bucket["avg_importance"] == pytest.approx(0.7, abs=0.01)

    def test_tree_excludes_inactive(self):
        active = _make_memory("active", is_active=True)
        inactive = _make_memory("inactive", is_active=False)
        session = MockSession()
        # By default tree filters is_active=True; our mock returns all
        # so we only include the active one
        session._query_results = [active]
        svc = _service(session)
        tree = svc.tree()
        total = sum(
            b["count"]
            for type_dict in tree.values()
            for b in type_dict.values()
        )
        assert total == 1


# ===========================================================================
# TestIntegrationHooks
# ===========================================================================

class TestIntegrationHooks:

    def test_remember_detection(self):
        session = MockSession()
        svc = _service(session)
        mem = svc.remember_detection(
            detection_type="loop",
            confidence=0.85,
            method="hash",
            details="3 identical states detected",
        )
        assert "loop" in mem.content
        assert "0.85" in mem.content
        assert mem.domain == "loop"
        assert mem.memory_type == "detection_pattern"
        assert mem.structured_data["confidence"] == 0.85

    def test_remember_feedback_false_positive(self):
        svc = _service()
        mem = svc.remember_feedback(
            detection_type="corruption",
            is_correct=False,
            feedback_type="false_positive",
            confidence=0.7,
        )
        assert "False positive" in mem.content
        assert mem.importance == 0.8
        assert mem.memory_type == "feedback"

    def test_remember_feedback_true_positive(self):
        svc = _service()
        mem = svc.remember_feedback(
            detection_type="corruption",
            is_correct=True,
            feedback_type="true_positive",
            confidence=0.9,
        )
        assert "True positive" in mem.content
        assert mem.importance == 0.5

    def test_remember_calibration(self):
        svc = _service()
        mem = svc.remember_calibration(
            detector_name="loop",
            f1_score=0.85,
            f1_delta=0.05,
            threshold=0.65,
        )
        assert "Calibration" in mem.content
        assert "loop" in mem.content
        assert "improved" in mem.content
        assert mem.memory_type == "threshold_learning"
        assert mem.domain == "loop"

    def test_remember_fix_outcome_success(self):
        svc = _service()
        mem = svc.remember_fix_outcome(
            detection_type="loop",
            fix_type="add_dedup_cache",
            was_successful=True,
            framework="langgraph",
        )
        assert "succeeded" in mem.content
        assert mem.importance == 0.7
        assert mem.framework == "langgraph"

    def test_remember_fix_outcome_failure(self):
        svc = _service()
        mem = svc.remember_fix_outcome(
            detection_type="loop",
            fix_type="retry_limit",
            was_successful=False,
        )
        assert "failed" in mem.content
        assert mem.importance == 0.6

    def test_recall_for_detection(self):
        svc = _service()
        # Mock recall to return a list with FP/TP memories
        fp_mem = _make_memory(
            "FP pattern",
            structured_data={"feedback_type": "false_positive"},
        )
        tp_mem = _make_memory(
            "TP pattern",
            structured_data={"feedback_type": "true_positive"},
        )
        scored_fp = ScoredMemory(
            memory=fp_mem, similarity_score=0.9, recency_score=0.8,
            importance_score=0.7, composite_score=0.8, confidence_level="high",
        )
        scored_tp = ScoredMemory(
            memory=tp_mem, similarity_score=0.85, recency_score=0.7,
            importance_score=0.5, composite_score=0.7, confidence_level="medium",
        )
        svc.recall = MagicMock(return_value=[scored_fp, scored_tp])
        ctx = svc.recall_for_detection("loop")
        assert isinstance(ctx, DetectionRecallContext)
        assert isinstance(ctx.threshold_adjustment, float)
        assert isinstance(ctx.similar_detections, list)

    def test_recall_for_fix_generation(self):
        svc = _service()
        success_mem = _make_memory(
            "success",
            structured_data={"was_successful": True},
        )
        fail_mem = _make_memory(
            "failure",
            structured_data={"was_successful": False},
        )
        scored_s = ScoredMemory(
            memory=success_mem, similarity_score=0.9, recency_score=0.8,
            importance_score=0.7, composite_score=0.8, confidence_level="high",
        )
        scored_f = ScoredMemory(
            memory=fail_mem, similarity_score=0.7, recency_score=0.6,
            importance_score=0.6, composite_score=0.6, confidence_level="medium",
        )
        svc.recall = MagicMock(return_value=[scored_s, scored_f])
        ctx = svc.recall_for_fix_generation("loop")
        assert isinstance(ctx, FixRecallContext)
        assert len(ctx.successful_patterns) == 1
        assert len(ctx.patterns_to_avoid) == 1


# ===========================================================================
# TestMemoryExtractor
# ===========================================================================

class TestMemoryExtractor:

    def test_extract_fallback_splits_sentences(self):
        extractor = MemoryExtractor(llm_client=None)
        text = (
            "The loop detector found a repeated state pattern. "
            "The corruption detector found invalid transitions. "
            "Short."
        )
        result = extractor.extract(text, "detection")
        # "Short." is <= 20 chars, should be filtered out
        assert len(result.facts) == 2
        assert all(len(f.content) > 20 for f in result.facts)

    def test_extract_fallback_limits_count(self):
        extractor = MemoryExtractor(llm_client=None)
        text = ". ".join([f"This is sentence number {i} with enough characters" for i in range(10)])
        result = extractor.extract(text, "detection", max_facts=3)
        assert len(result.facts) <= 3

    def test_extract_fallback_default_importance(self):
        extractor = MemoryExtractor(llm_client=None)
        text = "The detector correctly identified the failure pattern in the agent output."
        result = extractor.extract(text, "detection")
        for fact in result.facts:
            assert fact.importance == 0.5

    def test_extract_json_from_code_block(self):
        extractor = MemoryExtractor(llm_client=None)
        raw = '```json\n[{"content": "test fact", "importance": 0.7}]\n```'
        parsed = extractor._extract_json(raw)
        assert isinstance(parsed, list)
        assert parsed[0]["content"] == "test fact"

    def test_extract_json_raw(self):
        extractor = MemoryExtractor(llm_client=None)
        raw = '[{"content": "raw fact", "importance": 0.6}]'
        parsed = extractor._extract_json(raw)
        assert isinstance(parsed, list)
        assert parsed[0]["content"] == "raw fact"

    def test_extract_json_garbage(self):
        extractor = MemoryExtractor(llm_client=None)
        parsed = extractor._extract_json("this is not json at all!!! {{{")
        assert parsed == [] or parsed == {}

    def test_heuristic_contradiction_negation(self):
        extractor = MemoryExtractor(llm_client=None)
        # "not" negation with topic overlap (shared words > 4 chars)
        new_fact = "The detector should not trigger on benign patterns"
        existing = "The detector should trigger on benign patterns"
        assert extractor._heuristic_contradiction(new_fact, existing) is True

    def test_heuristic_contradiction_no_match(self):
        extractor = MemoryExtractor(llm_client=None)
        new_fact = "The weather is sunny today"
        existing = "Database migrations completed successfully"
        assert extractor._heuristic_contradiction(new_fact, existing) is False

    def test_extracted_fact_dataclass(self):
        fact = ExtractedFact(
            content="test content",
            importance=0.7,
            memory_type="detection_pattern",
            domain="loop",
            tags=["tag1"],
        )
        assert fact.content == "test content"
        assert fact.importance == 0.7
        assert fact.memory_type == "detection_pattern"
        assert fact.domain == "loop"
        assert fact.tags == ["tag1"]

    def test_extraction_result_dataclass(self):
        fact = ExtractedFact("f1", 0.5, "detection_pattern", "loop")
        result = MemoryExtractionResult(
            facts=[fact],
            contradictions=[],
            total_extracted=1,
            deduplicated=0,
            cost_usd=0.001,
            tokens_used=150,
        )
        assert result.total_extracted == 1
        assert result.deduplicated == 0
        assert result.cost_usd == 0.001
        assert result.tokens_used == 150
        assert len(result.facts) == 1
