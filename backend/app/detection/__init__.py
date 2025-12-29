"""Detection algorithms for MAO Testing Platform."""

from .loop import loop_detector, MultiLevelLoopDetector, LoopDetectionResult, StateSnapshot
from .corruption import corruption_detector, SemanticCorruptionDetector, CorruptionIssue
from .persona import persona_scorer, PersonaConsistencyScorer, PersonaConsistencyResult, Agent
from .coordination import coordination_analyzer, CoordinationAnalyzer, CoordinationIssue
from .cost import cost_calculator, CostCalculator, CostResult, LLM_PRICING_2025
from .hallucination import hallucination_detector, HallucinationDetector, HallucinationResult
from .injection import injection_detector, InjectionDetector, InjectionResult
from .overflow import overflow_detector, ContextOverflowDetector, OverflowResult, OverflowSeverity
from .derailment import TaskDerailmentDetector, DerailmentResult, DerailmentSeverity
from .context import ContextNeglectDetector, ContextNeglectResult, NeglectSeverity
from .communication import CommunicationBreakdownDetector, CommunicationBreakdownResult, BreakdownType
from .specification import SpecificationMismatchDetector, SpecificationMismatchResult, MismatchType
from .decomposition import TaskDecompositionDetector, DecompositionResult, DecompositionIssue
from .workflow import FlawedWorkflowDetector, WorkflowAnalysisResult, WorkflowIssue, WorkflowNode

derailment_detector = TaskDerailmentDetector()
context_neglect_detector = ContextNeglectDetector()
communication_detector = CommunicationBreakdownDetector()
specification_detector = SpecificationMismatchDetector()
decomposition_detector = TaskDecompositionDetector()
workflow_detector = FlawedWorkflowDetector()

__all__ = [
    "loop_detector",
    "MultiLevelLoopDetector",
    "LoopDetectionResult",
    "StateSnapshot",
    "corruption_detector",
    "SemanticCorruptionDetector",
    "CorruptionIssue",
    "persona_scorer",
    "PersonaConsistencyScorer",
    "PersonaConsistencyResult",
    "Agent",
    "coordination_analyzer",
    "CoordinationAnalyzer",
    "CoordinationIssue",
    "cost_calculator",
    "CostCalculator",
    "CostResult",
    "LLM_PRICING_2025",
    "hallucination_detector",
    "HallucinationDetector",
    "HallucinationResult",
    "injection_detector",
    "InjectionDetector",
    "InjectionResult",
    "overflow_detector",
    "ContextOverflowDetector",
    "OverflowResult",
    "OverflowSeverity",
    "derailment_detector",
    "TaskDerailmentDetector",
    "DerailmentResult",
    "DerailmentSeverity",
    "context_neglect_detector",
    "ContextNeglectDetector",
    "ContextNeglectResult",
    "NeglectSeverity",
    "communication_detector",
    "CommunicationBreakdownDetector",
    "CommunicationBreakdownResult",
    "BreakdownType",
    "specification_detector",
    "SpecificationMismatchDetector",
    "SpecificationMismatchResult",
    "MismatchType",
    "decomposition_detector",
    "TaskDecompositionDetector",
    "DecompositionResult",
    "DecompositionIssue",
    "workflow_detector",
    "FlawedWorkflowDetector",
    "WorkflowAnalysisResult",
    "WorkflowIssue",
    "WorkflowNode",
]
