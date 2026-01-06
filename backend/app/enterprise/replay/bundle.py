"""
Replay Bundle - Storage format for replay data.

A bundle contains all the data needed to replay a trace:
- Original trace metadata
- Recorded events (LLM responses, tool outputs)
- Checkpoints for partial replay
"""

import gzip
import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from .recorder import RecordedEvent, EventType


class BundleMetadata(BaseModel):
    bundle_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str
    tenant_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    original_duration_ms: int
    event_count: int
    llm_call_count: int
    tool_call_count: int
    checkpoint_count: int
    
    models_used: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    agents_involved: list[str] = Field(default_factory=list)
    
    total_tokens: int = 0
    compressed_size_bytes: Optional[int] = None
    checksum: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class ReplayBundle(BaseModel):
    metadata: BundleMetadata
    events: list[RecordedEvent] = Field(default_factory=list)
    
    original_input: Optional[dict[str, Any]] = None
    original_output: Optional[dict[str, Any]] = None
    
    frozen_responses: dict[str, dict] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_recorder(
        cls,
        trace_id: str,
        tenant_id: str,
        events: list[RecordedEvent],
        original_input: Optional[dict] = None,
        original_output: Optional[dict] = None,
        duration_ms: int = 0,
    ) -> "ReplayBundle":
        llm_responses = [e for e in events if e.event_type == EventType.LLM_RESPONSE]
        tool_responses = [e for e in events if e.event_type == EventType.TOOL_RESPONSE]
        checkpoints = [e for e in events if e.event_type == EventType.CHECKPOINT]
        
        models = list(set(e.model for e in llm_responses if e.model))
        tools = list(set(
            e.input_data.get("tool_name", "")
            for e in tool_responses
            if e.input_data
        ))
        agents = list(set(e.agent_name for e in events if e.agent_name))
        total_tokens = sum(e.tokens_used or 0 for e in llm_responses)
        
        frozen = {}
        for i, event in enumerate(llm_responses):
            key = f"llm_{i}"
            frozen[key] = {
                "content": event.output_data.get("content") if event.output_data else "",
                "tool_calls": event.output_data.get("tool_calls") if event.output_data else None,
                "model": event.model,
            }
        
        for i, event in enumerate(tool_responses):
            key = f"tool_{event.input_data.get('tool_name', i)}" if event.input_data else f"tool_{i}"
            frozen[key] = {
                "result": event.output_data.get("result") if event.output_data else None,
                "success": event.output_data.get("success", True) if event.output_data else True,
            }
        
        metadata = BundleMetadata(
            trace_id=trace_id,
            tenant_id=tenant_id,
            original_duration_ms=duration_ms,
            event_count=len(events),
            llm_call_count=len(llm_responses),
            tool_call_count=len(tool_responses),
            checkpoint_count=len(checkpoints),
            models_used=models,
            tools_used=tools,
            agents_involved=agents,
            total_tokens=total_tokens,
        )
        
        bundle = cls(
            metadata=metadata,
            events=events,
            original_input=original_input,
            original_output=original_output,
            frozen_responses=frozen,
        )
        
        bundle.metadata.checksum = bundle.compute_checksum()
        
        return bundle

    def compute_checksum(self) -> str:
        data = {
            "trace_id": self.metadata.trace_id,
            "event_count": self.metadata.event_count,
            "events": [e.checksum for e in self.events],
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get_frozen_llm_response(self, index: int) -> Optional[dict]:
        key = f"llm_{index}"
        return self.frozen_responses.get(key)

    def get_frozen_tool_response(self, tool_name: str) -> Optional[dict]:
        key = f"tool_{tool_name}"
        return self.frozen_responses.get(key)

    def get_checkpoint(self, name: str) -> Optional[RecordedEvent]:
        for event in self.events:
            if event.event_type == EventType.CHECKPOINT:
                if event.input_data and event.input_data.get("name") == name:
                    return event
        return None

    def get_events_after_checkpoint(self, checkpoint_name: str) -> list[RecordedEvent]:
        checkpoint = self.get_checkpoint(checkpoint_name)
        if not checkpoint:
            return self.events
        
        return [e for e in self.events if e.sequence_number > checkpoint.sequence_number]

    def serialize(self, compress: bool = True) -> bytes:
        data = self.json().encode("utf-8")
        if compress:
            data = gzip.compress(data)
            self.metadata.compressed_size_bytes = len(data)
        return data

    @classmethod
    def deserialize(cls, data: bytes, compressed: bool = True) -> "ReplayBundle":
        if compressed:
            data = gzip.decompress(data)
        return cls.parse_raw(data)

    def to_partial_bundle(
        self,
        freeze_agents: list[str],
    ) -> "ReplayBundle":
        frozen = dict(self.frozen_responses)
        
        for event in self.events:
            if event.agent_name in freeze_agents:
                if event.event_type == EventType.LLM_RESPONSE:
                    key = f"frozen_agent_{event.agent_name}_{event.sequence_number}"
                    frozen[key] = event.output_data
        
        return ReplayBundle(
            metadata=self.metadata,
            events=self.events,
            original_input=self.original_input,
            original_output=self.original_output,
            frozen_responses=frozen,
        )

    def create_what_if_bundle(
        self,
        modifications: dict[int, dict],
    ) -> "ReplayBundle":
        modified_events = []
        for event in self.events:
            if event.sequence_number in modifications:
                mod = modifications[event.sequence_number]
                new_event = event.copy()
                if "output_data" in mod:
                    new_event.output_data = mod["output_data"]
                if "input_data" in mod:
                    new_event.input_data = mod["input_data"]
                new_event.checksum = new_event.compute_checksum()
                modified_events.append(new_event)
            else:
                modified_events.append(event)
        
        return ReplayBundle(
            metadata=self.metadata.copy(),
            events=modified_events,
            original_input=self.original_input,
            original_output=self.original_output,
            frozen_responses=self.frozen_responses,
        )
