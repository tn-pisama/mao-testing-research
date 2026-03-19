"""LLM-powered source code fix generator.

Analyzes detection results and relevant source code to generate
concrete source-level fixes (actual code changes, not just config tweaks).
Uses Anthropic Claude to understand failure patterns and produce
production-ready code patches with unified diffs.
"""

import difflib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from anthropic import Anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anthropic pricing (per 1M tokens) for cost tracking
# ---------------------------------------------------------------------------
_SONNET_INPUT_COST_PER_1M = 3.0    # $3 per 1M input tokens
_SONNET_OUTPUT_COST_PER_1M = 15.0   # $15 per 1M output tokens

_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_MAX_TOKENS = 8192

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class SourceFixInput:
    """Input payload describing the detected failure and source code to fix."""

    detection_type: str
    detection_method: str
    detection_details: Dict[str, Any]
    confidence: int
    file_path: str
    file_content: str
    language: str
    root_cause_analysis: Optional[str] = None
    framework: Optional[str] = None
    related_files: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class SourceFixOutput:
    """Result of an LLM-powered source fix generation."""

    file_path: str
    language: str
    original_code: str
    fixed_code: str
    unified_diff: str
    explanation: str
    root_cause: str
    confidence: float
    breaking_risk: str          # low, medium, high
    requires_testing: bool
    framework_specific: bool
    model_used: str
    cost_usd: float
    tokens_used: int


# ---------------------------------------------------------------------------
# Per-detection-type prompt guidance
# ---------------------------------------------------------------------------

