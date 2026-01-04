"""Universal feature extraction for multi-agent trace analysis.

Extracts framework-agnostic structural and behavioral features that can be
used for training and detection without overfitting to framework-specific patterns.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


class TraceFeatureExtractor:
    """Extract universal features from multi-agent traces."""

    def __init__(self):
        # Semantic categories for output analysis
        self.completion_indicators = [
            "complete", "completed", "done", "finished", "success",
            "passed", "approved", "valid", "verified"
        ]
        self.failure_indicators = [
            "failed", "error", "invalid", "rejected", "missing",
            "incomplete", "timeout", "unavailable"
        ]
        self.uncertainty_indicators = [
            "maybe", "perhaps", "might", "could", "possibly",
            "approximately", "estimated", "unclear", "uncertain"
        ]
        self.delegation_indicators = [
            "delegat", "handoff", "pass to", "forward to", "assign",
            "route to", "transfer"
        ]

    def extract_structural_features(self, trace: dict) -> dict:
        """Extract structural features from trace topology."""
        spans = trace.get("spans", [])

        if not spans:
            return self._empty_structural_features()

        # Build span hierarchy
        span_by_id = {s["span_id"]: s for s in spans}
        children_map = defaultdict(list)
        root_spans = []

        for span in spans:
            parent_id = span.get("parent_id")
            if parent_id and parent_id in span_by_id:
                children_map[parent_id].append(span["span_id"])
            elif parent_id is None:
                root_spans.append(span["span_id"])

        # Calculate depth
        def get_depth(span_id: str, memo: dict = None) -> int:
            if memo is None:
                memo = {}
            if span_id in memo:
                return memo[span_id]
            children = children_map.get(span_id, [])
            if not children:
                memo[span_id] = 0
            else:
                memo[span_id] = 1 + max(get_depth(c, memo) for c in children)
            return memo[span_id]

        max_depth = max((get_depth(r) for r in root_spans), default=0)

        # Calculate branching factor
        branching_factors = [len(children) for children in children_map.values() if children]
        avg_branching = sum(branching_factors) / len(branching_factors) if branching_factors else 0
        max_branching = max(branching_factors) if branching_factors else 0

        # Agent analysis
        agents = set()
        agent_counts = Counter()
        span_types = Counter()

        for span in spans:
            agent_id = span.get("agent_id", "unknown")
            agents.add(agent_id)
            agent_counts[agent_id] += 1
            span_types[span.get("span_type", "unknown")] += 1

        # Duration analysis
        durations = [s.get("duration_ms", 0) for s in spans if s.get("duration_ms")]
        total_duration = sum(durations)
        avg_duration = total_duration / len(durations) if durations else 0
        max_duration = max(durations) if durations else 0

        return {
            "span_count": len(spans),
            "unique_agents": len(agents),
            "max_depth": max_depth,
            "avg_branching_factor": round(avg_branching, 2),
            "max_branching_factor": max_branching,
            "total_duration_ms": total_duration,
            "avg_span_duration_ms": round(avg_duration, 2),
            "max_span_duration_ms": max_duration,
            "span_type_counts": dict(span_types),
            "agent_span_counts": dict(agent_counts),
            "has_parallel_execution": max_branching > 1,
            "root_span_count": len(root_spans),
        }

    def _empty_structural_features(self) -> dict:
        """Return empty structural features for empty traces."""
        return {
            "span_count": 0,
            "unique_agents": 0,
            "max_depth": 0,
            "avg_branching_factor": 0,
            "max_branching_factor": 0,
            "total_duration_ms": 0,
            "avg_span_duration_ms": 0,
            "max_span_duration_ms": 0,
            "span_type_counts": {},
            "agent_span_counts": {},
            "has_parallel_execution": False,
            "root_span_count": 0,
        }

    def extract_behavioral_features(self, trace: dict) -> dict:
        """Extract behavioral patterns from span outputs and interactions."""
        spans = trace.get("spans", [])

        if not spans:
            return self._empty_behavioral_features()

        # Collect all output text
        outputs = []
        for span in spans:
            output_data = span.get("output_data", {})
            if isinstance(output_data, dict):
                for key, value in output_data.items():
                    if isinstance(value, str):
                        outputs.append(value.lower())
            elif isinstance(output_data, str):
                outputs.append(output_data.lower())

        combined_output = " ".join(outputs)

        # Semantic indicator counts
        completion_score = sum(1 for ind in self.completion_indicators if ind in combined_output)
        failure_score = sum(1 for ind in self.failure_indicators if ind in combined_output)
        uncertainty_score = sum(1 for ind in self.uncertainty_indicators if ind in combined_output)
        delegation_score = sum(1 for ind in self.delegation_indicators if ind in combined_output)

        # Tool usage analysis
        tool_calls = []
        tool_success_count = 0
        tool_failure_count = 0

        for span in spans:
            span_tools = span.get("tool_calls", [])
            for tool in span_tools:
                tool_calls.append(tool.get("name", "unknown"))
                status = tool.get("status", "").lower()
                if status in ["success", "ok"]:
                    tool_success_count += 1
                elif status in ["error", "failed", "timeout"]:
                    tool_failure_count += 1

        # Status analysis
        status_counts = Counter(s.get("status", "unknown") for s in spans)
        error_rate = status_counts.get("error", 0) / len(spans) if spans else 0
        retry_count = sum(s.get("retry_count", 0) for s in spans)

        # Input/output size analysis
        input_sizes = []
        output_sizes = []

        for span in spans:
            input_data = span.get("input_data", {})
            output_data = span.get("output_data", {})
            input_sizes.append(len(json.dumps(input_data)) if input_data else 0)
            output_sizes.append(len(json.dumps(output_data)) if output_data else 0)

        avg_input_size = sum(input_sizes) / len(input_sizes) if input_sizes else 0
        avg_output_size = sum(output_sizes) / len(output_sizes) if output_sizes else 0

        # Calculate info preservation ratio (output/input size ratio)
        total_input = sum(input_sizes)
        total_output = sum(output_sizes)
        info_ratio = total_output / total_input if total_input > 0 else 1.0

        return {
            "completion_score": completion_score,
            "failure_score": failure_score,
            "uncertainty_score": uncertainty_score,
            "delegation_score": delegation_score,
            "tool_call_count": len(tool_calls),
            "unique_tools_used": len(set(tool_calls)),
            "tool_success_rate": tool_success_count / len(tool_calls) if tool_calls else 1.0,
            "tool_failure_rate": tool_failure_count / len(tool_calls) if tool_calls else 0.0,
            "span_error_rate": round(error_rate, 3),
            "total_retries": retry_count,
            "avg_input_size": round(avg_input_size, 2),
            "avg_output_size": round(avg_output_size, 2),
            "info_preservation_ratio": round(info_ratio, 3),
            "status_distribution": dict(status_counts),
        }

    def _empty_behavioral_features(self) -> dict:
        """Return empty behavioral features."""
        return {
            "completion_score": 0,
            "failure_score": 0,
            "uncertainty_score": 0,
            "delegation_score": 0,
            "tool_call_count": 0,
            "unique_tools_used": 0,
            "tool_success_rate": 1.0,
            "tool_failure_rate": 0.0,
            "span_error_rate": 0.0,
            "total_retries": 0,
            "avg_input_size": 0,
            "avg_output_size": 0,
            "info_preservation_ratio": 1.0,
            "status_distribution": {},
        }

    def extract_coordination_features(self, trace: dict) -> dict:
        """Extract inter-agent coordination patterns."""
        spans = trace.get("spans", [])

        if not spans:
            return self._empty_coordination_features()

        # Sort spans by start time
        sorted_spans = sorted(spans, key=lambda s: s.get("start_time", ""))

        # Agent transition analysis
        agent_sequence = [s.get("agent_id", "unknown") for s in sorted_spans]
        transitions = [(agent_sequence[i], agent_sequence[i+1])
                       for i in range(len(agent_sequence) - 1)
                       if agent_sequence[i] != agent_sequence[i+1]]

        # Unique transition types
        unique_transitions = len(set(transitions))
        total_transitions = len(transitions)

        # Self-loops (agent processing multiple times)
        agent_counts = Counter(agent_sequence)
        agents_with_multiple = sum(1 for count in agent_counts.values() if count > 1)

        # Context passing analysis (check if outputs are used as inputs)
        context_pass_count = 0
        for i in range(len(sorted_spans) - 1):
            current_output = sorted_spans[i].get("output_data", {})
            next_input = sorted_spans[i + 1].get("input_data", {})

            if current_output and next_input:
                # Check for reference in input
                current_out_str = json.dumps(current_output)[:100]
                next_in_str = json.dumps(next_input)
                if any(word in next_in_str for word in current_out_str.split()[:5]):
                    context_pass_count += 1

        # Calculate handoff quality score
        handoff_quality = context_pass_count / total_transitions if total_transitions > 0 else 1.0

        return {
            "total_agent_transitions": total_transitions,
            "unique_transition_types": unique_transitions,
            "agents_with_multiple_calls": agents_with_multiple,
            "context_passes": context_pass_count,
            "handoff_quality_score": round(handoff_quality, 3),
            "transition_diversity": unique_transitions / total_transitions if total_transitions > 0 else 0,
        }

    def _empty_coordination_features(self) -> dict:
        """Return empty coordination features."""
        return {
            "total_agent_transitions": 0,
            "unique_transition_types": 0,
            "agents_with_multiple_calls": 0,
            "context_passes": 0,
            "handoff_quality_score": 1.0,
            "transition_diversity": 0,
        }

    def extract_all_features(self, trace: dict) -> dict:
        """Extract all feature categories from a trace."""
        structural = self.extract_structural_features(trace)
        behavioral = self.extract_behavioral_features(trace)
        coordination = self.extract_coordination_features(trace)

        # Combine all features with prefixes
        features = {}
        for key, value in structural.items():
            features[f"struct_{key}"] = value
        for key, value in behavioral.items():
            features[f"behav_{key}"] = value
        for key, value in coordination.items():
            features[f"coord_{key}"] = value

        # Add metadata
        features["metadata_framework"] = trace.get("framework", "unknown")
        features["metadata_failure_mode"] = trace.get("failure_mode", "unknown")
        features["metadata_complexity"] = trace.get("complexity", "unknown")
        features["metadata_is_healthy"] = trace.get("is_healthy", False)

        return features

    def extract_features_from_file(self, file_path: str | Path) -> list[dict]:
        """Extract features from all traces in a JSONL file."""
        file_path = Path(file_path)
        features_list = []

        with open(file_path) as f:
            for line in f:
                if line.strip():
                    trace = json.loads(line)
                    features = self.extract_all_features(trace)
                    features["trace_id"] = trace.get("trace_id", "unknown")
                    features_list.append(features)

        return features_list


def extract_features_for_all_frameworks(
    traces_dir: str = "traces",
    output_file: str = "traces/extracted_features.jsonl",
) -> None:
    """Extract features from all framework trace files."""
    traces_dir = Path(traces_dir)
    extractor = TraceFeatureExtractor()

    all_features = []
    frameworks = ["langchain", "autogen", "crewai", "n8n"]

    print("Extracting universal features from traces...")

    for framework in frameworks:
        # Process failure traces
        failure_file = traces_dir / f"{framework}_scaled_traces.jsonl"
        if failure_file.exists():
            features = extractor.extract_features_from_file(failure_file)
            print(f"  {framework} failure traces: {len(features)} features extracted")
            all_features.extend(features)

        # Process healthy traces
        healthy_file = traces_dir / f"{framework}_healthy_traces.jsonl"
        if healthy_file.exists():
            features = extractor.extract_features_from_file(healthy_file)
            print(f"  {framework} healthy traces: {len(features)} features extracted")
            all_features.extend(features)

    # Save features
    output_path = Path(output_file)
    with open(output_path, "w") as f:
        for features in all_features:
            f.write(json.dumps(features) + "\n")

    print(f"\nSaved {len(all_features)} feature records to {output_path}")

    # Print feature summary
    if all_features:
        sample = all_features[0]
        print(f"\nFeature dimensions: {len([k for k in sample.keys() if not k.startswith('metadata_') and k != 'trace_id'])}")
        print("Feature categories:")
        print(f"  Structural: {len([k for k in sample.keys() if k.startswith('struct_')])}")
        print(f"  Behavioral: {len([k for k in sample.keys() if k.startswith('behav_')])}")
        print(f"  Coordination: {len([k for k in sample.keys() if k.startswith('coord_')])}")


if __name__ == "__main__":
    extract_features_for_all_frameworks()
