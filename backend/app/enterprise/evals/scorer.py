"""Base evaluation scorer and result types."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
from abc import ABC, abstractmethod
import uuid
from datetime import datetime


class EvalType(str, Enum):
    RELEVANCE = "relevance"
    COHERENCE = "coherence"
    HELPFULNESS = "helpfulness"
    SAFETY = "safety"
    FACTUALITY = "factuality"
    COMPLETENESS = "completeness"
    TOXICITY = "toxicity"
    CUSTOM = "custom"
    # Additional eval types used by the tiered detection system
    ACCURACY = "accuracy"
    QUALITY = "quality"
    GROUNDING = "grounding"


@dataclass
class EvalResult:
    id: str
    eval_type: EvalType
    score: float
    passed: bool
    reasoning: Optional[str] = None
    threshold: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "eval_type": self.eval_type.value,
            "score": self.score,
            "passed": self.passed,
            "reasoning": self.reasoning,
            "threshold": self.threshold,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EvalConfig:
    eval_type: EvalType
    threshold: float = 0.7
    weight: float = 1.0
    required: bool = False
    custom_prompt: Optional[str] = None


class BaseScorer(ABC):
    @abstractmethod
    def score(
        self,
        output: str,
        context: Optional[str] = None,
        expected: Optional[str] = None,
        **kwargs,
    ) -> EvalResult:
        pass


class EvalScorer:
    def __init__(self):
        self._scorers: Dict[EvalType, BaseScorer] = {}
        self._custom_scorers: Dict[str, Callable] = {}

    def register_scorer(self, eval_type: EvalType, scorer: BaseScorer) -> None:
        self._scorers[eval_type] = scorer

    def register_custom(self, name: str, scorer_fn: Callable) -> None:
        self._custom_scorers[name] = scorer_fn

    def evaluate(
        self,
        output: str,
        configs: List[EvalConfig],
        context: Optional[str] = None,
        expected: Optional[str] = None,
        **kwargs,
    ) -> List[EvalResult]:
        results = []

        for config in configs:
            if config.eval_type in self._scorers:
                scorer = self._scorers[config.eval_type]
                result = scorer.score(
                    output=output,
                    context=context,
                    expected=expected,
                    threshold=config.threshold,
                    **kwargs,
                )
                result.threshold = config.threshold
                result.passed = result.score >= config.threshold
                results.append(result)

        return results

    def evaluate_batch(
        self,
        outputs: List[str],
        configs: List[EvalConfig],
        contexts: Optional[List[str]] = None,
        expected: Optional[List[str]] = None,
    ) -> List[List[EvalResult]]:
        results = []

        for i, output in enumerate(outputs):
            ctx = contexts[i] if contexts else None
            exp = expected[i] if expected else None
            results.append(self.evaluate(output, configs, ctx, exp))

        return results

    def aggregate_scores(self, results: List[EvalResult], configs: List[EvalConfig]) -> Dict[str, Any]:
        if not results:
            return {"overall_score": 0, "passed": False, "scores": {}}

        config_map = {c.eval_type: c for c in configs}

        weighted_sum = 0
        total_weight = 0
        all_required_passed = True
        scores = {}

        for result in results:
            config = config_map.get(result.eval_type)
            weight = config.weight if config else 1.0

            weighted_sum += result.score * weight
            total_weight += weight
            scores[result.eval_type.value] = result.score

            if config and config.required and not result.passed:
                all_required_passed = False

        overall_score = weighted_sum / total_weight if total_weight > 0 else 0

        return {
            "overall_score": round(overall_score, 4),
            "passed": all_required_passed and overall_score >= 0.7,
            "scores": scores,
            "required_passed": all_required_passed,
        }


eval_scorer = EvalScorer()
