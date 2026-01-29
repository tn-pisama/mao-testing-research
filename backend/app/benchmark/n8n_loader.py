"""n8n Workflow Benchmark Loader

Loads n8n workflow JSON files from n8n-workflows/ directory and converts them
into TurnSnapshot format for testing n8n detectors.

Usage:
    loader = N8nBenchmarkLoader()
    workflows = loader.load_directory("n8n-workflows/loop/")
    for wf in workflows:
        print(f"{wf.id}: {wf.expected_failure_mode}")
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.detection.turn_aware._base import TurnSnapshot

logger = logging.getLogger(__name__)

# Map directory names to failure modes
DIRECTORY_FAILURE_MAP = {
    "loop": ["F11"],
    "coordination": ["F11"],  # Also coordination failures
    "persona": ["F4"],  # Persona drift
    "state": ["F2"],  # State corruption
    "resource": ["F3", "F6"],  # Resource/token explosion
}

# Map workflow name patterns to specific failure modes
WORKFLOW_FAILURE_MAP = {
    r"LOOP-\d+": "F11",
    r"COORD-\d+": "F11",
    r"STATE-\d+": "F2",
    r"PERSONA-\d+": "F4",
    r"RESOURCE-\d+": "F3",
}


@dataclass
class N8nBenchmarkWorkflow:
    """A single n8n workflow for benchmarking."""

    id: str
    name: str
    file_path: Path
    nodes: List[Dict[str, Any]]
    expected_failure_mode: Optional[str] = None
    source_directory: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_turn_snapshots(self) -> List[TurnSnapshot]:
        """Convert workflow to TurnSnapshot list for detector input.

        Simulates workflow execution by creating a turn for each node.
        """
        turns = []
        base_time = datetime.now()

        for i, node in enumerate(self.nodes):
            node_name = node.get("name", f"Node{i}")
            node_type = node.get("type", "unknown")
            parameters = node.get("parameters", {})

            # Simulate execution timing
            timestamp = base_time + timedelta(milliseconds=i * 1000)

            # Build turn content (simplified for testing)
            content = f"Node: {node_name} (type: {node_type})"

            # Extract relevant metadata
            turn_metadata = {
                "node_type": node_type,
                "timestamp": timestamp.isoformat(),
                "execution_time_ms": 100,  # Default execution time
                "parameters": parameters,
            }

            # Create turn snapshot
            turn = TurnSnapshot(
                turn_number=i,
                participant_type="node",
                participant_id=node_name,
                content=content,
                turn_metadata=turn_metadata,
            )

            turns.append(turn)

        return turns


class N8nBenchmarkLoader:
    """Loads n8n workflows for benchmarking detectors."""

    def __init__(self):
        self.loaded_workflows: List[N8nBenchmarkWorkflow] = []

    def _extract_failure_mode_from_path(self, file_path: Path) -> Optional[str]:
        """Determine expected failure mode from file path and name."""
        # Check directory name
        parent_dir = file_path.parent.name
        if parent_dir in DIRECTORY_FAILURE_MAP:
            modes = DIRECTORY_FAILURE_MAP[parent_dir]
            # If multiple modes possible, try to refine from filename
            for pattern, mode in WORKFLOW_FAILURE_MAP.items():
                if re.search(pattern, file_path.stem):
                    return mode
            # Return first mode from directory
            return modes[0]

        # Check filename patterns
        for pattern, mode in WORKFLOW_FAILURE_MAP.items():
            if re.search(pattern, file_path.stem):
                return mode

        return None

    def load_workflow(self, file_path: Path) -> Optional[N8nBenchmarkWorkflow]:
        """Load a single n8n workflow JSON file."""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            workflow_id = file_path.stem
            workflow_name = data.get("name", workflow_id)
            nodes = data.get("nodes", [])

            if not nodes:
                logger.warning(f"Workflow {file_path} has no nodes, skipping")
                return None

            failure_mode = self._extract_failure_mode_from_path(file_path)

            workflow = N8nBenchmarkWorkflow(
                id=workflow_id,
                name=workflow_name,
                file_path=file_path,
                nodes=nodes,
                expected_failure_mode=failure_mode,
                source_directory=file_path.parent.name,
                metadata={
                    "node_count": len(nodes),
                    "file_size": file_path.stat().st_size,
                },
            )

            return workflow

        except Exception as e:
            logger.error(f"Failed to load workflow {file_path}: {e}")
            return None

    def load_directory(
        self, directory: Path, recursive: bool = False
    ) -> List[N8nBenchmarkWorkflow]:
        """Load all workflows from a directory.

        Args:
            directory: Path to directory containing workflow JSON files
            recursive: Whether to search subdirectories

        Returns:
            List of loaded workflows
        """
        if isinstance(directory, str):
            directory = Path(directory)

        if not directory.exists():
            logger.error(f"Directory {directory} does not exist")
            return []

        pattern = "**/*.json" if recursive else "*.json"
        workflow_files = list(directory.glob(pattern))

        logger.info(f"Found {len(workflow_files)} workflow files in {directory}")

        workflows = []
        for file_path in workflow_files:
            workflow = self.load_workflow(file_path)
            if workflow:
                workflows.append(workflow)
                self.loaded_workflows.append(workflow)

        logger.info(f"Successfully loaded {len(workflows)} workflows")
        return workflows

    def load_failure_patterns(
        self, base_dir: Path
    ) -> Dict[str, List[N8nBenchmarkWorkflow]]:
        """Load all failure pattern workflows grouped by type.

        Args:
            base_dir: Base directory containing failure pattern subdirectories
                     (e.g., n8n-workflows/)

        Returns:
            Dict mapping failure pattern type to workflows
        """
        if isinstance(base_dir, str):
            base_dir = Path(base_dir)

        pattern_dirs = ["loop", "coordination", "persona", "state", "resource"]
        results = {}

        for pattern_type in pattern_dirs:
            pattern_dir = base_dir / pattern_type
            if pattern_dir.exists():
                workflows = self.load_directory(pattern_dir)
                results[pattern_type] = workflows
            else:
                logger.warning(f"Pattern directory {pattern_dir} not found")
                results[pattern_type] = []

        total = sum(len(wfs) for wfs in results.values())
        logger.info(f"Loaded {total} failure pattern workflows across {len(results)} types")

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded workflows."""
        if not self.loaded_workflows:
            return {"total": 0}

        failure_mode_counts = {}
        for wf in self.loaded_workflows:
            mode = wf.expected_failure_mode or "unknown"
            failure_mode_counts[mode] = failure_mode_counts.get(mode, 0) + 1

        return {
            "total": len(self.loaded_workflows),
            "by_failure_mode": failure_mode_counts,
            "by_directory": {
                dir_name: len([w for w in self.loaded_workflows if w.source_directory == dir_name])
                for dir_name in set(w.source_directory for w in self.loaded_workflows if w.source_directory)
            },
        }
