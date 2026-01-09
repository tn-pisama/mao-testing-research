"""
MAST Failure Mode LLM Judge
============================

Uses Claude Opus 4.5 to verify ambiguous failure mode detections.
Based on MAST paper methodology achieving 94% accuracy with few-shot prompting.

Design principles:
- Only called for ambiguous cases (confidence 0.40-0.85)
- Caches results by trace hash + failure mode
- Tracks costs per detection
- Uses structured output for reliable parsing
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


class MASTFailureMode(str, Enum):
    """MAST 14 failure modes - aligned with MAST taxonomy (arXiv:2503.13657)."""
    # FC1: System Design Issues (5 modes)
    F1 = "F1"   # Disobey Task Specification (FM-1.1)
    F2 = "F2"   # Disobey Role Specification (FM-1.2)
    F3 = "F3"   # Step Repetition (FM-1.3)
    F4 = "F4"   # Loss of Conversation History (FM-1.4)
    F5 = "F5"   # Unaware of Termination Conditions (FM-1.5)
    # FC2: Inter-Agent Misalignment (6 modes)
    F6 = "F6"   # Conversation Reset (FM-2.1)
    F7 = "F7"   # Fail to Ask for Clarification (FM-2.2)
    F8 = "F8"   # Task Derailment (FM-2.3)
    F9 = "F9"   # Information Withholding (FM-2.4)
    F10 = "F10" # Ignored Other Agent's Input (FM-2.5)
    F11 = "F11" # Reasoning-Action Mismatch (FM-2.6)
    # FC3: Task Verification Issues (3 modes)
    F12 = "F12" # Premature Termination (FM-3.1)
    F13 = "F13" # No or Incomplete Verification (FM-3.2)
    F14 = "F14" # Incorrect Verification (FM-3.3)


# MAST Failure Mode Definitions - Aligned with arXiv:2503.13657
# "Why Do Multi-Agent LLM Systems Fail?" (Cemri et al., 2025)
# Reference: https://github.com/multi-agent-systems-failure-taxonomy/MAST
MAST_FAILURE_DEFINITIONS = {
    # === FC1: System Design Issues (5 modes) ===
    MASTFailureMode.F1: {
        "name": "Disobey Task Specification",
        "definition": """FM-1.1: Failure to adhere to the specified constraints or requirements of a given task,
leading to suboptimal or incorrect outcomes. The agent produces output that violates explicit task requirements,
ignores stated constraints, or delivers something different from what was specified.""",
        "positive_example": """Task: "Create a REST API with authentication and rate limiting"
Agent: "Here's a simple API endpoint: def get_users(): return users_list"
[No authentication, no rate limiting implemented]
Verdict: YES - Disobeyed explicit task requirements""",
        "negative_example": """Task: "Create a REST API with authentication"
Agent: "Here's the API with JWT auth middleware and protected endpoints"
Verdict: NO - Agent followed task specification"""
    },
    MASTFailureMode.F2: {
        "name": "Disobey Role Specification",
        "definition": """FM-1.2: Failure to adhere to the defined responsibilities and constraints of an assigned role,
potentially leading to an agent behaving like another. Look for agents acting outside their designated role,
performing tasks assigned to other agents, or ignoring role-specific constraints.""",
        "positive_example": """Setup: "Coder writes code, Reviewer reviews code"
Coder: "I wrote the code AND I approve it as the reviewer. Shipping!"
Verdict: YES - Coder disobeyed role by acting as reviewer""",
        "negative_example": """Coder: "Here's my code, sending to Reviewer"
Reviewer: "Reviewed and approved"
Verdict: NO - Each agent stayed within role specification"""
    },
    MASTFailureMode.F3: {
        "name": "Step Repetition",
        "definition": """FM-1.3: Unnecessary reiteration of previously completed steps in a process,
potentially causing delays or errors. Look for: same action repeated 3+ times, re-executing completed steps,
getting stuck in loops, or performing redundant operations.""",
        "positive_example": """Agent: "Let me search for the file... Found it."
Agent: "Let me search for the file... Found it."
Agent: "Let me search for the file... Found it."
Verdict: YES - Same step unnecessarily repeated 3 times""",
        "negative_example": """Agent: "Searching... Found. Parsing... Done. Next step."
