# Execution Failures (FC2)

Execution failures occur during agent runtime -- when agents deviate from their task, ignore context, withhold information, or fail to coordinate with each other.

---

## F6: Task Derailment

| Field | Value |
|---|---|
| **Detector key** | `derailment` |
| **Tier** | ICP |
| **Severity** | High |
| **Accuracy** | F1 0.800, P 0.791, R 0.809 |
| **MAST mapping** | FM-2.3 Task Derailment |

**Plain language:** The agent went off-topic. It was asked to do one thing but started doing something else entirely -- like asking someone to write a blog post and getting API documentation instead.

**Technical:** Computes embedding distance between the task description and the agent's output, combined with topic drift detection via keyword clustering and task substitution pair analysis (e.g., authentication vs authorization confusion).

**Examples (non-technical):**

- You ask for a pricing analysis and the agent delivers a feature comparison instead
- A code review agent starts writing new features rather than reviewing existing ones
- An agent asked to summarize a document starts editing it instead

**Examples (technical):**

- Agent assigned `write_auth_docs` produces output about authorization middleware instead of authentication flows
- Research agent's output embeddings have cosine similarity < 0.3 with the task description embedding
- Agent confuses `pytest` test writing with `unittest` -- delivers wrong framework's patterns

**Detection methods:**

- **Semantic Similarity**: Compares embedding distance between task description and output
- **Topic Drift Detection**: Tracks topic focus using keyword clustering
- **Task Substitution Detection**: Identifies confused concepts using substitution pairs
- **Coverage Verification**: Checks whether core task requirements are addressed

---

## F7: Context Neglect

| Field | Value |
|---|---|
| **Detector key** | `context` |
| **Tier** | ICP |
| **Severity** | Medium |
| **Accuracy** | F1 0.731, P 0.856, R 0.637 |
| **MAST mapping** | FM-1.4 Loss of Conversation History |

**Plain language:** The agent ignored information it was given. A previous step provided important context, but the agent acted as if it never received it -- starting from scratch instead of building on prior work.

**Technical:** Checks for key information elements from upstream context using element matching, critical marker detection (`CRITICAL`, `IMPORTANT` labels), and semantic overlap measurement between context and response.

**Examples (non-technical):**

- Agent B ignores Agent A's research findings and redoes the analysis from scratch
- Important warnings from a previous step are completely absent from the output
- Agent says "based on prior analysis" but doesn't actually use any of the prior data

**Examples (technical):**

- Upstream context contains `CRITICAL: rate limit is 100 req/s` but agent's output proposes 1000 req/s
- Agent receives structured JSON context with 12 fields but only references 2 in its response
- Context marked `priority: high` with 8 key findings -- agent's output mentions zero of them

**Detection methods:**

- **Element Matching**: Checks for key information elements from upstream context
- **Critical Marker Detection**: Flags when CRITICAL/IMPORTANT-labeled context is ignored
- **Conceptual Overlap**: Measures semantic similarity between context and response
- **Reference Tracking**: Verifies claims of context usage against actual content

---

## F8: Information Withholding

| Field | Value |
|---|---|
| **Detector key** | `withholding` |
| **Tier** | ICP |
| **Severity** | Medium |
| **Accuracy** | F1 0.796, P 0.661, R 1.000 |
| **MAST mapping** | FM-2.4 Information Withholding |

**Plain language:** The agent knows something important but didn't share it. It might have found a security issue but only reported "task completed successfully" -- hiding bad news or over-simplifying critical details.

**Technical:** Compares information density between the agent's internal state and its output, detecting critical omissions (errors, security issues), negative finding suppression, and excessive summarization loss.

**Examples (non-technical):**

- Agent finds a security problem but reports only "everything looks good"
- A 10-page analysis is summarized into 2 sentences, losing all the important details
- Agent reports only the positive findings and hides all the errors it encountered

**Examples (technical):**

- Agent's internal state contains `{"vulnerabilities": [{"severity": "critical", ...}]}` but output says "No issues found"
- Input document has 47 data points; agent output references only 3
- Agent discovers `DeprecationWarning` in 4 dependencies but output lists zero deprecations

**Detection methods:**

- **Information Density Comparison**: Compares input richness against output content
- **Critical Omission Detection**: Checks for missing high-importance information (errors, security, financial)
- **Negative Suppression Detection**: Flags when negative findings are absent from positive-heavy reports
- **Semantic Retention Check**: Uses embeddings to verify key concepts are preserved

**Critical pattern weights:**

| Pattern | Weight |
|---|---|
| Errors/failures | 1.0 |
| Security/vulnerabilities | 1.0 |
| Time constraints | 0.9 |
| Financial info | 0.8 |
| Warnings | 0.7 |
| Deprecation notices | 0.6 |

**Sub-types:** `critical_omission`, `detail_loss`, `negative_suppression`, `selective_reporting`, `context_stripping`

---

## F9: Role Usurpation (Enterprise)

