"""MAO Testing SDK Tracer implementation."""

from __future__ import annotations
import logging
import random
import threading
import time
from typing import Any, Dict, List, Optional, Callable
from queue import Queue, Empty

import httpx
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

from .config import MAOConfig, SamplingRule
from .session import TraceSession, SessionData
from .errors import TracingError, ExportError

logger = logging.getLogger("mao_testing")


class MAOTracer:
    """Main tracer for MAO Testing SDK."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        environment: Optional[str] = None,
        service_name: Optional[str] = None,
        sample_rate: Optional[float] = None,
        batch_size: Optional[int] = None,
        flush_interval: Optional[float] = None,
        on_error: Optional[str] = None,
        sampling_rules: Optional[List[SamplingRule]] = None,
        config: Optional[MAOConfig] = None,
    ):
        if config:
            self._config = config
        else:
            self._config = MAOConfig(
                api_key=api_key,
                endpoint=endpoint or "https://api.mao-testing.com",
                environment=environment or "development",
                service_name=service_name or "mao-agent-system",
                sample_rate=sample_rate if sample_rate is not None else 1.0,
                batch_size=batch_size or 100,
                flush_interval=flush_interval or 5.0,
                on_error=on_error or "log",
                sampling_rules=sampling_rules or [],
            )
        
        self._sessions: List[TraceSession] = []
        self._export_queue: Queue[SessionData] = Queue()
        self._export_thread: Optional[threading.Thread] = None
        self._shutdown = threading.Event()
        self._http_client: Optional[httpx.Client] = None
        
        self._setup_otel()
        self._start_export_thread()
    
    def _setup_otel(self) -> None:
        """Configure OpenTelemetry."""
        resource = Resource.create({
            "service.name": self._config.service_name,
            "deployment.environment": self._config.environment,
            "mao.sdk.version": "0.1.0",
        })
        
        provider = TracerProvider(resource=resource)
        
        if self._config.api_key:
            headers = {"Authorization": f"Bearer {self._config.api_key}"}
            exporter = OTLPSpanExporter(
                endpoint=f"{self._config.endpoint}/v1/traces",
                headers=headers,
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))
        
        otel_trace.set_tracer_provider(provider)
    
    def _start_export_thread(self) -> None:
        """Start background thread for exporting sessions."""
        self._export_thread = threading.Thread(
            target=self._export_loop,
            daemon=True,
            name="mao-export",
        )
        self._export_thread.start()
    
    def _export_loop(self) -> None:
        """Background loop for exporting sessions."""
        batch: List[SessionData] = []
        last_flush = time.time()
        
        while not self._shutdown.is_set():
            try:
                session = self._export_queue.get(timeout=0.5)
                batch.append(session)
                
                if len(batch) >= self._config.batch_size:
                    self._export_batch(batch)
                    batch = []
                    last_flush = time.time()
                    
            except Empty:
                if batch and (time.time() - last_flush) >= self._config.flush_interval:
                    self._export_batch(batch)
                    batch = []
                    last_flush = time.time()
        
        if batch:
            self._export_batch(batch)
    
    def _export_batch(self, batch: List[SessionData]) -> None:
        """Export a batch of sessions to the backend."""
        if not self._config.api_key:
            return
        
        if self._http_client is None:
            self._http_client = httpx.Client(
                base_url=self._config.endpoint,
                headers={"Authorization": f"Bearer {self._config.api_key}"},
                timeout=30.0,
            )
        
        try:
            payload = {
                "sessions": [self._session_to_dict(s) for s in batch]
            }
            
            response = self._http_client.post("/v1/sessions", json=payload)
            response.raise_for_status()
            
        except Exception as e:
            self._handle_error(ExportError(f"Failed to export sessions: {e}"))
    
    def _session_to_dict(self, session: SessionData) -> Dict[str, Any]:
        """Convert session data to dictionary for export."""
        return {
            "trace_id": session.trace_id,
            "name": session.name,
            "start_time_ns": session.start_time_ns,
            "end_time_ns": session.end_time_ns,
            "metadata": session.metadata,
            "tags": session.tags,
            "spans": [
                {
                    "name": s.name,
                    "span_id": s.span_id,
                    "parent_span_id": s.parent_span_id,
                    "start_time_ns": s.start_time_ns,
                    "end_time_ns": s.end_time_ns,
                    "attributes": s.attributes,
                    "events": s.events,
                    "status": s.status,
                    "status_message": s.status_message,
                }
                for s in session.spans
            ],
            "states": [
                {
                    "name": s.name,
                    "data": s.data,
                    "timestamp_ns": s.timestamp_ns,
                    "agent_id": s.agent_id,
                }
                for s in session.states
            ],
            "status": session.status,
            "framework": session.framework,
            "environment": session.environment,
            "service_name": session.service_name,
        }
    
    def _handle_error(self, error: Exception) -> None:
        """Handle errors based on configuration."""
        if self._config.on_error == "raise":
            raise error
        elif self._config.on_error == "log":
            logger.error(str(error))
    
    def _should_sample(self, context: Optional[Dict[str, Any]] = None) -> bool:
        """Determine if this trace should be sampled."""
        if context and self._config.sampling_rules:
            for rule in self._config.sampling_rules:
                if rule.matches(context):
                    return random.random() < rule.rate
        
        return random.random() < self._config.sample_rate
    
    def trace(
        self,
        name: str,
        framework: Optional[str] = None,
    ) -> TraceSession:
        """Start a new trace session."""
        session = TraceSession(
            name=name,
            tracer=self,
            framework=framework,
        )
        self._sessions.append(session)
        return session
    
    def _on_session_end(self, session: TraceSession) -> None:
        """Handle session end - queue for export."""
        context = {
            "status": session._status,
            "duration_s": session.duration_ms / 1000,
            "tags": session._tags,
        }
        
        if self._should_sample(context):
            self._export_queue.put(session.to_data())
    
    def flush(self, timeout: float = 30.0) -> None:
        """Flush all pending exports."""
        deadline = time.time() + timeout
        while not self._export_queue.empty() and time.time() < deadline:
            time.sleep(0.1)
    
    def shutdown(self) -> None:
        """Shutdown the tracer and flush pending exports."""
        self._shutdown.set()
        
        if self._export_thread:
            self._export_thread.join(timeout=5.0)
        
        if self._http_client:
            self._http_client.close()
    
    def __enter__(self) -> "MAOTracer":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown()
