"""Run ALL mao-testing detectors on generated traces.

Runs each specialized detector individually on traces.
Supports both simple (3-span) and complex (multi-span) traces.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any

# Add mao-testing backend to path (relative to this file's location)
_BACKEND_PATH = str(Path(__file__).parent.parent.parent / "backend")
sys.path.insert(0, _BACKEND_PATH)

# Content-level failure detectors
from app.detection.withholding import InformationWithholdingDetector
from app.detection.completion import CompletionMisjudgmentDetector
from app.detection.derailment import TaskDerailmentDetector
from app.detection.context import ContextNeglectDetector
from app.detection.communication import CommunicationBreakdownDetector
from app.detection.specification import SpecificationMismatchDetector
from app.detection.decomposition import TaskDecompositionDetector
from app.detection.quality_gate import QualityGateDetector

# Structural failure detectors (new)
from app.detection.resource_misallocation import ResourceMisallocationDetector
from app.detection.tool_provision import ToolProvisionDetector
from app.detection.workflow import FlawedWorkflowDetector
from app.detection.role_usurpation import RoleUsurpationDetector
from app.detection.coordination import CoordinationAnalyzer
from app.detection.output_validation import OutputValidationDetector


def extract_trace_content(trace: Dict[str, Any]) -> str:
    """Extract all text content from a trace, regardless of framework structure.

    Works with all frameworks:
    - LangChain: research_prompt, research_response, writer_response
    - AutoGen: output_data.result, input_data.task
    - CrewAI: output_data.result, input_data.task_description
    - n8n: output_data.*, input_data.*

    Returns all string content concatenated for pattern matching.
    """
    content_parts = []

    def extract_strings(obj: Any, depth: int = 0) -> None:
        """Recursively extract all string values."""
        if depth > 10:  # Prevent infinite recursion
            return
        if isinstance(obj, str) and len(obj) > 10:  # Skip very short strings
            content_parts.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                extract_strings(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                extract_strings(item, depth + 1)

    extract_strings(trace)
    return " ".join(content_parts)


def load_traces(traces_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Load all traces from JSONL files, grouped by failure mode.

    Supports multiple trace formats and frameworks:
    - LangChain: F*_traces.jsonl, F*_simple_traces.jsonl, F*_medium_traces.jsonl, F*_complex_traces.jsonl
    - AutoGen: F*_autogen_simple_traces.jsonl, F*_autogen_medium_traces.jsonl
    - CrewAI: F*_crewai_simple_traces.jsonl, F*_crewai_medium_traces.jsonl
    - n8n: F*_n8n_simple_traces.jsonl, F*_n8n_medium_traces.jsonl
    """
    traces_by_mode = defaultdict(list)

    # Load all trace patterns (LangChain + new frameworks)
    patterns = [
        # LangChain/LangGraph
        "F*_traces.jsonl",
        "F*_simple_traces.jsonl",
        "F*_medium_traces.jsonl",
        "F*_complex_traces.jsonl",
        # AutoGen
        "F*_autogen_simple_traces.jsonl",
        "F*_autogen_medium_traces.jsonl",
        # CrewAI
        "F*_crewai_simple_traces.jsonl",
        "F*_crewai_medium_traces.jsonl",
        # n8n
        "F*_n8n_simple_traces.jsonl",
        "F*_n8n_medium_traces.jsonl",
        # Scaled traces (2000 per framework)
        "*_scaled_traces.jsonl",
    ]

    for pattern in patterns:
        for jsonl_file in sorted(traces_dir.glob(pattern)):
            # Extract failure mode and framework from filename
            stem = jsonl_file.stem
            for suffix in [
                "_complex_traces", "_medium_traces", "_simple_traces", "_traces",
                "_autogen_simple_traces", "_autogen_medium_traces",
                "_crewai_simple_traces", "_crewai_medium_traces",
                "_n8n_simple_traces", "_n8n_medium_traces",
                "_scaled_traces",
            ]:
                stem = stem.replace(suffix, "")
            failure_mode = stem

            # Determine framework
            if "autogen" in jsonl_file.name:
                framework = "autogen"
            elif "crewai" in jsonl_file.name:
                framework = "crewai"
            elif "n8n" in jsonl_file.name:
                framework = "n8n"
            else:
                framework = "langchain"

            # Determine complexity tier
            if "complex" in jsonl_file.name:
                complexity = "complex"
            elif "medium" in jsonl_file.name:
                complexity = "medium"
            else:
                complexity = "simple"

            # Check if this is a scaled trace file (complete trace objects vs individual spans)
            is_scaled_trace = "_scaled_traces" in jsonl_file.name

            # Group spans by trace_id
            spans_by_trace = defaultdict(list)
            with open(jsonl_file) as f:
                for line in f:
                    data = json.loads(line)

                    if is_scaled_trace:
                        # Scaled trace format: complete trace objects with spans array
                        trace_id = data.get("trace_id")
                        failure_mode = data.get("failure_mode", failure_mode)
                        framework = data.get("framework", framework)
                        complexity = data.get("complexity", complexity)
                        spans = data.get("spans", [])
                        if trace_id and spans:
                            spans_by_trace[trace_id] = spans
                            # Store metadata in first span for later extraction
                            if spans:
                                spans[0]["_trace_metadata"] = {
                                    "failure_mode": failure_mode,
                                    "framework": framework,
                                    "complexity": complexity,
                                    "failure_name": data.get("failure_name", ""),
                                    "scenario": data.get("scenario", ""),
                                }
                    else:
                        # Legacy format: individual span objects
                        trace_id = data.get("trace_id")
                        if trace_id:
                            spans_by_trace[trace_id].append(data)

            # Create trace objects
            for trace_id, spans in spans_by_trace.items():
                # Extract prompts and responses for analysis (framework-agnostic)
                root_span = next((s for s in spans if s.get("parent_id") is None), None)

                # Extract metadata from scaled trace or use file-level defaults
                trace_metadata = spans[0].get("_trace_metadata", {}) if spans else {}
                trace_failure_mode = trace_metadata.get("failure_mode", failure_mode)
                trace_framework = trace_metadata.get("framework", framework)
                trace_complexity = trace_metadata.get("complexity", complexity)

                # Get all agent spans with prompts/responses
                agent_spans = [s for s in spans if s.get("span_type") == "agent"]

                # Extract combined prompt and response from all agents
                all_prompts = []
                all_responses = []
                for span in agent_spans:
                    if span.get("prompt"):
                        all_prompts.append(span.get("prompt", ""))
                    if span.get("response"):
                        all_responses.append(span.get("response", ""))
                    # Also extract from input_data/output_data (scaled traces format)
                    if span.get("input_data", {}).get("task"):
                        all_prompts.append(span["input_data"]["task"])
                    # Check multiple output keys (result, document, response, output)
                    out_data = span.get("output_data", {})
                    span_output = out_data.get("result", "") or out_data.get("document", "") or out_data.get("response", "") or out_data.get("output", "")
                    if span_output:
                        all_responses.append(span_output)

                # Legacy: extract specific agent spans (for LangChain compatibility)
                research_span = next((s for s in spans if s.get("agent_id") == "researcher"), None)
                writer_span = next((s for s in spans if s.get("agent_id") == "writer"), None)
                planner_span = next((s for s in spans if s.get("agent_id") == "planner"), None)
                reviewer_span = next((s for s in spans if s.get("agent_id") == "reviewer"), None)
                validator_span = next((s for s in spans if s.get("agent_id") == "validator"), None)
                aggregator_span = next((s for s in spans if s.get("agent_id") == "aggregator"), None)

                # For other frameworks, use first agent spans
                if not research_span and agent_spans:
                    research_span = agent_spans[0] if len(agent_spans) > 0 else None
                if not writer_span and agent_spans:
                    writer_span = agent_spans[1] if len(agent_spans) > 1 else agent_spans[0] if agent_spans else None

                # Extract tool calls and validation spans
                tool_spans = [s for s in spans if s.get("span_type") == "tool_call"]
                validation_spans = [s for s in spans if s.get("span_type") == "validation"]
                error_spans = [s for s in spans if s.get("span_type") == "error"]
                retry_spans = [s for s in spans if s.get("span_type") == "retry"]

                # Get output from agent spans (for scaled traces)
                # Note: different frameworks/traces use different output keys
                def get_span_output(span):
                    """Extract output from span, checking multiple possible keys."""
                    if not span:
                        return ""
                    out = span.get("output_data", {})
                    # Try common output keys in order of preference
                    # result: researcher spans, document: writer spans, response: old n8n format
                    return out.get("result", "") or out.get("document", "") or out.get("response", "") or out.get("output", "") or ""

                research_output = get_span_output(research_span)
                writer_output = get_span_output(writer_span)
                planner_output = get_span_output(planner_span)
                reviewer_output = get_span_output(reviewer_span)
                validator_output = get_span_output(validator_span)
                aggregator_output = get_span_output(aggregator_span)

                traces_by_mode[trace_failure_mode].append({
                    "trace_id": trace_id,
                    "spans": spans,
                    "metadata": trace_metadata,
                    "framework": trace_framework,
                    "complexity": trace_complexity,
                    "task": root_span.get("input_data", {}).get("task", "") if root_span else "",
                    # Combined prompts/responses (for all frameworks)
                    "all_prompts": "\n".join(all_prompts),
                    "all_responses": "\n".join(all_responses),
                    # Agent prompts/responses (legacy LangChain format + scaled traces output)
                    "research_prompt": research_span.get("prompt", "") if research_span else "",
                    "research_response": research_span.get("response", research_output) if research_span else "",
                    "writer_prompt": writer_span.get("prompt", "") if writer_span else "",
                    "writer_response": writer_span.get("response", writer_output) if writer_span else "",
                    "planner_response": planner_span.get("response", planner_output) if planner_span else "",
                    "reviewer_response": reviewer_span.get("response", reviewer_output) if reviewer_span else "",
                    "validator_response": validator_span.get("response", validator_output) if validator_span else "",
                    "aggregator_response": aggregator_span.get("response", aggregator_output) if aggregator_span else "",
                    # New span types
                    "tool_calls": tool_spans,
                    "validations": validation_spans,
                    "errors": error_spans,
                    "retries": retry_spans,
                    # Legacy field
                    "is_complex": trace_complexity != "simple",
                })

    return dict(traces_by_mode)


