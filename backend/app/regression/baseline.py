"""
Baseline Store - Captures and stores golden traces for regression testing.

Stores:
- Known-good prompt → output pairs
- Model version fingerprints
- Performance metrics baselines
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BaselineEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    prompt_hash: str
    prompt_text: str
    
    output_text: str
    output_hash: str
    
    model: str
    model_version: Optional[str] = None
    
    tokens_used: int = 0
    latency_ms: int = 0
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def create(
        cls,
        prompt: str,
        output: str,
        model: str,
        model_version: Optional[str] = None,
        tokens_used: int = 0,
        latency_ms: int = 0,
        tags: Optional[list[str]] = None,
    ) -> "BaselineEntry":
        return cls(
            prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()[:32],
            prompt_text=prompt,
            output_text=output,
            output_hash=hashlib.sha256(output.encode()).hexdigest()[:32],
            model=model,
            model_version=model_version,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            tags=tags or [],
        )


class Baseline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    
    tenant_id: str
    agent_name: Optional[str] = None
    
    entries: list[BaselineEntry] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    is_active: bool = True
    version: int = 1
    
    models_covered: list[str] = Field(default_factory=list)
    total_prompts: int = 0
    
    pass_rate_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    latency_threshold_ms: int = Field(default=5000, ge=0)

    class Config:
        arbitrary_types_allowed = True

    def add_entry(self, entry: BaselineEntry):
        self.entries.append(entry)
        self.total_prompts = len(self.entries)
        if entry.model not in self.models_covered:
            self.models_covered.append(entry.model)
        self.updated_at = datetime.utcnow()

    def get_entry_by_prompt(self, prompt: str) -> Optional[BaselineEntry]:
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:32]
        for entry in self.entries:
            if entry.prompt_hash == prompt_hash:
                return entry
        return None

    def get_entries_by_model(self, model: str) -> list[BaselineEntry]:
        return [e for e in self.entries if e.model == model]


class BaselineStore:
    """
    In-memory store for baselines. Production would use database.
    """
    
    def __init__(self):
        self.baselines: dict[str, Baseline] = {}
        self.by_tenant: dict[str, list[str]] = {}

    def create_baseline(
        self,
        name: str,
        description: str,
        tenant_id: str,
        agent_name: Optional[str] = None,
    ) -> Baseline:
        baseline = Baseline(
            name=name,
            description=description,
            tenant_id=tenant_id,
            agent_name=agent_name,
        )
        self.baselines[baseline.id] = baseline
        
        if tenant_id not in self.by_tenant:
            self.by_tenant[tenant_id] = []
        self.by_tenant[tenant_id].append(baseline.id)
        
        return baseline

    def get_baseline(self, baseline_id: str) -> Optional[Baseline]:
        return self.baselines.get(baseline_id)

    def get_baselines_for_tenant(self, tenant_id: str) -> list[Baseline]:
        baseline_ids = self.by_tenant.get(tenant_id, [])
        return [self.baselines[bid] for bid in baseline_ids if bid in self.baselines]

    def get_active_baseline(
        self,
        tenant_id: str,
        agent_name: Optional[str] = None,
    ) -> Optional[Baseline]:
        baselines = self.get_baselines_for_tenant(tenant_id)
        active = [b for b in baselines if b.is_active]
        
        if agent_name:
            agent_baselines = [b for b in active if b.agent_name == agent_name]
            if agent_baselines:
                return max(agent_baselines, key=lambda b: b.updated_at)
        
        if active:
            return max(active, key=lambda b: b.updated_at)
        
        return None

    def add_entry_to_baseline(
        self,
        baseline_id: str,
        prompt: str,
        output: str,
        model: str,
        model_version: Optional[str] = None,
        tokens_used: int = 0,
        latency_ms: int = 0,
    ) -> Optional[BaselineEntry]:
        baseline = self.get_baseline(baseline_id)
        if not baseline:
            return None
        
        entry = BaselineEntry.create(
            prompt=prompt,
            output=output,
            model=model,
            model_version=model_version,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
        
        baseline.add_entry(entry)
        return entry

    def create_baseline_from_trace(
        self,
        trace: dict,
        name: str,
        tenant_id: str,
    ) -> Baseline:
        baseline = self.create_baseline(
            name=name,
            description=f"Auto-generated from trace {trace.get('trace_id', 'unknown')}",
            tenant_id=tenant_id,
        )
        
        spans = trace.get("spans", [])
        for span in spans:
            if span.get("type") in ["llm", "chat", "completion"]:
                input_data = span.get("input", {})
                output_data = span.get("output", {})
                
                prompt = ""
                if isinstance(input_data, dict):
                    messages = input_data.get("messages", [])
                    if messages:
                        prompt = json.dumps(messages)
                    else:
                        prompt = input_data.get("prompt", str(input_data))
                else:
                    prompt = str(input_data)
                
                output = ""
                if isinstance(output_data, dict):
                    output = output_data.get("content", str(output_data))
                else:
                    output = str(output_data)
                
                if prompt and output:
                    self.add_entry_to_baseline(
                        baseline_id=baseline.id,
                        prompt=prompt,
                        output=output,
                        model=span.get("model", "unknown"),
                        model_version=span.get("model_version"),
                        tokens_used=span.get("tokens_used", 0),
                        latency_ms=span.get("latency_ms", 0),
                    )
        
        return baseline

    def deactivate_baseline(self, baseline_id: str) -> bool:
        baseline = self.get_baseline(baseline_id)
        if baseline:
            baseline.is_active = False
            return True
        return False

    def delete_baseline(self, baseline_id: str) -> bool:
        if baseline_id in self.baselines:
            baseline = self.baselines[baseline_id]
            del self.baselines[baseline_id]
            
            if baseline.tenant_id in self.by_tenant:
                self.by_tenant[baseline.tenant_id] = [
                    bid for bid in self.by_tenant[baseline.tenant_id]
                    if bid != baseline_id
                ]
            return True
        return False


baseline_store = BaselineStore()
