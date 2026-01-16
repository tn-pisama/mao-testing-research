"""
F9: Role Usurpation Detector
============================

Analyzes whether agents act outside their designated roles:
1. Role boundary violation - agent performs tasks outside role scope
2. Role ambiguity - unclear or conflicting role assignments
3. Unauthorized actions - agent exceeds permission boundaries
4. Role drift - gradual deviation from assigned responsibilities

Based on MAST research (NeurIPS 2025): FM-2.5 Role Usurpation (3%)
"""

import logging
from typing import List, Optional, Dict, Any

from ._base import (
    TurnSnapshot,
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
)
from ._embedding_mixin import EmbeddingMixin

logger = logging.getLogger(__name__)


class TurnAwareRoleUsurpationDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects F9: Role Usurpation in conversations.

    Analyzes whether agents act outside their designated roles:
    1. Role boundary violation - agent performs tasks outside role scope
    2. Role ambiguity - unclear or conflicting role assignments
    3. Unauthorized actions - agent exceeds permission boundaries
    4. Role drift - gradual deviation from assigned responsibilities

    Phase 2 Enhancement (v2.0): Uses semantic similarity to:
    - Better infer agent roles from conversation context
    - Detect semantic role boundary violations (not just keyword matching)
    - Track role consistency across conversation turns
    - Identify implicit role conflicts through embedding analysis

    Based on MAST research (NeurIPS 2025): FM-2.5 Role Usurpation (3%)
    """

    name = "TurnAwareRoleUsurpationDetector"
    version = "2.0"  # Phase 2: Enhanced with semantic analysis
    supported_failure_modes = ["F9"]

    # Role definitions with semantic descriptions
    ROLE_DEFINITIONS = {
        "coordinator": {
            "description": "Orchestrates workflow, delegates tasks, manages communication between agents",
            "indicators": ["i will assign", "let me delegate", "i'll coordinate", "as coordinator",
                         "orchestrating", "managing the team", "distributing work"],
            "actions": ["assign", "delegate", "coordinate", "organize", "manage team", "distribute"],
        },
        "executor": {
            "description": "Implements solutions, executes code, performs concrete actions",
            "indicators": ["executing now", "i will implement", "implementing the", "as executor",
                         "running the code", "performing the task", "making changes"],
            "actions": ["execute", "implement", "run", "perform", "build", "create", "modify"],
        },
        "reviewer": {
            "description": "Evaluates work quality, provides feedback, validates outputs",
            "indicators": ["reviewing your", "let me review", "my review shows", "as reviewer",
                         "upon review", "checking the quality", "validating output"],
            "actions": ["review", "evaluate", "validate", "check quality", "assess", "critique"],
        },
        "researcher": {
            "description": "Gathers information, investigates problems, analyzes data",
            "indicators": ["researching this", "my research shows", "investigating the", "as researcher",
                         "analyzing the data", "gathering information", "exploring options"],
            "actions": ["research", "investigate", "analyze", "gather info", "explore", "study"],
        },
        "planner": {
            "description": "Designs strategies, creates plans, outlines approaches",
            "indicators": ["planning the approach", "let me plan", "my plan is", "as planner",
                         "designing the strategy", "outlining steps", "creating roadmap"],
            "actions": ["plan", "design", "strategize", "outline", "architect", "blueprint"],
        },
        "tester": {
            "description": "Tests functionality, verifies correctness, finds bugs",
            "indicators": ["testing this", "let me test", "my tests show", "as tester",
                         "verifying functionality", "checking for bugs", "running tests"],
            "actions": ["test", "verify", "debug", "check", "validate functionality", "qa"],
        },
    }

    def __init__(self, min_turns: int = 3, strict_mode: bool = False):
        self.min_turns = min_turns
        self.strict_mode = strict_mode  # If True, be more aggressive in detection

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect role usurpation issues."""
        if len(turns) < self.min_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns to analyze",
                detector_name=self.name,
            )

        # Track agent roles across conversation
        agent_roles = self._infer_agent_roles(turns)

        # Detect various types of role violations
        violations = []
        affected_turns = []

        # 1. Boundary violations (agent acting outside assigned role)
        boundary_violations = self._detect_boundary_violations(turns, agent_roles)
        violations.extend(boundary_violations)
        for v in boundary_violations:
            affected_turns.extend(v.get("turns", []))

        # 2. Role conflicts (multiple agents claiming same role)
        role_conflicts = self._detect_role_conflicts(turns, agent_roles)
        violations.extend(role_conflicts)
        for v in role_conflicts:
            affected_turns.extend(v.get("turns", []))

        # 3. Unauthorized actions (agent performing actions outside permission scope)
        unauthorized = self._detect_unauthorized_actions(turns, agent_roles)
        violations.extend(unauthorized)
        for v in unauthorized:
            affected_turns.extend(v.get("turns", []))

        if not violations:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation="No role usurpation detected",
                detector_name=self.name,
            )

        # Severity based on violation count and types
        critical_violations = [v for v in violations if v.get("severity") == "critical"]
        if len(critical_violations) >= 2 or len(violations) >= 5:
            severity = TurnAwareSeverity.SEVERE
        elif len(violations) >= 3:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.88, 0.45 + len(violations) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F9",
            explanation=f"Role usurpation: {len(violations)} violations found across {len(set(affected_turns))} turns",
            affected_turns=list(set(affected_turns)),
            evidence={
                "violations": violations[:5],  # Top 5 violations
                "agent_roles": agent_roles,
                "critical_violations": len(critical_violations),
            },
            suggested_fix=(
                "Enforce role boundaries: 1) Clearly define agent roles upfront, "
                "2) Add permission checks before actions, 3) Use role-based access control, "
                "4) Monitor for role drift and conflicts."
            ),
            detector_name=self.name,
        )

    def _infer_agent_roles(self, turns: List[TurnSnapshot]) -> Dict[str, Dict[str, Any]]:
        """Infer agent roles from conversation using semantic analysis.

        Phase 2 Enhancement: Uses embeddings to match agent behavior to role descriptions.
        """
        agent_roles = {}
        agent_turns = {}

        # Collect turns by agent
        for turn in turns:
            agent_id = turn.participant_id or "unknown"
            if agent_id not in agent_turns:
                agent_turns[agent_id] = []
            agent_turns[agent_id].append(turn)

        # Infer role for each agent
        for agent_id, agent_turn_list in agent_turns.items():
            # Combine first few turns for role inference
            combined_content = " ".join([t.content[:200] for t in agent_turn_list[:3]])

            # Method 1: Semantic similarity to role descriptions (if embeddings available)
            if self.embedder:
                best_role = self._semantic_role_matching(combined_content)
                if best_role:
                    agent_roles[agent_id] = best_role
                    continue

            # Method 2: Keyword-based fallback
            keyword_role = self._keyword_role_matching(agent_id, combined_content)
            if keyword_role:
                agent_roles[agent_id] = keyword_role
            else:
                # No clear role detected
                agent_roles[agent_id] = {
                    "role": "unclear",
                    "confidence": 0.2,
                    "method": "none",
                }

        return agent_roles

    def _semantic_role_matching(self, content: str) -> Optional[Dict[str, Any]]:
        """Use semantic similarity to match agent content to role descriptions.

        Phase 2: Core semantic enhancement for better role inference.
        """
        if not self.embedder:
            return None

        try:
            # Compare content to each role description
            role_similarities = {}
            for role_name, role_def in self.ROLE_DEFINITIONS.items():
                # Use role description for semantic matching
                similarity = self.semantic_similarity(content, role_def["description"])
                if similarity >= 0:  # Valid similarity score
                    role_similarities[role_name] = similarity

            if not role_similarities:
                return None

            # Get best matching role
            best_role = max(role_similarities, key=role_similarities.get)
            best_score = role_similarities[best_role]

            # Require reasonable confidence threshold
            if best_score >= 0.50:  # Semantic similarity threshold
                return {
                    "role": best_role,
                    "confidence": best_score,
                    "method": "semantic",
                    "description": self.ROLE_DEFINITIONS[best_role]["description"],
                }

        except Exception as e:
            logger.debug(f"Semantic role matching failed: {e}")

        return None

    def _keyword_role_matching(self, agent_id: str, content: str) -> Optional[Dict[str, Any]]:
        """Fallback keyword-based role matching."""
        agent_lower = agent_id.lower()
        content_lower = content.lower()

        # Check agent ID
        for role_name, role_def in self.ROLE_DEFINITIONS.items():
            if role_name in agent_lower:
                return {
                    "role": role_name,
                    "confidence": 0.75,
                    "method": "agent_id",
                    "description": role_def["description"],
                }

        # Check content indicators
        role_scores = {}
        for role_name, role_def in self.ROLE_DEFINITIONS.items():
            score = sum(1 for indicator in role_def["indicators"] if indicator in content_lower)
            if score > 0:
                role_scores[role_name] = score

        if role_scores:
            best_role = max(role_scores, key=role_scores.get)
            score = role_scores[best_role]
            return {
                "role": best_role,
                "confidence": min(0.70, 0.4 + score * 0.15),
                "method": "keyword",
                "description": self.ROLE_DEFINITIONS[best_role]["description"],
            }

        return None

    def _detect_boundary_violations(
        self,
        turns: List[TurnSnapshot],
        agent_roles: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect agents acting outside their role boundaries.

        Phase 2: Uses semantic similarity to detect boundary violations beyond keywords.
        """
        violations = []

        for turn in turns:
            agent_id = turn.participant_id or "unknown"

            # Skip if no clear role assigned
            if agent_id not in agent_roles or agent_roles[agent_id]["role"] == "unclear":
                continue

            assigned_role = agent_roles[agent_id]["role"]
            content = turn.content

            # Check if agent is performing actions from other roles
            for other_role, role_def in self.ROLE_DEFINITIONS.items():
                if other_role == assigned_role:
                    continue

                # Semantic boundary check (if embeddings available)
                if self.embedder:
                    # Check similarity to other role's description
                    other_similarity = self.semantic_similarity(content[:300], role_def["description"])

                    # Also check similarity to OWN role for comparison
                    own_role_def = self.ROLE_DEFINITIONS.get(assigned_role, {})
                    own_similarity = self.semantic_similarity(
                        content[:300], own_role_def.get("description", "")
                    ) if own_role_def else 0.0

                    # FPR FIX: Require ALL conditions to reduce false positives:
                    # 1. High similarity to other role (>= 0.80, raised from 0.65)
                    # 2. Significant margin over own role (0.20 margin)
                    # 3. Low similarity to own role (< 0.55)
                    if (other_similarity >= 0.80 and
                        other_similarity > own_similarity + 0.20 and
                        own_similarity < 0.55):
                        violations.append({
                            "type": "boundary_violation",
                            "turns": [turn.turn_number],
                            "agent": agent_id,
                            "assigned_role": assigned_role,
                            "violated_role": other_role,
                            "similarity": other_similarity,
                            "own_similarity": own_similarity,
                            "severity": "moderate",
                            "description": f"{agent_id} ({assigned_role}) acting as {other_role}",
                        })
                        break  # Only report first violation per turn

                # Keyword fallback
                else:
                    content_lower = content.lower()
                    matches = sum(1 for indicator in role_def["indicators"] if indicator in content_lower)
                    if matches >= 2:  # Multiple indicators = likely violation
                        violations.append({
                            "type": "boundary_violation",
                            "turns": [turn.turn_number],
                            "agent": agent_id,
                            "assigned_role": assigned_role,
                            "violated_role": other_role,
                            "matches": matches,
                            "severity": "moderate",
                            "description": f"{agent_id} ({assigned_role}) using {other_role} patterns",
                        })
                        break

        return violations[:5]  # Limit to top 5

    def _detect_role_conflicts(
        self,
        turns: List[TurnSnapshot],
        agent_roles: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect multiple agents claiming or performing the same role."""
        conflicts = []

        # Group agents by role
        role_to_agents = {}
        for agent_id, role_info in agent_roles.items():
            role = role_info["role"]
            if role == "unclear":
                continue
            if role not in role_to_agents:
                role_to_agents[role] = []
            role_to_agents[role].append(agent_id)

        # Check for conflicts (multiple agents with same role)
        for role, agents in role_to_agents.items():
            if len(agents) > 1:
                # Find turns where both agents act in that role
                conflict_turns = []
                for turn in turns:
                    agent_id = turn.participant_id or "unknown"
                    if agent_id in agents:
                        conflict_turns.append(turn.turn_number)

                if len(conflict_turns) >= 2:  # Actual conflict (both agents active)
                    conflicts.append({
                        "type": "role_conflict",
                        "turns": conflict_turns[:3],  # Sample turns
                        "role": role,
                        "agents": agents,
                        "severity": "critical",  # Role conflicts are serious
                        "description": f"Multiple agents ({', '.join(agents)}) assigned {role} role",
                    })

        return conflicts

    def _detect_unauthorized_actions(
        self,
        turns: List[TurnSnapshot],
        agent_roles: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect agents performing actions outside their permission scope."""
        unauthorized = []

        # High-privilege actions that require specific roles
        sensitive_actions = {
            "delete": ["executor", "coordinator"],  # Only these roles can delete
            "deploy": ["executor", "coordinator"],
            "approve": ["reviewer", "coordinator"],
            "reject": ["reviewer", "coordinator"],
            "assign": ["coordinator"],  # Only coordinator can assign
            "delegate": ["coordinator"],
        }

        for turn in turns:
            agent_id = turn.participant_id or "unknown"

            # Skip if no role assigned
            if agent_id not in agent_roles or agent_roles[agent_id]["role"] == "unclear":
                continue

            assigned_role = agent_roles[agent_id]["role"]
            content_lower = turn.content.lower()

            # Check for sensitive actions
            for action, allowed_roles in sensitive_actions.items():
                if action in content_lower and assigned_role not in allowed_roles:
                    unauthorized.append({
                        "type": "unauthorized_action",
                        "turns": [turn.turn_number],
                        "agent": agent_id,
                        "assigned_role": assigned_role,
                        "action": action,
                        "allowed_roles": allowed_roles,
                        "severity": "critical",
                        "description": f"{agent_id} ({assigned_role}) attempted '{action}' (requires {allowed_roles})",
                    })

        return unauthorized[:3]  # Limit to top 3
