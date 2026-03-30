# Execution Failures (FC2)

Execution failures occur during agent runtime -- when agents deviate from their task, ignore context, withhold information, or fail to coordinate with each other.

---

## F6: Task Derailment

| Field | Value |
|---|---|
| **Detector key** | `derailment` |
| **Tier** | ICP |
| **Severity** | High |
| **Accuracy** | F1 0.667, P 0.588, R 0.769 |
| **MAST mapping** | FM-2.3 Task Derailment |

**What it detects:** Agent goes off-topic or deviates from its assigned task. One of the most common failure modes (20% prevalence in MAST-Data).

**Real-world examples:**

- Agent asked to write authentication docs starts writing about authorization instead
- Research agent asked about pricing analysis delivers feature comparison instead
- Code review agent starts implementing new features rather than reviewing
- Agent asked for a blog post delivers API documentation

**Detection methods:**

- **Semantic Similarity**: Compares embedding distance between task description and output
- **Topic Drift Detection**: Tracks topic focus using keyword clustering
- **Task Substitution Detection**: Identifies confused concepts using task clusters and substitution pairs (e.g., authentication vs authorization)
- **Coverage Verification**: Checks whether core task requirements are addressed

!!! note "Common false positives"
    Framework-specific patterns (AG2 tool_code, MetaGPT speaker selection) and legitimate comprehensive responses that touch adjacent topics can trigger false positives.

---

## F7: Context Neglect

| Field | Value |
|---|---|
| **Detector key** | `context` |
| **Tier** | ICP |
| **Severity** | Medium |
| **Accuracy** | F1 0.865, P 0.762, R 1.000 |
| **MAST mapping** | FM-1.4 Loss of Conversation History |

**What it detects:** Agent ignores or fails to use upstream context provided by previous agents or workflow steps.

**Real-world examples:**

- Agent B ignores the analysis provided by Agent A and starts from scratch
- Context marked as `CRITICAL` in upstream output is completely absent from response
- Agent references "based on prior analysis" but doesn't actually use any prior data
- Key findings from upstream research are lost during agent-to-agent handoff

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
| **Accuracy** | F1 0.800, P 0.667, R 1.000 |
| **MAST mapping** | FM-2.4 Information Withholding |

**What it detects:** Agent doesn't share critical information with peers, including omitting negative findings, over-summarizing, or selectively reporting.

**Real-world examples:**

- Agent discovers a security vulnerability but reports only "task completed successfully"
- Agent summarizes a 10-page report into 2 sentences, losing critical details
- Agent reports only positive findings, omitting error cases and edge conditions
- Output is significantly less informative than the agent's internal state suggests

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

**What it detects:** Agent exceeds its designated role boundaries, taking actions or making decisions reserved for other roles.

**Real-world examples:**

- Code reviewer agent starts modifying code instead of just reviewing
- Research agent makes final product decisions reserved for the PM agent
- Support agent escalates to admin-level operations without authorization
- Agent gradually expands its scope of actions beyond its original assignment

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
| **Accuracy** | F1 0.667, P 0.571, R 0.800 |
| **MAST mapping** | FM-2.1, FM-2.2, FM-2.5 |

**What it detects:** Messages between agents are misunderstood or misinterpreted, causing incorrect downstream behavior.

**Real-world examples:**

- Agent A sends JSON data but Agent B parses it as plain text
- Ambiguous instruction "process the results" interpreted differently by two agents
- Agent receives conflicting instructions from two upstream agents
- Critical information missing from inter-agent message

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
| **Accuracy** | F1 0.914, P 0.842, R 1.000 |
| **MAST mapping** | FM-2.5 Ignored Input |

**What it detects:** Handoff failures, circular delegation, excessive back-and-forth, and ignored messages between coordinating agents.

**Real-world examples:**

- Agent A waits for B's output while B waits for A's approval -- deadlock
- Message from Agent A to Agent B never acknowledged
- Agents A and B exchange 15 clarification messages without making progress
- Task delegated A -> B -> C -> A, creating circular delegation

**Detection methods:**

- **Message Acknowledgment Tracking**: Detects ignored or unacknowledged messages
- **Back-and-Forth Detection**: Flags excessive message exchanges between agent pairs (threshold: 5)
- **Circular Delegation Analysis**: Traces delegation chains for cycles
- **Progress Monitoring**: Measures whether exchanges produce forward progress

The `CoordinationAnalyzer` checks 12 issue types including information withholding, conflicting instructions, duplicate dispatch, data corruption relay, ordering violations, resource contention, rapid instruction changes, and response delays.
