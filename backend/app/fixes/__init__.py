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

def create_fix_generator() -> FixGenerator:
    """Create a FixGenerator with all detection-specific generators registered."""
    gen = FixGenerator()
    gen.register(LoopFixGenerator())
    gen.register(CorruptionFixGenerator())
    gen.register(PersonaFixGenerator())
    gen.register(DeadlockFixGenerator())
    gen.register(HallucinationFixGenerator())
    gen.register(InjectionFixGenerator())
    gen.register(OverflowFixGenerator())
    gen.register(DerailmentFixGenerator())
    gen.register(ContextNeglectFixGenerator())
    gen.register(CommunicationFixGenerator())
    gen.register(SpecificationFixGenerator())
    gen.register(DecompositionFixGenerator())
    gen.register(WorkflowFixGenerator())
    gen.register(WithholdingFixGenerator())
    gen.register(CompletionFixGenerator())
    gen.register(CostFixGenerator())
    return gen


__all__ = [
    "FixSuggestion",
    "FixType",
    "CodeChange",
    "FixConfidence",
    "FixGenerator",
    "create_fix_generator",
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
]
