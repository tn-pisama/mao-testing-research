"""Fix suggestion system for detected agent failures."""

from .models import FixSuggestion, FixType, CodeChange, FixConfidence
from .generator import FixGenerator
from .loop_fixes import LoopFixGenerator
from .corruption_fixes import CorruptionFixGenerator
from .persona_fixes import PersonaFixGenerator
from .deadlock_fixes import DeadlockFixGenerator
from .hallucination_fixes import HallucinationFixGenerator
from .injection_fixes import InjectionFixGenerator
from .overflow_fixes import OverflowFixGenerator
from .derailment_fixes import DerailmentFixGenerator
from .context_neglect_fixes import ContextNeglectFixGenerator
from .communication_fixes import CommunicationFixGenerator
from .specification_fixes import SpecificationFixGenerator
from .decomposition_fixes import DecompositionFixGenerator
from .workflow_fixes import WorkflowFixGenerator
from .withholding_fixes import WithholdingFixGenerator
from .completion_fixes import CompletionFixGenerator
from .cost_fixes import CostFixGenerator
from .convergence_fixes import ConvergenceFixGenerator

__all__ = [
    "FixSuggestion",
    "FixType",
    "CodeChange",
    "FixConfidence",
    "FixGenerator",
    "LoopFixGenerator",
    "CorruptionFixGenerator",
    "PersonaFixGenerator",
    "DeadlockFixGenerator",
    "HallucinationFixGenerator",
    "InjectionFixGenerator",
    "OverflowFixGenerator",
    "DerailmentFixGenerator",
    "ContextNeglectFixGenerator",
    "CommunicationFixGenerator",
    "SpecificationFixGenerator",
    "DecompositionFixGenerator",
    "WorkflowFixGenerator",
    "WithholdingFixGenerator",
    "CompletionFixGenerator",
    "CostFixGenerator",
    "ConvergenceFixGenerator",
]
