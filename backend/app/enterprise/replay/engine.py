"""
Replay Engine - Executes deterministic replays.

Supports:
- Full replay: All agents use recorded responses
- Partial replay: Freeze N-1 agents, test 1 live
- What-if: Modify one response, see cascade
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from pydantic import BaseModel, Field

from .bundle import ReplayBundle
from .recorder import RecordedEvent, EventType

logger = logging.getLogger(__name__)


class ReplayMode(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    WHAT_IF = "what_if"
    VALIDATION = "validation"


class ReplayStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DIVERGED = "diverged"


class ReplayResult(BaseModel):
    replay_id: str
    bundle_id: str
    mode: ReplayMode
    status: ReplayStatus
    
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    
    events_replayed: int = 0
    events_matched: int = 0
    events_diverged: int = 0
    
    divergence_points: list[dict] = Field(default_factory=list)
    
    replay_output: Optional[dict[str, Any]] = None
    original_output: Optional[dict[str, Any]] = None
    
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class ReplayEngine:
    """
    Executes deterministic replays of recorded traces.
    
    Can operate in multiple modes:
    - FULL: Replay all agents with recorded responses
    - PARTIAL: Freeze some agents, run others live
    - WHAT_IF: Modify specific responses and observe effects
    - VALIDATION: Compare live execution with recorded
    """
    
    def __init__(
        self,
        bundle: ReplayBundle,
        mode: ReplayMode = ReplayMode.FULL,
    ):
        self.bundle = bundle
        self.mode = mode
        self.current_event_index = 0
        self.llm_response_index = 0
        self.divergences: list[dict] = []
        self.live_agents: set[str] = set()
        self.frozen_agents: set[str] = set()

    def freeze_agents(self, agent_names: list[str]):
        self.frozen_agents = set(agent_names)
        all_agents = set(self.bundle.metadata.agents_involved)
        self.live_agents = all_agents - self.frozen_agents

    def set_live_agents(self, agent_names: list[str]):
        self.live_agents = set(agent_names)
        all_agents = set(self.bundle.metadata.agents_involved)
        self.frozen_agents = all_agents - self.live_agents

    def get_next_llm_response(
        self,
        agent_name: Optional[str] = None,
    ) -> Optional[dict]:
        if self.mode == ReplayMode.FULL:
            response = self.bundle.get_frozen_llm_response(self.llm_response_index)
            self.llm_response_index += 1
            return response
        
        if self.mode == ReplayMode.PARTIAL:
            if agent_name and agent_name in self.frozen_agents:
                response = self.bundle.get_frozen_llm_response(self.llm_response_index)
                self.llm_response_index += 1
                return response
            return None
        
        return None

    def get_tool_response(self, tool_name: str) -> Optional[dict]:
        if self.mode in [ReplayMode.FULL, ReplayMode.PARTIAL]:
            return self.bundle.get_frozen_tool_response(tool_name)
        return None

    def record_divergence(
        self,
        event_index: int,
        expected: Any,
        actual: Any,
        divergence_type: str,
    ):
        self.divergences.append({
            "event_index": event_index,
            "expected": expected,
            "actual": actual,
            "type": divergence_type,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def execute_full_replay(
        self,
        event_handler: Optional[Callable[[RecordedEvent], Any]] = None,
    ) -> ReplayResult:
        import uuid
        
        replay_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        result = ReplayResult(
            replay_id=replay_id,
            bundle_id=self.bundle.metadata.bundle_id,
            mode=self.mode,
            status=ReplayStatus.RUNNING,
            started_at=started_at,
        )
        
        try:
            for i, event in enumerate(self.bundle.events):
                self.current_event_index = i
                
                if event_handler:
                    await self._maybe_async(event_handler, event)
                
                if event.event_type == EventType.LLM_RESPONSE:
                    self.llm_response_index += 1
                
                result.events_replayed += 1
                result.events_matched += 1
            
            result.status = ReplayStatus.COMPLETED
            result.replay_output = self.bundle.original_output
            result.original_output = self.bundle.original_output
            
        except Exception as e:
            logger.error(f"Replay failed: {e}")
            result.status = ReplayStatus.FAILED
            result.error = str(e)
        
        result.completed_at = datetime.utcnow()
        result.duration_ms = int(
            (result.completed_at - started_at).total_seconds() * 1000
        )
        
        return result

    async def execute_partial_replay(
        self,
        live_executor: Callable[[str, dict], Any],
    ) -> ReplayResult:
        import uuid
        
        replay_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        result = ReplayResult(
            replay_id=replay_id,
            bundle_id=self.bundle.metadata.bundle_id,
            mode=ReplayMode.PARTIAL,
            status=ReplayStatus.RUNNING,
            started_at=started_at,
        )
        
        replay_outputs = {}
        
        try:
            for i, event in enumerate(self.bundle.events):
                self.current_event_index = i
                agent_name = event.agent_name
                
                if event.event_type == EventType.LLM_RESPONSE:
                    if agent_name in self.frozen_agents:
                        response = self.bundle.get_frozen_llm_response(self.llm_response_index)
                        replay_outputs[f"llm_{self.llm_response_index}"] = response
                    else:
                        llm_request = self._find_preceding_request(i)
                        if llm_request and llm_request.input_data:
                            live_response = await self._maybe_async(
                                live_executor,
                                agent_name,
                                llm_request.input_data,
                            )
                            replay_outputs[f"llm_{self.llm_response_index}"] = live_response
                            
                            if event.output_data:
                                original = event.output_data.get("content", "")
                                actual = live_response.get("content", "") if live_response else ""
                                if original != actual:
                                    self.record_divergence(i, original, actual, "llm_response")
                                    result.events_diverged += 1
                    
                    self.llm_response_index += 1
                
                result.events_replayed += 1
            
            if self.divergences:
                result.status = ReplayStatus.DIVERGED
                result.divergence_points = self.divergences
            else:
                result.status = ReplayStatus.COMPLETED
            
            result.replay_output = replay_outputs
            result.original_output = self.bundle.original_output
            
        except Exception as e:
            logger.error(f"Partial replay failed: {e}")
            result.status = ReplayStatus.FAILED
            result.error = str(e)
        
        result.completed_at = datetime.utcnow()
        result.duration_ms = int(
            (result.completed_at - started_at).total_seconds() * 1000
        )
        
        return result

    async def execute_validation_replay(
        self,
        live_executor: Callable[[str, dict], Any],
        comparison_threshold: float = 0.9,
    ) -> ReplayResult:
        import uuid
        
        replay_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        result = ReplayResult(
            replay_id=replay_id,
            bundle_id=self.bundle.metadata.bundle_id,
            mode=ReplayMode.VALIDATION,
            status=ReplayStatus.RUNNING,
            started_at=started_at,
        )
        
        try:
            for i, event in enumerate(self.bundle.events):
                self.current_event_index = i
                
                if event.event_type == EventType.LLM_RESPONSE:
                    request = self._find_preceding_request(i)
                    if request and request.input_data:
                        live_response = await self._maybe_async(
                            live_executor,
                            event.agent_name,
                            request.input_data,
                        )
                        
                        if event.output_data and live_response:
                            similarity = self._compute_similarity(
                                event.output_data.get("content", ""),
                                live_response.get("content", ""),
                            )
                            
                            if similarity < comparison_threshold:
                                self.record_divergence(
                                    i,
                                    event.output_data.get("content", ""),
                                    live_response.get("content", ""),
                                    "semantic_divergence",
                                )
                                result.events_diverged += 1
                            else:
                                result.events_matched += 1
                
                result.events_replayed += 1
            
            if result.events_diverged > 0:
                result.status = ReplayStatus.DIVERGED
            else:
                result.status = ReplayStatus.COMPLETED
            
            result.divergence_points = self.divergences
            
        except Exception as e:
            logger.error(f"Validation replay failed: {e}")
            result.status = ReplayStatus.FAILED
            result.error = str(e)
        
        result.completed_at = datetime.utcnow()
        result.duration_ms = int(
            (result.completed_at - started_at).total_seconds() * 1000
        )
        
        return result

    def _find_preceding_request(self, response_index: int) -> Optional[RecordedEvent]:
        for i in range(response_index - 1, -1, -1):
            if self.bundle.events[i].event_type == EventType.LLM_REQUEST:
                return self.bundle.events[i]
        return None

    def _compute_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0 if text1 != text2 else 1.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)

    async def _maybe_async(self, func: Callable, *args) -> Any:
        result = func(*args)
        if asyncio.iscoroutine(result):
            return await result
        return result

    def reset(self):
        self.current_event_index = 0
        self.llm_response_index = 0
        self.divergences = []
