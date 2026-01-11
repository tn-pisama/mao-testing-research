"""
RAG Retrieval Service for MAST Failure Detection
=================================================

Provides dynamic few-shot example retrieval from the failure_examples table
using pgvector similarity search. Used by MASTLLMJudge for improved accuracy.

Key features:
- Per-failure-mode example retrieval
- Balanced positive/negative examples
- Similarity-weighted example selection
- In-memory caching for frequently accessed examples
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RetrievedExample:
    """A single retrieved failure example."""
    id: str
    failure_mode: str
    is_failure: bool
    task_description: str
    conversation_summary: str
    key_events: List[str]
    similarity: float
    framework: Optional[str] = None
    confidence: int = 100


class FailureExampleRetriever:
    """
    Retrieves similar failure examples for RAG-augmented detection.

    Uses pgvector for similarity search to find relevant examples
    from the failure_examples table, providing few-shot context
    for the LLM judge.

    Usage:
        retriever = FailureExampleRetriever(session)
        examples = retriever.retrieve(
            failure_mode="F1",
            query_embedding=embedding,
            k=3
        )
    """

    def __init__(
        self,
        session=None,
        embedding_service=None,
        cache_enabled: bool = True,
    ):
        """
        Initialize the retriever.

        Args:
            session: SQLAlchemy async session (optional, can be set per call)
            embedding_service: EmbeddingService instance (lazy loaded if None)
            cache_enabled: Whether to cache embeddings in memory
        """
        self._session = session
        self._embedding_service = embedding_service
        self._cache_enabled = cache_enabled
        self._embedding_cache: Dict[str, np.ndarray] = {}

    @property
    def embedder(self):
        """Lazy load embedding service."""
        if self._embedding_service is None:
            from app.core.embeddings import get_embedder
            self._embedding_service = get_embedder()
        return self._embedding_service

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text, using cache if enabled."""
        if self._cache_enabled:
            cache_key = text[:200]  # Use prefix as cache key
            if cache_key in self._embedding_cache:
                return self._embedding_cache[cache_key]

        embedding = self.embedder.encode_query(text)

        if self._cache_enabled and len(self._embedding_cache) < 1000:
            self._embedding_cache[cache_key] = embedding

        return embedding

    async def retrieve(
        self,
        failure_mode: str,
        query_text: str,
        query_embedding: Optional[np.ndarray] = None,
        k: int = 3,
        include_healthy: bool = True,
        session=None,
    ) -> List[RetrievedExample]:
        """
        Retrieve similar examples for a failure mode.

        Args:
            failure_mode: MAST failure mode (e.g., "F1", "F6")
            query_text: Text to embed for similarity search
            query_embedding: Pre-computed embedding (optional)
            k: Number of examples to retrieve per category
            include_healthy: Include healthy (non-failure) examples
            session: SQLAlchemy session (overrides instance session)

        Returns:
            List of RetrievedExample objects, sorted by relevance
        """
        from sqlalchemy import select, text
        from app.storage.models import FailureExample

        db_session = session or self._session
        if db_session is None:
            logger.warning("No database session provided, returning empty results")
            return []

        # Get or compute embedding
        if query_embedding is None:
            query_embedding = self._get_embedding(query_text)

        # Convert to list for SQL
        embedding_list = query_embedding.tolist()

        examples = []

        # Retrieve failure examples (positive)
        failure_examples = await self._query_similar(
            db_session,
            failure_mode=failure_mode,
            is_failure=True,
            embedding=embedding_list,
            limit=k,
        )
        examples.extend(failure_examples)

        # Retrieve healthy examples (negative) for contrast
        if include_healthy:
            healthy_examples = await self._query_similar(
                db_session,
                failure_mode=failure_mode,
                is_failure=False,
                embedding=embedding_list,
                limit=k,
            )
            examples.extend(healthy_examples)

        # Sort by similarity
        examples.sort(key=lambda x: x.similarity, reverse=True)

        return examples

    async def _query_similar(
        self,
        session,
        failure_mode: str,
        is_failure: bool,
        embedding: List[float],
        limit: int,
    ) -> List[RetrievedExample]:
        """Query similar examples from database using pgvector."""
        from sqlalchemy import select, text, cast
        from sqlalchemy.dialects.postgresql import ARRAY
        from pgvector.sqlalchemy import Vector
        from app.storage.models import FailureExample

        try:
            # Use raw SQL for pgvector distance query
            # cosine distance: 1 - (embedding <=> query_embedding)
            query = text("""
                SELECT
                    id::text,
                    failure_mode,
                    is_failure,
                    task_description,
                    conversation_summary,
                    key_events,
                    framework,
                    confidence,
                    1 - (embedding <=> :query_embedding::vector) as similarity
                FROM failure_examples
                WHERE failure_mode = :failure_mode
                  AND is_failure = :is_failure
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> :query_embedding::vector
                LIMIT :limit
            """)

            result = await session.execute(
                query,
                {
                    "failure_mode": failure_mode,
                    "is_failure": is_failure,
                    "query_embedding": str(embedding),
                    "limit": limit,
                }
            )

            rows = result.fetchall()

            examples = []
            for row in rows:
                examples.append(RetrievedExample(
                    id=row.id,
                    failure_mode=row.failure_mode,
                    is_failure=row.is_failure,
                    task_description=row.task_description,
                    conversation_summary=row.conversation_summary,
                    key_events=row.key_events or [],
                    framework=row.framework,
                    confidence=row.confidence or 100,
                    similarity=float(row.similarity) if row.similarity else 0.0,
                ))

            return examples

        except Exception as e:
            logger.error(f"Error querying similar examples: {e}")
            return []

    def retrieve_sync(
        self,
        failure_mode: str,
        query_text: str,
        query_embedding: Optional[np.ndarray] = None,
        k: int = 3,
        include_healthy: bool = True,
        session=None,
    ) -> List[RetrievedExample]:
        """
        Synchronous version of retrieve() for non-async contexts.

        Uses direct SQL query without async session.
        """
        import sqlalchemy
        from sqlalchemy import create_engine, text

        db_session = session or self._session
        if db_session is None:
            logger.warning("No database session provided, returning empty results")
            return []

        # Get or compute embedding
        if query_embedding is None:
            query_embedding = self._get_embedding(query_text)

        embedding_list = query_embedding.tolist()

        examples = []

        # Query failures
        failure_examples = self._query_similar_sync(
            db_session,
            failure_mode=failure_mode,
            is_failure=True,
            embedding=embedding_list,
            limit=k,
        )
        examples.extend(failure_examples)

        # Query healthy examples
        if include_healthy:
            healthy_examples = self._query_similar_sync(
                db_session,
                failure_mode=failure_mode,
                is_failure=False,
                embedding=embedding_list,
                limit=k,
            )
            examples.extend(healthy_examples)

        examples.sort(key=lambda x: x.similarity, reverse=True)
        return examples

    def _query_similar_sync(
        self,
        session,
        failure_mode: str,
        is_failure: bool,
        embedding: List[float],
        limit: int,
    ) -> List[RetrievedExample]:
        """Synchronous query for similar examples."""
        from sqlalchemy import text

        try:
            query = text("""
                SELECT
                    id::text,
                    failure_mode,
                    is_failure,
                    task_description,
                    conversation_summary,
                    key_events,
                    framework,
                    confidence,
                    1 - (embedding <=> :query_embedding::vector) as similarity
                FROM failure_examples
                WHERE failure_mode = :failure_mode
                  AND is_failure = :is_failure
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> :query_embedding::vector
                LIMIT :limit
            """)

            result = session.execute(
                query,
                {
                    "failure_mode": failure_mode,
                    "is_failure": is_failure,
                    "query_embedding": str(embedding),
                    "limit": limit,
                }
            )

            rows = result.fetchall()

            examples = []
            for row in rows:
                examples.append(RetrievedExample(
                    id=row.id,
                    failure_mode=row.failure_mode,
                    is_failure=row.is_failure,
                    task_description=row.task_description,
                    conversation_summary=row.conversation_summary,
                    key_events=row.key_events or [],
                    framework=row.framework,
                    confidence=row.confidence or 100,
                    similarity=float(row.similarity) if row.similarity else 0.0,
                ))

            return examples

        except Exception as e:
            logger.error(f"Error querying similar examples (sync): {e}")
            return []

    async def retrieve_contrastive(
        self,
        failure_mode: str,
        query_text: str,
        k_positive: int = 3,
        k_negative: int = 2,
        k_hard_negative: int = 1,
        session=None,
    ) -> Dict[str, List[RetrievedExample]]:
        """
        Retrieve contrastive examples for few-shot learning.

        Returns positive (failure) examples, negative (healthy) examples,
        and hard negatives (similar but not failures) for better calibration.

        Args:
            failure_mode: MAST failure mode (e.g., "F1", "F6")
            query_text: Text to embed for similarity search
            k_positive: Number of failure examples to retrieve
            k_negative: Number of healthy examples to retrieve
            k_hard_negative: Number of hard negative examples (similar non-failures)
            session: SQLAlchemy session

        Returns:
            Dict with keys: "positives", "negatives", "hard_negatives"
        """
        from sqlalchemy import text

        db_session = session or self._session
        if db_session is None:
            logger.warning("No database session provided, returning empty results")
            return {"positives": [], "negatives": [], "hard_negatives": []}

        # Get embedding
        query_embedding = self._get_embedding(query_text)
        embedding_list = query_embedding.tolist()

        # Get similar positive examples (failures)
        positives = await self._query_similar(
            db_session,
            failure_mode=failure_mode,
            is_failure=True,
            embedding=embedding_list,
            limit=k_positive,
        )

        # Get similar negative examples (healthy)
        negatives = await self._query_similar(
            db_session,
            failure_mode=failure_mode,
            is_failure=False,
            embedding=embedding_list,
            limit=k_negative,
        )

        # Get hard negatives (very similar non-failures with min_similarity)
        hard_negatives = await self._query_similar_with_threshold(
            db_session,
            failure_mode=failure_mode,
            is_failure=False,
            embedding=embedding_list,
            limit=k_hard_negative,
            min_similarity=0.7,
        )

        return {
            "positives": positives,
            "negatives": negatives,
            "hard_negatives": hard_negatives,
        }

    async def _query_similar_with_threshold(
        self,
        session,
        failure_mode: str,
        is_failure: bool,
        embedding: List[float],
        limit: int,
        min_similarity: float = 0.0,
    ) -> List[RetrievedExample]:
        """Query similar examples with minimum similarity threshold."""
        from sqlalchemy import text

        try:
            query = text("""
                SELECT
                    id::text,
                    failure_mode,
                    is_failure,
                    task_description,
                    conversation_summary,
                    key_events,
                    framework,
                    confidence,
                    1 - (embedding <=> :query_embedding::vector) as similarity
                FROM failure_examples
                WHERE failure_mode = :failure_mode
                  AND is_failure = :is_failure
                  AND embedding IS NOT NULL
                  AND 1 - (embedding <=> :query_embedding::vector) >= :min_similarity
                ORDER BY embedding <=> :query_embedding::vector
                LIMIT :limit
            """)

            result = await session.execute(
                query,
                {
                    "failure_mode": failure_mode,
                    "is_failure": is_failure,
                    "query_embedding": str(embedding),
                    "limit": limit,
                    "min_similarity": min_similarity,
                }
            )

            rows = result.fetchall()

            examples = []
            for row in rows:
                examples.append(RetrievedExample(
                    id=row.id,
                    failure_mode=row.failure_mode,
                    is_failure=row.is_failure,
                    task_description=row.task_description,
                    conversation_summary=row.conversation_summary,
                    key_events=row.key_events or [],
                    framework=row.framework,
                    confidence=row.confidence or 100,
                    similarity=float(row.similarity) if row.similarity else 0.0,
                ))

            return examples

        except Exception as e:
            logger.error(f"Error querying similar examples with threshold: {e}")
            return []

    def retrieve_contrastive_sync(
        self,
        failure_mode: str,
        query_text: str,
        k_positive: int = 3,
        k_negative: int = 2,
        k_hard_negative: int = 1,
        session=None,
    ) -> Dict[str, List[RetrievedExample]]:
        """
        Synchronous version of retrieve_contrastive() for non-async contexts.
        """
        db_session = session or self._session
        if db_session is None:
            logger.warning("No database session provided, returning empty results")
            return {"positives": [], "negatives": [], "hard_negatives": []}

        # Get embedding
        query_embedding = self._get_embedding(query_text)
        embedding_list = query_embedding.tolist()

        # Get similar positive examples (failures)
        positives = self._query_similar_sync(
            db_session,
            failure_mode=failure_mode,
            is_failure=True,
            embedding=embedding_list,
            limit=k_positive,
        )

        # Get similar negative examples (healthy)
        negatives = self._query_similar_sync(
            db_session,
            failure_mode=failure_mode,
            is_failure=False,
            embedding=embedding_list,
            limit=k_negative,
        )

        # Get hard negatives with threshold
        hard_negatives = self._query_similar_with_threshold_sync(
            db_session,
            failure_mode=failure_mode,
            is_failure=False,
            embedding=embedding_list,
            limit=k_hard_negative,
            min_similarity=0.7,
        )

        return {
            "positives": positives,
            "negatives": negatives,
            "hard_negatives": hard_negatives,
        }

    def _query_similar_with_threshold_sync(
        self,
        session,
        failure_mode: str,
        is_failure: bool,
        embedding: List[float],
        limit: int,
        min_similarity: float = 0.0,
    ) -> List[RetrievedExample]:
        """Synchronous query for similar examples with threshold."""
        from sqlalchemy import text

        try:
            query = text("""
                SELECT
                    id::text,
                    failure_mode,
                    is_failure,
                    task_description,
                    conversation_summary,
                    key_events,
                    framework,
                    confidence,
                    1 - (embedding <=> :query_embedding::vector) as similarity
                FROM failure_examples
                WHERE failure_mode = :failure_mode
                  AND is_failure = :is_failure
                  AND embedding IS NOT NULL
                  AND 1 - (embedding <=> :query_embedding::vector) >= :min_similarity
                ORDER BY embedding <=> :query_embedding::vector
                LIMIT :limit
            """)

            result = session.execute(
                query,
                {
                    "failure_mode": failure_mode,
                    "is_failure": is_failure,
                    "query_embedding": str(embedding),
                    "limit": limit,
                    "min_similarity": min_similarity,
                }
            )

            rows = result.fetchall()

            examples = []
            for row in rows:
                examples.append(RetrievedExample(
                    id=row.id,
                    failure_mode=row.failure_mode,
                    is_failure=row.is_failure,
                    task_description=row.task_description,
                    conversation_summary=row.conversation_summary,
                    key_events=row.key_events or [],
                    framework=row.framework,
                    confidence=row.confidence or 100,
                    similarity=float(row.similarity) if row.similarity else 0.0,
                ))

            return examples

        except Exception as e:
            logger.error(f"Error querying similar examples with threshold (sync): {e}")
            return []

    def format_contrastive_examples(
        self,
        examples: Dict[str, List[RetrievedExample]],
        max_chars: int = 6000,
    ) -> str:
        """
        Format contrastive examples with clear labeling for LLM prompt.

        Args:
            examples: Dict with "positives", "negatives", "hard_negatives" keys
            max_chars: Maximum characters for all examples

        Returns:
            Formatted string with clearly labeled sections
        """
        sections = []
        current_chars = 0

        # Format positives first (most important)
        if examples.get("positives"):
            section = ["### FAILURE EXAMPLES (this IS the failure mode):\n"]
            for ex in examples["positives"]:
                if current_chars > max_chars:
                    break
                formatted = self._format_single_example(ex, "FAILURE")
                section.append(formatted)
                current_chars += len(formatted)
            sections.append("".join(section))

        # Format hard negatives (tricky cases)
        if examples.get("hard_negatives"):
            section = ["### TRICKY NON-FAILURES (similar but NOT failures):\n"]
            for ex in examples["hard_negatives"]:
                if current_chars > max_chars:
                    break
                formatted = self._format_single_example(ex, "NOT FAILURE")
                section.append(formatted)
                current_chars += len(formatted)
            sections.append("".join(section))

        # Format negatives (healthy examples)
        if examples.get("negatives"):
            section = ["### HEALTHY EXAMPLES (clearly not failures):\n"]
            for ex in examples["negatives"]:
                if current_chars > max_chars:
                    break
                formatted = self._format_single_example(ex, "NOT FAILURE")
                section.append(formatted)
                current_chars += len(formatted)
            sections.append("".join(section))

        return "\n\n".join(sections)

    def _format_single_example(
        self,
        example: RetrievedExample,
        verdict_label: str,
    ) -> str:
        """Format a single example with verdict label."""
        return f"""
**Task:** {example.task_description[:400]}
**Behavior:** {example.conversation_summary[:600]}
**Verdict:** {verdict_label}
---
"""

    def format_examples_for_prompt(
        self,
        examples: List[RetrievedExample],
        max_chars: int = 4000,
    ) -> str:
        """
        Format retrieved examples for inclusion in LLM prompt.

        Args:
            examples: List of RetrievedExample objects
            max_chars: Maximum characters for all examples

        Returns:
            Formatted string for LLM prompt
        """
        if not examples:
            return ""

        lines = ["## Retrieved Similar Examples\n"]
        current_chars = len(lines[0])

        for i, ex in enumerate(examples, 1):
            verdict = "YES (this IS a failure)" if ex.is_failure else "NO (healthy behavior)"

            example_text = f"""
### Example {i} (similarity: {ex.similarity:.2f})
**Task:** {ex.task_description[:500]}
**Agent Behavior:** {ex.conversation_summary[:800]}
**Verdict:** {verdict}
---
"""
            if current_chars + len(example_text) > max_chars:
                break

            lines.append(example_text)
            current_chars += len(example_text)

        return "".join(lines)


# Singleton instance
_retriever_instance: Optional[FailureExampleRetriever] = None


def get_retriever(session=None) -> FailureExampleRetriever:
    """Get or create singleton retriever instance."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = FailureExampleRetriever(session=session)
    elif session is not None:
        _retriever_instance._session = session
    return _retriever_instance
