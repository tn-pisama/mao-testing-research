#!/usr/bin/env python3
"""Generate independently-labeled delegation golden entries from MAST + synthetic.

Labels are computed from STRUCTURAL text analysis of delegation instructions
(length, presence of criteria keywords, vague terms, etc.), NOT from running
Pisama detectors. This provides an independent ground truth.

Output: merges into data/golden_dataset_external.json

Usage:
    python -m scripts.generate_delegation_data
    python -m scripts.generate_delegation_data --dry-run
"""

import hashlib
import json
import logging
import os
import re
import random
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import Dataset

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import (
    GoldenDataset,
    GoldenDatasetEntry,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

BACKEND = Path(__file__).resolve().parent.parent
MAST_PATH = BACKEND / "data" / "external" / "mast_full"
EXTERNAL_PATH = BACKEND / "data" / "golden_dataset_external.json"

SOURCE_TAG = "delegation_structural"


# ---------------------------------------------------------------------------
# Independent labeling for delegation quality
# ---------------------------------------------------------------------------

CRITERIA_KEYWORDS = {
    "when",
    "should",
    "must",
    "verify",
    "test",
    "ensure",
    "check",
    "confirm",
    "validate",
    "assert",
    "expect",
    "require",
    "at least",
    "at most",
    "no more than",
    "within",
    "before",
    "after",
    "deadline",
    "constraint",
    "acceptance",
}

VAGUE_TERMS = {
    "somehow",
    "figure out",
    "whatever",
    "just do",
    "handle it",
    "take care of",
    "deal with",
    "make it work",
    "fix it",
    "do something",
    "sort it out",
    "you know what",
    "etc",
    "stuff",
    "things",
    "something like",
    "kind of",
    "maybe",
    "i guess",
    "idk",
    "asap",
    "try to",
}

BOUND_KEYWORDS = {
    "limit",
    "max",
    "min",
    "budget",
    "timeout",
    "deadline",
    "scope",
    "boundary",
    "constraint",
    "token",
    "cost",
    "within",
    "under",
    "below",
    "above",
    "between",
}


def label_delegation_independently(
    instruction: str,
    task_context: str = "",
    success_criteria: str = "",
) -> bool:
    """Return True if delegation is POOR (should be detected as a failure).

    Positive = poor delegation (vague, missing criteria).
    Negative = well-specified delegation.
    """
    instruction_lower = instruction.lower()
    combined = f"{instruction} {task_context} {success_criteria}".lower()

    # Rule 1: Very short instructions are almost always vague
    if len(instruction.strip()) < 30:
        return True

    # Rule 2: No success criteria keywords at all
    has_criteria = any(kw in combined for kw in CRITERIA_KEYWORDS)

    # Rule 3: Contains vague terms
    has_vague = any(term in instruction_lower for term in VAGUE_TERMS)

    # Rule 4: Has numeric bounds or constraint keywords
    has_bounds = any(kw in combined for kw in BOUND_KEYWORDS)
    has_numbers = bool(re.search(r"\b\d+\b", combined))

    # Decision logic:
    # - Length > 100 AND has criteria AND (has bounds OR has numbers) -> negative (well-specified)
    if len(instruction.strip()) > 100 and has_criteria and (has_bounds or has_numbers):
        return False

    # - Has vague terms -> positive
    if has_vague:
        return True

    # - No criteria at all -> positive
    if not has_criteria:
        return True

    # - Short instruction (< 60 chars) without explicit bounds -> positive
    if len(instruction.strip()) < 60 and not has_bounds:
        return True

    # Default: if instruction is reasonably detailed, it is acceptable
    return False


# ---------------------------------------------------------------------------
# MAST trajectory parsing
# ---------------------------------------------------------------------------


def _extract_task_from_mast(row: dict) -> str:
    """Extract the task/instruction from a MAST trajectory."""
    trajectory = row["trace"].get("trajectory", "") or ""
    framework = row.get("mas_name", "")

    if framework == "ChatDev":
        m = re.search(r"\*\*task_prompt\*\*:\s*([^\n|]+)", trajectory)
        if m:
            return m.group(1).strip()

    if framework == "MetaGPT":
        m = re.search(
            r"UserRequirement\s*\nCONTENT:\s*\n(.+?)(?:\n\n|\n\[)",
            trajectory,
            re.DOTALL,
        )
        if m:
            return m.group(1).strip()

    if framework in ("AG2", "AutoGen"):
        m = re.search(
            r"(?:problem_statement|task):\s*(.+?)(?:\n[a-z_]+:|$)",
            trajectory,
            re.DOTALL,
        )
        if m:
            return m.group(1).strip()

    if framework == "Magentic":
        # Magentic traces often start with build/install output
        # Look for task-like content after that
        m = re.search(
            r"(?:Task|Query|Prompt|Question):\s*(.+?)(?:\n\n|\n\[|$)",
            trajectory,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            return m.group(1).strip()

    # Generic fallback
    m = re.search(
        r"(?:Task|Query|Prompt|Problem):\s*(.+?)(?:\n\n|\n\[|$)",
        trajectory,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()

    return trajectory[:200].strip()


def _truncate(text: str, max_chars: int = 2000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def _stable_id(prefix: str, *parts: str) -> str:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]
    return f"{prefix}_{h}"


# ---------------------------------------------------------------------------
# Synthetic entries
# ---------------------------------------------------------------------------

SYNTHETIC_POSITIVE = [
    {
        "delegator_instruction": "Do the thing",
        "task_context": "Some project",
        "success_criteria": "",
        "delegatee_capabilities": "General agent",
    },
    {
        "delegator_instruction": "Handle the customer issue somehow",
        "task_context": "Support ticket",
        "success_criteria": "",
        "delegatee_capabilities": "Support agent",
    },
    {
        "delegator_instruction": "Make the app work better",
        "task_context": "Mobile app project",
        "success_criteria": "",
        "delegatee_capabilities": "Developer agent",
    },
    {
        "delegator_instruction": "Fix whatever is broken in the data pipeline",
        "task_context": "Data engineering",
        "success_criteria": "",
        "delegatee_capabilities": "Data engineer agent",
    },
    {
        "delegator_instruction": "Write some tests",
        "task_context": "Testing task",
        "success_criteria": "",
        "delegatee_capabilities": "QA agent",
    },
    {
        "delegator_instruction": "Deal with the deployment stuff",
        "task_context": "",
        "success_criteria": "",
        "delegatee_capabilities": "DevOps agent",
    },
    {
        "delegator_instruction": "Update the docs or something",
        "task_context": "Documentation",
        "success_criteria": "",
        "delegatee_capabilities": "Technical writer agent",
    },
    {
        "delegator_instruction": "Try to make the API faster",
        "task_context": "Performance",
        "success_criteria": "",
        "delegatee_capabilities": "Backend agent",
    },
    {
        "delegator_instruction": "Sort out the security things",
        "task_context": "Security review",
        "success_criteria": "",
        "delegatee_capabilities": "Security agent",
    },
    {
        "delegator_instruction": "Clean up the code, I guess",
        "task_context": "Refactoring",
        "success_criteria": "",
        "delegatee_capabilities": "Developer agent",
    },
]

SYNTHETIC_NEGATIVE = [
    {
        "delegator_instruction": "Implement a REST API endpoint POST /api/v1/users that accepts JSON body with fields 'name' (string, required, 2-100 chars), 'email' (string, required, valid email format), and 'role' (enum: admin|user|viewer). Return 201 on success with the created user object including auto-generated UUID.",
        "task_context": "User management microservice, Python FastAPI, PostgreSQL database",
        "success_criteria": "Endpoint must return 201 for valid input, 422 for validation errors, 409 for duplicate email. Must include unit tests with at least 5 test cases covering happy path and edge cases.",
        "delegatee_capabilities": "FastAPI developer agent with database access and pytest capabilities",
    },
    {
        "delegator_instruction": "Write a Python function that calculates compound interest. Input: principal (float > 0), annual_rate (float 0-1), years (int >= 1), compounds_per_year (int >= 1). Output: final amount as float rounded to 2 decimal places. Must handle edge cases: zero rate returns principal, single compound equals simple interest formula.",
        "task_context": "Financial calculation library",
        "success_criteria": "Function must pass these test cases: (1000, 0.05, 10, 12) -> 1647.01, (5000, 0, 5, 4) -> 5000.00, (100, 0.10, 1, 1) -> 110.00. Must include type hints and docstring.",
        "delegatee_capabilities": "Python developer agent",
    },
    {
        "delegator_instruction": "Migrate the user_sessions table from MySQL 8 to PostgreSQL 16. Table has 12M rows, columns: id (bigint PK), user_id (FK to users), session_token (varchar 256 unique), created_at (datetime), expires_at (datetime), ip_address (inet). Maintain all indexes and constraints. Migration must complete within 2 hours with zero downtime.",
        "task_context": "Database migration project, current load: 500 req/s to sessions table",
        "success_criteria": "All 12M rows migrated with data integrity verified via row count and checksum comparison. Application must remain operational during migration. Rollback plan documented and tested.",
        "delegatee_capabilities": "DBA agent with MySQL and PostgreSQL access, can execute DDL and DML, has monitoring dashboard access",
    },
    {
        "delegator_instruction": "Create a CI/CD pipeline for the Node.js monorepo. Must run lint (eslint), type-check (tsc), unit tests (jest, min 80% coverage), integration tests (playwright), build (webpack), and deploy to staging on merge to develop branch. Deploy to production on tagged releases only.",
        "task_context": "GitHub Actions, Node.js 20, pnpm workspaces with 4 packages",
        "success_criteria": "Pipeline must complete in under 15 minutes. All stages must pass before deployment. Staging deploy must include smoke tests. Production deploy requires manual approval gate. Cost budget: under $50/month for CI.",
        "delegatee_capabilities": "DevOps agent with GitHub Actions configuration, AWS access (ECS), and monitoring setup capabilities",
    },
    {
        "delegator_instruction": "Implement rate limiting middleware for the Express.js API server. Limit to 100 requests per minute per IP address for unauthenticated users, 1000 requests per minute for authenticated users (identified by Bearer token). Use Redis for distributed rate limit state. Return 429 status with Retry-After header when limit exceeded.",
        "task_context": "Express.js 4.x API server, Redis 7 cluster, deployed across 3 instances behind AWS ALB",
        "success_criteria": "Rate limiter must be accurate within 5% tolerance under concurrent load. Must not add more than 5ms p99 latency. Must gracefully degrade if Redis is unavailable (allow traffic). Include load test script validating limits.",
        "delegatee_capabilities": "Node.js backend developer agent with Redis access and load testing tools",
    },
    {
        "delegator_instruction": "Refactor the payment processing module to support multiple payment providers. Currently hardcoded to Stripe. Must support Stripe, PayPal, and Square via a provider interface pattern. Each provider must implement: charge(amount, currency, token), refund(transaction_id, amount), and get_status(transaction_id). No changes to existing API contracts.",
        "task_context": "Python Django application, current monthly transaction volume: 50K",
        "success_criteria": "All existing payment tests must pass unchanged. New provider interface must have 100% test coverage. Switching providers must require only a config change, no code changes. Must maintain PCI DSS compliance.",
        "delegatee_capabilities": "Python developer agent with payment API access (sandbox environments for all 3 providers)",
    },
    {
        "delegator_instruction": "Set up monitoring and alerting for the Kubernetes cluster. Must monitor: node CPU/memory (alert at 80%), pod restart count (alert if > 3 in 5 min), API server latency p99 (alert if > 500ms), PVC usage (alert at 90%). Use Prometheus for metrics collection and Grafana for dashboards. Alert via PagerDuty for critical, Slack for warnings.",
        "task_context": "AWS EKS cluster with 12 nodes, running 40 services, Helm for deployment",
        "success_criteria": "All 4 alert rules must fire correctly when thresholds are exceeded (test with artificial load). Grafana dashboard must show cluster overview with drill-down per namespace. Alert latency must be under 30 seconds from threshold breach to notification.",
        "delegatee_capabilities": "SRE agent with kubectl access, Helm, Prometheus operator, Grafana API, PagerDuty and Slack webhook access",
    },
    {
        "delegator_instruction": "Implement a search feature for the product catalog. Must support full-text search across product name, description, and category fields. Results must be ranked by relevance with optional filters for price range (min/max), category (multi-select), and in-stock status. Pagination with 20 results per page. Search must return results within 200ms for up to 1M products.",
        "task_context": "React frontend, FastAPI backend, Elasticsearch 8 cluster",
        "success_criteria": "Search relevance must return expected top-3 results for 10 predefined test queries. Autocomplete must work with minimum 2 characters. Filters must be composable (AND logic). Must handle special characters and typos gracefully.",
        "delegatee_capabilities": "Full-stack developer agent with Elasticsearch, FastAPI, and React experience",
    },
    {
        "delegator_instruction": "Create a data validation pipeline for incoming CSV uploads. Must validate: file size (max 100MB), column schema (must match template with 15 required columns), data types per column (dates in ISO format, amounts as decimal with 2 places, emails matching RFC 5322). Generate a validation report with row-level errors. Reject files with more than 5% error rate.",
        "task_context": "Python data processing service, AWS S3 for file storage, PostgreSQL for reports",
        "success_criteria": "Pipeline must process a 100MB file in under 60 seconds. Must catch all 8 predefined error types in the test fixture. Validation report must be downloadable as CSV. Must handle UTF-8 and Latin-1 encoded files.",
        "delegatee_capabilities": "Data engineer agent with pandas, S3 access, and PostgreSQL write access",
    },
    {
        "delegator_instruction": "Implement WebSocket-based real-time notifications for the dashboard. Must support: new order alerts (to admin users), status change updates (to order owner), system announcements (broadcast to all connected users). Authentication via JWT token on connection handshake. Must handle reconnection with message replay for missed events (last 5 minutes).",
        "task_context": "Next.js frontend, FastAPI backend with Redis pub/sub, deployed on 3 backend instances",
        "success_criteria": "Messages must be delivered within 100ms of event. Must support 10K concurrent connections per instance. Must not lose messages during backend restart (Redis persistence). Include integration test simulating 100 concurrent clients.",
        "delegatee_capabilities": "Full-stack developer agent with WebSocket, Redis, and load testing capabilities",
    },
]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate_mast_delegation_entries(mast: Dataset) -> list[GoldenDatasetEntry]:
    """Extract delegation entries from MAST, labeled independently."""
    log.info("Mining MAST trajectories for delegation entries...")
    entries = []
    rng = random.Random(48)

    # Collect all rows with extracted tasks
    candidates = []
    for i in range(len(mast)):
        row = mast[i]
        task = _extract_task_from_mast(row)
        if not task or len(task) < 10:
            continue
        candidates.append((i, row, task))

    log.info("  Found %d MAST entries with extractable tasks", len(candidates))
    rng.shuffle(candidates)

    positive_entries = []
    negative_entries = []

    for idx, row, task in candidates:
        framework = row.get("mas_name", "unknown")
        task_context = f"Multi-agent {framework} system"

        # For positive candidates, use empty criteria (simulating poor delegation)
        is_positive = label_delegation_independently(task, task_context, "")

        if is_positive and len(positive_entries) < 15:
            entry_id = _stable_id("del_ind_pos", str(idx), framework)
            positive_entries.append(
                GoldenDatasetEntry(
                    id=entry_id,
                    detection_type=DetectionType.DELEGATION,
                    input_data={
                        "delegator_instruction": _truncate(task, 2000),
                        "task_context": task_context,
                        "success_criteria": "",
                        "delegatee_capabilities": f"{framework} agent",
                    },
                    expected_detected=True,
                    expected_confidence_min=0.3,
                    expected_confidence_max=1.0,
                    description=f"MAST {framework}: independently labeled as vague delegation",
                    source=SOURCE_TAG,
                    difficulty="medium",
                    split="test",
                    tags=[
                        "independent_label",
                        "mast",
                        "positive",
                        "delegation",
                        framework.lower(),
                    ],
                )
            )

        # For negatives, provide full context (simulating good delegation)
        full_criteria = f"Complete the task as specified: {task[:100]}. Verify output correctness and test coverage."
        full_capabilities = f"{framework} agent with code generation, testing, review, and deployment capabilities"
        is_negative = not label_delegation_independently(
            task, task_context, full_criteria
        )

        if is_negative and len(negative_entries) < 15:
            entry_id = _stable_id("del_ind_neg", str(idx), framework)
            negative_entries.append(
                GoldenDatasetEntry(
                    id=entry_id,
                    detection_type=DetectionType.DELEGATION,
                    input_data={
                        "delegator_instruction": _truncate(task, 2000),
                        "task_context": task_context,
                        "success_criteria": full_criteria,
                        "delegatee_capabilities": full_capabilities,
                    },
                    expected_detected=False,
                    expected_confidence_min=0.0,
                    expected_confidence_max=0.3,
                    description=f"MAST {framework}: independently labeled as well-specified delegation",
                    source=SOURCE_TAG,
                    difficulty="medium",
                    split="test",
                    tags=[
                        "independent_label",
                        "mast",
                        "negative",
                        "delegation",
                        framework.lower(),
                    ],
                )
            )

        if len(positive_entries) >= 15 and len(negative_entries) >= 15:
            break

    entries.extend(positive_entries)
    entries.extend(negative_entries)
    log.info(
        "  MAST delegation: %d positive, %d negative",
        len(positive_entries),
        len(negative_entries),
    )
    return entries


def generate_synthetic_delegation_entries() -> list[GoldenDatasetEntry]:
    """Create synthetic delegation entries with clear independent labels."""
    log.info("Generating synthetic delegation entries...")
    entries = []

    for i, data in enumerate(SYNTHETIC_POSITIVE):
        entry_id = _stable_id("del_syn_pos", str(i), data["delegator_instruction"][:50])
        # Verify independent label agrees
        label = label_delegation_independently(
            data["delegator_instruction"],
            data.get("task_context", ""),
            data.get("success_criteria", ""),
        )
        if not label:
            log.warning(
                "Synthetic positive %d labeled as NEGATIVE by independent labeler -- skipping",
                i,
            )
            continue

        entries.append(
            GoldenDatasetEntry(
                id=entry_id,
                detection_type=DetectionType.DELEGATION,
                input_data=data,
                expected_detected=True,
                expected_confidence_min=0.5,
                expected_confidence_max=1.0,
                description=f"Synthetic vague delegation (independently verified)",
                source=SOURCE_TAG,
                difficulty="easy",
                split="test",
                tags=[
                    "independent_label",
                    "synthetic",
                    "positive",
                    "delegation",
                ],
            )
        )

    for i, data in enumerate(SYNTHETIC_NEGATIVE):
        entry_id = _stable_id("del_syn_neg", str(i), data["delegator_instruction"][:50])
        # Verify independent label agrees
        label = label_delegation_independently(
            data["delegator_instruction"],
            data.get("task_context", ""),
            data.get("success_criteria", ""),
        )
        if label:
            log.warning(
                "Synthetic negative %d labeled as POSITIVE by independent labeler -- skipping",
                i,
            )
            continue

        entries.append(
            GoldenDatasetEntry(
                id=entry_id,
                detection_type=DetectionType.DELEGATION,
                input_data=data,
                expected_detected=False,
                expected_confidence_min=0.0,
                expected_confidence_max=0.2,
                description=f"Synthetic well-specified delegation (independently verified)",
                source=SOURCE_TAG,
                difficulty="easy",
                split="test",
                tags=[
                    "independent_label",
                    "synthetic",
                    "negative",
                    "delegation",
                ],
            )
        )

    pos = sum(1 for e in entries if e.expected_detected)
    neg = len(entries) - pos
    log.info("  Synthetic delegation: %d positive, %d negative", pos, neg)
    return entries


def merge_to_external(entries: list[GoldenDatasetEntry]) -> int:
    """Merge entries into external golden dataset, replacing old ones."""
    log.info("Loading external dataset from %s", EXTERNAL_PATH)
    dataset = GoldenDataset()
    if EXTERNAL_PATH.exists():
        dataset.load(EXTERNAL_PATH)
        log.info("Loaded %d existing entries", len(dataset.entries))

    # Remove old delegation_structural entries
    old_ids = [
        eid
        for eid in dataset.entries
        if dataset.entries[eid].source == SOURCE_TAG
    ]
    for eid in old_ids:
        dataset.remove_entry(eid)
    if old_ids:
        log.info("Removed %d old %s entries", len(old_ids), SOURCE_TAG)

    for entry in entries:
        dataset.add_entry(entry)

    dataset.save(EXTERNAL_PATH)
    log.info(
        "Saved external dataset: %d total entries to %s",
        len(dataset.entries),
        EXTERNAL_PATH,
    )
    return len(dataset.entries)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate independently-labeled delegation golden entries"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show plan only")
    args = parser.parse_args()

    # Load MAST
    log.info("Loading MAST dataset from %s", MAST_PATH)
    mast = Dataset.load_from_disk(str(MAST_PATH))
    log.info("MAST: %d entries", len(mast))

    # Generate entries
    mast_entries = generate_mast_delegation_entries(mast)
    synthetic_entries = generate_synthetic_delegation_entries()

    all_entries = mast_entries + synthetic_entries

    # Summary
    pos = sum(1 for e in all_entries if e.expected_detected)
    neg = len(all_entries) - pos
    log.info("")
    log.info("=" * 60)
    log.info("Delegation Data Generation Summary")
    log.info("=" * 60)
    log.info("  MAST entries:      %d", len(mast_entries))
    log.info("  Synthetic entries:  %d", len(synthetic_entries))
    log.info("  Total:             %d (%d positive, %d negative)", len(all_entries), pos, neg)
    log.info("=" * 60)

    if args.dry_run:
        log.info("Dry run -- not saving.")
        return

    if all_entries:
        merge_to_external(all_entries)
    else:
        log.warning("No entries generated.")


if __name__ == "__main__":
    main()
