"""LLM-based golden dataset expansion for detection calibration.

Generates realistic positive and negative samples for each detection type
using Claude Sonnet, with per-type prompt templates and few-shot examples.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDatasetEntry, GoldenDataset

logger = logging.getLogger(__name__)

try:
    from anthropic import Anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False


# ---------------------------------------------------------------------------
# Per-type prompt metadata
# ---------------------------------------------------------------------------
# Each entry contains:
#   description  - what this failure mode is
#   positive_desc - what a positive (failure detected) sample looks like
#   negative_desc - what a negative (no failure) sample looks like
#   schema       - the JSON schema of input_data
# ---------------------------------------------------------------------------

TYPE_PROMPTS: Dict[str, Dict[str, str]] = {
    "loop": {
        "description": (
            "Loop detection identifies when an agent gets stuck repeating the same "
            "or semantically equivalent actions without making progress. This includes "
            "exact repetition, paraphrased repetition, and error-retry loops."
        ),
        "positive_desc": (
            "The agent repeats the same task with identical or near-identical content "
            "and state deltas across multiple states. Examples: retrying the same failing "
            "API call, rephrasing the same search query, or producing identical outputs."
        ),
        "negative_desc": (
            "The agent progresses through distinct steps with different content and "
            "changing state. Examples: processing different items in a batch, executing "
            "sequential pipeline stages, or iterating through a checklist."
        ),
        "schema": (
            '{"states": [{"agent_id": "<string>", "content": "<string describing the action>", '
            '"state_delta": {<key-value pairs showing state changes>}}, ...]}'
        ),
    },
    "persona_drift": {
        "description": (
            "Persona drift detection identifies when an agent's output deviates from "
            "its assigned role or persona. The agent should maintain consistent behavior "
            "aligned with its persona_description."
        ),
        "positive_desc": (
            "The agent produces output that is clearly outside its assigned persona. "
            "Examples: a legal assistant talking about recipes, a medical bot giving "
            "investment advice, or a formal assistant using slang."
        ),
        "negative_desc": (
            "The agent's output is consistent with its persona, even when handling "
            "edge cases or adjacent topics. Examples: a support agent addressing billing "
            "in addition to tech issues, or an advisor deferring to another specialist."
        ),
        "schema": (
            '{"agent": {"id": "<string>", "persona_description": "<string>"}, '
            '"output": "<string>"}'
        ),
    },
    "hallucination": {
        "description": (
            "Hallucination detection identifies when an agent fabricates facts, "
            "statistics, citations, or claims that are not supported by the provided "
            "source documents."
        ),
        "positive_desc": (
            "The agent invents specific numbers, names, dates, or quotes not present "
            "in sources. Examples: fabricated study citations, invented statistics, "
            "or claims contradicting the source material."
        ),
        "negative_desc": (
            "The agent accurately synthesizes information from sources, adds appropriate "
            "caveats, or honestly acknowledges gaps. Paraphrasing and reasonable "
            "inference from sources are acceptable."
        ),
        "schema": (
            '{"output": "<string>", "sources": [{"content": "<string>", '
            '"metadata": {<optional metadata>}}, ...]}'
        ),
    },
    "injection": {
        "description": (
            "Injection detection identifies prompt injection attempts where a user "
            "tries to override, hijack, or manipulate the agent's instructions or "
            "behavior through crafted input."
        ),
        "positive_desc": (
            "The text contains explicit attempts to override instructions, assume a "
            "different role, bypass safety filters, or extract system prompts. "
            "Examples: 'ignore previous instructions', DAN jailbreaks, delimiter attacks."
        ),
        "negative_desc": (
            "The text is a legitimate user query, even if it uses technical terms like "
            "'override', 'system', 'instructions', or discusses security topics "
            "in a benign context."
        ),
        "schema": '{"text": "<string>"}',
    },
    "overflow": {
        "description": (
            "Overflow detection identifies when an agent's context window is nearing "
            "or exceeding its capacity, risking truncation or degraded output quality."
        ),
        "positive_desc": (
            "The token count is at or near the model's context limit. "
            "Examples: 125000 tokens on a 128k model, or 3900 tokens on a 4k model."
        ),
        "negative_desc": (
            "The token count is well within the model's capacity with comfortable "
            "headroom. Examples: 2000 tokens on a 128k model, or 1000 tokens on a 4k model."
        ),
        "schema": '{"current_tokens": <int>, "model": "<string, e.g. gpt-4o or claude-sonnet>"}',
    },
    "corruption": {
        "description": (
            "Corruption detection identifies invalid state transitions where the "
            "agent's state mutates in ways that violate expected invariants or loses "
            "critical information between steps."
        ),
        "positive_desc": (
            "The current_state contains unexpected null values, type changes, missing "
            "required fields, or contradictory values compared to prev_state. "
            "Examples: a non-null field becoming null, status regressing, or data loss."
        ),
        "negative_desc": (
            "The state transition is valid with fields properly updated, new fields "
            "added logically, and no data loss. Status progressions are forward-moving."
        ),
        "schema": '{"prev_state": {<key-value pairs>}, "current_state": {<key-value pairs>}}',
    },
    "coordination": {
        "description": (
            "Coordination detection identifies failures in multi-agent communication "
            "including dropped messages, missing acknowledgments, conflicting actions, "
            "or deadlocks between agents."
        ),
        "positive_desc": (
            "Messages go unacknowledged, agents take conflicting actions, or agents "
            "wait indefinitely for each other. Examples: agent B never acknowledges "
            "agent A's handoff, or two agents modify the same resource simultaneously."
        ),
        "negative_desc": (
            "Agents communicate cleanly with proper handoffs and acknowledgments. "
            "Messages flow in logical order and all participants respond appropriately."
        ),
        "schema": (
            '{"messages": [{"from_agent": "<string>", "to_agent": "<string>", '
            '"content": "<string>", "timestamp": "<ISO datetime>", '
            '"acknowledged": <bool>}, ...], "agent_ids": ["<string>", ...]}'
        ),
    },
    "communication": {
        "description": (
            "Communication detection identifies breakdowns in agent-to-agent message "
            "exchange where the receiver misinterprets, ignores, or fails to address "
            "the sender's message content."
        ),
        "positive_desc": (
            "The receiver's response is irrelevant to, contradicts, or completely "
            "ignores the sender's message. Examples: answering a different question, "
            "missing key constraints, or providing contradictory information."
        ),
        "negative_desc": (
            "The receiver correctly addresses the sender's message, answering questions "
            "asked and acknowledging constraints or requirements mentioned."
        ),
        "schema": '{"sender_message": "<string>", "receiver_response": "<string>"}',
    },
    "context": {
        "description": (
            "Context detection identifies when an agent's output ignores or contradicts "
            "the provided context, effectively neglecting relevant information that "
            "should inform its response."
        ),
        "positive_desc": (
            "The output ignores key facts from the context, contradicts stated "
            "constraints, or fails to reference critical information. Examples: "
            "ignoring a budget limit, contradicting stated dates, or missing stated requirements."
        ),
        "negative_desc": (
            "The output properly reflects the context, addressing stated constraints "
            "and incorporating relevant information from the provided context."
        ),
        "schema": '{"context": "<string>", "output": "<string>"}',
    },
    "grounding": {
        "description": (
            "Grounding detection measures how well an agent's output is supported by "
            "provided source documents. Unlike hallucination detection, this focuses "
            "on the degree of groundedness rather than fabrication detection."
        ),
        "positive_desc": (
            "The agent makes claims or provides information that cannot be traced back "
            "to any of the source documents. Examples: introducing external knowledge, "
            "overgeneralizing beyond source scope, or providing unsupported recommendations."
        ),
        "negative_desc": (
            "Every claim in the agent's output can be traced to a specific source "
            "document. The output stays within the scope of the provided materials."
        ),
        "schema": (
            '{"agent_output": "<string>", "source_documents": ["<string>", ...]}'
        ),
    },
    "retrieval_quality": {
        "description": (
            "Retrieval quality detection evaluates whether the retrieved documents "
            "are relevant to the query and whether the agent's output makes good use "
            "of them."
        ),
        "positive_desc": (
            "Retrieved documents are irrelevant to the query, the agent ignores "
            "relevant retrieved content, or the output quality suffers from poor "
            "retrieval. Examples: retrieving cooking recipes for a legal query."
        ),
        "negative_desc": (
            "Retrieved documents are relevant to the query and the agent synthesizes "
            "them effectively into a coherent, accurate response."
        ),
        "schema": (
            '{"query": "<string>", "retrieved_documents": ["<string>", ...], '
            '"agent_output": "<string>"}'
        ),
    },
    "completion": {
        "description": (
            "Completion detection identifies when an agent misjudges task completion, "
            "either declaring a task done prematurely or failing to recognize that "
            "all subtasks have been satisfied."
        ),
        "positive_desc": (
            "The agent claims the task is complete but subtasks remain unaddressed, "
            "success criteria are not met, or the output is clearly incomplete. "
            "Examples: missing required sections, unfinished analysis, or skipped steps."
        ),
        "negative_desc": (
            "The agent correctly addresses all subtasks and meets the success criteria. "
            "The output is thorough and complete relative to the task requirements."
        ),
        "schema": (
            '{"task": "<string>", "agent_output": "<string>", '
            '"subtasks": ["<string>", ...], "success_criteria": "<string>"}'
        ),
    },
    "derailment": {
        "description": (
            "Derailment detection identifies when an agent's output diverges from "
            "the assigned task, going off on tangents or addressing unrelated topics."
        ),
        "positive_desc": (
            "The output addresses a completely different topic from the task, "
            "goes on extended tangents, or loses focus on the core objective. "
            "Examples: writing about history when asked for code, or discussing "
            "philosophy when asked for data analysis."
        ),
        "negative_desc": (
            "The output stays focused on the task, even if it includes relevant "
            "context, caveats, or adjacent information that supports the main objective."
        ),
        "schema": '{"output": "<string>", "task": "<string>"}',
    },
    "specification": {
        "description": (
            "Specification detection identifies mismatches between the user's original "
            "intent and the task specification produced by the agent. The specification "
            "may miss requirements, add unwanted constraints, or misinterpret the intent."
        ),
        "positive_desc": (
            "The task specification misses stated requirements, adds constraints the "
            "user did not request, misinterprets ambiguous language, or changes the "
            "scope. Examples: ignoring a stated deadline, adding unnecessary features, "
            "or narrowing scope without justification."
        ),
        "negative_desc": (
            "The task specification faithfully captures the user's intent, including "
            "all stated requirements, reasonable defaults for ambiguities, and "
            "appropriate scope."
        ),
        "schema": '{"user_intent": "<string>", "task_specification": "<string>"}',
    },
    "decomposition": {
        "description": (
            "Decomposition detection identifies failures in how an agent breaks down "
            "a complex task into subtasks. Poor decomposition can lead to missed steps, "
            "redundant work, or incorrect ordering."
        ),
        "positive_desc": (
            "The decomposition misses critical steps, has incorrect ordering, contains "
            "redundant subtasks, or is too coarse/fine-grained. Examples: skipping "
            "error handling, putting deployment before testing, or splitting a simple "
            "task into 20 micro-steps."
        ),
        "negative_desc": (
            "The decomposition logically breaks the task into appropriate subtasks "
            "with correct ordering, no redundancy, and reasonable granularity."
        ),
        "schema": '{"decomposition": "<string>", "task_description": "<string>"}',
    },
    "withholding": {
        "description": (
            "Withholding detection identifies when an agent's public output omits "
            "important information that is present in its internal state or reasoning. "
            "The agent knows something relevant but does not share it."
        ),
        "positive_desc": (
            "The agent's output omits critical findings, warnings, or caveats that "
            "are visible in its internal state. Examples: hiding error logs, omitting "
            "negative results, or not mentioning known risks."
        ),
        "negative_desc": (
            "The agent's output accurately reflects its internal state, sharing all "
            "relevant findings, warnings, and caveats. Nothing material is withheld."
        ),
        "schema": '{"agent_output": "<string>", "internal_state": "<string>"}',
    },
    "workflow": {
        "description": (
            "Workflow detection identifies structural or execution problems in "
            "multi-step workflows including disconnected nodes, circular dependencies, "
            "missing error handling, and execution failures."
        ),
        "positive_desc": (
            "The workflow has structural issues (disconnected nodes, circular connections) "
            "or execution failures (timeouts, merge mismatches, unhandled errors). "
            "Examples: orphaned nodes, infinite loops, or failed parallel merges."
        ),
        "negative_desc": (
            "The workflow has a valid structure with all nodes connected, proper "
            "branching, and successful execution with no errors."
        ),
        "schema": (
            '{"workflow_definition": {"nodes": ["<string>", ...], '
            '"connections": [{"from": "<string>", "to": "<string>"}, ...]}, '
            '"execution_result": {"status": "<success|error>", ...}}'
        ),
    },
}


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> Any:
    """Extract JSON from LLM text that may include markdown fences."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding array or object
    for pattern in [r'\[.*\]', r'\{.*\}']:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------

