"""Parser for LangGraph run data."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.ingestion.base_provider import BaseProviderParser


@dataclass
class LangGraphStep:
    """A single graph node execution from LangGraph."""

    node: str  # Node name in the graph (e.g., "agent", "tools", "__start__")
    step_number: int
    thread_id: Optional[str] = None
    run_id: Optional[str] = None
    checkpoint_ns: Optional[str] = None  # Subgraph namespace
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    status: str = "completed"  # completed, error, interrupted
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_subgraph: bool = False  # True if this step is inside a subgraph


@dataclass
class LangGraphRun:
    """Parsed LangGraph graph execution."""

    run_id: str
    assistant_id: str
    thread_id: str
    graph_id: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str  # completed, error, interrupted, pending
    steps: List[LangGraphStep] = field(default_factory=list)
    total_tokens: int = 0
    total_steps: int = 0
    error: Optional[str] = None
    multitask_strategy: Optional[str] = None  # reject, rollback, interrupt, enqueue
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedLangGraphState:
    """State record for PISAMA storage. Parallels ParsedDifyState."""

    trace_id: str
    sequence_num: int
    agent_id: str
    state_delta: dict
    state_hash: str
    node_name: str
    latency_ms: int
    timestamp: datetime
    is_subgraph_step: bool = False
    token_count: int = 0


# Maps LangGraph node names to PISAMA span categories
NODE_NAME_MAP = {
    "__start__": "system",
    "__end__": "system",
    "agent": "agent_turn",
    "tools": "tool",
    "tool_node": "tool",
    "retrieve": "retrieval",
    "generate": "agent_turn",
    "grade_documents": "system",
    "rewrite": "agent_turn",
    "should_continue": "system",
    "route": "system",
    "supervisor": "agent_turn",
    "planner": "agent_turn",
    "executor": "agent_turn",
}


class LangGraphParser(BaseProviderParser):
    """Parses LangGraph run data into PISAMA trace format."""

    def parse_raw(self, raw_data: Dict[str, Any]) -> LangGraphRun:
        return self.parse_run(raw_data)

    def extract_states(self, execution: LangGraphRun, tenant_id: str, ingestion_mode: str = "full") -> List[ParsedLangGraphState]:
        return self.parse_to_states(execution, tenant_id, ingestion_mode=ingestion_mode)

    def parse_run(self, raw_data: Dict[str, Any]) -> LangGraphRun:
        """Parse raw webhook payload into structured graph run."""
        started_at = self._parse_datetime(raw_data.get("started_at"))
        finished_at = self._parse_datetime(raw_data.get("finished_at"))

        steps = []
        for raw_step in raw_data.get("steps", []):
            step = LangGraphStep(
                node=raw_step.get("node", "unknown"),
                step_number=raw_step.get("step_number", 0),
                thread_id=raw_step.get("thread_id"),
                run_id=raw_step.get("run_id"),
                checkpoint_ns=raw_step.get("checkpoint_ns"),
                inputs=raw_step.get("inputs", {}),
                outputs=raw_step.get("outputs", {}),
                started_at=self._parse_datetime(raw_step.get("started_at")),
                finished_at=self._parse_datetime(raw_step.get("finished_at")),
                status=raw_step.get("status", "completed"),
                error=raw_step.get("error"),
                metadata=raw_step.get("metadata", {}),
                is_subgraph=bool(raw_step.get("checkpoint_ns")),
            )
            steps.append(step)

        return LangGraphRun(
            run_id=raw_data.get("run_id", ""),
            assistant_id=raw_data.get("assistant_id", ""),
            thread_id=raw_data.get("thread_id", ""),
            graph_id=raw_data.get("graph_id", ""),
            started_at=started_at,
            finished_at=finished_at,
            status=raw_data.get("status", "completed"),
            steps=steps,
            total_tokens=raw_data.get("total_tokens", 0),
            total_steps=raw_data.get("total_steps", len(steps)),
            error=raw_data.get("error"),
            multitask_strategy=raw_data.get("multitask_strategy"),
            config=raw_data.get("config", {}),
        )

    def parse_to_states(
        self, run: LangGraphRun, tenant_id: str, ingestion_mode: str = "full"
    ) -> List[ParsedLangGraphState]:
        """Convert graph run steps to PISAMA state records."""
        states = []

        for seq, step in enumerate(run.steps):
            state_delta = self._redact_and_filter(
                {
                    "node": step.node,
                    "step_number": step.step_number,
                    "status": step.status,
                    "inputs": step.inputs,
                    "outputs": step.outputs,
                    "error": step.error,
                    "checkpoint_ns": step.checkpoint_ns,
                    "is_subgraph": step.is_subgraph,
                },
                skip_keys=["messages", "prompt", "thinking", "reasoning"],
                content_keys=["inputs", "outputs"],
                ingestion_mode=ingestion_mode,
            )

            # Compute latency from step timestamps
            latency_ms = 0
            if step.started_at and step.finished_at:
                delta = step.finished_at - step.started_at
                latency_ms = int(delta.total_seconds() * 1000)

            # Extract token count from step metadata if available
            token_count = step.metadata.get("token_count", 0)

            states.append(
                ParsedLangGraphState(
                    trace_id=run.run_id,
                    sequence_num=seq,
                    agent_id=step.node,
                    state_delta=state_delta,
                    state_hash=self._compute_hash(state_delta),
                    node_name=step.node,
                    latency_ms=max(0, latency_ms),
                    timestamp=step.started_at or run.started_at,
                    is_subgraph_step=step.is_subgraph,
                    token_count=token_count,
                )
            )

        return states


langgraph_parser = LangGraphParser()
