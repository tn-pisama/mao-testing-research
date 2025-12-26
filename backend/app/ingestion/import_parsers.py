"""Parsers for historical data import formats."""

import json
import hashlib
from typing import Iterator, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from abc import ABC, abstractmethod


@dataclass
class ParsedRecord:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    agent_id: str
    name: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    start_time: datetime
    end_time: datetime
    token_count: int
    metadata: Dict[str, Any]


class ImportParser(ABC):
    MAX_JSON_DEPTH = 50
    MAX_RECORD_SIZE = 10 * 1024 * 1024
    
    @abstractmethod
    def parse(self, content: str) -> Iterator[ParsedRecord]:
        pass
    
    @classmethod
    def detect_format(cls, content: str) -> Optional[str]:
        try:
            first_line = content.split('\n')[0].strip()
            if not first_line:
                return None
            
            sample = json.loads(first_line)
            
            if "run_type" in sample and "inputs" in sample:
                return "langsmith"
            if "traces" in sample or "observations" in sample:
                return "langfuse"
            if "resourceSpans" in sample or "traceId" in sample:
                return "otlp"
            if "agent_id" in sample or "agent" in sample:
                return "generic"
            
            return "generic"
        except json.JSONDecodeError:
            return None
    
    def _parse_timestamp(self, ts: Any) -> datetime:
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, (int, float)):
            if ts > 1e12:
                ts = ts / 1000
            return datetime.fromtimestamp(ts)
        if isinstance(ts, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
            ]:
                try:
                    return datetime.strptime(ts.replace("+00:00", "Z"), fmt)
                except ValueError:
                    continue
        return datetime.utcnow()
    
    def _check_depth(self, obj: Any, depth: int = 0) -> bool:
        if depth > self.MAX_JSON_DEPTH:
            return False
        if isinstance(obj, dict):
            return all(self._check_depth(v, depth + 1) for v in obj.values())
        if isinstance(obj, list):
            return all(self._check_depth(v, depth + 1) for v in obj)
        return True


class LangSmithParser(ImportParser):
    def parse(self, content: str) -> Iterator[ParsedRecord]:
        for line_num, line in enumerate(content.strip().split('\n')):
            if not line.strip():
                continue
            
            try:
                record = json.loads(line)
                
                if not self._check_depth(record):
                    raise ValueError("JSON depth exceeds limit")
                
                yield ParsedRecord(
                    trace_id=record.get("session_id") or record.get("id", ""),
                    span_id=record.get("id", ""),
                    parent_span_id=record.get("parent_run_id"),
                    agent_id=record.get("name", "unknown"),
                    name=record.get("name", "unknown"),
                    inputs=record.get("inputs", {}),
                    outputs=record.get("outputs", {}),
                    start_time=self._parse_timestamp(record.get("start_time")),
                    end_time=self._parse_timestamp(record.get("end_time")),
                    token_count=self._extract_tokens(record),
                    metadata={
                        "run_type": record.get("run_type"),
                        "extra": record.get("extra", {}),
                    },
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"Line {line_num + 1}: Invalid JSON - {e}")
    
    def _extract_tokens(self, record: dict) -> int:
        extra = record.get("extra", {})
        if "tokens" in extra:
            return extra["tokens"]
        if "usage" in extra:
            usage = extra["usage"]
            return usage.get("total_tokens", 0)
        return 0


class LangfuseParser(ImportParser):
    def parse(self, content: str) -> Iterator[ParsedRecord]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        
        if not self._check_depth(data):
            raise ValueError("JSON depth exceeds limit")
        
        traces = data.get("traces", [data] if "observations" in data else [])
        
        for trace in traces:
            trace_id = trace.get("id", "")
            
            for obs in trace.get("observations", []):
                yield ParsedRecord(
                    trace_id=trace_id,
                    span_id=obs.get("id", ""),
                    parent_span_id=obs.get("parentObservationId"),
                    agent_id=obs.get("name", "unknown"),
                    name=obs.get("name", "unknown"),
                    inputs=obs.get("input", {}),
                    outputs=obs.get("output", {}),
                    start_time=self._parse_timestamp(obs.get("startTime")),
                    end_time=self._parse_timestamp(obs.get("endTime")),
                    token_count=self._extract_tokens(obs),
                    metadata={
                        "type": obs.get("type"),
                        "model": obs.get("model"),
                        "level": obs.get("level"),
                    },
                )
    
    def _extract_tokens(self, obs: dict) -> int:
        usage = obs.get("usage", {})
        return usage.get("totalTokens", 0) or usage.get("total", 0)


class GenericParser(ImportParser):
    def parse(self, content: str) -> Iterator[ParsedRecord]:
        for line_num, line in enumerate(content.strip().split('\n')):
            if not line.strip():
                continue
            
            try:
                record = json.loads(line)
                
                if not self._check_depth(record):
                    raise ValueError("JSON depth exceeds limit")
                
                yield ParsedRecord(
                    trace_id=record.get("trace_id") or record.get("session_id") or str(line_num),
                    span_id=record.get("span_id") or record.get("id") or str(line_num),
                    parent_span_id=record.get("parent_span_id") or record.get("parent_id"),
                    agent_id=record.get("agent_id") or record.get("agent") or record.get("name") or "unknown",
                    name=record.get("name") or record.get("event") or "step",
                    inputs=record.get("inputs") or record.get("input") or {},
                    outputs=record.get("outputs") or record.get("output") or {},
                    start_time=self._parse_timestamp(record.get("start_time") or record.get("timestamp")),
                    end_time=self._parse_timestamp(record.get("end_time") or record.get("timestamp")),
                    token_count=record.get("tokens") or record.get("token_count") or 0,
                    metadata=record.get("metadata") or {},
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"Line {line_num + 1}: Invalid JSON - {e}")


def get_parser(format_type: str) -> ImportParser:
    parsers = {
        "langsmith": LangSmithParser(),
        "langfuse": LangfuseParser(),
        "generic": GenericParser(),
    }
    return parsers.get(format_type, GenericParser())


def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def count_records(content: str, format_type: str) -> int:
    if format_type == "langfuse":
        try:
            data = json.loads(content)
            traces = data.get("traces", [data] if "observations" in data else [])
            return sum(len(t.get("observations", [])) for t in traces)
        except:
            return 0
    else:
        return len([l for l in content.strip().split('\n') if l.strip()])