class GoldenDataGenerator:
    """Generates golden dataset entries using an LLM (Claude Sonnet).

    Uses the Anthropic SDK directly to request structured JSON output
    containing realistic positive and negative samples for each detection type.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.8,
    ):
        self.model = model
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._client: Optional[Any] = None
        self.max_tokens = max_tokens
        self.temperature = temperature

    @property
    def client(self):
        """Lazy Anthropic client initialization."""
        if self._client is None and _HAS_ANTHROPIC:
            self._client = Anthropic(api_key=self._api_key)
        return self._client

    @property
    def is_available(self) -> bool:
        """True when the Anthropic SDK is installed and an API key is set."""
        return _HAS_ANTHROPIC and bool(self._api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        detection_type: DetectionType,
        count: int = 20,
        positive_ratio: float = 0.5,
        existing_entries: Optional[List[GoldenDatasetEntry]] = None,
    ) -> List[GoldenDatasetEntry]:
        """Generate golden entries for a single detection type.

        Args:
            detection_type: The detection type to generate samples for.
            count: Total number of samples to generate.
            positive_ratio: Fraction of samples that should be positive (failure detected).
            existing_entries: Optional existing entries to use as few-shot examples.

        Returns:
            List of generated GoldenDatasetEntry objects.
        """
        if not self.is_available:
            logger.warning(
                "GoldenDataGenerator not available (missing SDK or API key). "
                "Returning empty list."
            )
            return []

        n_positive = round(count * positive_ratio)
        n_negative = count - n_positive

        # Select few-shot examples (up to 3, mix of positive and negative)
        examples = self._select_examples(existing_entries or [], max_examples=3)

        prompt = self._build_prompt(
            detection_type=detection_type,
            count=count,
            n_positive=n_positive,
            n_negative=n_negative,
            examples=examples,
        )

        logger.info(
            "Generating %d samples for %s (%d positive, %d negative)",
            count, detection_type.value, n_positive, n_negative,
        )

        raw_response = self._call_llm(prompt)
        if not raw_response:
            logger.error("Empty LLM response for %s", detection_type.value)
            return []

        entries = self._parse_entries(raw_response, detection_type)
        logger.info(
            "Parsed %d/%d entries for %s", len(entries), count, detection_type.value,
        )
        return entries

    def generate_all(
        self,
        existing_dataset: GoldenDataset,
        target_per_type: int = 30,
    ) -> List[GoldenDatasetEntry]:
        """Generate entries for all detection types below *target_per_type*.

        Skips types that already have enough entries and uses existing entries
        as few-shot examples for the LLM.

        Returns:
            All newly generated entries across all types.
        """
        all_generated: List[GoldenDatasetEntry] = []

        for dt in DetectionType:
            existing = existing_dataset.get_entries_by_type(dt)
            current_count = len(existing)
            if current_count >= target_per_type:
                logger.debug(
                    "Skipping %s: already has %d entries (target %d)",
                    dt.value, current_count, target_per_type,
                )
                continue

            needed = target_per_type - current_count
            entries = self.generate(
                detection_type=dt,
                count=needed,
                positive_ratio=0.5,
                existing_entries=existing,
            )
            all_generated.extend(entries)

        logger.info("Generated %d total entries across all types", len(all_generated))
        return all_generated

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_examples(
        self,
        entries: List[GoldenDatasetEntry],
        max_examples: int = 3,
    ) -> List[GoldenDatasetEntry]:
        """Pick up to *max_examples* entries, mixing positive and negative."""
        if not entries:
            return []

        positives = [e for e in entries if e.expected_detected]
        negatives = [e for e in entries if not e.expected_detected]

        selected: List[GoldenDatasetEntry] = []

        # Take 1-2 positives and 1-2 negatives to demonstrate both classes
        if positives:
            selected.append(positives[0])
        if negatives:
            selected.append(negatives[0])
        if len(positives) > 1 and len(selected) < max_examples:
            selected.append(positives[1])
        if len(negatives) > 1 and len(selected) < max_examples:
            selected.append(negatives[1])

        return selected[:max_examples]

    def _build_prompt(
        self,
        detection_type: DetectionType,
        count: int,
        n_positive: int,
        n_negative: int,
        examples: List[GoldenDatasetEntry],
    ) -> str:
        """Build the generation prompt with per-type instructions and few-shot examples."""
        type_key = detection_type.value
        type_info = TYPE_PROMPTS.get(type_key)
        if not type_info:
            raise ValueError(f"No prompt template for detection type: {type_key}")

        # Format few-shot examples
        examples_block = ""
        if examples:
            example_items = []
            for ex in examples:
                example_items.append(json.dumps({
                    "input_data": ex.input_data,
                    "expected_detected": ex.expected_detected,
                    "expected_confidence_min": ex.expected_confidence_min,
                    "expected_confidence_max": ex.expected_confidence_max,
                    "description": ex.description,
                }, indent=2))
            examples_block = (
                "\n\nHere are existing examples for reference (use similar style "
                "and complexity, but create NEW and DIFFERENT scenarios):\n\n"
                + "\n---\n".join(examples_block for examples_block in example_items)
            )

        prompt = f"""You are a test data engineer generating golden dataset entries for a multi-agent orchestration failure detection system.

