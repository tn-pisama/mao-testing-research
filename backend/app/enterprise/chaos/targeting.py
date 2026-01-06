import random
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class TargetType(str, Enum):
    ALL = "all"
    AGENT = "agent"
    TOOL = "tool"
    TENANT = "tenant"
    PERCENTAGE = "percentage"
    TRACE = "trace"


class ChaosTarget(BaseModel):
    target_type: TargetType
    agent_names: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    tenant_ids: list[str] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    percentage: float = Field(default=100.0, ge=0.0, le=100.0)
    exclude_production: bool = Field(default=True)

    def matches(self, context: dict[str, Any]) -> bool:
        if self.exclude_production and context.get("environment") == "production":
            return False

        if self.target_type == TargetType.ALL:
            return self._check_percentage()

        if self.target_type == TargetType.AGENT:
            agent_name = context.get("agent_name", "")
            if agent_name not in self.agent_names:
                return False
            return self._check_percentage()

        if self.target_type == TargetType.TOOL:
            tool_name = context.get("tool_name", "")
            if tool_name not in self.tool_names:
                return False
            return self._check_percentage()

        if self.target_type == TargetType.TENANT:
            tenant_id = context.get("tenant_id", "")
            if tenant_id not in self.tenant_ids:
                return False
            return self._check_percentage()

        if self.target_type == TargetType.TRACE:
            trace_id = context.get("trace_id", "")
            if trace_id not in self.trace_ids:
                return False
            return self._check_percentage()

        if self.target_type == TargetType.PERCENTAGE:
            return self._check_percentage()

        return False

    def _check_percentage(self) -> bool:
        if self.percentage >= 100.0:
            return True
        return random.random() * 100 < self.percentage

    def describe(self) -> str:
        if self.target_type == TargetType.ALL:
            return f"All requests ({self.percentage}%)"
        if self.target_type == TargetType.AGENT:
            return f"Agents: {', '.join(self.agent_names)} ({self.percentage}%)"
        if self.target_type == TargetType.TOOL:
            return f"Tools: {', '.join(self.tool_names)} ({self.percentage}%)"
        if self.target_type == TargetType.TENANT:
            return f"Tenants: {', '.join(self.tenant_ids)} ({self.percentage}%)"
        if self.target_type == TargetType.TRACE:
            return f"Traces: {', '.join(self.trace_ids)}"
        if self.target_type == TargetType.PERCENTAGE:
            return f"{self.percentage}% of all requests"
        return "Unknown target"


class TargetBuilder:
    def __init__(self):
        self._target = ChaosTarget(target_type=TargetType.ALL)

    def all(self) -> "TargetBuilder":
        self._target.target_type = TargetType.ALL
        return self

    def agents(self, *names: str) -> "TargetBuilder":
        self._target.target_type = TargetType.AGENT
        self._target.agent_names = list(names)
        return self

    def tools(self, *names: str) -> "TargetBuilder":
        self._target.target_type = TargetType.TOOL
        self._target.tool_names = list(names)
        return self

    def tenants(self, *ids: str) -> "TargetBuilder":
        self._target.target_type = TargetType.TENANT
        self._target.tenant_ids = list(ids)
        return self

    def traces(self, *ids: str) -> "TargetBuilder":
        self._target.target_type = TargetType.TRACE
        self._target.trace_ids = list(ids)
        return self

    def percentage(self, pct: float) -> "TargetBuilder":
        self._target.percentage = pct
        return self

    def include_production(self) -> "TargetBuilder":
        self._target.exclude_production = False
        return self

    def build(self) -> ChaosTarget:
        return self._target


def target() -> TargetBuilder:
    return TargetBuilder()
