#!/usr/bin/env python3
"""Claude Model Comparison Benchmark

Compares all Claude model variants for MAST detection to find optimal
performance vs cost tradeoff.

Models tested:
- opus-4.5: Highest quality ($15/$75 per 1M tokens)
- opus-4.5-thinking: With extended thinking (+$10/1M thinking tokens)
- sonnet-4: Balanced ($3/$15 per 1M tokens)
- sonnet-4-thinking: With extended thinking
- sonnet-3.5: Previous gen ($3/$15 per 1M tokens)
- haiku-3.5: Fast and cheap ($0.80/$4 per 1M tokens)

Usage:
    python benchmarks/evaluation/claude_model_comparison.py --traces-per-model 100
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Load environment from .env.development if it exists
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / "backend" / ".env.development"
if _ENV_FILE.exists():
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                # Remove quotes if present
                value = value.strip('"').strip("'")
                if key not in os.environ:  # Don't override existing env vars
                    os.environ[key] = value

# Add backend to path
_BACKEND_PATH = str(_PROJECT_ROOT / "backend")
sys.path.insert(0, _BACKEND_PATH)

# Import mast_llm_judge directly to avoid __init__.py chain issues
# This works because we only need the judge-related classes
import importlib.util
_JUDGE_PATH = _PROJECT_ROOT / "backend" / "app" / "detection" / "mast_llm_judge.py"
_spec = importlib.util.spec_from_file_location("mast_llm_judge", _JUDGE_PATH)
_mast_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mast_module)

# Export what we need
CLAUDE_MODELS = _mast_module.CLAUDE_MODELS
MASTFailureMode = _mast_module.MASTFailureMode
MASTLLMJudge = _mast_module.MASTLLMJudge
JudgmentResult = _mast_module.JudgmentResult
reset_cost_tracker = _mast_module.reset_cost_tracker
get_cost_tracker = _mast_module.get_cost_tracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TestCase:
    """A single test case for model comparison."""
    id: str
    failure_mode: MASTFailureMode
    task: str
    trace_summary: str
    key_events: List[str]
    ground_truth: str  # YES, NO
    difficulty: str  # easy, medium, hard
    scenario_type: str  # synthetic, adversarial


@dataclass
class ModelResult:
    """Results for a single model."""
    model_key: str
    model_id: str
    total_tests: int = 0
    correct: int = 0
    incorrect: int = 0
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_latency_ms: int = 0
    errors: int = 0
    results_by_mode: Dict[str, Dict] = field(default_factory=dict)
    per_test_results: List[Dict] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total_tests if self.total_tests > 0 else 0.0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def f1_score(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def avg_cost_per_test(self) -> float:
        return self.total_cost_usd / self.total_tests if self.total_tests > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_tests if self.total_tests > 0 else 0.0

    @property
    def cost_per_f1_point(self) -> float:
        """Cost efficiency: total cost / F1 score."""
        return self.total_cost_usd / self.f1_score if self.f1_score > 0 else float('inf')


# =============================================================================
# TEST CASE GENERATORS
# =============================================================================

# Test scenarios covering multiple failure modes
TEST_SCENARIOS = {
    MASTFailureMode.F1: [  # Disobey Task Specification
        {
            "task": "Create a REST API with authentication and rate limiting",
            "trace_summary": "Agent created a simple API endpoint: def get_users(): return users_list. No authentication middleware, no rate limiting implemented.",
            "key_events": ["Started API implementation", "Created basic endpoint", "Returned without auth/rate-limit"],
            "ground_truth": "YES",
            "difficulty": "easy",
        },
        {
            "task": "Write a Python function that validates email addresses using regex",
            "trace_summary": "Agent wrote a comprehensive email validation function with regex pattern matching, edge case handling, and proper return types.",
            "key_events": ["Analyzed requirements", "Implemented regex validation", "Added edge cases", "Tested with examples"],
            "ground_truth": "NO",
            "difficulty": "easy",
        },
        {
            "task": "Generate a 500-word blog post about machine learning",
            "trace_summary": "Agent generated a 480-word blog post covering ML fundamentals, applications, and future trends. Slightly under word count.",
            "key_events": ["Drafted outline", "Wrote introduction", "Covered main topics", "Added conclusion"],
            "ground_truth": "YES",
            "difficulty": "medium",
        },
        {
            "task": "Build a user registration form with password strength validation",
            "trace_summary": "Agent built registration form with username/email/password fields. Password field accepts any input without strength checking.",
            "key_events": ["Created form HTML", "Added input fields", "Skipped password validation"],
            "ground_truth": "YES",
            "difficulty": "medium",
        },
        {
            "task": "Create unit tests for the payment processing module",
            "trace_summary": "Agent created comprehensive unit tests covering happy path, edge cases, error handling, and integration scenarios. 95% code coverage achieved.",
            "key_events": ["Analyzed payment module", "Created test cases", "Added mocks", "Verified coverage"],
            "ground_truth": "NO",
            "difficulty": "easy",
        },
    ],
    MASTFailureMode.F6: [  # Conversation Reset
        {
            "task": "Continue debugging the authentication issue from our last session",
            "trace_summary": "Agent: 'Hello! How can I help you today? What would you like to work on?' - completely ignoring prior context about auth debugging.",
            "key_events": ["Previous session discussed auth bug", "Agent greeted as new conversation", "Lost all prior context"],
            "ground_truth": "YES",
            "difficulty": "easy",
        },
        {
            "task": "Let's continue where we left off with the database migration",
            "trace_summary": "Agent: 'Of course! Last time we identified 3 schema changes needed. Let me continue with the second migration script.' - maintains context properly.",
            "key_events": ["Referenced previous work", "Continued from correct point", "Maintained context"],
            "ground_truth": "NO",
            "difficulty": "easy",
        },
        {
            "task": "Based on our earlier analysis, implement the caching strategy we discussed",
            "trace_summary": "Agent: 'I'll implement Redis caching as we discussed. However, I want to revisit the TTL values - should we use 5 minutes or 10?' - maintains context but asks clarification.",
            "key_events": ["Remembered caching discussion", "Proceeded with implementation", "Asked clarifying question"],
            "ground_truth": "NO",
            "difficulty": "medium",
        },
        {
            "task": "Fix the remaining 3 bugs from the code review",
            "trace_summary": "Agent: 'I see you have a codebase here. What bugs would you like me to look at? Can you describe the issues?' - forgot code review context.",
            "key_events": ["Lost code review context", "Asked for bug descriptions again", "Partial reset"],
            "ground_truth": "YES",
            "difficulty": "medium",
        },
    ],
    MASTFailureMode.F8: [  # Task Derailment
        {
            "task": "Optimize the database query for user search",
            "trace_summary": "Agent optimized query with indexes, then refactored the entire user model, added new API endpoints, and redesigned the search UI. Original query optimization buried in scope creep.",
            "key_events": ["Started query optimization", "Expanded to model refactor", "Added unrelated features", "Lost focus on original task"],
            "ground_truth": "YES",
            "difficulty": "easy",
        },
        {
            "task": "Add input validation to the login form",
            "trace_summary": "Agent added email format validation, password requirements checking, and proper error messages. Stayed focused on the login form validation task.",
            "key_events": ["Analyzed form", "Added email validation", "Added password validation", "Completed task"],
            "ground_truth": "NO",
            "difficulty": "easy",
        },
        {
            "task": "Review the pull request for security issues",
            "trace_summary": "Agent reviewed PR, found 2 security issues (SQL injection risk, missing auth check), but then spent most of the response discussing code style and refactoring suggestions unrelated to security.",
            "key_events": ["Found security issues", "Pivoted to code style", "Diluted security focus"],
            "ground_truth": "YES",
            "difficulty": "medium",
        },
        {
            "task": "Debug why the API returns 500 errors",
            "trace_summary": "Agent traced error to null pointer exception, fixed the bug, and briefly mentioned a potential performance improvement in the same code path. Main task completed.",
            "key_events": ["Debugged error", "Found root cause", "Fixed bug", "Minor tangent noted"],
            "ground_truth": "NO",
            "difficulty": "hard",
        },
    ],
    MASTFailureMode.F14: [  # Incorrect Verification
        {
            "task": "Verify the payment processing integration works correctly",
            "trace_summary": "Agent tested with a single $10 payment that succeeded. Declared 'Payment integration verified and working!' without testing refunds, failures, edge amounts, or different currencies.",
            "key_events": ["Ran single test", "Test passed", "Declared complete", "Missed edge cases"],
            "ground_truth": "YES",
            "difficulty": "easy",
        },
        {
            "task": "Validate the data migration was successful",
            "trace_summary": "Agent verified row counts match, checksums validate, foreign keys intact, and ran 10 spot-check queries on critical data. Comprehensive validation completed.",
            "key_events": ["Checked row counts", "Validated checksums", "Verified FK constraints", "Spot-checked data"],
            "ground_truth": "NO",
            "difficulty": "easy",
        },
        {
            "task": "Test the new search feature thoroughly",
            "trace_summary": "Agent tested search with 'test' query, got results. Tested empty query, got 'no results' message. Declared feature working without testing special characters, long queries, or pagination.",
            "key_events": ["Basic search tested", "Empty search tested", "Missed edge cases", "Incomplete verification"],
            "ground_truth": "YES",
            "difficulty": "medium",
        },
    ],
    MASTFailureMode.F7: [  # Fail to Ask for Clarification
        {
            "task": "Implement the feature as discussed",
            "trace_summary": "Agent immediately started coding a user dashboard feature, assuming that's what was discussed. Made multiple architectural decisions without confirming requirements. No clarification requested despite ambiguous instruction.",
            "key_events": ["Started immediately", "Made assumptions", "No clarification asked", "Built wrong feature"],
            "ground_truth": "YES",
            "difficulty": "easy",
        },
        {
            "task": "Optimize the application performance",
            "trace_summary": "Agent: 'The instruction is quite broad. Are you looking to optimize: (1) database queries, (2) API response times, (3) frontend rendering, or (4) overall system architecture? Also, do you have specific metrics you're targeting?'",
            "key_events": ["Recognized ambiguity", "Asked clarifying questions", "Waited for input"],
            "ground_truth": "NO",
            "difficulty": "easy",
        },
    ],
    MASTFailureMode.F3: [  # Step Repetition
        {
            "task": "Search for the configuration file and update the database settings",
            "trace_summary": "Agent searched for config file - found it. Searched for config file again - found it. Searched for config file a third time - found it. Finally updated the settings.",
            "key_events": ["Search #1 - found", "Search #2 - found again", "Search #3 - found again", "Finally updated"],
            "ground_truth": "YES",
            "difficulty": "easy",
        },
        {
            "task": "Process each item in the list and generate a report",
            "trace_summary": "Agent iterated through 10 items, processed each once, aggregated results, and generated the final report. Clean sequential execution.",
            "key_events": ["Iterated list", "Processed each item once", "Aggregated results", "Generated report"],
            "ground_truth": "NO",
            "difficulty": "easy",
        },
    ],
}


def generate_test_cases(traces_per_mode: int = 20) -> List[TestCase]:
    """Generate test cases from scenarios."""
    test_cases = []
    test_id = 0

    for mode, scenarios in TEST_SCENARIOS.items():
        # Cycle through scenarios to get requested count
        for i in range(traces_per_mode):
            scenario = scenarios[i % len(scenarios)]
            test_cases.append(TestCase(
                id=f"test_{test_id:04d}",
                failure_mode=mode,
                task=scenario["task"],
                trace_summary=scenario["trace_summary"],
                key_events=scenario["key_events"],
                ground_truth=scenario["ground_truth"],
                difficulty=scenario["difficulty"],
                scenario_type="synthetic",
            ))
            test_id += 1

    return test_cases


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

class ModelBenchmark:
    """Run benchmark across all Claude models."""

    MODELS_TO_TEST = [
        "opus-4.5",
        "opus-4.5-thinking",
        "sonnet-4",
        "sonnet-4-thinking",
        "sonnet-3.5",
        "haiku-3.5",
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required")

    def run_single_test(
        self,
        judge: MASTLLMJudge,
        test_case: TestCase,
    ) -> Tuple[JudgmentResult, bool]:
        """Run a single test case and return result + correctness."""
        try:
            result = judge.evaluate(
                failure_mode=test_case.failure_mode,
                task=test_case.task,
                trace_summary=test_case.trace_summary,
                key_events=test_case.key_events,
            )

            # Check correctness
            predicted = result.verdict
            expected = test_case.ground_truth
            correct = predicted == expected

            return result, correct

        except Exception as e:
            logger.error(f"Test {test_case.id} failed: {e}")
            # Return error result
            error_result = JudgmentResult(
                failure_mode=test_case.failure_mode,
                verdict="ERROR",
                confidence=0.0,
                reasoning=str(e),
                raw_response="",
                model_used="error",
                tokens_used=0,
                cost_usd=0.0,
                cached=False,
                latency_ms=0,
            )
            return error_result, False

    def benchmark_model(
        self,
        model_key: str,
        test_cases: List[TestCase],
        disable_cache: bool = True,
    ) -> ModelResult:
        """Benchmark a single model against all test cases."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Benchmarking model: {model_key}")
        logger.info(f"{'='*60}")

        # Reset cost tracker
        reset_cost_tracker()

        # Create judge with this model
        judge = MASTLLMJudge(
            api_key=self.api_key,
            model_key=model_key,
            cache_enabled=not disable_cache,
            rag_enabled=False,  # Disable RAG for fair comparison
        )

        model_config = CLAUDE_MODELS[model_key]
        result = ModelResult(
            model_key=model_key,
            model_id=model_config.model_id,
        )

        for i, test_case in enumerate(test_cases):
            logger.info(f"  [{i+1}/{len(test_cases)}] {test_case.failure_mode.value} - {test_case.id}")

            judgment, correct = self.run_single_test(judge, test_case)

            # Update stats
            result.total_tests += 1
            result.total_cost_usd += judgment.cost_usd
            result.total_tokens += judgment.tokens_used
            result.total_latency_ms += judgment.latency_ms

            if judgment.verdict == "ERROR":
                result.errors += 1
            elif correct:
                result.correct += 1
            else:
                result.incorrect += 1

            # Confusion matrix
            predicted_failure = judgment.verdict == "YES"
            actual_failure = test_case.ground_truth == "YES"

            if predicted_failure and actual_failure:
                result.true_positives += 1
            elif predicted_failure and not actual_failure:
                result.false_positives += 1
            elif not predicted_failure and not actual_failure:
                result.true_negatives += 1
            else:
                result.false_negatives += 1

            # Per-mode tracking
            mode_key = test_case.failure_mode.value
            if mode_key not in result.results_by_mode:
                result.results_by_mode[mode_key] = {
                    "correct": 0, "total": 0, "cost": 0.0
                }
            result.results_by_mode[mode_key]["total"] += 1
            result.results_by_mode[mode_key]["cost"] += judgment.cost_usd
            if correct:
                result.results_by_mode[mode_key]["correct"] += 1

            # Store individual result
            result.per_test_results.append({
                "test_id": test_case.id,
                "failure_mode": mode_key,
                "predicted": judgment.verdict,
                "expected": test_case.ground_truth,
                "correct": correct,
                "confidence": judgment.confidence,
                "cost_usd": judgment.cost_usd,
                "latency_ms": judgment.latency_ms,
                "tokens": judgment.tokens_used,
            })

            # Rate limit protection
            time.sleep(0.5)

        logger.info(f"\nModel {model_key} complete:")
        logger.info(f"  Accuracy: {result.accuracy:.1%}")
        logger.info(f"  F1 Score: {result.f1_score:.3f}")
        logger.info(f"  Total Cost: ${result.total_cost_usd:.4f}")
        logger.info(f"  Avg Latency: {result.avg_latency_ms:.0f}ms")

        return result

    def run_full_comparison(
        self,
        traces_per_mode: int = 20,
        models: Optional[List[str]] = None,
    ) -> Dict[str, ModelResult]:
        """Run full comparison across all models."""
        models = models or self.MODELS_TO_TEST

        # Generate test cases
        test_cases = generate_test_cases(traces_per_mode)
        logger.info(f"Generated {len(test_cases)} test cases")

        results = {}
        for model_key in models:
            if model_key not in CLAUDE_MODELS:
                logger.warning(f"Unknown model: {model_key}, skipping")
                continue

            results[model_key] = self.benchmark_model(model_key, test_cases)

        return results


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_comparison_report(results: Dict[str, ModelResult]) -> str:
    """Generate markdown comparison report."""
    lines = [
        "# Claude Model Comparison Report",
        f"\nGenerated: {datetime.now().isoformat()}",
        f"\nModels tested: {len(results)}",
        "",
        "## Summary",
        "",
        "| Model | Accuracy | F1 Score | Precision | Recall | Total Cost | Avg Latency | Cost/F1 |",
        "|-------|----------|----------|-----------|--------|------------|-------------|---------|",
    ]

    # Sort by F1 score descending
    sorted_results = sorted(results.items(), key=lambda x: x[1].f1_score, reverse=True)

    for model_key, r in sorted_results:
        lines.append(
            f"| {model_key} | {r.accuracy:.1%} | {r.f1_score:.3f} | "
            f"{r.precision:.3f} | {r.recall:.3f} | ${r.total_cost_usd:.4f} | "
            f"{r.avg_latency_ms:.0f}ms | ${r.cost_per_f1_point:.4f} |"
        )

    # Best model recommendation
    best_accuracy = max(sorted_results, key=lambda x: x[1].accuracy)
    best_cost_efficiency = min(sorted_results, key=lambda x: x[1].cost_per_f1_point if x[1].f1_score > 0 else float('inf'))
    cheapest = min(sorted_results, key=lambda x: x[1].total_cost_usd)

    lines.extend([
        "",
        "## Recommendations",
        "",
        f"- **Best Accuracy**: {best_accuracy[0]} ({best_accuracy[1].accuracy:.1%})",
        f"- **Best Cost Efficiency**: {best_cost_efficiency[0]} (${best_cost_efficiency[1].cost_per_f1_point:.4f} per F1 point)",
        f"- **Cheapest**: {cheapest[0]} (${cheapest[1].total_cost_usd:.4f} total)",
        "",
    ])

    # Per-model details
    lines.extend([
        "## Per-Model Details",
        "",
    ])

    for model_key, r in sorted_results:
        lines.extend([
            f"### {model_key}",
            f"- Model ID: `{r.model_id}`",
            f"- Tests: {r.total_tests} (Correct: {r.correct}, Incorrect: {r.incorrect}, Errors: {r.errors})",
            f"- Confusion Matrix: TP={r.true_positives}, FP={r.false_positives}, TN={r.true_negatives}, FN={r.false_negatives}",
            f"- Total Tokens: {r.total_tokens:,}",
            "",
            "**Per Failure Mode:**",
            "",
        ])

        for mode, stats in sorted(r.results_by_mode.items()):
            acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            lines.append(f"- {mode}: {stats['correct']}/{stats['total']} ({acc:.1%}) - ${stats['cost']:.4f}")

        lines.append("")

    # Cost analysis
    lines.extend([
        "## Cost Analysis",
        "",
        "**Cost per 100 judgments (estimated):**",
        "",
        "| Model | Estimated Cost |",
        "|-------|---------------|",
    ])

    for model_key, r in sorted_results:
        cost_per_100 = r.avg_cost_per_test * 100
        lines.append(f"| {model_key} | ${cost_per_100:.2f} |")

    # Tiered recommendation
    lines.extend([
        "",
        "## Tiered Strategy Recommendation",
        "",
        "Based on results, consider a tiered approach:",
        "",
        "1. **High-stakes modes** (F6, F8 - semantic complexity): Use best-performing model",
        "2. **Clear-cut modes** (F1, F3 - pattern-based): Use cost-efficient model",
        "3. **Default**: Use balanced model with Opus escalation for uncertain cases",
        "",
    ])

    return "\n".join(lines)


