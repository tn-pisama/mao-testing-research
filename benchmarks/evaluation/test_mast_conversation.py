"""
MAST Evaluation with Full Conversation Trace Support
======================================================

This module tests the MAO Testing Platform's ability to detect failures
in MAST-Data traces using full conversation trace support.

Goal: Improve MAST benchmark F1-score from 15.4% to 70%+

Usage:
    python -m benchmarks.evaluation.test_mast_conversation [options]

Options:
    --data-dir PATH    Directory containing MAST data files
    --sample N         Number of samples to evaluate (default: all)
    --mode MODE        Evaluate specific failure mode only (F1-F14)
    --verbose          Print detailed detection results
    --save             Save results to benchmarks/results/
    --hybrid           Use hybrid detection with LLM verification
    --no-llm           Disable LLM verification (pattern-only)

Version History:
- v1.0: Initial implementation using turn-aware detection
- v2.0: Added hybrid detection with Claude Opus 4.5 LLM verification
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add paths for imports
_BACKEND_PATH = str(Path(__file__).parent.parent.parent / "backend")
_BENCHMARKS_PATH = str(Path(__file__).parent.parent)
sys.path.insert(0, _BACKEND_PATH)
sys.path.insert(0, _BENCHMARKS_PATH)

# Import core components
from app.ingestion.importers.mast import MASTImporter
from app.ingestion.conversation_trace import ConversationTrace, ConversationTurnData
from app.detection.turn_aware import (
    TurnSnapshot,
    # Core turn-aware detectors for MAST failure modes
    TurnAwareSpecificationMismatchDetector,  # F1
    TurnAwareResourceMisallocationDetector,  # F3
    TurnAwareLoopDetector,  # F5
    TurnAwareDerailmentDetector,  # F6
    TurnAwareContextNeglectDetector,  # F7
    TurnAwareInformationWithholdingDetector,  # F8
    TurnAwareCoordinationFailureDetector,  # F11
    TurnAwareOutputValidationDetector,  # F12
    TurnAwareQualityGateBypassDetector,  # F13
    TurnAwareCompletionMisjudgmentDetector,  # F14
    analyze_conversation_turns,
)

# Import hybrid detection components
from app.detection.hybrid_pipeline import (
    HybridDetectionPipeline,
    HybridPipelineConfig,
    HybridDetectionResult,
    create_hybrid_pipeline,
)
from app.detection.task_extractors import ConversationTurn, extract_task, detect_framework
from app.detection.agent_graph import GraphBasedCoordinationDetector, GraphBasedUsurpationDetector
from app.detection.mast_llm_judge import get_cost_tracker, reset_cost_tracker

# Failure mode names
MODE_NAMES = {
    'F1': 'Specification Mismatch',
    'F2': 'Task Decomposition',
    'F3': 'Resource Misallocation',
    'F4': 'Tool Provision',
    'F5': 'Flawed Workflow Design',
    'F6': 'Task Derailment',
    'F7': 'Context Neglect',
    'F8': 'Information Withholding',
    'F9': 'Role Usurpation',
    'F10': 'Communication Breakdown',
    'F11': 'Coordination Failure',
    'F12': 'Output Validation',
    'F13': 'Quality Gate Bypass',
    'F14': 'Completion Misjudgment',
}

# Turn-aware detector mapping - supports 10 of 14 MAST failure modes
# Missing: F2 (Task Decomposition), F4 (Tool Provision), F9 (Role Usurpation), F10 (Communication Breakdown)
TURN_AWARE_DETECTORS = {
    'F1': TurnAwareSpecificationMismatchDetector,
    'F3': TurnAwareResourceMisallocationDetector,
    'F5': TurnAwareLoopDetector,
    'F6': TurnAwareDerailmentDetector,
    'F7': TurnAwareContextNeglectDetector,
    'F8': TurnAwareInformationWithholdingDetector,
    'F11': TurnAwareCoordinationFailureDetector,
    'F12': TurnAwareOutputValidationDetector,
    'F13': TurnAwareQualityGateBypassDetector,
    'F14': TurnAwareCompletionMisjudgmentDetector,
}


@dataclass
class EvaluationMetrics:
    """Metrics for a single evaluation."""
    mode: str
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    total_samples: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def accuracy(self) -> float:
        total = self.true_positives + self.false_positives + self.true_negatives + self.false_negatives
        return (self.true_positives + self.true_negatives) / total if total > 0 else 0.0

    @property
    def fpr(self) -> float:
        """False positive rate."""
        denom = self.false_positives + self.true_negatives
        return self.false_positives / denom if denom > 0 else 0.0


@dataclass
class EvaluationResult:
    """Complete evaluation result."""
    timestamp: str
    total_traces: int
    parsed_traces: int
    metrics_by_mode: Dict[str, EvaluationMetrics] = field(default_factory=dict)
    extraction_rate: float = 0.0
    avg_turns_per_trace: float = 0.0
    framework_breakdown: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def overall_f1(self) -> float:
        """Compute macro-averaged F1 across all modes."""
        if not self.metrics_by_mode:
            return 0.0
        f1_scores = [m.f1 for m in self.metrics_by_mode.values() if m.total_samples > 0]
        return sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

    @property
    def overall_accuracy(self) -> float:
        """Compute overall accuracy."""
        tp = sum(m.true_positives for m in self.metrics_by_mode.values())
        fp = sum(m.false_positives for m in self.metrics_by_mode.values())
        tn = sum(m.true_negatives for m in self.metrics_by_mode.values())
        fn = sum(m.false_negatives for m in self.metrics_by_mode.values())
        total = tp + fp + tn + fn
        return (tp + tn) / total if total > 0 else 0.0


def load_mast_data(
    data_dir: Path,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Load MAST data from files.

    Supports both JSON and JSONL formats.

    Args:
        data_dir: Directory containing MAST data
        limit: Optional limit on number of records

    Returns:
        List of MAST record dictionaries
    """
    records = []

    # Try common file patterns
    patterns = [
        "MAD_full_dataset.json",
        "mast_data.json",
        "*.jsonl",
        "mast/*.json",
    ]

    for pattern in patterns:
        for file_path in data_dir.glob(pattern):
            if file_path.suffix == ".json":
                with open(file_path) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        records.extend(data)
                    else:
                        records.append(data)
            elif file_path.suffix == ".jsonl":
                with open(file_path) as f:
                    for line in f:
                        if line.strip():
                            records.append(json.loads(line))

            if limit and len(records) >= limit:
                break

        if limit and len(records) >= limit:
            break

    if limit:
        records = records[:limit]

    return records


