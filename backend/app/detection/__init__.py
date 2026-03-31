"""Detection algorithms for MAO Testing Platform.

ICP (Startup) detectors - always available:
- Loop detection (exact, structural, semantic)
- State corruption detection
- Persona consistency scoring
- Coordination analysis
- Cost calculation
- Hallucination detection
- Injection detection
- Context overflow detection
- Task derailment detection
- Context neglect detection
- Communication breakdown detection
- Specification mismatch detection
- Task decomposition detection
- Workflow analysis

Enterprise detectors (require feature flags):
- ML-based detection (ml_detection flag)
- Tiered detection with LLM-as-Judge (ml_detection flag)
- Quality gate detection (advanced_evals flag)
- Retrieval quality detection (advanced_evals flag)
- Turn-aware detection (ml_detection flag)
"""

# ICP (Startup) detectors - always available
from .loop import loop_detector, MultiLevelLoopDetector, LoopDetectionResult, StateSnapshot
from .corruption import corruption_detector, SemanticCorruptionDetector, CorruptionIssue, CorruptionResult
from .persona import persona_scorer, PersonaConsistencyScorer, PersonaConsistencyResult, Agent
from .coordination import coordination_analyzer, CoordinationAnalyzer, CoordinationIssue, CoordinationAnalysisResult, Message
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
from .withholding import (
    withholding_detector,
    InformationWithholdingDetector,
    WithholdingResult,
    WithholdingIssue,
    WithholdingSeverity,
    WithholdingType,
)
from .completion import (
    completion_detector,
    CompletionMisjudgmentDetector,
    CompletionResult,
    CompletionIssue,
    CompletionSeverity,
    CompletionIssueType,
)
from .convergence import (
    convergence_detector,
    ConvergenceDetector,
    ConvergenceResult,
    ConvergenceIssue,
    ConvergenceFailureType,
    ConvergenceSeverity,
)
from .delegation import (
    delegation_detector,
    DelegationQualityDetector,
    DelegationResult,
    DelegationIssue,
    DelegationSeverity,
    DelegationIssueType,
)
from .context_pressure import (
    context_pressure_detector,
    ContextPressureDetector,
    ContextPressureResult,
    PressureSignal,
    PressureSeverity,
)
from .compaction_quality import (
    compaction_quality_detector,
    CompactionQualityDetector,
    CompactionQualityResult,
    CompactionIssue,
    CompactionSeverity,
)
from .validation import DetectionValidator, ValidationMetrics

# Create singleton instances for convenience
derailment_detector = TaskDerailmentDetector()
context_neglect_detector = ContextNeglectDetector()
communication_detector = CommunicationBreakdownDetector()
specification_detector = SpecificationMismatchDetector()
decomposition_detector = TaskDecompositionDetector()
workflow_detector = FlawedWorkflowDetector()

# ICP exports - always available
__all__ = [
    # Loop detection
    "loop_detector",
    "MultiLevelLoopDetector",
    "LoopDetectionResult",
    "StateSnapshot",
    # Corruption detection
    "corruption_detector",
    "SemanticCorruptionDetector",
    "CorruptionIssue",
    "CorruptionResult",
    # Persona scoring
    "persona_scorer",
    "PersonaConsistencyScorer",
    "PersonaConsistencyResult",
    "Agent",
    # Coordination analysis
    "coordination_analyzer",
    "CoordinationAnalyzer",
    "CoordinationIssue",
    "CoordinationAnalysisResult",
    "Message",
    # Cost calculation
    "cost_calculator",
    "CostCalculator",
    "CostResult",
    "LLM_PRICING_2025",
    # Hallucination detection
    "hallucination_detector",
    "HallucinationDetector",
    "HallucinationResult",
    # Injection detection
    "injection_detector",
    "InjectionDetector",
    "InjectionResult",
    # Overflow detection
    "overflow_detector",
    "ContextOverflowDetector",
    "OverflowResult",
    "OverflowSeverity",
    # Derailment detection
    "derailment_detector",
    "TaskDerailmentDetector",
    "DerailmentResult",
    "DerailmentSeverity",
    # Context neglect detection
    "context_neglect_detector",
    "ContextNeglectDetector",
    "ContextNeglectResult",
    "NeglectSeverity",
    # Communication breakdown detection
    "communication_detector",
    "CommunicationBreakdownDetector",
    "CommunicationBreakdownResult",
    "BreakdownType",
    # Specification mismatch detection
    "specification_detector",
    "SpecificationMismatchDetector",
    "SpecificationMismatchResult",
    "MismatchType",
    # Task decomposition detection
    "decomposition_detector",
    "TaskDecompositionDetector",
    "DecompositionResult",
    "DecompositionIssue",
    # Workflow analysis
    "workflow_detector",
    "FlawedWorkflowDetector",
    "WorkflowAnalysisResult",
    "WorkflowIssue",
    "WorkflowNode",
    # Information withholding detection
    "withholding_detector",
    "InformationWithholdingDetector",
    "WithholdingResult",
    "WithholdingIssue",
    "WithholdingSeverity",
    "WithholdingType",
    # Completion misjudgment detection
    "completion_detector",
    "CompletionMisjudgmentDetector",
    "CompletionResult",
    "CompletionIssue",
    "CompletionSeverity",
    "CompletionIssueType",
    # Convergence detection
    "convergence_detector",
    "ConvergenceDetector",
    "ConvergenceResult",
    "ConvergenceIssue",
    "ConvergenceFailureType",
    "ConvergenceSeverity",
    # Delegation quality detection
    "delegation_detector",
    "DelegationQualityDetector",
    "DelegationResult",
    "DelegationIssue",
    "DelegationSeverity",
    "DelegationIssueType",
    # Context pressure detection
    "context_pressure_detector",
    "ContextPressureDetector",
    "ContextPressureResult",
    "PressureSignal",
    "PressureSeverity",
    # Compaction quality detection
    "compaction_quality_detector",
    "CompactionQualityDetector",
    "CompactionQualityResult",
    "CompactionIssue",
    "CompactionSeverity",
    # Validation
    "DetectionValidator",
    "ValidationMetrics",
]

# Enterprise exports - conditionally add when enabled
# These are imported from app.detection_enterprise when needed
# Example usage when enterprise is enabled:
#   from app.detection_enterprise import TieredDetector, TurnAwareDetector
