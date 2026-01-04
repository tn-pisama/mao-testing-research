"""Semantic detector using LLM to analyze if traces exhibit failure modes.

Unlike pattern-matching detectors, this actually:
1. Understands the task intent
2. Analyzes what the agent actually produced
3. Determines if there's a semantic mismatch
"""

import asyncio
import json
from pathlib import Path
from typing import Literal
from collections import defaultdict

from anthropic import AsyncAnthropic


FAILURE_MODE_DESCRIPTIONS = {
    "F1": {
        "name": "Specification Mismatch",
        "description": "The agent produces output that doesn't match what was requested",
        "detection_prompt": """Analyze if the agent's output matches the task specification.

Task requested: {task}
Agent output: {output}

Consider:
1. Does the output address what was actually asked for?
2. Is the format/type correct (e.g., Python vs JavaScript, summary vs full article)?
3. Are the requirements met?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F6": {
        "name": "Task Derailment",
        "description": "The agent goes off-topic or addresses something other than the assigned task",
        "detection_prompt": """Analyze if the agent stayed on topic or derailed.

Original task: {task}
Agent output: {output}

Consider:
1. Is the output about the original task?
2. Did the agent drift to unrelated topics?
3. Is there scope creep or tangential exploration?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F14": {
        "name": "Completion Misjudgment",
        "description": "The agent declares completion when the task is actually incomplete",
        "detection_prompt": """Analyze if the agent completed the task fully or only partially.

Task requested: {task}
Agent output: {output}

Consider:
1. Are all parts of the task addressed?
2. Is anything obviously missing or incomplete?
3. Did the agent do a thorough job or just the minimum?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F7": {
        "name": "Context Neglect",
        "description": "The agent ignores important context or prior information",
        "detection_prompt": """Analyze if the agent properly used context when context was EXPLICITLY provided.

Task: {task}
Agent output: {output}

IMPORTANT: Only flag as failure if:
1. The task EXPLICITLY mentions prior context (e.g., "continue from...", "based on previous...", "update existing...")
2. AND the agent clearly ignored that specific context

Do NOT flag as failure if:
- The task is standalone with no mention of prior context
- The agent produced a reasonable output for a fresh task
- The output is generic but the task didn't require specific context

Default to is_failure: false unless there's clear evidence of context being ignored.

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F8": {
        "name": "Information Withholding",
        "description": "The agent omits important information from its output",
        "detection_prompt": """Analyze if the agent deliberately withheld critical information.

Task requested: {task}
Agent output: {output}

IMPORTANT: Only flag as failure if:
1. The task explicitly asked for COMPLETE/ALL information (e.g., "list ALL", "report ALL", "complete logs")
2. AND the agent clearly omitted significant portions that were specifically requested

Do NOT flag as failure if:
- Output appears truncated but contains the essential information
- The agent provided a reasonable summary when not asked for exhaustive detail
- Minor details are missing but core content is present
- The output is concise but addresses the main request

Brevity is NOT the same as withholding. Default to is_failure: false unless critical information was clearly omitted.

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F2": {
        "name": "Poor Task Decomposition",
        "description": "The agent fails to properly break down a complex task",
        "detection_prompt": """Analyze if the agent properly decomposed the task.

Complex task: {task}
Agent approach: {output}

Consider:
1. Did the agent identify subtasks for a complex task?
2. Is the approach systematic or ad-hoc?
3. Are dependencies between parts identified?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F3": {
        "name": "Resource Misallocation",
        "description": "The agent uses resources inefficiently",
        "detection_prompt": """Analyze if the agent used resources appropriately.

Task: {task}
Agent approach: {output}

Consider:
1. Is the approach efficient or wasteful?
2. Are there obvious resource problems (memory, time, etc.)?
3. Would the approach scale or fail under load?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F4": {
        "name": "Inadequate Tool Provision",
        "description": "The agent lacks or misuses necessary tools",
        "detection_prompt": """Analyze if the agent had and used appropriate tools.

Task requiring tools: {task}
Agent output: {output}

Consider:
1. Did the agent use appropriate tools for the task?
2. Were workarounds used when proper tools exist?
3. Did tool limitations affect the output?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F5": {
        "name": "Flawed Workflow Design",
        "description": "The workflow has missing error handling or edge cases",
        "detection_prompt": """Analyze if the agent's workflow handles edge cases.

Task with potential edge cases: {task}
Agent workflow/output: {output}

Consider:
1. Are error conditions handled?
2. What happens with invalid input?
3. Is there retry/fallback logic where needed?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F9": {
        "name": "Role Usurpation",
        "description": "The agent exceeds its designated role",
        "detection_prompt": """Analyze if the agent stayed within its designated role.

Agent role and task: {task}
Agent output: {output}

Consider:
1. Did the agent stay within its role boundaries?
2. Did it make decisions it shouldn't make?
3. Did it modify things it should only report on?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F10": {
        "name": "Communication Breakdown",
        "description": "Agents fail to communicate effectively",
        "detection_prompt": """Analyze if there are communication issues between agents.

Task involving communication: {task}
Agent outputs: {output}

Consider:
1. Is information passed clearly between agents?
2. Are messages understandable and actionable?
3. Is there information loss in handoffs?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F11": {
        "name": "Coordination Failure",
        "description": "Agents fail to coordinate their activities",
        "detection_prompt": """Analyze if there are coordination issues.

Task requiring coordination: {task}
Agent activities: {output}

Consider:
1. Are agents working on the same thing redundantly?
2. Are there synchronization issues?
3. Do handoffs happen at the right time?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F12": {
        "name": "Output Validation Failure",
        "description": "The output doesn't meet format/schema requirements",
        "detection_prompt": """Analyze if the output has a FUNDAMENTAL format violation.

Task: {task}
Agent output: {output}

ONLY flag as failure (is_failure: true) if ONE of these is clearly true:
1. WRONG FORMAT TYPE: Task asked for format X but got format Y (e.g., asked for CSV, got JSON)
2. COMPLETELY BROKEN: Output has syntax errors making it unusable (e.g., unclosed braces, invalid JSON)
3. WRONG SPECIFICATION: Output violates explicit format requirements (e.g., asked for ISO 8601 date YYYY-MM-DD, got MM/DD/YYYY)

ALWAYS mark as SUCCESS (is_failure: false) if:
- Output appears truncated/cut off but structure is valid (truncation is display issue, not failure)
- Format is correct even with minor variations (extra fields, whitespace, naming)
- Output is parseable and matches requested format type
- No explicit format specification was violated

BE VERY CONSERVATIVE. If unsure, default to is_failure: false.
Most outputs that look reasonable are NOT failures.

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F13": {
        "name": "Quality Gate Bypass",
        "description": "The agent skips required validation or approval steps",
        "detection_prompt": """Analyze if quality gates were properly followed.

Task with quality requirements: {task}
Agent behavior: {output}

Consider:
1. Were validation steps completed?
2. Were approvals obtained when needed?
3. Were any quality checks skipped?

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F15": {
        "name": "Grounding Failure",
        "description": "Agent output contains claims not supported by source documents",
        "detection_prompt": """Analyze if the agent's output is properly grounded in source documents.

Task: {task}
Agent output: {output}

Consider:
1. Does the output make factual claims? If so, are they supported by context/sources mentioned?
2. Are any numbers/statistics in the output consistent with what sources would contain?
3. Are there citations or references? Do they accurately reflect what sources would say?
4. Does the output contradict any information that appears to come from sources?

IMPORTANT: Only flag as failure if:
- The output makes specific factual claims that contradict or misrepresent sources
- Numbers/dates/names are clearly incorrect compared to source context
- Citations or quotes misrepresent source content
- Agent claims data from a source but the data doesn't match

Do NOT flag if:
- The output is a reasonable summary/synthesis
- Minor paraphrasing that preserves meaning
- No sources were explicitly referenced (can't verify grounding)
- Output contains reasonable inferences from available context

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
    "F16": {
        "name": "Retrieval Quality Failure",
        "description": "Agent retrieved wrong or insufficient documents for the task",
        "detection_prompt": """Analyze if the agent retrieved appropriate documents for the task.

Task/Query: {task}
Agent output: {output}

Consider:
1. Does the output reference retrieving or searching for documents?
2. Are the retrieved/referenced documents relevant to the task?
3. Does the output show signs of missing critical information that should be available?
4. Is there evidence the agent looked in the wrong place or got irrelevant results?

IMPORTANT: Only flag as failure if:
- Output explicitly mentions retrieving documents that are clearly irrelevant
- Output shows signs of missing critical information due to poor retrieval
- Agent searched wrong time period, wrong topic, or wrong source
- Retrieval results are mentioned as unhelpful or off-topic

Do NOT flag if:
- No explicit retrieval was mentioned or needed
- Documents seem reasonably relevant even if not perfect
- Limited retrieval but covers the essential info
- No clear evidence of retrieval problems

Respond with JSON: {{"is_failure": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    },
}


class SemanticDetector:
    """Detect failures using semantic analysis with LLM."""

    def __init__(self, api_key: str = None):
        self.client = AsyncAnthropic(api_key=api_key)

    def _extract_text_from_trace(self, trace: dict) -> tuple[str, str]:
        """Extract task and combined output from trace."""
        task = ""
        output = ""

        for span in trace.get("spans", []):
            input_data = span.get("input_data", {})
            output_data = span.get("output_data", {})

            if isinstance(input_data, dict):
                if "task" in input_data and not task:
                    task = input_data["task"]

            if isinstance(output_data, dict):
                for key in ["result", "document", "content", "response", "output"]:
                    if key in output_data:
                        output += " " + str(output_data[key])

        # Also check top-level scenario
        if not task:
            task = trace.get("scenario", "")

        return task.strip(), output.strip()

    async def analyze_trace(
        self,
        trace: dict,
        failure_mode: str,
    ) -> dict:
        """Analyze a single trace for a specific failure mode."""

        task, output = self._extract_text_from_trace(trace)

        if not task or not output:
            return {
                "is_failure": False,
                "confidence": 0.0,
                "reason": "Could not extract task or output",
                "error": True,
            }

        mode_info = FAILURE_MODE_DESCRIPTIONS.get(failure_mode)
        if not mode_info:
            return {
                "is_failure": False,
                "confidence": 0.0,
                "reason": f"Unknown failure mode: {failure_mode}",
                "error": True,
            }

        prompt = mode_info["detection_prompt"].format(
            task=task[:500],
            output=output[:1000],
        )

        try:
            response = await self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON response
            text = response.content[0].text
            # Find JSON in response
            import re
            json_match = re.search(r'\{[^}]+\}', text)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "is_failure": result.get("is_failure", False),
                    "confidence": result.get("confidence", 0.5),
                    "reason": result.get("reason", ""),
                    "error": False,
                }
            else:
                return {
                    "is_failure": False,
                    "confidence": 0.0,
                    "reason": f"Could not parse response: {text[:100]}",
                    "error": True,
                }
        except Exception as e:
            return {
                "is_failure": False,
                "confidence": 0.0,
                "reason": f"API error: {e}",
                "error": True,
            }

    async def evaluate_traces(
        self,
        traces: list[dict],
        failure_mode: str,
        concurrency: int = 5,
    ) -> dict:
        """Evaluate a batch of traces."""

        results = {
            "total": len(traces),
            "detected_failures": 0,
            "true_positives": 0,
            "false_positives": 0,
            "true_negatives": 0,
            "false_negatives": 0,
            "errors": 0,
            "details": [],
        }

        # Process in batches for rate limiting
        semaphore = asyncio.Semaphore(concurrency)

        async def analyze_with_limit(trace):
            async with semaphore:
                return await self.analyze_trace(trace, failure_mode)

        # Analyze all traces
        tasks = [analyze_with_limit(trace) for trace in traces]
        analyses = await asyncio.gather(*tasks)

        for trace, analysis in zip(traces, analyses):
            is_actually_failure = not trace.get("is_healthy", True)
            detected_failure = analysis.get("is_failure", False)

            if analysis.get("error"):
                results["errors"] += 1
                continue

            if detected_failure:
                results["detected_failures"] += 1

            if is_actually_failure and detected_failure:
                results["true_positives"] += 1
            elif is_actually_failure and not detected_failure:
                results["false_negatives"] += 1
            elif not is_actually_failure and detected_failure:
                results["false_positives"] += 1
            else:
                results["true_negatives"] += 1

            results["details"].append({
                "trace_id": trace.get("trace_id"),
                "is_actually_failure": is_actually_failure,
                "detected_failure": detected_failure,
                "confidence": analysis.get("confidence"),
                "reason": analysis.get("reason"),
            })

        # Calculate metrics
        tp = results["true_positives"]
        fp = results["false_positives"]
        tn = results["true_negatives"]
        fn = results["false_negatives"]

        results["precision"] = tp / (tp + fp) if (tp + fp) > 0 else 0
        results["recall"] = tp / (tp + fn) if (tp + fn) > 0 else 0
        results["f1"] = (
            2 * results["precision"] * results["recall"] /
            (results["precision"] + results["recall"])
            if (results["precision"] + results["recall"]) > 0 else 0
        )
        results["accuracy"] = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
        results["fpr"] = fp / (fp + tn) if (fp + tn) > 0 else 0

        return results


async def evaluate_on_semantic_traces(api_key: str, traces_file: Path) -> dict:
    """Evaluate semantic detector on semantic traces."""

    detector = SemanticDetector(api_key=api_key)

    # Load traces
    traces = []
    with open(traces_file) as f:
        for line in f:
            if line.strip():
                traces.append(json.loads(line))

    print(f"Loaded {len(traces)} traces from {traces_file}")

    # Group by failure mode
    by_mode = defaultdict(list)
    for trace in traces:
        by_mode[trace["failure_mode"]].append(trace)

    all_results = {}

    for mode, mode_traces in sorted(by_mode.items()):
        print(f"\nEvaluating {mode} ({len(mode_traces)} traces)...")
        results = await detector.evaluate_traces(mode_traces, mode)
        all_results[mode] = results

        print(f"  Precision: {results['precision']*100:.1f}%")
        print(f"  Recall: {results['recall']*100:.1f}%")
        print(f"  F1: {results['f1']*100:.1f}%")
        print(f"  FPR: {results['fpr']*100:.1f}%")
        print(f"  Errors: {results['errors']}")

    return all_results


async def main():
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    traces_file = Path("traces/semantic/langchain_semantic_traces.jsonl")

    if not traces_file.exists():
        print(f"Traces file not found: {traces_file}")
        print("Run semantic_trace_generator.py first")
        return

    results = await evaluate_on_semantic_traces(api_key, traces_file)

    # Save results
    output_file = Path("traces/semantic/semantic_evaluation_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