DETECTION_FIX_PROMPTS: Dict[str, str] = {
    "loop": (
        "Common source-level causes of infinite/repetitive loops:\n"
        "- Missing or unreachable loop termination condition (e.g. while True without a "
        "reachable break, retry counter never incremented)\n"
        "- State not advancing between iterations — the same inputs produce the same "
        "outputs causing the agent to repeat itself\n"
        "- Circular dependency between two or more agents where Agent A delegates to "
        "Agent B which delegates back to Agent A with no exit gate\n"
        "- Conversation turn counter or max-iteration guard absent from the "
        "orchestration layer"
    ),
    "corruption": (
        "Common source-level causes of state corruption:\n"
        "- Shared mutable state modified concurrently by multiple agents without "
        "synchronization (missing locks, no copy-on-write)\n"
        "- Schema-less state dict allows arbitrary keys — a typo in a key name "
        "silently creates a parallel state path\n"
        "- Partial writes: an update function sets some fields but crashes before "
        "committing the rest, leaving state half-updated\n"
        "- Missing validation on state transitions — invalid enum values or out-of-range "
        "numbers propagate silently"
    ),
    "persona_drift": (
        "Common source-level causes of persona drift:\n"
        "- System prompt is only included in the first message; subsequent calls "
        "to the LLM omit or truncate it due to context window management\n"
        "- Role instructions are overridden by user or inter-agent messages that "
        "include conflicting persona directives\n"
        "- Agent identity is stored in mutable state that gets overwritten during "
        "multi-agent handoffs\n"
        "- No periodic persona reinforcement — long conversations dilute the "
        "original role instructions below the attention threshold"
    ),
    "coordination": (
        "Common source-level causes of coordination failures:\n"
        "- Missing acknowledgment protocol — Agent A sends a handoff message but "
        "never verifies Agent B received and accepted it\n"
        "- Race condition in shared message queue: two agents read the same task "
        "and both attempt to process it\n"
        "- Incompatible message schemas between agents — sender uses one key name, "
        "receiver expects another\n"
        "- No timeout on inter-agent waits, causing indefinite blocking when the "
        "target agent fails silently"
    ),
    "hallucination": (
        "Common source-level causes of hallucination:\n"
        "- Retrieved context is not injected into the LLM prompt, so the model "
        "generates answers from parametric memory alone\n"
        "- Source documents are truncated or summarized too aggressively, removing "
        "key facts the answer depends on\n"
        "- No grounding instruction in the system prompt telling the model to "
        "cite sources and decline when evidence is insufficient\n"
        "- Temperature set too high (>0.7) for factual tasks, increasing creative "
        "but unfounded completions"
    ),
    "injection": (
        "Common source-level causes of prompt injection vulnerabilities:\n"
        "- User input is concatenated directly into the system prompt without "
        "sanitization or escaping\n"
        "- No input validation layer — special characters, role-override phrases, "
        "and encoded payloads pass through unchecked\n"
        "- Agent tool-use permissions are not scoped: a compromised prompt can "
        "invoke any registered tool including destructive ones\n"
        "- Missing output filtering — the model's response is returned verbatim "
        "without checking for leaked instructions or injected commands"
    ),
    "overflow": (
        "Common source-level causes of context window overflow:\n"
        "- Conversation history grows unbounded — every message is appended "
        "without summarization or sliding-window truncation\n"
        "- Large documents are embedded in-prompt rather than retrieved via RAG, "
        "consuming most of the available context window\n"
        "- Tool call results are included at full length instead of being "
        "summarized before insertion into the prompt\n"
        "- No token counting before API calls — the code assumes the prompt fits "
        "without checking against the model's context limit"
    ),
    "derailment": (
        "Common source-level causes of task derailment:\n"
        "- No task-anchoring mechanism — the agent processes each message in "
        "isolation without referencing the original goal\n"
        "- User follow-up questions cause the agent to abandon the primary task "
        "and pursue tangents without a return path\n"
        "- Missing progress tracking — the agent cannot tell whether it is making "
        "forward progress toward the stated objective\n"
        "- Overly broad tool access allows the agent to wander into unrelated "
        "capabilities instead of staying on-task"
    ),
    "context": (
        "Common source-level causes of context neglect:\n"
        "- Relevant context is loaded but placed too far from the query in the "
        "prompt, falling outside the model's effective attention span\n"
        "- Context is passed as metadata rather than included in the conversation "
        "messages, so the LLM never sees it\n"
        "- Retrieval returns low-relevance chunks due to poor embedding quality "
        "or missing re-ranking step\n"
        "- Context window is consumed by system instructions, leaving insufficient "
        "room for the actual retrieved context"
    ),
    "communication": (
        "Common source-level causes of inter-agent communication breakdown:\n"
        "- Message format mismatch — sender emits JSON but receiver expects "
        "plain text, or vice versa\n"
        "- Routing logic sends messages to the wrong agent because agent IDs are "
        "hard-coded or looked up from stale configuration\n"
        "- No message schema validation — malformed messages are silently dropped "
        "or cause downstream parsing errors\n"
        "- Fire-and-forget messaging with no delivery confirmation or retry on "
        "transient failures"
    ),
    "specification": (
        "Common source-level causes of specification violations:\n"
        "- Output format requirements (JSON schema, field constraints) are "
        "described in documentation but never enforced in code\n"
        "- The LLM is asked for structured output but no parser validates the "
        "response before it is returned to the caller\n"
        "- Edge cases in the spec (optional fields, null values, empty arrays) "
        "are not handled, causing partial compliance\n"
        "- Multiple agents contribute to a single output but have inconsistent "
        "understanding of the output specification"
    ),
    "decomposition": (
        "Common source-level causes of task decomposition failures:\n"
        "- Decomposition prompt lacks examples or constraints, producing subtasks "
        "that are too vague or too granular to be actionable\n"
        "- Dependencies between subtasks are not captured, so they execute in "
        "the wrong order or in parallel when they should be sequential\n"
        "- No validation that the union of subtask outputs covers the original "
        "task requirements — gaps go undetected\n"
        "- Decomposition result is not checked for circular dependencies or "
        "duplicate subtasks before execution begins"
    ),
    "workflow": (
        "Common source-level causes of workflow execution failures:\n"
        "- Step transition conditions are incorrect or incomplete, causing the "
        "workflow to skip steps or enter invalid states\n"
        "- Error handling in individual steps does not propagate to the workflow "
        "engine, so a failed step is treated as successful\n"
        "- Workflow state is not persisted between steps, so a restart loses "
        "progress and re-executes completed work\n"
        "- Timeout and retry policies are defined at the workflow level but not "
        "respected by individual step implementations"
    ),
    "withholding": (
        "Common source-level causes of information withholding:\n"
        "- The agent's system prompt instructs it to be concise, which the model "
        "interprets as an instruction to omit relevant details\n"
        "- Internal reasoning (chain-of-thought) is available but not surfaced "
        "to the user because the output formatter strips it\n"
        "- Confidence thresholds are set too high — the agent suppresses correct "
        "but uncertain answers instead of qualifying them\n"
        "- Multi-step retrieval gathers relevant information in intermediate steps "
        "but the final summarization step drops key findings"
    ),
    "completion": (
        "Common source-level causes of premature or incomplete task completion:\n"
        "- Success criteria are checked superficially (e.g. 'output is not empty') "
        "rather than validating actual content quality\n"
        "- The agent declares completion after the first sub-goal is met without "
        "verifying that all required sub-goals are satisfied\n"
        "- Timeout-based termination fires before the agent has finished, and the "
        "partial result is returned as if it were complete\n"
        "- No quality gate between the agent's output and the caller — whatever "
        "the agent returns is accepted without review"
    ),
    "cost": (
        "Common source-level causes of cost/token budget overruns:\n"
        "- No per-request or per-session token budget — the agent calls the LLM "
        "in an unbounded loop until the task is done or fails\n"
        "- Verbose prompts include full document contents instead of using "
        "summarization or retrieval to reduce token consumption\n"
        "- Retry logic re-sends the entire conversation history on each attempt "
        "instead of just the failed portion\n"
        "- Model selection is hard-coded to the most capable (and expensive) model "
        "even for simple classification or routing tasks"
    ),
    "grounding": (
        "Common source-level causes of grounding failures:\n"
        "- Source documents are retrieved but not cited — the LLM generates a "
        "response that sounds authoritative but has no traceable evidence\n"
        "- Embedding search returns semantically similar but factually irrelevant "
        "passages, and no re-ranking step filters them\n"
        "- The grounding check compares surface-level word overlap instead of "
        "verifying factual entailment between source and output\n"
        "- Retrieved chunks are too short to provide sufficient context, causing "
        "the model to hallucinate missing details"
    ),
    "convergence": (
        "Common source-level causes of convergence issues in iterative agent systems:\n"
        "- No metric tracking between iterations — the agent cannot measure whether "
        "it is improving, plateauing, or regressing\n"
        "- Missing best-checkpoint saving — the system does not snapshot the best-so-far "
        "state, making it impossible to revert after regression\n"
        "- Fixed exploration strategy — the agent uses the same approach every iteration "
        "instead of switching strategy when progress stalls\n"
        "- No early stopping condition — the agent continues iterating even when metrics "
        "have clearly plateaued or started diverging\n"
        "- Oscillating hyperparameters — the agent alternates between two configurations "
        "without converging, creating thrashing behavior"
    ),
}

