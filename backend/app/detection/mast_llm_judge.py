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
from anthropic import Anthropic, APIError, RateLimitError, APITimeoutError

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
    """Tracks cumulative costs for LLM judge calls with per-tier breakdown."""
    total_calls: int = 0
    cached_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    # Per-tier tracking for cost analysis
    haiku_calls: int = 0
    haiku_cost: float = 0.0
    sonnet_calls: int = 0
    sonnet_cost: float = 0.0
    sonnet_thinking_calls: int = 0
    sonnet_thinking_cost: float = 0.0

    def record(self, result: JudgmentResult):
        self.total_calls += 1
        if result.cached:
            self.cached_calls += 1
        else:
            self.total_tokens += result.tokens_used
            self.total_cost_usd += result.cost_usd
            # Track per-tier costs
            model = result.model_used.lower()
            if "haiku" in model:
                self.haiku_calls += 1
                self.haiku_cost += result.cost_usd
            elif "thinking" in model or "extended" in model:
                self.sonnet_thinking_calls += 1
                self.sonnet_thinking_cost += result.cost_usd
            else:
                self.sonnet_calls += 1
                self.sonnet_cost += result.cost_usd

    def get_tier_summary(self) -> dict:
        """Get cost breakdown by tier."""
        return {
            "haiku": {"calls": self.haiku_calls, "cost": self.haiku_cost},
            "sonnet": {"calls": self.sonnet_calls, "cost": self.sonnet_cost},
            "sonnet_thinking": {"calls": self.sonnet_thinking_calls, "cost": self.sonnet_thinking_cost},
            "total": {"calls": self.total_calls, "cost": self.total_cost_usd},
        }


# Global cost tracker
_cost_tracker = JudgeCostTracker()


@dataclass
class ClaudeModelConfig:
    """Configuration for a Claude model variant."""
    model_id: str
    input_price_per_1m: float
    output_price_per_1m: float
    thinking_price_per_1m: float = 0.0
    use_extended_thinking: bool = False
    thinking_budget: int = 0  # Max thinking tokens (0 = disabled)
    context_window: int = 200000


# All Claude models to benchmark for performance vs cost
CLAUDE_MODELS: Dict[str, ClaudeModelConfig] = {
    # Opus 4.5 - Highest quality, most expensive
    "opus-4.5": ClaudeModelConfig(
        model_id="claude-opus-4-5-20251101",
        input_price_per_1m=15.0,
        output_price_per_1m=75.0,
        context_window=200000,
    ),
    # Opus 4.5 with extended thinking - Best for complex reasoning
    "opus-4.5-thinking": ClaudeModelConfig(
        model_id="claude-opus-4-5-20251101",
        input_price_per_1m=15.0,
        output_price_per_1m=75.0,
        thinking_price_per_1m=10.0,
        use_extended_thinking=True,
        thinking_budget=16000,
        context_window=200000,
    ),
    # Sonnet 4 - Balanced performance/cost
    "sonnet-4": ClaudeModelConfig(
        model_id="claude-sonnet-4-20250514",
        input_price_per_1m=3.0,
        output_price_per_1m=15.0,
        context_window=200000,
    ),
    # Sonnet 4 with extended thinking - 32K budget for complex MAST analysis
    "sonnet-4-thinking": ClaudeModelConfig(
        model_id="claude-sonnet-4-20250514",
        input_price_per_1m=3.0,
        output_price_per_1m=15.0,
        thinking_price_per_1m=10.0,
        use_extended_thinking=True,
        thinking_budget=32000,  # Increased from 16K for F6/F8/F9/F13/F14 analysis
        context_window=200000,
    ),
    # Sonnet 3.5 - Previous generation, good balance
    "sonnet-3.5": ClaudeModelConfig(
        model_id="claude-3-5-sonnet-20241022",
        input_price_per_1m=3.0,
        output_price_per_1m=15.0,
        context_window=200000,
    ),
    # Haiku 3.5 - Fast and cheap
    "haiku-3.5": ClaudeModelConfig(
        model_id="claude-3-5-haiku-20241022",
        input_price_per_1m=0.80,
        output_price_per_1m=4.0,
        context_window=200000,
    ),
}

