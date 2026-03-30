# LangGraph Failure Modes

Platform-specific detectors for LangGraph state-graph agent execution. These catch issues unique to LangGraph's superstep execution model, conditional routing, parallel branches, and checkpoint persistence.

---

## Recursion Limit

| Field | Value |
|---|---|
| **Detector key** | `langgraph_recursion` |
| **Severity** | Critical |

**Plain language:** Your graph agent hit the recursion limit and was forcibly stopped. It ran too many steps -- either because it's stuck in a cycle or because the task genuinely requires more steps than the limit allows.

**Technical:** Checks execution status for `recursion_limit` (definitive hit), monitors the ratio of completed supersteps to configured recursion limit (flags at >90%), and detects unbounded node repetition (same node appearing in 3+ distinct supersteps).

**Examples (non-technical):**

- Your agent was set to a maximum of 25 steps but the task needed 30 -- it stopped mid-work
- The agent kept going back to the same planning step over and over until it hit the limit
- The agent used 23 of its 25 allowed steps -- it's about to hit the wall

**Examples (technical):**

- Graph status: `"recursion_limit"` -- hard stop after exhausting configured limit
- Superstep ratio: 23/25 = 0.92 (threshold: 0.90 -- approaching limit warning)
- Node `"planner"` appears in supersteps [1, 4, 7, 10, 13] -- repeating every 3 steps (unbounded cycle)
- Recursion limit set to 10 but task requires tool-call → result → tool-call chains of 15+ steps

**Detection methods:**

- **Status Check**: Definitive detection when `status == "recursion_limit"`
- **Ratio Monitoring**: Warns when `supersteps / recursion_limit > 0.90`
- **Node Repetition Analysis**: Flags nodes appearing in 3+ distinct supersteps (configurable threshold)

**Sub-types:** `recursion_limit_hit`, `approaching_limit`, `node_repetition`

---

## State Corruption

| Field | Value |
|---|---|
| **Detector key** | `langgraph_state_corruption` |
| **Severity** | High |

**Plain language:** Your agent's state got corrupted between steps. Values changed type unexpectedly, important fields disappeared, identity fields were modified, or counters went backwards -- things that should never happen.

**Technical:** Performs 10 integrity checks across consecutive state snapshots: type changes, null injection, field deletion, value explosion (>10x container growth), list shrinkage (append-only violation), identity field mutation (user_id, session_id, etc.), counter decreases, value jumps (>100x), suspicious field injection, and node error signals containing corruption keywords.

**Examples (non-technical):**

- The user ID changed mid-conversation -- the agent confused who it was talking to
- A counter that should only go up suddenly went backwards
- A list of messages that should only grow got shorter -- messages were lost

**Examples (technical):**

- Type change: `state["price"]` transitions from `float` to `str` between supersteps 3 and 4
- Identity mutation: `state["user_id"]` changes from `"usr_abc"` to `"usr_xyz"` (immutable field violated)
- Counter decrease: `state["step_count"]` goes from 8 to 5 (monotonic violation)
- Value explosion: `state["messages"]` grows from 3 items to 45 items in one superstep (>10x)
- Null injection: `state["context"]` was `{"key": "value"}` but becomes `None`
- Node error: agent node output contains `"state_error: schema violation"`

**Detection methods:**

- **Type Drift Detection**: Flags same key changing Python type between snapshots
- **Identity Field Protection**: Monitors immutable fields (user_id, session_id, thread_id, etc.)
- **Monotonic Counter Validation**: Ensures counters like step_count never decrease
- **Container Growth Tracking**: Detects value explosion (>10x) and list shrinkage
- **Null Injection Detection**: Catches non-None values becoming None
- **Error Signal Analysis**: Scans node errors for corruption-related keywords

**Sub-types:** `type_change`, `null_injection`, `field_deletion`, `value_explosion`, `list_shrinkage`, `identity_mutation`, `counter_decrease`, `value_jump`, `field_injection`, `node_error`

---

## Edge Misrouting

| Field | Value |
|---|---|
| **Detector key** | `langgraph_edge_misroute` |
| **Severity** | High |

**Plain language:** Your graph routed to the wrong node. A conditional edge sent the agent down the wrong path -- like a GPS giving you a turn that leads to a dead end. The routing decision contradicted the agent's state or output.

**Technical:** Validates conditional edge routing by checking target node existence, detecting dead-end and unreachable nodes, and performing semantic analysis between condition text and target node types. Cross-references routing decisions against actual state values and node outputs to detect contradictions.

**Examples (non-technical):**

- The agent's condition said "task complete" but it routed to a processing node instead of the end node
- A branch in the graph leads to a node that doesn't exist anymore
- A node has no connections going out -- the workflow gets stuck there

**Examples (technical):**

- Edge condition `"finish"` routes to node `process_data` instead of `__end__` (condition-target mismatch)
- Conditional edge targets `node_id: "validator"` but no node with that ID exists in the graph
- State has `{"should_continue": false}` but conditional edge evaluates to `continue` path (state-condition contradiction)
- Node `transform` output is `{"decision": "reject"}` but edge routes to `approve` node (output-condition contradiction)
- Dead-end: node `analyze` has incoming edges but no outgoing edges and is not `__end__`

**Detection methods:**

- **Target Existence Check**: Validates edge targets exist in graph definition
- **Dead-End Detection**: Finds non-terminal nodes with no outgoing edges
- **Condition-Target Semantic Analysis**: Compares condition text against target node type
- **State-Condition Cross-Reference**: Checks if routing decisions match actual state values
- **Output-Condition Validation**: Verifies node outputs align with taken edge condition

