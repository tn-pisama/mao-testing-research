"""Scheduled Task Drift Detection — Recurring Run Quality.

Detects degradation in /loop scheduled recurring tasks.
Thresholds calibrated against real /loop behavior:
- /loop has 90s timing jitter by design (tasks fire up to 90s early)
- 3-day auto-expiry forces periodic review
- Silent failures are the #1 real issue (no external notification)

EXPERIMENTAL: Based on documentation + user reports. Will improve with production traces.
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

    # 1. Latency drift: flag at 50%+ increase (not 20% — some jitter is normal)
    latencies = [r.get("latency_ms", 0) for r in run_list if r.get("latency_ms")]
    if len(latencies) >= 4:
        first_half = sum(latencies[:len(latencies) // 2]) / max(len(latencies) // 2, 1)
        second_half = sum(latencies[len(latencies) // 2:]) / max(len(latencies) - len(latencies) // 2, 1)
        if first_half > 0 and second_half > first_half * 1.5:
            drift_ratio = second_half / first_half
            scores.append(min(1.0, (drift_ratio - 1.5) * 2))  # 1.5x→0, 2.0x→1.0

    # 2. Output staleness: 98%+ overlap across 3+ consecutive runs
    # (not 95% across 2 — recurring reports legitimately repeat structure)
    stale_streak = 0
    max_stale_streak = 0
    for i in range(1, len(run_list)):
        prev = str(run_list[i - 1].get("output_summary", ""))
        curr = str(run_list[i].get("output_summary", ""))
        if prev and curr:
            prev_words = set(prev.lower().split())
            curr_words = set(curr.lower().split())
            if prev_words:
                overlap = len(prev_words & curr_words) / max(min(len(prev_words), len(curr_words)), 1)
                if overlap > 0.98:
                    stale_streak += 1
                    max_stale_streak = max(max_stale_streak, stale_streak)
                else:
                    stale_streak = 0
    if max_stale_streak >= 3:
        scores.append(min(1.0, max_stale_streak * 0.25))

    # 3. Skipped executions: gap > 3x interval (/loop has 90s jitter, so 2x is normal)
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
            if gap_ms > schedule_interval_ms * 3:
                skips += 1
        if skips > 0:
            scores.append(min(1.0, skips * 0.35))

    # 4. Error escalation: increasing error rate in second half of runs
    errors = [1 if r.get("error") else 0 for r in run_list]
    if len(errors) >= 4:
        first_errors = sum(errors[:len(errors) // 2])
        second_errors = sum(errors[len(errors) // 2:])
        if second_errors > first_errors + 1 and second_errors >= 2:
            scores.append(min(1.0, second_errors * 0.25))

    # 5. All runs failed (silent failure pattern — the #1 real issue)
    if len(run_list) >= 3 and all(r.get("error") for r in run_list):
        scores.append(0.9)

    if not scores:
        return False, 0.0
    return True, round(max(scores), 4)
