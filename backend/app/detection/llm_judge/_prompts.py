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
#
# IMPORTANT: These definitions MUST match mast_loader.py FAILURE_MODE_NAMES
# F1-F5: Planning Failures (FC1)
# F6-F11: Execution Failures (FC2)
# F12-F14: Verification Failures (FC3)
MAST_FAILURE_DEFINITIONS = {
    # === FC1: Planning Failures (5 modes) ===
    MASTFailureMode.F1: {
        "name": "Specification Mismatch",
        "definition": """FM-1.1: Failure to properly understand or interpret task specifications, leading to
misalignment between what was requested and what is being attempted. Look for: misunderstanding requirements,
interpreting instructions incorrectly, working on wrong aspects of the task, or producing output that doesn't
match what was specified.""",
        "positive_example": """Task: "Create a REST API with authentication and rate limiting"
Agent: "I'll build a GraphQL endpoint with caching"
[Wrong API type, wrong features - misunderstood the specification]
Verdict: YES - Specification was misinterpreted""",
        "negative_example": """Task: "Create a REST API with authentication"
Agent: "Building REST API with JWT authentication as specified"
Verdict: NO - Correctly understood specification"""
    },
    MASTFailureMode.F2: {
        "name": "Poor Task Decomposition",
        "definition": """FM-1.2: Inadequate breakdown of complex tasks into manageable subtasks, leading to
inefficient execution or missed components. Look for: attempting everything at once without planning,
missing logical steps, poor sequencing of subtasks, or failing to identify dependencies between steps.""",
        "positive_example": """Task: "Build e-commerce checkout with payment, inventory, and shipping"
Agent: "Let me just write all the code at once..." [produces incomplete, tangled code]
Verdict: YES - Failed to decompose into payment, inventory, shipping subtasks""",
        "negative_example": """Task: "Build checkout system"
Agent: "Step 1: Cart validation. Step 2: Payment processing. Step 3: Inventory update. Step 4: Shipping."
Verdict: NO - Properly decomposed into logical subtasks"""
    },
    MASTFailureMode.F3: {
        "name": "Resource Misallocation",
        "definition": """FM-1.3: Inefficient or incorrect allocation of computational resources, time, or agent
capabilities to tasks. Look for: using expensive operations when cheap ones suffice, assigning wrong agents
to tasks, spending too much effort on minor issues, or under-resourcing critical tasks.""",
        "positive_example": """Agent: "For this simple string comparison, let me spin up a GPU cluster and train a neural network"
Verdict: YES - Massive over-allocation of resources for trivial task""",
        "negative_example": """Agent: "Simple comparison - I'll use a direct string match. For ML tasks, I'll use GPU."
Verdict: NO - Resources appropriately matched to task complexity"""
    },
    MASTFailureMode.F4: {
        "name": "Inadequate Tool Provision",
        "definition": """FM-1.4: Lack of necessary tools, APIs, or capabilities to complete the assigned task.
Look for: agent attempting to use unavailable tools, lacking required permissions, missing API access,
or not having the right capabilities for the task at hand.""",
        "positive_example": """Task: "Query the production database"
Agent: "I don't have database access credentials. Let me try anyway..." [fails]
Agent: "Tool not found: db_query. I cannot complete this task."
Verdict: YES - Lacked necessary tool/access to complete task""",
        "negative_example": """Task: "Query the database"
Agent: "Using db_query tool with my credentials to fetch data... Success!"
Verdict: NO - Had adequate tools and access"""
    },
    MASTFailureMode.F5: {
        "name": "Flawed Workflow Design",
        "definition": """FM-1.5: Poor design of the overall workflow or process, leading to inefficiencies,
bottlenecks, or failures. Look for: circular dependencies, missing error handling in workflow,
improper sequencing, lack of fallback paths, or workflows that can't handle edge cases.""",
        "positive_example": """Workflow: "Agent A waits for Agent B, Agent B waits for Agent A"
[Deadlock - neither can proceed]
Verdict: YES - Flawed workflow design created circular dependency""",
        "negative_example": """Workflow: "Agent A processes, passes to B, B validates, returns to A if issues"
Verdict: NO - Well-designed workflow with proper sequencing"""
    },
    # === FC2: Execution Failures (6 modes) ===
    MASTFailureMode.F6: {
        "name": "Task Derailment",
        "definition": """FM-2.1: Agent deviates from the assigned task, pursuing tangential or unrelated activities.
Look for: scope creep, getting sidetracked by interesting but irrelevant work, abandoning the original task,
or spending time on optimizations/features not requested.
For n8n workflows: Look for nodes that execute unrelated operations or workflow branches that don't contribute to the goal.""",
        "positive_example": """Task: "Fix the login bug"
Agent: "While looking at login, I noticed the CSS could be better. Let me refactor all styles..."
[Hours later, still doing CSS, login bug unfixed]
Verdict: YES - Derailed from bug fix into unrelated CSS work

n8n Example: Workflow for data extraction adds unexpected email notification nodes not in requirements.
Verdict: YES - Workflow derailed from data extraction into email notifications""",
        "negative_example": """Task: "Fix the login bug"
Agent: "Found the bug in auth.js line 42. Fixed. Login now works."
Verdict: NO - Stayed focused on the assigned task"""
    },
    MASTFailureMode.F7: {
        "name": "Context Neglect",
        "definition": """FM-2.2: Failing to consider or utilize relevant context from the conversation or environment.
Look for: ignoring previously provided information, not using available context, making decisions without
considering established constraints, or acting as if important context doesn't exist.""",
        "positive_example": """Earlier: "The system uses PostgreSQL, not MySQL"
Agent: "I'll write this MySQL query to fetch the data..."
Verdict: YES - Neglected the context that system uses PostgreSQL""",
        "negative_example": """Earlier: "Use PostgreSQL"
Agent: "Writing PostgreSQL query as specified earlier..."
Verdict: NO - Properly used context from conversation"""
    },
    MASTFailureMode.F8: {
        "name": "Information Withholding",
        "definition": """FM-2.3: Failure to share necessary information between agents or with the user,
leading to incomplete understanding or suboptimal decisions. Look for: agent not providing requested info,
ignoring questions, withholding context needed by others, or not sharing relevant findings.""",
        "positive_example": """User: "What error message did you see?"
Agent: "I fixed the issue. Moving on to the next task."
[Never shared the error message despite being asked]
Verdict: YES - Withheld requested information""",
        "negative_example": """User: "What error message did you see?"
Agent: "The error was 'ConnectionTimeout after 30s'. I fixed it by increasing the timeout."
Verdict: NO - Shared the requested information"""
    },
    MASTFailureMode.F9: {
        "name": "Role Usurpation",
        "definition": """FM-2.4: Agent acts outside their designated role, exceeding boundaries or taking over
responsibilities assigned to other agents. Look for: agent performing tasks explicitly assigned to another role,
claiming authority they don't have, making decisions outside their scope, or overriding role-specific constraints.""",
        "positive_example": """Setup: "Coder writes, Reviewer reviews, Deployer deploys"
Coder: "Code done. I'm also reviewing it myself - APPROVED. Deploying now."
Verdict: YES - Coder usurped Reviewer and Deployer roles""",
        "negative_example": """Coder: "Code done. Sending to Reviewer."
Reviewer: "LGTM. Approved for deployment."
Deployer: "Deploying now."
Verdict: NO - Each agent stayed within role boundaries"""
    },
    MASTFailureMode.F10: {
        "name": "Communication Breakdown",
        "definition": """FM-2.5: Failure in communication between agents, leading to misunderstandings, missed
handoffs, or uncoordinated actions. Look for: agents talking past each other, messages not received or
acknowledged, unclear handoffs, or agents making conflicting decisions due to poor communication.""",
        "positive_example": """Agent A: "I'll handle the frontend"
Agent B: "I'll handle the frontend"
[Both build frontend, no one does backend - communication breakdown]
Verdict: YES - Failed to communicate and coordinate work division""",
        "negative_example": """Agent A: "I'll do frontend, you do backend"
Agent B: "Confirmed. Starting backend now."
Verdict: NO - Clear communication and coordination"""
    },
    MASTFailureMode.F11: {
        "name": "Coordination Failure",
        "definition": """FM-2.6: Failure to properly coordinate actions between multiple agents, leading to
conflicts, duplicated work, or missed dependencies. Look for: agents working on same thing without knowing,
timing issues, dependency violations, or lack of synchronization between parallel activities.
For n8n workflows: Look for parallel branches that produce conflicting state updates, race conditions, or nodes that don't wait for required predecessors.""",
        "positive_example": """Agent A: "Deploying version 1.0"
Agent B: "Deploying version 1.1" [at same time]
[Deployment conflict - no coordination]
Verdict: YES - Failed to coordinate deployments

n8n Example: Parallel branches both write to the same database record, causing data race.
Verdict: YES - Parallel nodes failed to coordinate database writes""",
        "negative_example": """Agent A: "Ready to deploy 1.0, waiting for B's approval"
Agent B: "Approved. Proceed with deployment."
Verdict: NO - Properly coordinated the deployment"""
    },
    # === FC3: Verification Failures (3 modes) ===
    MASTFailureMode.F12: {
        "name": "Output Validation Failure",
        "definition": """FM-3.1: Failure to properly validate outputs before delivery, resulting in incorrect,
incomplete, or malformed results being passed on. Look for: not checking output format, missing validation
of results, accepting invalid data, or delivering outputs that don't meet requirements.
For n8n workflows: Look for node outputs that don't match the expected schema of downstream nodes, data type mismatches, or missing required fields.""",
        "positive_example": """Task: "Return JSON response"
Agent: "Here's the result: {invalid json syntax"
[Delivered malformed JSON without validation]
Verdict: YES - Failed to validate output format

n8n Example: Node outputs {\"data\": [...]} but next node expects {\"items\": [...]}, causing schema mismatch.
Verdict: YES - Node output schema doesn't match expected input of next node""",
        "negative_example": """Agent: "Validating JSON... Valid. Returning response."
Verdict: NO - Properly validated output before delivery"""
    },
    MASTFailureMode.F13: {
        "name": "Quality Gate Bypass",
        "definition": """FM-3.2: Skipping or bypassing quality checks, tests, or review processes that should
have been performed. Look for: explicitly skipping tests, bypassing code review, ignoring CI failures,
or deploying without required approvals.""",
        "positive_example": """Agent: "Tests are failing but deadline is tight. Deploying anyway."
Verdict: YES - Bypassed quality gate (failing tests)""",
        "negative_example": """Agent: "All tests pass. Code reviewed. Deploying."
Verdict: NO - Followed quality gates properly"""
    },
    MASTFailureMode.F14: {
        "name": "Completion Misjudgment",
        "definition": """FM-3.3: Incorrectly assessing whether a task is complete, either claiming completion
prematurely or failing to recognize when work is done. Look for: declaring "done" with missing features,
continuing work after completion, or misjudging the state of deliverables.""",
        "positive_example": """Task: "Build login with email verification and password reset"
Agent: "Login done! Task complete!"
[Missing: email verification, password reset]
Verdict: YES - Misjudged completion - missing required features""",
        "negative_example": """Task: "Build login with email verification"
Agent: "Login done. Email verification done. All requirements met. Complete."
Verdict: NO - Correctly judged task completion"""
    },
}


