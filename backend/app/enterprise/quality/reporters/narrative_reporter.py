"""Human-readable narrative quality reporter.

Generates markdown narratives from QualityReport objects that explain
workflow quality in plain language for n8n workflow builders.
"""

from typing import List, Tuple

from ..models import QualityReport, DimensionScore


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

    def generate(self, report: QualityReport) -> str:
        """Return a markdown narrative summarizing workflow quality."""
        sections = [
            self._summary_section(report),
            self._strengths_section(report),
            self._risks_section(report),
            self._n8n_findings_section(report),
            self._recommendations_section(report),
        ]
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
            for dim_name, score, issues in risks[:5]:
                desc = _DIMENSION_DESCRIPTIONS.get(dim_name, dim_name)
                lines.append(f"- **{dim_name.replace('_', ' ').title()}** ({score:.0%}): {desc}")
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
    ) -> List[Tuple[str, float, List[str]]]:
        """Find dimensions scoring < 0.5."""
        weak = []
        all_dims = self._all_dimensions(report)
        for dim in all_dims:
            if dim.score < 0.5:
                weak.append((dim.dimension, dim.score, dim.issues or []))

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