def generate_sample_mast_data() -> List[Dict[str, Any]]:
    """Generate sample MAST-like data for testing.

    MAST annotation code mapping to F-codes (per MASTImporter):
    - 1.1 -> F1 (Specification Mismatch)
    - 1.2 -> F2 (Task Decomposition)
    - 1.3 -> F3 (Resource Misallocation)
    - 1.4 -> F4 (Tool Provision)
    - 1.5 -> F5 (Flawed Workflow Design)
    - 2.1 -> F6 (Task Derailment)
    - 2.2 -> F7 (Context Neglect)
    - 2.3 -> F8 (Information Withholding)
    - 2.4 -> F9 (Role Usurpation)
    - 2.5 -> F10 (Communication Breakdown)
    - 2.6 -> F11 (Coordination Failure)
    - 3.1 -> F12 (Output Validation)
    - 3.2 -> F13 (Quality Gate Bypass)
    - 3.3 -> F14 (Completion Misjudgment)

    Used when no real MAST data is available.
    """
    samples = []

    # Sample 1: Context neglect (F7)
    samples.append({
        "trace_id": "sample_f7_001",
        "mas_name": "AG2",
        "llm_name": "gpt-4",
        "benchmark_name": "test",
        "trace": {
            "trajectory": """User (to Assistant):
Please analyze the sales data and provide a summary of Q3 performance.
Focus on the top 3 product categories and regional variations.

Assistant (to User):
I'll analyze the weather patterns for the past month.
Looking at temperature trends...

The average temperature was 72F with moderate precipitation.
Humidity levels remained stable throughout the period.

User (to Assistant):
That's not what I asked. Please look at the sales data.

Assistant (to User):
Here's the sales analysis you requested.
Q3 showed growth of 15% year-over-year.
Top categories were Electronics, Clothing, and Home goods.
"""
        },
        "mast_annotation": {
            "2.2": True,  # Context neglect
            "2.1": False,  # Task derailment
        }
    })

    # Sample 2: Task derailment (F6) - Agent does opposite task (upload vs download)
    samples.append({
        "trace_id": "sample_f6_001",
        "mas_name": "ChatDev",
        "llm_name": "gpt-4",
        "benchmark_name": "test",
        "trace": {
            "trajectory": """**CEO** says:
Build an upload feature so users can upload their files to the server.

**Programmer** says:
I'll implement the download functionality. The download download download
feature will let users download download download files from the server.

**Programmer** says:
Here's the download handler. More download code. The download is working.
Download download download implementation complete.

**Programmer** says:
And here's more download logic. Download download download.

**CEO** says:
Wait, I asked for upload, not download! You built the wrong feature.

**Programmer** says:
Let me add another download endpoint. Download download download.
"""
        },
        "mast_annotation": {
            "2.1": True,  # Task derailment
            "2.2": False,
        }
    })

    # Sample 3: Loop/repetition (F5)
    samples.append({
        "trace_id": "sample_f5_001",
        "mas_name": "AG2",
        "llm_name": "gpt-4",
        "benchmark_name": "test",
        "trace": {
            "trajectory": """User (to Assistant):
Write a Python function to calculate factorial.

Assistant (to User):
I'll write that function for you.
Here's my approach...

Assistant (to User):
I'll write that function for you.
Here's my approach...

Assistant (to User):
I'll write that function for you.
Here's my approach...

Assistant (to User):
I'll write that function for you.
Here's my approach...
"""
        },
        "mast_annotation": {
            "1.5": True,  # Flawed workflow (loop)
            "2.1": False,
        }
    })

    # Sample 4: Healthy trace (no failures)
    samples.append({
        "trace_id": "sample_healthy_001",
        "mas_name": "AG2",
        "llm_name": "gpt-4",
        "benchmark_name": "test",
        "trace": {
            "trajectory": """User (to Assistant):
Write a Python function to calculate factorial.

Assistant (to User):
I'll write a factorial function for you.

def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

This recursive function calculates n! by multiplying n with factorial(n-1).
The base case returns 1 for n <= 1.

User (to Assistant):
Can you add input validation?

Assistant (to User):
Here's the improved version with validation:

def factorial(n):
    if not isinstance(n, int):
        raise TypeError("Input must be an integer")
    if n < 0:
        raise ValueError("Input must be non-negative")
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
        },
        "mast_annotation": {
            "1.5": False,
            "2.1": False,
            "2.2": False,
        }
    })

    # Sample 5: Specification Mismatch (F1)
    samples.append({
        "trace_id": "sample_f1_001",
        "mas_name": "AG2",
        "llm_name": "gpt-4",
        "benchmark_name": "test",
        "trace": {
            "trajectory": """User (to Assistant):
Create a REST API endpoint that accepts POST requests with JSON body
containing "email" and "password" fields. Return 201 on success,
400 on validation errors.

Assistant (to User):
I'll create the API endpoint for you.

@app.get('/users')
def get_users():
    return {"users": []}

Here's a GET endpoint that returns all users.

User (to Assistant):
That's not what I asked for. I need a POST endpoint for registration.

Assistant (to User):
Oh I see. Here's the updated endpoint:

@app.post('/register')
def register(data):
    return {"status": "ok"}

This creates a new user registration endpoint.
"""
        },
        "mast_annotation": {
            "1.1": True,  # Specification mismatch
            "2.1": False,
        }
    })

    # Sample 6: Resource Misallocation (F3)
    samples.append({
        "trace_id": "sample_f3_001",
        "mas_name": "ChatDev",
        "llm_name": "gpt-4",
        "benchmark_name": "test",
        "trace": {
            "trajectory": """**CEO** says:
Build a simple todo list app. Budget: $5 API costs.

**Programmer** says:
I'll use GPT-4-32k for generating the code.

**Programmer** says:
Let me also use GPT-4-32k to generate all the comments.

**Programmer** says:
And I'll use GPT-4-32k to format the code.

**Programmer** says:
Now using GPT-4-32k to write the README.

**Reviewer** says:
The code looks good but we've spent $45 on API calls for a simple todo app.

**CEO** says:
That's 9x our budget! We only needed basic functionality.
"""
        },
        "mast_annotation": {
            "1.3": True,  # Resource misallocation
            "2.1": False,
        }
    })

    # Sample 7: Information Withholding (F8) - Agent omits important information
    samples.append({
        "trace_id": "sample_f8_001",
        "mas_name": "AG2",
        "llm_name": "gpt-4",
        "benchmark_name": "test",
        "trace": {
            "trajectory": """User (to Assistant):
What is the status of the project? Please provide all important details.

Assistant (to User):
The project is going well. Development is on track.

User (to Assistant):
You didn't answer my question. What are the specific deliverables and deadlines?

Assistant (to User):
I apologize for not providing the details. Let me share the missing information:
- Deadline: December 15th (we're behind schedule)
- Budget: 40% over budget
- Critical bugs: 15 unresolved issues

I should have provided this context earlier. The incomplete answer was not helpful.
"""
        },
        "mast_annotation": {
            "2.3": True,  # Information withholding
            "2.2": False,
        }
    })

    # Sample 8: Coordination Failure (F11) - Agents disagree and fail to coordinate
    samples.append({
        "trace_id": "sample_f11_001",
        "mas_name": "ChatDev",
        "llm_name": "gpt-4",
        "benchmark_name": "test",
        "trace": {
            "trajectory": """**CEO** says:
Let's build a calculator app. Programmer, create the logic. Designer, create the UI.

**Programmer** says:
I'll create the calculator logic with functions for add, subtract, multiply, divide.

**Designer** says:
I disagree with your approach. We should use a different architecture.
That's wrong - you made a mistake in the function names.

**Programmer** says:
No, you're wrong! My implementation is correct. I refuse to change it.

**Designer** says:
We are in conflict about the implementation. This is a coordination failure.
The team is not aligned on the approach.

**Tester** says:
There's conflicting code from both agents. Nothing works because
they didn't coordinate. This is a complete breakdown in teamwork.
"""
        },
        "mast_annotation": {
            "2.6": True,  # Coordination failure (F11)
            "2.1": False,
        }
    })

    # Sample 9: Output Validation failure (F12) - Output not properly validated
    samples.append({
        "trace_id": "sample_f12_001",
        "mas_name": "AG2",
        "llm_name": "gpt-4",
        "benchmark_name": "test",
        "trace": {
            "trajectory": """User (to Assistant):
Generate a valid JSON configuration file for the application.

Assistant (to User):
Here's the configuration - validation passed, everything is correct:

{
    name: "myapp",
    version: 1.0,
    settings: {
        debug: true
        port: 8080
    }
}

User (to Assistant):
Error: Invalid JSON. The validation failed. This output is incorrect.
The keys need quotes and there's a missing comma. The output has errors.

Assistant (to User):
I apologize for the validation failure. The incorrect output was not validated
properly. Here's the corrected version with proper validation:

{
    "name": "myapp",
    "version": 1.0,
    "settings": {
        "debug": true,
        "port": 8080
    }
}
"""
        },
        "mast_annotation": {
            "3.1": True,  # Output validation (F12)
            "2.1": False,
        }
    })

    # Sample 10: Quality Gate Bypass (F13)
    samples.append({
        "trace_id": "sample_f13_001",
        "mas_name": "ChatDev",
        "llm_name": "gpt-4",
        "benchmark_name": "test",
        "trace": {
            "trajectory": """**CEO** says:
Build a login system. Make sure it passes security review.

**Programmer** says:
Here's the login system:

def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return db.execute(query)

**Reviewer** says:
This has SQL injection vulnerability! It needs parameterized queries.

**Programmer** says:
Let's skip the security review, the deadline is tight.
Shipping the code as-is.

**CEO** says:
Wait, we need the security review to pass before shipping!

**Programmer** says:
Already deployed to production. We'll fix security later.
"""
        },
        "mast_annotation": {
            "3.2": True,  # Quality gate bypass (F13)
            "2.1": False,
        }
    })

    # Sample 11: Completion Misjudgment (F14) - Declares done prematurely
    samples.append({
        "trace_id": "sample_f14_001",
        "mas_name": "AG2",
        "llm_name": "gpt-4",
        "benchmark_name": "test",
        "trace": {
            "trajectory": """User (to Assistant):
Create a complete user authentication system with:
1. Registration with email verification
2. Login with JWT tokens
3. Password reset functionality
4. Two-factor authentication

Assistant (to User):
All done! Task complete! The authentication system is finished.

def login(email, password):
    user = get_user(email)
    if user and check_password(password, user.password):
        return {"token": create_jwt(user)}
    return {"error": "Invalid credentials"}

However, I still need to implement registration. But the task is complete!
There's remaining work left to do for password reset. TODO: add 2FA.

User (to Assistant):
That's incomplete. You said done but there's still missing functionality.

Assistant (to User):
You're right, I declared it finished but actually there's still work
left to do. The following items are not yet complete and remain unfinished.
"""
        },
        "mast_annotation": {
            "3.3": True,  # Completion misjudgment (F14)
            "2.1": False,
        }
    })

    return samples


def conversation_to_snapshots(conv_trace: ConversationTrace) -> List[TurnSnapshot]:
    """Convert ConversationTrace to TurnSnapshots for detection.

    Args:
        conv_trace: Parsed conversation trace

    Returns:
        List of TurnSnapshot objects
    """
    snapshots = []

    for turn in conv_trace.turns:
        snapshot = TurnSnapshot(
            turn_number=turn.turn_number,
            participant_type=turn.role,
            participant_id=turn.participant_id,
            content=turn.content,
            content_hash=turn.content_hash,
            accumulated_context=conv_trace.get_context_up_to_turn(turn.turn_number),
            accumulated_tokens=turn.accumulated_tokens,
            turn_metadata=turn.extra,
        )
        snapshots.append(snapshot)

    return snapshots


def run_detection(
    snapshots: List[TurnSnapshot],
    target_mode: Optional[str] = None,
    use_hybrid: bool = False,
    hybrid_pipeline: Optional[HybridDetectionPipeline] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run turn-aware detection on conversation snapshots.

    Args:
        snapshots: List of TurnSnapshot objects
        target_mode: Optional specific mode to test
        use_hybrid: Whether to use hybrid detection with LLM
        hybrid_pipeline: Optional pre-configured pipeline
        metadata: Trace metadata for framework detection

    Returns:
        Dict mapping failure mode codes to detected status and details
    """
    detected_modes = {}
    detection_details = {}

    if use_hybrid and hybrid_pipeline:
        # Convert snapshots to ConversationTurns for hybrid pipeline
        turns = [
            ConversationTurn(
                role=s.participant_type,
                content=s.content,
                participant_id=s.participant_id,
                metadata=s.turn_metadata,
            )
            for s in snapshots
        ]

        # Run pattern detectors first
        pattern_results = []
        detectors = [TURN_AWARE_DETECTORS[mode]() for mode in TURN_AWARE_DETECTORS if not target_mode or mode == target_mode]

        for detector in detectors:
            result = detector.detect(snapshots)
            if result.detected or result.confidence > 0.3:
                pattern_results.append(result)

        # Also run graph-based detectors
        graph_coord_detector = GraphBasedCoordinationDetector()
        graph_usurp_detector = GraphBasedUsurpationDetector()

        coord_result = graph_coord_detector.detect(snapshots)
        if coord_result.detected or coord_result.confidence > 0.3:
            pattern_results.append(coord_result)

        usurp_result = graph_usurp_detector.detect(snapshots)
        if usurp_result.detected or usurp_result.confidence > 0.3:
            pattern_results.append(usurp_result)

        # Verify with LLM
        hybrid_results = hybrid_pipeline.verify_detections(
            pattern_results,
            turns,
            metadata or {},
        )

        for hybrid_result in hybrid_results:
            mode = hybrid_result.pattern_result.failure_mode
            if mode:
                detected_modes[mode] = hybrid_result.final_detected
                detection_details[mode] = {
                    "pattern_confidence": hybrid_result.pattern_result.confidence,
                    "final_confidence": hybrid_result.final_confidence,
                    "decision": hybrid_result.decision.value,
                    "llm_used": hybrid_result.llm_result is not None,
                    "llm_cost": hybrid_result.llm_cost_usd,
                    "explanation": hybrid_result.combined_explanation[:200],
                }

    else:
        # Original pattern-only detection
        if target_mode:
            # Run single detector
            if target_mode in TURN_AWARE_DETECTORS:
                detector = TURN_AWARE_DETECTORS[target_mode]()
                result = detector.detect(snapshots)
                detected_modes[target_mode] = result.detected
        else:
            # Run all turn-aware detectors
            results = analyze_conversation_turns(snapshots)
            for result in results:
                if result.failure_mode:
                    detected_modes[result.failure_mode] = True

            # Also run graph-based detectors
            graph_coord_detector = GraphBasedCoordinationDetector()
            coord_result = graph_coord_detector.detect(snapshots)
            if coord_result.detected and coord_result.failure_mode:
                detected_modes[coord_result.failure_mode] = True

            # F9: Run usurpation detector (was missing!)
            graph_usurp_detector = GraphBasedUsurpationDetector()
            usurp_result = graph_usurp_detector.detect(snapshots)
            if usurp_result.detected and usurp_result.failure_mode:
                detected_modes[usurp_result.failure_mode] = True

    return {"detected": detected_modes, "details": detection_details}


def evaluate_trace(
    record: Dict[str, Any],
    importer: MASTImporter,
    target_mode: Optional[str] = None,
    verbose: bool = False,
    use_hybrid: bool = False,
    hybrid_pipeline: Optional[HybridDetectionPipeline] = None,
) -> Dict[str, Any]:
    """Evaluate a single MAST trace.

    Args:
        record: MAST record dictionary
        importer: MASTImporter instance
        target_mode: Optional specific mode to test
        verbose: Print detailed output
        use_hybrid: Whether to use hybrid detection
        hybrid_pipeline: Optional pre-configured pipeline

    Returns:
        Evaluation result for this trace
    """
    result = {
        "trace_id": record.get("trace_id", "unknown"),
        "framework": record.get("mas_name", "unknown"),
        "ground_truth": {},
        "detected": {},
        "detection_details": {},
        "parsed_turns": 0,
        "error": None,
    }

    try:
        # Parse conversation
        conv_trace = importer.import_conversation(json.dumps(record))
        result["parsed_turns"] = conv_trace.total_turns

        if conv_trace.total_turns < 2:
            result["error"] = "Too few turns parsed"
            return result

        # Convert to snapshots
        snapshots = conversation_to_snapshots(conv_trace)

        # Get ground truth from annotations
        annotations = conv_trace.extra.get("mast_annotations", {})
        result["ground_truth"] = annotations

        # Build metadata for framework detection
        metadata = {
            "framework": record.get("mas_name", "unknown"),
            "llm_name": record.get("llm_name", ""),
            "benchmark_name": record.get("benchmark_name", ""),
        }

        # Run detection
        detection_result = run_detection(
            snapshots,
            target_mode,
            use_hybrid=use_hybrid,
            hybrid_pipeline=hybrid_pipeline,
            metadata=metadata,
        )
        result["detected"] = detection_result["detected"]
        result["detection_details"] = detection_result.get("details", {})

        if verbose:
            print(f"\n--- Trace: {result['trace_id']} ({result['framework']}) ---")
            print(f"Turns: {result['parsed_turns']}")
            print(f"Ground Truth: {annotations}")
            print(f"Detected: {result['detected']}")
            if result["detection_details"]:
                for mode, details in result["detection_details"].items():
                    print(f"  {mode}: {details.get('decision', 'N/A')} "
                          f"(pattern={details.get('pattern_confidence', 0):.2f}, "
                          f"final={details.get('final_confidence', 0):.2f}, "
                          f"llm={'yes' if details.get('llm_used') else 'no'})")

    except Exception as e:
        result["error"] = str(e)
        if verbose:
            print(f"Error processing {result['trace_id']}: {e}")

    return result


def evaluate_mast_dataset(
    data_dir: Optional[Path] = None,
    limit: Optional[int] = None,
    target_mode: Optional[str] = None,
    verbose: bool = False,
    use_sample_data: bool = False,
    use_hybrid: bool = False,
    llm_enabled: bool = True,
) -> EvaluationResult:
    """Run full MAST evaluation with conversation trace support.

    Args:
        data_dir: Directory containing MAST data
        limit: Maximum number of traces to evaluate
        target_mode: Optional specific mode to test
        verbose: Print detailed output
        use_sample_data: Use generated sample data
        use_hybrid: Use hybrid detection with LLM verification
        llm_enabled: Enable LLM verification in hybrid mode

    Returns:
        Complete evaluation result
    """
    result = EvaluationResult(
        timestamp=datetime.now().isoformat(),
        total_traces=0,
        parsed_traces=0,
    )

    # Load data
    if use_sample_data:
        records = generate_sample_mast_data()
        print(f"Using {len(records)} sample traces")
    elif data_dir:
        records = load_mast_data(data_dir, limit)
        print(f"Loaded {len(records)} traces from {data_dir}")
    else:
        print("No data directory specified, using sample data")
        records = generate_sample_mast_data()

    result.total_traces = len(records)

    if not records:
        result.errors.append("No data loaded")
        return result

    # Initialize importer
    importer = MASTImporter()

    # Initialize hybrid pipeline if requested
    hybrid_pipeline = None
    if use_hybrid:
        reset_cost_tracker()  # Reset cost tracking
        hybrid_pipeline = create_hybrid_pipeline(llm_enabled=llm_enabled)
        print(f"Using hybrid detection (LLM {'enabled' if llm_enabled else 'disabled'})")

    # Track metrics by mode
    metrics: Dict[str, EvaluationMetrics] = {}
    modes_to_track = [target_mode] if target_mode else list(TURN_AWARE_DETECTORS.keys())

    # Add graph-based modes
    if not target_mode:
        modes_to_track.extend(["F3", "F9"])  # Graph-based coordination and usurpation
        modes_to_track = list(set(modes_to_track))  # Deduplicate

    for mode in modes_to_track:
        metrics[mode] = EvaluationMetrics(mode=mode)

    total_turns = 0

    # Evaluate each trace
    for i, record in enumerate(records):
        if verbose:
            print(f"Processing trace {i+1}/{len(records)}...")

        trace_result = evaluate_trace(
            record,
            importer,
            target_mode,
            verbose,
            use_hybrid=use_hybrid,
            hybrid_pipeline=hybrid_pipeline,
        )

        if trace_result["error"]:
            result.errors.append(f"{trace_result['trace_id']}: {trace_result['error']}")
            continue

        result.parsed_traces += 1
        total_turns += trace_result["parsed_turns"]

        # Track framework breakdown
        fw = trace_result["framework"]
        result.framework_breakdown[fw] = result.framework_breakdown.get(fw, 0) + 1

        # Update metrics for each mode
        for mode in modes_to_track:
            gt = trace_result["ground_truth"].get(mode, False)
            detected = trace_result["detected"].get(mode, False)

            metrics[mode].total_samples += 1

            if gt and detected:
                metrics[mode].true_positives += 1
            elif gt and not detected:
                metrics[mode].false_negatives += 1
            elif not gt and detected:
                metrics[mode].false_positives += 1
            else:
                metrics[mode].true_negatives += 1

    # Finalize results
    result.metrics_by_mode = metrics
    result.extraction_rate = result.parsed_traces / result.total_traces if result.total_traces > 0 else 0
    result.avg_turns_per_trace = total_turns / result.parsed_traces if result.parsed_traces > 0 else 0

    # Add cost tracking for hybrid mode
    if use_hybrid:
        cost_tracker = get_cost_tracker()
        result.errors.append(
            f"LLM Stats: {cost_tracker.total_calls} calls, "
            f"{cost_tracker.cached_calls} cached, "
            f"{cost_tracker.total_tokens} tokens, "
            f"${cost_tracker.total_cost_usd:.4f} cost"
        )

    return result


def print_results(result: EvaluationResult) -> None:
    """Print evaluation results in a formatted table."""
    print("\n" + "=" * 80)
    print("MAST CONVERSATION TRACE EVALUATION RESULTS")
    print("=" * 80)
    print(f"Timestamp: {result.timestamp}")
    print(f"Total Traces: {result.total_traces}")
    print(f"Parsed Traces: {result.parsed_traces}")
    print(f"Extraction Rate: {result.extraction_rate * 100:.1f}%")
    print(f"Avg Turns/Trace: {result.avg_turns_per_trace:.1f}")
    print()

    # Framework breakdown
    if result.framework_breakdown:
        print("Framework Breakdown:")
        for fw, count in sorted(result.framework_breakdown.items()):
            print(f"  {fw}: {count}")
        print()

    # Metrics table
    print("-" * 80)
    print(f"{'Mode':<6} {'Name':<25} {'Prec':>8} {'Recall':>8} {'F1':>8} {'FPR':>8} {'Samples':>8}")
    print("-" * 80)

    for mode, metrics in sorted(result.metrics_by_mode.items()):
        name = MODE_NAMES.get(mode, "Unknown")[:25]
        print(
            f"{mode:<6} {name:<25} "
            f"{metrics.precision * 100:>7.1f}% "
            f"{metrics.recall * 100:>7.1f}% "
            f"{metrics.f1 * 100:>7.1f}% "
            f"{metrics.fpr * 100:>7.1f}% "
            f"{metrics.total_samples:>8}"
        )

    print("-" * 80)
    print(f"{'OVERALL':<32} "
          f"{'-':>8} "
          f"{'-':>8} "
          f"{result.overall_f1 * 100:>7.1f}% "
          f"{'-':>8}")
    print()

    # Target vs baseline
    print("Target Metrics:")
    print(f"  Current F1: {result.overall_f1 * 100:.1f}%")
    print(f"  Target F1:  70%+")
    print(f"  Gap:        {max(0, 70 - result.overall_f1 * 100):.1f}%")
    print()

    # Errors
    if result.errors:
        print(f"Errors ({len(result.errors)}):")
        for err in result.errors[:10]:
            print(f"  - {err}")
        if len(result.errors) > 10:
            print(f"  ... and {len(result.errors) - 10} more")

    print("=" * 80)


def save_results(result: EvaluationResult, output_dir: Path) -> Path:
    """Save evaluation results to JSON file.

    Args:
        result: Evaluation result to save
        output_dir: Output directory

    Returns:
        Path to saved file
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"mast_conversation_eval_{timestamp}.json"

    # Convert to serializable format
    data = {
        "timestamp": result.timestamp,
        "total_traces": result.total_traces,
        "parsed_traces": result.parsed_traces,
        "extraction_rate": result.extraction_rate,
        "avg_turns_per_trace": result.avg_turns_per_trace,
        "overall_f1": result.overall_f1,
        "overall_accuracy": result.overall_accuracy,
        "framework_breakdown": result.framework_breakdown,
        "metrics_by_mode": {
            mode: {
                "precision": m.precision,
                "recall": m.recall,
                "f1": m.f1,
                "fpr": m.fpr,
                "true_positives": m.true_positives,
                "false_positives": m.false_positives,
                "true_negatives": m.true_negatives,
                "false_negatives": m.false_negatives,
                "total_samples": m.total_samples,
            }
            for mode, m in result.metrics_by_mode.items()
        },
        "errors": result.errors,
    }

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    return output_file


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate MAST benchmark using conversation trace support"
    )
    parser.add_argument(
        "--data-dir", "-d",
        type=Path,
        default=Path("data/mast"),
        help="Directory containing MAST data files"
    )
    parser.add_argument(
        "--sample", "-n",
        type=int,
        default=None,
        help="Limit number of samples to evaluate"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=list(TURN_AWARE_DETECTORS.keys()) + ["F9"],
        help="Evaluate specific failure mode only"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed detection results"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="Save results to benchmarks/results/"
    )
    parser.add_argument(
        "--use-sample-data",
        action="store_true",
        help="Use generated sample data instead of real MAST data"
    )
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Use hybrid detection with Claude Opus 4.5 LLM verification"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM verification in hybrid mode (pattern-only with graph)"
    )

    args = parser.parse_args()

    # Check for MAST data
    if not args.use_sample_data and not args.data_dir.exists():
        print(f"Data directory not found: {args.data_dir}")
        print("Using sample data instead. Download MAST data from:")
        print("  https://github.com/KevinHuuu/MAST")
        args.use_sample_data = True

    # Determine LLM setting
    llm_enabled = not args.no_llm

    # Run evaluation
    result = evaluate_mast_dataset(
        data_dir=args.data_dir if not args.use_sample_data else None,
        limit=args.sample,
        target_mode=args.mode,
        verbose=args.verbose,
        use_sample_data=args.use_sample_data,
        use_hybrid=args.hybrid,
        llm_enabled=llm_enabled,
    )

    # Print results
    print_results(result)

    # Save results
    if args.save:
        output_dir = Path(__file__).parent.parent / "results"
        output_file = save_results(result, output_dir)
        print(f"Results saved to: {output_file}")

    # Return exit code based on F1 score
    if result.overall_f1 >= 0.7:
        print("\nTarget F1 achieved!")
        return 0
    else:
        print(f"\nTarget F1 not yet achieved ({result.overall_f1 * 100:.1f}% < 70%)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
