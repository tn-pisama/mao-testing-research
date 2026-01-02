"""
F9: Role Usurpation Detection (MAST Taxonomy)
==============================================

Detects when an agent exceeds its designated role boundaries:
- Taking actions outside assigned responsibilities
- Making decisions reserved for other roles
- Scope expansion beyond assignment
- Authority violations
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Set

logger = logging.getLogger(__name__)


class UsurpationSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class UsurpationIssueType(str, Enum):
    ROLE_VIOLATION = "role_violation"
    SCOPE_EXPANSION = "scope_expansion"
    AUTHORITY_VIOLATION = "authority_violation"
    DECISION_OVERREACH = "decision_overreach"
    TASK_HIJACKING = "task_hijacking"


@dataclass
class RoleDefinition:
    """Defines an agent's role and boundaries."""
    role_name: str
    allowed_actions: Set[str] = field(default_factory=set)
    forbidden_actions: Set[str] = field(default_factory=set)
    scope: str = "own_tasks"  # "own_tasks", "team", "system"


@dataclass
class AgentAction:
    """Represents an action taken by an agent."""
    agent_id: str
    agent_role: str
    action_type: str
    action_description: str
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsurpationIssue:
    issue_type: UsurpationIssueType
    agent_id: str
    assigned_role: str
    violated_role: str
    action: str
    description: str
    severity: UsurpationSeverity


@dataclass
class RoleUsurpationResult:
    detected: bool
    severity: UsurpationSeverity
    confidence: float
    issues: List[UsurpationIssue] = field(default_factory=list)
    violations_count: int = 0
    agents_violating: List[str] = field(default_factory=list)
    explanation: str = ""
    suggested_fix: Optional[str] = None


