# n8n Failure Modes

Platform-specific detectors for n8n workflow automation. These run in addition to the general-purpose detectors and catch issues unique to n8n's visual workflow architecture.

---

## Schema Mismatch

| Field | Value |
|---|---|
| **Detector key** | `n8n_schema` |
| **Severity** | Medium |

**Plain language:** Two connected nodes in your workflow are speaking different languages. One node outputs data in a format the next node doesn't expect -- like plugging a USB-C cable into a USB-A port.

**Technical:** Compares JSON schemas between consecutive nodes, checking for type mismatches (json vs text), missing fields referenced via `$json.fieldName` expressions, and progressive schema drift where >60% of original fields are lost through the workflow.

**Examples (non-technical):**

- A code node outputs text, but the next node expects structured JSON data
- A node references a field called `customerEmail` but the previous node doesn't produce that field
- Data passes through 5 nodes and by the end, most of the original fields have disappeared

**Examples (technical):**

- HTTP Request node outputs `items[]` but downstream Code node expects `$json.data` (type mismatch)
- Set node references `$json.orderId` but upstream Postgres node returns `order_id` (field mismatch)
- Schema drift: workflow starts with 12 fields, Set node keeps 4, by node 5 only 3 remain (>60% loss)
- Expression `{{ $json.customer.address.zip }}` references nested path not produced by upstream node

**Detection methods:**

- **Type Compatibility Check**: Validates source output types match destination input expectations
- **Expression Reference Validation**: Traces `$json.fieldName` references to upstream node outputs
- **Schema Drift Tracking**: Monitors field count across workflow to detect progressive data loss
- **Benign Type Filtering**: Whitelists n8n auto-coerced pairs (json-to-text, items-to-any)

**Sub-types:** `type_mismatch`, `field_mismatch`, `schema_error`, `schema_drift`, `expression_reference`

---

## Workflow Cycles

| Field | Value |
|---|---|
| **Detector key** | `n8n_cycle` |
| **Severity** | Critical |

**Plain language:** Your workflow has a loop that never ends. Nodes keep passing data back and forth or re-executing the same steps endlessly, burning execution time and credits.

**Technical:** Performs DFS graph traversal on workflow connections to detect structural cycles, then analyzes execution history for semantic loops (normalized node name repetition), ping-pong patterns (A-B-A-B with 4+ repetitions), retry storms (same node executing 4+ consecutive times), and node overexecution (single node running >40% of total executions). Filters benign patterns like pagination, polling, and scheduled retries.

**Examples (non-technical):**

- Two AI agents keep asking each other for clarification and never produce a result
- A node retries the same API call over and over because it keeps failing
- One node runs 50 times while all other nodes run once -- it's doing most of the work repeatedly

**Examples (technical):**

- Execution log: `Agent Answer → User Proxy → Agent Answer → User Proxy` repeating 8 times (semantic loop)
- Node `HTTP Request` executes 12 consecutive times with identical inputs (retry storm, threshold: 4)
- Graph cycle: `Process → Validate → Process` with no break condition in the loop
- Node `AI Agent` accounts for 65% of total node executions (overexecution threshold: 40%)

**Detection methods:**

- **Graph DFS**: Detects structural cycles in node connections
- **Semantic Loop Detection**: Groups nodes by normalized names to catch renamed duplicates
- **Ping-Pong Detection**: Identifies A-B-A-B alternation patterns between two nodes
- **Retry Storm Detection**: Flags same node executing 4+ consecutive times
- **Benign Pattern Filtering**: Excludes pagination, polling, heartbeat, forEach, splitInBatches

**Sub-types:** `semantic_loop`, `sequence_cycle`, `circular_delegation`, `pingpong`, `retry_storm`, `node_overexecution`, `self_loop`, `graph_cycle`

---

## Workflow Complexity

| Field | Value |
|---|---|
| **Detector key** | `n8n_complexity` |
| **Severity** | Medium |

**Plain language:** Your workflow has grown too complex. It has too many nodes, too many nested branches, or tries to do too many unrelated things in one workflow -- making it fragile and hard to maintain.

**Technical:** Measures structural complexity via node count (threshold: 25, scaled by workflow size), branch depth via DFS through if/switch nodes (threshold: 6), cyclomatic complexity via E-N+2P formula (threshold: 10), and separation of concerns by categorizing nodes into functional groups (flags 3+ unrelated categories).

**Examples (non-technical):**

- A workflow with 40 nodes that's become impossible to understand at a glance
- Branches nested 8 levels deep -- if this, then if that, then if another thing...
- One workflow handles email, database cleanup, API sync, and report generation -- it should be 4 separate workflows

**Examples (technical):**

- Node count: 42 nodes (threshold: 25, scaled to 33 for large workflows)
- Branch depth: 8 levels of nested If/Switch nodes (threshold: 6)
- Cyclomatic complexity: 14 (E=45, N=35, P=2; threshold: 10)
- Functional categories: `{data_fetch, ai_processing, notification, storage, file_processing}` -- 5 unrelated concerns (threshold: 3)

**Detection methods:**

- **Node Count Analysis**: Counts total nodes with size-aware scaling
- **Branch Depth Calculation**: DFS through if/switch (depth++) and merge (depth--) nodes
- **Cyclomatic Complexity**: E - N + 2P formula on workflow graph
- **Separation of Concerns**: Categorizes nodes into functional groups, flags unrelated mixing

**Sub-types:** `excessive_nodes`, `deep_branching`, `high_cyclomatic_complexity`, `multiple_concerns`, `long_execution`

---

## Error Handling Failures

| Field | Value |
|---|---|
| **Detector key** | `n8n_error` |
| **Severity** | High |