## Detection Type: {type_key}

{type_info['description']}

## Input Data Schema

The `input_data` field must match this JSON structure exactly:
{type_info['schema']}

## What Positive Samples Look Like (expected_detected = true)

{type_info['positive_desc']}

## What Negative Samples Look Like (expected_detected = false)

{type_info['negative_desc']}
{examples_block}

## Your Task

Generate exactly {count} samples:
- {n_positive} POSITIVE samples (expected_detected: true) with expected_confidence_min between 0.4 and 0.85 and expected_confidence_max between 0.6 and 0.99
- {n_negative} NEGATIVE samples (expected_detected: false) with expected_confidence_min between 0.0 and 0.1 and expected_confidence_max between 0.15 and 0.35

Requirements:
1. Each sample must have realistic, diverse content (different domains, scenarios, agent types)
2. Positive samples should range from subtle/borderline to obvious failures
3. Negative samples should include tricky cases that LOOK like failures but are not
4. The input_data must strictly follow the schema above
5. Each sample needs a concise description explaining why it is positive or negative
6. Use varied tags (2-4 per sample) that describe the scenario

Respond with a JSON array of objects, each with these fields:
- "input_data": <object matching the schema>
- "expected_detected": <boolean>
- "expected_confidence_min": <float>
- "expected_confidence_max": <float>
- "description": <string>
- "tags": <list of strings>