| Field | Value |
|---|---|
| **Detector key** | `role_usurpation` |
| **Tier** | Enterprise |
| **Severity** | High |
| **Accuracy** | Benchmarking in progress |
| **MAST mapping** | FM-2.6 |

**Plain language:** The agent overstepped its role. A reviewer started making changes instead of just reviewing, or a support agent made admin-level decisions it wasn't authorized to make.

**Technical:** Validates agent actions against allowed/forbidden action sets defined in the role specification, detecting scope expansion, authority violations, and task hijacking through action-role boundary analysis.

**Examples (non-technical):**

- A code reviewer starts rewriting the code instead of just reviewing it
- A research assistant makes final product decisions that should be the manager's call
- A support agent escalates itself to admin privileges without authorization

**Examples (technical):**

- Agent with `role: "reviewer"` calls `git commit` and `git push` -- write actions outside its `allowed_actions: ["comment", "approve", "request_changes"]`
- Agent with `role: "data_analyst"` executes `DROP TABLE` -- a DBA-only operation
- Agent gradually expands: first reads files, then edits configs, then modifies production deployments

**Detection methods:**

- **Role Boundary Check**: Validates actions against allowed/forbidden action sets
- **Scope Analysis**: Detects gradual scope expansion beyond assignment
- **Authority Verification**: Checks decision authority against role definition
- **Task Hijacking Detection**: Identifies when agent takes over another agent's task

**Sub-types:** `role_violation`, `scope_expansion`, `authority_violation`, `decision_overreach`, `task_hijacking`

---

## F10: Communication Breakdown

| Field | Value |
|---|---|
| **Detector key** | `communication` |
| **Tier** | ICP |
| **Severity** | Medium |
| **Accuracy** | F1 0.821, P 0.780, R 0.868 |
| **MAST mapping** | FM-2.1, FM-2.2, FM-2.5 |

**Plain language:** Agents are miscommunicating. One agent sends a message but the receiving agent misunderstands it -- like giving someone directions in kilometers when they expect miles.

**Technical:** Measures alignment between sender intent and receiver interpretation using semantic similarity, validates message format compliance against expected schemas, and detects ambiguous or incomplete inter-agent messages.

**Examples (non-technical):**

- Agent A sends data in one format but Agent B expects a different format
- An ambiguous instruction like "process the results" is interpreted differently by two agents
- Critical details are missing from a handoff message between agents

**Examples (technical):**

- Agent A sends JSON `{"price": "19.99"}` (string) but Agent B expects `{"price": 19.99}` (number), causing a type error
- Agent A's message says "update the config" -- Agent B updates `nginx.conf` instead of `app.config.yml`
- Inter-agent message missing required `correlation_id` field, breaking downstream tracing

**Detection methods:**

- **Intent Alignment**: Measures alignment between sender's intent and receiver's interpretation
- **Format Compliance**: Checks message format matches expected schema
- **Ambiguity Detection**: Flags semantically ambiguous instructions
- **Completeness Check**: Verifies all required information is present

**Sub-types:** `intent_mismatch`, `format_mismatch`, `semantic_ambiguity`, `incomplete_information`, `conflicting_instructions`

---

## F11: Coordination Failure

| Field | Value |
|---|---|
| **Detector key** | `coordination` |
| **Tier** | ICP |
| **Severity** | Critical |
| **Accuracy** | F1 0.912, P 0.845, R 0.992 |
| **MAST mapping** | FM-2.5 Ignored Input |

**Plain language:** Agents can't work together. They're waiting on each other in circles, ignoring each other's messages, or going back and forth endlessly without making progress -- like two people stuck saying "no, you go first" at a doorway.

**Technical:** Tracks message acknowledgment patterns, detects excessive back-and-forth exchanges (threshold: 5), analyzes delegation chains for cycles, and monitors whether inter-agent exchanges produce measurable forward progress.

**Examples (non-technical):**

- Agent A waits for Agent B's output while Agent B waits for Agent A -- neither moves
- One agent sends a request but the other agent never responds
- Two agents exchange 15 messages clarifying the same thing without making any progress

**Examples (technical):**

- Circular delegation: task routed A → B → C → A, creating an infinite delegation loop
- Agent A's `POST /handoff` to Agent B returns no acknowledgment after 30s timeout
- Agents exchange 12 `clarify_request`/`clarify_response` messages with cosine similarity > 0.95 (repeating themselves)
- Agent B receives Agent A's output but `processed: false` -- input was silently dropped

**Detection methods:**

- **Message Acknowledgment Tracking**: Detects ignored or unacknowledged messages
- **Back-and-Forth Detection**: Flags excessive message exchanges between agent pairs (threshold: 5)
- **Circular Delegation Analysis**: Traces delegation chains for cycles
- **Progress Monitoring**: Measures whether exchanges produce forward progress

**Sub-types:** `ignored_messages`, `information_withholding`, `excessive_back_forth`, `circular_delegation`, `conflicting_instructions`, `duplicate_dispatch`, `data_corruption_relay`, `ordering_violations`, `excessive_delegation`, `resource_contention`, `rapid_instruction_change`, `response_delay`, `indirect_delegation`
