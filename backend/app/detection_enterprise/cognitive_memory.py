"""Cognitive Memory Service for PISAMA.

Implements the five cognitive operations — remember, recall, tree, forget,
and integration hooks — providing detection-aware memory that encodes
selectively, recalls with composite scoring, and forgets deliberately.

Memory recall uses a composite score blending vector similarity, temporal
recency, and importance weighting to surface the most relevant memories.
"""

import datetime
import hashlib
import logging
import math
import time
import uuid as uuid_mod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.storage.models import CognitiveMemory, MemoryRecallLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CompositeWeights:
    """Weights for the composite recall scorer."""

    similarity: float = 0.4
    recency: float = 0.2
    importance: float = 0.4


@dataclass
class ScoredMemory:
    """A memory annotated with composite scoring breakdown."""

    memory: CognitiveMemory
    similarity_score: float
    recency_score: float
    importance_score: float
    composite_score: float
    confidence_level: str  # "high" / "medium" / "low"


@dataclass
class DetectionRecallContext:
    """Context returned when recalling memories for a detection run."""

    threshold_adjustment: float
    similar_detections: List[ScoredMemory]
    framework_patterns: List[ScoredMemory]
    confidence_adjustment: float


@dataclass
class FixRecallContext:
    """Context returned when recalling memories for fix generation."""

    past_outcomes: List[ScoredMemory]
    successful_patterns: List[ScoredMemory]
    patterns_to_avoid: List[ScoredMemory]


# ---------------------------------------------------------------------------
# Composite scorer
# ---------------------------------------------------------------------------