class RoleUsurpationDetector:
    """
    Detects F9: Role Usurpation - agents exceeding role boundaries.

    Analyzes agent actions against role definitions to identify
    when agents take actions outside their designated responsibilities.
    """

    # Default role-action mappings
    DEFAULT_ROLE_ACTIONS = {
        "planning": {"plan", "design", "architect", "strategy", "prioritize", "schedule", "assign", "allocate"},
        "execution": {"implement", "execute", "build", "code", "develop", "create", "process"},
        "review": {"review", "approve", "reject", "validate", "check", "audit", "inspect"},
        "analysis": {"analyze", "research", "investigate", "study", "evaluate", "assess"},
        "frontend": {"ui", "interface", "component", "style", "render", "display"},
        "backend": {"api", "server", "database", "endpoint", "service", "integration"},
        "testing": {"test", "verify", "qa", "debug", "benchmark", "measure"},
        "monitoring": {"monitor", "observe", "track", "alert", "log", "metric"},
    }

    # Actions that require specific authority levels
    AUTHORITY_ACTIONS = {
        "approve": "review",
        "reject": "review",
        "assign": "planning",
        "prioritize": "planning",
        "deploy": "review",
        "release": "review",
        "merge": "review",
        "delete": "review",
        "terminate": "planning",
    }

    # Patterns indicating role boundary violations
    VIOLATION_PATTERNS = [
        (r"(?:I'll |I will |let me )(?:decide|determine|choose) (?:to |the |which )", "decision_overreach"),
        (r"(?:reorganiz|reprioritiz|reassign)(?:ing|e)", "planning_usurpation"),
        (r"(?:approv|reject|merg)(?:ing|ed|e) (?:the |this )?(?:code|pr|request)", "review_usurpation"),
        (r"(?:skip|bypass|ignore)(?:ping|ed)? (?:the |this )?(?:review|approval|check)", "authority_bypass"),
        (r"(?:also |additionally |furthermore )(?:implement|add|creat)(?:ing|ed)? (?:additional|extra|more)", "scope_expansion"),
        (r"not in (?:the |my )?(?:scope|assignment|task)", "scope_acknowledgment"),
        (r"(?:tak|assum)(?:ing|e) (?:over|control|charge)", "task_hijacking"),
    ]

    def __init__(
        self,
        role_definitions: Optional[Dict[str, RoleDefinition]] = None,
        strict_mode: bool = False,
    ):
        self.role_definitions = role_definitions or {}
        self.strict_mode = strict_mode

    def _get_role_actions(self, role: str) -> Set[str]:
        """Get allowed actions for a role."""
        if role in self.role_definitions:
            return self.role_definitions[role].allowed_actions

        # Use default mappings
        role_lower = role.lower()
        for role_key, actions in self.DEFAULT_ROLE_ACTIONS.items():
            if role_key in role_lower:
                return actions

        # Generic fallback
        return set()

    def _extract_action_types(self, text: str) -> Set[str]:
        """Extract action types from text."""
        actions = set()
        text_lower = text.lower()

        # Check for action keywords
        action_keywords = {
            "plan": "planning", "design": "planning", "assign": "planning",
            "prioritize": "planning", "schedule": "planning", "reorganize": "planning",
            "implement": "execution", "build": "execution", "code": "execution",
            "develop": "execution", "create": "execution",
            "review": "review", "approve": "review", "reject": "review",
            "merge": "review", "validate": "review",
            "analyze": "analysis", "research": "analysis", "investigate": "analysis",
            "test": "testing", "verify": "testing", "debug": "testing",
            "monitor": "monitoring", "track": "monitoring", "observe": "monitoring",
        }

        for keyword, action_type in action_keywords.items():
            if keyword in text_lower:
                actions.add(action_type)

        return actions

    def _detect_pattern_violations(
        self,
        text: str,
        agent_role: str,
    ) -> List[tuple]:
        """Detect violations using regex patterns."""
        violations = []

        for pattern, violation_type in self.VIOLATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append((pattern, violation_type))

        return violations

    def _check_action_against_role(
        self,
        action: AgentAction,
    ) -> List[UsurpationIssue]:
        """Check if an action violates role boundaries."""
        issues = []
        role_lower = action.agent_role.lower()

        # Get allowed actions for this role
        allowed_actions = self._get_role_actions(action.agent_role)

        # Extract actions from description
        detected_actions = self._extract_action_types(action.action_description)

        for detected_action in detected_actions:
            # Check if this action type is allowed for this role
            if allowed_actions and detected_action not in allowed_actions:
                # Check if it belongs to another role
                violated_role = None
                for role_key, role_actions in self.DEFAULT_ROLE_ACTIONS.items():
                    if detected_action in role_actions and role_key not in role_lower:
                        violated_role = role_key
                        break

                if violated_role:
                    severity = UsurpationSeverity.MODERATE
                    if detected_action in self.AUTHORITY_ACTIONS:
                        severity = UsurpationSeverity.SEVERE

                    issues.append(UsurpationIssue(
                        issue_type=UsurpationIssueType.ROLE_VIOLATION,
                        agent_id=action.agent_id,
                        assigned_role=action.agent_role,
                        violated_role=violated_role,
                        action=detected_action,
                        description=f"Agent with role '{action.agent_role}' performed '{detected_action}' action belonging to '{violated_role}' role",
                        severity=severity,
                    ))

        # Check for pattern-based violations
        pattern_violations = self._detect_pattern_violations(
            action.action_description,
            action.agent_role,
        )

        for pattern, violation_type in pattern_violations:
            issue_type = UsurpationIssueType.SCOPE_EXPANSION
            if "hijack" in violation_type:
                issue_type = UsurpationIssueType.TASK_HIJACKING
            elif "usurp" in violation_type:
                issue_type = UsurpationIssueType.ROLE_VIOLATION
            elif "authority" in violation_type or "bypass" in violation_type:
                issue_type = UsurpationIssueType.AUTHORITY_VIOLATION
            elif "decision" in violation_type:
                issue_type = UsurpationIssueType.DECISION_OVERREACH

            issues.append(UsurpationIssue(
                issue_type=issue_type,
                agent_id=action.agent_id,
                assigned_role=action.agent_role,
                violated_role="system",
                action=violation_type,
                description=f"Agent '{action.agent_id}' exhibited {violation_type} behavior",
                severity=UsurpationSeverity.MODERATE,
            ))

        return issues

    def detect(
        self,
        actions: List[AgentAction],
        role_definitions: Optional[Dict[str, RoleDefinition]] = None,
    ) -> RoleUsurpationResult:
        """
        Detect role usurpation issues.

        Args:
            actions: List of agent actions to analyze
            role_definitions: Optional role definitions override

        Returns:
            RoleUsurpationResult with detection outcome
        """
        if not actions:
            return RoleUsurpationResult(
                detected=False,
                severity=UsurpationSeverity.NONE,
                confidence=0.0,
                explanation="No agent actions to analyze",
            )

        if role_definitions:
            self.role_definitions = role_definitions

        all_issues = []
        for action in actions:
            issues = self._check_action_against_role(action)
            all_issues.extend(issues)

        if not all_issues:
            return RoleUsurpationResult(
                detected=False,
                severity=UsurpationSeverity.NONE,
                confidence=0.9,
                explanation="No role usurpation detected",
            )

        # Aggregate metrics
        agents_violating = list(set(i.agent_id for i in all_issues))
        violations_count = len(all_issues)

        # Determine overall severity
        if any(i.severity == UsurpationSeverity.CRITICAL for i in all_issues):
            severity = UsurpationSeverity.CRITICAL
        elif any(i.severity == UsurpationSeverity.SEVERE for i in all_issues):
            severity = UsurpationSeverity.SEVERE
        elif any(i.severity == UsurpationSeverity.MODERATE for i in all_issues):
            severity = UsurpationSeverity.MODERATE
        else:
            severity = UsurpationSeverity.MINOR

        # Calculate confidence
        confidence = min(0.95, 0.5 + (violations_count * 0.1))

        # Build explanation
        issue_types = set(i.issue_type.value for i in all_issues)
        explanation = f"Detected {violations_count} role violation(s) by {len(agents_violating)} agent(s): {', '.join(issue_types)}"

        # Suggest fix
        fixes = []
        if any(i.issue_type == UsurpationIssueType.SCOPE_EXPANSION for i in all_issues):
            fixes.append("enforce explicit scope boundaries in agent prompts")
        if any(i.issue_type == UsurpationIssueType.AUTHORITY_VIOLATION for i in all_issues):
            fixes.append("implement authority checks before sensitive actions")
        if any(i.issue_type == UsurpationIssueType.ROLE_VIOLATION for i in all_issues):
            fixes.append("clarify role responsibilities and add role-based action filtering")

        return RoleUsurpationResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            issues=all_issues,
            violations_count=violations_count,
            agents_violating=agents_violating,
            explanation=explanation,
            suggested_fix="; ".join(fixes) if fixes else None,
        )

    def detect_from_trace(
        self,
        trace: dict,
    ) -> RoleUsurpationResult:
        """
        Detect role usurpation from trace data.
        """
        spans = trace.get("spans", [])
        if not spans:
            return RoleUsurpationResult(
                detected=False,
                severity=UsurpationSeverity.NONE,
                confidence=0.0,
                explanation="No spans in trace",
            )

        actions = []
        for span in spans:
            agent_id = span.get("agent_id", span.get("name", "unknown"))
            metadata = span.get("metadata", {})
            role = metadata.get("role", span.get("name", "unknown"))

            # Get output text
            output = span.get("output_data", {}).get("result", "")
            if not isinstance(output, str):
                output = span.get("response", "")

            if output:
                # Check for role violation indicators in metadata
                in_role = metadata.get("in_role", True)
                role_violation = metadata.get("role_violation")
                exceeded_scope = metadata.get("exceeded_scope", False)

                # Create action from span
                action = AgentAction(
                    agent_id=agent_id,
                    agent_role=role,
                    action_type=span.get("span_type", "agent"),
                    action_description=output,
                    timestamp=span.get("start_time", 0),
                    metadata={
                        "in_role": in_role,
                        "role_violation": role_violation,
                        "exceeded_scope": exceeded_scope,
                    },
                )
                actions.append(action)

                # If metadata explicitly indicates violation, create additional action
                if not in_role or role_violation or exceeded_scope:
                    violation_action = AgentAction(
                        agent_id=agent_id,
                        agent_role=role,
                        action_type="violation",
                        action_description=f"Agent exceeded role: {role_violation or 'scope expansion'}" if role_violation else "Agent exceeded assigned scope",
                        metadata=metadata,
                    )
                    actions.append(violation_action)

        return self.detect(actions)


# Singleton instance
role_usurpation_detector = RoleUsurpationDetector()
