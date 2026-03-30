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

**What it detects:** Validation steps are skipped or bypassed, or approval is given despite failed checks.

**Real-world examples:**

- Agent approves code review without actually running the test suite
- Validation step exists in workflow but its results are ignored
- Agent marks output as "validated" when the validation actually failed
- No validation step at all in a workflow that processes sensitive data

**Detection methods:**

- **Bypass Pattern Detection**: Identifies patterns indicating validation was skipped ("BYPASS validation", "will validate later")
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

**What it detects:** Agents skip mandatory quality checks, ignore quality thresholds, or proceed despite failing checks.

**Real-world examples:**

- Agent skips required code linting step and proceeds to deployment
- Quality score of 45% is below the 80% threshold, but agent proceeds anyway
- Mandatory peer review process omitted from the workflow
- Agent uses `--no-verify` or `--force` flags to bypass checks

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

**What it detects:** Agent incorrectly determines task completion, including premature claims, partial delivery, and ignored subtasks. One of the most prevalent failure modes -- 40% in MAST-Data for FM-1.5.

**Real-world examples:**

- Agent claims "all 10 endpoints documented" but only 8 are present
- Task marked complete with "planned for future work" items still pending
- JSON output has `"status": "complete"` but `"documented": false` for key items
- Agent delivers 80% of requirements and declares the task done

**Detection methods:**

- **Completion Marker Detection**: Identifies explicit and implicit completion claims ("task complete", "finished", "comprehensive", "fully covered")
- **Quantitative Requirement Check**: Verifies numerical completeness ("all", "every", N items)
- **Hedging Language Detection**: Flags qualifiers like "appears complete" or "seems done"
- **JSON Indicator Analysis**: Checks structured output for incomplete flags (`"status": "complete"` with `"documented": false`)
- **Numeric Ratio Detection**: Catches partial delivery (e.g., "8/10 endpoints", `documentedEndpoints: 8, total: 10`)
- **Structural Incompleteness**: List item count validation, missing sections
- **Planned/Future Work Detection**: Identifies indicators that the task is not actually complete

**Sub-types:** `premature_completion`, `partial_delivery`, `ignored_subtasks`, `missed_criteria`, `false_completion_claim`, `incomplete_verification`
