"""
MAST LLM Judge Prompts
======================

Failure mode definitions and chain-of-thought prompts for LLM-based detection.
Based on MAST paper methodology achieving 94% accuracy with few-shot prompting.
"""

from ._enums import MASTFailureMode


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
        "name": "Role Usurpation",
        "definition": """FM-2.4: Agent acts outside their designated role, exceeding boundaries or taking over
responsibilities assigned to other agents. Look for: agent performing tasks explicitly assigned to another role,
claiming authority they don't have, making decisions outside their scope, or overriding role-specific constraints.
Note: This differs from F2 (Role Specification) which is about initial role definition; F9 is about runtime role violations.""",
        "positive_example": """Setup: "Coder writes, Reviewer reviews, Deployer deploys"
Coder: "Code done. I'm also reviewing it myself - APPROVED. Deploying now."
Verdict: YES - Coder usurped Reviewer and Deployer roles""",
        "negative_example": """Coder: "Code done. Sending to Reviewer."
Reviewer: "LGTM. Approved for deployment."
Deployer: "Deploying now."
Verdict: NO - Each agent stayed within role boundaries"""
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
