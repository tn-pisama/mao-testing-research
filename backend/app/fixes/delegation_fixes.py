"""Fix generators for delegation quality detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class DelegationFixGenerator(BaseFixGenerator):
    """Generates fixes for delegation quality issues — bad task splitting or unclear instructions."""

    def can_handle(self, detection_type: str) -> bool:
        return detection_type == "delegation"

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._task_specification_fix(detection_id, details, context))
        fixes.append(self._capability_matching_fix(detection_id, details, context))
        fixes.append(self._delegation_validation_fix(detection_id, details, context))

        return fixes

    def _task_specification_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="delegation",
            fix_type=FixType.TASK_DECOMPOSER,
            confidence=FixConfidence.HIGH,
            title="Enforce structured task specifications for delegated work",
            description=(
                "Require the delegator agent to provide structured task specifications "
                "with explicit acceptance criteria, required inputs, expected outputs, "
                "and constraints. Reject vague delegations."
            ),
            rationale=(
                "Delegation failures often stem from ambiguous instructions. "
                "The delegatee agent doesn't know what 'done' looks like. Structured "
                "specs with acceptance criteria prevent scope drift and ensure the "
                "delegatee can self-verify completion."
            ),
            code_changes=[CodeChange(original_code=None,
                file_path="delegation_policy.py",
                language="python",
                suggested_code="""+ # Delegation fix: require structured task specs
+ DELEGATION_TEMPLATE = \"\"\"
+ ## Delegated Task
+ **Objective:** {objective}
+ **Required Inputs:** {inputs}
+ **Expected Output:** {output_format}
+ **Acceptance Criteria:**
+ {criteria}
+ **Constraints:** {constraints}
+ **Deadline:** {deadline}
+ \"\"\"
+
+ def validate_delegation(instruction: str) -> bool:
+     required = ['objective', 'expected output', 'acceptance criteria']
+     instruction_lower = instruction.lower()
+     return all(r in instruction_lower for r in required)
""",
            )],
            estimated_impact="Prevents vague delegations; adds overhead to delegation step",
            breaking_changes=False,
            requires_testing=True,
            tags=["delegation", "task_spec", "clarity"],
        )

    def _capability_matching_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="delegation",
            fix_type=FixType.SUBTASK_VALIDATOR,
            confidence=FixConfidence.MEDIUM,
            title="Add capability-aware agent routing for delegation",
            description=(
                "Before delegating a task, check that the target agent has the "
                "required capabilities (tools, knowledge, permissions). Route tasks "
                "to the most capable agent instead of round-robin or random selection."
            ),
            rationale=(
                "Delegation fails when tasks are sent to agents that lack the "
                "required tools or domain knowledge. Capability matching ensures "
                "the delegatee CAN perform the task before accepting it."
            ),
            code_changes=[CodeChange(original_code=None,
                file_path="agent_router.py",
                language="python",
                suggested_code="""+ # Delegation fix: capability-aware routing
+ AGENT_CAPABILITIES = {
+     'researcher': ['web_search', 'document_analysis'],
+     'coder': ['code_execution', 'file_editing', 'testing'],
+     'writer': ['text_generation', 'formatting'],
+ }
+
+ def route_delegation(task, available_agents):
+     required = extract_required_capabilities(task)
+     for agent_id, caps in AGENT_CAPABILITIES.items():
+         if agent_id in available_agents and required.issubset(set(caps)):
+             return agent_id
+     raise DelegationError(f'No agent has capabilities: {required}')
""",
            )],
            estimated_impact="Prevents misrouted delegations; requires capability registry",
            breaking_changes=False,
            requires_testing=True,
            tags=["delegation", "routing", "capability_matching"],
        )

    def _delegation_validation_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="delegation",
            fix_type=FixType.QUALITY_CHECKPOINT,
            confidence=FixConfidence.MEDIUM,
            title="Add delegation output validation checkpoint",
            description=(
                "After the delegatee completes the task, validate the output against "
                "the original acceptance criteria before returning it to the delegator. "
                "Re-delegate with clarified instructions if validation fails."
            ),
            rationale=(
                "Without output validation, the delegator blindly trusts the result. "
                "Adding a checkpoint catches incomplete or incorrect work before it "
                "propagates through the agent pipeline."
            ),
            code_changes=[CodeChange(original_code=None,
                file_path="delegation_validator.py",
                language="python",
                suggested_code="""+ # Delegation fix: validate delegatee output
+ def validate_delegation_output(instruction, output, criteria):
+     checks = []
+     for criterion in criteria:
+         met = criterion.lower() in output.lower()
+         checks.append({'criterion': criterion, 'met': met})
+     passed = all(c['met'] for c in checks)
+     return {'passed': passed, 'checks': checks}
+
+ def delegation_with_retry(delegator, delegatee, task, max_retries=2):
+     for attempt in range(max_retries + 1):
+         result = delegatee.execute(task)
+         validation = validate_delegation_output(
+             task['instruction'], result, task['acceptance_criteria'])
+         if validation['passed']:
+             return result
+         task['instruction'] += f'\\n[Retry {attempt+1}]: Previous output failed: {validation["checks"]}'
+     return result  # Return last attempt even if failed
""",
            )],
            estimated_impact="Catches delegation failures before propagation; may add retry latency",
            breaking_changes=False,
            requires_testing=True,
            tags=["delegation", "validation", "retry"],
        )