# ---------------------------------------------------------------------------
# System prompt for the fix-generation LLM call
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert software engineer specializing in multi-agent AI systems.
Your task is to analyze a detected failure in a multi-agent orchestration
system and generate a COMPLETE, production-ready source code fix.

## Instructions

1. **Analyze the detection** — understand what type of failure was detected,
   what method found it, and what the root cause is.
2. **Examine the source code** — read the file carefully, identify the
   specific lines and patterns that caused the failure.
3. **Generate the COMPLETE fixed file** — output the entire file with your
   fixes applied. Do NOT output fragments or partial patches. The fixed code
   must be a drop-in replacement for the original file.
4. **Only modify what is necessary** — do not refactor unrelated code, rename
   variables for style, or reorganize imports unless required by the fix.
5. **Preserve existing functionality** — your fix must not break any existing
   behavior. If in doubt, add safeguards rather than removing code.
6. **Add comments explaining the fix** — mark each changed section with a
   brief inline comment prefixed with "# FIX:" explaining what was changed
   and why.

## Output Format

Wrap each section in XML-like tags exactly as shown:

<fixed_code>
(complete file content with fixes applied)
</fixed_code>

<explanation>
(2-4 sentence description of what was changed and why)
</explanation>

<root_cause>
(1-2 sentence description of the underlying cause of the failure)
</root_cause>

