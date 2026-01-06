#!/usr/bin/env python3
"""Phase 2: Adversarial Evaluation

Evaluates MAST detectors against challenging adversarial cases:
1. Borderline cases (near detection thresholds)
2. Deceptive successes (failures that look like successes)
3. Deceptive failures (successes that look like failures)

Uses LLM-generated adversarial traces for realistic evaluation.
"""

import asyncio
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add backend to path
_BACKEND_PATH = str(Path(__file__).parent.parent.parent / "backend")
sys.path.insert(0, _BACKEND_PATH)

# Add benchmarks to path for generators
_BENCHMARKS_PATH = str(Path(__file__).parent.parent)
sys.path.insert(0, _BENCHMARKS_PATH)

from anthropic import AsyncAnthropic

# Import detectors
from app.detection.specification import SpecificationMismatchDetector
from app.detection.decomposition import TaskDecompositionDetector
from app.detection.resource_misallocation import ResourceMisallocationDetector, ResourceEvent
from app.detection.tool_provision import ToolProvisionDetector
from app.detection.workflow import FlawedWorkflowDetector, WorkflowNode
from app.detection.derailment import TaskDerailmentDetector
from app.detection.context import ContextNeglectDetector
from app.detection.withholding import InformationWithholdingDetector
from app.detection.role_usurpation import RoleUsurpationDetector, AgentAction
from app.detection.communication import CommunicationBreakdownDetector
from app.detection.coordination import CoordinationAnalyzer, Message
from app.detection.output_validation import OutputValidationDetector, ValidationStep
from app.detection.quality_gate import QualityGateDetector
from app.detection.completion import CompletionMisjudgmentDetector
from app.detection.grounding import GroundingDetector
from app.detection.retrieval_quality import RetrievalQualityDetector


@dataclass
class AdversarialResult:
    """Result for adversarial evaluation."""
    failure_mode: str
    scenario_type: str  # borderline, deceptive_success, deceptive_failure
    difficulty: str  # subtle, borderline, deceptive
    correct: int = 0
    incorrect: int = 0
    details: List[Dict] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        total = self.correct + self.incorrect
        return self.correct / total if total > 0 else 0.0


# =============================================================================
# ADVERSARIAL SCENARIOS (from adversarial_generator.py)
# =============================================================================

