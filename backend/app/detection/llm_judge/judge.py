"""
MAST LLM Judge Core Class
==========================

Main judge class for evaluating traces using Claude models.
Uses few-shot prompting based on MAST paper methodology for 94% accuracy.
"""

import hashlib
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from anthropic import Anthropic, APIError, RateLimitError, APITimeoutError

from ._enums import MASTFailureMode
from ._dataclasses import JudgmentResult, ClaudeModelConfig
from ._models import (
    # Multi-provider support (primary)
    MODELS,
    ModelConfig,
    ModelProvider,
    get_model_config,
    # Legacy backward compatibility
    CLAUDE_MODELS,
    DEFAULT_MODEL_KEY,
    get_cost_tracker,
)
from ._prompts import (
    MAST_FAILURE_DEFINITIONS,
    CHAIN_OF_THOUGHT_PROMPTS,
    KNOWLEDGE_AUGMENTED_MODES,
)

logger = logging.getLogger(__name__)


class MASTLLMJudge:
    """
    MAST Failure Mode Judge using Claude models or GPT-4 (fallback).

    Supports multiple Claude models for performance vs cost optimization:
    - opus-4.5: Highest quality ($15/$75 per 1M tokens)
    - opus-4.5-thinking: With extended thinking (+$10/1M thinking tokens)
    - sonnet-4: Balanced ($3/$15 per 1M tokens)
    - sonnet-4-thinking: With extended thinking
    - sonnet-3.5: Previous gen ($3/$15 per 1M tokens)
    - haiku-3.5: Fast and cheap ($0.80/$4 per 1M tokens)

    Uses few-shot prompting based on MAST paper methodology for 94% accuracy.
    Caches results by trace hash + failure mode to reduce API costs.

    Supports automatic fallback to OpenAI GPT-4 if Claude API fails.

    Usage:
        # Default (Opus 4.5)
        judge = MASTLLMJudge()

        # Cost-optimized
        judge = MASTLLMJudge(model_key="haiku-3.5")

        # Extended thinking for complex cases
        judge = MASTLLMJudge(model_key="sonnet-4-thinking")

        result = judge.evaluate(
            failure_mode=MASTFailureMode.F1,
            task="Write a factorial function",
            trace_summary="Agent wrote: def factorial(n): return n * factorial(n)",
            key_events=["Started coding", "No base case added", "Returned incomplete function"]
        )
    """

    # OpenAI GPT-4 fallback (class constants for backward compat)
    OPENAI_MODEL = "gpt-4o"
    OPENAI_INPUT_PRICE_PER_1M = 2.50
    OPENAI_OUTPUT_PRICE_PER_1M = 10.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
        cache_enabled: bool = True,
        max_cache_size: int = 1000,
        rag_enabled: bool = True,
        rag_examples_per_mode: int = 3,
        db_session=None,
        use_openai_fallback: bool = False,
        model_key: str = DEFAULT_MODEL_KEY,
    ):
        # Model configuration - try multi-provider first, fallback to Claude-only
        self.model_key = model_key

        if model_key in MODELS:
            # Use new multi-provider registry
            self._multi_provider_config = get_model_config(model_key)
            self._provider = self._multi_provider_config.provider

            # Create backward-compatible ClaudeModelConfig view
            self.model_config = ClaudeModelConfig(
                model_id=self._multi_provider_config.model_id,
                input_price_per_1m=self._multi_provider_config.input_price_per_1m,
                output_price_per_1m=self._multi_provider_config.output_price_per_1m,
                thinking_price_per_1m=self._multi_provider_config.thinking_price_per_1m,
                use_extended_thinking=self._multi_provider_config.supports_thinking and "thinking" in model_key,
                thinking_budget=self._multi_provider_config.thinking_budget,
                context_window=self._multi_provider_config.context_window,
            )
        elif model_key in CLAUDE_MODELS:
            # Backward compatibility with legacy Claude-only config
            self.model_config = CLAUDE_MODELS[model_key]
            self._multi_provider_config = ModelConfig(
                model_id=self.model_config.model_id,
                provider=ModelProvider.ANTHROPIC,
                input_price_per_1m=self.model_config.input_price_per_1m,
                output_price_per_1m=self.model_config.output_price_per_1m,
                thinking_price_per_1m=self.model_config.thinking_price_per_1m,
                supports_thinking=self.model_config.use_extended_thinking,
                thinking_budget=self.model_config.thinking_budget,
                context_window=self.model_config.context_window,
            )
            self._provider = ModelProvider.ANTHROPIC
        else:
            raise ValueError(
                f"Unknown model_key '{model_key}'. "
                f"Available multi-provider: {list(MODELS.keys())}, "
                f"Legacy Claude: {list(CLAUDE_MODELS.keys())}"
            )

        # For backward compatibility, expose MODEL as instance attribute
        self.MODEL = self.model_config.model_id
        self.INPUT_PRICE_PER_1M = self.model_config.input_price_per_1m
        self.OUTPUT_PRICE_PER_1M = self.model_config.output_price_per_1m

        self._api_key = api_key
        self._openai_api_key = openai_api_key
        self._google_api_key = google_api_key
        self.cache_enabled = cache_enabled
        self._cache: Dict[str, JudgmentResult] = {}
        self._max_cache_size = max_cache_size
        self.rag_enabled = rag_enabled
        self.rag_examples_per_mode = rag_examples_per_mode
        self._db_session = db_session
        self._retriever = None
        self.use_openai_fallback = use_openai_fallback

        # Initialize Anthropic client (lazy - will be created on first use)
        self._anthropic_client: Optional[Anthropic] = None

        logger.info(
            f"MASTLLMJudge initialized with model={self.model_config.model_id}, "
            f"extended_thinking={self.model_config.use_extended_thinking}"
        )

    @property
    def api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return os.getenv("ANTHROPIC_API_KEY", "")

    @property
    def openai_api_key(self) -> str:
        if self._openai_api_key:
            return self._openai_api_key
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def google_api_key(self) -> str:
        """Get Google API key from explicit setting or environment."""
        if self._google_api_key:
            return self._google_api_key
        return os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))

    @property
    def anthropic_client(self) -> Anthropic:
        """Lazy initialization of Anthropic client."""
        if self._anthropic_client is None:
            self._anthropic_client = Anthropic(api_key=self.api_key)
        return self._anthropic_client

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

    def _generate_timeline(self, full_conversation: str, sample_every: int = 5) -> str:
        """Generate a conversation timeline by sampling turns.

        Phase 3 Enhancement: Provides high-level flow context to LLM.

        Args:
            full_conversation: Full conversation text
            sample_every: Sample every Nth turn (default: 5)

        Returns:
            Formatted timeline string
        """
        if not full_conversation:
            return ""

        lines = full_conversation.split('\n')
        timeline_entries = []

        # Extract turn-like patterns (various formats)
        turn_count = 0
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()

            # Detect turn markers (various formats)
            is_turn = (
                line_lower.startswith('turn ') or
                line_lower.startswith('agent:') or
                line_lower.startswith('user:') or
                line_lower.startswith('[agent') or
                line_lower.startswith('[user') or
                (i > 0 and len(line) > 20 and not line.startswith(' '))  # Likely new turn
            )

            if is_turn:
                turn_count += 1

                # Sample every Nth turn
                if turn_count % sample_every == 0 or turn_count <= 3:  # Always include first 3
                    # Get preview of content (next few lines or rest of current line)
                    preview = line[:120].replace('\n', ' ').strip()
                    if len(line) > 120:
                        preview += "..."

                    timeline_entries.append(f"Turn {turn_count}: {preview}")

                    # Limit timeline to 30 entries
                    if len(timeline_entries) >= 30:
                        break

        if not timeline_entries:
            return ""

        return "\n".join(timeline_entries)

    def _retrieve_few_shot_examples(
        self,
        failure_mode: MASTFailureMode,
        task: str,
        framework: str = None,
        k: int = 2
    ) -> str:
        """
        Retrieve few-shot examples from MAST trace embeddings.

        Phase 4 Enhancement: Uses pgvector similarity search to find
        relevant MAST traces with ground truth annotations as in-context examples.

        Args:
            failure_mode: MAST failure mode to find examples for
            task: Task description to match against
            framework: Optional framework filter (ChatDev, MetaGPT, etc.)
            k: Number of examples to retrieve (default: 2)

        Returns:
            Formatted string with few-shot examples, or empty string if unavailable
        """
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from app.config import get_settings
            from app.storage.models import MASTTraceEmbedding

            # Create database session
            settings = get_settings()
            engine = create_engine(settings.database_url)
            Session = sessionmaker(bind=engine)
            session = Session()

            try:
                # Find similar traces
                similar_traces = MASTTraceEmbedding.find_similar_traces(
                    session=session,
                    query_task=task,
                    failure_mode=failure_mode.value,
                    framework=framework,
                    k=k,
                    min_similarity=0.65  # Lower threshold for Phase 4
                )

                if not similar_traces:
                    logger.debug(f"No few-shot examples found for {failure_mode.value}")
                    return ""

                # Format examples
                examples = []
                for i, trace in enumerate(similar_traces, 1):
                    example = f"""
### Example {i} (Ground Truth: {failure_mode.value})
{trace.formatted_example()}
"""
                    examples.append(example.strip())

                formatted = "\n\n".join(examples)

                logger.info(f"Retrieved {len(similar_traces)} few-shot examples for {failure_mode.value}")
                return formatted

            finally:
                session.close()

        except Exception as e:
            logger.debug(f"Few-shot examples unavailable (optional): {e}")
            return ""

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
        knowledge_context: str = "",
        framework: str = "",
    ) -> str:
        """Build the judge prompt with few-shot examples and enhanced context.

        Phase 3 Enhancement: Now includes conversation timeline for better context.
        Phase 5 Enhancement: Framework-aware prompting for n8n and MAST.

        Args:
            rag_examples: Pre-formatted RAG examples from retrieval service
            knowledge_context: Domain knowledge for modes like F3, F4, F9
            framework: Source framework (n8n, ChatDev, MetaGPT, etc.)
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

        # Phase 3: Generate conversation timeline for high-level context
        timeline_str = ""
        if full_conversation:
            timeline = self._generate_timeline(full_conversation, sample_every=5)
            if timeline:
                timeline_str = f"""