# 3-Tier Model Selection for Cost Optimization
# Benchmark results (claude_comparison_20260111): All achieve 97%+ accuracy

# Low-stakes model - haiku-3.5 at $0.0011/judgment (5x cheaper than sonnet)
LOW_STAKES_MODEL_KEY = "haiku-3.5"

# Default model - sonnet-4 provides 97.1% accuracy at 80% lower cost than opus
DEFAULT_MODEL_KEY = "sonnet-4"

# High-stakes model for critical failure modes - achieves 99.0% accuracy
HIGH_STAKES_MODEL_KEY = "sonnet-4-thinking"

# Low-stakes modes - high pattern accuracy, simple behavioral checks
# Based on benchmark: 100% accuracy with pattern-based detection
LOW_STAKES_FAILURE_MODES = {"F3", "F7", "F11", "F12"}

# High-stakes modes - complex semantic analysis required
# Based on benchmark results: these modes have higher complexity and ambiguity
# Updated to include zero-F1 modes that need chain-of-thought reasoning
HIGH_STAKES_FAILURE_MODES = {"F6", "F8", "F9", "F13", "F14"}

# Default tier (sonnet-4): F1, F2, F4, F5, F10 - moderate complexity


def get_model_for_failure_mode(failure_mode: str) -> str:
    """
    Select optimal model based on failure mode complexity (3-tier).

    Tier 1 (Low-stakes): haiku-3.5 for F3, F7, F11, F12, F14
        - $0.0011/judgment, 97.1% accuracy
        - High pattern accuracy, simple behavioral checks

    Tier 2 (Default): sonnet-4 for F1, F2, F4, F5, F10, F13
        - $0.0048/judgment, 97.1% accuracy
        - Moderate semantic complexity

    Tier 3 (High-stakes): sonnet-4-thinking for F6, F8, F9
        - $0.0163/judgment, 99.0% accuracy
        - Complex semantic analysis with extended thinking

    Args:
        failure_mode: MAST failure mode code (e.g., "F6", "F8")

    Returns:
        Model key to use for detection
    """
    mode = failure_mode.upper()
    if mode in HIGH_STAKES_FAILURE_MODES:
        return HIGH_STAKES_MODEL_KEY
    elif mode in LOW_STAKES_FAILURE_MODES:
        return LOW_STAKES_MODEL_KEY
    return DEFAULT_MODEL_KEY


