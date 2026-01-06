"""
Replay Diff - Compare original and replay outputs.

Provides detailed comparison between:
- Original trace output
- Replay output
- Multiple replay variants (A/B testing)
"""

import difflib
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DiffType(str, Enum):
    IDENTICAL = "identical"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    COMPLETELY_DIFFERENT = "completely_different"


@dataclass
class DiffSegment:
    segment_type: str
    original: str
    replay: str
    position: int
    length: int


@dataclass
class DiffResult:
    diff_type: DiffType
    similarity_score: float
    segments: list[DiffSegment]
    summary: str
    original_length: int
    replay_length: int
    added_chars: int
    removed_chars: int
    changed_lines: int


class ReplayDiff:
    """
    Compares original and replay outputs to identify divergences.
    
    Provides:
    - Character-level diffs
    - Semantic similarity scoring
    - Structured diff segments
    """
    
    def __init__(
        self,
        similarity_threshold_identical: float = 0.99,
        similarity_threshold_minor: float = 0.90,
        similarity_threshold_moderate: float = 0.70,
    ):
        self.threshold_identical = similarity_threshold_identical
        self.threshold_minor = similarity_threshold_minor
        self.threshold_moderate = similarity_threshold_moderate

    def compare_text(
        self,
        original: str,
        replay: str,
    ) -> DiffResult:
        if original == replay:
            return DiffResult(
                diff_type=DiffType.IDENTICAL,
                similarity_score=1.0,
                segments=[],
                summary="Outputs are identical",
                original_length=len(original),
                replay_length=len(replay),
                added_chars=0,
                removed_chars=0,
                changed_lines=0,
            )
        
        similarity = self._compute_similarity(original, replay)
        
        diff_type = self._classify_diff(similarity)
        
        segments = self._compute_segments(original, replay)
        
        added = sum(len(s.replay) for s in segments if s.segment_type == "added")
        removed = sum(len(s.original) for s in segments if s.segment_type == "removed")
        
        original_lines = original.split("\n")
        replay_lines = replay.split("\n")
        changed_lines = sum(
            1 for a, b in zip(original_lines, replay_lines) if a != b
        ) + abs(len(original_lines) - len(replay_lines))
        
        summary = self._generate_summary(diff_type, similarity, segments)
        
        return DiffResult(
            diff_type=diff_type,
            similarity_score=similarity,
            segments=segments,
            summary=summary,
            original_length=len(original),
            replay_length=len(replay),
            added_chars=added,
            removed_chars=removed,
            changed_lines=changed_lines,
        )

    def compare_structured(
        self,
        original: dict[str, Any],
        replay: dict[str, Any],
    ) -> dict[str, DiffResult]:
        results = {}
        
        all_keys = set(original.keys()) | set(replay.keys())
        
        for key in all_keys:
            orig_val = original.get(key, "")
            replay_val = replay.get(key, "")
            
            if isinstance(orig_val, str) and isinstance(replay_val, str):
                results[key] = self.compare_text(orig_val, replay_val)
            elif isinstance(orig_val, dict) and isinstance(replay_val, dict):
                nested = self.compare_structured(orig_val, replay_val)
                for nested_key, nested_result in nested.items():
                    results[f"{key}.{nested_key}"] = nested_result
            else:
                orig_str = str(orig_val) if orig_val else ""
                replay_str = str(replay_val) if replay_val else ""
                results[key] = self.compare_text(orig_str, replay_str)
        
        return results

    def compare_multiple(
        self,
        original: str,
        replays: dict[str, str],
    ) -> dict[str, DiffResult]:
        results = {}
        for name, replay in replays.items():
            results[name] = self.compare_text(original, replay)
        return results

    def _compute_similarity(self, text1: str, text2: str) -> float:
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        matcher = difflib.SequenceMatcher(None, text1, text2)
        return matcher.ratio()

    def _classify_diff(self, similarity: float) -> DiffType:
        if similarity >= self.threshold_identical:
            return DiffType.IDENTICAL
        elif similarity >= self.threshold_minor:
            return DiffType.MINOR
        elif similarity >= self.threshold_moderate:
            return DiffType.MODERATE
        elif similarity >= 0.3:
            return DiffType.MAJOR
        else:
            return DiffType.COMPLETELY_DIFFERENT

    def _compute_segments(
        self,
        original: str,
        replay: str,
    ) -> list[DiffSegment]:
        segments = []
        
        matcher = difflib.SequenceMatcher(None, original, replay)
        position = 0
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                position += i2 - i1
                continue
            
            segment = DiffSegment(
                segment_type=tag,
                original=original[i1:i2],
                replay=replay[j1:j2],
                position=position,
                length=max(i2 - i1, j2 - j1),
            )
            segments.append(segment)
            position += i2 - i1
        
        return segments

    def _generate_summary(
        self,
        diff_type: DiffType,
        similarity: float,
        segments: list[DiffSegment],
    ) -> str:
        if diff_type == DiffType.IDENTICAL:
            return "Outputs are identical"
        
        change_count = len(segments)
        
        if diff_type == DiffType.MINOR:
            return f"Minor differences: {change_count} changes, {similarity:.1%} similarity"
        elif diff_type == DiffType.MODERATE:
            return f"Moderate differences: {change_count} changes, {similarity:.1%} similarity"
        elif diff_type == DiffType.MAJOR:
            return f"Major differences: {change_count} changes, {similarity:.1%} similarity"
        else:
            return f"Completely different outputs: {similarity:.1%} similarity"

    def format_diff_html(self, result: DiffResult, original: str, replay: str) -> str:
        if result.diff_type == DiffType.IDENTICAL:
            return f"<pre>{original}</pre>"
        
        html_parts = []
        
        differ = difflib.HtmlDiff()
        table = differ.make_table(
            original.split("\n"),
            replay.split("\n"),
            fromdesc="Original",
            todesc="Replay",
        )
        
        return table

    def format_diff_markdown(self, result: DiffResult, original: str, replay: str) -> str:
        if result.diff_type == DiffType.IDENTICAL:
            return f"**Identical outputs**\n\n```\n{original}\n```"
        
        lines = [
            f"## Diff Summary",
            f"- **Type**: {result.diff_type.value}",
            f"- **Similarity**: {result.similarity_score:.1%}",
            f"- **Changes**: {len(result.segments)} segments",
            "",
            "## Original",
            "```",
            original,
            "```",
            "",
            "## Replay",
            "```",
            replay,
            "```",
        ]
        
        if result.segments:
            lines.extend([
                "",
                "## Changes",
            ])
            for i, seg in enumerate(result.segments[:10]):
                lines.append(f"- **{seg.segment_type}** at position {seg.position}")
                if seg.original:
                    lines.append(f"  - Original: `{seg.original[:50]}...`" if len(seg.original) > 50 else f"  - Original: `{seg.original}`")
                if seg.replay:
                    lines.append(f"  - Replay: `{seg.replay[:50]}...`" if len(seg.replay) > 50 else f"  - Replay: `{seg.replay}`")
        
        return "\n".join(lines)