**Conversation Timeline (sampled every 5 turns):**
{timeline}
"""

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

        # Include RAG examples if available (contrastive format)
        rag_section = ""
        if rag_examples:
            rag_section = f"""
---

## Reference Examples for Calibration

Use these examples to calibrate your judgment. Pay special attention to:
- **FAILURE EXAMPLES**: What makes these clear failures of this mode
- **TRICKY NON-FAILURES**: Why these LOOK like failures but aren't (key for avoiding false positives)
- **HEALTHY EXAMPLES**: What normal successful behavior looks like

{rag_examples}

---
"""

        # Add Chain-of-Thought section for hard semantic modes (F6, F8)
        cot_section = ""
        if failure_mode in CHAIN_OF_THOUGHT_PROMPTS:
            cot_section = f"""
---

{CHAIN_OF_THOUGHT_PROMPTS[failure_mode]}
"""

        # Add knowledge context section for modes that need it (F3, F4, F9)
        knowledge_section = ""
        if knowledge_context:
            knowledge_section = f"""
---

## Domain Knowledge Reference

{knowledge_context}

---
"""

        # Framework-aware context
        framework_lower = framework.lower() if framework else ""
        if "n8n" in framework_lower:
            framework_context = """You are evaluating traces from **n8n workflow automation**. Key differences from conversational multi-agent systems:
