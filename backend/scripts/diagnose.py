#!/usr/bin/env python3
"""CLI tool for diagnosing agent traces.

Usage:
    python scripts/diagnose.py <trace_file>
    python scripts/diagnose.py --stdin < trace.json
    cat trace.json | python scripts/diagnose.py --stdin

Examples:
    python scripts/diagnose.py my_trace.json
    python scripts/diagnose.py my_trace.json --format langsmith
    python scripts/diagnose.py my_trace.json --output results.json
    python scripts/diagnose.py --stdin --format otel < trace.json
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ingestion.importers import import_trace, detect_format, IMPORTERS
from app.detection.orchestrator import DetectionOrchestrator


def colorize(text: str, color: str) -> str:
    """Add ANSI color codes to text."""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "purple": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def severity_color(severity: str) -> str:
    """Get color for severity level."""
    return {
        "critical": "red",
        "high": "red",
        "medium": "yellow",
        "low": "blue",
    }.get(severity.lower(), "white")


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{colorize('═' * 60, 'cyan')}")
    print(colorize(f"  {text}", 'bold'))
    print(colorize('═' * 60, 'cyan'))


def print_detection(detection, index: int) -> None:
    """Print a single detection."""
    severity = detection.severity.value if hasattr(detection.severity, 'value') else str(detection.severity)
    color = severity_color(severity)

    print(f"\n  {colorize(f'[{index}]', 'bold')} {colorize(detection.title, color)}")
    print(f"      Category: {detection.category.value if hasattr(detection.category, 'value') else detection.category}")
    print(f"      Severity: {colorize(severity.upper(), color)}")
    print(f"      Confidence: {detection.confidence:.0%}")
    print(f"      {detection.description}")

    if detection.evidence:
        print(f"      Evidence: {json.dumps(detection.evidence[:2], indent=8)[:200]}...")

    if detection.suggested_fix:
        print(f"      {colorize('Fix:', 'green')} {detection.suggested_fix}")


def diagnose_trace(content: str, format_name: str = "auto", verbose: bool = False) -> dict:
    """Diagnose a trace and return results.

    Args:
        content: Raw trace content
        format_name: Format name or "auto"
        verbose: Print verbose output

    Returns:
        Diagnosis result dictionary
    """
    # Detect format if auto
    if format_name == "auto":
        format_name = detect_format(content)
        if verbose:
            print(f"Detected format: {format_name}")

    # Import trace
    trace = import_trace(content, format_name)
    if verbose:
        print(f"Imported {len(trace.spans)} spans")

    # Run detection
    orchestrator = DetectionOrchestrator()
    result = orchestrator.analyze_trace(trace)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose agent traces for failures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Trace file to analyze (JSON or JSONL)"
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read trace from stdin"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["auto"] + list(IMPORTERS.keys()),
        default="auto",
        help="Trace format (default: auto-detect)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file for JSON results"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="List supported formats and exit"
    )

    args = parser.parse_args()

    # List formats
    if args.list_formats:
        print("Supported formats:")
        for name in sorted(set(IMPORTERS.keys())):
            print(f"  - {name}")
        return 0

    # Get content
    if args.stdin:
        content = sys.stdin.read()
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            return 1
        content = file_path.read_text()
    else:
        parser.print_help()
        return 1

    if not content.strip():
        print("Error: Empty input", file=sys.stderr)
        return 1

    try:
        result = diagnose_trace(content, args.format, args.verbose)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    # Convert result to dict for JSON output
    result_dict = {
        "trace_id": result.trace_id,
        "analyzed_at": result.analyzed_at.isoformat() if isinstance(result.analyzed_at, datetime) else result.analyzed_at,
        "has_failures": result.has_failures,
        "failure_count": result.failure_count,
        "total_spans": result.total_spans,
        "error_spans": result.error_spans,
        "total_tokens": result.total_tokens,
        "duration_ms": result.duration_ms,
        "detection_time_ms": result.detection_time_ms,
        "detectors_run": result.detectors_run,
        "self_healing_available": result.self_healing_available,
        "all_detections": [
            {
                "category": d.category.value if hasattr(d.category, 'value') else str(d.category),
                "severity": d.severity.value if hasattr(d.severity, 'value') else str(d.severity),
                "title": d.title,
                "description": d.description,
                "confidence": d.confidence,
                "evidence": d.evidence,
                "affected_spans": d.affected_spans,
                "suggested_fix": d.suggested_fix,
            }
            for d in result.all_detections
        ],
    }

    if result.primary_failure:
        pf = result.primary_failure
        result_dict["primary_failure"] = {
            "category": pf.category.value if hasattr(pf.category, 'value') else str(pf.category),
            "severity": pf.severity.value if hasattr(pf.severity, 'value') else str(pf.severity),
            "title": pf.title,
            "description": pf.description,
            "confidence": pf.confidence,
            "suggested_fix": pf.suggested_fix,
        }

    if result.root_cause_explanation:
        result_dict["root_cause_explanation"] = result.root_cause_explanation

    if result.auto_fix_preview:
        if isinstance(result.auto_fix_preview, dict):
            result_dict["auto_fix_preview"] = result.auto_fix_preview
        else:
            result_dict["auto_fix_preview"] = {
                "description": result.auto_fix_preview.description,
                "confidence": result.auto_fix_preview.confidence,
                "action": result.auto_fix_preview.action,
            }

    # Output JSON
    if args.json:
        print(json.dumps(result_dict, indent=2))
    elif args.output:
        with open(args.output, 'w') as f:
            json.dump(result_dict, f, indent=2)
        print(f"Results saved to {args.output}")
    else:
        # Pretty print
        print_header("Agent Forensics - Diagnosis Report")

        # Summary
        if result.has_failures:
            status = colorize(f"✗ {result.failure_count} ISSUE(S) DETECTED", "red")
        else:
            status = colorize("✓ NO ISSUES DETECTED", "green")

        print(f"\n  Status: {status}")
        print(f"  Trace ID: {result.trace_id}")
        print(f"  Spans analyzed: {result.total_spans} ({result.error_spans} errors)")
        print(f"  Tokens: {result.total_tokens:,}")
        print(f"  Analysis time: {result.detection_time_ms}ms")

        # Root cause
        if result.root_cause_explanation:
            print_header("Root Cause Analysis")
            print(f"\n  {result.root_cause_explanation[:500]}")

        # Detections
        if result.all_detections:
            print_header(f"Detections ({len(result.all_detections)})")
            for i, detection in enumerate(result.all_detections, 1):
                print_detection(detection, i)

        # Self-healing
        if result.self_healing_available and result.auto_fix_preview:
            print_header("Self-Healing Available")
            fix = result.auto_fix_preview
            if isinstance(fix, dict):
                print(f"\n  {colorize('Auto-fix:', 'purple')} {fix.get('description', '')}")
                print(f"  Confidence: {fix.get('confidence', 0):.0%}")
                print(f"  Action: {fix.get('action', '')}")
            else:
                print(f"\n  {colorize('Auto-fix:', 'purple')} {fix.description}")
                print(f"  Confidence: {fix.confidence:.0%}")
                print(f"  Action: {fix.action}")

        print(f"\n{colorize('─' * 60, 'cyan')}\n")

    return 0 if not result.has_failures else 1


if __name__ == "__main__":
    sys.exit(main())