<confidence>
(a decimal number between 0.0 and 1.0 representing your confidence that
this fix resolves the detected issue without introducing regressions)
</confidence>

<breaking_risk>
(one of: low, medium, high — how likely this fix is to break existing
behavior or require changes in other files)
</breaking_risk>
"""


# ---------------------------------------------------------------------------
# SourceFixGenerator
# ---------------------------------------------------------------------------


class SourceFixGenerator:
    """Generates source-level code fixes using Anthropic Claude.

    Unlike the rule-based fix generators that produce generic code snippets,
    this generator analyzes the actual source file where a failure was
    detected and produces a complete patched version with a unified diff.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: str = _DEFAULT_MODEL,
        max_tokens: int = _MAX_TOKENS,
    ) -> None:
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Anthropic API key is required. Pass api_key= or set "
                "the ANTHROPIC_API_KEY environment variable."
            )
        self._client = Anthropic(api_key=resolved_key)
        self._model = model
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_fix(self, input: SourceFixInput) -> SourceFixOutput:
        """Generate a source-level fix for a detected failure.

        Builds a prompt from the detection details and source code, calls
        Claude, parses the structured response, and returns a
        ``SourceFixOutput`` with the patched code and a unified diff.
        """
        user_prompt = self._build_user_prompt(input)

        logger.info(
            "Generating source fix for %s in %s (method=%s)",
            input.detection_type,
            input.file_path,
            input.detection_method,
        )

        start_time = time.monotonic()

        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Extract text content from the response
        raw_text = ""
        for block in response.content:
            if block.type == "text":
                raw_text += block.text

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = input_tokens + output_tokens
        cost_usd = self._calculate_cost(input_tokens, output_tokens)

        logger.info(
            "Claude responded in %.0f ms — %d tokens (in=%d, out=%d), $%.4f",
            elapsed_ms,
            total_tokens,
            input_tokens,
            output_tokens,
            cost_usd,
        )

        # Parse structured response
        fixed_code, explanation, root_cause, confidence, breaking_risk = (
            self._parse_response(raw_text, input.file_content)
        )

        unified_diff = self._generate_diff(
            input.file_path, input.file_content, fixed_code
        )

        framework_specific = bool(input.framework) and (
            input.framework.lower() in fixed_code.lower()
        )

        return SourceFixOutput(
            file_path=input.file_path,
            language=input.language,
            original_code=input.file_content,
            fixed_code=fixed_code,
            unified_diff=unified_diff,
            explanation=explanation,
            root_cause=root_cause,
            confidence=confidence,
            breaking_risk=breaking_risk,
            requires_testing=breaking_risk in ("medium", "high"),
            framework_specific=framework_specific,
            model_used=self._model,
            cost_usd=cost_usd,
            tokens_used=total_tokens,
        )

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_user_prompt(self, input: SourceFixInput) -> str:
        """Assemble the user-message prompt from detection data and source."""
        sections: List[str] = []

        # Detection context
        detection_guidance = DETECTION_FIX_PROMPTS.get(
            input.detection_type, ""
        )
        sections.append(
            f"## Detection\n"
            f"- **Type:** {input.detection_type}\n"
            f"- **Method:** {input.detection_method}\n"
            f"- **Confidence:** {input.confidence}%\n"
        )
        if detection_guidance:
            sections.append(
                f"### Known patterns for this detection type\n"
                f"{detection_guidance}\n"
            )

        # Detection details (serialized as JSON for clarity)
        if input.detection_details:
            details_json = json.dumps(input.detection_details, indent=2, default=str)
            sections.append(
                f"### Detection details\n"
                f"```json\n{details_json}\n```\n"
            )

        # Root cause analysis (if provided upstream)
        if input.root_cause_analysis:
            sections.append(
                f"### Root cause analysis (from upstream)\n"
                f"{input.root_cause_analysis}\n"
            )

        # Framework context
        if input.framework:
            sections.append(
                f"### Framework\n"
                f"The code uses the **{input.framework}** framework. "
                f"Generate fixes that are idiomatic for this framework.\n"
            )

        # Primary source file
        sections.append(
            f"## Source file to fix\n"
            f"**Path:** `{input.file_path}`\n"
            f"**Language:** {input.language}\n"
            f"\n```{input.language}\n{input.file_content}\n```\n"
        )

        # Related files (for cross-file context)
        if input.related_files:
            sections.append("## Related files (read-only context)\n")
            for rf in input.related_files:
                rf_path = rf.get("path", "unknown")
                rf_lang = rf.get("language", input.language)
                rf_content = rf.get("content", "")
                sections.append(
                    f"### `{rf_path}`\n"
                    f"```{rf_lang}\n{rf_content}\n```\n"
                )

        sections.append(
            "## Task\n"
            "Generate the complete fixed version of the source file. "
            "Follow the output format specified in your instructions."
        )

        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(
        self,
        raw: str,
        original_code: str,
    ) -> Tuple[str, str, str, float, str]:
        """Extract structured fields from the LLM's XML-tagged response.

        Returns:
            (fixed_code, explanation, root_cause, confidence, breaking_risk)
        """
        fixed_code = self._extract_tag(raw, "fixed_code")
        explanation = self._extract_tag(raw, "explanation")
        root_cause = self._extract_tag(raw, "root_cause")
        confidence_str = self._extract_tag(raw, "confidence")
        breaking_risk = self._extract_tag(raw, "breaking_risk")

        # --- fixed_code fallback ---
        if not fixed_code:
            logger.warning(
                "Could not extract <fixed_code> from response; "
                "returning original code unchanged."
            )
            fixed_code = original_code

        # --- explanation fallback ---
        if not explanation:
            explanation = "The model did not provide a structured explanation."

        # --- root_cause fallback ---
        if not root_cause:
            root_cause = "Unable to determine root cause from model response."

        # --- confidence parsing ---
        confidence = 0.5  # default
        if confidence_str:
            try:
                parsed = float(confidence_str.strip())
                confidence = max(0.0, min(1.0, parsed))
            except ValueError:
                logger.warning(
                    "Could not parse confidence value '%s'; defaulting to 0.5",
                    confidence_str,
                )

        # --- breaking_risk normalisation ---
        valid_risks = {"low", "medium", "high"}
        if breaking_risk:
            breaking_risk = breaking_risk.strip().lower()
        if breaking_risk not in valid_risks:
            logger.warning(
                "Invalid breaking_risk '%s'; defaulting to 'medium'",
                breaking_risk,
            )
            breaking_risk = "medium"

        return fixed_code, explanation, root_cause, confidence, breaking_risk

    @staticmethod
    def _extract_tag(text: str, tag: str) -> str:
        """Extract content between ``<tag>`` and ``</tag>`` markers.

        Handles optional leading/trailing whitespace inside the tags.
        Returns an empty string if the tag is not found.
        """
        pattern = rf"<{re.escape(tag)}>\s*(.*?)\s*</{re.escape(tag)}>"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    # ------------------------------------------------------------------
    # Diff generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_diff(
        file_path: str,
        original: str,
        fixed: str,
    ) -> str:
        """Produce a unified diff between original and fixed code.

        Returns an empty string if the files are identical.
        """
        original_lines = original.splitlines(keepends=True)
        fixed_lines = fixed.splitlines(keepends=True)

        diff_lines = list(
            difflib.unified_diff(
                original_lines,
                fixed_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
            )
        )

        if not diff_lines:
            return ""

        return "\n".join(diff_lines)

    # ------------------------------------------------------------------
    # Cost calculation
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_cost(input_tokens: int, output_tokens: int) -> float:
        """Calculate USD cost based on Anthropic Sonnet pricing.

        Sonnet pricing (as of 2025-05):
            Input:  $3.00  per 1M tokens
            Output: $15.00 per 1M tokens
        """
        input_cost = (input_tokens / 1_000_000) * _SONNET_INPUT_COST_PER_1M
        output_cost = (output_tokens / 1_000_000) * _SONNET_OUTPUT_COST_PER_1M
        return round(input_cost + output_cost, 6)