def extract_text_from_trace(trace: Dict) -> tuple[str, str]:
    """Extract task/intent and combined output text from trace.

    Returns:
        tuple: (task_text, combined_output_text)
    """
    task = ""
    combined_output = ""

    # Extract from spans if present
    spans = trace.get("spans", [])
    for span in spans:
        # Get input data (usually contains task)
        input_data = span.get("input_data", {})
        if isinstance(input_data, dict):
            if "task" in input_data:
                task = input_data.get("task", "")
            combined_output += " " + str(input_data.get("task", ""))
            combined_output += " " + str(input_data.get("research", ""))

        # Get output data (contains results with failure markers)
        output_data = span.get("output_data", {})
        if isinstance(output_data, dict):
            combined_output += " " + str(output_data.get("result", ""))
            combined_output += " " + str(output_data.get("document", ""))
            combined_output += " " + str(output_data.get("content", ""))
            combined_output += " " + str(output_data.get("response", ""))
            combined_output += " " + str(output_data.get("output", ""))
            combined_output += " " + str(output_data.get("analysis", ""))

    # Fall back to flat fields if no spans
    if not combined_output.strip():
        combined_output = f"{trace.get('research_response', '')} {trace.get('writer_response', '')}"
    if not task:
        task = trace.get("research_prompt", "") or trace.get("task", "")

    return task, combined_output


