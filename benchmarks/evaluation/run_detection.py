"""Run mao-testing detection on generated traces.

Loads traces from JSONL files and runs the mao-testing detection pipeline.
Reports detection results for each failure mode.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add mao-testing backend to path (relative to this file's location)
_BACKEND_PATH = str(Path(__file__).parent.parent.parent / "backend")
sys.path.insert(0, _BACKEND_PATH)

from app.ingestion.universal_trace import UniversalTrace, UniversalSpan, SpanType, SpanStatus
from app.detection.orchestrator import DetectionOrchestrator, diagnose_trace


def parse_span_type(span_type_str: str) -> SpanType:
    """Convert span type string to SpanType enum."""
    mapping = {
        "agent": SpanType.AGENT,
        "tool_call": SpanType.TOOL_CALL,
        "llm_call": SpanType.LLM_CALL,
        "handoff": SpanType.HANDOFF,
        "chain": SpanType.CHAIN,
        "retrieval": SpanType.RETRIEVAL,
    }
    return mapping.get(span_type_str.lower(), SpanType.UNKNOWN)


def parse_span_status(status_str: str) -> SpanStatus:
    """Convert status string to SpanStatus enum."""
    mapping = {
        "ok": SpanStatus.OK,
        "error": SpanStatus.ERROR,
        "timeout": SpanStatus.TIMEOUT,
        "cancelled": SpanStatus.CANCELLED,
    }
    return mapping.get(status_str.lower(), SpanStatus.OK)


def load_traces(traces_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load all traces from JSONL files, grouped by failure mode."""
    traces_by_mode = defaultdict(list)

    for jsonl_file in sorted(traces_dir.glob("F*_traces.jsonl")):
        failure_mode = jsonl_file.stem.replace("_traces", "")

        # Group spans by trace_id
        spans_by_trace = defaultdict(list)
        with open(jsonl_file) as f:
            for line in f:
                span_data = json.loads(line)
                trace_id = span_data.get("trace_id")
                if trace_id:
                    spans_by_trace[trace_id].append(span_data)

        # Create trace objects
        for trace_id, spans in spans_by_trace.items():
            traces_by_mode[failure_mode].append({
                "trace_id": trace_id,
                "spans": spans,
                "metadata": spans[0].get("_trace_metadata", {}) if spans else {},
            })

    return dict(traces_by_mode)


def convert_to_universal_trace(trace_data: Dict[str, Any]) -> UniversalTrace:
    """Convert raw trace data to UniversalTrace format."""
    trace_id = trace_data["trace_id"]
    spans_data = trace_data["spans"]

    # Convert spans
    universal_spans = []
    for span_data in spans_data:
        # Parse timestamps
        start_time = datetime.fromisoformat(span_data.get("start_time", "").replace("Z", "+00:00"))
        end_time = None
        if span_data.get("end_time"):
            end_time = datetime.fromisoformat(span_data["end_time"].replace("Z", "+00:00"))

        span = UniversalSpan(
            id=span_data.get("span_id", ""),
            trace_id=trace_id,
            name=span_data.get("name", ""),
            span_type=parse_span_type(span_data.get("span_type", "unknown")),
            status=parse_span_status(span_data.get("status", "ok")),
            start_time=start_time,
            end_time=end_time,
            duration_ms=span_data.get("duration_ms", 0),
            parent_id=span_data.get("parent_id"),
            agent_id=span_data.get("agent_id"),
            agent_name=span_data.get("name"),
            input_data=span_data.get("input_data", {}),
            output_data=span_data.get("output_data", {}),
            prompt=span_data.get("prompt"),
            response=span_data.get("response"),
            model=span_data.get("model"),
            tokens_input=span_data.get("tokens_input", 0),
            tokens_output=span_data.get("tokens_output", 0),
            source_format=span_data.get("source_format", "langgraph"),
            metadata=span_data.get("metadata", {}),
        )
        universal_spans.append(span)

    # Create trace
    return UniversalTrace(
        trace_id=trace_id,
        spans=universal_spans,
        source_format="langgraph",
        metadata=trace_data.get("metadata", {}),
    )