# Chain-of-Thought prompts for complex semantic analysis modes
# These modes require step-by-step reasoning for accurate detection
CHAIN_OF_THOUGHT_PROMPTS = {
    MASTFailureMode.F6: """## Chain-of-Thought Analysis for Conversation Reset (F6)

Before making your judgment, work through these steps carefully:

### Step 1: Identify the Conversation State
- What was the accumulated context at the point of suspected reset?
- List key facts, decisions, and progress made before the reset.

### Step 2: Detect Reset Indicators
Look for these specific patterns:
- Greeting phrases that restart dialogue ("Hello!", "How can I help?", "Nice to meet you")
- Loss of previously established facts or preferences
- Agent asking questions already answered
- Abandoning in-progress work without explanation
- Sudden topic change with no transition

### Step 3: Evaluate Continuity
- Does the agent reference prior context appropriately?
- Is there a logical flow from previous turns?
- Were any explicit handoffs or continuations present?

### Step 4: Distinguish from Legitimate Transitions
NOT a reset if:
- Agent summarizes and transitions to a new phase
- Explicit acknowledgment of context before change
- User-initiated topic change that agent follows appropriately

### Step 5: Severity Assessment
- Complete reset (loses ALL context) = HIGH confidence YES
- Partial reset (loses SOME context) = MEDIUM confidence YES
- Style change only (context maintained) = NO

Now apply this analysis to the trace below:
""",
    MASTFailureMode.F8: """## Chain-of-Thought Analysis for Task Derailment (F8)

Before making your judgment, work through these steps carefully:

### Step 1: Extract Original Task Specification
- What was the explicit task given to the agent?
- List ALL requirements, constraints, and success criteria.
- Note any implicit requirements based on context.

### Step 2: Trace Agent Actions
For each major action the agent takes:
- Is this action directly advancing the original task?
- Is this a necessary prerequisite for the task?
- Or is this tangential/unrelated work?

### Step 3: Identify Deviation Points
Look for these patterns:
- "While I'm at it..." or "I noticed that..." (scope creep)
- Switching to related but different work
- Optimizing/improving things not requested
- Adding features not in specification
- Pursuing interesting tangents

### Step 4: Assess Impact
- Did the deviation prevent task completion?
- Did it significantly delay the original task?
- Was the original task ultimately completed?

### Step 5: Distinguish from Legitimate Work
NOT derailment if:
- Agent asks permission before expanding scope
- Work is a necessary dependency for the task
- Agent explicitly acknowledges trade-off and justifies
- Minor efficiency improvements while completing task

### Step 6: Calculate Derailment Severity
- Complete abandonment of task = HIGH confidence YES
- Significant distraction but task attempted = MEDIUM confidence YES
- Minor tangent with task completed = NO

Now apply this analysis to the trace below:
""",
    MASTFailureMode.F9: """## Chain-of-Thought Analysis for Role Usurpation (F9)

Before making your judgment, work through these steps carefully:

### Step 1: Identify Assigned Roles
- What role is each agent assigned? (e.g., Programmer, Reviewer, Designer)
- What are the explicit boundaries of each role?
- What decisions/actions belong to which role?

### Step 2: Map Actions to Roles
For each action taken by an agent:
- Does this action fall within their assigned role?
- Is this action typically owned by another role?
- Did they seek permission before acting outside scope?

### Step 3: Detect Usurpation Patterns
Look for:
- Self-approval (Programmer approving own code)
- Decision override (Junior overriding Senior)
- Role bleed (Designer making architectural decisions)
- Authority escalation (QA modifying production code)
- Unauthorized commits or deployments

### Step 4: Check for Permission/Coordination
NOT usurpation if:
- Agent explicitly asks permission ("Is it okay if I...?")
- Another role delegates authority ("You handle this")
- Role is ambiguous and agent clarifies
- Agent provides suggestion without taking action

### Step 5: Assess Severity
- Taking action that should require approval = HIGH confidence YES
- Making decision outside role scope = MEDIUM confidence YES
- Offering helpful suggestion within scope = NO

Now apply this analysis to the trace below:
""",
    MASTFailureMode.F13: """## Chain-of-Thought Analysis for Quality Gate Bypass (F13)

Before making your judgment, work through these steps carefully:

### Step 1: Identify Quality Gates
- What verification steps should have occurred?
- Were tests expected to be run?
- Was code review required?
- Are there explicit quality criteria mentioned?

### Step 2: Trace Verification Activities
For each quality gate:
- Was it explicitly skipped or bypassed?
- Was there any evidence of verification (test output, review comments)?
- Did the agent claim verification without evidence?

### Step 3: Detect Bypass Patterns
Look for:
- "Skipping tests to meet deadline"
- "No need to test, it looks correct"
- "LGTM" without actual review evidence
- Deployment without any test results shown
- Ignoring test failures ("probably flaky")

### Step 4: Distinguish from Legitimate Scenarios
NOT a bypass if:
- Prototype/MVP explicitly scoped without tests
- Tests run with passing results shown
- Hotfix with post-deploy testing planned
- Partial coverage explicitly acknowledged and tracked

### Step 5: Assess Severity
- Deploying without any testing = HIGH confidence YES
- Ignoring test failures = HIGH confidence YES
- Claiming review without evidence = MEDIUM confidence YES
- Acknowledged limited coverage with plan = NO

Now apply this analysis to the trace below:
""",
    MASTFailureMode.F14: """## Chain-of-Thought Analysis for Completion Misjudgment (F14)

Before making your judgment, work through these steps carefully:

### Step 1: Extract Task Requirements
- List ALL explicit requirements from the task
- Note any implicit requirements (standard practices)
- Identify success criteria if stated

### Step 2: Verify Requirement Coverage
For each requirement:
- Is there evidence of implementation?
- Is there evidence of completion?
- Are there gaps or missing pieces?

### Step 3: Detect Completion Claim
Look for:
- Explicit completion claims ("Task complete!", "Done!")
- Confident delivery ("Here's the final version")
- Implicit completion (proceeding to next phase)

### Step 4: Identify Gaps
Check for:
- Missing features from requirements
- Errors in output (syntax errors, runtime errors)
- Uncertainty language ("should work", "probably done")
- Partial completion ("most features", "core functionality")
- Planned work still pending ("tests will be added later")

### Step 5: Distinguish Legitimate Completion
NOT misjudgment if:
- All requirements explicitly addressed
- Agent acknowledges partial completion
- Verification shows all tests passing
- Clear handoff with no false claims

### Step 6: Assess Severity
- Claiming complete with obvious bugs = HIGH confidence YES
- Claiming complete with missing features = HIGH confidence YES
- Uncertain language with claims = MEDIUM confidence YES
- Honest partial progress reporting = NO

Now apply this analysis to the trace below:
""",
}

