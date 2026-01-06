"""Run semantic detection on workflow traces."""

import asyncio
import json
import os
from collections import defaultdict
from pathlib import Path

from anthropic import AsyncAnthropic


# Detection prompts for workflow-specific failure modes
WORKFLOW_DETECTION_PROMPTS = {
    "F5": {
        "name": "Flawed Workflow Design",
        "description": "Missing error handling, retries, or recovery patterns",
        "detection_prompt": """Analyze this multi-agent workflow trace for flawed workflow design.

Workflow Information:
- Workflow type: {workflow_type}
- Task: {task}
- Retry count: {retry_count}
- Used fallback: {used_fallback}
- Errors encountered: {errors}

Agent outputs and flow:
{agent_outputs}

Consider:
1. Were errors properly handled with retries?
2. Was fallback logic triggered when needed?
3. Are there unhandled error conditions?
4. Does the workflow recover gracefully from failures?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F11": {
        "name": "Coordination Failure",
        "description": "Race conditions, timing issues, or handoff failures",
        "detection_prompt": """Analyze this multi-agent workflow trace for coordination failures.

Workflow Information:
- Workflow type: {workflow_type}
- Task: {task}
- Span count: {span_count}
- Validation checkpoints: {validation_checkpoints}

Agent activities:
{agent_outputs}

Consider:
1. Are agents working in proper sequence?
2. Are there synchronization issues or race conditions?
3. Do validation steps happen at the right time?
4. Are handoffs between agents clean?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F13": {
        "name": "Quality Gate Bypass",
        "description": "Validation or approval steps were skipped",
        "detection_prompt": """Analyze this multi-agent workflow trace for quality gate bypass.

Workflow Information:
- Workflow type: {workflow_type}
- Task: {task}
- Gates skipped: {gates_skipped}
- Validation checkpoints: {validation_checkpoints}

Validation and gate status:
{validation_outputs}

ONLY flag as failure (is_failure: true) if ONE of these is clearly true:
1. Gates explicitly marked as "SKIPPED" in the validation outputs
2. The gates_skipped field is true
3. Validation was explicitly bypassed (output contains "bypassed", "skipped", or "disabled")

DO NOT flag as failure if:
- Validation outputs are truncated or incomplete (this is a display issue)
- All gates show "PASSED" status
- Validation was performed even if content was brief
- The workflow completed normally with all checkpoints executed

BE VERY CONSERVATIVE. Default to is_failure: false unless gates were explicitly skipped.

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F14": {
        "name": "Completion Misjudgment",
        "description": "Task marked complete when actually incomplete",
        "detection_prompt": """Analyze this multi-agent workflow trace for premature completion claims.

Workflow Information:
- Workflow type: {workflow_type}
- Task: {task}
- Final status: {final_status}
- Errors encountered: {errors}
- Used fallback: {used_fallback}

Agent outputs:
{agent_outputs}

Consider:
1. Does the final status accurately reflect the work done?
2. Were there unresolved errors when marked complete?
3. Is the output actually complete given the task requirements?
4. Did the workflow claim success despite partial results?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
}


class WorkflowDetector:
    """Detect failures in workflow traces using semantic analysis."""

    def __init__(self, api_key: str = None):
        self.client = AsyncAnthropic(api_key=api_key)

    def _load_workflow_traces(self, trace_file: Path) -> list[dict]:
        """Load and reconstruct traces from JSONL file."""
        traces_by_id = defaultdict(lambda: {"spans": [], "metadata": {}})

        with open(trace_file) as f:
            for line in f:
                span = json.loads(line)
                trace_id = span["trace_id"]
                traces_by_id[trace_id]["spans"].append(span)

                # Extract metadata from root span
                if span.get("parent_id") is None:
                    traces_by_id[trace_id]["metadata"] = {
                        "workflow_type": span.get("workflow_type"),
                        "task": span.get("input_data", {}).get("task"),
                        "requirements": span.get("input_data", {}).get("requirements"),
                        "context": span.get("input_data", {}).get("context"),
                        "final_status": span.get("output_data", {}).get("final_status"),
                        "gates_skipped": span.get("gates_skipped", False),
                        "validation_checkpoints": span.get("validation_checkpoints", 0),
                        "total_retries": span.get("total_retries", 0),
                        "used_fallback": span.get("used_fallback", False),
                        "errors_encountered": span.get("errors_encountered", 0),
                        "failure_mode": span.get("metadata", {}).get("failure_mode"),
                        "failure_injected": span.get("metadata", {}).get("failure_injected", False),
                    }

                # Also get from trace metadata
                if "_trace_metadata" in span:
                    if not traces_by_id[trace_id]["metadata"].get("failure_mode"):
                        traces_by_id[trace_id]["metadata"]["failure_mode"] = span["_trace_metadata"].get("failure_mode")
                    if not traces_by_id[trace_id]["metadata"].get("workflow_type"):
                        traces_by_id[trace_id]["metadata"]["workflow_type"] = span["_trace_metadata"].get("workflow_type")

        return [
            {
                "trace_id": trace_id,
                "spans": data["spans"],
                **data["metadata"],
            }
            for trace_id, data in traces_by_id.items()
        ]

    def _extract_agent_outputs(self, trace: dict) -> str:
        """Extract agent outputs from trace spans."""
        outputs = []
        for span in sorted(trace["spans"], key=lambda s: s.get("start_time", "")):
            span_type = span.get("span_type", "")
            name = span.get("name", "")
            status = span.get("status", "")
            output_data = span.get("output_data", {})

            if span_type == "agent":
                result = output_data.get("result", output_data.get("content", output_data.get("research", "")))
                outputs.append(f"[{name}] ({status}): {str(result)[:200]}")
            elif span_type == "tool_call":
                tool_status = span.get("tool_status", status)
                outputs.append(f"[TOOL:{span.get('tool_name', name)}] ({tool_status}): {output_data.get('result', '')}")
            elif span_type == "retry":
                outputs.append(f"[RETRY] Attempt {span.get('retry_count', '?')}: {output_data.get('decision', '')}")

        return "\n".join(outputs) if outputs else "No agent outputs found"

    def _extract_validation_outputs(self, trace: dict) -> str:
        """Extract validation-specific outputs from trace spans."""
        outputs = []
        for span in sorted(trace["spans"], key=lambda s: s.get("start_time", "")):
            span_type = span.get("span_type", "")
            name = span.get("name", "")

            if span_type == "validation":
                gate_skipped = span.get("gate_skipped", False)
                gate_passed = span.get("gate_passed", True)
                status = "SKIPPED" if gate_skipped else ("PASSED" if gate_passed else "FAILED")
                result = span.get("output_data", {}).get("result", "")
                outputs.append(f"[{name}] {status}: {str(result)[:150]}")

        return "\n".join(outputs) if outputs else "No validation checkpoints found"

    async def analyze_trace(
        self,
        trace: dict,
        failure_mode: str,
    ) -> dict:
        """Analyze a single trace for a specific failure mode."""

        if failure_mode not in WORKFLOW_DETECTION_PROMPTS:
            return {"error": f"Unknown failure mode: {failure_mode}"}

        prompt_template = WORKFLOW_DETECTION_PROMPTS[failure_mode]["detection_prompt"]

        # Prepare context for the prompt
        agent_outputs = self._extract_agent_outputs(trace)
        validation_outputs = self._extract_validation_outputs(trace)

        # Build errors list from spans
        errors = []
        for span in trace["spans"]:
            if span.get("status") == "error":
                errors.append(span.get("error", f"Error in {span.get('name')}"))
            if span.get("errors"):
                errors.extend(span.get("errors", []))

        prompt = prompt_template.format(
            workflow_type=trace.get("workflow_type", "unknown"),
            task=trace.get("task", trace.get("requirements", "unknown task")),
            retry_count=trace.get("total_retries", 0),
            used_fallback=trace.get("used_fallback", False),
            errors=errors[:5] if errors else "None",
            agent_outputs=agent_outputs[:2000],
            span_count=len(trace.get("spans", [])),
            validation_checkpoints=trace.get("validation_checkpoints", 0),
            gates_skipped=trace.get("gates_skipped", False),
            validation_outputs=validation_outputs[:1500],
            final_status=trace.get("final_status", "unknown"),
        )

        try:
            response = await self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )

            result_text = response.content[0].text

            # Parse JSON response
            import re
            json_match = re.search(r'\{[^}]+\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "detected_failure": result.get("is_failure", False),
                    "confidence": result.get("confidence", 0.0),
                    "reason": result.get("reason", ""),
                }
            else:
                return {"error": f"Could not parse response: {result_text[:100]}"}

        except Exception as e:
            return {"error": str(e)}

    async def evaluate_workflow_traces(
        self,
        trace_file: Path,
        concurrency: int = 10,
    ) -> dict:
        """Evaluate all workflow traces and compute metrics."""

        traces = self._load_workflow_traces(trace_file)
        print(f"Loaded {len(traces)} traces from {trace_file}")

        results = {
            "by_mode": defaultdict(lambda: {
                "total": 0,
                "true_positives": 0,
                "false_positives": 0,
                "true_negatives": 0,
                "false_negatives": 0,
                "details": [],
            }),
            "by_workflow": defaultdict(lambda: {"total": 0, "detected": 0}),
        }

        semaphore = asyncio.Semaphore(concurrency)

        async def analyze_with_semaphore(trace: dict, target_mode: str):
            async with semaphore:
                return await self.analyze_trace(trace, target_mode)

        # Analyze each trace for its expected failure mode
        tasks = []
        trace_info = []

        for trace in traces:
            expected_mode = trace.get("failure_mode")
            workflow_type = trace.get("workflow_type", "unknown")

            # Determine which mode to test for
            if expected_mode in WORKFLOW_DETECTION_PROMPTS:
                target_mode = expected_mode
            elif workflow_type == "pipeline":
                target_mode = "F13"  # Pipeline primarily tests F13
            else:
                target_mode = "F5"  # Recovery primarily tests F5

            tasks.append(analyze_with_semaphore(trace, target_mode))
            trace_info.append({
                "trace_id": trace["trace_id"],
                "expected_mode": expected_mode,
                "target_mode": target_mode,
                "workflow_type": workflow_type,
                "is_actually_failure": expected_mode is not None,
            })

        print(f"Analyzing {len(tasks)} traces...")
        analysis_results = await asyncio.gather(*tasks)

        # Compile results
        for info, result in zip(trace_info, analysis_results):
            mode = info["target_mode"]
            workflow = info["workflow_type"]
            is_failure = info["is_actually_failure"]

            results["by_workflow"][workflow]["total"] += 1

            if "error" in result:
                continue

            detected = result.get("detected_failure", False)
            results["by_mode"][mode]["total"] += 1

            if detected:
                results["by_workflow"][workflow]["detected"] += 1

            # Compute TP/FP/TN/FN
            if is_failure and detected:
                results["by_mode"][mode]["true_positives"] += 1
            elif is_failure and not detected:
                results["by_mode"][mode]["false_negatives"] += 1
            elif not is_failure and detected:
                results["by_mode"][mode]["false_positives"] += 1
            else:
                results["by_mode"][mode]["true_negatives"] += 1

            results["by_mode"][mode]["details"].append({
                "trace_id": info["trace_id"],
                "workflow_type": workflow,
                "expected_failure": is_failure,
                "detected_failure": detected,
                "confidence": result.get("confidence", 0),
                "reason": result.get("reason", ""),
            })

        # Compute metrics for each mode
        for mode, data in results["by_mode"].items():
            tp = data["true_positives"]
            fp = data["false_positives"]
            tn = data["true_negatives"]
            fn = data["false_negatives"]

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

            data["precision"] = precision
            data["recall"] = recall
            data["f1"] = f1
            data["fpr"] = fpr

        return dict(results)


