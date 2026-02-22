"""Prometheus metrics exporter for MAO Testing Platform."""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import time


@dataclass
class MetricValue:
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Counter:
    def __init__(self, name: str, description: str, label_names: list = None):
        self.name = name
        self.description = description
        self.label_names = label_names or []
        self._values: Dict[tuple, float] = defaultdict(float)
    
    def inc(self, value: float = 1, **labels):
        key = tuple(sorted(labels.items()))
        self._values[key] += value
    
    def get_all(self) -> Dict[tuple, float]:
        return dict(self._values)


class Gauge:
    def __init__(self, name: str, description: str, label_names: list = None):
        self.name = name
        self.description = description
        self.label_names = label_names or []
        self._values: Dict[tuple, float] = {}
    
    def set(self, value: float, **labels):
        key = tuple(sorted(labels.items()))
        self._values[key] = value
    
    def inc(self, value: float = 1, **labels):
        key = tuple(sorted(labels.items()))
        self._values[key] = self._values.get(key, 0) + value
    
    def dec(self, value: float = 1, **labels):
        key = tuple(sorted(labels.items()))
        self._values[key] = self._values.get(key, 0) - value
    
    def get_all(self) -> Dict[tuple, float]:
        return dict(self._values)


class Histogram:
    def __init__(self, name: str, description: str, label_names: list = None, buckets: list = None):
        self.name = name
        self.description = description
        self.label_names = label_names or []
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        self._observations: Dict[tuple, list] = defaultdict(list)
    
    def observe(self, value: float, **labels):
        key = tuple(sorted(labels.items()))
        self._observations[key].append(value)
    
    def get_all(self) -> Dict[tuple, Dict[str, Any]]:
        result = {}
        for key, observations in self._observations.items():
            bucket_counts = {b: 0 for b in self.buckets}
            bucket_counts[float('inf')] = 0
            
            for obs in observations:
                for bucket in self.buckets + [float('inf')]:
                    if obs <= bucket:
                        bucket_counts[bucket] += 1
            
            result[key] = {
                "buckets": bucket_counts,
                "sum": sum(observations),
                "count": len(observations),
            }
        
        return result


