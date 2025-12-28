"""Datadog integration for MAO Testing Platform."""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import os
import time
import json
import httpx
from enum import Enum


class MetricType(str, Enum):
    COUNT = "count"
    GAUGE = "gauge"
    RATE = "rate"
    DISTRIBUTION = "distribution"


@dataclass
class DatadogMetric:
    metric: str
    type: MetricType
    points: List[tuple]
    tags: List[str] = field(default_factory=list)
    host: Optional[str] = None
    interval: Optional[int] = None


@dataclass
class DatadogEvent:
    title: str
    text: str
    alert_type: str = "info"
    tags: List[str] = field(default_factory=list)
    host: Optional[str] = None


class DatadogExporter:
    def __init__(
        self,
        api_key: Optional[str] = None,
        app_key: Optional[str] = None,
        site: str = "datadoghq.com",
    ):
        self.api_key = api_key or os.getenv("DD_API_KEY", "")
        self.app_key = app_key or os.getenv("DD_APP_KEY", "")
        self.site = site
        self.base_url = f"https://api.{site}"
        self._buffer: List[DatadogMetric] = []
        self._events_buffer: List[DatadogEvent] = []
        self.prefix = "mao"
        self.default_tags = ["service:mao-testing", "env:" + os.getenv("ENVIRONMENT", "development")]
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
            "Content-Type": "application/json",
        }
    
    def gauge(
        self,
        metric: str,
        value: float,
        tags: Optional[List[str]] = None,
        timestamp: Optional[float] = None,
    ):
        ts = timestamp or time.time()
        all_tags = self.default_tags + (tags or [])
        
        self._buffer.append(DatadogMetric(
            metric=f"{self.prefix}.{metric}",
            type=MetricType.GAUGE,
            points=[(int(ts), value)],
            tags=all_tags,
        ))
    
    def count(
        self,
        metric: str,
        value: float = 1,
        tags: Optional[List[str]] = None,
        timestamp: Optional[float] = None,
    ):
        ts = timestamp or time.time()
        all_tags = self.default_tags + (tags or [])
        
        self._buffer.append(DatadogMetric(
            metric=f"{self.prefix}.{metric}",
            type=MetricType.COUNT,
            points=[(int(ts), value)],
            tags=all_tags,
            interval=10,
        ))
    
    def distribution(
        self,
        metric: str,
        value: float,
        tags: Optional[List[str]] = None,
        timestamp: Optional[float] = None,
    ):
        ts = timestamp or time.time()
        all_tags = self.default_tags + (tags or [])
        
        self._buffer.append(DatadogMetric(
            metric=f"{self.prefix}.{metric}",
            type=MetricType.DISTRIBUTION,
            points=[(int(ts), value)],
            tags=all_tags,
        ))
    
    def event(
        self,
        title: str,
        text: str,
        alert_type: str = "info",
        tags: Optional[List[str]] = None,
    ):
        all_tags = self.default_tags + (tags or [])
        
        self._events_buffer.append(DatadogEvent(
            title=title,
            text=text,
            alert_type=alert_type,
            tags=all_tags,
        ))
    
    def record_trace(self, tenant_id: str, framework: str, status: str, tokens: int, cost_usd: float):
        tags = [f"tenant:{tenant_id}", f"framework:{framework}", f"status:{status}"]
        
        self.count("traces.total", 1, tags)
        self.count("tokens.total", tokens, tags)
        self.gauge("cost.usd", cost_usd, tags)
    
    def record_detection(
        self,
        tenant_id: str,
        detection_type: str,
        severity: str,
        confidence: float,
    ):
        tags = [f"tenant:{tenant_id}", f"type:{detection_type}", f"severity:{severity}"]
        
        self.count("detections.total", 1, tags)
        self.gauge("detections.confidence", confidence, tags)
        
        if severity in ["high", "critical"]:
            self.event(
                title=f"MAO Detection: {detection_type}",
                text=f"Detected {detection_type} with {confidence:.0%} confidence",
                alert_type="warning" if severity == "high" else "error",
                tags=tags,
            )
    
    def record_latency(self, operation: str, latency_seconds: float, tags: Optional[List[str]] = None):
        all_tags = [f"operation:{operation}"] + (tags or [])
        self.distribution("latency.seconds", latency_seconds, all_tags)
    
    def record_eval(self, tenant_id: str, eval_type: str, score: float, passed: bool):
        tags = [f"tenant:{tenant_id}", f"eval_type:{eval_type}", f"passed:{passed}"]
        
        self.distribution("eval.score", score, tags)
        self.count("eval.total", 1, tags)
        if passed:
            self.count("eval.passed", 1, tags)
    
    async def flush(self) -> bool:
        if not self.api_key:
            self._buffer.clear()
            self._events_buffer.clear()
            return False
        
        success = True
        
        if self._buffer:
            metrics_success = await self._send_metrics()
            success = success and metrics_success
            self._buffer.clear()
        
        if self._events_buffer:
            events_success = await self._send_events()
            success = success and events_success
            self._events_buffer.clear()
        
        return success
    
    async def _send_metrics(self) -> bool:
        if not self._buffer:
            return True
        
        series = []
        for metric in self._buffer:
            series.append({
                "metric": metric.metric,
                "type": metric.type.value,
                "points": metric.points,
                "tags": metric.tags,
                "host": metric.host,
                "interval": metric.interval,
            })
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/series",
                    headers=self._get_headers(),
                    json={"series": series},
                    timeout=10.0,
                )
                return response.status_code == 202
            except Exception:
                return False
    
    async def _send_events(self) -> bool:
        if not self._events_buffer:
            return True
        
        async with httpx.AsyncClient() as client:
            for event in self._events_buffer:
                try:
                    await client.post(
                        f"{self.base_url}/api/v1/events",
                        headers=self._get_headers(),
                        json={
                            "title": event.title,
                            "text": event.text,
                            "alert_type": event.alert_type,
                            "tags": event.tags,
                            "host": event.host,
                        },
                        timeout=10.0,
                    )
                except Exception:
                    return False
        
        return True
    
    def flush_sync(self) -> bool:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return False
            return loop.run_until_complete(self.flush())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.flush())
            finally:
                loop.close()
    
    def get_dashboard_json(self) -> Dict[str, Any]:
        return {
            "title": "MAO Testing Platform",
            "description": "Multi-Agent Orchestration Testing Platform metrics",
            "widgets": [
                {
                    "definition": {
                        "type": "timeseries",
                        "title": "Traces Ingested",
                        "requests": [
                            {"q": f"sum:{self.prefix}.traces.total{{*}}.as_count()"}
                        ]
                    }
                },
                {
                    "definition": {
                        "type": "timeseries",
                        "title": "Detections by Type",
                        "requests": [
                            {"q": f"sum:{self.prefix}.detections.total{{*}} by {{type}}.as_count()"}
                        ]
                    }
                },
                {
                    "definition": {
                        "type": "timeseries",
                        "title": "Token Usage",
                        "requests": [
                            {"q": f"sum:{self.prefix}.tokens.total{{*}}.as_count()"}
                        ]
                    }
                },
                {
                    "definition": {
                        "type": "timeseries",
                        "title": "Cost (USD)",
                        "requests": [
                            {"q": f"sum:{self.prefix}.cost.usd{{*}}"}
                        ]
                    }
                },
                {
                    "definition": {
                        "type": "heatmap",
                        "title": "Latency Distribution",
                        "requests": [
                            {"q": f"avg:{self.prefix}.latency.seconds{{*}}"}
                        ]
                    }
                },
                {
                    "definition": {
                        "type": "query_value",
                        "title": "Detection Confidence (Avg)",
                        "requests": [
                            {"q": f"avg:{self.prefix}.detections.confidence{{*}}"}
                        ]
                    }
                },
            ],
            "layout_type": "ordered",
        }


datadog_exporter = DatadogExporter()