# Modes that benefit from knowledge augmentation
KNOWLEDGE_AUGMENTED_MODES = {
    MASTFailureMode.F3: "F3",  # Resource Allocation -> Cost DB
    MASTFailureMode.F4: "F4",  # Tool Provision -> Tool Catalog
    MASTFailureMode.F9: "F9",  # Role Usurpation -> Role Specs
}


def get_cost_tracker() -> JudgeCostTracker:
    """Get the global cost tracker."""
    return _cost_tracker


def reset_cost_tracker():
    """Reset the global cost tracker."""
    global _cost_tracker
    _cost_tracker = JudgeCostTracker()


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
        cache_enabled: bool = True,
        max_cache_size: int = 1000,
        rag_enabled: bool = True,
        rag_examples_per_mode: int = 3,
        db_session=None,
        use_openai_fallback: bool = True,
        model_key: str = DEFAULT_MODEL_KEY,
    ):
        # Model configuration
        if model_key not in CLAUDE_MODELS:
            raise ValueError(
                f"Unknown model_key '{model_key}'. Available: {list(CLAUDE_MODELS.keys())}"
            )
        self.model_key = model_key
        self.model_config = CLAUDE_MODELS[model_key]

        # For backward compatibility, expose MODEL as instance attribute
        self.MODEL = self.model_config.model_id
        self.INPUT_PRICE_PER_1M = self.model_config.input_price_per_1m
        self.OUTPUT_PRICE_PER_1M = self.model_config.output_price_per_1m

        self._api_key = api_key
        self._openai_api_key = openai_api_key
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
            logger.warning(f"Could not retrieve few-shot examples: {e}")
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
    ) -> str:
        """Build the judge prompt with few-shot examples and enhanced context.

        Phase 3 Enhancement: Now includes conversation timeline for better context.

        Args:
            rag_examples: Pre-formatted RAG examples from retrieval service
            knowledge_context: Domain knowledge for modes like F3, F4, F9
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

        prompt = f"""You are an expert evaluator of AI agent behavior, specifically trained to detect failure modes in multi-agent systems. You are evaluating traces from the MAST benchmark dataset.

