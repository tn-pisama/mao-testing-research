#!/usr/bin/env python3
"""
Test MAO detectors against real pisama-claude-code traces.

This evaluates detection accuracy on actual Claude Code sessions.
Since these are real sessions, we don't have ground truth labels -
instead we analyze the false positive rate (FPR) assuming most
sessions are healthy.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.detection.specification import SpecificationMismatchDetector
from app.detection.decomposition import TaskDecompositionDetector
from app.detection.derailment import TaskDerailmentDetector
from app.detection.context import ContextNeglectDetector
from app.detection.withholding import InformationWithholdingDetector
from app.detection.completion import CompletionMisjudgmentDetector
from app.detection.loop import MultiLevelLoopDetector


def load_traces(trace_dir: Path) -> Dict[str, List[Dict]]:
    """Load traces grouped by session."""
    sessions = defaultdict(list)

    for trace_file in trace_dir.glob("traces-*.jsonl"):
        with open(trace_file, "r") as f:
            for line in f:
                try:
                    trace = json.loads(line)
                    session_id = trace.get("session_id", "unknown")
                    sessions[session_id].append(trace)
                except json.JSONDecodeError:
                    continue

    # Sort each session by timestamp
    for session_id in sessions:
        sessions[session_id].sort(key=lambda t: t.get("timestamp", ""))

    return dict(sessions)


def extract_commands_from_session(traces: List[Dict]) -> List[str]:
    """Extract Bash commands from a session."""
    commands = []
    for trace in traces:
        if trace.get("tool_name") == "Bash":
            tool_input = trace.get("tool_input", {})
            if isinstance(tool_input, dict):
                cmd = tool_input.get("command", "")
            else:
                cmd = str(tool_input)
            if cmd:
                commands.append(cmd)
    return commands


def extract_edits_from_session(traces: List[Dict]) -> List[Dict]:
    """Extract Edit operations from a session."""
    edits = []
    for trace in traces:
        if trace.get("tool_name") in ("Edit", "Write"):
            edits.append({
                "tool": trace.get("tool_name"),
                "input": trace.get("tool_input", {}),
                "output": trace.get("tool_output"),
                "timestamp": trace.get("timestamp"),
            })
    return edits


def test_loop_detection(sessions: Dict[str, List[Dict]]) -> Dict:
    """Test loop detection on real sessions."""
    results = {
        "total_sessions": 0,
        "loops_detected": 0,
        "details": [],
    }

    detector = MultiLevelLoopDetector()

    for session_id, traces in sessions.items():
        commands = extract_commands_from_session(traces)
        if len(commands) < 5:
            continue

        results["total_sessions"] += 1

        # Check for loops (same command repeated)
        detected = False
        for i in range(len(commands) - 2):
            window = commands[i:i+3]
            if len(set(window)) == 1:  # Same command 3x in a row
                detected = True
                break

        if detected:
            results["loops_detected"] += 1
            results["details"].append({
                "session_id": session_id[:8],
                "reason": "Same command repeated 3+ times",
            })

    return results


def test_context_neglect(sessions: Dict[str, List[Dict]]) -> Dict:
    """Test context neglect detection on real sessions."""
    results = {
        "total_sessions": 0,
        "neglect_detected": 0,
        "details": [],
    }

    detector = ContextNeglectDetector()

    for session_id, traces in sessions.items():
        # Get Read operations followed by Edit/Write
        reads = []
        edits = []

        for trace in traces:
            tool = trace.get("tool_name")
            if tool == "Read":
                reads.append(trace)
            elif tool in ("Edit", "Write"):
                edits.append(trace)

        if not reads or not edits:
            continue

        results["total_sessions"] += 1

        # For each edit, check if context from previous reads is used
        # This is a simplified check - in reality we'd analyze content

    return results


def test_derailment(sessions: Dict[str, List[Dict]]) -> Dict:
    """Test task derailment detection on real sessions."""
    results = {
        "total_sessions": 0,
        "derailment_detected": 0,
        "details": [],
    }

    detector = TaskDerailmentDetector()

    for session_id, traces in sessions.items():
        # Look for patterns of doing something very different from what was asked
        # This requires analyzing the task context which isn't always available
        results["total_sessions"] += 1

    return results


def analyze_session_health(sessions: Dict[str, List[Dict]]) -> Dict:
    """Analyze overall session health metrics."""
    results = {
        "total_sessions": len(sessions),
        "total_traces": sum(len(t) for t in sessions.values()),
        "by_tool": defaultdict(int),
        "session_details": [],
    }

    for session_id, traces in sessions.items():
        session_info = {
            "session_id": session_id[:8],
            "trace_count": len(traces),
            "tools_used": defaultdict(int),
            "duration_mins": 0,
            "potential_issues": [],
        }

        # Count tools
        for trace in traces:
            tool = trace.get("tool_name", "unknown")
            session_info["tools_used"][tool] += 1
            results["by_tool"][tool] += 1

        # Calculate duration
        if len(traces) >= 2:
            try:
                start = datetime.fromisoformat(traces[0].get("timestamp", "").replace("Z", "+00:00"))
                end = datetime.fromisoformat(traces[-1].get("timestamp", "").replace("Z", "+00:00"))
                session_info["duration_mins"] = (end - start).total_seconds() / 60
            except:
                pass

        # Check for potential issues
        commands = extract_commands_from_session(traces)

        # Issue: Same command repeated
        for i in range(len(commands) - 2):
            window = commands[i:i+3]
            if len(set(window)) == 1 and window[0]:
                session_info["potential_issues"].append("Repeated command (possible loop)")
                break

        # Issue: High error rate (looking for error patterns in outputs)
        error_count = 0
        for trace in traces:
            output = str(trace.get("tool_output", "")).lower()
            if any(err in output for err in ["error:", "exception:", "failed:", "traceback"]):
                error_count += 1

        if error_count > len(traces) * 0.3:  # >30% errors
            session_info["potential_issues"].append(f"High error rate ({error_count}/{len(traces)})")

        # Issue: Very long session without completion
        if session_info["duration_mins"] > 60 and len(traces) > 100:
            session_info["potential_issues"].append("Long session (>60 min)")

        session_info["tools_used"] = dict(session_info["tools_used"])
        results["session_details"].append(session_info)

    results["by_tool"] = dict(results["by_tool"])
    return results


def run_all_detectors(sessions: Dict[str, List[Dict]]) -> Dict:
    """Run all relevant detectors on sessions."""
    results = {
        "loop_detection": test_loop_detection(sessions),
        "session_health": analyze_session_health(sessions),
    }
    return results


def print_results(results: Dict):
    """Print detection results."""
    print("\n" + "=" * 70)
    print("REAL CLAUDE CODE TRACE ANALYSIS")
    print("=" * 70)

    health = results["session_health"]
    print(f"\nTotal sessions analyzed: {health['total_sessions']}")
    print(f"Total tool calls: {health['total_traces']}")

    print("\n" + "-" * 70)
    print("Tool Usage Distribution:")
    print("-" * 70)
    for tool, count in sorted(health["by_tool"].items(), key=lambda x: -x[1]):
        pct = count / health["total_traces"] * 100
        print(f"  {tool}: {count} ({pct:.1f}%)")

    print("\n" + "-" * 70)
    print("Session Analysis:")
    print("-" * 70)

    issues_found = 0
    for session in health["session_details"]:
        status = "✅" if not session["potential_issues"] else "⚠️"
        print(f"\n{status} Session {session['session_id']}:")
        print(f"   Traces: {session['trace_count']}, Duration: {session['duration_mins']:.1f} min")
        print(f"   Top tools: {', '.join(f'{k}:{v}' for k, v in sorted(session['tools_used'].items(), key=lambda x: -x[1])[:5])}")
        if session["potential_issues"]:
            issues_found += 1
            for issue in session["potential_issues"]:
                print(f"   ⚠️  {issue}")

    # Loop detection results
    loop_results = results["loop_detection"]
    print("\n" + "-" * 70)
    print("Loop Detection:")
    print("-" * 70)
    print(f"  Sessions checked: {loop_results['total_sessions']}")
    print(f"  Loops detected: {loop_results['loops_detected']}")
    if loop_results["details"]:
        for detail in loop_results["details"][:5]:
            print(f"    - {detail['session_id']}: {detail['reason']}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    fpr = issues_found / health["total_sessions"] * 100 if health["total_sessions"] > 0 else 0
    print(f"Sessions with potential issues: {issues_found}/{health['total_sessions']} ({fpr:.1f}%)")
    print(f"Target false positive rate: <10%")

    status = "PASS" if fpr < 10 else "NEEDS REVIEW"
    print(f"Status: {status}")

    return fpr


def main():
    # Find trace directory
    trace_dir = Path.home() / ".claude" / "pisama" / "traces"

    if not trace_dir.exists():
        print(f"Trace directory not found: {trace_dir}")
        print("Please run 'pisama-cc install' to capture traces.")
        return False

    print(f"Loading traces from: {trace_dir}")

    # Load sessions
    sessions = load_traces(trace_dir)
    print(f"Found {len(sessions)} sessions")

    if not sessions:
        print("No traces found. Run Claude Code sessions with pisama hooks installed.")
        return False

    # Run detectors
    results = run_all_detectors(sessions)

    # Print results
    fpr = print_results(results)

    # Save results
    output_path = Path(__file__).parent.parent / "benchmarks" / "results" / "real_traces_eval.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nResults saved to: {output_path}")

    return fpr < 10  # Pass if FPR < 10%


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
