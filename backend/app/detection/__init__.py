"""Detection algorithms for MAO Testing Platform."""

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
from .tiered import (
    TieredDetector,
    TieredResult,
    TierConfig,
    DetectionTier,
    EscalationReason,
    create_tiered_injection_detector,
    create_tiered_hallucination_detector,
    create_tiered_corruption_detector,
)
from .tool_provision import (
    tool_provision_detector,
    ToolProvisionDetector,
    ToolProvisionResult,
    ToolProvisionIssue,
    ProvisionSeverity,
    ProvisionIssueType,
)
from .withholding import (
    withholding_detector,
    InformationWithholdingDetector,
    WithholdingResult,
    WithholdingIssue,
    WithholdingSeverity,
    WithholdingType,
)
from .quality_gate import (
    quality_gate_detector,
    QualityGateDetector,
    QualityGateResult,
    QualityGateIssue,
    QualityGateSeverity,
    QualityGateIssueType,
)
from .completion import (
    completion_detector,
    CompletionMisjudgmentDetector,
    CompletionResult,
    CompletionIssue,
    CompletionSeverity,
    CompletionIssueType,
)
from .grounding import (
    grounding_detector,
    GroundingDetector,
    GroundingResult,
    GroundingSeverity,
    UngroundedClaim,
    NumericalError,
)
from .retrieval_quality import (
    retrieval_quality_detector,
    RetrievalQualityDetector,
    RetrievalQualityResult,
    RetrievalSeverity,
    IrrelevantDocument,
    CoverageGap,
)
from .turn_aware import (
    TurnSnapshot,
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
    TurnAwareContextNeglectDetector,
    TurnAwareDerailmentDetector,
    TurnAwareLoopDetector,
    analyze_conversation_turns,
)

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
    "CorruptionResult",
    "persona_scorer",
    "PersonaConsistencyScorer",
    "PersonaConsistencyResult",
    "Agent",
    "coordination_analyzer",
    "CoordinationAnalyzer",
    "CoordinationIssue",
    "CoordinationAnalysisResult",
    "Message",
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
    # Tiered detection with LLM-as-Judge
    "TieredDetector",
    "TieredResult",
    "TierConfig",
    "DetectionTier",
    "EscalationReason",
    "create_tiered_injection_detector",
    "create_tiered_hallucination_detector",
    "create_tiered_corruption_detector",
    # MAST F4: Inadequate Tool Provision
    "tool_provision_detector",
    "ToolProvisionDetector",
    "ToolProvisionResult",
    "ToolProvisionIssue",
    "ProvisionSeverity",
    "ProvisionIssueType",
    # MAST F8: Information Withholding
    "withholding_detector",
    "InformationWithholdingDetector",
    "WithholdingResult",
    "WithholdingIssue",
    "WithholdingSeverity",
    "WithholdingType",
    # MAST F13: Quality Gate Bypass
    "quality_gate_detector",
    "QualityGateDetector",
    "QualityGateResult",
    "QualityGateIssue",
    "QualityGateSeverity",
    "QualityGateIssueType",
    # MAST F14: Completion Misjudgment
    "completion_detector",
    "CompletionMisjudgmentDetector",
    "CompletionResult",
    "CompletionIssue",
    "CompletionSeverity",
    "CompletionIssueType",
    # MAST F15: Grounding Failure (OfficeQA-inspired)
    "grounding_detector",
    "GroundingDetector",
    "GroundingResult",
    "GroundingSeverity",
    "UngroundedClaim",
    "NumericalError",
    # MAST F16: Retrieval Quality Failure (OfficeQA-inspired)
    "retrieval_quality_detector",
    "RetrievalQualityDetector",
    "RetrievalQualityResult",
    "RetrievalSeverity",
    "IrrelevantDocument",
    "CoverageGap",
    # Turn-aware detection for multi-turn conversations (MAST-Data)
    "TurnSnapshot",
    "TurnAwareDetector",
    "TurnAwareDetectionResult",
    "TurnAwareSeverity",
    "TurnAwareContextNeglectDetector",
    "TurnAwareDerailmentDetector",
    "TurnAwareLoopDetector",
    "analyze_conversation_turns",
]