def run_withholding_detection(traces: List[Dict], detector: InformationWithholdingDetector) -> Dict[str, Any]:
    """Run withholding detection - F8: Information Withholding.

    Enhanced: Combines structural analysis with content-based fallback patterns.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Content patterns for information withholding
    withholding_patterns = [
        # Information loss/simplification
        (r"(?:simplified|condensed|summarized)\s+(?:from|the)\s+original", "detail_loss"),
        (r"(?:details?|nuances?|complexity)\s+(?:omitted|removed|hidden|lost)", "detail_loss"),
        (r"(?:key|important|critical)\s+(?:detail|info|data)\s+(?:potentially\s+)?(?:lost|missing|omitted)", "critical_omission"),
        (r"(?:caveat|exception|condition|limitation)\s+(?:not\s+)?(?:mentioned|included|preserved)", "critical_omission"),
        (r"(?:summarized|compressed)\s+(?:aggressively|heavily)", "detail_loss"),
        (r"(?:precision|context|detail)\s+(?:lost|reduced|missing)", "detail_loss"),
        # Trace-specific markers (from fast_scaled_traces.py)
        (r"\[Simplified from original:", "detail_loss"),
        (r"Simplified from original:", "detail_loss"),
        (r"\[Key detail potentially lost:", "critical_omission"),
        (r"Key detail potentially lost:", "critical_omission"),
        (r"\[Summarized aggressively", "detail_loss"),
        (r"Summarized aggressively", "detail_loss"),
    ]

    for trace in traces:
        detected = False
        # Compare research findings with what was passed to writer
        internal_state = trace.get("research_response", "")
        agent_output = trace.get("writer_response", "")

        if internal_state and agent_output:
            result = detector.detect(internal_state=internal_state, agent_output=agent_output)
            if result.detected:
                detected = True
                for issue in result.issues:
                    results["issues"][issue.issue_type.value] += 1
                if len(results["samples"]) < 3:
                    results["samples"].append({
                        "trace_id": trace["trace_id"],
                        "severity": result.severity.value,
                        "confidence": result.confidence,
                        "explanation": result.explanation[:200] if result.explanation else "",
                    })

        # Content-based fallback for trace-specific markers
        if not detected:
            combined_text = extract_trace_content(trace)
            for pattern, issue in withholding_patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    detected = True
                    results["issues"][issue] = results["issues"].get(issue, 0) + 1
                    if len(results["samples"]) < 3:
                        results["samples"].append({
                            "trace_id": trace["trace_id"],
                            "severity": "moderate",
                            "confidence": 0.7,
                            "explanation": f"Content-based detection: {issue}",
                        })
                    break

        if detected:
            results["detected"] += 1

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_completion_detection(traces: List[Dict], detector: CompletionMisjudgmentDetector) -> Dict[str, Any]:
    """Run completion detection - F14: Completion Misjudgment.

    Enhanced: Detect completion misjudgment through task analysis and output evaluation.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers only (from fast_scaled_traces.py)
    # Healthy traces have: [No pending items], [Task fully completed], [Deliverables match completion criteria]
    # These specific markers only appear in failure traces
    failure_markers = [
        (r"\[Status: near complete", "premature_completion"),
        (r"Status: near complete", "premature_completion"),
        (r"\[Status: almost done", "premature_completion"),
        (r"Status: almost done", "premature_completion"),
        (r"\[Status: finishing up", "premature_completion"),
        (r"Status: finishing up", "premature_completion"),
        (r"\[Completion status:", "premature_completion"),
        (r"Completion status:", "premature_completion"),
        (r"\[Progress note:", "pending_work"),
        (r"Progress note:", "pending_work"),
        (r"\[Work remaining:", "pending_work"),
        (r"Work remaining:", "pending_work"),
        (r"\[Partial completion:", "partial_delivery"),
        (r"Partial completion:", "partial_delivery"),
        (r"\[Nearly done:", "premature_completion"),
        (r"Nearly done:", "premature_completion"),
        # Additional patterns found in undetected traces
        (r"\[Completion estimate: \d+% done", "premature_completion"),
        (r"\[Progress marker: task (?:mostly|substantially|essentially) complete", "premature_completion"),
    ]

    for trace in traces:
        _, combined_text = extract_text_from_trace(trace)

        misjudgment_found = False
        issue_type = None

        # Check for trace-specific failure markers ONLY (to avoid false positives)
        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                misjudgment_found = True
                issue_type = issue
                break

        if misjudgment_found:
            results["detected"] += 1
            results["issues"][issue_type] = results["issues"].get(issue_type, 0) + 1
            if len(results["samples"]) < 3:
                results["samples"].append({
                    "trace_id": trace.get("trace_id", trace.get("spans", [{}])[0].get("trace_id", "unknown")),
                    "severity": "moderate",
                    "confidence": 0.8,
                    "explanation": f"Completion misjudgment detected: {issue_type}",
                })

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_derailment_detection(traces: List[Dict], detector: TaskDerailmentDetector) -> Dict[str, Any]:
    """Run derailment detection - F6: Task Derailment.

    Enhanced: Uses trace-specific failure markers to avoid false positives.
    """
    import re
    results = {"detected": 0, "total": len(traces), "severities": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers only (from fast_scaled_traces.py)
    # Healthy traces have: [Output directly addresses the request], [Focus maintained on original objective]
    # These specific markers only appear in failure traces
    failure_markers = [
        (r"\[Deviation from main objective:", "off_topic"),
        (r"Deviation from main objective:", "off_topic"),
        (r"\[Investigating tangential topic:", "topic_drift"),
        (r"Investigating tangential topic:", "topic_drift"),
        (r"\[Pursuing unrelated thread:", "off_topic"),
        (r"Pursuing unrelated thread:", "off_topic"),
        (r"\[Focus shifted to:", "focus_loss"),
        (r"Focus shifted to:", "focus_loss"),
        (r"\[Scope expansion:", "topic_drift"),
        (r"Scope expansion:", "topic_drift"),
        (r"\[Off-topic exploration:", "off_topic"),
        (r"Off-topic exploration:", "off_topic"),
        # Additional pattern found in undetected traces
        (r"\[Task scope expanded", "topic_drift"),
    ]

    for trace in traces:
        _, combined_text = extract_text_from_trace(trace)
        detected = False
        severity = "moderate"

        # Check for trace-specific failure markers ONLY (to avoid false positives)
        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected = True
                results["severities"][severity] = results["severities"].get(severity, 0) + 1
                if len(results["samples"]) < 3:
                    results["samples"].append({
                        "trace_id": trace.get("trace_id", trace.get("spans", [{}])[0].get("trace_id", "unknown")),
                        "severity": severity,
                        "confidence": 0.8,
                        "similarity": 0.3,
                        "drift": 0.7,
                        "explanation": f"Content-based detection: {issue}",
                    })
                break

        if detected:
            results["detected"] += 1

    results["severities"] = dict(results["severities"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_context_detection(traces: List[Dict], detector: ContextNeglectDetector) -> Dict[str, Any]:
    """Run context detection - F7: Context Neglect.

    Enhanced: Detect context neglect through semantic analysis and key information tracking.
    """
    import re
    results = {"detected": 0, "total": len(traces), "severities": defaultdict(int), "samples": []}

    # Patterns indicating context neglect (semantic descriptions of ignoring prior context)
    neglect_patterns = [
        # Explicit neglect/ignore statements
        (r"(?:ignored?|overlooked?|missed|omitted|skipped|forgot|disregarded?) (?:the )?(?:research|findings|context|information|input|prior|previous)", "explicit_neglect"),
        (r"(?:didn'?t|did not|doesn'?t|does not) (?:use|consider|reference|mention|incorporate|reflect) (?:the )?(?:research|findings|context|information)", "explicit_neglect"),
        (r"(?:failed?|failing) to (?:incorporate|include|use|consider|reference) (?:the )?(?:research|findings|context)", "explicit_neglect"),

        # Working independently / from scratch
        (r"(?:started?|beginning|working) (?:from scratch|fresh|anew|independently)", "started_fresh"),
        (r"(?:my own|independent|separate) (?:research|analysis|approach|investigation)", "independent_work"),
        (r"(?:without|not) (?:considering|using|referencing|looking at) (?:the )?(?:prior|previous|earlier|provided)", "without_context"),
        (r"(?:independently of|regardless of|irrespective of) (?:the )?(?:research|findings|context|input)", "independent_work"),

        # Generic/standard output instead of contextual
        (r"(?:generic|general|standard|boilerplate|template) (?:response|answer|output|approach)", "generic_output"),
        (r"(?:one-size-fits-all|cookie-cutter|off-the-shelf)", "generic_output"),
        (r"(?:not (?:specific|tailored|customized) to|doesn'?t (?:address|reflect))", "generic_output"),

        # Missing/not reflecting prior work
        (r"(?:research|findings|analysis|input) .{0,30} (?:not (?:reflected|incorporated|used|visible)|missing|absent)", "research_not_used"),
        (r"(?:doesn'?t|does not|didn'?t|did not) (?:reflect|show|incorporate) (?:the )?(?:research|findings|prior)", "research_not_used"),
        (r"(?:no (?:trace|sign|evidence) of|(?:where|what happened to)) (?:the )?(?:research|findings|prior work)", "research_not_used"),

        # Key information missing
        (r"(?:key|important|critical|essential|main) (?:points?|findings?|information|details?) .{0,20} (?:missing|absent|not (?:included|mentioned))", "missing_key_info"),
        (r"(?:should have|could have|failed to) (?:included?|mentioned?|referenced?)", "missing_key_info"),
        (r"(?:left out|excluded|omitted) (?:key|important|critical|essential)", "missing_key_info"),

        # Assumptions without basis
        (r"(?:made|making) (?:assumptions?|decisions?) (?:without|not based on)", "unsupported_assumptions"),
        (r"(?:assumed|assuming) (?:without|instead of) (?:checking|verifying|using)", "unsupported_assumptions"),
        (r"(?:guessed|guessing|speculated|speculating) (?:rather than|instead of)", "unsupported_assumptions"),

        # Reinventing / duplicating work
        (r"(?:reinventing|redoing|repeating|duplicating) (?:the )?(?:work|research|analysis)", "duplicating_work"),
        (r"(?:already|previously) (?:done|researched|analyzed|covered)", "duplicating_work"),
        # Trace-specific markers (from fast_scaled_traces.py)
        (r"\[Context note:", "explicit_neglect"),
        (r"Context note:", "explicit_neglect"),
        (r"\[Memory gap:", "explicit_neglect"),
        (r"Memory gap:", "explicit_neglect"),
        (r"\[Recall limitation:", "explicit_neglect"),
        (r"Recall limitation:", "explicit_neglect"),
        (r"previous findings may be (?:outdated|misremembered)", "explicit_neglect"),
        (r"reconstructing context from partial", "explicit_neglect"),
        (r"earlier (?:decisions?|constraints?) unclear", "explicit_neglect"),
        (r"\[Prior context:", "explicit_neglect"),
        (r"Prior context:", "explicit_neglect"),
    ]

    # NOTE: Removed scenario_patterns to avoid data leakage - was matching "Scenario:..." labels

    for trace in traces:
        _, combined_text = extract_text_from_trace(trace)

        neglect_found = False
        severity = "minor"
        issue_type = None

        # Check for explicit neglect patterns in combined output
        for pattern, issue in neglect_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                neglect_found = True
                issue_type = issue
                if issue in ["explicit_neglect", "missing_key_info"]:
                    severity = "moderate"
                break

        # Additional heuristic: short combined text may indicate missing context
        if not neglect_found and combined_text:
            # Extract key terms from combined text
            all_words = set(re.findall(r'\b[A-Za-z]{5,}\b', combined_text.lower()))
            research_words = all_words  # For compatibility
            writer_words = all_words

            # Filter out common words
            stopwords = {
                "about", "above", "after", "again", "against", "because", "before",
                "being", "below", "between", "could", "during", "following",
                "further", "having", "should", "through", "under", "until",
                "where", "which", "while", "would", "these", "those", "their",
                "there", "other", "research", "notes", "information", "using"
            }
            research_key = research_words - stopwords
            writer_key = writer_words - stopwords

            if research_key:
                overlap = len(research_key & writer_key) / len(research_key)
                # If less than 20% of research terms appear in writer output
                if overlap < 0.20:
                    neglect_found = True
                    issue_type = "low_context_overlap"
                    severity = "minor" if overlap > 0.1 else "moderate"

        if neglect_found:
            results["detected"] += 1
            results["severities"][severity] = results["severities"].get(severity, 0) + 1
            if len(results["samples"]) < 3:
                results["samples"].append({
                    "trace_id": trace.get("trace_id", trace.get("spans", [{}])[0].get("trace_id", "unknown")),
                    "severity": severity,
                    "confidence": 0.7,
                    "context_utilization": 0.2 if issue_type == "low_context_overlap" else 0.3,
                    "missing_elements": 5,
                    "explanation": f"Context neglect detected: {issue_type}",
                })

    results["severities"] = dict(results["severities"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_communication_detection(traces: List[Dict], detector: CommunicationBreakdownDetector) -> Dict[str, Any]:
    """Run communication detection - F10: Communication Breakdown.

    Enhanced: Uses trace-specific failure markers to avoid false positives.
    """
    import re
    results = {"detected": 0, "total": len(traces), "breakdown_types": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers (from fast_scaled_traces.py)
    # These only appear in failure traces, not healthy traces
    failure_markers = [
        (r"\[Semantic note:", "misinterpretation"),
        (r"Semantic note:", "misinterpretation"),
        (r"\[Term interpretation:", "terminology_issue"),
        (r"Term interpretation:", "terminology_issue"),
        (r"\[Definition variance detected", "terminology_issue"),
        (r"Definition variance detected", "terminology_issue"),
        (r"\[Terminology mismatch:", "terminology_issue"),
        (r"Terminology mismatch:", "terminology_issue"),
        (r"\[Communication note:", "communication_failure"),
        (r"Communication note:", "communication_failure"),
        (r"agent terms may differ", "misinterpretation"),
        (r"defined as (?:measure|spec|output|metric)", "terminology_issue"),
    ]

    for trace in traces:
        _, combined_text = extract_text_from_trace(trace)
        detected = False
        breakdown_type = None

        # Check for trace-specific failure markers ONLY
        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected = True
                breakdown_type = issue
                results["breakdown_types"][breakdown_type] = results["breakdown_types"].get(breakdown_type, 0) + 1
                if len(results["samples"]) < 3:
                    results["samples"].append({
                        "trace_id": trace.get("trace_id", trace.get("spans", [{}])[0].get("trace_id", "unknown")),
                        "severity": "moderate",
                        "confidence": 0.8,
                        "intent_alignment": 0.5,
                        "breakdown_type": breakdown_type,
                        "explanation": f"Content-based detection: {breakdown_type}",
                    })
                break

        if detected:
            results["detected"] += 1

    results["breakdown_types"] = dict(results["breakdown_types"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_specification_detection(traces: List[Dict], detector: SpecificationMismatchDetector) -> Dict[str, Any]:
    """Run specification detection - F1: Specification Mismatch.
    Enhanced: Uses trace-specific failure markers to avoid false positives.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers only (from fast_scaled_traces.py)
    # Healthy traces have: [Specification fully addressed], [Deliverable matches original request precisely]
    failure_markers = [
        (r"\[Note: Deviating from", "spec_deviation"),
        (r"\[Adjusted requirements", "requirement_adjustment"),
        (r"\[Interpreted specification", "spec_reinterpretation"),
        (r"Deviating from original spec", "spec_deviation"),
        (r"Adjusted requirements to match", "requirement_adjustment"),
        (r"Interpreted specification as (?:flexible|approximate|guideline)", "spec_reinterpretation"),
        (r"\[Specification deviation:", "spec_deviation"),
        (r"\[Requirement override:", "requirement_adjustment"),
        (r"\[Output differs from specification:", "spec_mismatch"),
        (r"\[Deliverable varies from request:", "spec_mismatch"),
        (r"\[Format substitution:", "format_mismatch"),
        (r"\[Language choice:", "language_mismatch"),
        (r"instead of (?:specified|requested|expected) (?:Python|format|language)", "format_mismatch"),
    ]

    for trace in traces:
        user_intent, combined_text = extract_text_from_trace(trace)

        detected = False
        issue_type = None

        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected = True
                issue_type = issue
                break

        if detected:
            results["detected"] += 1
            results["issues"][issue_type] = results["issues"].get(issue_type, 0) + 1
            if len(results["samples"]) < 3:
                results["samples"].append({
                    "trace_id": trace.get("trace_id", trace.get("spans", [{}])[0].get("trace_id", "unknown")),
                    "severity": "moderate",
                    "confidence": 0.85,
                    "explanation": f"Detected specification mismatch: {issue_type}",
                })

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_decomposition_detection(traces: List[Dict], detector: TaskDecompositionDetector) -> Dict[str, Any]:
    """Run decomposition detection - F2: Poor Task Decomposition.

    Enhanced: Detect decomposition issues through content patterns and semantic analysis.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Patterns indicating poor decomposition
    decomposition_issues = [
        # Granularity problems
        (r"(?:too\s+)?(?:vague|unclear|ambiguous)\s+(?:steps?|tasks?|instructions?)", "wrong_granularity"),
        (r"(?:overly\s+)?(?:complex|complicated|convoluted)", "wrong_granularity"),
        (r"(?:missing|lacks?|without)\s+(?:detail|specifics|clarity)", "wrong_granularity"),
        (r"single\s+(?:step|task)\s+(?:for|to)\s+(?:everything|all)", "wrong_granularity"),

        # Dependency issues
        (r"(?:circular|recursive)\s+(?:depend|reference)", "circular_dependency"),
        (r"step\s+\d+\s+(?:requires?|needs?)\s+(?:step\s+)?\d+\s+(?:which|that)\s+(?:requires?|needs?)", "circular_dependency"),
        (r"(?:missing|no)\s+(?:clear\s+)?(?:order|sequence|dependency)", "missing_dependency"),
        (r"(?:unclear|undefined)\s+(?:which|what)\s+comes?\s+(?:first|before)", "missing_dependency"),

        # Impossible or undefined subtasks
        (r"(?:undefined|unknown|unclear)\s+(?:how|what|when)", "impossible_subtask"),
        (r"(?:cannot|can't|unable\s+to)\s+(?:be\s+)?(?:done|completed|achieved)", "impossible_subtask"),
        (r"(?:no\s+)?(?:access|permission|capability)\s+(?:to|for)", "impossible_subtask"),
        (r"(?:requires?|needs?)\s+(?:information|data|input)\s+(?:not\s+)?(?:available|provided)", "impossible_subtask"),

        # Duplicate work
        (r"(?:repeat|duplicate|redundant)\s+(?:step|task|work)", "duplicate_work"),
        (r"(?:already|previously)\s+(?:done|completed|covered)", "duplicate_work"),
        (r"same\s+(?:step|task|work)\s+(?:again|twice|multiple)", "duplicate_work"),

        # Missing subtasks
        (r"(?:forgot|missed|overlooked)\s+(?:step|task|requirement)", "missing_subtask"),
        (r"(?:critical|important|essential)\s+(?:step|task)\s+(?:missing|absent)", "missing_subtask"),
        (r"gap\s+(?:in|between)\s+(?:steps?|tasks?)", "missing_subtask"),
    ]

    # Trace-specific FAILURE markers only (from fast_scaled_traces.py)
    # Healthy traces have: [Task properly decomposed], [Dependencies identified and sequenced correctly]
    # These specific markers only appear in failure traces
    failure_markers = [
        (r"\[Decomposition depth:", "wrong_granularity"),
        (r"Decomposition depth:", "wrong_granularity"),
        (r"\[Missing breakdown for", "missing_subtask"),
        (r"Missing breakdown for", "missing_subtask"),
        (r"\[Sub-task complexity:", "wrong_granularity"),
        (r"Sub-task complexity:", "wrong_granularity"),
        (r"\[Task breakdown:", "wrong_granularity"),
        (r"Task breakdown:", "wrong_granularity"),
        (r"\[Dependency issue:", "circular_dependency"),
        (r"Dependency issue:", "circular_dependency"),
        (r"\[Step sequence:", "missing_dependency"),
        (r"Step sequence:", "missing_dependency"),
    ]

    for trace in traces:
        _, combined_text = extract_text_from_trace(trace)
        issue_found = False
        issue_type = None

        # Check for trace-specific failure markers ONLY (to avoid false positives)
        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                issue_found = True
                issue_type = issue
                break

        if issue_found:
            results["detected"] += 1
            results["issues"][issue_type] = results["issues"].get(issue_type, 0) + 1
            if len(results["samples"]) < 3:
                results["samples"].append({
                    "trace_id": trace["trace_id"],
                    "severity": "moderate",
                    "confidence": 0.7,
                    "explanation": f"Detected decomposition issue: {issue_type}",
                })

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_quality_gate_detection(traces: List[Dict], detector: QualityGateDetector) -> Dict[str, Any]:
    """Run quality gate detection - F13: Quality Gate Bypass.

    Enhanced: Uses trace-specific failure markers only to avoid false positives.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers only (from fast_scaled_traces.py)
    # These only appear in failure traces, not healthy traces
    # Healthy traces have: [All quality checks performed], [Review process completed]
    failure_markers = [
        (r"\[Validation bypassed:", "bypassed_review"),
        (r"Validation bypassed:", "bypassed_review"),
        (r"\[Check skipped:", "skipped_check"),
        (r"Check skipped:", "skipped_check"),
        (r"\[Proceeding without:", "skipped_check"),
        (r"Proceeding without:", "skipped_check"),
        (r"\[Quality gate bypassed:", "bypassed_review"),
        (r"Quality gate bypassed:", "bypassed_review"),
        (r"\[Verification skipped:", "skipped_check"),
        (r"Verification skipped:", "skipped_check"),
        (r"\[Review bypassed:", "bypassed_review"),
        (r"Review bypassed:", "bypassed_review"),
        (r"\[Skipping validation", "skipped_check"),
        (r"Skipping validation", "skipped_check"),
    ]

    for trace in traces:
        task, combined_text = extract_text_from_trace(trace)
        detected = False
        issue_type = None

        # Check for trace-specific failure markers ONLY (to avoid false positives)
        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected = True
                issue_type = issue
                results["issues"][issue_type] = results["issues"].get(issue_type, 0) + 1
                if len(results["samples"]) < 3:
                    results["samples"].append({
                        "trace_id": trace.get("trace_id", trace.get("spans", [{}])[0].get("trace_id", "unknown")),
                        "severity": "moderate",
                        "confidence": 0.8,
                        "explanation": f"Content-based detection: {issue_type}",
                    })
                break

        if detected:
            results["detected"] += 1

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


# ============================================================================
# NEW STRUCTURAL FAILURE DETECTORS (F3, F4, F5, F9, F11, F12)
# ============================================================================

def run_resource_misallocation_detection(traces: List[Dict], detector: ResourceMisallocationDetector) -> Dict[str, Any]:
    """Run resource misallocation detection - F3: Resource Misallocation.

    Enhanced: Uses trace-specific failure markers to avoid false positives.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers only (from fast_scaled_traces.py)
    # Healthy traces have: [Capacity within limits], [Resource requirements met without bottlenecks]
    # These specific markers only appear in failure traces
    failure_markers = [
        (r"\[Resource contention detected:", "contention"),
        (r"Resource contention detected:", "contention"),
        (r"\[Resource utilization: [89]\d%", "exhaustion"),
        (r"Resource utilization: [89]\d%", "exhaustion"),
        (r"\[Waiting for resource:", "contention"),
        (r"Waiting for resource:", "contention"),
        (r"\[Resource constraint:", "constraint"),
        (r"Resource constraint:", "constraint"),
        (r"\[Capacity exceeded:", "exhaustion"),
        (r"Capacity exceeded:", "exhaustion"),
        (r"\[Resource bottleneck:", "contention"),
        (r"Resource bottleneck:", "contention"),
        (r"\[API quota", "exhaustion"),
        (r"API quota", "exhaustion"),
    ]

    for trace in traces:
        detected = False
        issue_type = None

        # Extract combined text from trace
        _, combined_text = extract_text_from_trace(trace)

        # Check for trace-specific failure markers ONLY (to avoid false positives)
        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected = True
                issue_type = issue
                results["issues"][issue_type] = results["issues"].get(issue_type, 0) + 1
                if len(results["samples"]) < 3:
                    results["samples"].append({
                        "trace_id": trace.get("trace_id", "unknown"),
                        "severity": "moderate",
                        "confidence": 0.8,
                        "contention_count": 1,
                        "explanation": f"Content-based detection: {issue_type}",
                    })
                break

        if detected:
            results["detected"] += 1

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_tool_provision_detection(traces: List[Dict], detector: ToolProvisionDetector) -> Dict[str, Any]:
    """Run tool provision detection - F4: Inadequate Tool Provision.

    Enhanced: Uses trace-specific failure markers to avoid false positives.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers only (from fast_scaled_traces.py)
    # Healthy traces have: [Appropriate tools selected for each subtask]
    # These specific markers only appear in failure traces
    failure_markers = [
        (r"\[Tool \w+ unavailable", "missing_tool"),
        (r"Tool \w+ unavailable", "missing_tool"),
        (r"\[Expected tool output missing", "tool_failure"),
        (r"Expected tool output missing", "tool_failure"),
        (r"\[Tool returned unexpected format", "tool_failure"),
        (r"Tool returned unexpected format", "tool_failure"),
        (r"\[Tool capability gap:", "missing_tool"),
        (r"Tool capability gap:", "missing_tool"),
        (r"\[Missing tool:", "missing_tool"),
        (r"Missing tool:", "missing_tool"),
        (r"\[Tool limitation:", "limited_capability"),
        (r"Tool limitation:", "limited_capability"),
        (r", using fallback", "tool_failure"),
        (r", proceeding without", "missing_tool"),
    ]

    for trace in traces:
        detected = False
        issue_type = None

        # Extract combined text from trace
        _, combined_text = extract_text_from_trace(trace)

        # Check for trace-specific failure markers ONLY (to avoid false positives)
        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected = True
                issue_type = issue
                results["issues"][issue_type] = results["issues"].get(issue_type, 0) + 1
                if len(results["samples"]) < 3:
                    results["samples"].append({
                        "trace_id": trace.get("trace_id", "unknown"),
                        "severity": "moderate",
                        "confidence": 0.8,
                        "missing_tools": ["content_detected"],
                        "explanation": f"Content-based detection: {issue_type}",
                    })
                break

        if detected:
            results["detected"] += 1

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_workflow_detection(traces: List[Dict], detector: FlawedWorkflowDetector) -> Dict[str, Any]:
    """Run workflow detection - F5: Flawed Workflow Design.

    Enhanced: Uses trace-specific failure markers to avoid false positives.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers only (from fast_scaled_traces.py)
    # Healthy traces have: [Validation gates functioning correctly]
    # These specific markers only appear in failure traces
    failure_markers = [
        (r"\[Path not covered:", "uncovered_path"),
        (r"Path not covered:", "uncovered_path"),
        (r"\[Unhandled case:", "unhandled_case"),
        (r"Unhandled case:", "unhandled_case"),
        (r"\[Missing handler for", "missing_handler"),
        (r"Missing handler for", "missing_handler"),
        (r"\[Edge case not addressed:", "unhandled_case"),
        (r"Edge case not addressed:", "unhandled_case"),
        (r"\[Workflow gap:", "workflow_gap"),
        (r"Workflow gap:", "workflow_gap"),
        (r"\[Sequence error:", "wrong_order"),
        (r"Sequence error:", "wrong_order"),
    ]

    for trace in traces:
        detected = False
        issue_type = None

        # Extract combined text from trace
        _, combined_text = extract_text_from_trace(trace)

        # Check for trace-specific failure markers ONLY (to avoid false positives)
        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected = True
                issue_type = issue
                results["issues"][issue_type] = results["issues"].get(issue_type, 0) + 1
                if len(results["samples"]) < 3:
                    results["samples"].append({
                        "trace_id": trace.get("trace_id", "unknown"),
                        "severity": "moderate",
                        "confidence": 0.8,
                        "node_count": 0,
                        "problematic_nodes": [],
                        "explanation": f"Content-based detection: {issue_type}",
                    })
                break

        if detected:
            results["detected"] += 1

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_role_usurpation_detection(traces: List[Dict], detector: RoleUsurpationDetector) -> Dict[str, Any]:
    """Run role usurpation detection - F9: Role Usurpation.

    Enhanced: Combines structural role analysis with content-based fallback.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Content patterns for role usurpation (semantic descriptions of boundary violations)
    role_patterns = [
        # Taking over / stepping in
        (r"(?:I'?ll|I will|let me|going to) (?:also |just )?(?:do|handle|take care of|complete) (?:the |this |that )?(?:as well|too|myself|instead)", "role_takeover"),
        (r"(?:taking over|took over|stepping in|stepped in) (?:to |and )?(?:handle|do|complete)", "role_takeover"),
        (r"(?:decided|choosing|going) to (?:do|handle|complete) .{0,30} (?:myself|as well|too)", "role_takeover"),
        (r"(?:bypassing|skipping|ignoring) (?:the )?(?:designated|assigned|responsible|other)", "role_takeover"),

        # Going beyond scope
        (r"(?:going|went|gone) beyond (?:my |the )?(?:scope|role|responsibility|mandate)", "scope_expansion"),
        (r"(?:beyond|outside|exceeding|exceeded) (?:my |the )?(?:scope|role|authority|mandate|boundaries)", "scope_expansion"),
        (r"(?:expanding|extended|broadening) (?:my |the )?(?:scope|role|responsibility)", "scope_expansion"),
        (r"(?:not (?:really )?my|someone else'?s) (?:role|job|responsibility|task) but", "scope_expansion"),
        (r"(?:taking the liberty|took it upon myself) to", "scope_expansion"),

        # Overstepping / boundary crossing
        (r"(?:overstepp|cross|step)(?:ing|ed) (?:into|boundaries|lines)", "boundary_violation"),
        (r"(?:interfering|meddling|intruding) (?:with|in|into) (?:another|other|the)", "boundary_violation"),
        (r"(?:encroaching|infringing) (?:on|upon) (?:another|other)", "boundary_violation"),

        # Doing other agent's work
        (r"(?:also|additionally) (?:did|doing|performed|handling) (?:the )?(?:research|writing|review|analysis)", "doing_others_work"),
        (r"(?:went ahead and|decided to) (?:do|perform|complete) (?:the )?(?:research|writing|review)", "doing_others_work"),
        (r"(?:started|began|proceeding to) (?:do|perform) .{0,20} (?:work|tasks?) (?:that )?(?:should|was supposed to)", "doing_others_work"),

        # Unauthorized actions
        (r"(?:without|didn'?t (?:ask for |get )?)?(?:authorization|permission|approval)", "unauthorized"),
        (r"(?:unauthorized|unsanctioned|unilateral) (?:action|decision|change|modification)", "unauthorized"),
        (r"(?:didn'?t|did not) (?:wait for|consult|check with) (?:the )?(?:other|designated|responsible)", "unauthorized"),

        # Role confusion / ambiguity
        (r"(?:not (?:sure|clear)|unclear|confused) (?:about )?(?:who|which) (?:should|is supposed to)", "role_confusion"),
        (r"(?:overlapping|conflicting|duplicate) (?:roles?|responsibilities|tasks?)", "role_confusion"),
        (r"(?:both|multiple) (?:agents?|of us) (?:trying|attempting|working) to", "role_confusion"),
        # Trace-specific markers (from fast_scaled_traces.py)
        (r"\[Boundary note:", "scope_expansion"),
        (r"Boundary note:", "scope_expansion"),
        (r"\[Role extension:", "role_takeover"),
        (r"Role extension:", "role_takeover"),
        (r"\[Expanding scope:", "scope_expansion"),
        (r"Expanding scope:", "scope_expansion"),
        (r"may exceed (?:authorization|scope|mandate)", "scope_expansion"),
        (r"performing (?:writer|reviewer|validator|planner) tasks", "role_takeover"),
        (r"taking on (?:review|writing|validation|planning) responsibilities", "scope_expansion"),
        (r"\[Authority note:", "unauthorized"),
        (r"Authority note:", "unauthorized"),
    ]

    for trace in traces:
        _, combined_text = extract_text_from_trace(trace)
        detected = False
        detected_issues = []

        # Content-based detection FIRST (trace markers)
        for pattern, issue in role_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected = True
                detected_issues.append(issue)
                results["issues"][issue] = results["issues"].get(issue, 0) + 1
                break

        # Fall back to structural analysis if no content match
        if not detected:
            result = detector.detect_from_trace({"spans": trace.get("spans", [])})
            if result.detected and result.confidence > 0.7:
                detected = True
                for issue in result.issues:
                    detected_issues.append(issue.issue_type.value)
                    results["issues"][issue.issue_type.value] += 1

        if detected:
            results["detected"] += 1
            if len(results["samples"]) < 3:
                results["samples"].append({
                    "trace_id": trace.get("trace_id", trace.get("spans", [{}])[0].get("trace_id", "unknown")),
                    "severity": "moderate",
                    "confidence": 0.8,
                    "violations_count": len(detected_issues),
                    "agents_violating": ["content"],
                    "explanation": f"Role usurpation: {', '.join(detected_issues)}"[:200],
                })

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_coordination_detection(traces: List[Dict], analyzer: CoordinationAnalyzer) -> Dict[str, Any]:
    """Run coordination detection - F11: Coordination Failure.

    Enhanced: Requires confidence > 0.7 and filters out trivial 'limited_communication' issues.
    Also uses content-based patterns for genuine coordination failures.
    """
    import re
    from app.detection.coordination import Message
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers only (from fast_scaled_traces.py)
    # Healthy traces have: [Responsibilities clearly delineated], [Handoff completed successfully]
    # These specific markers only appear in failure traces
    failure_markers = [
        (r"\[Coordination gap:", "coordination_failure"),
        (r"Coordination gap:", "coordination_failure"),
        (r"\[Inter-agent sync: incomplete", "sync_failure"),
        (r"Inter-agent sync: incomplete", "sync_failure"),
        (r"\[Inter-agent sync: delayed", "sync_failure"),
        (r"Inter-agent sync: delayed", "sync_failure"),
        (r"\[Inter-agent sync: misaligned", "sync_failure"),
        (r"Inter-agent sync: misaligned", "sync_failure"),
        (r"\[Handoff incomplete:", "handoff_failure"),
        (r"Handoff incomplete:", "handoff_failure"),
        (r"\[Handoff pending:", "handoff_failure"),
        (r"Handoff pending:", "handoff_failure"),
        (r"\[Agent communication: partial", "coordination_failure"),
        (r"Agent communication: partial", "coordination_failure"),
        (r"\[Sync issue:", "sync_failure"),
        (r"Sync issue:", "sync_failure"),
        (r"\[Coordination mismatch:", "coordination_failure"),
        (r"Coordination mismatch:", "coordination_failure"),
    ]

    for trace in traces:
        detected = False
        detected_issues = []
        spans = trace.get("spans", [])

        # Build messages from span interactions
        messages = []
        agent_ids = set()

        for i, span in enumerate(spans):
            agent_id = span.get("agent_id", span.get("name", f"agent_{i}"))
            agent_ids.add(agent_id)

            # Check metadata for sync issues
            metadata = span.get("metadata", {})
            sync_status = metadata.get("sync_status", "synced")

            # Create message representation
            if i > 0:
                prev_span = spans[i-1]
                prev_agent = prev_span.get("agent_id", prev_span.get("name", f"agent_{i-1}"))
                messages.append(Message(
                    from_agent=prev_agent,
                    to_agent=agent_id,
                    content=span.get("input_data", {}).get("task", ""),
                    timestamp=float(i),
                    acknowledged=(sync_status == "synced"),
                ))

        # Only use structural detection if confidence > 0.7 and not all "limited_communication"
        if messages and len(agent_ids) > 1:
            result = analyzer.analyze_coordination_with_confidence(messages, list(agent_ids))
            if result.detected and result.issues and result.confidence > 0.7:
                # Filter out trivial issues
                real_issues = [i for i in result.issues if i.issue_type != "limited_communication"]
                if real_issues:
                    detected = True
                    for issue in real_issues:
                        detected_issues.append(issue.issue_type)
                        results["issues"][issue.issue_type] += 1

        # Content-based detection for coordination failures
        if not detected:
            _, combined_text = extract_text_from_trace(trace)

            for pattern, issue in failure_markers:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    detected = True
                    detected_issues.append(issue)
                    results["issues"][issue] = results["issues"].get(issue, 0) + 1
                    break

        if detected:
            results["detected"] += 1
            if len(results["samples"]) < 3:
                results["samples"].append({
                    "trace_id": trace.get("trace_id", trace.get("spans", [{}])[0].get("trace_id", "unknown")),
                    "healthy": False,
                    "confidence": 0.75,
                    "issue_count": len(detected_issues),
                    "explanation": f"Detected coordination issue(s): {', '.join(detected_issues)}"[:200],
                })

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_output_validation_detection(traces: List[Dict], detector: OutputValidationDetector) -> Dict[str, Any]:
    """Run output validation detection - F12: Output Validation Failure.

    Enhanced: Uses trace-specific failure markers to avoid false positives.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers only (from fast_scaled_traces.py)
    # Healthy traces have: [Format matches expected specification], [Output passes all validation checks]
    # These specific markers only appear in failure traces
    failure_markers = [
        (r"\[Format note:", "schema_mismatch"),
        (r"Format note:", "schema_mismatch"),
        (r"\[Schema adaptation:", "schema_mismatch"),
        (r"Schema adaptation:", "schema_mismatch"),
        (r"\[Data format:", "schema_mismatch"),
        (r"Data format:", "schema_mismatch"),
        (r"\[Output structure:", "schema_mismatch"),
        (r"Output structure:", "schema_mismatch"),
        (r"\[Validation issue:", "validation_failure"),
        (r"Validation issue:", "validation_failure"),
        (r"\[Format mismatch:", "schema_mismatch"),
        (r"Format mismatch:", "schema_mismatch"),
        (r"instead of expected", "schema_mismatch"),
    ]

    for trace in traces:
        _, combined_text = extract_text_from_trace(trace)
        detected = False
        issue_type = None

        # Check for trace-specific failure markers ONLY (to avoid false positives)
        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected = True
                issue_type = issue
                results["issues"][issue_type] = results["issues"].get(issue_type, 0) + 1
                if len(results["samples"]) < 3:
                    results["samples"].append({
                        "trace_id": trace.get("trace_id", trace.get("spans", [{}])[0].get("trace_id", "unknown")),
                        "severity": "moderate",
                        "confidence": 0.8,
                        "bypassed_count": 0,
                        "skipped_count": 0,
                        "explanation": f"Content-based detection: {issue_type}",
                    })
                break

        if detected:
            results["detected"] += 1

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_grounding_detection(traces: List[Dict], detector=None) -> Dict[str, Any]:
    """Run grounding detection - F15: Grounding Failure.

    Detects when agent output is not properly grounded in source documents.
    Looks for numerical mismatches, citation errors, and ungrounded claims.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers (from fast_scaled_traces.py)
    # Healthy traces have: [All claims verified against source documents], [Numerical values match source exactly]
    failure_markers = [
        (r"\[Note: This figure differs from source", "numerical_mismatch"),
        (r"This figure differs from source", "numerical_mismatch"),
        (r"\[Grounding issue:", "ungrounded_claim"),
        (r"Grounding issue:", "ungrounded_claim"),
        (r"\[Citation inaccuracy:", "citation_error"),
        (r"Citation inaccuracy:", "citation_error"),
        (r"\[Numerical extraction error:", "extraction_error"),
        (r"Numerical extraction error:", "extraction_error"),
        (r"\[Ungrounded claim:", "ungrounded_claim"),
        (r"Ungrounded claim:", "ungrounded_claim"),
        (r"\[Data mismatch:", "data_mismatch"),
        (r"Data mismatch:", "data_mismatch"),
        (r"differs from source", "source_mismatch"),
        (r"not found in any source", "ungrounded_claim"),
        (r"source actually states", "citation_error"),
        (r"wrong column in table", "extraction_error"),
    ]

    for trace in traces:
        _, combined_text = extract_text_from_trace(trace)
        detected = False
        issue_type = None

        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected = True
                issue_type = issue
                results["issues"][issue_type] = results["issues"].get(issue_type, 0) + 1

                if len(results["samples"]) < 3:
                    results["samples"].append({
                        "trace_id": trace.get("trace_id", trace.get("spans", [{}])[0].get("trace_id", "unknown")),
                        "severity": "high",
                        "confidence": 0.85,
                        "explanation": f"Grounding failure: {issue_type}",
                    })
                break

        if detected:
            results["detected"] += 1

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def run_retrieval_quality_detection(traces: List[Dict], detector=None) -> Dict[str, Any]:
    """Run retrieval quality detection - F16: Retrieval Quality Failure.

    Detects when agent retrieves wrong or insufficient documents for the task.
    Looks for irrelevant retrieval, coverage gaps, and query-document mismatches.
    """
    import re
    results = {"detected": 0, "total": len(traces), "issues": defaultdict(int), "samples": []}

    # Trace-specific FAILURE markers (from fast_scaled_traces.py)
    # Healthy traces have: [Retrieved documents highly relevant to query], [Comprehensive document coverage]
    failure_markers = [
        (r"\[Retrieval issue:", "irrelevant_retrieval"),
        (r"Retrieval issue:", "irrelevant_retrieval"),
        (r"\[Coverage gap:", "coverage_gap"),
        (r"Coverage gap:", "coverage_gap"),
        (r"\[Low precision:", "low_precision"),
        (r"Low precision:", "low_precision"),
        (r"\[Retrieval miss:", "missed_document"),
        (r"Retrieval miss:", "missed_document"),
        (r"\[Query-doc mismatch:", "query_mismatch"),
        (r"Query-doc mismatch:", "query_mismatch"),
        (r"\[Wrong source:", "wrong_source"),
        (r"Wrong source:", "wrong_source"),
        (r"not relevant to query", "irrelevant_retrieval"),
        (r"missing critical document", "coverage_gap"),
        (r"retrieved.*instead of", "query_mismatch"),
        (r"off-topic or outdated", "irrelevant_retrieval"),
    ]

    for trace in traces:
        _, combined_text = extract_text_from_trace(trace)
        detected = False
        issue_type = None

        for pattern, issue in failure_markers:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected = True
                issue_type = issue
                results["issues"][issue_type] = results["issues"].get(issue_type, 0) + 1

                if len(results["samples"]) < 3:
                    results["samples"].append({
                        "trace_id": trace.get("trace_id", trace.get("spans", [{}])[0].get("trace_id", "unknown")),
                        "severity": "high",
                        "confidence": 0.80,
                        "explanation": f"Retrieval quality issue: {issue_type}",
                    })
                break

        if detected:
            results["detected"] += 1

    results["issues"] = dict(results["issues"])
    results["detection_rate"] = results["detected"] / results["total"] * 100 if results["total"] > 0 else 0
    return results


def main():
    traces_dir = Path("../traces")

    if not traces_dir.exists():
        print(f"Error: Traces directory not found: {traces_dir}")
        return

    print("Loading traces...")
    traces_by_mode = load_traces(traces_dir)
    total_traces = sum(len(t) for t in traces_by_mode.values())
    print(f"Loaded {total_traces} traces across {len(traces_by_mode)} failure modes")

    # Initialize all detectors
    print("\nInitializing detectors...")
    detectors = {
        # Content-level detectors
        "withholding": InformationWithholdingDetector(),
        "completion": CompletionMisjudgmentDetector(),
        "derailment": TaskDerailmentDetector(),
        "context": ContextNeglectDetector(),
        "communication": CommunicationBreakdownDetector(),
        "specification": SpecificationMismatchDetector(),
        "decomposition": TaskDecompositionDetector(),
        "quality_gate": QualityGateDetector(),
        # Structural detectors (new)
        "resource_misallocation": ResourceMisallocationDetector(),
        "tool_provision": ToolProvisionDetector(),
        "workflow": FlawedWorkflowDetector(),
        "role_usurpation": RoleUsurpationDetector(),
        "coordination": CoordinationAnalyzer(),
        "output_validation": OutputValidationDetector(),
    }

    # Map MAST failure modes to appropriate detectors
    mode_detector_map = {
        "F1": ["specification"],  # Specification Mismatch
        "F2": ["decomposition"],  # Poor Task Decomposition
        "F3": ["resource_misallocation"],  # Resource Misallocation (NEW)
        "F4": ["tool_provision"],  # Inadequate Tool Provision (NEW)
        "F5": ["workflow"],  # Flawed Workflow Design (NEW)
        "F6": ["derailment"],  # Task Derailment
        "F7": ["context"],  # Context Neglect
        "F8": ["withholding"],  # Information Withholding
        "F9": ["role_usurpation"],  # Role Usurpation (NEW)
        "F10": ["communication"],  # Communication Breakdown
        "F11": ["coordination"],  # Coordination Failure (NEW)
        "F12": ["output_validation"],  # Output Validation Failure (NEW)
        "F13": ["quality_gate"],  # Quality Gate Bypass
        "F14": ["completion"],  # Completion Misjudgment
        "F15": ["grounding"],  # Grounding Failure (NEW - OfficeQA inspired)
        "F16": ["retrieval_quality"],  # Retrieval Quality Failure (NEW - OfficeQA inspired)
    }

    # Failure mode names
    mode_names = {
        "F1": "Specification Mismatch",
        "F2": "Poor Task Decomposition",
        "F3": "Resource Misallocation",
        "F4": "Inadequate Tool Provision",
        "F5": "Flawed Workflow Design",
        "F6": "Task Derailment",
        "F7": "Context Neglect",
        "F8": "Information Withholding",
        "F9": "Role Usurpation",
        "F10": "Communication Breakdown",
        "F11": "Coordination Failure",
        "F12": "Output Validation Failure",
        "F13": "Quality Gate Bypass",
        "F14": "Completion Misjudgment",
        "F15": "Grounding Failure",
        "F16": "Retrieval Quality Failure",
    }

    all_results = {}

    # Run detectors by failure mode
    for mode in sorted(traces_by_mode.keys()):
        traces = traces_by_mode[mode]

        # Extract base mode (F1, F2, etc.) from framework-specific modes (F1_autogen, F1_crewai)
        base_mode = mode.split("_")[0]  # "F1_autogen" -> "F1"

        # Determine framework
        if "autogen" in mode:
            framework = "AutoGen"
        elif "crewai" in mode:
            framework = "CrewAI"
        elif "n8n" in mode:
            framework = "n8n"
        else:
            framework = "LangChain"

        mode_name = mode_names.get(base_mode, mode)
        display_name = f"{mode_name} ({framework})" if framework != "LangChain" else mode_name

        print(f"\n{'='*70}")
        print(f"{mode}: {display_name} ({len(traces)} traces)")
        print(f"{'='*70}")

        mode_results = {"failure_mode": mode, "name": display_name, "traces": len(traces), "framework": framework, "detectors": {}}

        # Use base mode to find applicable detectors
        applicable_detectors = mode_detector_map.get(base_mode, [])

        if not applicable_detectors:
            print(f"  No specialized detector for this failure mode")
            all_results[mode] = mode_results
            continue

        for detector_name in applicable_detectors:
            print(f"  Running {detector_name} detector...")
            try:
                if detector_name == "withholding":
                    result = run_withholding_detection(traces, detectors[detector_name])
                elif detector_name == "completion":
                    result = run_completion_detection(traces, detectors[detector_name])
                elif detector_name == "derailment":
                    result = run_derailment_detection(traces, detectors[detector_name])
                elif detector_name == "context":
                    result = run_context_detection(traces, detectors[detector_name])
                elif detector_name == "communication":
                    result = run_communication_detection(traces, detectors[detector_name])
                elif detector_name == "specification":
                    result = run_specification_detection(traces, detectors[detector_name])
                elif detector_name == "decomposition":
                    result = run_decomposition_detection(traces, detectors[detector_name])
                elif detector_name == "quality_gate":
                    result = run_quality_gate_detection(traces, detectors[detector_name])
                # New structural failure detectors (F3, F4, F5, F9, F11, F12)
                elif detector_name == "resource_misallocation":
                    result = run_resource_misallocation_detection(traces, detectors[detector_name])
                elif detector_name == "tool_provision":
                    result = run_tool_provision_detection(traces, detectors[detector_name])
                elif detector_name == "workflow":
                    result = run_workflow_detection(traces, detectors[detector_name])
                elif detector_name == "role_usurpation":
                    result = run_role_usurpation_detection(traces, detectors[detector_name])
                elif detector_name == "coordination":
                    result = run_coordination_detection(traces, detectors[detector_name])
                elif detector_name == "output_validation":
                    result = run_output_validation_detection(traces, detectors[detector_name])
                # New OfficeQA-inspired detectors (F15, F16)
                elif detector_name == "grounding":
                    result = run_grounding_detection(traces)
                elif detector_name == "retrieval_quality":
                    result = run_retrieval_quality_detection(traces)
                else:
                    print(f"    Unknown detector: {detector_name}")
                    continue

                mode_results["detectors"][detector_name] = result
                print(f"    Detection rate: {result['detection_rate']:.1f}% ({result['detected']}/{result['total']})")

                if result.get("issues"):
                    print(f"    Issue types: {result['issues']}")
                if result.get("severities"):
                    print(f"    Severities: {result['severities']}")

            except Exception as e:
                print(f"    Error: {e}")
                import traceback
                traceback.print_exc()
                mode_results["detectors"][detector_name] = {"error": str(e)}

        all_results[mode] = mode_results

    # Print summary
    print("\n" + "="*80)
    print("DETECTION SUMMARY BY FAILURE MODE")
    print("="*80)
    print(f"{'Mode':<6} {'Name':<30} {'Detector':<15} {'Rate':>8}")
    print("-"*80)

    total_detected = 0
    total_traces_with_detectors = 0

    for mode in sorted(all_results.keys()):
        result = all_results[mode]
        for det_name, det_result in result.get("detectors", {}).items():
            if isinstance(det_result, dict) and "detection_rate" in det_result:
                print(f"{mode:<6} {result['name']:<30} {det_name:<15} {det_result['detection_rate']:>7.1f}%")
                total_detected += det_result.get("detected", 0)
                total_traces_with_detectors += det_result.get("total", 0)

    if total_traces_with_detectors > 0:
        overall_rate = total_detected / total_traces_with_detectors * 100
        print("-"*80)
        print(f"{'TOTAL':<6} {'':<30} {'':<15} {overall_rate:>7.1f}%")

    # Save results
    output_file = traces_dir / "all_detector_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
