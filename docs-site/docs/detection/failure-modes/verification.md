# Verification Failures (FC3)

Verification failures occur when agents improperly validate their outputs, bypass quality checks, or incorrectly determine task completion.

---

## F12: Output Validation Failure (Enterprise)

| Field | Value |
|---|---|
| **Detector key** | `output_validation` |
| **Tier** | Enterprise |
| **Severity** | High |
| **Accuracy** | Benchmarking in progress |
| **MAST mapping** | FM-3.2, FM-3.3 |

**Plain language:** The agent skipped its quality checks or approved work that actually failed them. Like a building inspector signing off without ever visiting the site.

**Technical:** Detects validation bypass patterns in agent outputs and workflow logs, including skipped validation steps, false approvals despite failed checks, and missing validation stages in workflows that process sensitive data.

**Examples (non-technical):**

- Agent says "all tests passed" but never actually ran the tests
- A required review step exists in the process but its results were ignored
- Agent marks work as "validated" when the validation actually failed

**Examples (technical):**

- Agent output contains `"tests_passed": true` but CI logs show zero test executions
- Workflow step `validate_schema` ran but returned `{"valid": false}` -- agent proceeded anyway
- Agent bypasses validation with pattern: `# TODO: validate later` or `BYPASS validation`
- Pipeline processes PII data but has no `validate_pii_handling` step in the DAG

**Detection methods:**

- **Bypass Pattern Detection**: Identifies patterns indicating validation was skipped
- **Validation Performance Check**: Detects when validation steps actually ran
- **False Approval Detection**: Catches approval despite failed checks
- **Validation Presence Audit**: Ensures validation steps exist where required

**Sub-types:** `validation_bypassed`, `validation_skipped`, `approval_despite_failure`, `missing_validation`, `validation_ignored`, `incomplete_validation`

---

## F13: Quality Gate Bypass (Enterprise)

| Field | Value |
|---|---|
| **Detector key** | `quality_gate` |
| **Tier** | Enterprise |
| **Severity** | High |
| **Accuracy** | Benchmarking in progress |
| **MAST mapping** | FM-3.2 No/Incomplete Verification |

**Plain language:** The agent skipped mandatory quality checks or pushed work through despite failing them. Like submitting a paper without spell-checking when spell-check is required.

**Technical:** Audits workflow execution for missing quality gate steps, threshold violations (e.g., score 45% below 80% minimum), bypassed review processes, and use of force flags (`--no-verify`, `--force`, `--skip-*`).

**Examples (non-technical):**

- Agent skips the required review step and goes straight to deployment
- Quality score is 45% but the minimum is 80% -- agent proceeds anyway
- A mandatory peer review process is completely omitted from the workflow

**Examples (technical):**

- Agent runs `git push --no-verify`, bypassing pre-push hooks that enforce linting
- Code coverage gate requires 80% but agent deploys with 52% coverage
- Agent calls `deploy(force=True)` to skip the staging environment validation
- Workflow definition includes `review_step` but execution trace shows it was never invoked

**Detection methods:**

- **Validation Step Audit**: Checks for presence of required validation steps
- **Threshold Monitoring**: Verifies quality scores meet minimum thresholds
- **Review Process Check**: Ensures mandatory review processes are followed
- **Bypass Flag Detection**: Catches `--no-verify`, `--skip-*`, `-f`/`--force` patterns

**Sub-types:** `skipped_validation`, `ignored_threshold`, `bypassed_review`, `missing_checks`, `forced_completion`

---

## F14: Completion Misjudgment

| Field | Value |
|---|---|
| **Detector key** | `completion` |
| **Tier** | ICP |
| **Severity** | High |
| **Accuracy** | F1 0.703, P 0.619, R 0.812 |
| **MAST mapping** | FM-1.5 Unaware of Termination, FM-3.1 Premature Termination |

**Plain language:** The agent said "I'm done" when it wasn't. It claimed to have completed everything, but important pieces are still missing -- like a contractor saying a house is finished when the plumbing isn't connected.

**Technical:** Detects premature completion claims through completion marker analysis, quantitative requirement verification (numeric counts), hedging language detection, structured output inspection for incomplete flags, and planned/future work indicators.

**Examples (non-technical):**

- Agent says "all 10 items are documented" but only 8 actually are
- Task is marked complete but has items listed as "planned for future work"
- Agent delivers 80% of what was asked for and declares the job done

**Examples (technical):**

- Output claims "all endpoints documented" but `documented_count: 8` vs `total_endpoints: 10`
- JSON output has `{"status": "complete", "documented": false}` -- contradictory fields
- Agent output contains hedging: "appears to be complete" or "should cover most cases"
- Completion message includes `# TODO: implement remaining validators` -- clearly unfinished
- Numeric ratio detection catches "8/10 endpoints implemented"

**Detection methods:**

- **Completion Marker Detection**: Identifies explicit and implicit completion claims
- **Quantitative Requirement Check**: Verifies numerical completeness ("all", "every", N items)
- **Hedging Language Detection**: Flags qualifiers like "appears complete" or "seems done"
- **JSON Indicator Analysis**: Checks structured output for incomplete flags
- **Numeric Ratio Detection**: Catches partial delivery (e.g., "8/10 endpoints")
- **Planned/Future Work Detection**: Identifies indicators that the task is not actually complete

**Sub-types:** `premature_completion`, `partial_delivery`, `ignored_subtasks`, `missed_criteria`, `false_completion_claim`, `incomplete_verification`