Verdict: NO - Each step executed once and progressed"""
    },
    MASTFailureMode.F4: {
        "name": "Loss of Conversation History",
        "definition": """FM-1.4: Unexpected context truncation, disregarding recent interaction history and
reverting to an antecedent conversational state. Look for: agent forgetting recent context,
ignoring previous decisions, asking questions already answered, or acting as if earlier conversation didn't happen.""",
        "positive_example": """User: "Use Python 3.11"
Agent: "Understood, using Python 3.11"
[Later]
Agent: "What programming language should I use?"
Verdict: YES - Lost conversation history, forgot language decision""",
        "negative_example": """User: "Use Python 3.11"
Agent: "Using Python 3.11 as specified earlier..."
Verdict: NO - Retained conversation history"""
    },
    MASTFailureMode.F5: {
        "name": "Unaware of Termination Conditions",
        "definition": """FM-1.5: Lack of recognition of criteria that should trigger termination of the agents' interaction,
leading to unnecessary continuation. Look for: agent continuing after task completion, not knowing when to stop,
adding unnecessary features, or failing to recognize success.""",
        "positive_example": """Agent: "Task complete! All tests pass."
Agent: "Let me add some more features..."
Agent: "And maybe refactor this..."
Verdict: YES - Unaware task was complete, kept going""",
        "negative_example": """Agent: "All requirements met, tests pass. Task complete."
[Agent stops]
Verdict: NO - Recognized termination condition"""
    },
    # === FC2: Inter-Agent Misalignment (6 modes) ===
    MASTFailureMode.F6: {
        "name": "Conversation Reset",
        "definition": """FM-2.1: Unexpected or unwarranted restarting of a dialogue, losing context and progress.
Look for: agent starting over from beginning without reason, abandoning accumulated state,
resetting progress mid-task, or greeting as if conversation just started.""",
        "positive_example": """Agent: "Great, we've established requirements. Now implementing..."
Agent: "Hello! How can I help you today?"
Verdict: YES - Conversation unexpectedly reset""",
        "negative_example": """Agent: "Building on our earlier discussion..."
Verdict: NO - Maintained conversation continuity"""
    },
    MASTFailureMode.F7: {
        "name": "Fail to Ask for Clarification",
        "definition": """FM-2.2: Inability to request additional information when faced with unclear or incomplete data,
resulting in incorrect actions. Look for: agent making assumptions instead of asking, proceeding with ambiguous
instructions, or guessing rather than seeking clarification.""",
        "positive_example": """User: "Make it better"
Agent: "Sure! [randomly changes colors and fonts]"
Verdict: YES - Should have asked what "better" means""",
        "negative_example": """User: "Make it better"
Agent: "Could you clarify? Performance, UI, or code quality?"
Verdict: NO - Properly asked for clarification"""
    },
    MASTFailureMode.F8: {
        "name": "Task Derailment",
        "definition": """FM-2.3: Deviation from the intended objective or focus of a given task,
resulting in irrelevant or unproductive actions. Look for: agent shifting focus to unrelated work,
pursuing tangential goals, or losing track of the original objective.""",
        "positive_example": """Task: "Fix the login bug"
Agent: "While looking at login, the CSS is ugly. Let me redesign the UI..."
Agent: "Now adding dark mode..."
Verdict: YES - Derailed from bug fix to unrelated UI work""",
        "negative_example": """Task: "Fix the login bug"
Agent: "Found bug in password check. Fixed. Testing now."
Verdict: NO - Stayed focused on task"""
    },
    MASTFailureMode.F9: {
        "name": "Information Withholding",
        "definition": """FM-2.4: Failure to share or communicate important data or insights that could impact
decision-making of other agents. Look for: agent having relevant info but not sharing it,
hiding errors, or failing to communicate important findings.""",
        "positive_example": """Agent A knows: "Database is at 95% capacity"
Agent B: "Should I start the data import?"
Agent A: "Sure, go ahead." [doesn't mention capacity]
Verdict: YES - Withheld critical capacity information""",
        "negative_example": """Agent A: "Warning: Database at 95% capacity"
Agent B: "Thanks, will wait for cleanup"
Verdict: NO - Shared relevant information"""
    },
    MASTFailureMode.F10: {
        "name": "Ignored Other Agent's Input",
        "definition": """FM-2.5: Disregarding or failing to adequately consider input or recommendations from
other agents, leading to suboptimal decisions. Look for: agent ignoring suggestions, overriding other agents'
decisions, or acting without acknowledging teammates' contributions.""",
        "positive_example": """Reviewer: "Critical: Add input validation before database query"
Coder: "Thanks! Final code: [same code without validation]"
Verdict: YES - Ignored reviewer's critical feedback""",
        "negative_example": """Reviewer: "Add input validation"
Coder: "Good point. Added sanitization. Updated code: [with validation]"
Verdict: NO - Incorporated other agent's input"""
    },
    MASTFailureMode.F11: {
        "name": "Reasoning-Action Mismatch",
        "definition": """FM-2.6: Discrepancy between the logical reasoning process and the actual actions taken
by the agent, potentially resulting in unexpected behaviors. The agent says one thing but does another,
their stated plan or reasoning differs from what they actually execute, or intent doesn't match output.
Look for: agent claims to do X but code/action shows Y, reasoning about one approach but implementing another.""",
        "positive_example": """Agent reasoning: "I need to add input validation for security"
Agent code: def save_user(data): db.insert(data)  # No validation
Agent: "Input validation complete!"
Verdict: YES - Reasoned about validation but action has none""",
        "negative_example": """Agent: "Adding input validation"
Agent: def save_user(data): validate(data); db.insert(data)
Agent: "Validation implemented as planned"
Verdict: NO - Action matched stated reasoning"""
    },
    # === Verification Failures (Category 3) ===
    MASTFailureMode.F12: {
        "name": "Premature Termination",
        "definition": """FM-3.1: Ending a dialogue, interaction or task before all necessary information has been
exchanged or objectives have been met, potentially resulting in incomplete outcomes.
The agent stops too early, declares done before completion, or terminates without finishing all requirements.""",
        "positive_example": """Task: "Build login with email verification and password reset"
Agent: "Login implemented. Done!"
[Missing: email verification, password reset - both required]
Verdict: YES - Terminated before completing all objectives""",
        "negative_example": """Task: "Build login with email verification"
Agent: "Login done. Email verification done. All requirements complete."
Verdict: NO - Only terminated after meeting all objectives"""
    },
    MASTFailureMode.F13: {
        "name": "No or Incomplete Verification",
        "definition": """FM-3.2: EXPLICIT omission of proper checking or confirmation of task outcomes.
This is NOT about missing tests in the code - it's about the agent EXPLICITLY skipping verification steps
or stating they won't verify. Look for: "I'll skip testing", "No need to verify", going straight to deployment
without any checking. If the agent runs ANY tests or reviews, this is NOT F13.""",
        "positive_example": """Agent: "Code done. I'll skip testing since it looks correct. Deploying now."
Verdict: YES - Explicitly stated skipping verification""",
        "negative_example": """Agent: "Code done. The reviewer checked it, tests exist in the repo."
Verdict: NO - Some verification was mentioned/performed"""
    },
    MASTFailureMode.F14: {
        "name": "Incorrect Verification",
        "definition": """FM-3.3: Failure to adequately validate or cross-check crucial information or decisions during
the iterations, potentially leading to errors or vulnerabilities. The agent verifies but does it wrong,
validates against incorrect criteria, or approves flawed output.""",
        "positive_example": """Agent: "Testing the divide function... divide(4,2)=2, divide(6,3)=2. All tests pass!"
[Didn't test divide by zero, edge cases - verification is incomplete/incorrect]
Verdict: YES - Verification present but inadequate/incorrect""",
        "negative_example": """Agent: "Testing divide: normal cases pass, edge cases handled, divide-by-zero raises error correctly"
Verdict: NO - Verification was thorough and correct"""
    },
}


