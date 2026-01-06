import asyncio
import random
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ExperimentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class ExperimentType(str, Enum):
    LATENCY = "latency"
    ERROR = "error"
    MALFORMED_OUTPUT = "malformed_output"
    TOOL_UNAVAILABLE = "tool_unavailable"
    UNCOOPERATIVE_AGENT = "uncooperative_agent"
    CONTEXT_TRUNCATION = "context_truncation"


class ExperimentResult(BaseModel):
    experiment_id: str
    experiment_type: ExperimentType
    status: ExperimentStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    affected_requests: int = 0
    triggered_detections: int = 0
    cascade_detected: bool = False
    notes: list[str] = Field(default_factory=list)


class ChaosExperiment(ABC, BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    experiment_type: ExperimentType
    enabled: bool = True
    probability: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True

    def should_trigger(self) -> bool:
        if not self.enabled:
            return False
        return random.random() < self.probability

    @abstractmethod
    async def apply(self, context: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_effect_description(self) -> str:
        pass


class LatencyExperiment(ChaosExperiment):
    experiment_type: ExperimentType = ExperimentType.LATENCY
    min_delay_ms: int = Field(default=100, ge=0)
    max_delay_ms: int = Field(default=5000, ge=0)
    fixed_delay_ms: Optional[int] = None

    async def apply(self, context: dict[str, Any]) -> dict[str, Any]:
        if self.fixed_delay_ms:
            delay = self.fixed_delay_ms
        else:
            delay = random.randint(self.min_delay_ms, self.max_delay_ms)
        
        await asyncio.sleep(delay / 1000.0)
        
        context["chaos_applied"] = {
            "type": self.experiment_type,
            "delay_ms": delay,
            "experiment_id": self.id,
        }
        return context

    def get_effect_description(self) -> str:
        if self.fixed_delay_ms:
            return f"Fixed {self.fixed_delay_ms}ms delay"
        return f"Random delay {self.min_delay_ms}-{self.max_delay_ms}ms"


class ErrorExperiment(ChaosExperiment):
    experiment_type: ExperimentType = ExperimentType.ERROR
    error_codes: list[int] = Field(default_factory=lambda: [500, 502, 503, 504])
    error_messages: list[str] = Field(
        default_factory=lambda: [
            "Internal server error",
            "Bad gateway",
            "Service unavailable",
            "Gateway timeout",
        ]
    )

    async def apply(self, context: dict[str, Any]) -> dict[str, Any]:
        idx = random.randint(0, len(self.error_codes) - 1)
        context["chaos_applied"] = {
            "type": self.experiment_type,
            "error_code": self.error_codes[idx],
            "error_message": self.error_messages[idx] if idx < len(self.error_messages) else "Error",
            "experiment_id": self.id,
        }
        context["chaos_error"] = True
        return context

    def get_effect_description(self) -> str:
        return f"Random error from {self.error_codes}"


class MalformedOutputExperiment(ChaosExperiment):
    experiment_type: ExperimentType = ExperimentType.MALFORMED_OUTPUT
    corruption_types: list[str] = Field(
        default_factory=lambda: ["truncate", "json_break", "encoding", "empty"]
    )

    async def apply(self, context: dict[str, Any]) -> dict[str, Any]:
        corruption = random.choice(self.corruption_types)
        original_output = context.get("output", "")
        
        if corruption == "truncate":
            corrupted = original_output[:len(original_output) // 2] if original_output else ""
        elif corruption == "json_break":
            corrupted = original_output + '{"incomplete": true'
        elif corruption == "encoding":
            corrupted = original_output.encode("utf-8", errors="ignore").decode("latin-1", errors="ignore")
        elif corruption == "empty":
            corrupted = ""
        else:
            corrupted = original_output
        
        context["original_output"] = original_output
        context["output"] = corrupted
        context["chaos_applied"] = {
            "type": self.experiment_type,
            "corruption_type": corruption,
            "experiment_id": self.id,
        }
        return context

    def get_effect_description(self) -> str:
        return f"Corrupt output via {self.corruption_types}"


class ToolUnavailableExperiment(ChaosExperiment):
    experiment_type: ExperimentType = ExperimentType.TOOL_UNAVAILABLE
    target_tools: list[str] = Field(default_factory=list)
    failure_mode: str = Field(default="timeout")

    async def apply(self, context: dict[str, Any]) -> dict[str, Any]:
        tool_name = context.get("tool_name", "")
        
        if not self.target_tools or tool_name in self.target_tools:
            context["chaos_applied"] = {
                "type": self.experiment_type,
                "tool_name": tool_name,
                "failure_mode": self.failure_mode,
                "experiment_id": self.id,
            }
            context["tool_blocked"] = True
            
            if self.failure_mode == "timeout":
                await asyncio.sleep(30)
            elif self.failure_mode == "error":
                context["chaos_error"] = True
        
        return context

    def get_effect_description(self) -> str:
        tools = ", ".join(self.target_tools) if self.target_tools else "all tools"
        return f"Block {tools} with {self.failure_mode}"


class UncooperativeAgentExperiment(ChaosExperiment):
    experiment_type: ExperimentType = ExperimentType.UNCOOPERATIVE_AGENT
    target_agents: list[str] = Field(default_factory=list)
    behaviors: list[str] = Field(
        default_factory=lambda: ["refuse", "delay", "partial", "wrong_format"]
    )

    async def apply(self, context: dict[str, Any]) -> dict[str, Any]:
        agent_name = context.get("agent_name", "")
        
        if not self.target_agents or agent_name in self.target_agents:
            behavior = random.choice(self.behaviors)
            
            context["chaos_applied"] = {
                "type": self.experiment_type,
                "agent_name": agent_name,
                "behavior": behavior,
                "experiment_id": self.id,
            }
            
            if behavior == "refuse":
                context["output"] = "I cannot complete this request."
                context["agent_refused"] = True
            elif behavior == "delay":
                await asyncio.sleep(random.uniform(5, 15))
            elif behavior == "partial":
                original = context.get("output", "")
                context["output"] = original[:len(original) // 3] if original else ""
            elif behavior == "wrong_format":
                context["output"] = "ERROR: Unexpected format"
        
        return context

    def get_effect_description(self) -> str:
        agents = ", ".join(self.target_agents) if self.target_agents else "any agent"
        return f"Make {agents} behave as {self.behaviors}"


class ContextTruncationExperiment(ChaosExperiment):
    experiment_type: ExperimentType = ExperimentType.CONTEXT_TRUNCATION
    truncation_percent: float = Field(default=0.5, ge=0.0, le=1.0)
    truncate_from: str = Field(default="end")

    async def apply(self, context: dict[str, Any]) -> dict[str, Any]:
        original_context = context.get("agent_context", "")
        if not original_context:
            return context
        
        keep_length = int(len(original_context) * (1 - self.truncation_percent))
        
        if self.truncate_from == "end":
            truncated = original_context[:keep_length]
        elif self.truncate_from == "start":
            truncated = original_context[-keep_length:]
        else:
            mid = len(original_context) // 2
            half_keep = keep_length // 2
            truncated = original_context[:half_keep] + original_context[-half_keep:]
        
        context["original_context"] = original_context
        context["agent_context"] = truncated
        context["chaos_applied"] = {
            "type": self.experiment_type,
            "truncation_percent": self.truncation_percent,
            "truncate_from": self.truncate_from,
            "experiment_id": self.id,
        }
        return context

    def get_effect_description(self) -> str:
        return f"Truncate {self.truncation_percent * 100}% from {self.truncate_from}"