**Plain language:** Your workflow has errors that are being silently swallowed, or nodes are failing without anyone noticing. A node might fail but the workflow continues as if everything is fine, passing bad data downstream.

**Technical:** Detects hidden failures where nodes with `continueOnFail=true` still have errors, tracks null/invalid data propagation to downstream nodes (within 4-node radius), flags systemic error rates above 15%, and identifies workflows marked "success" despite containing failed nodes. Static analysis checks for AI nodes without error handlers and missing errorTrigger nodes.

**Examples (non-technical):**

- A node fails but the workflow says "success" because errors are set to be ignored
- An AI node crashes and the next node receives empty data instead of the expected response
- 20% of nodes in the workflow failed, but nobody was notified

**Examples (technical):**

- HTTP Request node has `continueOnFail=true`, returns error, downstream Set node receives `null` (hidden failure + data propagation)
- Workflow status: "success" but 3 of 15 nodes have `status: "error"` (success despite failures)
- Error rate: 4/20 nodes failed = 20% (threshold: 15%, flagged as systemic)
- AI Agent node has no `onError` handler and no errorTrigger node exists in workflow (static analysis)
- `continueOnFail` node feeds into Postgres write node -- failed data could corrupt database

**Detection methods:**

- **Hidden Failure Detection**: Finds nodes that failed despite `continueOnFail=true`
- **Data Propagation Tracking**: Traces null/invalid data from failed nodes to downstream consumers (4-node radius)
- **Error Rate Analysis**: Flags workflows where >15% of nodes failed
- **Static Error Handler Audit**: Checks for unprotected AI nodes, missing errorTrigger nodes, and risky `continueOnFail` chains

**Sub-types:** `hidden_failure`, `invalid_data_propagation`, `high_error_rate`, `success_despite_failures`, `unprotected_ai_nodes`, `missing_error_trigger`

---

## Resource Exhaustion

| Field | Value |
|---|---|
| **Detector key** | `n8n_resource` |
| **Severity** | High |

**Plain language:** Your workflow is consuming too many resources. Data is growing uncontrollably as it passes through nodes, API calls are being made excessively, or AI nodes are running without any token limits.

**Technical:** Tracks content size growth across nodes (flags >2.5x expansion), monitors data amplification (one item becoming many), counts API node executions (flags >5 calls to same node), and performs static analysis for AI nodes missing `maxTokens`, loops missing `maxIterations`, and HTTP nodes missing timeouts.

**Examples (non-technical):**

- A small input grows into a massive dataset as it passes through the workflow
- The same API endpoint is called 12 times in a single run
- An AI node has no limit on how many tokens it can use, risking a huge bill

**Examples (technical):**

- Content explosion: input 500 chars → output 45,000 chars after Code node (90x growth, threshold: 2.5x)
- Data amplification: 1 input item → 250 output items after SplitInBatches node (250x, threshold: 2.5x)
- API abuse: `HTTP Request` node to `api.example.com` called 12 times (threshold: 5)
- Static: AI Agent node has no `maxTokens` parameter set (unbounded token usage)
- Sequential AI: `AI Agent → Code → AI Agent` -- two AI nodes with no data reduction between them

**Detection methods:**

- **Content Explosion Tracking**: Monitors character count growth across nodes
- **Data Amplification Detection**: Tracks item count changes between nodes
- **API Call Counting**: Flags excessive calls to the same HTTP/API node
- **Static Resource Audit**: Checks for missing `maxTokens`, `maxIterations`, timeouts

**Sub-types:** `content_explosion`, `data_amplification`, `api_abuse`, `runaway_accumulation`, `oversized_payload`, `unbounded_ai_tokens`, `unbounded_loops`, `http_no_timeout`, `sequential_ai_no_reduction`

---

## Timeout Failures

| Field | Value |
|---|---|
| **Detector key** | `n8n_timeout` |
| **Severity** | High |

**Plain language:** Your workflow or individual nodes are taking too long. A webhook caller may have already given up waiting, or a node is stalled with no progress for over a minute.

**Technical:** Monitors workflow-level duration (threshold: 5 min), webhook response time (threshold: 30s for caller timeout), per-node execution against type-specific thresholds (HTTP: 30s, AI: 120s, Code: 10s), and inter-node gaps indicating stalls (threshold: 60s). Static analysis checks for missing timeout configurations.

**Examples (non-technical):**

- A workflow triggered by a webhook takes 45 seconds -- the caller has already timed out at 30 seconds
- An AI node has been processing for 3 minutes with no response
- There's a 90-second gap between two nodes where nothing happened -- the workflow stalled

**Examples (technical):**

- Workflow duration: 412s (threshold: 300s / 5 min)
- Webhook-triggered workflow: 35s total (threshold: 30s -- HTTP caller likely received 504)
- AI Agent node: 185s execution (threshold: 120s for AI nodes)
- Stall: 95s gap between `Code` node completion and `HTTP Request` node start (threshold: 60s)
- Static: Webhook node has no `responseTimeout` set; HTTP Request has no `timeout` parameter

**Detection methods:**

- **Workflow Duration Check**: Total execution time vs 5-minute threshold
- **Webhook Timeout Detection**: Flags webhook-triggered workflows exceeding 30s
- **Per-Node Timeout**: Type-specific thresholds (HTTP 30s, AI 120s, Code 10s, Set 1s)
- **Stall Detection**: Inter-node execution gaps exceeding 60s
- **Static Timeout Audit**: Missing timeout configurations on webhook, HTTP, AI, and Merge/Wait nodes

**Sub-types:** `workflow_timeout`, `webhook_timeout`, `node_timeout`, `stalled_execution`, `missing_workflow_timeout`, `webhook_no_response_timeout`, `http_no_timeout`, `ai_no_timeout`, `merge_wait_stall_risk`
