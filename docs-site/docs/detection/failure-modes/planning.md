# Planning Failures (FC1)

Planning failures occur when the task specification, decomposition, or workflow design is flawed before any agent begins execution.

---

## F1: Specification Mismatch

| Field | Value |
|---|---|
| **Detector key** | `specification` |
| **Tier** | ICP |
| **Severity** | Medium |
| **Accuracy** | F1 0.703, P 0.592, R 0.866 |
| **MAST mapping** | FM-1.1 Disobey Task Specification |

**What it detects:** Task output doesn't match the user's original specification. Catches scope drift, missing requirements, ambiguous specs, language mismatches, and conflicting specifications.

**Real-world examples:**

- User requests Python code but agent delivers TypeScript implementation
- Task asks for 500-word summary but agent delivers 150 words
- Agent reformulates requirements and loses critical constraints
- Output uses deprecated API patterns (e.g., Python 2 `print` statement)

**Detection methods:**

- **Semantic Coverage**: Measures how well output covers each requirement using embeddings
- **Keyword Matching**: Checks for presence of required elements, topics, and constraints
- **Code Quality Checks**: Validates language match, deprecated syntax, stub implementations
- **Numeric Tolerance**: Handles approximate constraints like word counts (within 20%)

**Sub-types:** `scope_drift`, `missing_requirement`, `ambiguous_spec`, `conflicting_spec`, `overspecified`

---

## F2: Poor Task Decomposition

| Field | Value |
|---|---|
| **Detector key** | `decomposition` |
| **Tier** | ICP |
| **Severity** | Medium |
| **Accuracy** | F1 0.727, P 0.727, R 0.727 |
| **MAST mapping** | FM-1.2 |

**What it detects:** Task breakdown creates subtasks that are impossible, circular, vague, too granular, or too broad.

**Real-world examples:**

- Task decomposed into subtasks with circular dependencies (A needs B, B needs A)
- Subtask says "handle the infrastructure" with no specifics
- Simple "add button" task over-decomposed into 15 steps when 3 would suffice
- Complex system design has only 2 subtasks, each too broad to execute

**Detection methods:**

- **Dependency Analysis**: Detects circular, missing, or impossible dependencies
- **Granularity Check**: Validates task-aware decomposition depth (complex vs simple)
- **Vagueness Detection**: Flags non-actionable steps using indicator words ("etc", "various", "if necessary")
- **Complexity Estimation**: Identifies subtasks too broad for single execution

**Sub-types:** `impossible_subtask`, `missing_dependency`, `circular_dependency`, `duplicate_work`, `wrong_granularity`, `missing_subtask`, `vague_subtask`, `overly_complex`

---

## F3: Resource Misallocation (Enterprise)

| Field | Value |
|---|---|
| **Detector key** | `resource_misallocation` |
| **Tier** | Enterprise |
| **Severity** | High |
| **Accuracy** | Benchmarking in progress |
| **MAST mapping** | FM-1.3 |

**What it detects:** Multiple agents compete for shared resources, leading to contention, starvation, or deadlock.

**Real-world examples:**

- Three agents simultaneously request access to the same database connection pool
- One agent holds a resource lock indefinitely, starving other agents
- Circular wait: Agent A waits for resource held by B, B waits for A
- Resources allocated inefficiently -- most agents idle while one is overloaded

**Detection methods:**

- **Contention Analysis**: Tracks concurrent resource access requests
- **Starvation Detection**: Identifies agents that never acquire needed resources
- **Deadlock Graph**: Analyzes circular wait conditions
- **Efficiency Scoring**: Measures resource utilization distribution

**Sub-types:** `contention`, `starvation`, `deadlock_risk`, `inefficient_allocation`, `excessive_wait`, `resource_exhaustion`

---

## F4: Inadequate Tool Provision (Enterprise)

| Field | Value |
|---|---|
| **Detector key** | `tool_provision` |
| **Tier** | Enterprise |
| **Severity** | High |
| **Accuracy** | Benchmarking in progress |
| **MAST mapping** | FM-1.4 |

**What it detects:** Agents lack the tools they need to complete assigned tasks.

**Real-world examples:**

- Agent attempts to call `search_database` but no such tool is provisioned
- Agent hallucinates tool name `web_search_v2` that doesn't exist
- Agent manually scrapes data because it lacks a proper API client tool
- Tool call fails repeatedly because the tool's capabilities don't match the task

**Detection methods:**

- **Tool Inventory Check**: Compares attempted tool calls against available tools
- **Hallucinated Tool Detection**: Identifies tool names not in the provisioned set
- **Workaround Detection**: Flags manual approaches that suggest missing tools
- **Capability Gap Analysis**: Matches task requirements against tool capabilities

**Sub-types:** `missing_tool`, `hallucinated_tool`, `tool_capability_gap`, `workaround_detected`, `tool_call_failure`

---

## F5: Flawed Workflow Design

| Field | Value |
|---|---|
| **Detector key** | `workflow` |
| **Tier** | ICP |
| **Severity** | High |
| **Accuracy** | F1 0.797, P 0.851, R 0.750 |
| **MAST mapping** | FM-1.5 |

**What it detects:** Structural problems in agent workflow graphs including unreachable nodes, dead ends, missing error handling, bottlenecks, and missing termination conditions.

**Real-world examples:**

- Workflow has a node that can never be reached from the start node
- Agent graph has a path with no terminal node -- workflow never ends
- AI processing nodes have no error handling -- single failure crashes entire workflow
- All paths funnel through a single bottleneck node

**Detection methods:**

- **Graph Traversal**: Checks reachability of all nodes from start
- **Dead End Detection**: Identifies paths with no terminal nodes
- **Error Handler Audit**: Verifies error handling on critical nodes
- **Bottleneck Analysis**: Detects nodes with disproportionate in-degree
- **Depth Analysis**: Flags excessively deep sequential chains

**Sub-types:** `unreachable_node`, `dead_end`, `missing_error_handling`, `infinite_loop_risk`, `bottleneck`, `missing_termination`, `orphan_node`, `excessive_depth`
