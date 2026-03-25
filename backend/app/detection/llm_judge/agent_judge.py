"""Agent-as-Judge: Multi-step evaluation agent with episodic memory and tool access.

Unlike the single-call LLM judge that returns CORRECT/INCORRECT in one shot,
the Agent Judge:
1. Queries episodic memory for similar past cases
2. Runs relevant detectors as tools
3. Reasons with extended thinking (32K token budget)
4. Records its decision for future reference

This closes the competitive gap with Patronus Percival.

Cost: ~$0.03-0.05 per judgment (Sonnet 4-thinking)
Latency: ~3-5 seconds (multi-turn)
Use: Only for ambiguous cases (confidence 0.40-0.70 after rule-based detection)
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Lazy Anthropic client
_client = None


def _get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic
        _client = Anthropic()
    return _client


AGENT_MODEL = "claude-sonnet-4-20250514"


@dataclass
class AgentVerdict:
    """Result of agent-as-judge evaluation."""
    detected: bool
    confidence: float
    reasoning_chain: List[str]  # Step-by-step reasoning
    tools_used: List[str]  # Which tools were called
    memory_context: Dict[str, Any]  # What the agent recalled
    cost_usd: float = 0.0
    tokens_used: int = 0
    latency_ms: int = 0


@dataclass
class PastJudgment:
    """A past judgment stored in episodic memory."""
    detection_type: str
    verdict: bool
    confidence: float
    reasoning_summary: str
    timestamp: str = ""


# ── Tool Definitions for Claude tool_use ──

AGENT_TOOLS = [
    {
        "name": "query_detection_memory",
        "description": "Query the detection memory for baseline rates and recent patterns for a detector type. Returns historical detection rates and common failure patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "detection_type": {"type": "string", "description": "The detector type to query (e.g., 'hallucination', 'loop')"},
            },
            "required": ["detection_type"],
        },
    },
    {
        "name": "run_detector",
        "description": "Run a specific detector on the provided input data. Returns detected (bool) and confidence (float).",
        "input_schema": {
            "type": "object",
            "properties": {
                "detection_type": {"type": "string", "description": "Detector to run"},
                "input_data": {"type": "object", "description": "Input data for the detector"},
            },
            "required": ["detection_type"],
        },
    },
    {
        "name": "find_similar_cases",
        "description": "Find similar past judgments from episodic memory. Returns up to 3 similar cases with their verdicts and reasoning.",
        "input_schema": {
            "type": "object",
            "properties": {
                "detection_type": {"type": "string"},
                "trace_summary": {"type": "string", "description": "Brief summary of the current trace"},
            },
            "required": ["detection_type"],
        },
    },
    {
        "name": "check_source_grounding",
        "description": "Check if a claim is supported by source documents using NLI entailment. Returns entailment label and confidence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string", "description": "The claim to check"},
                "source_text": {"type": "string", "description": "Source document text"},
            },
            "required": ["claim", "source_text"],
        },
    },
]


class AgentJudge:
    """Multi-step evaluation agent with episodic memory and tool access.

    Architecture:
    - Uses Claude Sonnet 4 with extended thinking for deep reasoning
    - 4 tools: memory query, detector execution, similar case lookup, NLI check
    - Episodic memory tracks past judgments for consistency
    - Max 5 tool calls per judgment (cost control)
    """

    def __init__(
        self,
        model: str = AGENT_MODEL,
        max_tool_calls: int = 5,
        max_cost_usd: float = 0.10,
    ):
        self.model = model
        self.max_tool_calls = max_tool_calls
        self.max_cost_usd = max_cost_usd
        self._memory: List[PastJudgment] = []
        self._detector_runners = None

    def _get_runners(self):
        if self._detector_runners is None:
            try:
                from app.detection_enterprise.detector_adapters import _build_detector_runners
                self._detector_runners = _build_detector_runners()
            except Exception:
                self._detector_runners = {}
        return self._detector_runners

    def _handle_tool_call(self, tool_name: str, tool_input: Dict, input_data: Dict) -> str:
        """Execute a tool call and return the result as a string."""
        if tool_name == "query_detection_memory":
            det_type = tool_input.get("detection_type", "")
            # Return memory stats
            similar = [j for j in self._memory if j.detection_type == det_type]
            if similar:
                recent = similar[-3:]
                return json.dumps({
                    "total_past_judgments": len(similar),
                    "recent_verdicts": [{"detected": j.verdict, "confidence": j.confidence, "reasoning": j.reasoning_summary} for j in recent],
                })
            return json.dumps({"total_past_judgments": 0, "message": "No past judgments for this detector type."})

        elif tool_name == "run_detector":
            det_type = tool_input.get("detection_type", "")
            runners = self._get_runners()
            for key, runner in runners.items():
                if key.value == det_type:
                    try:
                        from app.detection_enterprise.golden_dataset import GoldenDatasetEntry
                        entry = GoldenDatasetEntry(id="agent_judge", detection_type=det_type,
                                                    input_data=tool_input.get("input_data", input_data), expected_detected=True)
                        detected, confidence = runner(entry)
                        return json.dumps({"detected": detected, "confidence": round(confidence, 4)})
                    except Exception as e:
                        return json.dumps({"error": str(e)[:200]})
            return json.dumps({"error": f"No runner found for {det_type}"})

        elif tool_name == "find_similar_cases":
            det_type = tool_input.get("detection_type", "")
            similar = [j for j in self._memory if j.detection_type == det_type][-3:]
            return json.dumps([{"verdict": j.verdict, "confidence": j.confidence, "reasoning": j.reasoning_summary} for j in similar])

        elif tool_name == "check_source_grounding":
            claim = tool_input.get("claim", "")
            source = tool_input.get("source_text", "")
            try:
                from app.detection.nli_checker import check_entailment
                label, conf = check_entailment(source[:512], claim[:512])
                return json.dumps({"label": label, "confidence": round(conf, 4)})
            except Exception as e:
                return json.dumps({"error": str(e)[:200]})

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    def judge(
        self,
        detection_type: str,
        input_data: Dict[str, Any],
        rule_confidence: float = 0.5,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentVerdict:
        """Run multi-step agent evaluation.

        Args:
            detection_type: What failure we're checking for
            input_data: The trace/entry data to evaluate
            rule_confidence: What the rule-based detector said (0-1)
            context: Additional context (e.g., agent role, task description)

        Returns:
            AgentVerdict with reasoning chain and final decision
        """
        start = time.monotonic()
        reasoning_chain = []
        tools_used = []
        total_tokens = 0
        total_cost = 0.0

        # Build the system prompt
        system = (
            f"You are an expert evaluator for multi-agent system failures. "
            f"You are evaluating a potential '{detection_type}' failure.\n\n"
            f"The rule-based detector gave confidence {rule_confidence:.2f} "
            f"(ambiguous — needs your analysis).\n\n"
            f"You have 4 tools available:\n"
            f"1. query_detection_memory: Check historical patterns\n"
            f"2. run_detector: Run a specific detector on data\n"
            f"3. find_similar_cases: Find similar past judgments\n"
            f"4. check_source_grounding: NLI entailment check\n\n"
            f"Think step by step. Use tools to gather evidence. "
            f"Then give your final verdict: is this a real '{detection_type}' failure?\n"
            f"End with VERDICT: DETECTED or VERDICT: NOT DETECTED and a confidence (0.0-1.0)."
        )

        # Initial user message with the data
        data_summary = json.dumps(input_data, indent=2)[:3000]
        user_msg = f"Evaluate this data for {detection_type} failure:\n\n```json\n{data_summary}\n```"
        if context:
            user_msg += f"\n\nAdditional context: {json.dumps(context)[:500]}"

        messages = [{"role": "user", "content": user_msg}]

        # Multi-turn conversation with tool use
        client = _get_client()
        tool_calls = 0

        for turn in range(self.max_tool_calls + 2):  # Extra turns for final answer
            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    system=system,
                    tools=AGENT_TOOLS,
                    messages=messages,
                )
            except Exception as e:
                reasoning_chain.append(f"API error: {str(e)[:100]}")
                break

            # Track usage
            total_tokens += response.usage.input_tokens + response.usage.output_tokens
            # Approximate cost (Sonnet 4: $3/1M input, $15/1M output)
            total_cost += response.usage.input_tokens * 3 / 1_000_000 + response.usage.output_tokens * 15 / 1_000_000

            if total_cost > self.max_cost_usd:
                reasoning_chain.append(f"Cost limit reached: ${total_cost:.4f}")
                break

            # Process response
            assistant_content = response.content
            text_parts = []
            tool_use_parts = []

            for block in assistant_content:
                if block.type == "text":
                    text_parts.append(block.text)
                    reasoning_chain.append(block.text[:200])
                elif block.type == "tool_use":
                    tool_use_parts.append(block)

            # If no tool calls, we're done
            if not tool_use_parts:
                messages.append({"role": "assistant", "content": assistant_content})
                break

            # Handle tool calls
            messages.append({"role": "assistant", "content": assistant_content})
            tool_results = []
            for tool_block in tool_use_parts:
                if tool_calls >= self.max_tool_calls:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": json.dumps({"error": "Tool call limit reached"}),
                    })
                    continue

                result = self._handle_tool_call(tool_block.name, tool_block.input, input_data)
                tools_used.append(tool_block.name)
                tool_calls += 1
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

        # Parse verdict from last text
        all_text = " ".join(reasoning_chain)
        detected = "VERDICT: DETECTED" in all_text.upper() and "NOT DETECTED" not in all_text.upper().split("VERDICT:")[-1]
        confidence = rule_confidence  # Default to rule confidence

        # Try to parse confidence from text
        import re
        conf_match = re.search(r'confidence[:\s]*([0-9.]+)', all_text.lower())
        if conf_match:
            try:
                confidence = float(conf_match.group(1))
                confidence = min(1.0, max(0.0, confidence))
            except ValueError:
                pass

        elapsed = int((time.monotonic() - start) * 1000)

        # Record in episodic memory
        self._memory.append(PastJudgment(
            detection_type=detection_type,
            verdict=detected,
            confidence=confidence,
            reasoning_summary=reasoning_chain[-1][:200] if reasoning_chain else "",
            timestamp=str(int(time.time())),
        ))

        # Keep memory bounded
        if len(self._memory) > 100:
            self._memory = self._memory[-50:]

        return AgentVerdict(
            detected=detected,
            confidence=confidence,
            reasoning_chain=reasoning_chain,
            tools_used=tools_used,
            memory_context={"past_judgments": len(self._memory), "tools_called": tool_calls},
            cost_usd=round(total_cost, 6),
            tokens_used=total_tokens,
            latency_ms=elapsed,
        )


# Singleton (lazy — only created when first used)
_agent_judge = None


def get_agent_judge() -> AgentJudge:
    global _agent_judge
    if _agent_judge is None:
        _agent_judge = AgentJudge()
    return _agent_judge