async def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    detector = WorkflowDetector(api_key=api_key)

    trace_file = Path("../traces/workflow_traces.jsonl")
    results = await detector.evaluate_workflow_traces(trace_file, concurrency=10)

    # Print results
    print("\n" + "="*70)
    print("WORKFLOW TRACE DETECTION RESULTS")
    print("="*70)

    print("\n--- By Failure Mode ---")
    for mode, data in sorted(results["by_mode"].items()):
        print(f"\n{mode}: {WORKFLOW_DETECTION_PROMPTS.get(mode, {}).get('name', 'Unknown')}")
        print(f"  Total: {data['total']}")
        print(f"  TP: {data['true_positives']}, FP: {data['false_positives']}, TN: {data['true_negatives']}, FN: {data['false_negatives']}")
        print(f"  Precision: {data['precision']:.1%}")
        print(f"  Recall: {data['recall']:.1%}")
        print(f"  F1: {data['f1']:.1%}")
        print(f"  FPR: {data['fpr']:.1%}")

    print("\n--- By Workflow Type ---")
    for workflow, data in results["by_workflow"].items():
        print(f"  {workflow}: {data['total']} traces, {data['detected']} detected as failures")

    # Save results
    output_file = Path("../traces/workflow_detection_results.json")
    with open(output_file, "w") as f:
        # Convert defaultdict to dict for JSON serialization
        json.dump({
            "by_mode": {k: dict(v) for k, v in results["by_mode"].items()},
            "by_workflow": dict(results["by_workflow"]),
        }, f, indent=2)
    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
