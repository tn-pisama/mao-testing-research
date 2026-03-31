"""Benchmark Module.

Benchmarking system for evaluating detection accuracy against:
- UC Berkeley MAST dataset (16 failure modes, F1-F16)
- Patronus AI TRAIL benchmark (21 failure categories, OTEL traces)
- Who&When benchmark (ICML 2025, multi-agent failure attribution)
"""

from app.benchmark.mast_loader import MASTRecord, MASTDataLoader
from app.benchmark.metrics import ConfusionMatrix, FailureModeMetrics, BenchmarkMetrics, MetricsComputer
from app.benchmark.runner import DetectionAttempt, BenchmarkResult, BenchmarkRunner
from app.benchmark.report import ReportFormat, ReportGenerator
from app.benchmark.trail_loader import TRAILTrace, TRAILSpan, TRAILAnnotation, TRAILDataLoader
from app.benchmark.trail_adapter import TRAILSpanAdapter
from app.benchmark.trail_runner import TRAILBenchmarkRunner, TRAILBenchmarkResult
from app.benchmark.trail_report import generate_report as generate_trail_report
from app.benchmark.whowhen_loader import WhoWhenCase, WhoWhenMessage, WhoWhenDataLoader
from app.benchmark.whowhen_adapter import WhoWhenAdapter
from app.benchmark.whowhen_runner import WhoWhenBenchmarkRunner, WhoWhenBenchmarkResult
from app.benchmark.whowhen_report import generate_report as generate_whowhen_report

__all__ = [
    # MAST - Data loading
    "MASTRecord",
    "MASTDataLoader",
    # MAST - Metrics
    "ConfusionMatrix",
    "FailureModeMetrics",
    "BenchmarkMetrics",
    "MetricsComputer",
    # MAST - Runner
    "DetectionAttempt",
    "BenchmarkResult",
    "BenchmarkRunner",
    # MAST - Report
    "ReportFormat",
    "ReportGenerator",
    # TRAIL
    "TRAILTrace",
    "TRAILSpan",
    "TRAILAnnotation",
    "TRAILDataLoader",
    "TRAILSpanAdapter",
    "TRAILBenchmarkRunner",
    "TRAILBenchmarkResult",
    "generate_trail_report",
    # Who&When
    "WhoWhenCase",
    "WhoWhenMessage",
    "WhoWhenDataLoader",
    "WhoWhenAdapter",
    "WhoWhenBenchmarkRunner",
    "WhoWhenBenchmarkResult",
    "generate_whowhen_report",
]
