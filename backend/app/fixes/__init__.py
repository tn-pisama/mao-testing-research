"""Fix suggestion system for detected agent failures."""

from .models import FixSuggestion, FixType, CodeChange, FixConfidence
from .generator import FixGenerator
from .loop_fixes import LoopFixGenerator
from .corruption_fixes import CorruptionFixGenerator
from .persona_fixes import PersonaFixGenerator
from .deadlock_fixes import DeadlockFixGenerator

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
]