class MAOMetrics:
    def __init__(self):
        self.traces_total = Counter(
            "mao_traces_total",
            "Total number of traces ingested",
            ["tenant_id", "framework", "status"],
        )
        
        self.detections_total = Counter(
            "mao_detections_total",
            "Total number of detections",
            ["tenant_id", "detection_type", "severity"],
        )
        
        self.tokens_total = Counter(
            "mao_tokens_total",
            "Total tokens processed",
            ["tenant_id", "model", "token_type"],
        )
        
        self.cost_total = Counter(
            "mao_cost_usd_total",
            "Total cost in USD",
            ["tenant_id", "model", "provider"],
        )
        
        self.active_traces = Gauge(
            "mao_active_traces",
            "Number of currently active traces",
            ["tenant_id"],
        )
        
        self.detection_confidence = Gauge(
            "mao_detection_confidence",
            "Confidence score of latest detection",
            ["tenant_id", "detection_type"],
        )
        
        self.ingestion_latency = Histogram(
            "mao_ingestion_latency_seconds",
            "Latency of trace ingestion",
            ["tenant_id", "framework"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
        )
        
        self.detection_latency = Histogram(
            "mao_detection_latency_seconds",
            "Latency of detection processing",
            ["detection_type"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
        )
        
        self.eval_scores = Histogram(
            "mao_eval_score",
            "Distribution of evaluation scores",
            ["tenant_id", "eval_type"],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        # --- Per-detector calibration metrics (harness engineering) ---
        self.detector_f1 = Gauge(
            "pisama_detector_f1",
            "Current calibrated F1 score per detector",
            ["detector_type"],
        )

        self.detector_threshold = Gauge(
            "pisama_detector_threshold",
            "Current optimal threshold per detector",
            ["detector_type"],
        )

        self.detector_ece = Gauge(
            "pisama_detector_ece",
            "Expected Calibration Error per detector",
            ["detector_type"],
        )
    
    def record_trace(self, tenant_id: str, framework: str, status: str):
        self.traces_total.inc(tenant_id=tenant_id, framework=framework, status=status)
    
    def record_detection(self, tenant_id: str, detection_type: str, severity: str, confidence: float):
        self.detections_total.inc(tenant_id=tenant_id, detection_type=detection_type, severity=severity)
        self.detection_confidence.set(confidence, tenant_id=tenant_id, detection_type=detection_type)
    
    def record_tokens(self, tenant_id: str, model: str, input_tokens: int, output_tokens: int):
        self.tokens_total.inc(input_tokens, tenant_id=tenant_id, model=model, token_type="input")
        self.tokens_total.inc(output_tokens, tenant_id=tenant_id, model=model, token_type="output")
    
    def record_cost(self, tenant_id: str, model: str, provider: str, cost_usd: float):
        self.cost_total.inc(cost_usd, tenant_id=tenant_id, model=model, provider=provider)
    
    def record_ingestion_latency(self, tenant_id: str, framework: str, latency_seconds: float):
        self.ingestion_latency.observe(latency_seconds, tenant_id=tenant_id, framework=framework)
    
    def record_detection_latency(self, detection_type: str, latency_seconds: float):
        self.detection_latency.observe(latency_seconds, detection_type=detection_type)
    
    def record_eval(self, tenant_id: str, eval_type: str, score: float):
        self.eval_scores.observe(score, tenant_id=tenant_id, eval_type=eval_type)

    def update_calibration_metrics(self, report: dict) -> None:
        """Update per-detector gauges from a calibration report."""
        for dtype, metrics in report.get("results", {}).items():
            self.detector_f1.set(metrics.get("f1", 0.0), detector_type=dtype)
            self.detector_threshold.set(metrics.get("optimal_threshold", 0.5), detector_type=dtype)
            if "ece" in metrics:
                self.detector_ece.set(metrics["ece"], detector_type=dtype)


class PrometheusExporter:
    def __init__(self, metrics: MAOMetrics):
        self.metrics = metrics
    
    def export(self) -> str:
        lines = []
        
        lines.extend(self._export_counter(self.metrics.traces_total))
        lines.extend(self._export_counter(self.metrics.detections_total))
        lines.extend(self._export_counter(self.metrics.tokens_total))
        lines.extend(self._export_counter(self.metrics.cost_total))
        lines.extend(self._export_gauge(self.metrics.active_traces))
        lines.extend(self._export_gauge(self.metrics.detection_confidence))
        lines.extend(self._export_histogram(self.metrics.ingestion_latency))
        lines.extend(self._export_histogram(self.metrics.detection_latency))
        lines.extend(self._export_histogram(self.metrics.eval_scores))
        lines.extend(self._export_gauge(self.metrics.detector_f1))
        lines.extend(self._export_gauge(self.metrics.detector_threshold))
        lines.extend(self._export_gauge(self.metrics.detector_ece))

        return "\n".join(lines)
    
    def _format_labels(self, label_tuple: tuple) -> str:
        if not label_tuple:
            return ""
        labels = ",".join(f'{k}="{v}"' for k, v in label_tuple)
        return "{" + labels + "}"
    
    def _export_counter(self, counter: Counter) -> list:
        lines = [
            f"# HELP {counter.name} {counter.description}",
            f"# TYPE {counter.name} counter",
        ]
        
        for labels, value in counter.get_all().items():
            label_str = self._format_labels(labels)
            lines.append(f"{counter.name}{label_str} {value}")
        
        return lines
    
    def _export_gauge(self, gauge: Gauge) -> list:
        lines = [
            f"# HELP {gauge.name} {gauge.description}",
            f"# TYPE {gauge.name} gauge",
        ]
        
        for labels, value in gauge.get_all().items():
            label_str = self._format_labels(labels)
            lines.append(f"{gauge.name}{label_str} {value}")
        
        return lines
    
    def _export_histogram(self, histogram: Histogram) -> list:
        lines = [
            f"# HELP {histogram.name} {histogram.description}",
            f"# TYPE {histogram.name} histogram",
        ]
        
        for labels, data in histogram.get_all().items():
            base_labels = self._format_labels(labels)
            
            cumulative = 0
            for bucket, count in sorted(data["buckets"].items()):
                cumulative += count
                if bucket == float('inf'):
                    bucket_label = '+Inf'
                else:
                    bucket_label = str(bucket)
                
                if labels:
                    label_str = base_labels[:-1] + f',le="{bucket_label}"' + "}"
                else:
                    label_str = '{le="' + bucket_label + '"}'
                
                lines.append(f"{histogram.name}_bucket{label_str} {cumulative}")
            
            lines.append(f"{histogram.name}_sum{base_labels} {data['sum']}")
            lines.append(f"{histogram.name}_count{base_labels} {data['count']}")
        
        return lines


mao_metrics = MAOMetrics()
prometheus_exporter = PrometheusExporter(mao_metrics)
