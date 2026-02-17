"""Parser for Dify workflow run data."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.ingestion.base_provider import BaseProviderParser


@dataclass
class DifyNodeEvent:
    """A single workflow node execution from Dify."""

    node_id: str
    node_type: str  # llm, code, tool, http_request, knowledge_retrieval,
    # question_classifier, if_else, template_transform,
    # variable_aggregator, parameter_extractor, iteration, loop
    title: str
    status: str  # running, succeeded, failed, stopped
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    token_count: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    iteration_index: Optional[int] = None  # Index within iteration/loop block
    parent_node_id: Optional[str] = None  # Parent iteration/loop node


@dataclass
class DifyWorkflowRun:
    """Parsed Dify workflow execution."""

    workflow_run_id: str
    app_id: str
    app_name: str
    app_type: str  # chatbot, agent, workflow, chatflow
    started_at: datetime
    finished_at: Optional[datetime]
    status: str  # running, succeeded, failed, stopped
    total_tokens: int = 0
    total_steps: int = 0
    nodes: List[DifyNodeEvent] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ParsedDifyState:
    """State record for PISAMA storage. Parallels ParsedOpenClawState."""

    trace_id: str
    sequence_num: int
    agent_id: str
    state_delta: dict
    state_hash: str
    node_type: str
    latency_ms: int
    timestamp: datetime
    is_iteration_child: bool = False
    token_count: int = 0


# Maps Dify node types to PISAMA span categories
NODE_TYPE_MAP = {
    "llm": "agent_turn",
    "tool": "tool",
    "http_request": "tool",
    "code": "tool",
    "knowledge_retrieval": "retrieval",
    "question_classifier": "system",
    "if_else": "system",
    "template_transform": "system",
    "variable_aggregator": "system",
    "parameter_extractor": "system",
    "iteration": "workflow",
    "loop": "workflow",
}

ITERATION_NODE_TYPES = {"iteration", "loop"}


class DifyParser(BaseProviderParser):
    """Parses Dify workflow run data into PISAMA trace format."""

    def parse_raw(self, raw_data: Dict[str, Any]) -> DifyWorkflowRun:
        return self.parse_workflow_run(raw_data)

    def extract_states(self, execution: DifyWorkflowRun, tenant_id: str, ingestion_mode: str = "full") -> List[ParsedDifyState]:
        return self.parse_to_states(execution, tenant_id, ingestion_mode=ingestion_mode)

    def parse_workflow_run(self, raw_data: Dict[str, Any]) -> DifyWorkflowRun:
        """Parse raw webhook payload into structured workflow run."""
        started_at = self._parse_datetime(raw_data.get("started_at"))
        finished_at = self._parse_datetime(raw_data.get("finished_at"))

        nodes = []
        # Track iteration/loop parent nodes
        iteration_parents: set[str] = set()

        for raw_node in raw_data.get("nodes", []):
            node_type = raw_node.get("node_type", "unknown")

            if node_type in ITERATION_NODE_TYPES:
                iteration_parents.add(raw_node.get("node_id", ""))

            node = DifyNodeEvent(
                node_id=raw_node.get("node_id", ""),
                node_type=node_type,
                title=raw_node.get("title", ""),
                status=raw_node.get("status", "unknown"),
                inputs=raw_node.get("inputs", {}),
                outputs=raw_node.get("outputs", {}),
                started_at=self._parse_datetime(raw_node.get("started_at")),
                finished_at=self._parse_datetime(raw_node.get("finished_at")),
                token_count=raw_node.get("token_count", 0),
                error=raw_node.get("error"),
                metadata=raw_node.get("metadata", {}),
                iteration_index=raw_node.get("iteration_index"),
                parent_node_id=raw_node.get("parent_node_id"),
            )
            nodes.append(node)

        return DifyWorkflowRun(
            workflow_run_id=raw_data.get("workflow_run_id", ""),
            app_id=raw_data.get("app_id", ""),
            app_name=raw_data.get("app_name", ""),
            app_type=raw_data.get("app_type", "workflow"),
            started_at=started_at,
            finished_at=finished_at,
            status=raw_data.get("status", "succeeded"),
            total_tokens=raw_data.get("total_tokens", 0),
            total_steps=raw_data.get("total_steps", 0),
            nodes=nodes,
            error=raw_data.get("error"),
        )

    def parse_to_states(
        self, run: DifyWorkflowRun, tenant_id: str, ingestion_mode: str = "full"
    ) -> List[ParsedDifyState]:
        """Convert workflow run nodes to PISAMA state records."""
        states = []

        for seq, node in enumerate(run.nodes):
            # Determine if this node is a child of an iteration/loop block
            is_iteration_child = (
                node.parent_node_id is not None
                or node.iteration_index is not None
            )

            state_delta = self._redact_and_filter(
                {
                    "node_type": node.node_type,
                    "title": node.title,
                    "status": node.status,
                    "inputs": node.inputs,
                    "outputs": node.outputs,
                    "error": node.error,
                    "iteration_index": node.iteration_index,
                    "parent_node_id": node.parent_node_id,
                },
                skip_keys=["messages", "prompt", "thinking", "reasoning"],
                content_keys=["inputs", "outputs"],
                ingestion_mode=ingestion_mode,
            )

            # Compute latency from node timestamps
            latency_ms = 0
            if node.started_at and node.finished_at:
                delta = node.finished_at - node.started_at
                latency_ms = int(delta.total_seconds() * 1000)

            states.append(
                ParsedDifyState(
                    trace_id=run.workflow_run_id,
                    sequence_num=seq,
                    agent_id=node.title or node.node_type,
                    state_delta=state_delta,
                    state_hash=self._compute_hash(state_delta),
                    node_type=node.node_type,
                    latency_ms=max(0, latency_ms),
                    timestamp=node.started_at or run.started_at,
                    is_iteration_child=is_iteration_child,
                    token_count=node.token_count,
                )
            )

        return states


dify_parser = DifyParser()
