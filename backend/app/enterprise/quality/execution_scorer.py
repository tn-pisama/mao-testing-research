"""Execution-based quality scoring from actual workflow run results.

Integrates runtime performance data into quality scores, supplementing
static analysis with empirical evidence from workflow executions.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import statistics


@dataclass
class ExecutionDimensionScore:
    """Score for a single execution-derived dimension."""
    dimension: str
    score: float
    sample_count: int
    evidence: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)


@dataclass
class ExecutionScores:
    """Aggregated execution-based quality scores."""
    success_rate: ExecutionDimensionScore
    output_consistency: ExecutionDimensionScore
    error_rate: ExecutionDimensionScore
    retry_effectiveness: ExecutionDimensionScore
    latency_health: ExecutionDimensionScore
    overall_score: float = 0.0
    total_executions: int = 0

    def __post_init__(self):
        dims = [self.success_rate, self.output_consistency, self.error_rate,
                self.retry_effectiveness, self.latency_health]
        weights = [0.3, 0.2, 0.2, 0.15, 0.15]
        self.overall_score = sum(d.score * w for d, w in zip(dims, weights))
        self.total_executions = max(d.sample_count for d in dims) if dims else 0


class ExecutionQualityScorer:
    """Scores workflow quality based on actual execution history.

    Dimensions:
    - success_rate: % of executions completing successfully
    - output_consistency: Structural similarity across actual outputs
    - error_rate: % of executions hitting errors per agent node
    - retry_effectiveness: Of retried executions, % that eventually succeeded
    - latency_health: Flag agents with p95 latency > 3x median
    """

    def score_from_executions(
        self,
        execution_history: List[Dict[str, Any]],
    ) -> ExecutionScores:
        """Score quality from execution history.

        Args:
            execution_history: List of execution records, each containing:
                - status: "success" | "error" | "running" | "waiting"
                - duration_ms: execution time in milliseconds
                - node_results: dict of node_id -> {status, output, error, retries}
                - started_at: ISO timestamp
        """
        if not execution_history:
            return self._empty_scores()

        completed = [e for e in execution_history if e.get("status") in ("success", "error")]
        if not completed:
            return self._empty_scores()

        return ExecutionScores(
            success_rate=self._score_success_rate(completed),
            output_consistency=self._score_output_consistency(completed),
            error_rate=self._score_error_rate(completed),
            retry_effectiveness=self._score_retry_effectiveness(completed),
            latency_health=self._score_latency_health(completed),
        )

    def _score_success_rate(self, executions: List[Dict[str, Any]]) -> ExecutionDimensionScore:
        """Score based on overall execution success rate."""
        successful = sum(1 for e in executions if e.get("status") == "success")
        total = len(executions)
        rate = successful / total if total > 0 else 0

        issues = []
        if rate < 0.5:
            issues.append(f"Critical: Only {rate:.0%} of executions succeed ({successful}/{total})")
        elif rate < 0.8:
            issues.append(f"Warning: {rate:.0%} success rate ({successful}/{total})")

        return ExecutionDimensionScore(
            dimension="execution_success_rate",
            score=rate,
            sample_count=total,
            evidence={"successful": successful, "total": total, "rate": round(rate, 3)},
            issues=issues,
        )

    def _score_output_consistency(self, executions: List[Dict[str, Any]]) -> ExecutionDimensionScore:
        """Score output structural consistency across successful executions."""
        successful = [e for e in executions if e.get("status") == "success"]
        if len(successful) < 2:
            return ExecutionDimensionScore(
                dimension="execution_output_consistency",
                score=0.5,  # Insufficient data
                sample_count=len(successful),
                evidence={"reason": "insufficient_samples"},
            )

        # Collect output key structures per node
        node_structures: Dict[str, List[frozenset]] = {}
        for execution in successful:
            for node_id, result in execution.get("node_results", {}).items():
                output = result.get("output")
                if isinstance(output, dict):
                    keys = frozenset(output.keys())
                    node_structures.setdefault(node_id, []).append(keys)

        if not node_structures:
            return ExecutionDimensionScore(
                dimension="execution_output_consistency",
                score=0.5,
                sample_count=len(successful),
                evidence={"reason": "no_structured_outputs"},
            )

        # Calculate consistency per node
        consistencies = []
        inconsistent_nodes = []
        for node_id, structures in node_structures.items():
            if len(structures) < 2:
                continue
            unique = len(set(structures))
            consistency = 1.0 / unique
            consistencies.append(consistency)
            if unique > 1:
                inconsistent_nodes.append(node_id)

        if not consistencies:
            return ExecutionDimensionScore(
                dimension="execution_output_consistency",
                score=0.7,
                sample_count=len(successful),
                evidence={"reason": "single_sample_per_node"},
            )

        avg_consistency = statistics.mean(consistencies)
        issues = []
        if inconsistent_nodes:
            issues.append(f"{len(inconsistent_nodes)} node(s) produce inconsistent output structures")

        return ExecutionDimensionScore(
            dimension="execution_output_consistency",
            score=avg_consistency,
            sample_count=len(successful),
            evidence={
                "avg_consistency": round(avg_consistency, 3),
                "inconsistent_nodes": inconsistent_nodes[:5],
            },
            issues=issues,
        )

    def _score_error_rate(self, executions: List[Dict[str, Any]]) -> ExecutionDimensionScore:
        """Score based on per-node error rates."""
        node_errors: Dict[str, int] = {}
        node_runs: Dict[str, int] = {}

        for execution in executions:
            for node_id, result in execution.get("node_results", {}).items():
                node_runs[node_id] = node_runs.get(node_id, 0) + 1
                if result.get("status") == "error":
                    node_errors[node_id] = node_errors.get(node_id, 0) + 1

        if not node_runs:
            return ExecutionDimensionScore(
                dimension="execution_error_rate",
                score=0.5,
                sample_count=len(executions),
                evidence={"reason": "no_node_results"},
            )

        # Calculate per-node error rates
        error_rates = {}
        problem_nodes = []
        for node_id in node_runs:
            errors = node_errors.get(node_id, 0)
            rate = errors / node_runs[node_id]
            error_rates[node_id] = round(rate, 3)
            if rate > 0.1:
                problem_nodes.append((node_id, rate))

        # Overall score: 1.0 - average error rate
        avg_error_rate = statistics.mean(error_rates.values()) if error_rates else 0
        score = max(0.0, 1.0 - avg_error_rate)

        issues = []
        for node_id, rate in sorted(problem_nodes, key=lambda x: -x[1])[:3]:
            issues.append(f"Node '{node_id}' has {rate:.0%} error rate")

        return ExecutionDimensionScore(
            dimension="execution_error_rate",
            score=score,
            sample_count=len(executions),
            evidence={"avg_error_rate": round(avg_error_rate, 3), "problem_nodes": problem_nodes[:5]},
            issues=issues,
        )

    def _score_retry_effectiveness(self, executions: List[Dict[str, Any]]) -> ExecutionDimensionScore:
        """Score how effective retries are at recovering from failures."""
        retried = 0
        retry_success = 0

        for execution in executions:
            for result in execution.get("node_results", {}).values():
                retries = result.get("retries", 0)
                if retries > 0:
                    retried += 1
                    if result.get("status") == "success":
                        retry_success += 1

        if retried == 0:
            return ExecutionDimensionScore(
                dimension="execution_retry_effectiveness",
                score=0.7,  # No retries needed is good
                sample_count=len(executions),
                evidence={"reason": "no_retries_observed", "retried": 0},
            )

        effectiveness = retry_success / retried if retried > 0 else 0

        issues = []
        if effectiveness < 0.3:
            issues.append(f"Retries rarely help: only {effectiveness:.0%} recover ({retry_success}/{retried})")
        elif effectiveness < 0.6:
            issues.append(f"Retry effectiveness is moderate: {effectiveness:.0%} ({retry_success}/{retried})")

        return ExecutionDimensionScore(
            dimension="execution_retry_effectiveness",
            score=effectiveness,
            sample_count=retried,
            evidence={"retried": retried, "retry_success": retry_success, "effectiveness": round(effectiveness, 3)},
            issues=issues,
        )

    def _score_latency_health(self, executions: List[Dict[str, Any]]) -> ExecutionDimensionScore:
        """Score based on latency distribution — flag abnormal outliers."""
        durations = [e.get("duration_ms", 0) for e in executions if e.get("duration_ms")]

        if len(durations) < 3:
            return ExecutionDimensionScore(
                dimension="execution_latency_health",
                score=0.7,
                sample_count=len(durations),
                evidence={"reason": "insufficient_latency_data"},
            )

        median_ms = statistics.median(durations)
        p95 = sorted(durations)[int(len(durations) * 0.95)]

        issues = []
        # Score based on p95/median ratio
        ratio = p95 / median_ms if median_ms > 0 else 1
        if ratio > 5:
            score = 0.3
            issues.append(f"Severe latency spikes: p95 ({p95:.0f}ms) is {ratio:.1f}x median ({median_ms:.0f}ms)")
        elif ratio > 3:
            score = 0.5
            issues.append(f"Latency spikes: p95 ({p95:.0f}ms) is {ratio:.1f}x median ({median_ms:.0f}ms)")
        elif ratio > 2:
            score = 0.7
        else:
            score = 0.9

        return ExecutionDimensionScore(
            dimension="execution_latency_health",
            score=score,
            sample_count=len(durations),
            evidence={
                "median_ms": round(median_ms, 1),
                "p95_ms": round(p95, 1),
                "p95_median_ratio": round(ratio, 2),
                "min_ms": round(min(durations), 1),
                "max_ms": round(max(durations), 1),
            },
            issues=issues,
        )

    def _empty_scores(self) -> ExecutionScores:
        """Return empty scores when no execution data is available."""
        empty = ExecutionDimensionScore(
            dimension="no_data", score=0.0, sample_count=0,
            evidence={"reason": "no_execution_history"}, issues=["No execution history available"],
        )
        return ExecutionScores(
            success_rate=empty,
            output_consistency=empty,
            error_rate=empty,
            retry_effectiveness=empty,
            latency_health=empty,
        )