## Failure Mode: {failure_mode.value} - {mode_def['name']}

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
        thinking_tokens: int = 0,
    ) -> float:
        """Calculate cost in USD including thinking tokens for extended thinking."""
        if is_openai:
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
        import re as regex

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
                        wait_match = regex.search(r'try again in ([\d.]+)s', error_msg)
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
        )

        # Try Claude API first using official Anthropic SDK
        start_time = time.time()
        use_fallback = False
        claude_error = None

        try:
            # Build messages
            messages = [{"role": "user", "content": prompt}]

            # Prepare system prompt
            system_prompt = "You are an expert evaluator of AI agent behavior. Always respond with valid JSON."

            # For extended thinking, prepend system context to user message
            if self.model_config.use_extended_thinking:
                messages[0]["content"] = system_prompt + "\n\n" + prompt
                system_prompt = None  # Don't use separate system param with extended thinking

            # Build API call parameters
            api_params = {
                "model": self.MODEL,
                "max_tokens": 16000 if self.model_config.use_extended_thinking else 1000,
                "messages": messages,
            }

            # Add system prompt if not using extended thinking
            if system_prompt:
                api_params["system"] = system_prompt

            # Add extended thinking configuration
            if self.model_config.use_extended_thinking:
                api_params["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": self.model_config.thinking_budget,
                }

            # Call Claude API using SDK
            response = self.anthropic_client.messages.create(**api_params)

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract content - handle extended thinking response format
            content = ""
            thinking_content = ""
            for block in response.content:
                if block.type == "thinking":
                    thinking_content = block.thinking
                elif block.type == "text":
                    content = block.text

            # Extract token usage (SDK provides typed objects)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            thinking_tokens = 0

            # Extended thinking has separate thinking token count
            if self.model_config.use_extended_thinking:
                # Check for cache_creation_input_tokens in usage
                thinking_tokens = getattr(response.usage, 'cache_creation_input_tokens', 0) or 0
                if thinking_tokens == 0:
                    # Estimate from thinking content if not reported
                    thinking_tokens = len(thinking_content) // 4 if thinking_content else 0

            total_tokens = input_tokens + output_tokens + thinking_tokens

            # Calculate cost including thinking tokens
            cost = self._calculate_cost(
                input_tokens, output_tokens,
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
            )

            # Cache result
            self._set_cached(cache_key, result)

            # Track cost
            get_cost_tracker().record(result)

            thinking_info = f", thinking={thinking_tokens}" if thinking_tokens else ""
            logger.info(
                f"MAST Judge ({self.model_key}): {failure_mode.value} -> {verdict} "
                f"(conf={confidence:.2f}, tokens={total_tokens}{thinking_info}, cost=${cost:.4f})"
            )

            return result

        except RateLimitError as e:
            claude_error = f"Claude API rate limit: {str(e)}"
            logger.warning(claude_error)
            use_fallback = True
        except APITimeoutError as e:
            claude_error = f"Claude API timeout: {str(e)}"
            logger.warning(claude_error)
            use_fallback = True
        except APIError as e:
            claude_error = f"Claude API error: {str(e)}"
            logger.warning(claude_error)
            use_fallback = True
        except Exception as e:
            claude_error = f"Claude API exception: {str(e)}"
            logger.warning(claude_error)
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
                    f"MAST Judge (OpenAI): {failure_mode.value} -> {verdict} "
                    f"(conf={confidence:.2f}, tokens={total_tokens}, cost=${cost:.4f})"
                )

                return result

            except Exception as e:
                logger.error(f"OpenAI fallback also failed: {e}")
                return JudgmentResult(
                    failure_mode=failure_mode,
                    verdict="UNCERTAIN",
                    confidence=0.0,
                    reasoning=f"Both Claude and OpenAI APIs failed. Claude: {claude_error}. OpenAI: {str(e)}",
                    raw_response="",
                    model_used="none",
                    tokens_used=0,
                    cost_usd=0.0,
                    cached=False,
                    latency_ms=0,
                )

        # No fallback available
        return JudgmentResult(
            failure_mode=failure_mode,
            verdict="UNCERTAIN",
            confidence=0.0,
            reasoning=f"API error: {claude_error}",
            raw_response="",
            model_used=self.MODEL,
            tokens_used=0,
            cost_usd=0.0,
            cached=False,
            latency_ms=int((time.time() - start_time) * 1000),
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

    def __init__(self, api_key: Optional[str] = None, db_session=None):
        self._judge = MASTLLMJudge(api_key=api_key, db_session=db_session)

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
