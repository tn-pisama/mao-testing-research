# Detection Principles

Explicit evaluation criteria for each Pisama detector, following the principle that
**concrete criteria > vague thresholds** (GoodEye Labs, "Evaluation Is the Load-Bearing Part").

Each principle defines: WHAT the detector evaluates, WHY it matters, WHEN to flag,
and the BOUNDARY between acceptable and unacceptable.

## Evaluation Type Classification

### Permanent Evaluations
Quality standards that matter regardless of model capability:
- All Core ICP detectors (17)
- All framework detectors (n8n, Dify, LangGraph, OpenClaw — 24)
- orchestration_quality, multi_chain (2)
- cowork_safety (1)
- plan_correctness, implementation_correctness, cross_database (3)

### Temporary Evaluations
Compensate for current model limitations; will become less relevant as models improve:
- adaptive_thinking — models will self-regulate reasoning depth
- subagent_boundary — Claude will enforce its own tool boundaries
- computer_use — screen interaction accuracy will improve
- dispatch_async — async reliability will improve
- scheduled_task — scheduling robustness will improve

---

## Beta Detector Principles (F1 0.40-0.69)

### agent_teams (F1=0.552) — PERMANENT

**Principle**: A multi-agent team has failed when agents stop advancing the shared task list.

**Specific criteria**:
1. **Silent agent**: Any agent assigned a task that produces zero substantive output (< 20 meaningful tokens) indicates context loss — the agent "vanished" (Issue #23620 pattern).
2. **Communication without progress**: 3+ message rounds between the same agent pair where zero tasks change status = coordination loop. Distinguished from legitimate clarification by checking task list state before/after the exchange.
3. **Lead hoarding**: One agent handles > 60% of all tool calls/messages despite team having 3+ members = the lead is doing work instead of coordinating.
4. **Duplicate work**: Two agents modify the same file or produce > 60% overlapping output content.

**Boundary**: NOT a failure: clarification questions (Q&A pattern with resolution), uneven task sizes (one agent takes longer on a harder task), team lead doing initial planning (expected).

---

### adaptive_thinking (F1=0.530) — TEMPORARY

**Principle**: Flag when the cost of reasoning is disproportionate to the value of the output, using statistical baselines from production usage.

**Specific criteria**:
1. **Statistical anomaly**: Session cost exceeds P95 * 1.5 of the rolling baseline for that model type, indicating the model allocated excessive reasoning to a routine task.
2. **Z-score outlier**: Cost Z-score > 2.5 from mean = severe outlier (< 1% of sessions).
3. **Effort mismatch**: High cost (> P75) at low/medium effort level = likely misconfigured client.

**Boundary**: NOT a failure: complex queries legitimately requiring max effort (math proofs, multi-step reasoning), first call in a session (cache cold start increases cost), cost within P90 range.

**Why temporary**: As adaptive thinking matures, models will correctly match effort to complexity. The baseline distribution will narrow, making this detector unnecessary.

---

### subagent_boundary (F1=0.460) — TEMPORARY

**Principle**: Flag when a subagent uses capabilities outside its designated scope, or exhibits tool usage patterns significantly beyond normal for its type.

**Specific criteria**:
1. **Tool violation**: Any tool call not in the subagent's allowed_tools list = definitive boundary violation.
2. **Spawn attempt**: Subagents cannot spawn children. spawn_attempts > 0 = violation.
3. **Tool diversity anomaly**: Tool count exceeding P95+2 for the subagent's type (Explore: ~5 tools typical, general: ~7 typical).

**Boundary**: NOT a failure: using all allowed tools (full utilization != violation), high tool count within expected range, general-purpose agents that legitimately use many tools.

**Why temporary**: Claude Code will enforce subagent tool restrictions at the framework level, making this detector redundant. Currently, enforcement is advisory.

---

### dify_variable_leak (F1=0.460) — PERMANENT

**Principle**: Flag when sensitive data (API keys, passwords, tokens, PII) appears in workflow node outputs where it shouldn't be visible.

**Specific criteria**:
1. **Pattern match**: Output contains strings matching known sensitive formats (sk-proj-*, Bearer eyJ*, password=*, aws_secret_*).
2. **Scope leak**: A variable defined in one node's scope appears in a downstream node that shouldn't have access to it (parent_node_id boundary violation).
3. **Context**: "api_key_example" or "placeholder" in the value = NOT a leak (test/documentation pattern).

**Boundary**: NOT a failure: variables in system prompts (intentional), encrypted/hashed values, environment variable references (not the actual value), example/placeholder strings.

---

### langgraph_parallel_sync (F1=0.667) — PERMANENT

**Principle**: Flag when parallel branches in a LangGraph execution fail to synchronize correctly, causing data loss or deadlock.

**Specific criteria**:
1. **Branch completion mismatch**: One branch completes while another is still running AND the join node proceeds without waiting = data loss.
2. **State conflict**: Two branches write to the same state key with different values = race condition.
3. **Deadlock**: Both branches waiting on each other's output = infinite wait.

**Boundary**: NOT a failure: branches completing at different times if the join node properly waits, one branch failing while others succeed (handled by error recovery), intentional fan-out where branches are independent.

**Current issue**: Detector is too aggressive — flags clean executions as FPs. Needs to verify that the join node actually proceeded incorrectly, not just that branches had different timing.

---

### loop (F1=0.652) — PERMANENT

**Principle**: Flag when an agent repeats the same actions or produces the same outputs without making progress toward the task goal.

**Specific criteria**:
1. **Exact repetition**: State hash repeats 3+ times = structural loop.
2. **Semantic repetition**: Output embedding similarity > 0.95 across 3+ consecutive states = semantic loop (saying the same thing differently).
3. **Action repetition**: Same tool called with same arguments 3+ times = stuck.

**Boundary**: NOT a failure: retries with different parameters, iterative refinement where output improves each time, polling/monitoring loops (intentional repetition with status checks).

---

### injection (F1=0.667) — PERMANENT

**Principle**: Flag when input text contains patterns designed to override the agent's system instructions or manipulate its behavior.

**Specific criteria**:
1. **Override patterns**: "Ignore previous instructions", "You are now", "System prompt:", "DAN mode".
2. **Role manipulation**: Attempting to make the agent adopt a different persona or bypass safety constraints.
3. **Instruction extraction**: Attempting to reveal the system prompt or internal instructions.

**Boundary**: NOT a failure: discussion ABOUT injection (educational context), the word "ignore" in technical context ("ignore deprecated API"), quoted examples in security documentation.

---

### workflow (F1=0.667) — PERMANENT

**Principle**: Flag when a workflow definition has structural issues that will cause execution failures: unreachable nodes, missing error handling, bottlenecks, or infinite paths.

**Specific criteria**:
1. **Unreachable nodes**: Nodes with no incoming edges (orphans) that are not start nodes.
2. **Dead ends**: Nodes with no outgoing edges that are not end nodes.
3. **Missing error handling**: Nodes that can fail but have no error branch.
4. **Excessive sequential depth**: > 5 sequential nodes without branching (bottleneck risk).

**Boundary**: NOT a failure: intentional sequential pipelines (each step depends on previous), error handling via global error handler (not per-node), draft/incomplete workflows (expected during development).
