"""MAST Benchmark Module.

Comprehensive benchmarking system for evaluating detection accuracy
against the UC Berkeley MAST dataset (16 failure modes, F1-F16).
"""

from app.benchmark.mast_loader import MASTRecord, MASTDataLoader
from app.benchmark.metrics import ConfusionMatrix, FailureModeMetrics, BenchmarkMetrics, MetricsComputer
from app.benchmark.runner import DetectionAttempt, BenchmarkResult, BenchmarkRunner
from app.benchmark.report import ReportFormat, ReportGenerator

__all__ = [
    # Data loading
    "MASTRecord",
    "MASTDataLoader",
    # Metrics
    "ConfusionMatrix",
    "FailureModeMetrics",
    "BenchmarkMetrics",
    "MetricsComputer",
    # Runner
    "DetectionAttempt",
    "BenchmarkResult",
    "BenchmarkRunner",
    # Report
    "ReportFormat",
    "ReportGenerator",
]