class CompositeScorer:
    """Scores a memory candidate using similarity, recency, and importance."""

    RECENCY_HALF_LIFE_DAYS = 90

    def __init__(self, weights: Optional[CompositeWeights] = None):
        self.weights = weights or CompositeWeights()

    def score(
        self,
        similarity: float,
        created_at: datetime.datetime,
        importance: float,
        access_count: int,
    ) -> float:
        """Compute a composite score in [0, 1] (approximately).

        Args:
            similarity: Cosine similarity between query and memory (0-1).
            created_at: When the memory was created.
            importance: Stored importance weight (0-1).
            access_count: How many times the memory has been recalled.

        Returns:
            Composite score combining all factors.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=datetime.timezone.utc)
        days_since = max(0.0, (now - created_at).total_seconds() / 86400)

        recency = math.exp(-days_since / self.RECENCY_HALF_LIFE_DAYS)

        weighted = (
            similarity * self.weights.similarity
            + recency * self.weights.recency
            + importance * self.weights.importance
        )

        # Small bonus for frequently accessed memories
        bonus = min(0.05, math.log(1 + access_count) * 0.02)
        return weighted + bonus


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class CognitiveMemoryService:
    """Core cognitive memory service.

    Provides remember / recall / tree / forget operations plus thin
    integration hooks for detection, feedback, calibration, and fix outcomes.
    """

    def __init__(
        self,
        session: Session,
        tenant_id: uuid_mod.UUID,
        embedder=None,
        llm_client=None,
    ):
        """Initialise the service.

        Args:
            session: SQLAlchemy Session (synchronous).
            tenant_id: Tenant UUID for row-level isolation.
            embedder: Optional callable/object with an ``embed(text) -> List[float]``
                method.  When *None*, embedding-based operations are skipped.
            llm_client: Optional Anthropic client.  When *None*, importance
                scoring falls back to a static default.
        """
        self.session = session
        self.tenant_id = tenant_id
        self.embedder = embedder
        self.llm_client = llm_client
        self.scorer = CompositeScorer()

    # ------------------------------------------------------------------
    # remember
    # ------------------------------------------------------------------

    def remember(
        self,
        content: str,
        memory_type: str,
        domain: str,
        source_type: str,
        source_id: Optional[uuid_mod.UUID] = None,
        source_trace_id: Optional[uuid_mod.UUID] = None,
        structured_data: Optional[Dict[str, Any]] = None,
        importance: Optional[float] = None,
        tags: Optional[List[str]] = None,
        framework: Optional[str] = None,
    ) -> CognitiveMemory:
        """Encode a new memory, de-duplicating and resolving contradictions.

        Args:
            content: Free-text content to store.
            memory_type: Classification tag (e.g. ``detection_pattern``).
            domain: Logical domain (e.g. ``loop``, ``corruption``).
            source_type: Origin system (e.g. ``detection``, ``calibration``).
            source_id: Optional source entity UUID.
            source_trace_id: Optional trace UUID for provenance.
            structured_data: Optional JSON-serialisable metadata.
            importance: Manual importance (0-1).  Scored by LLM when *None*.
            tags: Optional list of string tags.
            framework: Optional framework identifier.

        Returns:
            The existing or newly created ``CognitiveMemory`` record.
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # --- exact-hash dedup ------------------------------------------
        existing = (
            self.session.query(CognitiveMemory)
            .filter(
                CognitiveMemory.tenant_id == self.tenant_id,
                CognitiveMemory.content_hash == content_hash,
                CognitiveMemory.is_active.is_(True),
            )
            .first()
        )
        if existing is not None:
            logger.debug("Exact hash dedup hit for %s", content_hash[:12])
            return existing

        # --- embedding -------------------------------------------------
        embedding = None
        if self.embedder is not None:
            try:
                embedding = self.embedder.embed(content)
            except Exception:
                logger.warning("Embedding failed; continuing without vector", exc_info=True)

        # --- near-duplicate check (cosine > 0.95) ----------------------
        if embedding is not None:
            near_dup = self._find_near_duplicate(embedding)
            if near_dup is not None:
                logger.debug("Near-duplicate (cosine > 0.95) found: %s", near_dup.id)
                return near_dup

        # --- importance scoring ----------------------------------------
        if importance is None:
            importance = self._score_importance(content, memory_type, domain)

        # --- contradiction detection & supersession --------------------
        supersedes_id = None
        contradicted = None
        if embedding is not None:
            contradicted = self._find_contradiction(embedding, domain, structured_data)
            if contradicted is not None:
                supersedes_id = contradicted.id
                contradicted.is_active = False
                logger.info(
                    "Memory %s superseded by new entry (contradiction in %s)",
                    contradicted.id, domain,
                )

        # --- create record ---------------------------------------------
        mem = CognitiveMemory(
            id=uuid_mod.uuid4(),
            tenant_id=self.tenant_id,
            memory_type=memory_type,
            domain=domain,
            content=content,
            content_hash=content_hash,
            structured_data=structured_data or {},
            source_type=source_type,
            source_id=source_id,
            source_trace_id=source_trace_id,
            importance=importance,
            confidence=importance,  # initial confidence mirrors importance
            access_count=0,
            is_active=True,
            embedding=embedding,
            tags=tags or [],
            framework=framework,
            supersedes_id=supersedes_id,
        )
        self.session.add(mem)

        # Link the superseded memory back to the new one
        if contradicted is not None:
            self.session.flush()  # ensure mem.id is populated
            contradicted.superseded_by_id = mem.id

        self.session.flush()
        return mem

    # ------------------------------------------------------------------
    # recall
    # ------------------------------------------------------------------

    def recall(
        self,
        query: str,
        domain: Optional[str] = None,
        memory_type: Optional[str] = None,
        framework: Optional[str] = None,
        k: int = 5,
        min_confidence: float = 0.3,
        weights: Optional[CompositeWeights] = None,
        recall_context: str = "general",
    ) -> List[ScoredMemory]:
        """Recall the most relevant memories for *query*.

        Combines vector similarity (when available) with recency and
        importance to produce a composite-ranked result set.

        Args:
            query: Natural-language recall query.
            domain: Optional domain filter.
            memory_type: Optional memory_type filter.
            framework: Optional framework filter.
            k: Maximum number of memories to return.
            min_confidence: Minimum composite score to include.
            weights: Custom composite weights.
            recall_context: Label for the recall log.

        Returns:
            Sorted list of ``ScoredMemory`` (descending composite score).
        """
        t0 = time.time()
        scorer = CompositeScorer(weights) if weights else self.scorer

        # --- embed the query -------------------------------------------
        query_embedding = None
        if self.embedder is not None:
            try:
                query_embedding = self.embedder.embed(query)
            except Exception:
                logger.warning("Query embedding failed; falling back to text search", exc_info=True)

        # --- candidate retrieval ---------------------------------------
        candidates = self._retrieve_candidates(
            query, query_embedding, domain, memory_type, framework, limit=50,
        )

        # --- composite scoring -----------------------------------------
        scored: List[ScoredMemory] = []
        for mem, sim in candidates:
            composite = scorer.score(sim, mem.created_at, mem.importance, mem.access_count)
            if composite >= min_confidence:
                scored.append(ScoredMemory(
                    memory=mem,
                    similarity_score=sim,
                    recency_score=0.0,  # filled below
                    importance_score=mem.importance,
                    composite_score=composite,
                    confidence_level="",
                ))

        # --- adaptive expansion ----------------------------------------
        if (
            query_embedding is not None
            and (not scored or scored[0].composite_score < 0.5)
        ):
            extra = self._retrieve_candidates(
                query, query_embedding, domain, memory_type, framework, limit=100,
            )
            seen_ids = {s.memory.id for s in scored}
            for mem, sim in extra:
                if mem.id in seen_ids:
                    continue
                composite = scorer.score(sim, mem.created_at, mem.importance, mem.access_count)
                if composite >= min_confidence:
                    scored.append(ScoredMemory(
                        memory=mem,
                        similarity_score=sim,
                        recency_score=0.0,
                        importance_score=mem.importance,
                        composite_score=composite,
                        confidence_level="",
                    ))

        # --- sort, slice, annotate -------------------------------------
        scored.sort(key=lambda s: s.composite_score, reverse=True)
        scored = scored[:k]

        for sm in scored:
            sm.confidence_level = (
                "high" if sm.composite_score >= 0.7
                else "medium" if sm.composite_score >= 0.5
                else "low"
            )

        # --- update access metadata ------------------------------------
        now = datetime.datetime.now(datetime.timezone.utc)
        for sm in scored:
            sm.memory.access_count = (sm.memory.access_count or 0) + 1
            sm.memory.last_accessed_at = now

        # --- recall log ------------------------------------------------
        latency_ms = int((time.time() - t0) * 1000)
        self._log_recall(query, domain, recall_context, scored, latency_ms)

        return scored

    # ------------------------------------------------------------------
    # tree
    # ------------------------------------------------------------------

    def tree(
        self,
        max_depth: int = 3,
        include_inactive: bool = False,
    ) -> Dict[str, Any]:
        """Return a nested overview of memories grouped by type and domain.

        Args:
            max_depth: Reserved for future hierarchical depth control.
            include_inactive: Include deactivated (superseded / forgotten) memories.

        Returns:
            ``{type: {domain: {count, avg_importance, memories: [...]}}}``
        """
        q = self.session.query(CognitiveMemory).filter(
            CognitiveMemory.tenant_id == self.tenant_id,
        )
        if not include_inactive:
            q = q.filter(CognitiveMemory.is_active.is_(True))

        result: Dict[str, Any] = {}
        for mem in q.all():
            mtype = mem.memory_type or "unknown"
            dom = mem.domain or "unknown"
            bucket = result.setdefault(mtype, {}).setdefault(dom, {
                "count": 0,
                "avg_importance": 0.0,
                "memories": [],
            })
            bucket["count"] += 1
            bucket["memories"].append({
                "id": str(mem.id),
                "content": mem.content[:120],
                "importance": mem.importance,
                "created_at": str(mem.created_at),
                "is_active": mem.is_active,
            })

        # Compute averages
        for mtype_dict in result.values():
            for bucket in mtype_dict.values():
                if bucket["count"] > 0:
                    total_imp = sum(m["importance"] for m in bucket["memories"])
                    bucket["avg_importance"] = round(total_imp / bucket["count"], 3)

        return result

    # ------------------------------------------------------------------
    # forget
    # ------------------------------------------------------------------

    def forget(
        self,
        memory_id: Optional[uuid_mod.UUID] = None,
        domain: Optional[str] = None,
        older_than_days: Optional[int] = None,
        importance_below: Optional[float] = None,
        reason: str = "manual",
    ) -> Dict[str, Any]:
        """Deactivate memories matching the given criteria.

        At least one filtering parameter must be supplied.

        Args:
            memory_id: Forget a single memory by ID.
            domain: Forget all active memories in this domain.
            older_than_days: Forget memories older than N days.
            importance_below: Forget memories with importance below this value.
            reason: Human-readable reason for the forget operation.

        Returns:
            ``{deactivated_count: int, reason: str}``
        """
        q = self.session.query(CognitiveMemory).filter(
            CognitiveMemory.tenant_id == self.tenant_id,
            CognitiveMemory.is_active.is_(True),
        )

        if memory_id is not None:
            q = q.filter(CognitiveMemory.id == memory_id)
        if domain is not None:
            q = q.filter(CognitiveMemory.domain == domain)
        if older_than_days is not None:
            cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=older_than_days)
            q = q.filter(CognitiveMemory.created_at < cutoff)
        if importance_below is not None:
            q = q.filter(CognitiveMemory.importance < importance_below)

        # Guard: require at least one filter
        if all(v is None for v in [memory_id, domain, older_than_days, importance_below]):
            return {"deactivated_count": 0, "reason": "no filter criteria provided"}

        memories = q.all()
        for mem in memories:
            mem.is_active = False

        count = len(memories)
        logger.info("Forgot %d memories (reason=%s)", count, reason)
        return {"deactivated_count": count, "reason": reason}

    # ------------------------------------------------------------------
    # Integration hooks
    # ------------------------------------------------------------------

    def remember_detection(
        self,
        detection_type: str,
        confidence: float,
        method: str,
        details: str,
        trace_id: Optional[uuid_mod.UUID] = None,
        framework: Optional[str] = None,
    ) -> CognitiveMemory:
        """Store a detection event as a memory.

        Args:
            detection_type: Type of detection (e.g. ``loop``, ``corruption``).
            confidence: Detection confidence (0-1).
            method: Detection method used.
            details: Free-text description of the detection.
            trace_id: Optional trace UUID.
            framework: Optional framework identifier.

        Returns:
            The stored ``CognitiveMemory`` record.
        """
        content = (
            f"Detection: {detection_type} found with confidence "
            f"{confidence} using {method}."
        )
        return self.remember(
            content=content,
            memory_type="detection_pattern",
            domain=detection_type,
            source_type="detection",
            source_trace_id=trace_id,
            structured_data={
                "detection_type": detection_type,
                "confidence": confidence,
                "method": method,
                "details": details,
            },
            importance=min(1.0, confidence * 0.8 + 0.2),
            framework=framework,
        )

    def remember_feedback(
        self,
        detection_type: str,
        is_correct: bool,
        feedback_type: str,
        confidence: float,
        framework: Optional[str] = None,
    ) -> CognitiveMemory:
        """Store user/system feedback on a detection as a memory.

        Args:
            detection_type: The detection type the feedback applies to.
            is_correct: Whether the original detection was correct.
            feedback_type: ``true_positive``, ``false_positive``, etc.
            confidence: Confidence of the feedback.
            framework: Optional framework identifier.

        Returns:
            The stored ``CognitiveMemory`` record.
        """
        if not is_correct:
            content = (
                f"False positive: {detection_type} was wrongly flagged "
                f"({feedback_type}) with confidence {confidence}."
            )
            importance = 0.8
        else:
            content = (
                f"True positive reinforcement: {detection_type} correctly "
                f"detected ({feedback_type}) with confidence {confidence}."
            )
            importance = 0.5

        return self.remember(
            content=content,
            memory_type="feedback",
            domain=detection_type,
            source_type="feedback",
            structured_data={
                "detection_type": detection_type,
                "is_correct": is_correct,
                "feedback_type": feedback_type,
                "confidence": confidence,
            },
            importance=importance,
            framework=framework,
        )

    def remember_calibration(
        self,
        detector_name: str,
        f1_score: float,
        f1_delta: float,
        threshold: float,
    ) -> CognitiveMemory:
        """Store calibration results as a memory.

        Args:
            detector_name: Name of the detector.
            f1_score: Achieved F1 score.
            f1_delta: Change in F1 from previous calibration.
            threshold: Optimal threshold found.

        Returns:
            The stored ``CognitiveMemory`` record.
        """
        direction = "improved" if f1_delta >= 0 else "regressed"
        content = (
            f"Calibration: {detector_name} achieved F1={f1_score:.3f} "
            f"(delta={f1_delta:+.3f}, {direction}) at threshold={threshold:.3f}."
        )
        return self.remember(
            content=content,
            memory_type="threshold_learning",
            domain=detector_name,
            source_type="calibration",
            structured_data={
                "detector_name": detector_name,
                "f1_score": f1_score,
                "f1_delta": f1_delta,
                "threshold": threshold,
            },
            importance=min(1.0, 0.4 + abs(f1_delta) * 2),
        )

    def remember_fix_outcome(
        self,
        detection_type: str,
        fix_type: str,
        was_successful: bool,
        framework: Optional[str] = None,
    ) -> CognitiveMemory:
        """Store the outcome of an applied fix as a memory.

        Args:
            detection_type: The detection type the fix addressed.
            fix_type: Description of the fix applied.
            was_successful: Whether the fix resolved the issue.
            framework: Optional framework identifier.

        Returns:
            The stored ``CognitiveMemory`` record.
        """
        outcome = "succeeded" if was_successful else "failed"
        content = (
            f"Fix outcome: {fix_type} for {detection_type} {outcome}."
        )
        return self.remember(
            content=content,
            memory_type="fix_outcome",
            domain=detection_type,
            source_type="fix",
            structured_data={
                "detection_type": detection_type,
                "fix_type": fix_type,
                "was_successful": was_successful,
            },
            importance=0.7 if was_successful else 0.6,
            framework=framework,
        )

    def recall_for_detection(
        self,
        detection_type: str,
        trace_context: str = "",
        framework: Optional[str] = None,
    ) -> DetectionRecallContext:
        """Recall memories relevant to running a detection.

        Computes a threshold adjustment based on false-positive history
        and returns similar past detections and framework-specific patterns.

        Args:
            detection_type: The detection type being run.
            trace_context: Optional trace context for the recall query.
            framework: Optional framework filter.

        Returns:
            ``DetectionRecallContext`` with adjustment parameters.
        """
        query = f"Detection patterns for {detection_type}"
        if trace_context:
            query += f": {trace_context}"

        similar = self.recall(
            query=query,
            domain=detection_type,
            k=10,
            min_confidence=0.2,
            recall_context="detection_recall",
        )

        framework_patterns: List[ScoredMemory] = []
        if framework:
            framework_patterns = self.recall(
                query=f"Framework patterns for {framework} {detection_type}",
                domain=detection_type,
                framework=framework,
                k=5,
                min_confidence=0.2,
                recall_context="framework_recall",
            )

        # Compute threshold adjustment from false-positive patterns
        fp_count = 0
        tp_count = 0
        for sm in similar:
            sd = sm.memory.structured_data or {}
            if sd.get("feedback_type") == "false_positive":
                fp_count += 1
            elif sd.get("feedback_type") == "true_positive":
                tp_count += 1

        # Raise threshold if many FPs seen; lower if mostly TPs
        threshold_adjustment = 0.0
        total = fp_count + tp_count
        if total >= 3:
            fp_rate = fp_count / total
            threshold_adjustment = (fp_rate - 0.5) * 0.1  # [-0.05, +0.05]

        # Confidence adjustment: boost confidence when many confirmed TPs
        confidence_adjustment = 0.0
        if tp_count >= 5:
            confidence_adjustment = min(0.05, tp_count * 0.005)

        return DetectionRecallContext(
            threshold_adjustment=round(threshold_adjustment, 4),
            similar_detections=similar,
            framework_patterns=framework_patterns,
            confidence_adjustment=round(confidence_adjustment, 4),
        )

    def recall_for_fix_generation(
        self,
        detection_type: str,
        detection_details: Optional[str] = None,
        framework: Optional[str] = None,
    ) -> FixRecallContext:
        """Recall memories relevant to generating a fix.

        Returns past fix outcomes grouped by success/failure to inform
        the fix generator about what has worked before.

        Args:
            detection_type: Detection type needing a fix.
            detection_details: Optional details about the detection.
            framework: Optional framework filter.

        Returns:
            ``FixRecallContext`` with past outcomes and pattern guidance.
        """
        query = f"Fix outcomes for {detection_type}"
        if detection_details:
            query += f": {detection_details}"

        past = self.recall(
            query=query,
            memory_type="fix_outcome",
            domain=detection_type,
            framework=framework,
            k=10,
            min_confidence=0.2,
            recall_context="fix_generation",
        )

        successful = [
            sm for sm in past
            if (sm.memory.structured_data or {}).get("was_successful") is True
        ]
        to_avoid = [
            sm for sm in past
            if (sm.memory.structured_data or {}).get("was_successful") is False
        ]

        return FixRecallContext(
            past_outcomes=past,
            successful_patterns=successful,
            patterns_to_avoid=to_avoid,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_near_duplicate(self, embedding: List[float]) -> Optional[CognitiveMemory]:
        """Find an active memory with cosine similarity > 0.95."""
        vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"
        sql = text("""
            SELECT id
            FROM cognitive_memories
            WHERE tenant_id = :tid
              AND is_active = true
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> :vec ::vector) > 0.95
            ORDER BY embedding <=> :vec ::vector
            LIMIT 1
        """)
        row = self.session.execute(sql, {"tid": self.tenant_id, "vec": vec_literal}).fetchone()
        if row is None:
            return None
        return self.session.query(CognitiveMemory).get(row[0])

    def _find_contradiction(
        self,
        embedding: List[float],
        domain: str,
        structured_data: Optional[Dict[str, Any]],
    ) -> Optional[CognitiveMemory]:
        """Find an active memory in the same domain with cosine sim > 0.8
        that contradicts the incoming structured data."""
        if not structured_data:
            return None

        vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"
        sql = text("""
            SELECT id, structured_data
            FROM cognitive_memories
            WHERE tenant_id = :tid
              AND domain = :domain
              AND is_active = true
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> :vec ::vector) > 0.8
            ORDER BY embedding <=> :vec ::vector
            LIMIT 5
        """)
        rows = self.session.execute(
            sql, {"tid": self.tenant_id, "domain": domain, "vec": vec_literal},
        ).fetchall()

        for row in rows:
            old_data = row[1] or {}
            if self._has_opposing_values(old_data, structured_data):
                return self.session.query(CognitiveMemory).get(row[0])

        return None

    @staticmethod
    def _has_opposing_values(old: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """Simple heuristic: two dicts contradict if they share a key
        whose values are different and both non-None."""
        for key in set(old) & set(new):
            if key in ("details", "content", "method"):
                continue  # skip free-text fields
            v_old, v_new = old[key], new[key]
            if v_old is not None and v_new is not None and v_old != v_new:
                return True
        return False

    def _score_importance(self, content: str, memory_type: str, domain: str) -> float:
        """Score importance using the LLM client, or return a default."""
        if self.llm_client is None:
            return 0.5

        try:
            response = self.llm_client.messages.create(
                model="claude-haiku-4-20250514",
                max_tokens=16,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Rate the importance (0.0 to 1.0) of remembering this "
                        f"observation for an AI testing platform.\n"
                        f"Type: {memory_type}, Domain: {domain}\n"
                        f"Content: {content[:500]}\n"
                        f"Reply with ONLY a decimal number."
                    ),
                }],
            )
            text_resp = response.content[0].text.strip()
            score = float(text_resp)
            return max(0.0, min(1.0, score))
        except Exception:
            logger.warning("LLM importance scoring failed; defaulting to 0.5", exc_info=True)
            return 0.5

    def _retrieve_candidates(
        self,
        query: str,
        query_embedding: Optional[List[float]],
        domain: Optional[str],
        memory_type: Optional[str],
        framework: Optional[str],
        limit: int = 50,
    ) -> List[tuple]:
        """Retrieve candidate (memory, similarity) pairs.

        Uses pgvector cosine search when an embedding is available,
        falling back to ILIKE text search otherwise.

        Returns:
            List of ``(CognitiveMemory, similarity_float)`` tuples.
        """
        if query_embedding is not None:
            return self._vector_search(
                query_embedding, domain, memory_type, framework, limit,
            )
        return self._text_search(query, domain, memory_type, framework, limit)

    def _vector_search(
        self,
        embedding: List[float],
        domain: Optional[str],
        memory_type: Optional[str],
        framework: Optional[str],
        limit: int,
    ) -> List[tuple]:
        """pgvector cosine similarity search."""
        vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"

        where_clauses = [
            "tenant_id = :tid",
            "is_active = true",
            "embedding IS NOT NULL",
        ]
        params: Dict[str, Any] = {"tid": self.tenant_id, "vec": vec_literal, "lim": limit}

        if domain is not None:
            where_clauses.append("domain = :domain")
            params["domain"] = domain
        if memory_type is not None:
            where_clauses.append("memory_type = :mtype")
            params["mtype"] = memory_type
        if framework is not None:
            where_clauses.append("framework = :fw")
            params["fw"] = framework

        where = " AND ".join(where_clauses)
        sql = text(f"""
            SELECT id, 1 - (embedding <=> :vec ::vector) AS similarity
            FROM cognitive_memories
            WHERE {where}
            ORDER BY embedding <=> :vec ::vector
            LIMIT :lim
        """)

        rows = self.session.execute(sql, params).fetchall()
        results = []
        for row in rows:
            mem = self.session.query(CognitiveMemory).get(row[0])
            if mem is not None:
                results.append((mem, float(row[1])))
        return results

    def _text_search(
        self,
        query: str,
        domain: Optional[str],
        memory_type: Optional[str],
        framework: Optional[str],
        limit: int,
    ) -> List[tuple]:
        """Fallback ILIKE text search when no embeddings are available."""
        q = self.session.query(CognitiveMemory).filter(
            CognitiveMemory.tenant_id == self.tenant_id,
            CognitiveMemory.is_active.is_(True),
        )
        if domain is not None:
            q = q.filter(CognitiveMemory.domain == domain)
        if memory_type is not None:
            q = q.filter(CognitiveMemory.memory_type == memory_type)
        if framework is not None:
            q = q.filter(CognitiveMemory.framework == framework)

        # Simple keyword matching: split query and match any word
        keywords = [w for w in query.split() if len(w) > 2]
        if keywords:
            from sqlalchemy import or_
            filters = [CognitiveMemory.content.ilike(f"%{kw}%") for kw in keywords[:5]]
            q = q.filter(or_(*filters))

        q = q.order_by(CognitiveMemory.importance.desc(), CognitiveMemory.created_at.desc())
        memories = q.limit(limit).all()

        # Assign a synthetic similarity based on keyword overlap
        results = []
        query_lower = query.lower()
        for mem in memories:
            content_lower = (mem.content or "").lower()
            matched = sum(1 for kw in keywords if kw.lower() in content_lower)
            sim = matched / max(len(keywords), 1)
            results.append((mem, sim))
        return results

    def _log_recall(
        self,
        query: str,
        domain: Optional[str],
        recall_context: str,
        scored: List[ScoredMemory],
        latency_ms: int,
    ) -> None:
        """Write a recall audit log entry."""
        try:
            log = MemoryRecallLog(
                id=uuid_mod.uuid4(),
                tenant_id=self.tenant_id,
                recall_context=recall_context,
                recall_query=query[:2000],
                domain_filter=domain,
                memories_returned=len(scored),
                top_memory_id=scored[0].memory.id if scored else None,
                composite_scores=[
                    {"id": str(sm.memory.id), "score": round(sm.composite_score, 4)}
                    for sm in scored
                ],
                latency_ms=latency_ms,
            )
            self.session.add(log)
            self.session.flush()
        except Exception:
            logger.warning("Failed to write recall log", exc_info=True)
