#!/usr/bin/env python3
"""
Populate failure_examples table from MAST dataset for RAG-based detection.

This script:
1. Loads MAST dataset from data/mast/MAD_full_dataset.json
2. Parses each trace with framework-specific extractors
3. Creates FailureExample records with embeddings
4. Stores in PostgreSQL with pgvector for similarity search

Usage:
    python -m scripts.populate_failure_examples

Environment:
    DATABASE_URL: PostgreSQL connection string
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MAST annotation to failure mode mapping
ANNOTATION_MAP = {
    "1.1": "F1",   # Specification Mismatch
    "1.2": "F2",   # Poor Task Decomposition
    "1.3": "F3",   # Resource Misallocation
    "1.4": "F4",   # Inadequate Tool Provision
    "1.5": "F5",   # Flawed Workflow Design
    "2.1": "F6",   # Task Derailment
    "2.2": "F7",   # Context Neglect
    "2.3": "F8",   # Information Withholding
    "2.4": "F9",   # Role Usurpation
    "2.5": "F10",  # Communication Breakdown
    "2.6": "F11",  # Coordination Failure
    "3.1": "F12",  # Output Validation Failure
    "3.2": "F13",  # Quality Gate Bypass
    "3.3": "F14",  # Completion Misjudgment
}


def parse_annotations(annotations: Dict[str, Any]) -> Dict[str, bool]:
    """Convert MAST annotations to failure mode flags."""
    result = {}
    for code, value in annotations.items():
        mode = ANNOTATION_MAP.get(str(code))
        if mode:
            if isinstance(value, bool):
                result[mode] = value
            elif isinstance(value, (int, float)):
                result[mode] = value > 0
            elif isinstance(value, str):
                result[mode] = value.lower() in ("true", "yes", "1")
            else:
                result[mode] = bool(value)
    return result


def extract_task(data: Dict[str, Any]) -> str:
    """Extract task description from MAST record."""
    # Try various locations
    task = data.get("task") or data.get("query") or data.get("prompt")
    if task:
        return str(task)[:2000]

    # Check trace for task
    trace = data.get("trace", {})
    trajectory = trace.get("trajectory", "")

    # Common patterns
    import re
    patterns = [
        r'\*\*task_prompt\*\*:\s*([^\n|]+)',
        r'(?:Task|Query|Prompt|Problem):\s*(.+?)(?:\n\n|\n\[|$)',
        r'problem_statement:\s*(.+?)(?:\n[a-z_]+:|$)',
    ]

    for pattern in patterns:
        match = re.search(pattern, trajectory[:5000], re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()[:2000]

    # Fallback: first 500 chars of trajectory
    return trajectory[:500] if trajectory else "Unknown task"


def extract_summary(data: Dict[str, Any]) -> str:
    """Extract conversation summary from MAST record."""
    trace = data.get("trace", {})
    trajectory = trace.get("trajectory", "")

    # Clean up trajectory for summary
    # Take first 3000 chars as summary
    summary = trajectory[:3000]

    # Clean up common log noise
    import re
    summary = re.sub(r'\[\d{4}-\d{2}-\d{2}[^\]]*\]', '', summary)
    summary = re.sub(r'\*\*\[[^\]]+\]\*\*', '', summary)
    summary = re.sub(r'\n{3,}', '\n\n', summary)

    return summary.strip()[:3000] if summary else "No conversation summary"


def extract_key_events(data: Dict[str, Any]) -> List[str]:
    """Extract key events from MAST record."""
    trace = data.get("trace", {})
    trajectory = trace.get("trajectory", "")

    events = []
    import re

    # Look for error/success indicators
    if "error" in trajectory.lower():
        events.append("Contains error indicators")
    if "success" in trajectory.lower() or "complete" in trajectory.lower():
        events.append("Contains completion indicators")
    if "failed" in trajectory.lower():
        events.append("Contains failure indicators")

    # Count agents
    agents = set()
    for match in re.finditer(r'\b(Agent|Assistant|User|Programmer|Reviewer|CEO|CTO)\b', trajectory, re.IGNORECASE):
        agents.add(match.group(1))
    if agents:
        events.append(f"Participants: {', '.join(list(agents)[:5])}")

    # Tool calls
    tool_count = len(re.findall(r'Tool:|Function:|API call', trajectory, re.IGNORECASE))
    if tool_count > 0:
        events.append(f"Tool calls: ~{tool_count}")

    return events


def get_embedder():
    """Lazy load embedding service."""
    try:
        from app.core.embeddings import get_embedder
        return get_embedder()
    except Exception as e:
        logger.warning(f"Could not load embedding service: {e}")
        return None


def populate_from_mast(
    data_path: str,
    db_url: str,
    batch_size: int = 100,
    max_records: Optional[int] = None,
    skip_embeddings: bool = False,
):
    """
    Populate failure_examples table from MAST dataset.

    Args:
        data_path: Path to MAD_full_dataset.json
        db_url: PostgreSQL connection URL
        batch_size: Number of records per batch insert
        max_records: Maximum records to process (None = all)
        skip_embeddings: Skip embedding generation (faster for testing)
    """
    logger.info(f"Loading MAST data from {data_path}")

    # Load data
    with open(data_path, 'r') as f:
        mast_data = json.load(f)

    logger.info(f"Loaded {len(mast_data)} MAST records")

    if max_records:
        mast_data = mast_data[:max_records]
        logger.info(f"Processing first {max_records} records")

    # Connect to database
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)

    # Get embedder
    embedder = None if skip_embeddings else get_embedder()
    if embedder:
        logger.info("Embedding service loaded")
    else:
        logger.warning("Embedding service not available, skipping embeddings")

    # Track stats
    stats = {
        "processed": 0,
        "inserted": 0,
        "skipped": 0,
        "errors": 0,
    }

    # Process in batches
    batch = []

    for i, record in enumerate(mast_data):
        try:
            framework = record.get("mas_name", "unknown")
            trace_id = str(record.get("trace_id", i))
            annotations = record.get("mast_annotation", {})

            # Parse annotations
            failure_modes = parse_annotations(annotations)

            # Extract content
            task = extract_task(record)
            summary = extract_summary(record)
            key_events = extract_key_events(record)

            # Create embedding text
            embed_text = f"{task} {summary[:1000]}"

            # Generate embedding if available
            embedding = None
            if embedder:
                try:
                    embedding = embedder.encode(embed_text, is_query=False).tolist()
                except Exception as e:
                    logger.warning(f"Embedding failed for record {i}: {e}")

            # Create examples for each failure mode
            for mode in ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "F13", "F14"]:
                is_failure = failure_modes.get(mode, False)

                # Create unique ID for this example (must be valid UUID format)
                hash_hex = hashlib.sha256(
                    f"{trace_id}:{mode}:{is_failure}".encode()
                ).hexdigest()[:32]
                # Format as UUID: 8-4-4-4-12
                example_id = f"{hash_hex[:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}-{hash_hex[16:20]}-{hash_hex[20:32]}"

                example = {
                    "id": example_id,
                    "dataset": "mast",
                    "framework": framework,
                    "trace_id": trace_id,
                    "failure_mode": mode,
                    "is_failure": is_failure,
                    "task_description": task,
                    "conversation_summary": summary,
                    "key_events": json.dumps(key_events),
                    "embedding": json.dumps(embedding) if embedding else None,
                    "confidence": 100,  # Ground truth from MAST
                    "source": "ground_truth",
                }

                batch.append(example)

            stats["processed"] += 1

            # Insert batch
            if len(batch) >= batch_size:
                inserted = _insert_batch(engine, batch)
                stats["inserted"] += inserted
                stats["skipped"] += len(batch) - inserted
                batch = []

                if stats["processed"] % 100 == 0:
                    logger.info(f"Progress: {stats['processed']}/{len(mast_data)} records processed")

        except Exception as e:
            logger.error(f"Error processing record {i}: {e}")
            stats["errors"] += 1
            continue

    # Insert remaining batch
    if batch:
        inserted = _insert_batch(engine, batch)
        stats["inserted"] += inserted
        stats["skipped"] += len(batch) - inserted

    logger.info(f"Complete! Stats: {stats}")


def _insert_batch(engine, batch: List[Dict]) -> int:
    """Insert batch of examples, handling duplicates."""
    if not batch:
        return 0

    inserted = 0
    with engine.connect() as conn:
        for example in batch:
            try:
                # Upsert query - use CAST() instead of :: to avoid parameter conflicts
                query = text("""
                    INSERT INTO failure_examples (
                        id, dataset, framework, trace_id, failure_mode, is_failure,
                        task_description, conversation_summary, key_events,
                        embedding, confidence, source
                    ) VALUES (
                        CAST(:id AS uuid), :dataset, :framework, :trace_id, :failure_mode, :is_failure,
                        :task_description, :conversation_summary, CAST(:key_events AS jsonb),
                        CAST(:embedding AS vector), :confidence, :source
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        updated_at = now()
                """)

                conn.execute(query, example)
                inserted += 1

            except Exception as e:
                logger.warning(f"Insert failed for {example['id']}: {e}")
                continue

        conn.commit()

    return inserted


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Populate failure_examples from MAST dataset")
    parser.add_argument("--data", default="data/mast/MAD_full_dataset.json", help="Path to MAST data")
    parser.add_argument("--max", type=int, default=None, help="Max records to process")
    parser.add_argument("--batch", type=int, default=100, help="Batch size")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embedding generation")
    args = parser.parse_args()

    # Get database URL from environment
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Default for local development
        db_url = "postgresql://postgres:postgres@localhost:5432/mao_testing"
        logger.warning(f"DATABASE_URL not set, using default: {db_url}")

    data_path = Path(__file__).parent.parent.parent / args.data
    if not data_path.exists():
        logger.error(f"Data file not found: {data_path}")
        sys.exit(1)

    populate_from_mast(
        data_path=str(data_path),
        db_url=db_url,
        batch_size=args.batch,
        max_records=args.max,
        skip_embeddings=args.skip_embeddings,
    )


if __name__ == "__main__":
    main()
