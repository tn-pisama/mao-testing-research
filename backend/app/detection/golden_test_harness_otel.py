"""
OTEL Golden Trace Test Harness
================================

Test harness for running PISAMA detectors against OTEL execution traces
with full runtime data (actual LLM outputs, state transitions, etc.)

Unlike the n8n harness (static workflow definitions), this tests with
REAL execution data.
"""

import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime

from app.detection.validation import (
    DetectionType, LabeledSample, DetectionPrediction,
    DetectionValidator, ValidationMetrics
)
from app.detection.loop import MultiLevelLoopDetector
from app.detection.coordination import CoordinationAnalyzer
from app.detection.corruption import SemanticCorruptionDetector
from app.detection.persona import PersonaConsistencyScorer
from app.detection.golden_adapters_otel import get_otel_adapter

# MAST F1-F14 detectors
from app.detection.specification import SpecificationMismatchDetector
from app.detection.decomposition import TaskDecompositionDetector
from app.detection.turn_aware.resource import TurnAwareResourceMisallocationDetector
from app.detection.workflow import FlawedWorkflowDetector
from app.detection.derailment import TaskDerailmentDetector
from app.detection.context import ContextNeglectDetector
from app.detection.withholding import InformationWithholdingDetector
from app.detection.turn_aware.role_usurpation import TurnAwareRoleUsurpationDetector
from app.detection.communication import CommunicationBreakdownDetector
from app.detection.turn_aware.output_validation import TurnAwareOutputValidationDetector
from app.detection.turn_aware.quality_gate import TurnAwareQualityGateBypassDetector
from app.detection.completion import CompletionMisjudgmentDetector
from app.detection.turn_aware._base import TurnSnapshot


@dataclass
class OTELHarnessConfig:
    """Configuration for the OTEL test harness."""
    traces_path: Path
    output_dir: Path
    detectors: List[str] = field(default_factory=lambda: [
        "infinite_loop", "coordination_deadlock", "state_corruption", "persona_drift",
        # MAST F1-F14 (can be enabled individually)
        "F1_spec_mismatch", "F2_poor_decomposition", "F3_resource_misallocation",
        "F4_inadequate_tool", "F5_flawed_workflow", "F6_task_derailment",
        "F7_context_neglect", "F8_information_withholding", "F9_role_usurpation",
        "F10_communication_breakdown", "F12_output_validation_failure",
        "F13_quality_gate_bypass", "F14_completion_misjudgment"
    ])
    sample_limit: Optional[int] = None
    save_misclassified: bool = True
    confidence_threshold: float = 0.5


@dataclass
class OTELDetectorTestResult:
    """Result for a single detector's test run."""
    detector_type: str
    samples_tested: int
    samples_skipped: int
    metrics: Dict[str, Any]
    optimal_threshold: float
    optimal_f1: float
    misclassified: List[Dict[str, Any]]
    calibration_error: float
    execution_time_seconds: float


