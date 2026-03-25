"""Predictive Failure Detection — Early Warning System.

Detects failures BEFORE they happen by recognizing early warning signals:
- Token usage trend climbing toward context limit
- Response quality declining over time
- Error rate increasing
- Output length shrinking (context pressure)
- Tool call failure rate rising

Extends the context_pressure detector with time-series prediction.

No competitor has this — prevention > detection > fixing.
"""

import logging
import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PredictiveWarning:
    """An early warning of impending failure."""
    warning_type: str  # token_exhaustion, quality_decline, error_spiral, etc.
    severity: str  # low, medium, high, critical
    predicted_failure_type: str  # What failure we predict
    time_to_failure: Optional[int]  # Estimated steps until failure
    confidence: float  # How confident are we in this prediction
    evidence: str  # What data supports this prediction
    recommended_action: str  # What to do about it


@dataclass
class PredictiveResult:
    """Result of predictive analysis on a trace sequence."""
    warnings: List[PredictiveWarning]
    risk_score: float  # 0.0 = no risk, 1.0 = imminent failure
    healthy: bool  # No warnings above low severity
    trends: Dict[str, float]  # Named trend values


class PredictiveDetector:
    """Predicts failures from time-series trends in trace data.

    Analyzes sequences of states/steps to detect deteriorating trends
    that precede common failure modes:

    1. Token Exhaustion: cumulative tokens approaching context limit
    2. Quality Decline: output quality metrics trending downward
    3. Error Spiral: error rate accelerating
    4. Repetition Onset: increasing similarity between consecutive outputs
    5. Stall Detection: steps taking progressively longer
    """

    def __init__(
        self,
        token_warning_threshold: float = 0.7,  # Warn at 70% context usage
        quality_decline_sigma: float = 2.0,  # 2σ decline triggers warning
        error_rate_threshold: float = 0.3,  # 30% error rate triggers warning
        min_steps: int = 5,  # Need at least 5 steps for trend analysis
    ):
        self.token_warning_threshold = token_warning_threshold
        self.quality_decline_sigma = quality_decline_sigma
        self.error_rate_threshold = error_rate_threshold
        self.min_steps = min_steps

    def predict(
        self,
        steps: List[Dict[str, Any]],
        context_limit: int = 200_000,
    ) -> PredictiveResult:
        """Analyze a sequence of steps for failure precursors.

        Args:
            steps: List of step dicts with metrics (tokens, output, status, etc.)
            context_limit: Model context window size
        """
        if len(steps) < self.min_steps:
            return PredictiveResult(
                warnings=[], risk_score=0.0, healthy=True,
                trends={"note": "too few steps for prediction"},
            )

        warnings = []
        trends = {}

        # 1. Token Exhaustion Prediction
        w, t = self._predict_token_exhaustion(steps, context_limit)
        if w:
            warnings.append(w)
        trends.update(t)

        # 2. Quality Decline Detection
        w, t = self._predict_quality_decline(steps)
        if w:
            warnings.append(w)
        trends.update(t)

        # 3. Error Spiral Detection
        w, t = self._predict_error_spiral(steps)
        if w:
            warnings.append(w)
        trends.update(t)

        # 4. Repetition Onset
        w, t = self._predict_repetition_onset(steps)
        if w:
            warnings.append(w)
        trends.update(t)

        # 5. Stall Detection
        w, t = self._predict_stall(steps)
        if w:
            warnings.append(w)
        trends.update(t)

        # Compute overall risk score
        if not warnings:
            risk_score = 0.0
        else:
            risk_score = min(1.0, max(w.confidence for w in warnings))

        healthy = all(w.severity in ("low",) for w in warnings) if warnings else True

        return PredictiveResult(
            warnings=warnings,
            risk_score=round(risk_score, 4),
            healthy=healthy,
            trends=trends,
        )

    def _predict_token_exhaustion(
        self, steps: List[Dict], context_limit: int
    ) -> tuple:
        """Predict when tokens will exhaust the context window."""
        token_counts = [s.get("token_count", s.get("tokens", 0)) for s in steps]
        token_counts = [t for t in token_counts if t > 0]

        if len(token_counts) < 3:
            return None, {"token_trend": 0}

        # Linear regression on token growth
        n = len(token_counts)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(token_counts)
        slope = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(token_counts)) / max(1, sum((i - x_mean) ** 2 for i in range(n)))

        current = token_counts[-1]
        usage_ratio = current / context_limit if context_limit > 0 else 0
        trends = {"token_trend": round(slope, 2), "token_usage": round(usage_ratio, 4)}

        if usage_ratio > self.token_warning_threshold and slope > 0:
            steps_remaining = int((context_limit - current) / max(slope, 1))
            severity = "critical" if usage_ratio > 0.9 else "high" if usage_ratio > 0.8 else "medium"
            return PredictiveWarning(
                warning_type="token_exhaustion",
                severity=severity,
                predicted_failure_type="overflow",
                time_to_failure=max(1, steps_remaining),
                confidence=min(1.0, usage_ratio + 0.1),
                evidence=f"Token usage at {usage_ratio:.0%}, growing at {slope:.0f} tokens/step",
                recommended_action="Implement context pruning or conversation summarization",
            ), trends

        return None, trends

    def _predict_quality_decline(self, steps: List[Dict]) -> tuple:
        """Detect declining output quality."""
        lengths = []
        for s in steps:
            out = s.get("output", s.get("state_delta", {}).get("output", ""))
            lengths.append(len(str(out)) if out else 0)

        if len(lengths) < 5 or all(l == 0 for l in lengths):
            return None, {"quality_trend": 0}

        # Compare first third vs last third
        third = max(1, len(lengths) // 3)
        early = statistics.mean(lengths[:third]) if lengths[:third] else 0
        late = statistics.mean(lengths[-third:]) if lengths[-third:] else 0

        if early == 0:
            return None, {"quality_trend": 0}

        decline_ratio = late / early
        trends = {"quality_trend": round(decline_ratio, 4)}

        if decline_ratio < 0.5:  # Output length dropped by >50%
            return PredictiveWarning(
                warning_type="quality_decline",
                severity="high" if decline_ratio < 0.3 else "medium",
                predicted_failure_type="context_pressure",
                time_to_failure=max(1, int(len(steps) * 0.2)),
                confidence=round(1.0 - decline_ratio, 4),
                evidence=f"Output length declined {(1-decline_ratio)*100:.0f}% from early to late steps",
                recommended_action="Reset context or increase model context window",
            ), trends

        return None, trends

    def _predict_error_spiral(self, steps: List[Dict]) -> tuple:
        """Detect accelerating error rate."""
        statuses = [str(s.get("status", "")).lower() for s in steps]
        errors = [1 if s in ("error", "failed", "timeout") else 0 for s in statuses]

        if not errors or sum(errors) == 0:
            return None, {"error_rate": 0}

        # Error rate in last 30% of steps
        tail_start = max(1, int(len(errors) * 0.7))
        tail_errors = errors[tail_start:]
        tail_rate = sum(tail_errors) / max(1, len(tail_errors))
        overall_rate = sum(errors) / len(errors)

        trends = {"error_rate": round(overall_rate, 4), "tail_error_rate": round(tail_rate, 4)}

        if tail_rate > self.error_rate_threshold and tail_rate > overall_rate * 1.5:
            return PredictiveWarning(
                warning_type="error_spiral",
                severity="critical" if tail_rate > 0.5 else "high",
                predicted_failure_type="coordination",
                time_to_failure=max(1, int((1 - tail_rate) * 10)),
                confidence=round(tail_rate, 4),
                evidence=f"Error rate {tail_rate:.0%} in recent steps (overall {overall_rate:.0%})",
                recommended_action="Add circuit breaker or fallback mechanisms",
            ), trends

        return None, trends

    def _predict_repetition_onset(self, steps: List[Dict]) -> tuple:
        """Detect increasing repetition (loop precursor)."""
        outputs = [str(s.get("content", s.get("output", "")))[:200] for s in steps]
        if len(outputs) < 4:
            return None, {"repetition_rate": 0}

        # Count consecutive identical outputs
        repeats = 0
        for i in range(1, len(outputs)):
            if outputs[i] == outputs[i-1] and len(outputs[i]) > 10:
                repeats += 1

        repeat_rate = repeats / max(1, len(outputs) - 1)
        trends = {"repetition_rate": round(repeat_rate, 4)}

        if repeat_rate > 0.3:
            return PredictiveWarning(
                warning_type="repetition_onset",
                severity="high" if repeat_rate > 0.5 else "medium",
                predicted_failure_type="loop",
                time_to_failure=max(1, int((1 - repeat_rate) * 5)),
                confidence=round(repeat_rate, 4),
                evidence=f"{repeats} consecutive repeated outputs ({repeat_rate:.0%} repeat rate)",
                recommended_action="Add loop detection with max_iterations limit",
            ), trends

        return None, trends

    def _predict_stall(self, steps: List[Dict]) -> tuple:
        """Detect steps taking progressively longer (stall precursor)."""
        durations = [s.get("duration_ms", s.get("elapsed_time", 0)) for s in steps]
        durations = [d for d in durations if d and d > 0]

        if len(durations) < 4:
            return None, {"latency_trend": 0}

        third = max(1, len(durations) // 3)
        early_avg = statistics.mean(durations[:third])
        late_avg = statistics.mean(durations[-third:])

        if early_avg == 0:
            return None, {"latency_trend": 0}

        slowdown = late_avg / early_avg
        trends = {"latency_trend": round(slowdown, 4)}

        if slowdown > 3.0:  # Steps taking 3x longer
            return PredictiveWarning(
                warning_type="stall_detected",
                severity="high" if slowdown > 5 else "medium",
                predicted_failure_type="n8n_timeout",
                time_to_failure=None,
                confidence=round(min(1.0, slowdown / 10), 4),
                evidence=f"Steps slowed down {slowdown:.1f}x (early avg {early_avg:.0f}ms → late avg {late_avg:.0f}ms)",
                recommended_action="Add execution timeout and performance monitoring",
            ), trends

        return None, trends


# Singleton
predictive_detector = PredictiveDetector()
