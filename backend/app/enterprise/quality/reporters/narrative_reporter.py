"""Human-readable narrative quality reporter.

Generates markdown narratives from QualityReport objects that explain
workflow quality in plain language for n8n workflow builders.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from ..models import QualityReport, DimensionScore

if TYPE_CHECKING:
    from ...quality.healing.models import QualityHealingResult


# Dimension descriptions for narrative context
_DIMENSION_DESCRIPTIONS = {
    "role_clarity": "how well agent roles and system prompts are defined",
    "output_consistency": "consistency of agent output structures",
    "error_handling": "error recovery capability (retry, timeout, failover)",
    "tool_usage": "quality of tool integration and descriptions",
    "config_appropriateness": "model configuration (temperature, tokens, model choice)",
    "data_flow_clarity": "clarity of data passing between nodes",
    "complexity_management": "workflow size and branching complexity",
    "agent_coupling": "balance of agent interdependence",
    "observability": "monitoring, checkpoints, and debugging capability",
    "best_practices": "adherence to n8n workflow best practices",
}


class QualityNarrativeReporter:
    """Generates human-readable markdown narratives from quality reports."""

    def generate(
        self,
        report: QualityReport,
        healing_result: Optional["QualityHealingResult"] = None,
        after_report: Optional[QualityReport] = None,
    ) -> str:
        """Return a markdown narrative summarizing workflow quality.

        Args:
            report: The initial quality assessment.
            healing_result: Optional healing result (includes applied fixes).
            after_report: Optional post-healing quality assessment.
        """
        sections = [
            self._summary_section(report),
            self._strengths_section(report),
            self._risks_section(report),
            self._n8n_findings_section(report),
            self._recommendations_section(report),
        ]

        if healing_result and after_report:
            sections.append(
                self._healing_impact_section(report, healing_result, after_report)
            )

        return "\n\n".join(s for s in sections if s)

    def _summary_section(self, report: QualityReport) -> str:
        score_pct = f"{report.overall_score:.0%}"
        grade = report.overall_grade
        agent_count = len(report.agent_scores)
        pattern = report.orchestration_score.detected_pattern or "unknown"

        lines = [
            f"## Quality Summary",
            "",
            f"Your workflow **{report.workflow_name}** scores **{score_pct}** "
            f"({grade}) across {agent_count} agent{'s' if agent_count != 1 else ''}.",
        ]

        if report.orchestration_score.complexity_metrics:
            cm = report.orchestration_score.complexity_metrics
            node_count = cm.node_count if hasattr(cm, "node_count") else cm.get("node_count", 0)
            conn_count = cm.connection_count if hasattr(cm, "connection_count") else cm.get("connection_count", 0)
            lines.append(
                f"The workflow uses a **{pattern}** pattern with "
                f"{node_count} nodes and {conn_count} connections."
            )

        if report.is_provisional:
            lines.append(
                "\n> **Note:** Some scores are provisional because no execution "
                "history was provided. Run the workflow 3+ times and re-assess "
                "for verified output consistency scores."
            )

        return "\n".join(lines)

    def _strengths_section(self, report: QualityReport) -> str:
        strengths = self._collect_strong_dimensions(report)
        if not strengths:
            return ""

        lines = ["## Strengths", ""]
        for dim_name, score, reliability in strengths[:5]:
            desc = _DIMENSION_DESCRIPTIONS.get(dim_name, dim_name)
            confidence_note = f" (high confidence)" if reliability == "high" else ""
            lines.append(f"- **{dim_name.replace('_', ' ').title()}** ({score:.0%}){confidence_note}: {desc}")

        return "\n".join(lines)

    def _risks_section(self, report: QualityReport) -> str:
        risks = self._collect_weak_dimensions(report)
        critical = self._collect_critical_issues(report)

        if not risks and not critical:
            return ""

        lines = ["## Risks", ""]

        if critical:
            lines.append("### Critical Issues")
            lines.append("")
            for issue in critical[:5]:
                lines.append(f"- {issue}")
            lines.append("")

        if risks:
            lines.append("### Low-Scoring Dimensions")
            lines.append("")
            for dim_name, score, issues, evidence in risks[:5]:
                desc = _DIMENSION_DESCRIPTIONS.get(dim_name, dim_name)
                lines.append(f"- **{dim_name.replace('_', ' ').title()}** ({score:.0%}): {desc}")
                # Add evidence-based explanation
                if evidence:
                    why = self._explain_evidence(dim_name, evidence)
                    if why:
                        lines.append(f"  - *Why:* {why}")
                for issue in issues[:2]:
                    lines.append(f"  - {issue}")

        return "\n".join(lines)

    def _n8n_findings_section(self, report: QualityReport) -> str:
        findings = getattr(report, "n8n_detection_findings", [])
        if not findings:
            return ""

        lines = ["## Structural Analysis", ""]
        lines.append(
            f"PISAMA's n8n-specific detectors found **{len(findings)} issue{'s' if len(findings) != 1 else ''}** "
            "in your workflow structure:"
        )
        lines.append("")

        for f in findings:
            severity = f.get("severity", "unknown")
            severity_icon = {"severe": "!!!", "moderate": "!!", "minor": "!"}.get(severity.lower(), "")
            lines.append(f"- **{f.get('detector', 'Unknown')}** [{severity}]: {f.get('explanation', '')}")
            if f.get("suggested_fix"):
                lines.append(f"  - *Fix:* {f['suggested_fix']}")

        return "\n".join(lines)

    def _recommendations_section(self, report: QualityReport) -> str:
        if not report.improvements:
            return "## Recommendations\n\nNo specific improvements recommended — your workflow looks solid!"

        # Sort by priority: impact * inverse-effort
        effort_weights = {"low": 3, "medium": 2, "high": 1}
        scored = []
        for imp in report.improvements:
            effort_str = imp.effort.value if hasattr(imp.effort, "value") else str(imp.effort)
            effort_w = effort_weights.get(effort_str, 2)
            scored.append((imp, effort_w))

        scored.sort(key=lambda x: -x[1])
        top = [s[0] for s in scored[:5]]

        lines = ["## Recommendations", ""]
        lines.append("Prioritized by impact and effort:")
        lines.append("")

        for i, imp in enumerate(top, 1):
            severity = imp.severity.value if hasattr(imp.severity, "value") else str(imp.severity)
            effort = imp.effort.value if hasattr(imp.effort, "value") else str(imp.effort)
            lines.append(f"### {i}. {imp.title}")
            lines.append("")
            lines.append(f"**Severity:** {severity} | **Effort:** {effort}")
            if imp.description:
                lines.append(f"\n{imp.description}")
            if imp.suggested_change:
                lines.append(f"\n*Suggested change:* {imp.suggested_change}")
            lines.append("")

        return "\n".join(lines)


    def _healing_impact_section(
        self,
        before_report: QualityReport,
        healing_result: "QualityHealingResult",
        after_report: QualityReport,
    ) -> str:
        """Generate a Healing Impact section showing before/after comparison."""
        before_score = before_report.overall_score
        after_score = after_report.overall_score
        improvement = after_score - before_score
        n_fixes = len(healing_result.applied_fixes)
        n_validated = sum(
            1 for v in healing_result.validation_results if v.success
        )

        lines = [
            "## Healing Impact",
            "",
            f"**Before:** {before_score:.0%} ({before_report.overall_grade}) "
            f"-> **After:** {after_score:.0%} ({after_report.overall_grade}) "
            f"-- **{improvement:+.0%} improvement**",
            "",
            f"- {n_fixes} fixes applied across "
            f"{len(healing_result.dimensions_targeted)} dimensions",
            f"- Fix success rate: {n_validated}/{n_fixes} "
            f"({n_validated / n_fixes:.0%})" if n_fixes else "",
            "",
        ]

        # Per-dimension before/after table
        before_dims = self._dimension_scores_map(before_report)
        after_dims = self._dimension_scores_map(after_report)

        changed = []
        for dim in sorted(set(list(before_dims.keys()) + list(after_dims.keys()))):
            b = before_dims.get(dim, 0.0)
            a = after_dims.get(dim, 0.0)
            delta = a - b
            if abs(delta) > 0.01:
                changed.append((dim, b, a, delta))

        if changed:
            lines.append("| Dimension | Before | After | Change |")
            lines.append("|-----------|--------|-------|--------|")
            changed.sort(key=lambda x: -x[3])
            for dim, b, a, delta in changed:
                dim_display = dim.replace("_", " ").title()
                lines.append(f"| {dim_display} | {b:.0%} | {a:.0%} | {delta:+.0%} |")
            lines.append("")

        # Code-level fix descriptions
        if healing_result.applied_fixes:
            lines.append("### What Changed")
            lines.append("")

            # Group by dimension
            by_dim: Dict[str, list] = {}
            for fix in healing_result.applied_fixes:
                by_dim.setdefault(fix.dimension, []).append(fix)

            for dim, fixes in sorted(by_dim.items()):
                dim_display = dim.replace("_", " ").title()
                lines.append(f"**{dim_display}:**")
                for fix in fixes:
                    desc = self._describe_fix_change(fix)
                    if desc:
                        lines.append(f"- {desc}")
                lines.append("")

        return "\n".join(lines)

    def _dimension_scores_map(self, report: QualityReport) -> Dict[str, float]:
        """Build a flat dimension -> average score map from a report."""
        scores: Dict[str, List[float]] = {}
        for agent in report.agent_scores:
            for d in agent.dimensions:
                scores.setdefault(d.dimension, []).append(d.score)
        for d in report.orchestration_score.dimensions:
            scores[d.dimension] = [d.score]
        return {k: sum(v) / len(v) for k, v in scores.items()}

    @staticmethod
    def _describe_fix_change(applied_fix) -> Optional[str]:
        """Generate a human-readable description of what a fix changed."""
        dim = applied_fix.dimension
        mod = applied_fix.modified_state or {}
        orig = applied_fix.original_state or {}
        target = applied_fix.target_component

        if dim == "role_clarity":
            # Look at systemMessage changes
            for node in mod.get("nodes", []):
                if node.get("name") == target:
                    msg = node.get("parameters", {}).get("systemMessage", "")
                    if msg:
                        word_count = len(msg.split())
                        return (
                            f"Added system prompt with role definition, output format, "
                            f"and boundaries ({word_count} words) to {target}"
                        )
            return f"Added role definition to {target}" if target else None

        elif dim == "error_handling":
            for node in mod.get("nodes", []):
                if node.get("name") == target:
                    parts = []
                    if node.get("continueOnFail"):
                        parts.append("continueOnFail: true")
                    opts = node.get("parameters", {}).get("options", {})
                    if opts.get("retryOnFail"):
                        retries = opts.get("maxRetries", 3)
                        parts.append(f"retryOnFail: true ({retries} retries)")
                    if opts.get("timeout"):
                        parts.append(f"timeout: {opts['timeout']}ms")
                    if parts:
                        return f"Set {', '.join(parts)} on {target}"
            return f"Configured error handling on {target}" if target else None

        elif dim == "best_practices":
            new_nodes = set()
            orig_names = {n.get("name") for n in orig.get("nodes", [])}
            for n in mod.get("nodes", []):
                if n.get("name") not in orig_names:
                    new_nodes.add(n.get("type", "unknown"))
            if "n8n-nodes-base.errorTrigger" in new_nodes:
                return "Added Error Trigger node for global error handling"
            return "Applied best practices configuration"

        elif dim == "test_coverage":
            pin_count = sum(
                1 for n in mod.get("nodes", [])
                if n.get("pinData") or n.get("parameters", {}).get("pinData")
            )
            if pin_count > 0:
                return f"Added pinData test fixtures to {pin_count} nodes"
            return "Added test data fixtures"

        elif dim == "observability":
            new_types = set()
            orig_names = {n.get("name") for n in orig.get("nodes", [])}
            for n in mod.get("nodes", []):
                if n.get("name") not in orig_names:
                    new_types.add(n.get("type", "unknown"))
            if new_types:
                return f"Added monitoring nodes: {', '.join(t.split('.')[-1] for t in new_types)}"
            return "Added observability instrumentation"

        elif dim == "documentation_quality":
            note_count = sum(
                1 for n in mod.get("nodes", [])
                if "stickyNote" in n.get("type", "")
            )
            orig_notes = sum(
                1 for n in orig.get("nodes", [])
                if "stickyNote" in n.get("type", "")
            )
            added = note_count - orig_notes
            if added > 0:
                return f"Added {added} sticky note{'s' if added != 1 else ''} documenting workflow logic"
            return "Added documentation"

        return None

    def _explain_evidence(self, dimension: str, evidence: Dict[str, Any]) -> Optional[str]:
        """Generate a human-readable explanation of WHY a dimension scored low."""
        if not evidence:
            return None

        if dimension == "role_clarity":
            word_count = evidence.get("word_count", 0)
            keywords = evidence.get("role_keywords_found", 0)
            if word_count == 0:
                return "No system prompt defined"
            parts = []
            if word_count < 50:
                parts.append(f"system prompt is only {word_count} words (aim for 50+)")
            if keywords < 2:
                parts.append(f"only {keywords} role keywords found (aim for 3+)")
            return "; ".join(parts) if parts else None

        elif dimension == "output_consistency":
            if evidence.get("is_provisional"):
                return "No execution history available — score is estimated"
            return None

        elif dimension == "error_handling":
            missing = []
            if not evidence.get("continue_on_fail"):
                missing.append("continueOnFail")
            if not evidence.get("retry_on_fail"):
                missing.append("retryOnFail")
            if not evidence.get("has_timeout"):
                missing.append("timeout")
            return f"Missing: {', '.join(missing)}" if missing else None

        elif dimension == "tool_usage":
            tools_missing_desc = evidence.get("tools_missing_description", 0)
            if tools_missing_desc > 0:
                return f"{tools_missing_desc} tool(s) have no description"
            return None

        elif dimension == "config_appropriateness":
            temp = evidence.get("temperature")
            if temp is not None and temp > 0.8:
                return f"Temperature is {temp} — consider lowering for more consistent output"
            return None

        elif dimension == "best_practices":
            issues = []
            if not evidence.get("has_global_error_handler"):
                issues.append("no global error handler")
            if not evidence.get("execution_timeout"):
                issues.append("no execution timeout")
            return "; ".join(issues) if issues else None

        elif dimension == "test_coverage":
            ratio = evidence.get("coverage_ratio", 0)
            nodes_with_data = evidence.get("nodes_with_test_data", 0)
            total = evidence.get("total_nodes", 0)
            if nodes_with_data == 0:
                return f"No test data (pinData) on any of {total} nodes"
            return f"Only {nodes_with_data}/{total} nodes have test data ({ratio:.0%} coverage)"

        elif dimension == "documentation_quality":
            notes = evidence.get("sticky_note_count", 0)
            if notes == 0:
                return "No sticky notes explaining workflow logic"
            return None

        elif dimension == "ai_architecture":
            ai_tools = evidence.get("ai_tool_connections", 0)
            ai_models = evidence.get("ai_model_connections", 0)
            if ai_tools == 0 and ai_models == 0:
                return "No AI tool or model sub-node connections found"
            return None

        return None

    def _collect_strong_dimensions(
        self, report: QualityReport
    ) -> List[Tuple[str, float, str]]:
        """Find dimensions scoring > 0.75 with non-low reliability."""
        from .. import DIMENSION_RELIABILITY

        strong = []
        all_dims = self._all_dimensions(report)
        for dim in all_dims:
            reliability = DIMENSION_RELIABILITY.get(dim.dimension, "medium")
            if dim.score >= 0.75 and reliability != "low":
                strong.append((dim.dimension, dim.score, reliability))

        strong.sort(key=lambda x: -x[1])
        return strong

    def _collect_weak_dimensions(
        self, report: QualityReport
    ) -> List[Tuple[str, float, List[str], Dict[str, Any]]]:
        """Find dimensions scoring < 0.5."""
        weak = []
        all_dims = self._all_dimensions(report)
        for dim in all_dims:
            if dim.score < 0.5:
                weak.append((dim.dimension, dim.score, dim.issues or [], dim.evidence or {}))

        weak.sort(key=lambda x: x[1])
        return weak

    def _collect_critical_issues(self, report: QualityReport) -> List[str]:
        """Collect all critical issues from agents and orchestration."""
        issues = list(report.orchestration_score.critical_issues)
        for agent in report.agent_scores:
            issues.extend(agent.critical_issues)
        return issues

    def _all_dimensions(self, report: QualityReport) -> List[DimensionScore]:
        """Collect all dimension scores from agents and orchestration."""
        dims = list(report.orchestration_score.dimensions)
        for agent in report.agent_scores:
            dims.extend(agent.dimensions)
        # Deduplicate by dimension name, keeping worst score
        seen = {}
        for dim in dims:
            if dim.dimension not in seen or dim.score < seen[dim.dimension].score:
                seen[dim.dimension] = dim
        return list(seen.values())