Return ONLY the JSON array, no other text."""

        return prompt

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM and return the raw text response."""
        if not self.client:
            logger.error("Anthropic client not available")
            return ""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
                system=(
                    "You are a precise test data generator. Always respond with "
                    "valid JSON arrays. Do not include markdown fences unless "
                    "necessary. Ensure every JSON object is complete and valid."
                ),
            )
            return response.content[0].text
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            return ""

    def _parse_entries(
        self,
        raw_response: str,
        detection_type: DetectionType,
    ) -> List[GoldenDatasetEntry]:
        """Parse LLM response into GoldenDatasetEntry objects.

        Handles markdown fences, partial JSON, and individual entry failures
        gracefully -- valid entries are kept even if some fail to parse.
        """
        parsed = _parse_json(raw_response)
        if parsed is None:
            logger.error(
                "Failed to parse any JSON from LLM response for %s",
                detection_type.value,
            )
            return []

        # Normalise: if we got a dict with an "entries" or "samples" key, unwrap
        if isinstance(parsed, dict):
            for key in ("entries", "samples", "data", "results"):
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                # Single object -- wrap it
                parsed = [parsed]

        if not isinstance(parsed, list):
            logger.error("Parsed JSON is not a list for %s", detection_type.value)
            return []

        entries: List[GoldenDatasetEntry] = []
        type_prefix = detection_type.value
        for item in parsed:
            try:
                if not isinstance(item, dict):
                    continue

                input_data = item.get("input_data")
                if input_data is None:
                    continue

                expected_detected = bool(item.get("expected_detected", False))
                conf_min = float(item.get("expected_confidence_min", 0.0))
                conf_max = float(item.get("expected_confidence_max", 1.0))

                # Clamp confidence bounds
                conf_min = max(0.0, min(1.0, conf_min))
                conf_max = max(conf_min, min(1.0, conf_max))

                description = str(item.get("description", ""))
                tags = item.get("tags", [])
                if not isinstance(tags, list):
                    tags = [str(tags)]
                tags = [str(t) for t in tags]

                entry_id = f"{type_prefix}_gen_{uuid.uuid4().hex[:8]}"

                entry = GoldenDatasetEntry(
                    id=entry_id,
                    detection_type=detection_type,
                    input_data=input_data,
                    expected_detected=expected_detected,
                    expected_confidence_min=conf_min,
                    expected_confidence_max=conf_max,
                    description=description,
                    source="llm_generated",
                    tags=tags,
                    augmentation_method="claude_sonnet",
                    human_verified=False,
                )
                entries.append(entry)

            except Exception as exc:
                logger.warning(
                    "Skipping malformed entry for %s: %s", detection_type.value, exc,
                )
                continue

        return entries
