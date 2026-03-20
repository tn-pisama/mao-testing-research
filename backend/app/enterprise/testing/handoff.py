"""
Handoff Extractor - Identifies and analyzes agent-to-agent handoffs.

Extracts:
- Handoff points from traces
- Context passed between agents
- Sender → receiver relationships
- Handoff timing and latency
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HandoffType(str, Enum):
    SEQUENTIAL = "sequential"
    DELEGATION = "delegation"
    CALLBACK = "callback"
    BROADCAST = "broadcast"
    CONDITIONAL = "conditional"


class HandoffStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class Handoff:
    id: str
    handoff_type: HandoffType
    
    sender_agent: str
    receiver_agent: str
    
    context_passed: dict[str, Any]
    context_received: dict[str, Any]
    
    sender_output: str
    receiver_input: str
    
    timestamp: datetime
    latency_ms: int
    
    status: HandoffStatus = HandoffStatus.SUCCESS
    error: Optional[str] = None
    
    fields_expected: list[str] = field(default_factory=list)
    fields_received: list[str] = field(default_factory=list)
    fields_missing: list[str] = field(default_factory=list)


@dataclass
class HandoffAnalysis:
    total_handoffs: int
    successful_handoffs: int
    failed_handoffs: int
    
    avg_latency_ms: float
    max_latency_ms: int
    
    context_completeness: float
    data_loss_detected: bool
    circular_handoffs: list[tuple[str, str]]
    
    agents_involved: list[str]
    handoff_graph: dict[str, list[str]]
    
    issues: list[str] = field(default_factory=list)


class HandoffExtractor:
    """
    Extracts and analyzes handoffs from multi-agent traces.
    
    Identifies handoff points, extracts context, and builds
    the agent communication graph.
    """
    
    def __init__(
        self,
        context_fields: Optional[list[str]] = None,
        latency_threshold_ms: int = 5000,
    ):
        self.context_fields = context_fields or []
        self.latency_threshold_ms = latency_threshold_ms

    def extract_from_trace(self, trace: dict) -> list[Handoff]:
        handoffs = []
        spans = trace.get("spans", [])
        
        if len(spans) < 2:
            return handoffs
        
        for i in range(len(spans) - 1):
            sender = spans[i]
            receiver = spans[i + 1]
            
            if self._is_handoff(sender, receiver):
                handoff = self._create_handoff(sender, receiver, i)
                handoffs.append(handoff)
        
        return handoffs

    def _is_handoff(self, sender: dict, receiver: dict) -> bool:
        sender_agent = sender.get("name", sender.get("agent_name", ""))
        receiver_agent = receiver.get("name", receiver.get("agent_name", ""))
        
        if not sender_agent or not receiver_agent:
            return False
        
        if sender_agent == receiver_agent:
            return False
        
        sender_type = sender.get("type", "")
        receiver_type = receiver.get("type", "")
        
        if sender_type in ["tool", "function"] or receiver_type in ["tool", "function"]:
            return False
        
        return True

    def _create_handoff(
        self,
        sender: dict,
        receiver: dict,
        index: int,
    ) -> Handoff:
        sender_agent = sender.get("name", sender.get("agent_name", f"agent_{index}"))
        receiver_agent = receiver.get("name", receiver.get("agent_name", f"agent_{index + 1}"))
        
        sender_output = ""
        if sender.get("output"):
            if isinstance(sender["output"], dict):
                sender_output = sender["output"].get("content", str(sender["output"]))
            else:
                sender_output = str(sender["output"])
        
        receiver_input = ""
        if receiver.get("input"):
            if isinstance(receiver["input"], dict):
                receiver_input = receiver["input"].get("context", str(receiver["input"]))
            else:
                receiver_input = str(receiver["input"])
        
        context_passed = self._extract_context(sender.get("output", {}))
        context_received = self._extract_context(receiver.get("input", {}))
        
        sender_end = sender.get("end_time") or sender.get("timestamp")
        receiver_start = receiver.get("start_time") or receiver.get("timestamp")
        
        latency = 0
        if sender_end and receiver_start:
            try:
                if isinstance(sender_end, str):
                    sender_end = datetime.fromisoformat(sender_end.replace("Z", "+00:00"))
                if isinstance(receiver_start, str):
                    receiver_start = datetime.fromisoformat(receiver_start.replace("Z", "+00:00"))
                latency = int((receiver_start - sender_end).total_seconds() * 1000)
            except Exception as e:
                logger.warning("Failed to parse handoff timestamps: %s", e)

        
        fields_expected = list(context_passed.keys())
        fields_received = list(context_received.keys())
        fields_missing = [f for f in fields_expected if f not in fields_received]
        
        status = HandoffStatus.SUCCESS
        if fields_missing:
            status = HandoffStatus.PARTIAL
        if latency > self.latency_threshold_ms:
            status = HandoffStatus.TIMEOUT
        
        handoff_type = self._determine_handoff_type(sender, receiver)
        
        return Handoff(
            id=f"handoff_{index}",
            handoff_type=handoff_type,
            sender_agent=sender_agent,
            receiver_agent=receiver_agent,
            context_passed=context_passed,
            context_received=context_received,
            sender_output=sender_output,
            receiver_input=receiver_input,
            timestamp=datetime.utcnow(),
            latency_ms=latency,
            status=status,
            fields_expected=fields_expected,
            fields_received=fields_received,
            fields_missing=fields_missing,
        )

    def _extract_context(self, data: Any) -> dict[str, Any]:
        if not data:
            return {}
        
        if isinstance(data, dict):
            context = {}
            for key, value in data.items():
                if key in ["context", "state", "memory", "shared"]:
                    if isinstance(value, dict):
                        context.update(value)
                    else:
                        context[key] = value
                elif key not in ["content", "role", "tool_calls"]:
                    context[key] = value
            return context
        
        return {"raw": str(data)}

    def _determine_handoff_type(self, sender: dict, receiver: dict) -> HandoffType:
        sender_attrs = sender.get("attributes", {})
        receiver_attrs = receiver.get("attributes", {})
        
        if sender_attrs.get("delegates_to") == receiver.get("name"):
            return HandoffType.DELEGATION
        
        if receiver_attrs.get("callback_from") == sender.get("name"):
            return HandoffType.CALLBACK
        
        if sender_attrs.get("broadcast"):
            return HandoffType.BROADCAST
        
        if sender_attrs.get("condition") or receiver_attrs.get("condition"):
            return HandoffType.CONDITIONAL
        
        return HandoffType.SEQUENTIAL

    def analyze(self, handoffs: list[Handoff]) -> HandoffAnalysis:
        if not handoffs:
            return HandoffAnalysis(
                total_handoffs=0,
                successful_handoffs=0,
                failed_handoffs=0,
                avg_latency_ms=0,
                max_latency_ms=0,
                context_completeness=1.0,
                data_loss_detected=False,
                circular_handoffs=[],
                agents_involved=[],
                handoff_graph={},
            )
        
        successful = sum(1 for h in handoffs if h.status == HandoffStatus.SUCCESS)
        failed = sum(1 for h in handoffs if h.status == HandoffStatus.FAILED)
        
        latencies = [h.latency_ms for h in handoffs if h.latency_ms > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        
        total_expected = sum(len(h.fields_expected) for h in handoffs)
        total_received = sum(len(h.fields_received) for h in handoffs)
        completeness = total_received / total_expected if total_expected > 0 else 1.0
        
        data_loss = any(h.fields_missing for h in handoffs)
        
        graph: dict[str, list[str]] = {}
        for h in handoffs:
            if h.sender_agent not in graph:
                graph[h.sender_agent] = []
            graph[h.sender_agent].append(h.receiver_agent)
        
        circular = self._detect_circular_handoffs(graph)
        
        agents = list(set(
            [h.sender_agent for h in handoffs] + [h.receiver_agent for h in handoffs]
        ))
        
        issues = []
        if data_loss:
            issues.append("Data loss detected in handoffs")
        if circular:
            issues.append(f"Circular handoffs detected: {circular}")
        if max_latency > self.latency_threshold_ms:
            issues.append(f"High latency handoffs: {max_latency}ms")
        
        return HandoffAnalysis(
            total_handoffs=len(handoffs),
            successful_handoffs=successful,
            failed_handoffs=failed,
            avg_latency_ms=avg_latency,
            max_latency_ms=max_latency,
            context_completeness=completeness,
            data_loss_detected=data_loss,
            circular_handoffs=circular,
            agents_involved=agents,
            handoff_graph=graph,
            issues=issues,
        )

    def _detect_circular_handoffs(
        self,
        graph: dict[str, list[str]],
    ) -> list[tuple[str, str]]:
        circular = []
        
        for sender, receivers in graph.items():
            for receiver in receivers:
                if receiver in graph and sender in graph.get(receiver, []):
                    if (receiver, sender) not in circular:
                        circular.append((sender, receiver))
        
        return circular

    def get_handoff_chain(
        self,
        handoffs: list[Handoff],
        start_agent: str,
    ) -> list[Handoff]:
        chain = []
        current = start_agent
        visited = set()
        
        while True:
            found = None
            for h in handoffs:
                if h.sender_agent == current and h.id not in visited:
                    found = h
                    visited.add(h.id)
                    break
            
            if not found:
                break
            
            chain.append(found)
            current = found.receiver_agent
        
        return chain
