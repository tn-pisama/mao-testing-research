"""Scheduled Task Drift Detection — Recurring Run Quality.

Detects degradation in /loop scheduled recurring tasks:
- Latency drift (runs getting slower)
- Output staleness (identical outputs across runs)
- Skipped executions (gaps > 2x interval)
- Error rate escalation

Based on Claude Code Scheduled Tasks (early 2026).
"""

from typing import Any, Dict, List, Tuple

def detect(
    runs: List[Dict[str, Any]] = None,
    schedule_interval_ms: int = 0,
) -> Tuple[bool, float]:
    run_list = runs or []
    if len(run_list) < 3:
        return False, 0.0

    scores = []

    # 1. Latency drift: trend increasing > 20% per run
    latencies = [r.get("latency_ms", 0) for r in run_list if r.get("latency_ms")]
    if len(latencies) >= 3:
        first_half = sum(latencies[:len(latencies) // 2]) / max(len(latencies) // 2, 1)
        second_half = sum(latencies[len(latencies) // 2:]) / max(len(latencies) - len(latencies) // 2, 1)
        if first_half > 0 and second_half > first_half * 1.2:
            drift_ratio = second_half / first_half
            scores.append(min(1.0, (drift_ratio - 1.0) * 2))

    # 2. Output staleness: consecutive runs with >95% word overlap
    stale_count = 0
    for i in range(1, len(run_list)):
        prev = str(run_list[i - 1].get("output_summary", ""))
        curr = str(run_list[i].get("output_summary", ""))
        if prev and curr:
            prev_words = set(prev.lower().split())
            curr_words = set(curr.lower().split())
            if prev_words:
                overlap = len(prev_words & curr_words) / max(min(len(prev_words), len(curr_words)), 1)
                if overlap > 0.95:
                    stale_count += 1
    if stale_count >= 2:
        scores.append(min(1.0, stale_count * 0.3))

    # 3. Skipped executions: gap > 2x interval
    if schedule_interval_ms > 0:
        timestamps = []
        for r in run_list:
            ts = r.get("timestamp", "")
            if ts:
                try:
                    from datetime import datetime
                    timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
                except (ValueError, TypeError):
                    pass
        skips = 0
        for i in range(1, len(timestamps)):
            gap_ms = (timestamps[i] - timestamps[i - 1]).total_seconds() * 1000
            if gap_ms > schedule_interval_ms * 2:
                skips += 1
        if skips > 0:
            scores.append(min(1.0, skips * 0.4))

    # 4. Error escalation: increasing error rate across runs
    errors = [1 if r.get("error") else 0 for r in run_list]
    if len(errors) >= 4:
        first_half_errors = sum(errors[:len(errors) // 2])
        second_half_errors = sum(errors[len(errors) // 2:])
        if second_half_errors > first_half_errors and second_half_errors >= 2:
            scores.append(min(1.0, second_half_errors * 0.3))

    if not scores:
        return False, 0.0
    return True, round(max(scores), 4)