def run_detection(traces_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Run detection on all traces and return results by failure mode."""
    print("Loading traces...")
    traces_by_mode = load_traces(traces_dir)

    print(f"Loaded {sum(len(t) for t in traces_by_mode.values())} traces across {len(traces_by_mode)} failure modes")

    # Initialize detection orchestrator
    orchestrator = DetectionOrchestrator(enable_llm_explanation=False)

    results_by_mode = {}

    for failure_mode in sorted(traces_by_mode.keys()):
        traces = traces_by_mode[failure_mode]
        print(f"\n{'='*60}")
        print(f"Running detection on {failure_mode}: {len(traces)} traces")
        print(f"{'='*60}")

        mode_results = {
            "total_traces": len(traces),
            "detections_found": 0,
            "detection_types": defaultdict(int),
            "severities": defaultdict(int),
            "traces_with_detection": 0,
            "traces_without_detection": 0,
            "sample_detections": [],
        }

        for i, trace_data in enumerate(traces):
            try:
                # Convert to UniversalTrace
                universal_trace = convert_to_universal_trace(trace_data)

                # Run detection
                diagnosis = orchestrator.analyze_trace(universal_trace)

                if diagnosis.has_failures:
                    mode_results["traces_with_detection"] += 1
                    mode_results["detections_found"] += diagnosis.failure_count

                    for detection in diagnosis.all_detections:
                        mode_results["detection_types"][detection.category.value] += 1
                        mode_results["severities"][detection.severity.value] += 1

                    # Save sample detections
                    if len(mode_results["sample_detections"]) < 3:
                        mode_results["sample_detections"].append({
                            "trace_id": trace_data["trace_id"],
                            "scenario": trace_data.get("metadata", {}).get("scenario", ""),
                            "primary_failure": diagnosis.primary_failure.to_dict() if diagnosis.primary_failure else None,
                        })
                else:
                    mode_results["traces_without_detection"] += 1

                # Progress indicator
                if (i + 1) % 10 == 0:
                    print(f"  Processed {i + 1}/{len(traces)} traces...")

            except Exception as e:
                print(f"  Error processing trace {i + 1}: {e}")
                mode_results["traces_without_detection"] += 1

        # Convert defaultdicts to regular dicts for JSON serialization
        mode_results["detection_types"] = dict(mode_results["detection_types"])
        mode_results["severities"] = dict(mode_results["severities"])

        # Calculate detection rate
        mode_results["detection_rate"] = (
            mode_results["traces_with_detection"] / mode_results["total_traces"] * 100
            if mode_results["total_traces"] > 0 else 0
        )

        results_by_mode[failure_mode] = mode_results

        print(f"  Detection rate: {mode_results['detection_rate']:.1f}%")
        print(f"  Traces with detection: {mode_results['traces_with_detection']}")
        print(f"  Total detections: {mode_results['detections_found']}")
        if mode_results["detection_types"]:
            print(f"  Detection types: {mode_results['detection_types']}")

    return results_by_mode


def print_summary(results: Dict[str, Dict[str, Any]]):
    """Print summary report of detection results."""
    print("\n" + "="*80)
    print("DETECTION RESULTS SUMMARY")
    print("="*80)

    # Header
    print(f"{'Failure Mode':<35} {'Traces':<10} {'Detected':<10} {'Rate':<10}")
    print("-"*80)

    total_traces = 0
    total_detected = 0

    for mode, result in sorted(results.items()):
        print(f"{mode:<35} {result['total_traces']:<10} {result['traces_with_detection']:<10} {result['detection_rate']:.1f}%")
        total_traces += result["total_traces"]
        total_detected += result["traces_with_detection"]

    print("-"*80)
    overall_rate = total_detected / total_traces * 100 if total_traces > 0 else 0
    print(f"{'TOTAL':<35} {total_traces:<10} {total_detected:<10} {overall_rate:.1f}%")

    # Detection types breakdown
    print("\n" + "="*80)
    print("DETECTION TYPES BREAKDOWN")
    print("="*80)

    all_detection_types = defaultdict(int)
    for result in results.values():
        for dtype, count in result.get("detection_types", {}).items():
            all_detection_types[dtype] += count

    for dtype, count in sorted(all_detection_types.items(), key=lambda x: -x[1]):
        print(f"  {dtype}: {count}")

    # Severity breakdown
    print("\n" + "="*80)
    print("SEVERITY BREAKDOWN")
    print("="*80)

    all_severities = defaultdict(int)
    for result in results.values():
        for severity, count in result.get("severities", {}).items():
            all_severities[severity] += count

    for severity in ["critical", "high", "medium", "low", "info"]:
        if severity in all_severities:
            print(f"  {severity.upper()}: {all_severities[severity]}")


def main():
    traces_dir = Path("../traces")

    if not traces_dir.exists():
        print(f"Error: Traces directory not found: {traces_dir}")
        return

    # Run detection
    results = run_detection(traces_dir)

    # Print summary
    print_summary(results)

    # Save results to JSON
    output_file = traces_dir / "detection_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
