"""Base fix generator and orchestrator."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import secrets

from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class BaseFixGenerator(ABC):
    """Base class for detection-specific fix generators."""
    
    @abstractmethod
    def can_handle(self, detection_type: str) -> bool:
        """Check if this generator can handle the detection type."""
        pass
    
    @abstractmethod
    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        """Generate fix suggestions for a detection."""
        pass
    
    def _generate_id(self) -> str:
        return f"fix_{secrets.token_hex(8)}"
    
    def _create_suggestion(
        self,
        detection_id: str,
        detection_type: str,
        fix_type: FixType,
        confidence: FixConfidence,
        title: str,
        description: str,
        rationale: str,
        code_changes: List[CodeChange] = None,
        **kwargs,
    ) -> FixSuggestion:
        return FixSuggestion(
            id=self._generate_id(),
            detection_id=detection_id,
            detection_type=detection_type,
            fix_type=fix_type,
            confidence=confidence,
            title=title,
            description=description,
            rationale=rationale,
            code_changes=code_changes or [],
            **kwargs,
        )


class FixGenerator:
    """Orchestrates fix generation across all detection types."""
    
    def __init__(self):
        self._generators: List[BaseFixGenerator] = []
    
    def register(self, generator: BaseFixGenerator) -> None:
        """Register a fix generator."""
        self._generators.append(generator)
    
    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[FixSuggestion]:
        """Generate all applicable fixes for a detection."""
        context = context or {}
        detection_type = detection.get("detection_type", "")
        
        all_fixes = []
        for generator in self._generators:
            if generator.can_handle(detection_type):
                fixes = generator.generate_fixes(detection, context)
                all_fixes.extend(fixes)
        
        all_fixes.sort(key=lambda f: (
            0 if f.confidence == FixConfidence.HIGH else 
            1 if f.confidence == FixConfidence.MEDIUM else 2
        ))
        
        return all_fixes
    
    def generate_fixes_batch(
        self,
        detections: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[FixSuggestion]]:
        """Generate fixes for multiple detections."""
        return {
            d.get("id", ""): self.generate_fixes(d, context)
            for d in detections
        }
