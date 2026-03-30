# Planning Failures (FC1)

Planning failures occur when the task specification, decomposition, or workflow design is flawed before any agent begins execution.

---

## F1: Specification Mismatch

| Field | Value |
|---|---|
| **Detector key** | `specification` |
| **Tier** | ICP |
| **Severity** | Medium |
| **Accuracy** | F1 0.857, P 0.923, R 0.800 |
| **MAST mapping** | FM-1.1 Disobey Task Specification |

**Plain language:** The agent delivered something different from what was asked for. Like ordering a blue car and receiving a red one -- the work got done, but it doesn't match the original request.

**Technical:** Measures semantic coverage between the user's specification and the agent's output using embedding similarity, keyword matching, and structural analysis. Detects scope drift, missing requirements, and constraint violations.

**Examples (non-technical):**

- You ask for a 500-word summary and get back 150 words
- You request a report in Spanish but receive it in English
- The agent completes only 3 of 5 requested tasks

**Examples (technical):**

- User specifies Python implementation but agent delivers TypeScript
- Agent output uses deprecated `print` statement syntax (Python 2 vs 3)
- Task requires REST API endpoints but agent generates GraphQL schema

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
| **Accuracy** | F1 1.000, P 1.000, R 1.000 |
| **MAST mapping** | FM-1.2 |

**Plain language:** The agent broke a big task into smaller pieces badly. Some pieces depend on each other in circles, some are too vague to act on, and the overall breakdown doesn't make sense for the complexity of the work.

**Technical:** Analyzes task decomposition graphs for structural issues including circular dependencies, granularity mismatches, and vague subtask definitions using dependency analysis and complexity estimation.

**Examples (non-technical):**

- A project plan where Step 3 requires Step 5 to be done first, but Step 5 requires Step 3
- A subtask that just says "handle the infrastructure" with no specifics
- A simple button change broken into 15 steps when 3 would do

**Examples (technical):**

- Subtask dependency graph contains cycle: `parse_data` → `validate_schema` → `parse_data`
- Subtask description uses non-actionable language: "etc.", "various components", "if necessary"
- Complex distributed system redesign decomposed into only 2 subtasks, each too broad for a single agent

**Detection methods:**

- **Dependency Analysis**: Detects circular, missing, or impossible dependencies
- **Granularity Check**: Validates task-aware decomposition depth (complex vs simple)
- **Vagueness Detection**: Flags non-actionable steps using indicator words
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

**Plain language:** Multiple agents are fighting over the same resources, like two people trying to use one printer at the same time. This causes delays, deadlocks, or wasted capacity.

**Technical:** Tracks concurrent resource access patterns across agents, detecting contention, starvation conditions, circular wait (deadlock), and inefficient allocation using resource graph analysis.

**Examples (non-technical):**

- Three agents all need database access at once, causing everything to slow down
- One agent holds a lock indefinitely, preventing all other agents from working
- Most agents sit idle while one agent is completely overloaded

**Examples (technical):**

- Three agents simultaneously request the same database connection pool, causing pool exhaustion
- Agent A holds write lock on `users` table while Agent B holds lock on `orders`, both waiting for the other (deadlock)
- Load balancer routes 90% of requests to one agent instance while others have zero utilization

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

**Plain language:** The agent doesn't have the right tools to do its job. It's like asking someone to build furniture but not giving them a screwdriver -- they'll either fail or improvise badly.

**Technical:** Compares attempted tool invocations against the provisioned tool inventory, detecting hallucinated tool names, capability gaps, and manual workarounds that indicate missing tools.

**Examples (non-technical):**

- Agent tries to search a database but that capability was never set up
- Agent manually copies data from a website because it lacks a proper data connector
- Agent keeps failing because the tool it needs doesn't support the required file format

**Examples (technical):**

- Agent calls `search_database()` but no such tool exists in its tool registry
- Agent hallucinates tool name `web_search_v2` -- only `web_search` is provisioned
- Agent writes raw HTTP requests to scrape data because it lacks an API client tool

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
| **Accuracy** | F1 0.667, P 0.517, R 0.938 |
| **MAST mapping** | FM-1.5 |

**Plain language:** The workflow itself is badly designed -- some steps can never be reached, some paths have no ending, and there's no plan for what happens when things go wrong.

**Technical:** Performs graph traversal on workflow DAGs to detect unreachable nodes, dead-end paths, missing error handlers, bottleneck nodes, and excessive sequential depth.

**Examples (non-technical):**

- A workflow step exists but no path ever leads to it -- it's orphaned
- A workflow path has no finish line -- the process never ends
- If any single step fails, the entire workflow crashes because there's no error handling

**Examples (technical):**

- Node `validate_output` is unreachable from the start node in the workflow DAG
- Execution path through `process → transform → enrich` has no terminal node
- AI processing nodes lack try/catch -- a single `APIError` crashes the entire pipeline
- All 8 parallel paths funnel through a single `aggregate` node (bottleneck)

**Detection methods:**

- **Graph Traversal**: Checks reachability of all nodes from start
- **Dead End Detection**: Identifies paths with no terminal nodes
- **Error Handler Audit**: Verifies error handling on critical nodes
- **Bottleneck Analysis**: Detects nodes with disproportionate in-degree
- **Depth Analysis**: Flags excessively deep sequential chains

**Sub-types:** `unreachable_node`, `dead_end`, `missing_error_handling`, `infinite_loop_risk`, `bottleneck`, `missing_termination`, `orphan_node`, `excessive_depth`
