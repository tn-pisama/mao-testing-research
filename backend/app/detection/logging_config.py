"""Structured logging for PISAMA detectors.

Provides a thin LoggerAdapter that adds detection context (detector name,
trace_id, confidence) to all log messages. Existing detectors can opt in
with one line: `logger = get_detector_logger("loop")`
"""

import logging
import json
from typing import Any, Dict, Optional


class DetectorLogAdapter(logging.LoggerAdapter):
    """Adds detection context to all log messages as structured extra fields."""

    def process(self, msg: str, kwargs: Any) -> tuple:
        extra = kwargs.get("extra", {})
        extra.update({
            "detector": self.extra.get("detector", "unknown"),
            "trace_id": self.extra.get("trace_id", ""),
        })
        kwargs["extra"] = extra
        return msg, kwargs


class StructuredFormatter(logging.Formatter):
    """JSON-line formatter for structured log output.

    When used, outputs each log record as a single JSON line with
    standard fields plus any extra context from DetectorLogAdapter.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Add detector context if present
        for key in ("detector", "trace_id", "confidence", "detection_type"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def get_detector_logger(
    detector_name: str,
    trace_id: str = "",
) -> DetectorLogAdapter:
    """Get a structured logger for a specific detector.

    Usage:
        logger = get_detector_logger("loop")
        logger.info("Loop detected", extra={"confidence": 0.85})
    """
    base_logger = logging.getLogger(f"app.detection.{detector_name}")
    return DetectorLogAdapter(base_logger, {"detector": detector_name, "trace_id": trace_id})


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Configure the root detection logger with structured JSON output.

    Call once at application startup to enable structured logging for
    all detectors.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())

    detection_logger = logging.getLogger("app.detection")
    detection_logger.addHandler(handler)
    detection_logger.setLevel(level)
    detection_logger.propagate = False
