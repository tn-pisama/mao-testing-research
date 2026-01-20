#!/usr/bin/env python3
"""
Populate MAST Trace Embeddings for Few-Shot Learning

Phase 4: Generates and stores embeddings for MAST benchmark traces
to enable similarity-based few-shot example selection in LLM prompts.

Usage:
    python benchmarks/scripts/populate_mast_embeddings.py \\
        --dataset data/mast_dev_869.json \\
        --batch-size 50 \\
        --clear-existing

This script:
1. Reads MAST dataset JSON
2. Extracts task descriptions and ground truth failures
3. Generates embeddings using BGE-M3 (1024 dimensions)
4. Stores in mast_trace_embeddings table with pgvector
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import sys

# Add backend to path for imports
backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.core.embeddings import get_embedder
from app.storage.models import MASTTraceEmbedding, Base

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_mast_dataset(dataset_path: Path) -> List[Dict]:
    """Load MAST dataset from JSON file."""
    logger.info(f"Loading MAST dataset from {dataset_path}")

    with open(dataset_path, 'r') as f:
        data = json.load(f)

    if isinstance(data, dict) and 'traces' in data:
        traces = data['traces']
    elif isinstance(data, list):
        traces = data
    else:
        raise ValueError(f"Unexpected dataset format: {type(data)}")

    logger.info(f"Loaded {len(traces)} traces")
    return traces


def extract_task_description(trace: Dict) -> str:
    """Extract task description from MAST trace.

    MAST structure: trace['trace']['trajectory'] contains the full log,
    starting with problem_statement which is the task description.
    """
    # Get trajectory from nested structure
    trajectory = trace.get('trace', {}).get('trajectory', '')

    if not trajectory:
        return ""

    # Extract problem_statement from trajectory
    # Format: "problem_statement:\n  <description>\n"
    import re
    problem_match = re.search(
        r'problem_statement:\s*\n\s*(.+?)(?=\n\s*\n[a-z_]+:|\nother_data:|\ntrajectory:|\Z)',
        trajectory,
        re.DOTALL
    )

    if problem_match:
        task = problem_match.group(1).strip()
        # Limit to reasonable length for embedding
        return task[:2000]

    # Fallback: use first 500 chars of trajectory
    return trajectory[:500].strip()


def extract_conversation_summary(trace: Dict, max_length: int = 500) -> Optional[str]:
    """Generate a brief summary of the conversation."""
    if 'conversation' not in trace:
        return None

    conversation = trace['conversation']
    if not conversation:
        return None

    # Sample first few turns for summary
    summary_turns = []
    for i, turn in enumerate(conversation[:5]):
        role = turn.get('role', 'unknown')
        content = turn.get('content', '')[:100]
        summary_turns.append(f"[{role}] {content}...")

        if i >= 3:  # Limit to first 3-4 turns
            break

    summary = "\n".join(summary_turns)
    return summary[:max_length]


def extract_ground_truth_failures(trace: Dict) -> Dict[str, bool]:
    """Extract ground truth failure annotations from MAST trace.

    MAST annotation codes (1.1, 1.2, etc.) map to F1-F14:
    - 1.1 = F1 (Specification Mismatch)
    - 1.2 = F2 (Poor Task Decomposition)
    - 1.3 = F3 (Resource Misallocation)
    - 1.4 = F4 (Inadequate Tool Provision)
    - 1.5 = F5 (Flawed Workflow Design)
    - 2.1 = F6 (Task Derailment)
    - 2.2 = F7 (Context Neglect)
    - 2.3 = F8 (Information Withholding)
    - 2.4 = F9 (Role Usurpation)
    - 2.5 = F10 (Communication Breakdown)
    - 2.6 = F11 (Coordination Failure)
    - 3.1 = F12 (Output Validation Failure)
    - 3.2 = F13 (Quality Gate Bypass)
    - 3.3 = F14 (Completion Misjudgment)
    """
    # MAST annotation mapping
    ANNOTATION_MAP = {
        "1.1": "F1", "1.2": "F2", "1.3": "F3", "1.4": "F4", "1.5": "F5",
        "2.1": "F6", "2.2": "F7", "2.3": "F8", "2.4": "F9", "2.5": "F10", "2.6": "F11",
        "3.1": "F12", "3.2": "F13", "3.3": "F14",
    }

    # Get MAST annotations
    mast_annotation = trace.get('mast_annotation', {})

    # Convert to F1-F14 format
    failures = {}
    for i in range(1, 15):
        failures[f"F{i}"] = False

    for code, value in mast_annotation.items():
        mode = ANNOTATION_MAP.get(str(code))
        if mode:
            # Value is integer (0 or 1)
            failures[mode] = bool(value)

    return failures


def populate_embeddings(
    dataset_path: Path,
    batch_size: int = 50,
    clear_existing: bool = False,
    dry_run: bool = False
) -> int:
    """
    Populate MAST trace embeddings table.

    Args:
        dataset_path: Path to MAST dataset JSON
        batch_size: Number of traces to process in each batch
        clear_existing: Whether to clear existing embeddings first
        dry_run: If True, don't actually insert into database

    Returns:
        Number of embeddings created
    """
    # Load dataset
    traces = load_mast_dataset(dataset_path)

    # Initialize embedder (uses configured model from settings - BGE-M3 by default)
    logger.info("Initializing embedder (BGE-M3)")
    embedder = get_embedder()

    # Connect to database (convert async URL to sync for this script)
    settings = get_settings()
    db_url = settings.database_url.replace("+asyncpg", "")  # Use psycopg2 (sync)
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Clear existing if requested
        if clear_existing and not dry_run:
            logger.warning("Clearing existing embeddings...")
            count = session.query(MASTTraceEmbedding).delete()
            session.commit()
            logger.info(f"Deleted {count} existing embeddings")

        # Process in batches
        created_count = 0
        skipped_count = 0

        for i in range(0, len(traces), batch_size):
            batch = traces[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1}/{(len(traces) + batch_size - 1) // batch_size}")

            for trace in batch:
                # Create unique trace ID from key + index
                # The trace_id field alone is not unique in MAST dataset
                key = trace.get('trace', {}).get('key', 'unknown')
                index = trace.get('trace', {}).get('index', i)
                trace_id = f"{key}_{index}"

                # Check if already exists
                if not clear_existing:
                    existing = session.query(MASTTraceEmbedding).filter_by(trace_id=trace_id).first()
                    if existing:
                        logger.debug(f"Skipping existing trace: {trace_id}")
                        skipped_count += 1
                        continue

                # Extract data
                task_description = extract_task_description(trace)
                if not task_description:
                    logger.warning(f"No task description for trace {trace_id}, skipping")
                    skipped_count += 1
                    continue

                ground_truth_failures = extract_ground_truth_failures(trace)
                framework = trace.get('mas_name', 'unknown')  # Framework name in MAST
                conversation_summary = extract_conversation_summary(trace)

                # Generate embedding
                task_embedding = embedder.encode(task_description, is_query=False)

                # Create record
                if not dry_run:
                    embedding_record = MASTTraceEmbedding(
                        trace_id=trace_id,
                        task_embedding=task_embedding.tolist(),  # Convert numpy array to list
                        ground_truth_failures=ground_truth_failures,
                        framework=framework,
                        task_description=task_description,
                        conversation_summary=conversation_summary,
                        trace_metadata={
                            'source': str(dataset_path),
                            'original_index': i,
                        }
                    )
                    session.add(embedding_record)
                    created_count += 1
                else:
                    logger.info(f"[DRY RUN] Would create embedding for {trace_id}")
                    created_count += 1

            # Commit batch
            if not dry_run:
                session.commit()
                logger.info(f"Committed batch {i // batch_size + 1}")

        logger.info(f"Population complete: {created_count} created, {skipped_count} skipped")
        return created_count

    except Exception as e:
        logger.error(f"Error populating embeddings: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Populate MAST trace embeddings for few-shot learning"
    )
    parser.add_argument(
        '--dataset', '-d',
        type=Path,
        required=True,
        help='Path to MAST dataset JSON (e.g., data/mast_dev_869.json)'
    )
    parser.add_argument(
        '--batch-size', '-b',
        type=int,
        default=50,
        help='Number of traces to process per batch (default: 50)'
    )
    parser.add_argument(
        '--clear-existing', '-c',
        action='store_true',
        help='Clear existing embeddings before populating'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Dry run mode (don\'t actually insert into database)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate dataset path
    if not args.dataset.exists():
        logger.error(f"Dataset not found: {args.dataset}")
        return 1

    # Run population
    try:
        count = populate_embeddings(
            dataset_path=args.dataset,
            batch_size=args.batch_size,
            clear_existing=args.clear_existing,
            dry_run=args.dry_run
        )

        logger.info(f"Successfully populated {count} embeddings")
        return 0

    except Exception as e:
        logger.error(f"Failed to populate embeddings: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