# Chain-of-Thought prompts for complex semantic analysis modes
# These modes require step-by-step reasoning for accurate detection
# NOTE: F-codes must match mast_loader.py definitions
CHAIN_OF_THOUGHT_PROMPTS = {
    MASTFailureMode.F6: """## Chain-of-Thought Analysis for Task Derailment (F6)

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
    MASTFailureMode.F8: """## Chain-of-Thought Analysis for Information Withholding (F8)

Before making your judgment, work through these steps carefully:

### Step 1: Identify Information Requests
- What questions were asked by users or other agents?
- What information was explicitly requested?
- What context would be expected to be shared?

### Step 2: Trace Information Sharing
For each request/question:
- Was a direct answer provided?
- Was the response substantive or evasive?
- Was relevant context included in the response?

### Step 3: Detect Withholding Patterns
Look for these specific indicators:
- Ignored questions (no acknowledgment)
- Deflection ("Let's move on" without answering)
- Partial responses that omit key details
- Generic answers that don't address specifics
- Refusal to share without justification
- Proceeding without sharing relevant findings

### Step 4: Distinguish from Legitimate Non-Sharing
NOT withholding if:
- Information genuinely unknown ("I don't have that data")
- Security/privacy constraints acknowledged
- Question acknowledged with plan to address later
- Clarification requested before answering

### Step 5: Assess Impact
- Did withholding prevent task completion?
- Did other agents/users make suboptimal decisions?
- Was critical context missing from handoffs?

### Step 6: Calculate Severity
- Ignoring direct questions = HIGH confidence YES
- Omitting critical context = MEDIUM confidence YES
- Minor details not shared = LOW confidence or NO

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
# Must match mast_loader.py FAILURE_MODE_NAMES
KNOWLEDGE_AUGMENTED_MODES = {
    MASTFailureMode.F3: "F3",  # Resource Misallocation -> Cost DB
    MASTFailureMode.F4: "F4",  # Inadequate Tool Provision -> Tool Catalog
    MASTFailureMode.F9: "F9",  # Role Usurpation -> Role Specs
}


# ============================================================================
# N8N WORKFLOW-SPECIFIC FAILURE DEFINITIONS
# ============================================================================
# n8n failures manifest STRUCTURALLY, not conversationally:
# - Data flows explicitly via $json between nodes
# - "Roles" are node types with defined purposes
# - Loops are graph cycles, not semantic repetition
# - Quality gates are missing validation nodes, not dialogue about tests
# - State is observable in node outputs
#
# These definitions help the LLM judge understand n8n-specific failure patterns.

N8N_FAILURE_DEFINITIONS = {
    MASTFailureMode.F3: {
        "name": "Resource Misallocation",
        "n8n_definition": """In n8n workflows, resource misallocation occurs when nodes use
excessive computational resources, make too many API calls, or process data inefficiently.
Look for:
- HTTP Request nodes called repeatedly in loops
- Large data sets passed between nodes without pagination
- Token/content explosion where output grows unboundedly
- AI nodes processing the same data multiple times""",
        "n8n_positive": """[Hourly Trigger] {"items": 1}
[Get All Users] {"users": [...50,000 users...]}
[Loop Each User] Iterating 50,000 times
[AI Summary] Calling OpenAI API 50,000 times
Verdict: YES - Massive resource waste: AI API called per user instead of batch""",
        "n8n_negative": """[Hourly Trigger] {"items": 1}
[Get Users - Paginated] {"users": [...100 users...], "page": 1}
[AI Batch Summary] Calling OpenAI API once with batched data
Verdict: NO - Efficient resource use with pagination and batching"""
    },
    MASTFailureMode.F6: {
        "name": "Task Derailment",
        "n8n_definition": """In n8n workflows, task derailment occurs when nodes execute
operations unrelated to the workflow's purpose, or when AI nodes generate off-topic content.
Look for:
- AI nodes producing content outside the task scope
- HTTP nodes calling APIs unrelated to workflow goal
- Data transformation nodes adding unexpected fields
- Workflow branches that don't contribute to the output""",
        "n8n_positive": """[Webhook: Customer Order] {"order_id": 123, "items": [...]}
[Get Order Details] {"order": {...}, "customer_email": "..."}
[AI Agent] {"summary": "Order processed", "promotional_content": "Check out our sale!", "unsubscribe_campaign": "..."}
[Send Email] Sends promotional email instead of order confirmation
Verdict: YES - Workflow derailed from order processing into marketing""",
        "n8n_negative": """[Webhook: Customer Order] {"order_id": 123}
[Get Order Details] {"order": {...}}
[Format Confirmation] {"subject": "Order 123 Confirmed", "body": "..."}
[Send Email] Sends order confirmation as expected
Verdict: NO - Each node performs its expected function for order processing"""
    },
    MASTFailureMode.F9: {
        "name": "Role Usurpation",
        "n8n_definition": """In n8n workflows, role usurpation occurs when a node performs
operations outside its designated scope or purpose. Each node type has an expected role:
- Trigger nodes: Initiate workflows
- HTTP nodes: Make external API calls
- AI nodes: Generate/analyze content
- Set nodes: Transform data
- Email nodes: Send notifications
Look for nodes that exceed their role.""",
        "n8n_positive": """[Hourly Trigger] {"timestamp": "..."}
[Fetch Stock Prices] {"stocks": [...]} - OK, this is an HTTP node
[AI Analyst] Generates analysis AND executes trades directly
[Log Results] ...
Verdict: YES - AI node should only analyze, not execute trades (that's a separate node's role)""",
        "n8n_negative": """[Hourly Trigger] {"timestamp": "..."}
[Fetch Stock Prices] {"stocks": [...]}
[AI Analyst] {"analysis": "BUY signal for AAPL", "confidence": 0.8}
[Execute Trade] Places trade based on AI analysis
[Log Results] ...
Verdict: NO - Each node stays within its role boundaries"""
    },
    MASTFailureMode.F11: {
        "name": "Coordination Failure",
        "n8n_definition": """In n8n workflows, coordination failure occurs when:
- Parallel branches conflict (both write same data)
- Circular delegation patterns emerge (A→B→C→A)
- Race conditions in state updates
- Nodes don't wait for required predecessors
Look for patterns where workflow execution order causes conflicts.""",
        "n8n_positive": """[Webhook] {"user_id": 123}
[Split] Parallel branches start
  [Branch A: Update Status] Updates user.status = "verified"
  [Branch B: Send Email] Updates user.status = "contacted"
[Merge] Conflict! Final status is non-deterministic
Verdict: YES - Parallel branches both modify user.status causing data race""",
        "n8n_negative": """[Webhook] {"user_id": 123}
[Split] Parallel branches start
  [Branch A: Verify Email] {"verification": "passed"}
  [Branch B: Check Credit] {"credit_score": 750}
[Merge] Combines results: {"verification": "passed", "credit_score": 750}
[Update User] Sets status based on combined results
Verdict: NO - Parallel branches work on independent data and merge cleanly"""
    },
    MASTFailureMode.F12: {
        "name": "Output Validation Failure / Schema Mismatch",
        "n8n_definition": """In n8n workflows, schema mismatch occurs when node outputs
don't match the expected inputs of downstream nodes. This causes:
- Undefined field access ($json.field is undefined)
- Type errors (expected array, got object)
- Data loss (fields present but ignored)
Look for mismatched JSON structures between connected nodes.""",
        "n8n_positive": """[API Node] Outputs: {"data": {"items": [...]}}
[Transform Node] Expects: $json.items (direct access)
[Error] Cannot read property 'items' - data is nested under 'data.items'
Verdict: YES - Schema mismatch: node expects $json.items but got $json.data.items""",
        "n8n_negative": """[API Node] Outputs: {"items": [...], "total": 100}
[Transform Node] Accesses: $json.items, $json.total
[Success] Both fields found and processed correctly
Verdict: NO - Output schema matches expected input schema"""
    },
}


# n8n-specific chain-of-thought prompts for structural analysis
N8N_CHAIN_OF_THOUGHT_PROMPTS = {
    MASTFailureMode.F6: """## n8n Workflow Analysis for Task Derailment (F6)

Before making your judgment, analyze the workflow structure:

### Step 1: Identify Workflow Purpose
- What is the trigger event? (Webhook, Schedule, Manual)
- What should the workflow accomplish?
- What output is expected?

### Step 2: Trace Data Flow Through Nodes
For each node execution:
- What data does it receive from previous node?
- What operation does it perform?
- Does this operation serve the workflow's purpose?

### Step 3: Detect Derailment Patterns
Look for n8n-specific derailment:
- AI nodes generating unrelated content in output
- HTTP nodes calling APIs not needed for the task
- Additional operations added to node output beyond requirements
- Branch nodes that lead nowhere useful

### Step 4: Assess Impact
- Did derailed actions prevent goal completion?
- Did they introduce side effects (unwanted emails, API calls)?
- Is the workflow output still correct?

Now apply this analysis to the trace:
""",
    MASTFailureMode.F11: """## n8n Workflow Analysis for Coordination Failure (F11)

Before making your judgment, analyze the workflow graph:

### Step 1: Identify Parallel Execution
- Are there Split/Merge nodes indicating parallel branches?
- Do multiple nodes execute concurrently?
- Are there any loops in the workflow?

### Step 2: Trace State Modifications
For each node:
- What data does it modify?
- Does any other node modify the same data?
- Is there a race condition risk?

### Step 3: Detect Coordination Issues
Look for:
- Both branches writing to same $json field
- Circular patterns: A→B→A or A→B→C→A
- Missing wait/sync points before merges
- Retry loops without exit conditions

### Step 4: Check for Graph Cycles
- Does any node appear multiple times in execution?
- Is there a pattern repeating (A,B,C,A,B,C)?
- Do execution counts seem excessive?

Now apply this analysis to the trace:
""",
    MASTFailureMode.F12: """## n8n Workflow Analysis for Schema Mismatch (F12)

Before making your judgment, analyze the data schemas:

### Step 1: Extract Node Outputs
For each node:
- What JSON structure does it output?
- What fields are present?
- What are the field types (string, number, array, object)?

### Step 2: Identify Expected Inputs
For each node:
- What $json fields does it access?
- What field types does it expect?
- Are any fields marked as required?

### Step 3: Compare Schemas
Between consecutive nodes:
- Do output fields match expected input fields?
- Are types compatible (e.g., array vs object)?
- Are nested paths correctly accessed ($json.data.items vs $json.items)?

### Step 4: Detect Mismatch Patterns
Look for:
- "undefined" or null values in outputs
- Type coercion errors
- Missing fields in transformations
- Schema drift over multiple nodes

Now apply this analysis to the trace:
""",
}


def get_failure_definition(mode: MASTFailureMode, framework: str = None) -> dict:
    """Get failure definition, using n8n-specific version if applicable.

    Args:
        mode: The failure mode to get definition for
        framework: Framework name (e.g., 'n8n', 'ChatDev', 'AG2')

    Returns:
        Dict with name, definition, and examples
    """
    if framework and 'n8n' in framework.lower() and mode in N8N_FAILURE_DEFINITIONS:
        n8n_def = N8N_FAILURE_DEFINITIONS[mode]
        base_def = MAST_FAILURE_DEFINITIONS.get(mode, {})

        # Merge: use n8n definition but fall back to base for missing fields
        return {
            "name": n8n_def.get("name", base_def.get("name", "")),
            "definition": n8n_def.get("n8n_definition", base_def.get("definition", "")),
            "positive_example": n8n_def.get("n8n_positive", base_def.get("positive_example", "")),
            "negative_example": n8n_def.get("n8n_negative", base_def.get("negative_example", "")),
        }

    return MAST_FAILURE_DEFINITIONS.get(mode, {})


def get_chain_of_thought_prompt(mode: MASTFailureMode, framework: str = None) -> str:
    """Get chain-of-thought prompt, using n8n-specific version if applicable.

    Args:
        mode: The failure mode
        framework: Framework name

    Returns:
        Chain-of-thought prompt string
    """
    if framework and 'n8n' in framework.lower() and mode in N8N_CHAIN_OF_THOUGHT_PROMPTS:
        return N8N_CHAIN_OF_THOUGHT_PROMPTS[mode]

    return CHAIN_OF_THOUGHT_PROMPTS.get(mode, "")


# ═══════════════════════════════════════════════════════════════════════
# FEW-SHOT EXEMPLARS — Scored examples with reasoning for evaluator calibration
#
# Following "Evaluation Is the Load-Bearing Part" (GoodEye Labs, 2026):
# Few-shot examples with detailed score breakdowns align evaluator judgment
# with human preferences and reduce score drift across iterations.
#
# Each entry: (input_summary, verdict, confidence, reasoning)
# ═══════════════════════════════════════════════════════════════════════

FEW_SHOT_EXEMPLARS: Dict[MASTFailureMode, str] = {

    MASTFailureMode.F6: """## Calibration Examples for Task Derailment (F6)

Example 1 (YES — detected):
Input: Agent asked to "write unit tests for auth module." Agent wrote tests, then refactored the auth module itself, renamed variables, and updated the README.
Verdict: YES | Confidence: 0.85
Reasoning: While the tests were written (partial completion), the agent deviated into unrequested refactoring and documentation updates. The scope creep pattern ("while I'm at it") is clear. The original task WAS completed, but the deviation consumed significant resources.

Example 2 (NO — not detected):
Input: Agent asked to "fix the login bug." Agent read the error logs, traced the issue to a missing null check, added the check, and ran tests to verify.
Verdict: NO | Confidence: 0.92
Reasoning: Every action directly advanced the task. Reading logs is a necessary prerequisite, not a deviation. The agent stayed focused on the specific bug without scope creep.

Example 3 (Borderline):
Input: Agent asked to "add error handling to the API endpoint." Agent added try-catch blocks, then also added input validation for the endpoint parameters.
Verdict: NO | Confidence: 0.55
Reasoning: Input validation is closely related to error handling and arguably part of "making the endpoint robust." This is a judgment call — the addition is minor and directly related. Low confidence because reasonable evaluators could disagree.""",

    MASTFailureMode.F8: """## Calibration Examples for Information Withholding (F8)

Example 1 (YES — detected):
Input: Agent has internal state showing 3 critical errors in the deployment log. Agent's output says "Deployment completed with minor issues."
Verdict: YES | Confidence: 0.90
Reasoning: "Minor issues" understates 3 critical errors. The agent's output omits severity information that would change the user's response. The gap between internal state (critical) and reported state (minor) is the withholding signal.

Example 2 (NO — not detected):
Input: Agent processed 10,000 records. Output says "Processed 10,000 records. 3 had validation warnings (see details below)." Full details provided.
Verdict: NO | Confidence: 0.95
Reasoning: Agent disclosed both the summary and the details. Summarization is not withholding when the full information is available.

Example 3 (Borderline):
Input: Agent found 15 security vulnerabilities. Output lists the top 5 by severity and says "10 additional low-severity issues found."
Verdict: NO | Confidence: 0.60
Reasoning: Agent disclosed the count and categorized by severity. Summarizing low-severity items is reasonable triage. However, some evaluators might want all 15 listed explicitly.""",

    MASTFailureMode.F9: """## Calibration Examples for Hallucination (F9)

Example 1 (YES — detected):
Input: Sources say "Revenue was $1.2M in Q3." Agent output says "Revenue reached $1.5M in Q3, showing strong growth."
Verdict: YES | Confidence: 0.95
Reasoning: The specific number ($1.5M) directly contradicts the source ($1.2M). This is not a rounding error — it's a fabricated figure. The addition of "showing strong growth" compounds the hallucination with unsupported interpretation.

Example 2 (NO — not detected):
Input: Sources say "The company was founded in 2019." Agent output says "The company, founded in 2019, has grown significantly."
Verdict: NO | Confidence: 0.88
Reasoning: The founding year matches the source. "Has grown significantly" is a general statement that doesn't contradict any specific source claim — it's interpretation, not fabrication.

Example 3 (Borderline):
Input: Sources discuss "machine learning applications in healthcare." Agent mentions "deep learning" specifically.
Verdict: NO | Confidence: 0.55
Reasoning: Deep learning is a subset of machine learning. The agent narrowed the scope but didn't fabricate information. This is imprecision, not hallucination. Low confidence because the distinction is subtle.""",

    MASTFailureMode.F3: """## Calibration Examples for Coordination Failure (F3)

Example 1 (YES — detected):
Input: Agent A sends "Please review the PR" to Agent B. Agent B responds with a completely unrelated task output about database migrations. No acknowledgment of the review request.
Verdict: YES | Confidence: 0.90
Reasoning: Agent B ignored Agent A's explicit request. The response doesn't reference the PR review at all. This is a clear coordination failure — the message was lost or ignored.

Example 2 (NO — not detected):
Input: Agent A says "Ready for review." Agent B says "Reviewing now... Found 2 issues: [list]." Agent A says "Fixed both, please re-review." Agent B says "Approved."
Verdict: NO | Confidence: 0.95
Reasoning: Clear request-response-resolution cycle. Both agents acknowledged each other's messages. Task progressed through review to approval.

Example 3 (Borderline):
Input: Agent A asks Agent B for data. Agent B provides data but in a different format than requested. Agent A proceeds with the wrong format without asking for clarification.
Verdict: YES | Confidence: 0.60
Reasoning: While Agent B did respond, the format mismatch created a silent failure. Agent A should have flagged the discrepancy. This is a subtle coordination failure — the agents communicated but didn't verify alignment.""",
}


def get_few_shot_exemplars(mode: MASTFailureMode) -> str:
    """Get few-shot calibration exemplars for a failure mode.

    Returns formatted examples with verdicts, confidence scores, and reasoning.
    Empty string if no exemplars available for this mode.
    """
    return FEW_SHOT_EXEMPLARS.get(mode, "")