- Traces consist of node executions, not conversational turns
- Each "[Node Name] {...}" block represents a node's output
- Look for: repeated node executions, data flow issues, error propagation between nodes
- Workflow failures manifest as: stuck loops, invalid data passing, missing error handling

"""
        elif any(x in framework_lower for x in ["chatdev", "metagpt", "autogen", "crewai"]):
            framework_context = f"""You are evaluating traces from **{framework}** (conversational multi-agent framework).
- Traces are dialogue between multiple AI agents (Programmer, Designer, Reviewer, etc.)
- Look for: role violations, communication breakdowns, coordination failures
- Typical failures: agents talking past each other, ignoring instructions, scope creep

"""
        else:
            framework_context = """You are evaluating traces from the MAST benchmark dataset (multi-agent systems).

"""

        prompt = f"""You are an expert evaluator of AI agent behavior, specifically trained to detect failure modes in multi-agent systems and workflow automation.

{framework_context}## Failure Mode: {failure_mode.value} - {mode_def['name']}

### Definition:
{mode_def['definition']}

### Example of This Failure (should return YES):
{mode_def['positive_example']}

### Example of NOT This Failure (should return NO):
{mode_def['negative_example']}
{rag_section}{knowledge_section}{cot_section}
---

## Trace to Evaluate