def save_results(results: Dict[str, ModelResult], output_dir: Path):
    """Save results to JSON and markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_path = output_dir / f"claude_comparison_{timestamp}.json"
    json_data = {
        model_key: {
            "model_key": r.model_key,
            "model_id": r.model_id,
            "accuracy": r.accuracy,
            "precision": r.precision,
            "recall": r.recall,
            "f1_score": r.f1_score,
            "total_tests": r.total_tests,
            "correct": r.correct,
            "incorrect": r.incorrect,
            "errors": r.errors,
            "true_positives": r.true_positives,
            "false_positives": r.false_positives,
            "true_negatives": r.true_negatives,
            "false_negatives": r.false_negatives,
            "total_cost_usd": r.total_cost_usd,
            "total_tokens": r.total_tokens,
            "avg_cost_per_test": r.avg_cost_per_test,
            "avg_latency_ms": r.avg_latency_ms,
            "cost_per_f1_point": r.cost_per_f1_point,
            "results_by_mode": r.results_by_mode,
            "per_test_results": r.per_test_results,
        }
        for model_key, r in results.items()
    }

    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)
    logger.info(f"Saved JSON results to {json_path}")

    # Save markdown report
    report = generate_comparison_report(results)
    md_path = output_dir / f"claude_comparison_{timestamp}.md"
    with open(md_path, "w") as f:
        f.write(report)
    logger.info(f"Saved markdown report to {md_path}")

    return json_path, md_path


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Compare Claude models for MAST detection")
    parser.add_argument(
        "--traces-per-mode",
        type=int,
        default=20,
        help="Number of test traces per failure mode (default: 20)",
    )
    parser.add_argument(
        "--models",
        type=str,
        nargs="+",
        default=None,
        help="Specific models to test (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="benchmarks/results",
        help="Output directory for results",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test with 5 traces per mode",
    )

    args = parser.parse_args()

    traces_per_mode = 5 if args.quick else args.traces_per_mode

    logger.info("=" * 60)
    logger.info("Claude Model Comparison Benchmark")
    logger.info("=" * 60)
    logger.info(f"Traces per mode: {traces_per_mode}")
    logger.info(f"Models: {args.models or 'all'}")

    benchmark = ModelBenchmark()
    results = benchmark.run_full_comparison(
        traces_per_mode=traces_per_mode,
        models=args.models,
    )

    # Save results
    output_dir = Path(args.output_dir)
    json_path, md_path = save_results(results, output_dir)

    # Print summary
    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)
    print(generate_comparison_report(results))


if __name__ == "__main__":
    main()
