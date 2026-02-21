"""Quality fix generators that produce concrete workflow changes."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List

from ..models import DimensionScore, QualityReport
from .models import QualityFixSuggestion, QualityFixCategory


class BaseQualityFixGenerator(ABC):
    """Base class for per-dimension quality fix generators."""

    @abstractmethod
    def can_handle(self, dimension: str) -> bool:
        """Check if this generator handles the given dimension."""
        pass

    @abstractmethod
    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        """Generate fix suggestions for a low-scoring dimension."""
        pass


class QualityFixGenerator:
    """Orchestrates quality fix generation across all dimensions."""

    def __init__(self):
        self._generators: List[BaseQualityFixGenerator] = []

    def register(self, generator: BaseQualityFixGenerator) -> None:
        self._generators.append(generator)

    def generate_fixes(
        self,
        quality_report: QualityReport,
        threshold: float = 0.7,
    ) -> List[QualityFixSuggestion]:
        """Generate fixes for all dimensions scoring below threshold."""
        all_fixes: List[QualityFixSuggestion] = []

        # Agent dimension fixes
        for agent_score in quality_report.agent_scores:
            context = {
                "target_type": "agent",
                "agent_id": agent_score.agent_id,
                "agent_name": agent_score.agent_name,
                "agent_type": agent_score.agent_type,
                "workflow_id": quality_report.workflow_id,
            }
            for dim_score in agent_score.dimensions:
                if dim_score.score < threshold:
                    for gen in self._generators:
                        if gen.can_handle(dim_score.dimension):
                            fixes = gen.generate_fixes(dim_score, context)
                            all_fixes.extend(fixes)

        # Orchestration dimension fixes
        orch = quality_report.orchestration_score
        context = {
            "target_type": "orchestration",
            "workflow_id": orch.workflow_id,
            "workflow_name": orch.workflow_name,
            "detected_pattern": orch.detected_pattern,
        }
        for dim_score in orch.dimensions:
            if dim_score.score < threshold:
                for gen in self._generators:
                    if gen.can_handle(dim_score.dimension):
                        fixes = gen.generate_fixes(dim_score, context)
                        all_fixes.extend(fixes)

        # Sort by expected_improvement descending
        all_fixes.sort(key=lambda f: f.expected_improvement, reverse=True)
        return all_fixes
