"""Adaptive Thinking Variance Detection.

Detects issues with Claude's adaptive thinking mode (early 2026).

Uses STATISTICAL BASELINES from real Claude Code data (P95, Z-score) instead
of fixed thresholds. Baselines computed from 908 real subagent transcripts.

Real data distribution (from 1,758 transcripts):
  P50=$0.79, P75=$4.21, P90=$12.58, P95=$26.01, Max=$1,367
  Mean=$7.40, Stdev=$59.87

Detection method: Z-score + percentile hybrid (CALM framework, March 2026).

EXPERIMENTAL: Calibrated against real Claude Code usage data.
"""

import json
import os
from typing import List, Optional, Tuple

# Load baselines if available
_BASELINES = None

def _load_baselines():
    global _BASELINES
    if _BASELINES is not None:
        return _BASELINES
    baseline_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "detector_baselines.json")
    try:
        with open(baseline_path) as f:
            _BASELINES = json.load(f).get("adaptive_thinking", {}).get("cost", {})
    except (FileNotFoundError, json.JSONDecodeError):
        _BASELINES = {}
    return _BASELINES


def detect(
    effort_level: str = "high",
    thinking_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    cost_usd: float = 0.0,
    prompt: str = "",
    output: str = "",
    baseline_costs: Optional[List[float]] = None,
) -> Tuple[bool, float]:
    scores = []
    baselines = _load_baselines()

    # ── 1. COST ANOMALY — Statistical baseline (primary signal) ──
    if cost_usd > 0:
        mean = baselines.get("mean", 7.4)
        stdev = baselines.get("stdev", 59.9)
        p95 = baselines.get("p95", 26.0)

        # Use caller-provided baselines if available
        if baseline_costs and len(baseline_costs) >= 10:
            from statistics import mean as _mean, stdev as _stdev
            mean = _mean(baseline_costs)
            stdev = _stdev(baseline_costs) if len(baseline_costs) > 1 else mean * 0.5
            sorted_costs = sorted(baseline_costs)
            p95 = sorted_costs[int(len(sorted_costs) * 0.95)]

        # Z-score: catches severe outliers (>2.5 standard deviations)
        if stdev > 0:
            z_score = (cost_usd - mean) / stdev
            if z_score > 2.5:
                scores.append(min(1.0, z_score / 5.0))

        # Percentile: catches costs above P95 * 1.5
        dynamic_threshold = p95 * 1.5
        if cost_usd > dynamic_threshold:
            scores.append(min(1.0, cost_usd / (dynamic_threshold * 2)))

        # Fallback fixed threshold for extreme cases (no baseline)
        if not baselines and cost_usd > 1.00:
            scores.append(min(1.0, cost_usd / 2.0))

    # ── 2. OVERTHINKING RATIO ──
    if thinking_tokens > 0 and output_tokens > 0:
        ratio = thinking_tokens / output_tokens
        if ratio > 20:
            scores.append(min(1.0, (ratio - 20) / 30))

    # ── 3. UNDERTHINKING ──
    if effort_level == "low" and output_tokens > 0 and output_tokens < 20:
        scores.append(0.5)

    # ── 4. HIGH COST AT LOW EFFORT (misconfigured) ──
    if cost_usd > 0 and effort_level in ("low", "medium"):
        p75 = baselines.get("p75", 4.2)
        if cost_usd > p75:
            scores.append(0.6)

    # ── 5. TIMEOUT RISK ──
    if latency_ms > 180000:
        scores.append(min(1.0, latency_ms / 300000))
    elif latency_ms > 90000 and effort_level not in ("high", "max"):
        scores.append(0.4)

    if not scores:
        return False, 0.0
    return True, round(max(scores), 4)
