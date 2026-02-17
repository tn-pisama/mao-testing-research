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

    @classmethod
    def detect_framework(cls, content: str) -> str:
        """Detect the agent framework from trace content.

        Args:
            content: Raw content to analyze

        Returns:
            Detected framework name (langgraph, autogen, crewai, langchain, etc.)
        """
        try:
            content_lower = content.lower()

            # Parse first few lines for inspection
            sample_items = []
            for line in content.strip().split('\n')[:10]:
                line = line.strip()
                if line.startswith('{'):
                    try:
                        sample_items.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            # Check for explicit framework markers in data
            for item in sample_items:
                if not isinstance(item, dict):
                    continue

                # Check mas_name field (MAST format)
                mas_name = str(item.get("mas_name", "")).lower()
                if mas_name:
                    return cls._normalize_framework_name(mas_name)

                # Check framework field
                framework = str(item.get("framework", "")).lower()
                if framework:
                    return cls._normalize_framework_name(framework)

                # Check metadata for framework hints
                metadata = item.get("metadata", {}) or {}
                if isinstance(metadata, dict):
                    fw = str(metadata.get("framework", "") or metadata.get("agent_framework", "")).lower()
                    if fw:
                        return cls._normalize_framework_name(fw)

                # Check run_type patterns (LangSmith traces)
                run_type = str(item.get("run_type", "")).lower()
                if run_type in ["agent", "chain"]:
                    if "langgraph" in content_lower:
                        return "langgraph"
                    return "langchain"

            # String-based heuristics
            framework_markers = {
                "langgraph": ["langgraph", "stategraph", "compiledgraph", "add_node", "add_edge"],
                "autogen": ["autogen", "conversableagent", "assistantagent", "useragent", "groupchat"],
                "crewai": ["crewai", "crew", "task.output", "agent.role", "kickoff"],
                "langchain": ["langchain", "lcel", "runnablesequence", "agentexecutor"],
                "openai": ["openai", "gpt-4", "gpt-3.5", "assistants", "function_call"],
                "anthropic": ["anthropic", "claude", "human_turn_idx"],
                "n8n": ["n8n", "workflowid", "executionid", "nodetype"],
                "openclaw": ["openclaw", "openclaw.request", "openclaw.agent", "sessions_spawn", "sessions_send"],
            }

            for framework, markers in framework_markers.items():
                if any(marker in content_lower for marker in markers):
                    return framework

            return "unknown"
        except Exception:
            return "unknown"

    @classmethod
    def _normalize_framework_name(cls, name: str) -> str:
        """Normalize framework name to standard form."""
        name = name.lower().strip()

        framework_aliases = {
            "langgraph": ["langgraph", "lang_graph", "lang-graph"],
            "langchain": ["langchain", "lang_chain", "lang-chain", "lcel"],
            "autogen": ["autogen", "auto_gen", "auto-gen", "ag2", "magentic-one", "magentic"],
            "crewai": ["crewai", "crew_ai", "crew-ai", "crew"],
            "openai": ["openai", "open_ai", "open-ai", "gpt", "chatgpt"],
            "anthropic": ["anthropic", "claude"],
            "n8n": ["n8n"],
            "openclaw": ["openclaw", "open_claw", "open-claw", "clawdbot", "moltbot"],
            "chatdev": ["chatdev", "chat_dev"],
            "metagpt": ["metagpt", "meta_gpt", "meta-gpt"],
        }

        for canonical, aliases in framework_aliases.items():
            if any(alias in name for alias in aliases):
                return canonical

        return name if name else "unknown"
    
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