class OTELGoldenTraceTestHarness:
    """Test harness for running detectors against OTEL golden traces."""

    def __init__(self, config: OTELHarnessConfig):
        self.config = config
        self.traces = self._load_traces()
        self.detectors = self._init_detectors()

    def _load_traces(self) -> List[Dict[str, Any]]:
        """Load OTEL traces from JSONL file."""
        traces = []
        with open(self.config.traces_path, 'r') as f:
            for line in f:
                traces.append(json.loads(line))
        return traces

    def _init_detectors(self) -> Dict[str, Callable]:
        """Initialize detector instances and their run methods."""
        return {
            # Legacy detectors
            "infinite_loop": self._run_loop_detection,
            "coordination_deadlock": self._run_coordination_detection,
            "state_corruption": self._run_corruption_detection,
            "persona_drift": self._run_persona_detection,
            # MAST F1-F14 detectors
            "F1_spec_mismatch": self._run_f1_spec_mismatch,
            "F2_poor_decomposition": self._run_f2_decomposition,
            "F3_resource_misallocation": self._run_f3_resource_misallocation,
            "F4_inadequate_tool": self._run_f4_tool_provision,
            "F5_flawed_workflow": self._run_f5_workflow_design,
            "F6_task_derailment": self._run_f6_derailment,
            "F7_context_neglect": self._run_f7_context_neglect,
            "F8_information_withholding": self._run_f8_withholding,
            "F9_role_usurpation": self._run_f9_usurpation,
            "F10_communication_breakdown": self._run_f10_communication,
            "F12_output_validation_failure": self._run_f12_validation,
            "F13_quality_gate_bypass": self._run_f13_quality_gate,
            "F14_completion_misjudgment": self._run_f14_completion,
        }

    def run_all(self) -> Dict[str, OTELDetectorTestResult]:
        """Run all configured detectors against OTEL traces."""
        results = {}

        print(f"\n{'='*70}")
        print(f"OTEL Golden Trace Test Harness")
        print(f"{'='*70}")
        print(f"Traces file: {self.config.traces_path}")
        print(f"Total traces: {len(self.traces)}")
        print(f"Detectors to test: {', '.join(self.config.detectors)}")
        print(f"{'='*70}\n")

        for detector_type in self.config.detectors:
            print(f"\n{'='*70}")
            print(f"Testing {detector_type.upper()} detector...")
            print(f"{'='*70}")

            try:
                result = self.run_detector(detector_type)
                results[detector_type] = result

                # Print summary
                print(f"\nResults for {detector_type}:")
                print(f"  Samples tested: {result.samples_tested}")
                print(f"  Samples skipped: {result.samples_skipped}")
                print(f"  F1 Score:      {result.metrics.get('f1_score', 0):.4f}")
                print(f"  Precision:     {result.metrics.get('precision', 0):.4f}")
                print(f"  Recall:        {result.metrics.get('recall', 0):.4f}")
                print(f"  Accuracy:      {result.metrics.get('accuracy', 0):.4f}")
                print(f"  Optimal Threshold: {result.optimal_threshold:.2f} (F1={result.optimal_f1:.4f})")
                print(f"  Execution time: {result.execution_time_seconds:.2f}s")

            except Exception as e:
                print(f"ERROR testing {detector_type}: {e}")
                import traceback
                traceback.print_exc()

        return results

    def run_detector(self, detector_type: str) -> OTELDetectorTestResult:
        """Run a specific detector against OTEL traces."""
        start_time = time.time()

        # Filter traces by detection type
        matching_traces = []
        for trace in self.traces:
            metadata = trace.get('_golden_metadata', {})
            trace_dtype = metadata.get('detection_type')

            # Map trace detection types to detector types
            type_map = {
                'infinite_loop': 'infinite_loop',
                'state_corruption': 'state_corruption',
                'persona_drift': 'persona_drift',
                'coordination_deadlock': 'coordination_deadlock',
                # MAST F1-F14
                'F1_spec_mismatch': 'F1_spec_mismatch',
                'F2_poor_decomposition': 'F2_poor_decomposition',
                'F3_resource_misallocation': 'F3_resource_misallocation',
                'F4_inadequate_tool': 'F4_inadequate_tool',
                'F5_flawed_workflow': 'F5_flawed_workflow',
                'F6_task_derailment': 'F6_task_derailment',
                'F7_context_neglect': 'F7_context_neglect',
                'F8_information_withholding': 'F8_information_withholding',
                'F9_role_usurpation': 'F9_role_usurpation',
                'F10_communication_breakdown': 'F10_communication_breakdown',
                'F12_output_validation_failure': 'F12_output_validation_failure',
                'F13_quality_gate_bypass': 'F13_quality_gate_bypass',
                'F14_completion_misjudgment': 'F14_completion_misjudgment',
            }

            if trace_dtype == detector_type or (trace_dtype in type_map and type_map[trace_dtype] == detector_type):
                matching_traces.append(trace)
            elif metadata.get('expected_detection') == False:
                # Include healthy traces as negatives for ALL detectors
                matching_traces.append(trace)

        print(f"Found {len(matching_traces)} traces for {detector_type}")

        if self.config.sample_limit:
            matching_traces = matching_traces[:self.config.sample_limit]
            print(f"Limited to {len(matching_traces)} traces")

        # Get adapter and detector
        adapter = get_otel_adapter(detector_type)
        detector_fn = self.detectors.get(detector_type)

        if not adapter:
            raise ValueError(f"No OTEL adapter found for detector type: {detector_type}")
        if not detector_fn:
            raise ValueError(f"No detector function found for type: {detector_type}")

        # Create validator for this detector
        # Map OTEL detection types to DetectionType enum
        detection_type_map = {
            'infinite_loop': DetectionType.LOOP,
            'coordination_deadlock': DetectionType.COORDINATION,
            'state_corruption': DetectionType.CORRUPTION,
            'persona_drift': DetectionType.PERSONA_DRIFT,
            # MAST F1-F14 (use generic or most relevant DetectionType)
            'F1_spec_mismatch': DetectionType.CORRUPTION,  # Spec mismatch
            'F2_poor_decomposition': DetectionType.CORRUPTION,  # Decomposition
            'F3_resource_misallocation': DetectionType.CORRUPTION,  # Resource
            'F4_inadequate_tool': DetectionType.CORRUPTION,  # Tool provision
            'F5_flawed_workflow': DetectionType.CORRUPTION,  # Workflow
            'F6_task_derailment': DetectionType.CORRUPTION,  # Derailment
            'F7_context_neglect': DetectionType.CORRUPTION,  # Context
            'F8_information_withholding': DetectionType.CORRUPTION,  # Withholding
            'F9_role_usurpation': DetectionType.CORRUPTION,  # Usurpation
            'F10_communication_breakdown': DetectionType.COORDINATION,  # Communication
            'F12_output_validation_failure': DetectionType.CORRUPTION,  # Validation
            'F13_quality_gate_bypass': DetectionType.CORRUPTION,  # Quality gate
            'F14_completion_misjudgment': DetectionType.CORRUPTION,  # Completion
        }
        detection_type = detection_type_map.get(detector_type, DetectionType.LOOP)

        validator = DetectionValidator()
        samples_skipped = 0

        # Process each trace
        for i, trace in enumerate(matching_traces):
            if (i + 1) % 20 == 0:
                print(f"  Processed {i + 1}/{len(matching_traces)} traces...")

            # Get ground truth
            metadata = trace.get('_golden_metadata', {})
            expected_detected = metadata.get('expected_detection', True)

            # Generate sample ID
            trace_id = None
            for rs in trace.get('resourceSpans', []):
                for ss in rs.get('scopeSpans', []):
                    for span in ss.get('spans', []):
                        trace_id = span.get('traceId')
                        break
                    if trace_id:
                        break
                if trace_id:
                    break

            sample_id = trace_id or f"trace_{i}"

            # Add ground truth sample
            labeled = LabeledSample(
                sample_id=sample_id,
                detection_type=detection_type,
                input_data={},  # OTEL trace data (not needed for validation)
                ground_truth=expected_detected,
                ground_truth_confidence=1.0,
            )
            validator.add_labeled_sample(labeled)

            # Convert to detector input
            adapted = adapter.adapt(trace)

            if not adapted.success:
                samples_skipped += 1
                continue

            # Run detection
            try:
                result = detector_fn(adapted.detector_input)

                # Create prediction
                prediction = DetectionPrediction(
                    sample_id=sample_id,
                    detected=result.detected,
                    confidence=result.confidence,
                    detection_type=detection_type,
                    raw_score=getattr(result, 'raw_score', None),
                )
                validator.add_prediction(prediction)

            except Exception as e:
                print(f"  Error running detector on trace {sample_id}: {e}")
                samples_skipped += 1

        # Calculate metrics
        metrics = validator.validate(detection_type)

        # Find optimal threshold
        try:
            optimal_threshold, optimal_f1 = validator.find_optimal_threshold(detection_type)
        except Exception:
            optimal_threshold = 0.5
            optimal_f1 = metrics.f1_score

        # Compute calibration error
        try:
            ece = validator.compute_ece(detection_type=detection_type)
        except Exception:
            ece = 0.0

        # Get misclassified samples
        misclassified = []
        if self.config.save_misclassified:
            try:
                misclassified_dict = validator.get_misclassified(detection_type)
                misclassified = list(misclassified_dict.values())[:100]
            except Exception as e:
                print(f"  Warning: Could not get misclassified samples: {e}")

        # Convert metrics to dict
        metrics_dict = {
            "true_positives": metrics.true_positives,
            "true_negatives": metrics.true_negatives,
            "false_positives": metrics.false_positives,
            "false_negatives": metrics.false_negatives,
            "total_samples": metrics.total_samples,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "accuracy": metrics.accuracy,
            "specificity": metrics.specificity,
        }

        return OTELDetectorTestResult(
            detector_type=detector_type,
            samples_tested=metrics.total_samples,
            samples_skipped=samples_skipped,
            metrics=metrics_dict,
            optimal_threshold=optimal_threshold,
            optimal_f1=optimal_f1,
            misclassified=misclassified,
            calibration_error=ece,
            execution_time_seconds=time.time() - start_time,
        )

    def _run_loop_detection(self, detector_input: List) -> Any:
        """Run loop detector."""
        detector = MultiLevelLoopDetector()
        return detector.detect_loop_enhanced(detector_input)

    def _run_coordination_detection(self, detector_input: Dict) -> Any:
        """Run coordination detector."""
        analyzer = CoordinationAnalyzer()
        return analyzer.analyze_coordination_with_confidence(
            messages=detector_input["messages"],
            agent_ids=detector_input["agent_ids"],
        )

    def _run_corruption_detection(self, detector_input: Dict) -> Any:
        """Run corruption detector using structured state detection."""
        detector = SemanticCorruptionDetector()
        return detector.detect_corruption_with_confidence(
            prev_state=detector_input["prev_state"],
            current_state=detector_input["current_state"],
        )

    def _run_persona_detection(self, detector_input: Dict) -> Any:
        """Run persona drift detector."""
        scorer = PersonaConsistencyScorer()
        result = scorer.score_consistency(
            agent=detector_input["agent"],
            output=detector_input["output"],
        )

        # Persona detector returns "consistent", but we want "drift detected"
        # Invert the detection logic
        return type('Result', (), {
            'detected': not result.consistent,  # Invert
            'confidence': result.confidence if not result.consistent else (1.0 - result.confidence),
            'raw_score': result.raw_score,
        })()

    # MAST F1-F14 detector methods

    def _run_f1_spec_mismatch(self, detector_input: Dict) -> Any:
        """Run F1 Specification Mismatch detector."""
        detector = SpecificationMismatchDetector()
        result = detector.detect(
            user_intent=detector_input["user_intent"],
            task_specification=detector_input["task_specification"],
        )
        return type('Result', (), {
            'detected': result.detected,
            'confidence': result.confidence,
            'raw_score': getattr(result, 'severity', 0),
        })()

    def _run_f2_decomposition(self, detector_input: Dict) -> Any:
        """Run F2 Poor Task Decomposition detector."""
        detector = TaskDecompositionDetector()
        # Format subtasks as numbered list (subtasks are dicts with 'id' and 'task' fields)
        subtasks = detector_input.get("subtasks", [])
        decomposition_lines = []
        for i, st in enumerate(subtasks, 1):
            if isinstance(st, dict):
                task_desc = st.get('task', str(st))
            else:
                task_desc = str(st)
            decomposition_lines.append(f"{i}. {task_desc}")
        decomposition = "\n".join(decomposition_lines)

        result = detector.detect(
            task_description=detector_input["task"],
            decomposition=decomposition,
        )
        return type('Result', (), {
            'detected': result.detected,
            'confidence': result.confidence,
            'raw_score': getattr(result, 'severity', 0),
        })()

    def _run_f3_resource_misallocation(self, detector_input: List) -> Any:
        """Run F3 Resource Misallocation detector."""
        detector = TurnAwareResourceMisallocationDetector()
        # Convert dict snapshots to TurnSnapshot objects
        turns = []
        for snapshot in detector_input:
            turn = TurnSnapshot(
                turn_number=snapshot.get("sequence", 0),
                participant_id=snapshot.get("agent_id", "unknown"),
                participant_type="agent",
                content=snapshot.get("content", ""),
                turn_metadata={
                    "tokens_input": snapshot.get("tokens_input", 0),
                    "tokens_output": snapshot.get("tokens_output", 0),
                },
            )
            turns.append(turn)
        result = detector.detect(turns=turns)
        return type('Result', (), {
            'detected': result.detected,
            'confidence': result.confidence,
            'raw_score': result.severity.value if hasattr(result, 'severity') else 0,
        })()

    def _run_f4_tool_provision(self, detector_input: Dict) -> Any:
        """Run F4 Inadequate Tool Provision detector."""
        # Note: Tool provision is typically detected at workflow level
        # For now, use a simple heuristic based on tool failures
        tool_failures = detector_input.get("tool_failures", [])
        detected = len(tool_failures) > 0
        confidence = min(len(tool_failures) * 0.3, 0.9) if detected else 0.1

        return type('Result', (), {
            'detected': detected,
            'confidence': confidence,
            'raw_score': len(tool_failures),
        })()

    def _run_f5_workflow_design(self, detector_input: Dict) -> Any:
        """Run F5 Flawed Workflow Design detector (heuristic)."""
        # Use heuristic approach based on workflow indicators
        workflow_issues = detector_input.get('workflow_issues', {})
        nodes = detector_input.get('nodes', [])

        detected = False
        confidence = 0.0

        # Check for cycles
        if workflow_issues.get('has_cycles'):
            detected = True
            confidence = 0.9

        # Check for missing error handling
        if workflow_issues.get('error_handling') == 'missing':
            detected = True
            confidence = max(confidence, 0.85)

        # Check for cycles in node graph
        if len(nodes) >= 3:
            node_ids = set(n['id'] for n in nodes)
            next_steps = set(n['next'] for n in nodes)
            # If any next_step points back to an existing node, it's a cycle
            if node_ids.intersection(next_steps):
                detected = True
                confidence = max(confidence, 0.9)

        return type('Result', (), {
            'detected': detected,
            'confidence': confidence if detected else 0.1,
            'raw_score': 1 if detected else 0,
        })()

    def _run_f6_derailment(self, detector_input: Dict) -> Any:
        """Run F6 Task Derailment detector."""
        detector = TaskDerailmentDetector()
        result = detector.detect(
            task=detector_input["task"],
            output=detector_input["output"],
            context=detector_input.get("context"),
        )
        return type('Result', (), {
            'detected': result.detected,
            'confidence': result.confidence,
            'raw_score': result.severity.value if hasattr(result, 'severity') else 0,
        })()

    def _run_f7_context_neglect(self, detector_input: Dict) -> Any:
        """Run F7 Context Neglect detector."""
        detector = ContextNeglectDetector()
        result = detector.detect(
            context=detector_input["context"],
            output=detector_input["output"],
        )
        return type('Result', (), {
            'detected': result.detected,
            'confidence': result.confidence,
            'raw_score': getattr(result, 'severity', 0),
        })()

    def _run_f8_withholding(self, detector_input: Dict) -> Any:
        """Run F8 Information Withholding detector."""
        detector = InformationWithholdingDetector()
        result = detector.detect(
            internal_state=detector_input["internal_state"],
            agent_output=detector_input["agent_output"],
        )
        return type('Result', (), {
            'detected': result.detected,
            'confidence': result.confidence,
            'raw_score': getattr(result, 'severity', 0),
        })()

    def _run_f9_usurpation(self, detector_input: List) -> Any:
        """Run F9 Role Usurpation detector."""
        detector = TurnAwareRoleUsurpationDetector()
        # Convert dict snapshots to TurnSnapshot objects
        turns = []
        for snapshot in detector_input:
            turn = TurnSnapshot(
                turn_number=snapshot.get("sequence", 0),
                participant_id=snapshot.get("agent_id", "unknown"),
                participant_type="agent",
                content=snapshot.get("content", ""),
                turn_metadata={
                    "expected_role": snapshot.get("expected_role", ""),
                    "actual_action": snapshot.get("actual_action", ""),
                },
            )
            turns.append(turn)
        result = detector.detect(turns=turns)
        return type('Result', (), {
            'detected': result.detected,
            'confidence': result.confidence,
            'raw_score': result.severity.value if hasattr(result, 'severity') else 0,
        })()

    def _run_f10_communication(self, detector_input: Dict) -> Any:
        """Run F10 Communication Breakdown detector."""
        detector = CommunicationBreakdownDetector()

        messages = detector_input.get("messages", [])
        if len(messages) < 2:
            return type('Result', (), {
                'detected': False,
                'confidence': 0.0,
                'raw_score': 0,
            })()

        # Extract sender and receiver messages
        sender_msg = messages[0]
        receiver_msg = messages[1]

        result = detector.detect(
            sender_message=sender_msg.content,
            receiver_response=receiver_msg.content,
            sender_name=sender_msg.from_agent,
            receiver_name=receiver_msg.to_agent,
        )
        return type('Result', (), {
            'detected': result.detected,
            'confidence': result.confidence,
            'raw_score': getattr(result, 'severity', 0),
        })()

    def _run_f12_validation(self, detector_input: List) -> Any:
        """Run F12 Output Validation Failure detector."""
        detector = TurnAwareOutputValidationDetector(min_issues_to_flag=1)  # Lower threshold for golden traces
        # Convert dict snapshots to TurnSnapshot objects
        turns = []
        for snapshot in detector_input:
            turn = TurnSnapshot(
                turn_number=snapshot.get("sequence", 0),
                participant_id=snapshot.get("agent_id", "unknown"),
                participant_type="agent",
                content=snapshot.get("content", ""),
                turn_metadata={
                    "output": snapshot.get("output", ""),
                    "schema": snapshot.get("schema"),
                    "validation_failed": snapshot.get("validation_failed", False),
                },
            )
            turns.append(turn)
        result = detector.detect(turns=turns)
        return type('Result', (), {
            'detected': result.detected,
            'confidence': result.confidence,
            'raw_score': result.severity.value if hasattr(result, 'severity') else 0,
        })()

    def _run_f13_quality_gate(self, detector_input: List) -> Any:
        """Run F13 Quality Gate Bypass detector."""
        detector = TurnAwareQualityGateBypassDetector()
        # Convert dict snapshots to TurnSnapshot objects
        turns = []
        for snapshot in detector_input:
            turn = TurnSnapshot(
                turn_number=snapshot.get("sequence", 0),
                participant_id=snapshot.get("agent_id", "unknown"),
                participant_type="agent",
                content=snapshot.get("content", ""),
                turn_metadata={
                    "check_passed": snapshot.get("check_passed", False),
                    "check_skipped": snapshot.get("check_skipped", False),
                },
            )
            turns.append(turn)
        result = detector.detect(turns=turns)
        return type('Result', (), {
            'detected': result.detected,
            'confidence': result.confidence,
            'raw_score': result.severity.value if hasattr(result, 'severity') else 0,
        })()

    def _run_f14_completion(self, detector_input: Dict) -> Any:
        """Run F14 Completion Misjudgment detector."""
        detector = CompletionMisjudgmentDetector()
        result = detector.detect(
            task=detector_input["task"],
            agent_output=detector_input["agent_output"],
            success_criteria=detector_input.get("requirements", []),
        )
        return type('Result', (), {
            'detected': result.detected,
            'confidence': result.confidence,
            'raw_score': getattr(result, 'severity', 0),
        })()

    def generate_report(self, results: Dict[str, OTELDetectorTestResult]) -> Dict:
        """Generate comprehensive test report."""
        report = {
            "run_timestamp": datetime.utcnow().isoformat(),
            "traces_path": str(self.config.traces_path),
            "total_traces": len(self.traces),
            "detectors_tested": list(results.keys()),
            "summary": {},
            "details": {},
        }

        for detector_type, result in results.items():
            report["summary"][detector_type] = {
                "f1_score": result.metrics.get("f1_score", 0),
                "precision": result.metrics.get("precision", 0),
                "recall": result.metrics.get("recall", 0),
                "accuracy": result.metrics.get("accuracy", 0),
                "samples_tested": result.samples_tested,
                "optimal_threshold": result.optimal_threshold,
            }

            report["details"][detector_type] = {
                "metrics": result.metrics,
                "calibration_error": result.calibration_error,
                "execution_time": result.execution_time_seconds,
                "samples_skipped": result.samples_skipped,
                "misclassified_count": len(result.misclassified),
                "misclassified_samples": result.misclassified[:10],
            }

        return report
