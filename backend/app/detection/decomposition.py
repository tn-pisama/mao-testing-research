"""
F2: Poor Task Decomposition Detection (MAST Taxonomy)
=====================================================

Detects when task decomposition creates:
- Subtasks that are impossible or ill-defined
- Missing dependencies between subtasks
- Circular dependencies
- Subtasks that duplicate work
- Subtasks that are too large or too granular
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re

logger = logging.getLogger(__name__)


class DecompositionIssue(str, Enum):
    IMPOSSIBLE_SUBTASK = "impossible_subtask"
    MISSING_DEPENDENCY = "missing_dependency"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    DUPLICATE_WORK = "duplicate_work"
    WRONG_GRANULARITY = "wrong_granularity"
    MISSING_SUBTASK = "missing_subtask"


class DecompositionSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


@dataclass
class Subtask:
    id: str
    description: str
    dependencies: list[str]
    assigned_agent: Optional[str] = None
    estimated_complexity: Optional[str] = None


@dataclass
class DecompositionResult:
    detected: bool
    issues: list[DecompositionIssue]
    severity: DecompositionSeverity
    confidence: float
    subtask_count: int
    problematic_subtasks: list[str]
    explanation: str
    suggested_fix: Optional[str] = None


class TaskDecompositionDetector:
    """
    Detects F2: Poor Task Decomposition - subtasks ill-defined or impossible.
    
    Analyzes task breakdown for logical issues, dependency problems,
    and coverage gaps.
    """
    
    def __init__(
        self,
        min_subtasks: int = 2,
        max_subtasks: int = 20,
        check_dependencies: bool = True,
    ):
        self.min_subtasks = min_subtasks
        self.max_subtasks = max_subtasks
        self.check_dependencies = check_dependencies

    def _parse_subtasks(self, decomposition: str) -> list[Subtask]:
        subtasks = []
        
        patterns = [
            r'(?:^|\n)\s*\d+[.)]\s*([^\n]+)',
            r'(?:^|\n)\s*[-•*]\s*([^\n]+)',
            r'(?:^|\n)\s*(?:step|task|subtask)\s*\d*[:.]\s*([^\n]+)',
        ]
        
        items = []
        for pattern in patterns:
            matches = re.findall(pattern, decomposition, re.IGNORECASE)
            if matches:
                items = matches
                break
        
        for i, item in enumerate(items):
            deps = []
            dep_patterns = [
                r'(?:after|following|requires?|depends?\s+on)\s+(?:step|task)?\s*(\d+)',
                r'(?:once|when)\s+(?:step|task)?\s*(\d+)\s+(?:is\s+)?(?:complete|done)',
            ]
            for pattern in dep_patterns:
                dep_matches = re.findall(pattern, item.lower())
                deps.extend([f"task_{int(d) - 1}" for d in dep_matches if int(d) <= i])
            
            subtasks.append(Subtask(
                id=f"task_{i}",
                description=item.strip(),
                dependencies=deps,
            ))
        
        return subtasks

    def _detect_impossible_subtasks(self, subtasks: list[Subtask]) -> list[str]:
        impossible_indicators = [
            "impossible", "cannot", "unable", "no way", "infeasible",
            "undefined", "unknown", "unclear", "ambiguous",
            "without access", "no information", "missing",
        ]
        
        problematic = []
        for subtask in subtasks:
            desc_lower = subtask.description.lower()
            for indicator in impossible_indicators:
                if indicator in desc_lower:
                    problematic.append(subtask.id)
                    break
        
        return problematic

    def _detect_circular_dependencies(self, subtasks: list[Subtask]) -> list[tuple[str, str]]:
        circular = []
        
        dep_map = {st.id: set(st.dependencies) for st in subtasks}
        
        for task_id, deps in dep_map.items():
            for dep in deps:
                if dep in dep_map and task_id in dep_map[dep]:
                    if (dep, task_id) not in circular:
                        circular.append((task_id, dep))
        
        return circular

    def _detect_duplicate_work(self, subtasks: list[Subtask]) -> list[tuple[str, str]]:
        duplicates = []
        
        for i, st1 in enumerate(subtasks):
            words1 = set(st1.description.lower().split())
            for j, st2 in enumerate(subtasks[i+1:], i+1):
                words2 = set(st2.description.lower().split())
                if not words1 or not words2:
                    continue
                overlap = len(words1 & words2) / min(len(words1), len(words2))
                if overlap > 0.7:
                    duplicates.append((st1.id, st2.id))
        
        return duplicates

    def _detect_missing_dependencies(self, subtasks: list[Subtask]) -> list[str]:
        missing = []
        
        output_indicators = ["create", "generate", "produce", "build", "write"]
        input_indicators = ["use", "read", "process", "analyze", "with"]
        
        outputs = {}
        for st in subtasks:
            desc_lower = st.description.lower()
            for indicator in output_indicators:
                if indicator in desc_lower:
                    words = desc_lower.split()
                    idx = words.index(indicator) if indicator in words else -1
                    if idx >= 0 and idx + 1 < len(words):
                        outputs[words[idx + 1]] = st.id
        
        for st in subtasks:
            desc_lower = st.description.lower()
            for indicator in input_indicators:
                if indicator in desc_lower:
                    words = desc_lower.split()
                    idx = words.index(indicator) if indicator in words else -1
                    if idx >= 0 and idx + 1 < len(words):
                        needed = words[idx + 1]
                        if needed in outputs and outputs[needed] not in st.dependencies:
                            if outputs[needed] != st.id:
                                missing.append(st.id)
        
        return missing

    def detect(
        self,
        task_description: str,
        decomposition: str,
        agent_capabilities: Optional[dict[str, list[str]]] = None,
    ) -> DecompositionResult:
        subtasks = self._parse_subtasks(decomposition)
        
        if not subtasks:
            return DecompositionResult(
                detected=False,
                issues=[],
                severity=DecompositionSeverity.NONE,
                confidence=0.5,
                subtask_count=0,
                problematic_subtasks=[],
                explanation="No subtasks found in decomposition",
            )

        issues = []
        problematic = []
        
        if len(subtasks) < self.min_subtasks:
            issues.append(DecompositionIssue.WRONG_GRANULARITY)
            problematic.append("too_few_subtasks")
        elif len(subtasks) > self.max_subtasks:
            issues.append(DecompositionIssue.WRONG_GRANULARITY)
            problematic.append("too_many_subtasks")
        
        impossible = self._detect_impossible_subtasks(subtasks)
        if impossible:
            issues.append(DecompositionIssue.IMPOSSIBLE_SUBTASK)
            problematic.extend(impossible)
        
        circular = self._detect_circular_dependencies(subtasks)
        if circular:
            issues.append(DecompositionIssue.CIRCULAR_DEPENDENCY)
            for c1, c2 in circular:
                problematic.extend([c1, c2])
        
        duplicates = self._detect_duplicate_work(subtasks)
        if duplicates:
            issues.append(DecompositionIssue.DUPLICATE_WORK)
            for d1, d2 in duplicates:
                problematic.extend([d1, d2])
        
        if self.check_dependencies:
            missing_deps = self._detect_missing_dependencies(subtasks)
            if missing_deps:
                issues.append(DecompositionIssue.MISSING_DEPENDENCY)
                problematic.extend(missing_deps)

        if not issues:
            return DecompositionResult(
                detected=False,
                issues=[],
                severity=DecompositionSeverity.NONE,
                confidence=0.9,
                subtask_count=len(subtasks),
                problematic_subtasks=[],
                explanation="Task decomposition appears valid",
            )

        if DecompositionIssue.CIRCULAR_DEPENDENCY in issues or DecompositionIssue.IMPOSSIBLE_SUBTASK in issues:
            severity = DecompositionSeverity.SEVERE
        elif len(issues) >= 2:
            severity = DecompositionSeverity.MODERATE
        else:
            severity = DecompositionSeverity.MINOR

        confidence = min(len(issues) * 0.3, 0.95)

        issue_names = [i.value for i in issues]
        unique_problematic = list(set(problematic))[:5]
        explanation = (
            f"Task decomposition has {len(issues)} issues: {', '.join(issue_names)}. "
            f"Affected subtasks: {', '.join(unique_problematic)}"
        )

        fixes = []
        if DecompositionIssue.CIRCULAR_DEPENDENCY in issues:
            fixes.append("Break circular dependencies by reordering subtasks")
        if DecompositionIssue.IMPOSSIBLE_SUBTASK in issues:
            fixes.append("Redefine impossible subtasks with achievable scope")
        if DecompositionIssue.DUPLICATE_WORK in issues:
            fixes.append("Merge duplicate subtasks")
        if DecompositionIssue.MISSING_DEPENDENCY in issues:
            fixes.append("Add missing dependencies between subtasks")

        return DecompositionResult(
            detected=True,
            issues=issues,
            severity=severity,
            confidence=confidence,
            subtask_count=len(subtasks),
            problematic_subtasks=list(set(problematic)),
            explanation=explanation,
            suggested_fix="; ".join(fixes) if fixes else None,
        )

    def detect_from_trace(
        self,
        trace: dict,
    ) -> list[DecompositionResult]:
        results = []
        
        spans = trace.get("spans", [])
        for span in spans:
            if span.get("type") == "planning" or "plan" in span.get("name", "").lower():
                task = span.get("input", {}).get("task", "")
                output = span.get("output", {}).get("content", "")
                
                if task and output:
                    result = self.detect(
                        task_description=task,
                        decomposition=output,
                    )
                    if result.detected:
                        results.append(result)
        
        return results
