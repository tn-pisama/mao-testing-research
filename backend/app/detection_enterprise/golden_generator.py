"""Generate golden dataset from production, synthetic, and external data sources."""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDatasetEntry, GoldenDataset
from app.storage.models import Trace, State, Detection


class GoldenDataGenerator:
    """Generate golden dataset entries from various data sources."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def from_production_traces(
        self,
        traces: List[Trace],
        detections: List[Detection],
    ) -> List[GoldenDatasetEntry]:
        """
        Generate golden samples from production execution traces.

        Args:
            traces: List of execution traces
            detections: List of detected failures

        Returns:
            List of golden dataset entries
        """
        entries = []

        # Generate positive samples from detected failures
        for detection in detections:
            trace = next((t for t in traces if t.id == detection.trace_id), None)
            if not trace:
                continue

            # Get states for this trace
            states = [s for s in trace.states] if hasattr(trace, 'states') else []

            entry = GoldenDatasetEntry(
                id=f"prod_{detection.id}",
                detection_type=detection.detection_type,
                input_data=self._extract_input_data(
                    detection.detection_type,
                    states,
                    trace
                ),
                expected_detected=True,
                expected_confidence_min=max(0.0, detection.confidence / 100 - 0.1),
                expected_confidence_max=min(1.0, detection.confidence / 100 + 0.1),
                description=f"Real failure from production: {detection.detection_type.value}",
                source="production",
                tags=["real_failure", detection.method, "production"],
                source_trace_id=str(trace.id),
                human_verified=False,
            )
            entries.append(entry)

        # Generate negative samples from successful traces
        successful_traces = [t for t in traces if t.status == "success"]
        for trace in successful_traces[:50]:  # Limit to avoid explosion
            states = [s for s in trace.states] if hasattr(trace, 'states') else []

            for detection_type in DetectionType:
                entry = GoldenDatasetEntry(
                    id=f"prod_neg_{trace.id}_{detection_type.value}",
                    detection_type=detection_type,
                    input_data=self._extract_input_data(
                        detection_type,
                        states,
                        trace
                    ),
                    expected_detected=False,
                    expected_confidence_min=0.0,
                    expected_confidence_max=0.3,
                    description=f"Healthy execution - no {detection_type.value}",
                    source="production",
                    tags=["real_healthy", "production", "negative"],
                    source_trace_id=str(trace.id),
                    human_verified=False,
                )
                entries.append(entry)

        return entries

    def from_synthetic_workflows(
        self,
        workflow_dir: Path,
    ) -> List[GoldenDatasetEntry]:
        """
        Generate golden samples from synthetic test workflows.

        Args:
            workflow_dir: Path to directory containing test workflows

        Returns:
            List of golden dataset entries
        """
        entries = []

        # Map workflow categories to detection types
        category_map = {
            "loop": DetectionType.LOOP,
            "coordination": DetectionType.COORDINATION,
            "state": DetectionType.CORRUPTION,
            "persona": DetectionType.PERSONA_DRIFT,
            "resource": DetectionType.OVERFLOW,
            "hallucination": DetectionType.HALLUCINATION,
        }

        # Process each category directory
        for category, detection_type in category_map.items():
            category_dir = workflow_dir / category
            if not category_dir.exists():
                continue

            workflow_files = list(category_dir.glob("*.json"))
            for workflow_file in workflow_files:
                try:
                    with open(workflow_file) as f:
                        workflow_data = json.load(f)

                    entry = self._workflow_to_golden_entry(
                        workflow_file.stem,
                        workflow_data,
                        detection_type,
                        expected_detected=True,
                        source="synthetic",
                        tags=[category, "synthetic", "clear_positive"],
                    )
                    entries.append(entry)

                except Exception as e:
                    print(f"Error processing {workflow_file}: {e}")
                    continue

        # Also process main test workflows
        main_workflows = [
            ("01-loop-injection.json", DetectionType.LOOP),
            ("02-hallucination-injection.json", DetectionType.HALLUCINATION),
            ("03-coordination-failure.json", DetectionType.COORDINATION),
            ("04-state-corruption.json", DetectionType.CORRUPTION),
            ("05-persona-drift.json", DetectionType.PERSONA_DRIFT),
        ]

        for workflow_name, detection_type in main_workflows:
            workflow_path = workflow_dir / workflow_name
            if workflow_path.exists():
                try:
                    with open(workflow_path) as f:
                        workflow_data = json.load(f)

                    entry = self._workflow_to_golden_entry(
                        workflow_path.stem,
                        workflow_data,
                        detection_type,
                        expected_detected=True,
                        source="synthetic",
                        tags=["main_test", "synthetic", "clear_positive"],
                    )
                    entries.append(entry)

                except Exception as e:
                    print(f"Error processing {workflow_path}: {e}")

        return entries

    def from_external_templates(
        self,
        template_dir: Path,
        limit: Optional[int] = 1000,
    ) -> List[GoldenDatasetEntry]:
        """
        Generate golden samples from external workflow templates.

        Args:
            template_dir: Path to directory containing external templates
            limit: Maximum number of templates to process

        Returns:
            List of golden dataset entries
        """
        entries = []

        template_files = list(template_dir.rglob("*.json"))[:limit]

        for template_file in template_files:
            try:
                with open(template_file) as f:
                    workflow_data = json.load(f)

                # Perform structural analysis
                issues = self._analyze_workflow_structure(workflow_data)

                # Generate entries based on detected issues
                if issues.get("has_circular_refs"):
                    entry = self._workflow_to_golden_entry(
                        f"ext_{template_file.stem}",
                        workflow_data,
                        DetectionType.LOOP,
                        expected_detected=True,
                        source="external",
                        tags=["circular_refs", "external", "structural"],
                    )
                    entries.append(entry)

                if issues.get("missing_error_handling"):
                    entry = self._workflow_to_golden_entry(
                        f"ext_{template_file.stem}",
                        workflow_data,
                        DetectionType.COORDINATION,
                        expected_detected=True,
                        source="external",
                        tags=["missing_error_handling", "external", "structural"],
                    )
                    entries.append(entry)

                # If workflow is well-structured, create negative samples
                if issues.get("well_structured"):
                    for detection_type in [DetectionType.LOOP, DetectionType.COORDINATION]:
                        entry = self._workflow_to_golden_entry(
                            f"ext_neg_{template_file.stem}_{detection_type.value}",
                            workflow_data,
                            detection_type,
                            expected_detected=False,
                            source="external",
                            tags=["well_structured", "external", "negative"],
                        )
                        entries.append(entry)

            except Exception as e:
                print(f"Error processing {template_file}: {e}")
                continue

        return entries

    def augment_samples(
        self,
        samples: List[GoldenDatasetEntry],
        multiplier: int = 4,
    ) -> List[GoldenDatasetEntry]:
        """
        Generate augmented variants of existing samples.

        Args:
            samples: List of golden dataset entries to augment
            multiplier: Number of variants per sample

        Returns:
            List of augmented entries
        """
        augmented = []

        for sample in samples:
            # Method 1: Severity variations
            if multiplier >= 1:
                severe = self._create_severity_variant(sample, increase=True)
                if severe:
                    augmented.append(severe)

            if multiplier >= 2:
                mild = self._create_severity_variant(sample, increase=False)
                if mild:
                    augmented.append(mild)

            # Method 2: Edge cases
            if multiplier >= 3:
                edge = self._create_edge_case_variant(sample)
                if edge:
                    augmented.append(edge)

            # Method 3: Noise injection
            if multiplier >= 4:
                noisy = self._create_noisy_variant(sample)
                if noisy:
                    augmented.append(noisy)

        return augmented

    def _extract_input_data(
        self,
        detection_type: DetectionType,
        states: List[State],
        trace: Trace,
    ) -> Dict[str, Any]:
        """Extract input_data based on detection type requirements."""
        input_data = {}

        if detection_type == DetectionType.LOOP:
            input_data["states"] = [
                {
                    "agent_id": s.agent_id,
                    "content": str(s.state_delta.get("output", "")),
                    "state_delta": s.state_delta,
                }
                for s in states
            ]

        elif detection_type == DetectionType.PERSONA_DRIFT:
            if states:
                last_state = states[-1]
                input_data["agent"] = {
                    "id": last_state.agent_id,
                    "persona_description": last_state.state_delta.get("parameters", {}).get("systemMessage", ""),
                }
                input_data["output"] = str(last_state.state_delta.get("output", ""))

        elif detection_type == DetectionType.OVERFLOW:
            input_data["current_tokens"] = trace.total_tokens or 0
            input_data["model"] = states[0].ai_model if states and states[0].ai_model else "unknown"

        elif detection_type == DetectionType.COORDINATION:
            input_data["messages"] = [
                {
                    "from_agent": s.agent_id,
                    "content": str(s.state_delta.get("output", "")),
                    "timestamp": float(i),
                    "acknowledged": True,
                }
                for i, s in enumerate(states)
            ]
            input_data["agent_ids"] = list(set(s.agent_id for s in states))

        else:
            # Generic structure
            input_data["states"] = [
                {
                    "agent_id": s.agent_id,
                    "state_delta": s.state_delta,
                }
                for s in states
            ]

        return input_data

    def _workflow_to_golden_entry(
        self,
        workflow_id: str,
        workflow_data: Dict[str, Any],
        detection_type: DetectionType,
        expected_detected: bool,
        source: str,
        tags: List[str],
    ) -> GoldenDatasetEntry:
        """Convert workflow JSON to golden entry."""
        nodes = workflow_data.get("nodes", [])

        # Extract relevant data based on detection type
        input_data = {
            "workflow_name": workflow_data.get("name", workflow_id),
            "nodes": [
                {
                    "type": node.get("type", ""),
                    "name": node.get("name", ""),
                    "parameters": node.get("parameters", {}),
                }
                for node in nodes
            ],
        }

        # Generate deterministic ID
        content_hash = hashlib.md5(
            json.dumps(input_data, sort_keys=True).encode()
        ).hexdigest()[:8]
        entry_id = f"{source}_{detection_type.value}_{workflow_id}_{content_hash}"

        return GoldenDatasetEntry(
            id=entry_id,
            detection_type=detection_type,
            input_data=input_data,
            expected_detected=expected_detected,
            expected_confidence_min=0.7 if expected_detected else 0.0,
            expected_confidence_max=0.95 if expected_detected else 0.3,
            description=f"Generated from {source} workflow: {workflow_id}",
            source=source,
            tags=tags,
            source_workflow_id=workflow_id,
            human_verified=False,
        )

    def _analyze_workflow_structure(self, workflow_data: Dict[str, Any]) -> Dict[str, bool]:
        """Analyze workflow structure for potential issues."""
        nodes = workflow_data.get("nodes", [])
        connections = workflow_data.get("connections", {})

        issues = {
            "has_circular_refs": False,
            "missing_error_handling": False,
            "well_structured": True,
        }

        # Check for circular dependencies
        visited = set()
        for node in nodes:
            node_name = node.get("name")
            if self._has_cycle(node_name, connections, visited, set()):
                issues["has_circular_refs"] = True
                issues["well_structured"] = False

        # Check for error handling
        has_error_handling = any(
            node.get("type", "").startswith("n8n-nodes-base.if")
            or node.get("parameters", {}).get("continueOnFail")
            for node in nodes
        )
        if not has_error_handling and len(nodes) > 3:
            issues["missing_error_handling"] = True
            issues["well_structured"] = False

        return issues

    def _has_cycle(
        self,
        node: str,
        connections: Dict,
        visited: set,
        rec_stack: set,
    ) -> bool:
        """Detect cycles in workflow graph using DFS."""
        visited.add(node)
        rec_stack.add(node)

        if node in connections:
            for connection_type in connections[node].values():
                for conn in connection_type:
                    next_node = conn[0].get("node") if isinstance(conn, list) and conn else None
                    if next_node:
                        if next_node not in visited:
                            if self._has_cycle(next_node, connections, visited, rec_stack):
                                return True
                        elif next_node in rec_stack:
                            return True

        rec_stack.remove(node)
        return False

    def _create_severity_variant(
        self,
        sample: GoldenDatasetEntry,
        increase: bool,
    ) -> Optional[GoldenDatasetEntry]:
        """Create severity variant of sample."""
        # Skip if sample is negative
        if not sample.expected_detected:
            return None

        variant_id = f"{sample.id}_sev_{'inc' if increase else 'dec'}"
        conf_delta = 0.1 if increase else -0.1

        return GoldenDatasetEntry(
            id=variant_id,
            detection_type=sample.detection_type,
            input_data=sample.input_data.copy(),
            expected_detected=sample.expected_detected,
            expected_confidence_min=max(0.0, sample.expected_confidence_min + conf_delta),
            expected_confidence_max=min(1.0, sample.expected_confidence_max + conf_delta),
            description=f"Severity variant: {sample.description}",
            source=sample.source,
            tags=sample.tags + ["augmented", "severity_variant"],
            source_trace_id=sample.source_trace_id,
            source_workflow_id=sample.source_workflow_id,
            augmentation_method="severity_variation",
            human_verified=False,
        )

    def _create_edge_case_variant(
        self,
        sample: GoldenDatasetEntry,
    ) -> Optional[GoldenDatasetEntry]:
        """Create edge case variant."""
        variant_id = f"{sample.id}_edge"

        return GoldenDatasetEntry(
            id=variant_id,
            detection_type=sample.detection_type,
            input_data=sample.input_data.copy(),
            expected_detected=sample.expected_detected,
            expected_confidence_min=sample.expected_confidence_min * 0.8,
            expected_confidence_max=sample.expected_confidence_max * 0.9,
            description=f"Edge case variant: {sample.description}",
            source=sample.source,
            tags=sample.tags + ["augmented", "edge_case"],
            source_trace_id=sample.source_trace_id,
            source_workflow_id=sample.source_workflow_id,
            augmentation_method="edge_case",
            human_verified=False,
        )

    def _create_noisy_variant(
        self,
        sample: GoldenDatasetEntry,
    ) -> Optional[GoldenDatasetEntry]:
        """Create noisy variant with slightly modified data."""
        variant_id = f"{sample.id}_noisy"

        return GoldenDatasetEntry(
            id=variant_id,
            detection_type=sample.detection_type,
            input_data=sample.input_data.copy(),
            expected_detected=sample.expected_detected,
            expected_confidence_min=max(0.0, sample.expected_confidence_min - 0.05),
            expected_confidence_max=min(1.0, sample.expected_confidence_max + 0.05),
            description=f"Noisy variant: {sample.description}",
            source=sample.source,
            tags=sample.tags + ["augmented", "noisy"],
            source_trace_id=sample.source_trace_id,
            source_workflow_id=sample.source_workflow_id,
            augmentation_method="noise_injection",
            human_verified=False,
        )

    def validate_samples(
        self,
        samples: List[GoldenDatasetEntry],
    ) -> Dict[str, Any]:
        """Validate generated samples for quality and consistency."""
        validation_report = {
            "total_samples": len(samples),
            "by_type": {},
            "by_source": {},
            "issues": [],
        }

        # Count by type
        for dt in DetectionType:
            type_samples = [s for s in samples if s.detection_type == dt]
            positive = sum(1 for s in type_samples if s.expected_detected)
            validation_report["by_type"][dt.value] = {
                "total": len(type_samples),
                "positive": positive,
                "negative": len(type_samples) - positive,
            }

        # Count by source
        sources = set(s.source for s in samples)
        for source in sources:
            validation_report["by_source"][source] = len([s for s in samples if s.source == source])

        # Check for issues
        ids = [s.id for s in samples]
        if len(ids) != len(set(ids)):
            validation_report["issues"].append("Duplicate IDs found")

        for sample in samples:
            if not (0 <= sample.expected_confidence_min <= sample.expected_confidence_max <= 1):
                validation_report["issues"].append(f"Invalid confidence range for {sample.id}")

        return validation_report
