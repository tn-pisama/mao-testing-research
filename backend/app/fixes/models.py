"""Data models for fix suggestions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class FixType(Enum):
    RETRY_LIMIT = "retry_limit"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    CIRCUIT_BREAKER = "circuit_breaker"
    STATE_VALIDATION = "state_validation"
    SCHEMA_ENFORCEMENT = "schema_enforcement"
    INPUT_SANITIZATION = "input_sanitization"
    PROMPT_REINFORCEMENT = "prompt_reinforcement"
    ROLE_BOUNDARY = "role_boundary"
    TIMEOUT_ADDITION = "timeout_addition"
    PRIORITY_ADJUSTMENT = "priority_adjustment"
    ASYNC_HANDOFF = "async_handoff"
    CHECKPOINT_RECOVERY = "checkpoint_recovery"


class FixConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CodeChange:
    """A single code change within a fix suggestion."""
    file_path: str
    language: str
    original_code: Optional[str]
    suggested_code: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    description: str = ""
    
    def to_diff(self) -> str:
        """Generate unified diff format."""
        if not self.original_code:
            return f"+++ {self.file_path}\n@@ -0,0 +1 @@\n+ {self.suggested_code}"
        
        original_lines = self.original_code.split('\n')
        suggested_lines = self.suggested_code.split('\n')
        
        diff_lines = [f"--- {self.file_path}", f"+++ {self.file_path}"]
        
        start = self.start_line or 1
        diff_lines.append(f"@@ -{start},{len(original_lines)} +{start},{len(suggested_lines)} @@")
        
        for line in original_lines:
            diff_lines.append(f"- {line}")
        for line in suggested_lines:
            diff_lines.append(f"+ {line}")
        
        return '\n'.join(diff_lines)


@dataclass
class FixSuggestion:
    """A complete fix suggestion for a detected issue."""
    id: str
    detection_id: str
    detection_type: str
    fix_type: FixType
    confidence: FixConfidence
    title: str
    description: str
    rationale: str
    code_changes: List[CodeChange] = field(default_factory=list)
    estimated_impact: str = ""
    breaking_changes: bool = False
    requires_testing: bool = True
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "detection_id": self.detection_id,
            "detection_type": self.detection_type,
            "fix_type": self.fix_type.value,
            "confidence": self.confidence.value,
            "title": self.title,
            "description": self.description,
            "rationale": self.rationale,
            "code_changes": [
                {
                    "file_path": c.file_path,
                    "language": c.language,
                    "original_code": c.original_code,
                    "suggested_code": c.suggested_code,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "description": c.description,
                    "diff": c.to_diff(),
                }
                for c in self.code_changes
            ],
            "estimated_impact": self.estimated_impact,
            "breaking_changes": self.breaking_changes,
            "requires_testing": self.requires_testing,
            "tags": self.tags,
            "metadata": self.metadata,
        }
    
    def to_markdown(self) -> str:
        """Generate markdown description for PR."""
        md = [
            f"## {self.title}",
            "",
            f"**Type:** {self.fix_type.value}",
            f"**Confidence:** {self.confidence.value}",
            f"**Breaking Changes:** {'Yes' if self.breaking_changes else 'No'}",
            "",
            "### Description",
            self.description,
            "",
            "### Rationale", 
            self.rationale,
            "",
        ]
        
        if self.code_changes:
            md.append("### Code Changes")
            md.append("")
            for change in self.code_changes:
                md.append(f"#### `{change.file_path}`")
                md.append(change.description)
                md.append("")
                md.append(f"```{change.language}")
                md.append(change.suggested_code)
                md.append("```")
                md.append("")
        
        if self.estimated_impact:
            md.append("### Expected Impact")
            md.append(self.estimated_impact)
            md.append("")
        
        return '\n'.join(md)