**Original Task:** {task[:1000]}

**Agent Output Summary:**
{trace_summary[:3000]}

**Key Events:**
{events_str}
{interactions_str}
{coordination_str}
{timeline_str}
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

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        is_openai: bool = False,
        is_gemini: bool = False,
        thinking_tokens: int = 0,
    ) -> float:
        """Calculate cost in USD including thinking tokens for extended thinking."""
        if is_gemini or self._provider == ModelProvider.GOOGLE:
            # Use multi-provider config for Gemini
            input_cost = (input_tokens / 1_000_000) * self._multi_provider_config.input_price_per_1m
            output_cost = (output_tokens / 1_000_000) * self._multi_provider_config.output_price_per_1m
            thinking_cost = 0.0
        elif is_openai:
            input_cost = (input_tokens / 1_000_000) * self.OPENAI_INPUT_PRICE_PER_1M
            output_cost = (output_tokens / 1_000_000) * self.OPENAI_OUTPUT_PRICE_PER_1M
            thinking_cost = 0.0
        else:
            input_cost = (input_tokens / 1_000_000) * self.INPUT_PRICE_PER_1M
            output_cost = (output_tokens / 1_000_000) * self.OUTPUT_PRICE_PER_1M
            # Thinking tokens are charged at thinking_price_per_1m
            thinking_cost = (thinking_tokens / 1_000_000) * self.model_config.thinking_price_per_1m
        return input_cost + output_cost + thinking_cost

    def _call_openai(
        self,
        prompt: str,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> Tuple[str, int, int, float]:
        """Call OpenAI GPT-4 API with retry logic for rate limits.

        Returns:
            Tuple of (content, input_tokens, output_tokens, latency_ms)

        Raises:
            Exception if API call fails after retries
        """
        start_time = time.time()

        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.openai_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.OPENAI_MODEL,
                            "max_tokens": 1000,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are an expert evaluator of AI agent behavior. Always respond with valid JSON.",
                                },
                                {"role": "user", "content": prompt},
                            ],
                            "response_format": {"type": "json_object"},
                        },
                    )

                    latency_ms = int((time.time() - start_time) * 1000)

                    if response.status_code == 429:
                        # Rate limited - extract wait time and retry
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", "")

                        # Extract wait time from message (e.g., "try again in 3.83s")
                        wait_match = re.search(r'try again in ([\d.]+)s', error_msg)
                        if wait_match:
                            wait_time = float(wait_match.group(1)) + 0.5  # Add buffer
                        else:
                            wait_time = (2 ** attempt) * 2  # Exponential backoff

                        logger.warning(f"OpenAI rate limit hit (attempt {attempt + 1}/{max_retries}), waiting {wait_time:.1f}s")
                        time.sleep(wait_time)
                        continue

                    if response.status_code != 200:
                        raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

                    data = response.json()
                    content = data["choices"][0]["message"]["content"]

                    # Extract token usage
                    usage = data.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)

                    return content, input_tokens, output_tokens, latency_ms

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    logger.warning(f"OpenAI timeout (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                raise

        raise Exception(f"OpenAI API failed after {max_retries} retries")

    def _call_gemini(
        self,
        prompt: str,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> Tuple[str, int, int, float]:
        """Call Google Gemini API with retry logic.

        Returns:
            Tuple of (content, input_tokens, output_tokens, latency_ms)

        Raises:
            Exception if API call fails after retries
        """
        start_time = time.time()

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.MODEL}:generateContent"

        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        f"{url}?key={self.google_api_key}",
                        headers={"Content-Type": "application/json"},
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "maxOutputTokens": 1000,
                                "temperature": 0.3,
                            },
                            "safetySettings": [
                                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                            ]
                        },
                    )

                    latency_ms = int((time.time() - start_time) * 1000)

                    if response.status_code == 429:
                        # Rate limited
                        wait_time = (2 ** attempt) * 2
                        logger.warning(f"Gemini rate limit (attempt {attempt + 1}/{max_retries}), waiting {wait_time}s")
                        time.sleep(wait_time)
                        continue

                    if response.status_code != 200:
                        raise Exception(f"Gemini API error: {response.status_code} - {response.text[:200]}")

                    data = response.json()

                    # Handle potential safety blocks
                    if "candidates" not in data or not data["candidates"]:
                        block_reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
                        raise Exception(f"Gemini blocked response: {block_reason}")

                    content = data["candidates"][0]["content"]["parts"][0]["text"]

                    # Gemini provides usage metadata (sometimes)
                    usage = data.get("usageMetadata", {})
                    input_tokens = usage.get("promptTokenCount", len(prompt) // 4)
                    output_tokens = usage.get("candidatesTokenCount", len(content) // 4)

                    return content, input_tokens, output_tokens, latency_ms

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    logger.warning(f"Gemini timeout (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                raise

        raise Exception(f"Gemini API failed after {max_retries} retries")

    def _call_claude(
        self,
        prompt: str,
        timeout: float = 60.0,
    ) -> Tuple[str, int, int, int, float, str]:
        """Call Anthropic Claude API using official SDK.

        Returns:
            Tuple of (content, input_tokens, output_tokens, thinking_tokens, latency_ms, thinking_content)

        Raises:
            Various Anthropic API exceptions
        """
        start_time = time.time()

        # Build messages
        messages = [{"role": "user", "content": prompt}]
        system_prompt = "You are an expert evaluator of AI agent behavior. Always respond with valid JSON."

        # For extended thinking, prepend system context to user message
        if self.model_config.use_extended_thinking:
            messages[0]["content"] = system_prompt + "\n\n" + prompt
            system_prompt = None

        # Build API call parameters
        # Note: max_tokens must be > thinking.budget_tokens for extended thinking
        thinking_budget = self.model_config.thinking_budget or 0
        api_params = {
            "model": self.MODEL,
            "max_tokens": max(thinking_budget + 8000, 16000) if self.model_config.use_extended_thinking else 1000,
            "messages": messages,
        }

        if system_prompt:
            api_params["system"] = system_prompt

        if self.model_config.use_extended_thinking:
            api_params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.model_config.thinking_budget,
            }

        # Call Claude API
        response = self.anthropic_client.messages.create(**api_params)

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract content
        content = ""
        thinking_content = ""
        for block in response.content:
            if block.type == "thinking":
                thinking_content = block.thinking
            elif block.type == "text":
                content = block.text

        # Token usage
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        thinking_tokens = 0

        if self.model_config.use_extended_thinking:
            thinking_tokens = getattr(response.usage, 'cache_creation_input_tokens', 0) or 0
            if thinking_tokens == 0:
                thinking_tokens = len(thinking_content) // 4 if thinking_content else 0

        return content, input_tokens, output_tokens, thinking_tokens, latency_ms, thinking_content

    def _parse_response(self, content: str, failure_mode: MASTFailureMode) -> Tuple[str, float, str]:
        """Parse LLM response into verdict, confidence, reasoning.

        Enhanced with multiple JSON extraction strategies for ~5% malformed responses.
        """
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
        framework: str = "",
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
            framework: Source framework (n8n, ChatDev, MetaGPT, etc.)

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

        # Get knowledge context for modes that need domain knowledge (F3, F4, F9)
        knowledge_context = ""
        if failure_mode in KNOWLEDGE_AUGMENTED_MODES:
            try:
                from app.detection.knowledge_bases import get_knowledge_context
                knowledge_context = get_knowledge_context([KNOWLEDGE_AUGMENTED_MODES[failure_mode]])
                if knowledge_context:
                    logger.debug(f"Added knowledge context for {failure_mode.value} ({len(knowledge_context)} chars)")
            except ImportError:
                logger.warning("knowledge_bases module not available")
            except Exception as e:
                logger.warning(f"Could not load knowledge context: {e}")

        # Retrieve RAG examples for dynamic few-shot learning with contrastive examples
        rag_examples_str = ""
        if self.rag_enabled and self.retriever is not None:
            try:
                # Create query text from task and summary
                query_text = f"{task[:500]} {trace_summary[:500]}"

                # Use contrastive retrieval for better calibration
                contrastive_examples = self.retriever.retrieve_contrastive_sync(
                    failure_mode=failure_mode.value,
                    query_text=query_text,
                    k_positive=self.rag_examples_per_mode,
                    k_negative=2,
                    k_hard_negative=1,
                )

                total_examples = (
                    len(contrastive_examples.get("positives", [])) +
                    len(contrastive_examples.get("negatives", [])) +
                    len(contrastive_examples.get("hard_negatives", []))
                )

                if total_examples > 0:
                    rag_examples_str = self.retriever.format_contrastive_examples(
                        contrastive_examples, max_chars=6000
                    )
                    logger.debug(
                        f"Retrieved {total_examples} contrastive examples for {failure_mode.value} "
                        f"(+{len(contrastive_examples.get('positives', []))}, "
                        f"-{len(contrastive_examples.get('negatives', []))}, "
                        f"hard-{len(contrastive_examples.get('hard_negatives', []))})"
                    )
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")

        # Phase 4: If no RAG examples available, try few-shot from MAST embeddings
        if not rag_examples_str:
            try:
                few_shot_examples = self._retrieve_few_shot_examples(
                    failure_mode=failure_mode,
                    task=task,
                    framework=None,  # Could extract from metadata if available
                    k=2  # Retrieve 2 similar examples
                )
                if few_shot_examples:
                    rag_examples_str = few_shot_examples
                    logger.debug(f"Using few-shot examples from MAST embeddings for {failure_mode.value}")
            except Exception as e:
                logger.warning(f"Few-shot retrieval failed: {e}")

        # Build prompt with enhanced context, RAG examples, and knowledge context
        prompt = self._build_prompt(
            failure_mode, task, trace_summary, key_events,
            full_conversation, agent_interactions, coordination_events,
            rag_examples=rag_examples_str,
            knowledge_context=knowledge_context,
            framework=framework,
        )

        # Try primary provider based on model config
        start_time = time.time()
        use_fallback = False
        primary_error = None
        thinking_content = ""

        try:
            if self._provider == ModelProvider.GOOGLE:
                # Call Gemini
                content, input_tokens, output_tokens, latency_ms = self._call_gemini(prompt, timeout)
                thinking_tokens = 0

            elif self._provider == ModelProvider.OPENAI:
                # Call OpenAI
                content, input_tokens, output_tokens, latency_ms = self._call_openai(prompt, timeout)
                thinking_tokens = 0

            else:  # ModelProvider.ANTHROPIC
                # Call Claude
                content, input_tokens, output_tokens, thinking_tokens, latency_ms, thinking_content = self._call_claude(prompt, timeout)

            total_tokens = input_tokens + output_tokens + thinking_tokens

            # Calculate cost
            cost = self._calculate_cost(
                input_tokens, output_tokens,
                is_openai=(self._provider == ModelProvider.OPENAI),
                is_gemini=(self._provider == ModelProvider.GOOGLE),
                thinking_tokens=thinking_tokens
            )

            # Parse response
            verdict, confidence, reasoning = self._parse_response(content, failure_mode)

            # Include thinking in reasoning if available
            if thinking_content and self.model_config.use_extended_thinking:
                reasoning = f"[Extended Thinking]\n{thinking_content[:500]}...\n\n[Response]\n{reasoning}"

            result = JudgmentResult(
                failure_mode=failure_mode,
                verdict=verdict,
                confidence=confidence,
                reasoning=reasoning,
                raw_response=content,
                model_used=f"{self.MODEL}" + ("-thinking" if self.model_config.use_extended_thinking else ""),
                tokens_used=total_tokens,
                cost_usd=cost,
                cached=False,
                latency_ms=latency_ms,
                provider=self._provider.value,  # Set provider
            )

            # Cache result
            self._set_cached(cache_key, result)

            # Track cost
            get_cost_tracker().record(result)

            thinking_info = f", thinking={thinking_tokens}" if thinking_tokens else ""
            logger.info(
                f"MAST Judge ({self.model_key}, {self._provider.value}): {failure_mode.value} -> {verdict} "
                f"(conf={confidence:.2f}, tokens={total_tokens}{thinking_info}, cost=${cost:.4f})"
            )

            return result

        except RateLimitError as e:
            primary_error = f"{self._provider.value} API rate limit: {str(e)}"
            logger.warning(primary_error)
            use_fallback = True
        except APITimeoutError as e:
            primary_error = f"{self._provider.value} API timeout: {str(e)}"
            logger.warning(primary_error)
            use_fallback = True
        except APIError as e:
            primary_error = f"{self._provider.value} API error: {str(e)}"
            logger.warning(primary_error)
            use_fallback = True
        except Exception as e:
            primary_error = f"{self._provider.value} API exception: {str(e)}"
            logger.warning(primary_error)
            use_fallback = True

        # Fallback to OpenAI GPT-4 if Claude fails
        if use_fallback and self.use_openai_fallback and self.openai_api_key:
            logger.info(f"Falling back to OpenAI GPT-4 for {failure_mode.value}")
            try:
                content, input_tokens, output_tokens, latency_ms = self._call_openai(prompt, timeout)
                total_tokens = input_tokens + output_tokens
                cost = self._calculate_cost(input_tokens, output_tokens, is_openai=True)

                # Parse response
                verdict, confidence, reasoning = self._parse_response(content, failure_mode)

                result = JudgmentResult(
                    failure_mode=failure_mode,
                    verdict=verdict,
                    confidence=confidence,
                    reasoning=reasoning,
                    raw_response=content,
                    model_used=self.OPENAI_MODEL,
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
                    f"MAST Judge (OpenAI fallback): {failure_mode.value} -> {verdict} "
                    f"(conf={confidence:.2f}, tokens={total_tokens}, cost=${cost:.4f})"
                )

                return result

            except Exception as e:
                logger.error(f"OpenAI fallback also failed: {e}")
                return JudgmentResult(
                    failure_mode=failure_mode,
                    verdict="UNCERTAIN",
                    confidence=0.0,
                    reasoning=f"Both primary and OpenAI APIs failed. Primary ({self._provider.value}): {primary_error}. OpenAI: {str(e)}",
                    raw_response="",
                    model_used="none",
                    tokens_used=0,
                    cost_usd=0.0,
                    cached=False,
                    latency_ms=0,
                    provider="none",
                )

        # No fallback available
        return JudgmentResult(
            failure_mode=failure_mode,
            verdict="UNCERTAIN",
            confidence=0.0,
            reasoning=f"API error ({self._provider.value}): {primary_error}",
            raw_response="",
            model_used=self.MODEL,
            tokens_used=0,
            cost_usd=0.0,
            cached=False,
            latency_ms=int((time.time() - start_time) * 1000),
            provider=self._provider.value,
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
