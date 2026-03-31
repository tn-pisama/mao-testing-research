"""
Context Compaction Quality Detection
=====================================

Detects when context summarization or compaction degrades information
below a usability threshold — a failure mode observed in production
agentic systems (e.g., Claude Code's three-tier compaction system
requires circuit breakers because compaction itself can fail).

Failure patterns:
- Critical entity loss: names, numbers, file paths, URLs dropped
- Semantic drift: summary contradicts or misrepresents the original
- Over-compression: summary loses too much content relative to original
- Hallucinated insertions: summary adds claims not in the original

Inputs:
    original (str): The original context before compaction
    compacted (str): The compacted/summarized version

Version History:
- v1.0: Initial implementation with entity preservation + compression ratio
"""

DETECTOR_VERSION = "1.0"
DETECTOR_NAME = "CompactionQualityDetector"

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class CompactionSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


@dataclass
class CompactionIssue:
    issue_type: str
    description: str
    severity: CompactionSeverity


@dataclass
class CompactionQualityResult:
    detected: bool
    confidence: float
    severity: CompactionSeverity
    entity_preservation_ratio: float  # 0.0-1.0, how many critical entities survived
    compression_ratio: float  # compacted_len / original_len
    issues: List[CompactionIssue] = field(default_factory=list)
    raw_score: Optional[float] = None
    calibration_info: Optional[Dict[str, Any]] = None


# Regex patterns for extracting critical entities
_NUMBER_PATTERN = re.compile(r'\b\d+(?:\.\d+)?(?:%|px|ms|MB|GB|KB|k|K|M)?\b')
_FILE_PATH_PATTERN = re.compile(r'(?:^|[\s(])[/~][\w./\-]+\.\w{1,10}\b')
_URL_PATTERN = re.compile(r'https?://\S+')
_QUOTED_PATTERN = re.compile(r'["\']([^"\']{3,50})["\']')
_CODE_PATTERN = re.compile(r'`([^`]{2,60})`')
_ERROR_PATTERN = re.compile(r'\b(?:Error|Exception|Failed|CRITICAL|WARNING):\s*\S+', re.IGNORECASE)

# Names that should survive compaction (capitalized words that aren't sentence starters)
_PROPER_NAME_PATTERN = re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b')


def _extract_entities(text: str) -> set[str]:
    """Extract critical entities that should survive compaction."""
    entities: set[str] = set()

    for pattern in [_NUMBER_PATTERN, _FILE_PATH_PATTERN, _URL_PATTERN,
                    _QUOTED_PATTERN, _CODE_PATTERN, _ERROR_PATTERN]:
        for match in pattern.finditer(text):
            val = match.group(1) if match.lastindex else match.group(0)
            val = val.strip()
            if len(val) >= 2:
                entities.add(val.lower())

    return entities


def _extract_key_phrases(text: str) -> set[str]:
    """Extract key 2-3 word phrases for semantic overlap."""
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    phrases: set[str] = set()
    for i in range(len(words) - 1):
        phrases.add(f"{words[i]} {words[i+1]}")
    return phrases


class CompactionQualityDetector:
    """Detects when context compaction loses critical information."""

    def __init__(
        self,
        min_entity_preservation: float = 0.50,
        critical_compression_floor: float = 0.03,
        entity_weight: float = 0.45,
        compression_weight: float = 0.25,
        semantic_weight: float = 0.30,
    ):
        self.min_entity_preservation = min_entity_preservation
        self.critical_compression_floor = critical_compression_floor
        self.entity_weight = entity_weight
        self.compression_weight = compression_weight
        self.semantic_weight = semantic_weight

    def detect(
        self,
        original: str,
        compacted: str,
    ) -> CompactionQualityResult:
        """Detect compaction quality degradation.

        Args:
            original: The original context before compaction
            compacted: The compacted/summarized version
        """
        if not original or not compacted:
            return CompactionQualityResult(
                detected=False, confidence=0.0, severity=CompactionSeverity.NONE,
                entity_preservation_ratio=1.0, compression_ratio=1.0,
            )

        issues: list[CompactionIssue] = []

        # --- Signal 1: Entity preservation ---
        original_entities = _extract_entities(original)
        compacted_entities = _extract_entities(compacted)

        if original_entities:
            preserved = original_entities & compacted_entities
            entity_ratio = len(preserved) / len(original_entities)
            lost = original_entities - compacted_entities
        else:
            entity_ratio = 1.0
            lost = set()

        entity_score = 0.0
        if entity_ratio < self.min_entity_preservation:
            entity_score = min((1.0 - entity_ratio) / 0.50, 1.0)
            sample_lost = sorted(lost)[:5]
            issues.append(CompactionIssue(
                issue_type="entity_loss",
                description=f"Lost {len(lost)}/{len(original_entities)} entities: {', '.join(sample_lost)}",
                severity=CompactionSeverity.SEVERE if entity_ratio < 0.25 else CompactionSeverity.MODERATE,
            ))

        # --- Signal 2: Compression ratio ---
        compression_ratio = len(compacted) / max(len(original), 1)

        compression_score = 0.0
        if compression_ratio < self.critical_compression_floor:
            # Over-compressed: summary is < 3% of original
            compression_score = min((self.critical_compression_floor - compression_ratio) / 0.03, 1.0)
            issues.append(CompactionIssue(
                issue_type="over_compression",
                description=f"Compacted to {compression_ratio:.1%} of original ({len(compacted)} vs {len(original)} chars)",
                severity=CompactionSeverity.SEVERE,
            ))
        elif compression_ratio > 1.2:
            # Expanded: summary is longer than original (hallucination risk)
            compression_score = min((compression_ratio - 1.0) / 0.5, 1.0)
            issues.append(CompactionIssue(
                issue_type="expansion",
                description=f"Compacted version is {compression_ratio:.0%} of original - possible hallucinated content",
                severity=CompactionSeverity.MODERATE,
            ))

        # --- Signal 3: Semantic overlap ---
        original_phrases = _extract_key_phrases(original)
        compacted_phrases = _extract_key_phrases(compacted)

        semantic_score = 0.0
        if original_phrases:
            overlap = original_phrases & compacted_phrases
            semantic_ratio = len(overlap) / len(original_phrases)
            if semantic_ratio < 0.10:
                semantic_score = min((0.20 - semantic_ratio) / 0.20, 1.0)
                issues.append(CompactionIssue(
                    issue_type="semantic_drift",
                    description=f"Only {semantic_ratio:.0%} phrase overlap - summary may not represent original",
                    severity=CompactionSeverity.MODERATE,
                ))

        # --- Aggregate ---
        raw_score = (
            self.entity_weight * entity_score
            + self.compression_weight * compression_score
            + self.semantic_weight * semantic_score
        )

        confidence = min(raw_score, 1.0)
        detected = confidence > 0.0 and len(issues) > 0

        if not issues:
            severity = CompactionSeverity.NONE
        else:
            severities = [i.severity for i in issues]
            if CompactionSeverity.SEVERE in severities:
                severity = CompactionSeverity.SEVERE
            elif CompactionSeverity.MODERATE in severities:
                severity = CompactionSeverity.MODERATE
            else:
                severity = CompactionSeverity.MINOR

        return CompactionQualityResult(
            detected=detected,
            confidence=confidence,
            severity=severity,
            entity_preservation_ratio=entity_ratio,
            compression_ratio=compression_ratio,
            issues=issues,
            raw_score=raw_score,
        )


# Singleton instance
compaction_quality_detector = CompactionQualityDetector()