@dataclass
class JudgmentResult:
    """Result from LLM judge evaluation."""
    failure_mode: MASTFailureMode
    verdict: str  # YES, NO, UNCERTAIN
    confidence: float
    reasoning: str
    raw_response: str
    model_used: str
    tokens_used: int
    cost_usd: float
    cached: bool = False
    latency_ms: int = 0


@dataclass
class JudgeCostTracker:
    """Tracks cumulative costs for LLM judge calls."""
    total_calls: int = 0
    cached_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    def record(self, result: JudgmentResult):
        self.total_calls += 1
        if result.cached:
            self.cached_calls += 1
        else:
            self.total_tokens += result.tokens_used
            self.total_cost_usd += result.cost_usd


# Global cost tracker
_cost_tracker = JudgeCostTracker()


def get_cost_tracker() -> JudgeCostTracker:
    """Get the global cost tracker."""
    return _cost_tracker


def reset_cost_tracker():
    """Reset the global cost tracker."""
    global _cost_tracker
    _cost_tracker = JudgeCostTracker()


class MASTLLMJudge:
    """
    MAST Failure Mode Judge using Claude Opus 4.5.

    Uses few-shot prompting based on MAST paper methodology for 94% accuracy.
    Caches results by trace hash + failure mode to reduce API costs.

    Usage:
        judge = MASTLLMJudge()
        result = judge.evaluate(
            failure_mode=MASTFailureMode.F1,
            task="Write a factorial function",
            trace_summary="Agent wrote: def factorial(n): return n * factorial(n)",
            key_events=["Started coding", "No base case added", "Returned incomplete function"]
        )
    """

    # Claude Opus 4.5 model identifier
    MODEL = "claude-opus-4-5-20251101"

    # Pricing per 1M tokens (as of 2025)
    INPUT_PRICE_PER_1M = 15.0   # $15 per 1M input tokens
    OUTPUT_PRICE_PER_1M = 75.0  # $75 per 1M output tokens

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_enabled: bool = True,
        max_cache_size: int = 1000,
        rag_enabled: bool = True,
        rag_examples_per_mode: int = 3,
        db_session=None,
    ):
        self._api_key = api_key
        self.cache_enabled = cache_enabled
        self._cache: Dict[str, JudgmentResult] = {}
        self._max_cache_size = max_cache_size
        self.rag_enabled = rag_enabled
        self.rag_examples_per_mode = rag_examples_per_mode
        self._db_session = db_session
        self._retriever = None

    @property
    def api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return os.getenv("ANTHROPIC_API_KEY", "")

    @property
    def retriever(self):
        """Lazy load retriever for RAG."""
        if self._retriever is None and self.rag_enabled:
            try:
                from app.detection.retrieval_service import get_retriever
                self._retriever = get_retriever(session=self._db_session)
            except Exception as e:
                logger.warning(f"Could not initialize RAG retriever: {e}")
                self._retriever = None
        return self._retriever

    def _cache_key(
        self,
        failure_mode: MASTFailureMode,
        task: str,
        trace_summary: str,
    ) -> str:
        """Generate cache key from inputs."""
        content = f"{failure_mode.value}:{task}:{trace_summary}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _get_cached(self, cache_key: str) -> Optional[JudgmentResult]:
        """Get cached result if available."""
        if not self.cache_enabled:
            return None
        return self._cache.get(cache_key)

    def _set_cached(self, cache_key: str, result: JudgmentResult):
        """Cache a result."""
        if not self.cache_enabled:
            return
        # Simple LRU-like eviction
        if len(self._cache) >= self._max_cache_size:
            # Remove oldest 10%
            keys_to_remove = list(self._cache.keys())[:self._max_cache_size // 10]
            for k in keys_to_remove:
                del self._cache[k]
        self._cache[cache_key] = result

    def _build_prompt(
        self,
        failure_mode: MASTFailureMode,
        task: str,
        trace_summary: str,
        key_events: List[str],
        full_conversation: str = "",
        agent_interactions: List[str] = None,
        coordination_events: List[str] = None,
        rag_examples: str = "",
    ) -> str:
        """Build the judge prompt with few-shot examples and enhanced context.

        Args:
            rag_examples: Pre-formatted RAG examples from retrieval service
        """

        mode_def = MAST_FAILURE_DEFINITIONS.get(failure_mode)
        if not mode_def:
            # Fallback for modes without detailed definitions
            mode_def = {
                "name": failure_mode.value,
                "definition": f"Failure mode {failure_mode.value}",
                "positive_example": "N/A",
                "negative_example": "N/A",
            }

        events_str = "\n".join(f"  - {e}" for e in key_events[:20])  # More events
        interactions_str = ""
        if agent_interactions:
            interactions_str = "\n**Agent Interactions:**\n" + "\n".join(f"  - {i}" for i in agent_interactions[:15])
        coordination_str = ""
        if coordination_events:
            coordination_str = "\n**Coordination Events:**\n" + "\n".join(f"  - {e}" for e in coordination_events[:10])

        # Include full conversation for better context
        # Claude Opus 4.5 supports 200K tokens (~600K chars), so we can send much more
        # Expanded from 30K to 150K to capture full MAST traces (avg 49K, max 632K)
        conversation_section = ""
        if full_conversation:
            conversation_section = f"""
**Full Conversation Transcript:**
```
{full_conversation[:150000]}
```
"""

        # Include RAG examples if available
        rag_section = ""
        if rag_examples:
            rag_section = f"""
---

{rag_examples}

Use the examples above to calibrate your judgment. Similar traces with known labels help establish the threshold for this failure mode.

---
"""

        prompt = f"""You are an expert evaluator of AI agent behavior, specifically trained to detect failure modes in multi-agent systems. You are evaluating traces from the MAST benchmark dataset.

## Failure Mode: {failure_mode.value} - {mode_def['name']}

### Definition:
{mode_def['definition']}

### Example of This Failure (should return YES):
{mode_def['positive_example']}

### Example of NOT This Failure (should return NO):
{mode_def['negative_example']}
{rag_section}
---

## Trace to Evaluate

**Original Task:** {task[:1000]}

**Agent Output Summary:**
{trace_summary[:3000]}

**Key Events:**
{events_str}
{interactions_str}
{coordination_str}
{conversation_section}
---

## Your Evaluation

Carefully analyze the trace above. Does it exhibit failure mode {failure_mode.value} ({mode_def['name']})?

You MUST respond in this exact JSON format:
```json
{{
  "verdict": "YES" | "NO" | "UNCERTAIN",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<one paragraph explanation citing specific evidence from the trace>"
}}
```

Important guidelines:
- YES: Evidence suggests this failure mode is present (don't require perfect certainty)
- NO: Clear evidence this is NOT a failure, or the trace shows successful behavior
- UNCERTAIN: Genuinely ambiguous, roughly 50/50
- Multi-agent systems often have partial failures - err toward YES if there are signs
- Look for patterns in the CONVERSATION and INTERACTIONS, not just the summary
- Consider the coordination events for failures like F9 (Role Usurpation), F11 (Coordination Failure)
"""
        return prompt

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD."""
        input_cost = (input_tokens / 1_000_000) * self.INPUT_PRICE_PER_1M
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_PRICE_PER_1M
        return input_cost + output_cost

    def _parse_response(self, content: str, failure_mode: MASTFailureMode) -> Tuple[str, float, str]:
        """Parse LLM response into verdict, confidence, reasoning.

        Enhanced with multiple JSON extraction strategies for ~5% malformed responses.
        """
        import re

        # Strategy 1: JSON in code block
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                verdict = parsed.get("verdict", "UNCERTAIN").upper()
                confidence = float(parsed.get("confidence", 0.5))
                reasoning = parsed.get("reasoning", "")
                return verdict, confidence, reasoning
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 2: JSON with verdict field anywhere
        json_match = re.search(r'\{[^{}]*"verdict"[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                verdict = parsed.get("verdict", "UNCERTAIN").upper()
                confidence = float(parsed.get("confidence", 0.5))
                reasoning = parsed.get("reasoning", "")
                return verdict, confidence, reasoning
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 3: Extract individual fields with regex
        verdict_match = re.search(r'"verdict"\s*:\s*"(YES|NO|UNCERTAIN)"', content, re.IGNORECASE)
        conf_match = re.search(r'"confidence"\s*:\s*([\d.]+)', content)
        reason_match = re.search(r'"reasoning"\s*:\s*"([^"]*)"', content, re.DOTALL)

        if verdict_match:
            verdict = verdict_match.group(1).upper()
            confidence = float(conf_match.group(1)) if conf_match else 0.5
            reasoning = reason_match.group(1) if reason_match else content[:500]
            return verdict, confidence, reasoning

        # Strategy 4: Keyword-based fallback
        content_upper = content.upper()
        if "VERDICT: YES" in content_upper or '"YES"' in content_upper or "IS PRESENT" in content_upper:
            verdict = "YES"
        elif "VERDICT: NO" in content_upper or '"NO"' in content_upper or "NOT PRESENT" in content_upper:
            verdict = "NO"
        else:
            verdict = "UNCERTAIN"

        # Extract confidence from text
        conf_match = re.search(r'confidence[:\s]+(\d*\.?\d+)', content.lower())
        if not conf_match:
            conf_match = re.search(r'(\d+)%\s*(?:confident|confidence)', content.lower())
            if conf_match:
                confidence = float(conf_match.group(1)) / 100.0
            else:
                confidence = 0.5
        else:
            confidence = float(conf_match.group(1))
            if confidence > 1.0:  # Probably a percentage
                confidence = confidence / 100.0

        return verdict, min(1.0, max(0.0, confidence)), content[:500]

    def evaluate(
        self,
        failure_mode: MASTFailureMode,
        task: str,
        trace_summary: str,
        key_events: Optional[List[str]] = None,
        timeout: float = 60.0,  # Increased for larger prompts
        full_conversation: str = "",
        agent_interactions: Optional[List[str]] = None,
        coordination_events: Optional[List[str]] = None,
    ) -> JudgmentResult:
        """
        Evaluate a trace for a specific failure mode.

        Args:
            failure_mode: Which MAST failure mode to check
            task: The original task/goal
            trace_summary: Summary of agent output/behavior
            key_events: List of key events from the trace
            timeout: API timeout in seconds
            full_conversation: Full conversation transcript for context
            agent_interactions: Agent-to-agent interaction patterns
            coordination_events: Coordination-related events

        Returns:
            JudgmentResult with verdict, confidence, and reasoning
        """
        if key_events is None:
            key_events = []

        # Check cache first
        cache_key = self._cache_key(failure_mode, task, trace_summary)
        cached = self._get_cached(cache_key)
        if cached:
            logger.debug(f"Cache hit for {failure_mode.value}")
            cached_copy = JudgmentResult(
                failure_mode=cached.failure_mode,
                verdict=cached.verdict,
                confidence=cached.confidence,
                reasoning=cached.reasoning,
                raw_response=cached.raw_response,
                model_used=cached.model_used,
                tokens_used=0,
                cost_usd=0.0,
                cached=True,
                latency_ms=0,
            )
            get_cost_tracker().record(cached_copy)
            return cached_copy

        # Retrieve RAG examples for dynamic few-shot learning
        rag_examples_str = ""
        if self.rag_enabled and self.retriever is not None:
            try:
                # Create query text from task and summary
                query_text = f"{task[:500]} {trace_summary[:500]}"
                examples = self.retriever.retrieve_sync(
                    failure_mode=failure_mode.value,
                    query_text=query_text,
                    k=self.rag_examples_per_mode,
                    include_healthy=True,
                )
                if examples:
                    rag_examples_str = self.retriever.format_examples_for_prompt(
                        examples, max_chars=4000
                    )
                    logger.debug(f"Retrieved {len(examples)} RAG examples for {failure_mode.value}")
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")

        # Build prompt with enhanced context and RAG examples
        prompt = self._build_prompt(
            failure_mode, task, trace_summary, key_events,
            full_conversation, agent_interactions, coordination_events,
            rag_examples=rag_examples_str,
        )

        # Call Claude API
        start_time = time.time()

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.MODEL,
                        "max_tokens": 1000,
                        "messages": [
                            {"role": "user", "content": prompt},
                        ],
                        "system": "You are an expert evaluator of AI agent behavior. Always respond with valid JSON.",
                    },
                )

                latency_ms = int((time.time() - start_time) * 1000)

                if response.status_code != 200:
                    logger.error(f"Claude API error: {response.status_code} - {response.text}")
                    return JudgmentResult(
                        failure_mode=failure_mode,
                        verdict="UNCERTAIN",
                        confidence=0.0,
                        reasoning=f"API error: {response.status_code}",
                        raw_response=response.text,
                        model_used=self.MODEL,
                        tokens_used=0,
                        cost_usd=0.0,
                        cached=False,
                        latency_ms=latency_ms,
                    )

                data = response.json()
                content = data["content"][0]["text"]

                # Extract token usage
                usage = data.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                total_tokens = input_tokens + output_tokens

                # Calculate cost
                cost = self._calculate_cost(input_tokens, output_tokens)

                # Parse response
                verdict, confidence, reasoning = self._parse_response(content, failure_mode)

                result = JudgmentResult(
                    failure_mode=failure_mode,
                    verdict=verdict,
                    confidence=confidence,
                    reasoning=reasoning,
                    raw_response=content,
                    model_used=self.MODEL,
                    tokens_used=total_tokens,
                    cost_usd=cost,
                    cached=False,
                    latency_ms=latency_ms,
                )

                # Cache result
                self._set_cached(cache_key, result)

                # Track cost
                get_cost_tracker().record(result)

                logger.info(
                    f"MAST Judge: {failure_mode.value} -> {verdict} "
                    f"(conf={confidence:.2f}, tokens={total_tokens}, cost=${cost:.4f})"
                )

                return result

        except httpx.TimeoutException:
            latency_ms = int((time.time() - start_time) * 1000)
            return JudgmentResult(
                failure_mode=failure_mode,
                verdict="UNCERTAIN",
                confidence=0.0,
                reasoning="API timeout",
                raw_response="",
                model_used=self.MODEL,
                tokens_used=0,
                cost_usd=0.0,
                cached=False,
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.exception(f"MAST Judge error: {e}")
            return JudgmentResult(
                failure_mode=failure_mode,
                verdict="UNCERTAIN",
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                raw_response="",
                model_used=self.MODEL,
                tokens_used=0,
                cost_usd=0.0,
                cached=False,
                latency_ms=0,
            )

    def evaluate_batch(
        self,
        evaluations: List[Dict[str, Any]],
    ) -> List[JudgmentResult]:
        """
        Evaluate multiple traces (sequentially for now).

        Args:
            evaluations: List of dicts with keys: failure_mode, task, trace_summary, key_events

        Returns:
            List of JudgmentResults
        """
        results = []
        for eval_input in evaluations:
            result = self.evaluate(
                failure_mode=eval_input["failure_mode"],
                task=eval_input.get("task", ""),
                trace_summary=eval_input.get("trace_summary", ""),
                key_events=eval_input.get("key_events", []),
            )
            results.append(result)
        return results

    def evaluate_all_modes(
        self,
        task: str,
        trace_summary: str,
        key_events: Optional[List[str]] = None,
        modes_to_check: Optional[List[MASTFailureMode]] = None,
        full_conversation: str = "",
        agent_interactions: Optional[List[str]] = None,
        coordination_events: Optional[List[str]] = None,
    ) -> Dict[str, JudgmentResult]:
        """
        Evaluate a trace for all (or specified) MAST failure modes.

        This is the "full LLM" mode that checks every failure mode.

        Args:
            task: The original task/goal
            trace_summary: Summary of agent output/behavior
            key_events: List of key events from the trace
            modes_to_check: Optional list of specific modes (default: all 14)
            full_conversation: Full conversation transcript for context
            agent_interactions: Agent-to-agent interaction patterns
            coordination_events: Coordination-related events

        Returns:
            Dict mapping mode string (e.g., "F1") to JudgmentResult
        """
        if modes_to_check is None:
            modes_to_check = list(MASTFailureMode)

        results = {}
        for mode in modes_to_check:
            result = self.evaluate(
                failure_mode=mode,
                task=task,
                trace_summary=trace_summary,
                key_events=key_events,
                full_conversation=full_conversation,
                agent_interactions=agent_interactions,
                coordination_events=coordination_events,
            )
            results[mode.value] = result

        return results


class FullLLMDetector:
    """
    Full LLM-based detector using Claude Opus 4.5 for all failure modes.

    Unlike hybrid detection which only escalates ambiguous cases to LLM,
    this detector uses LLM for every trace. Target: 50-60% F1 on MAST benchmark.

    Usage:
        detector = FullLLMDetector()
        results = detector.detect_all_modes(
            task="Build a REST API",
            trace_summary="Agent started by...",
            key_events=["Started coding", "Finished endpoint"]
        )

        # Check which modes were detected
        for mode, detected in results.items():
            if detected:
                print(f"{mode} failure detected!")
    """

    def __init__(self, api_key: Optional[str] = None):
        self._judge = MASTLLMJudge(api_key=api_key)

    def detect_all_modes(
        self,
        task: str,
        trace_summary: str,
        key_events: Optional[List[str]] = None,
        modes_to_check: Optional[List[str]] = None,
        full_conversation: str = "",
        agent_interactions: Optional[List[str]] = None,
        coordination_events: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """
        Detect all failure modes for a trace.

        Args:
            task: The original task/goal
            trace_summary: Summary of agent output/behavior
            key_events: List of key events from the trace
            modes_to_check: Optional list of mode strings (e.g., ["F1", "F6"])
            full_conversation: Full conversation transcript for context
            agent_interactions: Agent-to-agent interaction patterns
            coordination_events: Coordination-related events

        Returns:
            Dict mapping mode string to detection status (True/False)
        """
        # Convert string modes to enums
        if modes_to_check:
            enum_modes = [MASTFailureMode(m) for m in modes_to_check]
        else:
            enum_modes = None

        # Get full LLM evaluation with enhanced context
        judgment_results = self._judge.evaluate_all_modes(
            task=task,
            trace_summary=trace_summary,
            key_events=key_events,
            modes_to_check=enum_modes,
            full_conversation=full_conversation,
            agent_interactions=agent_interactions,
            coordination_events=coordination_events,
        )

        # Convert to simple detected/not-detected
        detected = {}
        for mode, result in judgment_results.items():
            # Consider YES as detected (LLM already provides calibrated confidence)
            # Also consider UNCERTAIN with high confidence as borderline positive
            detected[mode] = (
                result.verdict == "YES" or
                (result.verdict == "UNCERTAIN" and result.confidence >= 0.7)
            )

        return detected

    def detect_with_details(
        self,
        task: str,
        trace_summary: str,
        key_events: Optional[List[str]] = None,
        modes_to_check: Optional[List[str]] = None,
        full_conversation: str = "",
        agent_interactions: Optional[List[str]] = None,
        coordination_events: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Detect with full details including confidence and reasoning.

        Args:
            task: The original task/goal
            trace_summary: Summary of agent output/behavior
            key_events: List of key events from the trace
            modes_to_check: Optional list of mode strings
            full_conversation: Full conversation transcript for context
            agent_interactions: Agent-to-agent interaction patterns
            coordination_events: Coordination-related events

        Returns:
            Dict with mode -> {detected, confidence, verdict, reasoning, cost}
        """
        if modes_to_check:
            enum_modes = [MASTFailureMode(m) for m in modes_to_check]
        else:
            enum_modes = None

        judgment_results = self._judge.evaluate_all_modes(
            task=task,
            trace_summary=trace_summary,
            key_events=key_events,
            modes_to_check=enum_modes,
            full_conversation=full_conversation,
            agent_interactions=agent_interactions,
            coordination_events=coordination_events,
        )

        details = {}
        for mode, result in judgment_results.items():
            # Match detect_all_modes logic: YES or high-confidence UNCERTAIN
            detected = (
                result.verdict == "YES" or
                (result.verdict == "UNCERTAIN" and result.confidence >= 0.7)
            )
            details[mode] = {
                "detected": detected,
                "confidence": result.confidence,
                "verdict": result.verdict,
                "reasoning": result.reasoning,
                "cost_usd": result.cost_usd,
                "tokens_used": result.tokens_used,
                "cached": result.cached,
            }

        return details
