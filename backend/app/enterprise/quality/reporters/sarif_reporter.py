"""SARIF 2.1.0 export for PISAMA quality reports.

Produces a Static Analysis Results Interchange Format (SARIF) document so
quality findings can be consumed by GitHub Code Scanning, VS Code SARIF
Viewer, and other standard SARIF tooling.

Reference: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""

from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import QualityReport

from ..error_codes import ERROR_CODES, get_codes_for_dimension


# Map PISAMA severity to SARIF level
_SEVERITY_TO_SARIF_LEVEL: Dict[str, str] = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}


class QualitySARIFReporter:
    """Export a :class:`QualityReport` as a SARIF 2.1.0 JSON document.

    Each quality issue found in the report is emitted as a SARIF *result*
    with:

    * ``ruleId`` -- the PISAMA error code (e.g. ``QE-RC-001``)
    * ``level``  -- mapped from the error code's severity
    * ``message`` -- the issue text from the quality dimension
    * ``locations`` -- a single physical location pointing to the workflow
      file (since n8n workflows are single JSON files, the location is
      always line 1 col 1 unless more specific info is available)

    The tool descriptor includes every registered error code as a SARIF
    *rule* so consumers can display full rule metadata even for rules
    that produced no results in this run.
    """

    SARIF_VERSION = "2.1.0"
    SARIF_SCHEMA = (
        "https://docs.oasis-open.org/sarif/sarif/v2.1.0/"
        "cos02/schemas/sarif-schema-2.1.0.json"
    )
    TOOL_NAME = "PISAMA Quality Engine"
    TOOL_VERSION = "1.0.0"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export_report(
        self,
        report: "QualityReport",
        workflow_file: str = "workflow.json",
    ) -> Dict[str, Any]:
        """Render the quality report as a SARIF 2.1.0 JSON-serialisable dict.

        Args:
            report: A fully populated :class:`QualityReport`.
            workflow_file: The file path (relative or absolute) to attach
                to SARIF location entries.  Defaults to ``"workflow.json"``.

        Returns:
            A ``dict`` that conforms to the SARIF 2.1.0 schema and can be
            serialised with :func:`json.dumps`.
        """
        rules = self._build_rules()
        results = self._build_results(report, workflow_file)

        return {
            "$schema": self.SARIF_SCHEMA,
            "version": self.SARIF_VERSION,
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": self.TOOL_NAME,
                            "version": self.TOOL_VERSION,
                            "informationUri": "https://pisama.dev",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }

    # ------------------------------------------------------------------
    # Rule construction
    # ------------------------------------------------------------------

    def _build_rules(self) -> List[Dict[str, Any]]:
        """Build the SARIF rules array from the global error code registry."""
        rules: List[Dict[str, Any]] = []
        for ec in ERROR_CODES.values():
            rules.append(
                {
                    "id": ec.code,
                    "name": ec.code.replace("-", "_"),
                    "shortDescription": {"text": ec.description},
                    "fullDescription": {"text": ec.remediation},
                    "defaultConfiguration": {
                        "level": _SEVERITY_TO_SARIF_LEVEL.get(ec.severity, "warning"),
                    },
                    "helpUri": ec.doc_link or None,
                    "properties": {
                        "dimension": ec.dimension,
                        "severity": ec.severity,
                    },
                }
            )
        return rules

    # ------------------------------------------------------------------
    # Result construction
    # ------------------------------------------------------------------

    def _build_results(
        self,
        report: "QualityReport",
        workflow_file: str,
    ) -> List[Dict[str, Any]]:
        """Convert quality issues into SARIF result objects."""
        results: List[Dict[str, Any]] = []

        # Agent-level issues
        for agent_score in report.agent_scores:
            for dim in agent_score.dimensions:
                if not dim.issues:
                    continue
                dim_codes = get_codes_for_dimension(dim.dimension)
                for idx, issue_text in enumerate(dim.issues):
                    # Pick the most relevant error code for this issue
                    rule_id = dim_codes[idx].code if idx < len(dim_codes) else (
                        dim_codes[0].code if dim_codes else f"QE-UNKNOWN-{idx:03d}"
                    )
                    ec = ERROR_CODES.get(rule_id)
                    level = _SEVERITY_TO_SARIF_LEVEL.get(
                        ec.severity if ec else "medium", "warning"
                    )
                    results.append(
                        self._make_result(
                            rule_id=rule_id,
                            level=level,
                            message=issue_text,
                            workflow_file=workflow_file,
                            target_name=agent_score.agent_name,
                            scope="agent",
                        )
                    )

        # Orchestration-level issues
        for dim in report.orchestration_score.dimensions:
            if not dim.issues:
                continue
            dim_codes = get_codes_for_dimension(dim.dimension)
            for idx, issue_text in enumerate(dim.issues):
                rule_id = dim_codes[idx].code if idx < len(dim_codes) else (
                    dim_codes[0].code if dim_codes else f"QE-UNKNOWN-{idx:03d}"
                )
                ec = ERROR_CODES.get(rule_id)
                level = _SEVERITY_TO_SARIF_LEVEL.get(
                    ec.severity if ec else "medium", "warning"
                )
                results.append(
                    self._make_result(
                        rule_id=rule_id,
                        level=level,
                        message=issue_text,
                        workflow_file=workflow_file,
                        target_name=report.workflow_name,
                        scope="orchestration",
                    )
                )

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_result(
        rule_id: str,
        level: str,
        message: str,
        workflow_file: str,
        target_name: str,
        scope: str,
    ) -> Dict[str, Any]:
        """Build a single SARIF result object."""
        return {
            "ruleId": rule_id,
            "level": level,
            "message": {"text": message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": workflow_file,
                        },
                        "region": {
                            "startLine": 1,
                            "startColumn": 1,
                        },
                    }
                }
            ],
            "properties": {
                "target": target_name,
                "scope": scope,
            },
        }