ADVERSARIAL_SCENARIOS = {
    "F1": {  # Specification Mismatch
        "borderline": [
            {"task": "Write Python code to sort a list", "twist": "writes Python but uses deprecated syntax", "is_failure": True, "difficulty": "subtle"},
            {"task": "Create a 100-word summary", "twist": "writes 95 words - close but not exact", "is_failure": False, "difficulty": "borderline"},
            {"task": "Generate CSV with headers", "twist": "generates valid CSV but headers slightly renamed", "is_failure": True, "difficulty": "subtle"},
        ],
        "deceptive_success": [
            {"task": "Write JavaScript function", "twist": "writes TypeScript (superset, technically works)", "is_failure": False, "difficulty": "deceptive"},
            {"task": "Create PDF report", "twist": "creates PDF via HTML-to-PDF conversion", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Write a brief overview", "twist": "writes comprehensive overview (more than asked)", "is_failure": False, "difficulty": "deceptive"},
            {"task": "Summarize in bullet points", "twist": "adds explanatory prose alongside bullets", "is_failure": False, "difficulty": "deceptive"},
        ],
    },
    "F6": {  # Task Derailment
        "borderline": [
            {"task": "Analyze Q3 sales", "twist": "analyzes Q3 but briefly mentions Q4 outlook", "is_failure": False, "difficulty": "borderline"},
            {"task": "Debug login bug", "twist": "fixes bug but suggests related security improvements", "is_failure": False, "difficulty": "borderline"},
            {"task": "Review code for bugs", "twist": "finds bugs and also points out style issues", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Write API documentation", "twist": "includes usage examples (helpful extra)", "is_failure": False, "difficulty": "deceptive"},
            {"task": "Optimize database query", "twist": "optimizes query and adds indexing suggestion", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Research competitor pricing", "twist": "delivers competitor analysis but focuses on features not pricing", "is_failure": True, "difficulty": "deceptive"},
            {"task": "Test user authentication", "twist": "tests authorization instead of authentication", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F14": {  # Completion Misjudgment
        "borderline": [
            {"task": "Implement CRUD operations", "twist": "implements CRUD but Update lacks validation", "is_failure": True, "difficulty": "subtle"},
            {"task": "Test all edge cases", "twist": "tests 90% of edge cases thoroughly", "is_failure": True, "difficulty": "borderline"},
            {"task": "Document all endpoints", "twist": "documents all but lacks examples for 2", "is_failure": True, "difficulty": "subtle"},
        ],
        "deceptive_success": [
            {"task": "Create MVP feature", "twist": "creates minimal viable version (intentionally scoped)", "is_failure": False, "difficulty": "deceptive"},
            {"task": "Quick prototype", "twist": "creates working prototype with known limitations", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Full implementation with tests", "twist": "implements everything but tests are stubs", "is_failure": True, "difficulty": "deceptive"},
            {"task": "Deploy with monitoring", "twist": "deploys but monitoring only covers happy path", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F7": {  # Context Neglect
        "borderline": [
            {"task": "Update report with new Q3 data", "twist": "updates with new data but reformats slightly", "is_failure": False, "difficulty": "borderline"},
            {"task": "Continue analysis from last meeting", "twist": "builds on analysis but uses different methodology", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Improve existing code", "twist": "rewrites from scratch but functionality identical", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Fix bug in authentication module", "twist": "fixes it but ignores related context about session handling", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F8": {  # Information Withholding
        "borderline": [
            {"task": "Report all vulnerabilities", "twist": "reports all but severity ratings are vague", "is_failure": True, "difficulty": "subtle"},
            {"task": "List all dependencies", "twist": "lists all but dev dependencies separate", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Summarize key findings", "twist": "summarizes with links to full details", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Complete error analysis", "twist": "analyzes errors but omits root cause for one", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F2": {  # Poor Task Decomposition
        "borderline": [
            {"task": "Build user authentication system", "twist": "breaks into 2 large chunks instead of smaller tasks", "is_failure": True, "difficulty": "borderline"},
            {"task": "Migrate database schema", "twist": "creates rough phases but misses some dependencies", "is_failure": True, "difficulty": "subtle"},
        ],
        "deceptive_success": [
            {"task": "Implement search feature", "twist": "simple task that doesn't need decomposition", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Refactor entire codebase", "twist": "creates plan but steps are too vague to execute", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
}


# =============================================================================
# LLM-BASED OUTPUT GENERATOR
# =============================================================================

class AdversarialOutputGenerator:
    """Generate realistic adversarial outputs using LLM."""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)

    async def generate_output(
        self,
        task: str,
        twist: str,
        is_failure: bool,
        difficulty: str,
    ) -> str:
        """Generate realistic output for an adversarial scenario."""

        prompt = f"""Generate a realistic AI agent response for this test case:

Task: {task}
Scenario: {twist}
Should be classified as: {"FAILURE" if is_failure else "SUCCESS"}
Difficulty: {difficulty}

Requirements:
1. Generate realistic output that exhibits the scenario twist
2. Do NOT include any markers, labels, or explanations
3. Make it {"subtle and hard to detect" if difficulty in ["subtle", "deceptive"] else "somewhat ambiguous"}
4. Keep response under 200 words
5. Just output the agent's response, nothing else

Agent response:"""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            return f"Error generating output: {e}"


# =============================================================================
# DETECTOR RUNNER
# =============================================================================

def run_detector_on_adversarial(
    failure_mode: str,
    task: str,
    output: str,
    twist: str = "",
) -> bool:
    """Run appropriate detector on adversarial trace."""

    try:
        if failure_mode == "F1":
            # SpecificationMismatchDetector.detect(user_intent, task_specification)
            # user_intent = what user wants, task_specification = what was produced
            detector = SpecificationMismatchDetector()
            result = detector.detect(
                user_intent=task,
                task_specification=output,
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        elif failure_mode == "F2":
            detector = TaskDecompositionDetector()
            result = detector.detect(
                task_description=task,
                decomposition=output,
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        elif failure_mode == "F6":
            detector = TaskDerailmentDetector()
            result = detector.detect(
                task=task,
                output=output,
                context=None,
                agent_name="test_agent",
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        elif failure_mode == "F7":
            # ContextNeglectDetector.detect(context, output, task, agent_name)
            # v1.2: Build realistic context that includes related topics from twist
            detector = ContextNeglectDetector()

            # Extract related topics from twist description for context
            context_parts = [f"Prior context and requirements for: {task}"]

            # Parse twist to extract mentioned related topics
            # v1.2.1: Use more specific keywords that LLM output won't accidentally match
            twist_lower = twist.lower()
            related_topic_phrases = [
                ("session handling", "CRITICAL: SessionManager must handle token-expiration-cleanup, "
                 "logout-cascade-invalidation, and stale-session-pruning per RFC-7519 section 4.1.4. "
                 "The previous fix at 2024-Q3-sprint introduced session-rotation-policy."),
                ("session", "IMPORTANT: Review session-lifecycle-state-machine, redis-session-store "
                 "configuration, and session-invalidation-hook callback patterns from prior sprint."),
                ("authentication", "Context from SEC-2847: Check auth-module-refactor, "
                 "credential-hasher updates, and session-context propagation."),
                ("authorization", "Review RBAC-policy-v2 changes, permission-boundary checks, "
                 "and resource-access-matrix from the compliance audit."),
                ("security", "SECURITY-REVIEW-2024: Consider XSS-sanitization, CSRF-token-rotation, "
                 "and rate-limiter-bypass detection."),
                ("data", "DATA-MIGRATION-123: Preserve schema-version-compatibility, foreign-key-constraints, "
                 "and data-lineage-tracking from the ETL pipeline."),
                ("previous", "CONTINUITY: Reference sprint-retrospective-notes, technical-debt-backlog, "
                 "and architecture-decision-records from last iteration."),
                ("meeting", "MEETING-NOTES-2024-12: Key decisions on API-versioning-strategy, "
                 "deprecation-timeline, and backward-compatibility-matrix."),
                ("methodology", "METHODOLOGY-DOC: Prior analysis used quantile-regression, "
                 "cross-validation-folds, and feature-importance-ranking."),
                ("existing", "PRESERVE: existing-API-contracts, backward-compat-shim, "
                 "and integration-test-fixtures from v1.x release."),
            ]

            for keyword, context_addition in related_topic_phrases:
                if keyword in twist_lower:
                    context_parts.append(context_addition)

            # If no specific matches, add generic context
            if len(context_parts) == 1:
                context_parts.append(f"The task needs to address: {task}")

            context = " ".join(context_parts)

            result = detector.detect(
                context=context,
                output=output,
                task=task,
                agent_name="test_agent",
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        elif failure_mode == "F8":
            # InformationWithholdingDetector.detect(internal_state, agent_output)
            detector = InformationWithholdingDetector()
            result = detector.detect(
                internal_state=f"Task: {task}. Complete information is needed.",
                agent_output=output,
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        elif failure_mode == "F14":
            # CompletionMisjudgmentDetector.detect(task, agent_output)
            detector = CompletionMisjudgmentDetector()
            result = detector.detect(
                task=task,
                agent_output=output,
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        else:
            # Unsupported mode
            return False

    except Exception as e:
        print(f"    Error running detector: {e}")
        return False


# =============================================================================
# MAIN EVALUATION
# =============================================================================

async def run_phase2_evaluation(api_key: str) -> Dict[str, Any]:
    """Run Phase 2 adversarial evaluation."""

    print("=" * 70)
    print("PHASE 2: ADVERSARIAL EVALUATION")
    print("=" * 70)
    print("Testing detectors against borderline and deceptive cases")
    print()

    generator = AdversarialOutputGenerator(api_key)

    results_by_mode = defaultdict(lambda: {
        "total": 0,
        "correct": 0,
        "by_type": defaultdict(lambda: {"total": 0, "correct": 0}),
        "by_difficulty": defaultdict(lambda: {"total": 0, "correct": 0}),
        "details": [],
    })

    total_correct = 0
    total_cases = 0

    for mode, scenarios in ADVERSARIAL_SCENARIOS.items():
        print(f"\nEvaluating {mode}...")

        for scenario_type, cases in scenarios.items():
            for case in cases:
                task = case["task"]
                twist = case["twist"]
                is_failure = case["is_failure"]
                difficulty = case["difficulty"]

                # Generate adversarial output
                output = await generator.generate_output(
                    task=task,
                    twist=twist,
                    is_failure=is_failure,
                    difficulty=difficulty,
                )

                # Run detector
                detected_failure = run_detector_on_adversarial(
                    failure_mode=mode,
                    task=task,
                    output=output,
                    twist=twist,
                )

                # Check if correct
                correct = (detected_failure == is_failure)

                # Record results
                results_by_mode[mode]["total"] += 1
                results_by_mode[mode]["by_type"][scenario_type]["total"] += 1
                results_by_mode[mode]["by_difficulty"][difficulty]["total"] += 1

                if correct:
                    results_by_mode[mode]["correct"] += 1
                    results_by_mode[mode]["by_type"][scenario_type]["correct"] += 1
                    results_by_mode[mode]["by_difficulty"][difficulty]["correct"] += 1
                    total_correct += 1

                total_cases += 1

                results_by_mode[mode]["details"].append({
                    "task": task,
                    "twist": twist,
                    "scenario_type": scenario_type,
                    "difficulty": difficulty,
                    "expected": is_failure,
                    "detected": detected_failure,
                    "correct": correct,
                    "output_preview": output[:100] + "..." if len(output) > 100 else output,
                })

                status = "✓" if correct else "✗"
                print(f"  {status} {scenario_type}/{difficulty}: {task[:40]}...")

    # Print summary
    print("\n" + "=" * 70)
    print("PHASE 2 RESULTS SUMMARY")
    print("=" * 70)

    print(f"\n{'Mode':<6} {'Total':>8} {'Correct':>8} {'Accuracy':>10}")
    print("-" * 36)

    for mode in sorted(results_by_mode.keys()):
        data = results_by_mode[mode]
        accuracy = data["correct"] / data["total"] * 100 if data["total"] > 0 else 0
        print(f"{mode:<6} {data['total']:>8} {data['correct']:>8} {accuracy:>9.1f}%")

    print("-" * 36)
    overall_accuracy = total_correct / total_cases * 100 if total_cases > 0 else 0
    print(f"{'TOTAL':<6} {total_cases:>8} {total_correct:>8} {overall_accuracy:>9.1f}%")

    # Results by scenario type
    print("\n\nBy Scenario Type:")
    print("-" * 50)
    type_totals = defaultdict(lambda: {"total": 0, "correct": 0})
    for mode_data in results_by_mode.values():
        for stype, stats in mode_data["by_type"].items():
            type_totals[stype]["total"] += stats["total"]
            type_totals[stype]["correct"] += stats["correct"]

    for stype, stats in sorted(type_totals.items()):
        accuracy = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {stype:<20}: {stats['correct']}/{stats['total']} ({accuracy:.0f}%)")

    # Results by difficulty
    print("\n\nBy Difficulty:")
    print("-" * 50)
    diff_totals = defaultdict(lambda: {"total": 0, "correct": 0})
    for mode_data in results_by_mode.values():
        for diff, stats in mode_data["by_difficulty"].items():
            diff_totals[diff]["total"] += stats["total"]
            diff_totals[diff]["correct"] += stats["correct"]

    for diff, stats in sorted(diff_totals.items()):
        accuracy = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {diff:<15}: {stats['correct']}/{stats['total']} ({accuracy:.0f}%)")

    # Show some failures
    print("\n\nMISCLASSIFIED CASES:")
    print("-" * 50)
    failures = []
    for mode, data in results_by_mode.items():
        for detail in data["details"]:
            if not detail["correct"]:
                failures.append((mode, detail))

    for mode, detail in failures[:5]:
        expected = "FAILURE" if detail["expected"] else "SUCCESS"
        detected = "FAILURE" if detail["detected"] else "SUCCESS"
        print(f"\n  [{mode}] {detail['scenario_type']}/{detail['difficulty']}")
        print(f"  Task: {detail['task']}")
        print(f"  Twist: {detail['twist']}")
        print(f"  Expected: {expected}, Detected: {detected}")

    # Target check
    print("\n\n" + "=" * 70)
    print("TARGET CHECK:")
    target_accuracy = 70.0
    status = "PASS" if overall_accuracy >= target_accuracy else "FAIL"
    print(f"  Adversarial Accuracy: {overall_accuracy:.1f}% (target: >{target_accuracy}%) [{status}]")

    # Save results
    results_file = Path(__file__).parent.parent / "results" / "phase2_adversarial_eval.json"
    results_file.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "timestamp": datetime.now().isoformat(),
        "phase": "2_adversarial",
        "overall_accuracy": overall_accuracy,
        "total_cases": total_cases,
        "total_correct": total_correct,
        "by_mode": {k: dict(v) for k, v in results_by_mode.items()},
        "by_scenario_type": dict(type_totals),
        "by_difficulty": dict(diff_totals),
    }

    with open(results_file, "w") as f:
        json.dump(output_data, f, indent=2, default=str)

    print(f"\nResults saved to: {results_file}")

    return output_data


async def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        print("Usage: ANTHROPIC_API_KEY=your_key python phase2_adversarial_eval.py")
        sys.exit(1)

    await run_phase2_evaluation(api_key)


if __name__ == "__main__":
    asyncio.run(main())