**Sub-types:** `missing_target`, `dead_end`, `unreachable`, `condition_mismatch`, `condition_title_mismatch`, `state_condition_contradiction`, `output_condition_contradiction`, `condition_value_target_mismatch`, `skipped_conditional`

---

## Tool Failures

| Field | Value |
|---|---|
| **Detector key** | `langgraph_tool_failure` |
| **Severity** | High |

**Plain language:** A tool node in your graph failed, and the graph either couldn't recover or had to fall back to an alternative. Unrecovered tool failures can crash the entire graph execution.

**Technical:** Filters for `node_type == "tool"` nodes with `status == "failed"`, then classifies recovery pattern by checking the next superstep: retry (same node reappears), fallback (different node handles it), or uncaught (no recovery and graph fails).

**Examples (non-technical):**

- The agent tried to search the web but the search tool crashed -- the entire graph stopped
- A database query tool failed, and the agent retried it but it failed again
- A tool failed but the agent switched to an alternative tool and continued successfully

**Examples (technical):**

- Uncaught: tool `web_search` fails at superstep 3, no nodes in superstep 4, graph status: `"failed"`
- Retried failure: tool `query_db` fails at superstep 5, reappears at superstep 6 with `status: "failed"` again
- Fallback: tool `api_call` fails at superstep 4, node `fallback_handler` appears at superstep 5 with `status: "succeeded"`
- Tool error: `{"error": "ConnectionTimeout: API endpoint unreachable after 30s"}`

**Detection methods:**

- **Failure Detection**: Identifies tool nodes with `status == "failed"`
- **Retry Pattern Analysis**: Checks if same node_id appears in next superstep
- **Fallback Detection**: Identifies different nodes handling recovery in next superstep
- **Uncaught Failure Classification**: Flags failures with no recovery when graph status is failed/error

**Sub-types:** `uncaught_failure`, `retried_failure`, `fallback_handled`, `tool_failure`

---

## Parallel Sync Issues

| Field | Value |
|---|---|
| **Detector key** | `langgraph_parallel_sync` |
| **Severity** | High |

**Plain language:** Nodes running in parallel stepped on each other. Two nodes tried to write to the same piece of state simultaneously, or parallel branches didn't properly merge back together -- causing lost data or inconsistent results.

**Technical:** Detects parallel execution (multiple nodes in same superstep), then checks for write conflicts (multiple nodes writing same state key without a join), race conditions (overlapping read/write sets), missing join nodes, mixed success/failure in parallel branches, and state error keywords after parallel supersteps.

**Examples (non-technical):**

- Two parallel agents both tried to update the same field -- one overwrote the other's work
- Three branches ran in parallel but only two finished successfully -- the third failed silently
- Parallel branches completed but there was no step to merge their results together

**Examples (technical):**

- Write conflict: nodes `researcher` and `analyst` both write to `state["summary"]` in superstep 4 (no reducer defined)
- Race condition: node A reads `state["data"]`, node B writes `state["data"]` in same superstep
- Missing join: superstep 4 has 3 parallel nodes, superstep 5 has 2 nodes (expected 1 join node)
- Failed parallel: superstep 3 has nodes `[fetch_a: succeeded, fetch_b: failed]` -- mixed results
- State error: `state["sync_status"]` contains `"partial_failure"` after parallel superstep

**Detection methods:**

- **Write Conflict Detection**: Checks if multiple parallel nodes write the same state key
- **Race Condition Analysis**: Finds overlapping read/write sets between parallel nodes
- **Join Validation**: Verifies a single join node follows parallel execution
- **Mixed Result Detection**: Flags supersteps with both succeeded and failed nodes
- **Post-Parallel State Check**: Scans state for error keywords after parallel execution

**Sub-types:** `write_conflict`, `race_condition`, `missing_join`, `failed_parallel`, `downstream_failure`, `state_error_after_parallel`

---

## Checkpoint Corruption

| Field | Value |
|---|---|
| **Detector key** | `langgraph_checkpoint_corruption` |
| **Severity** | High |

**Plain language:** Your graph's saved checkpoints are corrupted. Checkpoints are snapshots that let you resume or replay a graph run -- if they're out of order, have gaps, or don't match the actual state, replaying from them will produce wrong results.

**Technical:** Validates checkpoint integrity by checking superstep monotonicity (ordering), sequence completeness (no gaps), state consistency (checkpoint state matches corresponding state snapshot), and schema completeness (all required keys from state_schema present in checkpoint state).

**Examples (non-technical):**

- A saved checkpoint says the agent was at step 5, but the next checkpoint says step 3 -- the order is wrong
- Checkpoints jump from step 2 to step 5 -- steps 3 and 4 are missing
- The checkpoint's saved state doesn't match what the agent actually had at that step

**Examples (technical):**

- Non-monotonic: checkpoint sequence has supersteps `[1, 2, 5, 3, 4]` -- step 3 appears after step 5
- Superstep gap: checkpoints at supersteps `[0, 1, 2, 5, 6]` -- gap at steps 3-4
- State inconsistency: checkpoint at superstep 3 has `{"messages": 5}` but state snapshot shows `{"messages": 8}` (value mismatch)
- Missing schema keys: `state_schema` requires `["messages", "context", "plan"]` but checkpoint only has `["messages"]`
- Extra keys in checkpoint not present in state snapshot indicate data integrity issue

**Detection methods:**

- **Monotonicity Validation**: Ensures checkpoint supersteps are non-decreasing
- **Sequence Completeness**: Detects gaps in superstep sequence (allows duplicates)
- **State Cross-Reference**: Compares checkpoint state against state snapshot at same superstep
- **Schema Completeness**: Validates all required keys from state_schema exist in checkpoint

**Sub-types:** `non_monotonic`, `superstep_gap`, `state_inconsistency`, `missing_schema_keys`
