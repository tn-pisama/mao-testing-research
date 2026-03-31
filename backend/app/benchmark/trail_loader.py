"""TRAIL Dataset Loader for benchmarking.

Downloads and parses the Patronus AI TRAIL benchmark from HuggingFace.
TRAIL provides OTEL-format agent traces with annotated failure categories.

See: https://huggingface.co/datasets/PatronusAI/TRAIL
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category mapping: TRAIL failure categories -> Pisama detector types
# ---------------------------------------------------------------------------

TRAIL_TO_PISAMA: Dict[str, str] = {
    "Language-only hallucinations": "hallucination",
    "Tool-related hallucinations": "hallucination",
    "Poor Information Retrieval": "retrieval_quality",
    "Tool Output Misinterpretation": "grounding",
    "Incorrect Problem Identification": "specification",
    "Context Handling Failures": "context",
    "Incorrect Memory Usage": "context",
    "Resource Abuse": "loop",
    "Goal Deviation": "derailment",
    "Instruction Non-compliance": "derailment",
    "Task Orchestration": "coordination",
    "Formatting Errors": "completion",
    "Tool Selection Errors": "workflow",
    "Resource Exhaustion": "overflow",
}

# Categories that are system-level, not agent reasoning — unmapped
TRAIL_UNMAPPED_CATEGORIES = {
    "Rate Limiting",
    "Authentication Errors",
    "Service Errors",
    "Resource Not Found",
    "Timeout Issues",
    "Tool Definition Issues",
    "Environment Setup Errors",
}

# All 21 TRAIL categories
TRAIL_ALL_CATEGORIES = list(TRAIL_TO_PISAMA.keys()) + list(TRAIL_UNMAPPED_CATEGORIES)

# Pisama detector types that have TRAIL mappings
TRAIL_COVERED_PISAMA_TYPES = sorted(set(TRAIL_TO_PISAMA.values()))


def _normalize_category(raw_cat: str) -> str:
    """Normalize TRAIL category strings to canonical form.

    The TRAIL dataset has inconsistencies: typos, case variations,
    singular/plural, trailing spaces, missing suffixes.
    """
    import re as _re
    c = raw_cat.strip()
    # Canonical lowered form for matching
    low = c.lower()
    # Map known variants to canonical names
    _VARIANTS = {
        "language-only": "Language-only hallucinations",
        "tool-related": "Tool-related hallucinations",
        "poor information retrieval": "Poor Information Retrieval",
        "poor information retrieval": "Poor Information Retrieval",
        "tool output misinterpretation": "Tool Output Misinterpretation",
        "incorrect problem identification": "Incorrect Problem Identification",
        "context handling failure": "Context Handling Failures",
        "context handling failures": "Context Handling Failures",
        "incorrect memory usage": "Incorrect Memory Usage",
        "resource abuse": "Resource Abuse",
        "goal deviation": "Goal Deviation",
        "instruction non-compliance": "Instruction Non-compliance",
        "instruction non complience": "Instruction Non-compliance",
        "instruction non-complience": "Instruction Non-compliance",
        "task orchestration": "Task Orchestration",
        "task orchestration error": "Task Orchestration",
        "task orchestration errors": "Task Orchestration",
        "formatting error": "Formatting Errors",
        "formatting errors": "Formatting Errors",
        "tool selection": "Tool Selection Errors",
        "tool selection errors": "Tool Selection Errors",
        "resource exhaustion": "Resource Exhaustion",
        "resource not found": "Resource Not Found",
        "authentication errors": "Authentication Errors",
        "service errors": "Service Errors",
        "timeout issues": "Timeout Issues",
        "tool definition issues": "Tool Definition Issues",
        "environment setup errors": "Environment Setup Errors",
        "rate limiting": "Rate Limiting",
        "language-only hallucinations": "Language-only hallucinations",
        "tool-related hallucinations": "Tool-related hallucinations",
    }
    canonical = _VARIANTS.get(low)
    if canonical:
        return canonical
    # Fallback: return stripped original
    return c


def _json_loads_lenient(s: str) -> Any:
    """Parse JSON with tolerance for trailing commas."""
    import re as _re
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        cleaned = _re.sub(r",\s*([}\]])", r"\1", s)
        return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TRAILSpan:
    """Single OTEL span from a TRAIL trace."""

    span_id: str
    parent_span_id: Optional[str]
    span_name: str
    span_kind: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    child_spans: List["TRAILSpan"] = field(default_factory=list)

    @property
    def input_value(self) -> str:
        """Extract input.value from attributes."""
        return str(self.attributes.get("input.value", ""))

    @property
    def output_value(self) -> str:
        """Extract output.value from attributes."""
        return str(self.attributes.get("output.value", ""))

    @property
    def tool_name(self) -> Optional[str]:
        """Extract tool.name from attributes if present."""
        return self.attributes.get("tool.name")


@dataclass
class TRAILAnnotation:
    """Ground truth annotation for a specific span in a trace."""

    category: str
    location: str  # span_id
    evidence: str
    description: str
    impact: str  # HIGH / MEDIUM / LOW
    pisama_type: Optional[str] = None  # Mapped Pisama detector name

    def __post_init__(self):
        if self.pisama_type is None:
            self.pisama_type = TRAIL_TO_PISAMA.get(self.category)


@dataclass
class TRAILTrace:
    """Complete TRAIL trace with spans and annotations."""

    trace_id: str
    spans: List[TRAILSpan] = field(default_factory=list)
    annotations: List[TRAILAnnotation] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    source: str = "unknown"  # "gaia" or "swe-bench"

    @property
    def has_failures(self) -> bool:
        return len(self.annotations) > 0

    @property
    def mapped_annotations(self) -> List[TRAILAnnotation]:
        """Annotations that have a Pisama detector mapping."""
        return [a for a in self.annotations if a.pisama_type is not None]

    @property
    def annotation_categories(self) -> List[str]:
        return [a.category for a in self.annotations]

    def find_span(self, span_id: str) -> Optional[TRAILSpan]:
        """Find a span by ID, searching the full tree."""
        return self._find_span_recursive(self.spans, span_id)

    def _find_span_recursive(
        self, spans: List[TRAILSpan], span_id: str
    ) -> Optional[TRAILSpan]:
        for span in spans:
            if span.span_id == span_id:
                return span
            found = self._find_span_recursive(span.child_spans, span_id)
            if found:
                return found
        return None

    def get_parent_span(self, span: TRAILSpan) -> Optional[TRAILSpan]:
        """Get the parent span of a given span."""
        if span.parent_span_id is None:
            return None
        return self.find_span(span.parent_span_id)

    def get_sibling_spans(self, span: TRAILSpan) -> List[TRAILSpan]:
        """Get sibling spans (same parent)."""
        if span.parent_span_id is None:
            return [s for s in self.spans if s.span_id != span.span_id]
        parent = self.find_span(span.parent_span_id)
        if parent is None:
            return []
        return [s for s in parent.child_spans if s.span_id != span.span_id]

    def flatten_spans(self) -> List[TRAILSpan]:
        """Flatten the span tree to a list."""
        result: List[TRAILSpan] = []
        self._flatten_recursive(self.spans, result)
        return result

    def _flatten_recursive(
        self, spans: List[TRAILSpan], result: List[TRAILSpan]
    ) -> None:
        for span in spans:
            result.append(span)
            self._flatten_recursive(span.child_spans, result)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class TRAILDataLoader:
    """Download and load the TRAIL benchmark dataset from HuggingFace."""

    CACHE_DIR = Path("data/trail")
    HF_DATASET = "PatronusAI/TRAIL"

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else self.CACHE_DIR
        self._traces: List[TRAILTrace] = []
        self._loaded = False

    def download(self, token: Optional[str] = None) -> Path:
        """Download the TRAIL dataset from HuggingFace.

        Tries the ``datasets`` library first, then falls back to
        direct HTTP fetch from the HuggingFace API.

        Args:
            token: HuggingFace token for gated datasets. Falls back to
                   HF_TOKEN environment variable.

        Returns:
            Path to the downloaded data directory.
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        hf_token = token or os.getenv("HF_TOKEN")

        try:
            return self._download_via_datasets(hf_token)
        except Exception as exc:
            logger.warning(
                "datasets library unavailable or failed (%s), "
                "falling back to HTTP fetch",
                exc,
            )
            return self._download_via_http(hf_token)

    def _download_via_datasets(self, token: Optional[str]) -> Path:
        """Download using the huggingface ``datasets`` library."""
        from datasets import load_dataset  # type: ignore[import-untyped]

        logger.info("Downloading TRAIL dataset via datasets library...")
        kwargs: Dict[str, Any] = {}
        if token:
            kwargs["token"] = token

        ds = load_dataset(self.HF_DATASET, **kwargs)

        # Save each split as JSONL
        for split_name in ds:
            split = ds[split_name]
            out_path = self.cache_dir / f"{split_name}.jsonl"
            with open(out_path, "w") as f:
                for row in split:
                    f.write(json.dumps(row, default=str) + "\n")
            logger.info("Saved %d records to %s", len(split), out_path)

        return self.cache_dir

    def _download_via_http(self, token: Optional[str]) -> Path:
        """Download using direct HTTP requests to the HuggingFace API."""
        import urllib.request

        logger.info("Downloading TRAIL dataset via HTTP...")

        base_url = (
            f"https://huggingface.co/api/datasets/{self.HF_DATASET}"
        )
        headers: Dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # First, get dataset info to find available splits/files
        info_url = base_url
        req = urllib.request.Request(info_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                info = json.loads(resp.read())
        except Exception as exc:
            raise RuntimeError(
                f"Failed to fetch TRAIL dataset info from {info_url}. "
                f"The dataset may be gated — set HF_TOKEN env var. Error: {exc}"
            ) from exc

        # Try parquet download first (most HF datasets provide this)
        parquet_url = (
            f"https://huggingface.co/api/datasets/{self.HF_DATASET}/parquet"
        )
        req = urllib.request.Request(parquet_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                parquet_info = json.loads(resp.read())

            for split_name, files in parquet_info.items():
                for file_url in files:
                    filename = file_url.split("/")[-1]
                    out_path = self.cache_dir / filename
                    if out_path.exists():
                        logger.info("Already downloaded: %s", out_path)
                        continue
                    dl_req = urllib.request.Request(file_url, headers=headers)
                    with urllib.request.urlopen(dl_req, timeout=300) as dl_resp:
                        with open(out_path, "wb") as f:
                            while True:
                                chunk = dl_resp.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                    logger.info("Downloaded: %s", out_path)

            return self.cache_dir

        except Exception as exc:
            logger.warning("Parquet download failed (%s), trying rows API", exc)

        # Fallback: use the rows API
        for split in ["train", "test", "validation"]:
            rows_url = (
                f"https://datasets-server.huggingface.co/rows?"
                f"dataset={self.HF_DATASET}&config=default&split={split}&offset=0&length=100"
            )
            req = urllib.request.Request(rows_url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())

                rows = data.get("rows", [])
                if not rows:
                    continue

                out_path = self.cache_dir / f"{split}.jsonl"
                total_fetched = 0
                with open(out_path, "w") as f:
                    for row_wrapper in rows:
                        row = row_wrapper.get("row", row_wrapper)
                        f.write(json.dumps(row, default=str) + "\n")
                        total_fetched += 1

                # Fetch remaining rows in pages
                num_rows = data.get("num_rows_total", 0)
                offset = len(rows)
                while offset < num_rows:
                    page_url = (
                        f"https://datasets-server.huggingface.co/rows?"
                        f"dataset={self.HF_DATASET}&config=default"
                        f"&split={split}&offset={offset}&length=100"
                    )
                    req = urllib.request.Request(page_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        page_data = json.loads(resp.read())
                    page_rows = page_data.get("rows", [])
                    if not page_rows:
                        break
                    with open(out_path, "a") as f:
                        for row_wrapper in page_rows:
                            row = row_wrapper.get("row", row_wrapper)
                            f.write(json.dumps(row, default=str) + "\n")
                            total_fetched += 1
                    offset += len(page_rows)

                logger.info("Fetched %d rows for split '%s'", total_fetched, split)

            except Exception as exc:
                logger.debug("Split '%s' not available: %s", split, exc)

        return self.cache_dir

    def load(self, data_path: Optional[Path] = None) -> int:
        """Load traces from downloaded TRAIL data files.

        Args:
            data_path: Override path (file or directory).

        Returns:
            Number of traces loaded.
        """
        path = Path(data_path) if data_path else self.cache_dir
        if not path.exists():
            raise FileNotFoundError(
                f"TRAIL data not found at {path}. Run download() first."
            )

        self._traces = []

        if path.is_file():
            self._load_file(path)
        else:
            # Load all JSONL and JSON files in the directory
            for ext in ("*.jsonl", "*.json"):
                for file_path in sorted(path.glob(ext)):
                    self._load_file(file_path)

            # Also try parquet files
            for pq_path in sorted(path.glob("*.parquet")):
                self._load_parquet(pq_path)

        self._loaded = True
        logger.info("Loaded %d traces from %s", len(self._traces), path)
        return len(self._traces)

    def _load_file(self, path: Path) -> None:
        """Load traces from a JSONL or JSON file."""
        if path.suffix.lower() == ".jsonl":
            self._load_jsonl(path)
        elif path.suffix.lower() == ".json":
            self._load_json(path)

    def _load_jsonl(self, path: Path) -> None:
        """Load traces from a JSONL file, one line at a time."""
        # Infer source from filename (gaia.jsonl -> gaia, swe_bench.jsonl -> swe-bench)
        source = path.stem.lower().replace("_", "-")
        with open(path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    raw.setdefault("source", source)
                    trace = self._parse_trace(raw)
                    if trace:
                        self._traces.append(trace)
                except json.JSONDecodeError as e:
                    logger.warning("Line %d in %s: Invalid JSON - %s", line_num, path, e)
                except Exception as e:
                    logger.warning("Line %d in %s: Parse error - %s", line_num, path, e)

    def _load_json(self, path: Path) -> None:
        """Load traces from a JSON file (array or single object)."""
        with open(path) as f:
            data = json.load(f)

        items = data if isinstance(data, list) else [data]
        for i, raw in enumerate(items):
            try:
                trace = self._parse_trace(raw)
                if trace:
                    self._traces.append(trace)
            except Exception as e:
                logger.warning("Record %d in %s: Parse error - %s", i, path, e)

    def _load_parquet(self, path: Path) -> None:
        """Load traces from a Parquet file."""
        try:
            import pyarrow.parquet as pq  # type: ignore[import-untyped]
        except ImportError:
            try:
                import pandas as pd  # type: ignore[import-untyped]
                df = pd.read_parquet(path)
                for _, row in df.iterrows():
                    raw = row.to_dict()
                    trace = self._parse_trace(raw)
                    if trace:
                        self._traces.append(trace)
                return
            except ImportError:
                logger.warning(
                    "Skipping %s: neither pyarrow nor pandas installed", path
                )
                return

        table = pq.read_table(path)
        for batch in table.to_batches():
            for row_dict in batch.to_pydict().items():
                # to_pydict returns {col: [values]} — need to transpose
                pass

        # Simpler approach: convert to pandas
        df = table.to_pandas()
        for _, row in df.iterrows():
            raw = row.to_dict()
            trace = self._parse_trace(raw)
            if trace:
                self._traces.append(trace)

    def _parse_trace(self, raw: Dict[str, Any]) -> Optional[TRAILTrace]:
        """Parse a raw JSON record into a TRAILTrace.

        Handles the actual TRAIL HuggingFace format:
        - {trace: JSON_STRING, labels: JSON_STRING}
        where trace contains {trace_id, spans} and labels contains
        {trace_id, errors, scores}.
        Also handles pre-parsed dict formats.
        """
        # --- Handle the actual HF format: {trace: str, labels: str} ---
        raw_trace_field = raw.get("trace")
        raw_labels_field = raw.get("labels")

        trace_data: Dict[str, Any] = {}
        labels_data: Dict[str, Any] = {}

        if isinstance(raw_trace_field, str):
            try:
                trace_data = _json_loads_lenient(raw_trace_field)
            except (json.JSONDecodeError, ValueError):
                trace_data = {}
        elif isinstance(raw_trace_field, dict):
            trace_data = raw_trace_field

        if isinstance(raw_labels_field, str):
            try:
                labels_data = _json_loads_lenient(raw_labels_field)
            except (json.JSONDecodeError, ValueError):
                labels_data = {}
        elif isinstance(raw_labels_field, dict):
            labels_data = raw_labels_field

        # Extract trace_id
        trace_id = str(
            trace_data.get("trace_id")
            or labels_data.get("trace_id")
            or raw.get("trace_id")
            or raw.get("id")
            or raw.get("instance_id")
            or ""
        )
        if not trace_id:
            return None

        # Determine source (gaia vs swe-bench) from file context
        source = str(raw.get("source", raw.get("benchmark", "unknown"))).lower()

        # Parse scores from labels
        scores: Dict[str, float] = {}
        raw_scores = labels_data.get("scores", raw.get("scores"))
        if isinstance(raw_scores, list) and raw_scores:
            # TRAIL format: scores is a list with one dict
            scores = {
                k: float(v)
                for k, v in raw_scores[0].items()
                if isinstance(v, (int, float))
            }
        elif isinstance(raw_scores, dict):
            scores = {k: float(v) for k, v in raw_scores.items() if v is not None}

        # Parse spans from trace_data or raw
        raw_spans = trace_data.get("spans", [])
        if not raw_spans:
            raw_spans = raw.get("spans", [])
        if not raw_spans:
            raw_spans = raw.get("otel_spans", [])
        if isinstance(raw_spans, str):
            try:
                raw_spans = _json_loads_lenient(raw_spans)
            except (json.JSONDecodeError, ValueError):
                raw_spans = []
        if not isinstance(raw_spans, list):
            raw_spans = []

        spans = self._build_span_tree(raw_spans)

        # Parse annotations from labels.errors or raw.annotations
        raw_annotations = labels_data.get("errors", [])
        if not raw_annotations:
            raw_annotations = raw.get("annotations", raw.get("failure_annotations", []))
        if isinstance(raw_annotations, str):
            try:
                raw_annotations = _json_loads_lenient(raw_annotations)
            except (json.JSONDecodeError, ValueError):
                raw_annotations = []
        if not isinstance(raw_annotations, list):
            raw_annotations = []

        annotations = []
        for ann in raw_annotations:
            if not isinstance(ann, dict):
                continue
            raw_cat = str(ann.get("category", ann.get("failure_type", "")))
            normalized_cat = _normalize_category(raw_cat)
            annotation = TRAILAnnotation(
                category=normalized_cat,
                location=str(ann.get("location", ann.get("span_id", ""))),
                evidence=str(ann.get("evidence", "")),
                description=str(ann.get("description", "")),
                impact=str(ann.get("impact", ann.get("severity", "MEDIUM"))).upper(),
            )
            annotations.append(annotation)

        return TRAILTrace(
            trace_id=trace_id,
            spans=spans,
            annotations=annotations,
            scores=scores,
            source=source,
        )

    def _build_span_tree(self, raw_spans: List[Dict[str, Any]]) -> List[TRAILSpan]:
        """Build a tree of spans from a flat or nested list.

        Handles both flat lists with parent_span_id references and
        pre-nested structures with child_spans arrays.
        """
        if not raw_spans:
            return []

        # Check if already nested (has child_spans)
        first = raw_spans[0] if raw_spans else {}
        if "child_spans" in first:
            return [self._parse_nested_span(s, parent_id=None) for s in raw_spans]

        # Flat list — build tree from parent references
        span_map: Dict[str, TRAILSpan] = {}
        for raw_span in raw_spans:
            span = self._parse_flat_span(raw_span)
            span_map[span.span_id] = span

        # Link children to parents
        roots: List[TRAILSpan] = []
        for span in span_map.values():
            if span.parent_span_id and span.parent_span_id in span_map:
                span_map[span.parent_span_id].child_spans.append(span)
            else:
                roots.append(span)

        return roots

    def _parse_flat_span(self, raw: Dict[str, Any]) -> TRAILSpan:
        """Parse a single flat span dict."""
        attributes = self._normalize_attributes(
            raw.get("span_attributes", raw.get("attributes", raw.get("attrs", {})))
        )

        events = raw.get("events", [])
        if isinstance(events, str):
            try:
                events = json.loads(events)
            except json.JSONDecodeError:
                events = []

        return TRAILSpan(
            span_id=str(raw.get("span_id", raw.get("spanId", raw.get("id", "")))),
            parent_span_id=raw.get("parent_span_id", raw.get("parentSpanId")),
            span_name=str(raw.get("name", raw.get("span_name", ""))),
            span_kind=str(raw.get("kind", raw.get("span_kind", "INTERNAL"))),
            attributes=attributes,
            events=events if isinstance(events, list) else [],
        )

    def _parse_nested_span(
        self, raw: Dict[str, Any], parent_id: Optional[str] = None
    ) -> TRAILSpan:
        """Parse a nested span dict (with child_spans)."""
        span = self._parse_flat_span(raw)

        # Set parent reference if not already set from raw data
        if span.parent_span_id is None and parent_id is not None:
            span.parent_span_id = parent_id

        raw_children = raw.get("child_spans", [])
        if isinstance(raw_children, str):
            try:
                raw_children = json.loads(raw_children)
            except json.JSONDecodeError:
                raw_children = []

        span.child_spans = [
            self._parse_nested_span(c, parent_id=span.span_id)
            for c in raw_children
            if isinstance(c, dict)
        ]
        return span

    def _normalize_attributes(
        self, attrs: Any
    ) -> Dict[str, Any]:
        """Normalize OTEL attributes to a flat dict.

        Handles both ``{"key": "val"}`` style and OTEL's
        ``[{"key": "k", "value": {"stringValue": "v"}}]`` format.
        """
        if isinstance(attrs, dict):
            return attrs

        if isinstance(attrs, str):
            try:
                attrs = json.loads(attrs)
            except json.JSONDecodeError:
                return {}

        if isinstance(attrs, list):
            result: Dict[str, Any] = {}
            for item in attrs:
                if not isinstance(item, dict):
                    continue
                key = item.get("key", "")
                value_obj = item.get("value", {})
                if isinstance(value_obj, dict):
                    for vtype in ("stringValue", "intValue", "doubleValue", "boolValue"):
                        if vtype in value_obj:
                            result[key] = value_obj[vtype]
                            break
                    else:
                        result[key] = value_obj
                else:
                    result[key] = value_obj
            return result

        return {}

    def __iter__(self) -> Iterator[TRAILTrace]:
        if not self._loaded:
            self.load()
        return iter(self._traces)

    def __len__(self) -> int:
        return len(self._traces)

    @property
    def traces(self) -> List[TRAILTrace]:
        return self._traces

    def filter_by_source(self, source: str) -> List[TRAILTrace]:
        """Filter traces by source benchmark (gaia, swe-bench)."""
        source_lower = source.lower()
        return [t for t in self._traces if t.source == source_lower]

    def filter_has_pisama_mappings(self) -> List[TRAILTrace]:
        """Return traces that have at least one Pisama-mappable annotation."""
        return [t for t in self._traces if t.mapped_annotations]

    def get_statistics(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        if not self._traces:
            return {"total": 0}

        by_source: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        by_pisama_type: Dict[str, int] = {}
        by_impact: Dict[str, int] = {}
        total_annotations = 0
        mapped_annotations = 0
        total_spans = 0

        for trace in self._traces:
            by_source[trace.source] = by_source.get(trace.source, 0) + 1
            total_spans += len(trace.flatten_spans())

            for ann in trace.annotations:
                total_annotations += 1
                by_category[ann.category] = by_category.get(ann.category, 0) + 1
                by_impact[ann.impact] = by_impact.get(ann.impact, 0) + 1
                if ann.pisama_type:
                    mapped_annotations += 1
                    by_pisama_type[ann.pisama_type] = (
                        by_pisama_type.get(ann.pisama_type, 0) + 1
                    )

        with_failures = sum(1 for t in self._traces if t.has_failures)

        return {
            "total_traces": len(self._traces),
            "with_failures": with_failures,
            "healthy": len(self._traces) - with_failures,
            "total_annotations": total_annotations,
            "mapped_annotations": mapped_annotations,
            "unmapped_annotations": total_annotations - mapped_annotations,
            "total_spans": total_spans,
            "by_source": dict(sorted(by_source.items(), key=lambda x: -x[1])),
            "by_category": dict(sorted(by_category.items(), key=lambda x: -x[1])),
            "by_pisama_type": dict(sorted(by_pisama_type.items(), key=lambda x: -x[1])),
            "by_impact": dict(sorted(by_impact.items(), key=lambda x: -x[1])),
            "coverage": f"{len(TRAIL_TO_PISAMA)}/{len(TRAIL_ALL_CATEGORIES)} categories mapped",
        }
