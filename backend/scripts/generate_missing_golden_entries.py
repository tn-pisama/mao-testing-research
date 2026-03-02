"""Generate missing golden dataset entries for LangGraph core types and Dify gaps.

Gaps identified:
- LangGraph: 0 entries for 17 core types (loop, corruption, persona_drift, etc.)
- Dify: 0 entries for dify_classifier_drift, dify_tool_schema_mismatch
- Dify: 44/50 entries for dify_variable_leak (needs 6 more)

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    cd backend
    python3 scripts/generate_missing_golden_entries.py --langgraph-core
    python3 scripts/generate_missing_golden_entries.py --dify-gaps
    python3 scripts/generate_missing_golden_entries.py --all
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env if present (so background invocations pick up ANTHROPIC_API_KEY)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

from app.detection.validation import DetectionType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

CORE_TYPES = [
    DetectionType.LOOP, DetectionType.CORRUPTION, DetectionType.PERSONA_DRIFT,
    DetectionType.HALLUCINATION, DetectionType.INJECTION, DetectionType.OVERFLOW,
    DetectionType.COORDINATION, DetectionType.COMMUNICATION, DetectionType.DERAILMENT,
    DetectionType.CONTEXT, DetectionType.SPECIFICATION, DetectionType.DECOMPOSITION,
    DetectionType.WITHHOLDING, DetectionType.COMPLETION, DetectionType.GROUNDING,
    DetectionType.RETRIEVAL_QUALITY, DetectionType.WORKFLOW,
]

DIFY_GAP_TYPES = [
    DetectionType.DIFY_CLASSIFIER_DRIFT,
    DetectionType.DIFY_TOOL_SCHEMA_MISMATCH,
    DetectionType.DIFY_VARIABLE_LEAK,
]


def generate_langgraph_core(target_per_type: int = 50):
    """Generate core type entries with LangGraph context."""
    from app.detection_enterprise.langgraph_golden_data_generator import LangGraphGoldenDataGenerator
    from app.detection_enterprise.golden_dataset import GoldenDataset

    output_path = DATA_DIR / "golden_dataset_langgraph_expanded.json"

    generator = LangGraphGoldenDataGenerator()
    if not generator.is_available:
        print("ERROR: No ANTHROPIC_API_KEY set")
        sys.exit(1)

    print(f"\n=== Generating LangGraph core type entries ===")
    print(f"Target: {target_per_type} per type, {len(CORE_TYPES)} core types")
    print(f"Output: {output_path}\n")

    result = generator.generate_batch(
        detection_types=CORE_TYPES,
        target_per_type=target_per_type,
        output_path=output_path,
        resume=True,  # Resume from existing file
    )

    print(f"\nGeneration complete:")
    total = sum(
        v.get("generated", 0) for v in result.items()
        if isinstance(v, dict)
    ) if isinstance(result, dict) else 0

    for type_key, stats in sorted(result.items()):
        if isinstance(stats, dict):
            if stats.get("skipped"):
                print(f"  {type_key}: skipped (already at {stats.get('existing', '?')})")
            else:
                print(f"  {type_key}: generated {stats.get('generated', 0)}")

    # Verify final count
    dataset = GoldenDataset()
    dataset.load_json(output_path)
    types = {}
    for entry in dataset.entries.values():
        dt = entry.detection_type.value if hasattr(entry.detection_type, 'value') else str(entry.detection_type)
        types[dt] = types.get(dt, 0) + 1
    print(f"\nFinal dataset: {len(dataset.entries)} entries")
    for dt, cnt in sorted(types.items()):
        print(f"  {dt}: {cnt}")


def generate_dify_gaps(target_per_type: int = 100):
    """Generate missing Dify framework type entries."""
    from app.detection_enterprise.dify_golden_data_generator import DifyGoldenDataGenerator
    from app.detection_enterprise.golden_dataset import GoldenDataset

    output_path = DATA_DIR / "golden_dataset_dify_expanded.json"

    generator = DifyGoldenDataGenerator()
    if not generator.is_available:
        print("ERROR: No ANTHROPIC_API_KEY set")
        sys.exit(1)

    print(f"\n=== Generating Dify gap entries ===")
    print(f"Target: {target_per_type} per type")
    print(f"Types: {[dt.value for dt in DIFY_GAP_TYPES]}")
    print(f"Output: {output_path}\n")

    result = generator.generate_batch(
        detection_types=DIFY_GAP_TYPES,
        target_per_type=target_per_type,
        output_path=output_path,
        resume=True,
    )

    print(f"\nGeneration complete:")
    for type_key, stats in sorted(result.items()):
        if isinstance(stats, dict):
            if stats.get("skipped"):
                print(f"  {type_key}: skipped (already at {stats.get('existing', '?')})")
            else:
                print(f"  {type_key}: generated {stats.get('generated', 0)}")

    # Verify
    dataset = GoldenDataset()
    dataset.load_json(output_path)
    types = {}
    for entry in dataset.entries.values():
        dt = entry.detection_type.value if hasattr(entry.detection_type, 'value') else str(entry.detection_type)
        types[dt] = types.get(dt, 0) + 1
    print(f"\nFinal Dify dataset: {len(dataset.entries)} entries")
    for dt, cnt in sorted(types.items()):
        print(f"  {dt}: {cnt}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate missing golden dataset entries")
    parser.add_argument("--langgraph-core", action="store_true", help="Generate LangGraph core type entries")
    parser.add_argument("--dify-gaps", action="store_true", help="Generate Dify missing framework type entries")
    parser.add_argument("--all", action="store_true", help="Generate all missing entries")
    parser.add_argument("--target", type=int, default=50, help="Target entries per type (default: 50)")
    args = parser.parse_args()

    if not any([args.langgraph_core, args.dify_gaps, args.all]):
        parser.print_help()
        sys.exit(1)

    if args.langgraph_core or args.all:
        generate_langgraph_core(target_per_type=args.target)

    if args.dify_gaps or args.all:
        generate_dify_gaps(target_per_type=args.target)

    print("\nDone!")
