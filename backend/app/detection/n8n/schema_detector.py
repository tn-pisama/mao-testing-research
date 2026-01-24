"""
F12: Schema Mismatch Detection for n8n Workflows
=================================================

Detects schema mismatches between consecutive n8n nodes where:
- Node A outputs JSON with certain structure
- Node B expects JSON with different structure
- Leading to data loss, errors, or undefined behavior

This is n8n-specific because schema flow is explicit in workflow automation,
unlike conversational agents where data flow is implicit.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set

from app.detection.turn_aware._base import (
    TurnSnapshot,
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
)

logger = logging.getLogger(__name__)


class N8NSchemaDetector(TurnAwareDetector):
    """Detects F12: Output Validation Failure / Schema Mismatch in n8n workflows.

    Analyzes workflow execution for:
    1. Missing required fields in node outputs
    2. Type mismatches between producer and consumer nodes
    3. Schema drift over workflow execution
    4. Undefined field access in downstream nodes

    n8n-specific manifestation of F12 (Output Validation Failure):
    In conversational agents, this is about validating LLM outputs.
    In n8n workflows, this is about JSON schema compatibility between nodes.
    """

    name = "N8NSchemaDetector"
    version = "1.0"
    supported_failure_modes = ["F12"]

    def __init__(
        self,
        strict_mode: bool = False,
        required_field_threshold: float = 0.5,
    ):
        """Initialize schema detector.

        Args:
            strict_mode: If True, flag any schema differences (not just breaking ones)
            required_field_threshold: Fraction of fields that must match (0.5 = 50%)
        """
        self.strict_mode = strict_mode
        self.required_field_threshold = required_field_threshold

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect schema mismatches between consecutive n8n nodes."""
        if len(turns) < 2:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Need at least 2 nodes to check schema compatibility",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        for i in range(len(turns) - 1):
            producer = turns[i]
            consumer = turns[i + 1]

            # Extract schemas from content
            producer_schema = self._extract_schema(producer.content)
            consumer_expected = self._infer_expected_schema(consumer)

            if producer_schema and consumer_expected:
                mismatch = self._check_schema_mismatch(
                    producer_schema,
                    consumer_expected,
                    producer.participant_id,
                    consumer.participant_id,
                )
                if mismatch:
                    issues.append(mismatch)
                    affected_turns.extend([producer.turn_number, consumer.turn_number])

            # Check for error indicators in content
            error_indicators = self._detect_schema_errors(consumer.content)
            if error_indicators:
                issues.append({
                    "type": "schema_error",
                    "producer": producer.participant_id,
                    "consumer": consumer.participant_id,
                    "errors": error_indicators,
                    "description": f"Schema-related errors detected in {consumer.participant_id}",
                })
                affected_turns.extend([producer.turn_number, consumer.turn_number])

        # Check for progressive schema drift
        drift = self._detect_schema_drift(turns)
        if drift["detected"]:
            issues.append(drift)
            affected_turns.extend(drift.get("turns", []))

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.85,
                failure_mode=None,
                explanation="No schema mismatches detected between nodes",
                detector_name=self.name,
            )

        # Determine severity
        error_count = sum(1 for i in issues if i.get("type") == "schema_error")
        mismatch_count = sum(1 for i in issues if i.get("type") in ("field_mismatch", "type_mismatch"))

        if error_count >= 2 or mismatch_count >= 3:
            severity = TurnAwareSeverity.SEVERE
        elif error_count >= 1 or mismatch_count >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.95, 0.6 + len(issues) * 0.1)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F12",
            explanation=f"Schema mismatch: {len(issues)} incompatibilities found between nodes",
            affected_turns=list(set(affected_turns)),
            evidence={
                "issues": issues,
                "total_transitions": len(turns) - 1,
            },
            suggested_fix=(
                "Ensure consistent JSON schemas between connected nodes. "
                "Add schema validation nodes or transform nodes to handle type mismatches. "
                "Use n8n's Expression Editor to properly map fields."
            ),
            detector_name=self.name,
        )

    def _extract_schema(self, content: str) -> Optional[Dict[str, str]]:
        """Extract JSON schema (field names and types) from node output.

        Returns dict mapping field name to type string.
        """
        content = content.strip()

        # Try to parse as JSON
        if content.startswith('{') or content.startswith('['):
            try:
                data = json.loads(content)
                return self._schema_from_data(data)
            except json.JSONDecodeError:
                pass

        # Try to extract from key: value format (from _clean_n8n_content)
        schema = {}
        for line in content.split('\n'):
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    schema[key] = self._infer_type(value)

        return schema if schema else None

    def _schema_from_data(self, data: Any, prefix: str = "") -> Dict[str, str]:
        """Convert JSON data to schema (field -> type mapping)."""
        schema = {}

        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key
                schema[full_key] = self._type_name(value)

                # Recurse into nested objects (one level only)
                if isinstance(value, dict) and not prefix:
                    nested = self._schema_from_data(value, full_key)
                    schema.update(nested)

        elif isinstance(data, list) and data:
            # Get schema from first element
            schema[prefix or "[]"] = f"array<{self._type_name(data[0])}>"
            if isinstance(data[0], dict) and not prefix:
                nested = self._schema_from_data(data[0], prefix or "[]")
                schema.update(nested)

        return schema

    def _type_name(self, value: Any) -> str:
        """Get type name for a value."""
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "unknown"

    def _infer_type(self, value_str: str) -> str:
        """Infer type from string representation."""
        value_str = value_str.strip()

        if value_str.lower() in ('null', 'none', ''):
            return "null"
        elif value_str.lower() in ('true', 'false'):
            return "boolean"
        elif value_str.startswith('{'):
            return "object"
        elif value_str.startswith('['):
            return "array"
        else:
            try:
                int(value_str)
                return "integer"
            except ValueError:
                pass
            try:
                float(value_str)
                return "number"
            except ValueError:
                pass
        return "string"

    def _infer_expected_schema(self, consumer: TurnSnapshot) -> Optional[Dict[str, str]]:
        """Infer expected input schema for a consumer node based on its behavior.

        This is heuristic-based since we don't have the actual n8n workflow definition.
        """
        node_name = consumer.participant_id.lower()
        content = consumer.content.lower()

        # Common node types and their expected inputs
        if any(x in node_name for x in ['email', 'mail', 'send']):
            return {"to": "string", "subject": "string", "body": "string"}
        elif any(x in node_name for x in ['http', 'request', 'api']):
            return {"url": "string"}
        elif any(x in node_name for x in ['slack', 'discord', 'teams']):
            return {"channel": "string", "message": "string"}
        elif any(x in node_name for x in ['database', 'db', 'postgres', 'mysql']):
            return {"query": "string"}

        # Check content for field access patterns like $json.fieldName
        accessed_fields = set()
        import re
        for match in re.finditer(r'\$json\.([a-zA-Z_][a-zA-Z0-9_]*)', content):
            accessed_fields.add(match.group(1))

        if accessed_fields:
            return {field: "any" for field in accessed_fields}

        return None

    def _check_schema_mismatch(
        self,
        producer_schema: Dict[str, str],
        expected_schema: Dict[str, str],
        producer_name: str,
        consumer_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Check if producer output matches consumer expectations."""
        missing_fields = []
        type_mismatches = []

        for field, expected_type in expected_schema.items():
            if field not in producer_schema:
                missing_fields.append(field)
            elif expected_type != "any" and producer_schema[field] != expected_type:
                type_mismatches.append({
                    "field": field,
                    "expected": expected_type,
                    "actual": producer_schema[field],
                })

        # Calculate compatibility score
        total_expected = len(expected_schema)
        matched = total_expected - len(missing_fields) - len(type_mismatches)
        compatibility = matched / total_expected if total_expected > 0 else 1.0

        if missing_fields or type_mismatches:
            if compatibility < self.required_field_threshold or self.strict_mode:
                return {
                    "type": "field_mismatch" if missing_fields else "type_mismatch",
                    "producer": producer_name,
                    "consumer": consumer_name,
                    "missing_fields": missing_fields,
                    "type_mismatches": type_mismatches,
                    "compatibility": compatibility,
                    "description": (
                        f"Schema incompatibility: {producer_name} -> {consumer_name}. "
                        f"Missing: {missing_fields}, Type mismatches: {len(type_mismatches)}"
                    ),
                }

        return None

    def _detect_schema_errors(self, content: str) -> List[str]:
        """Detect error patterns indicating schema issues."""
        errors = []
        content_lower = content.lower()

        error_patterns = [
            ("undefined", "Accessing undefined field"),
            ("cannot read property", "Property access on null/undefined"),
            ("is not defined", "Reference error on undefined field"),
            ("expected string", "Type mismatch - expected string"),
            ("expected number", "Type mismatch - expected number"),
            ("expected array", "Type mismatch - expected array"),
            ("expected object", "Type mismatch - expected object"),
            ("invalid json", "JSON parsing error"),
            ("null reference", "Null pointer/reference"),
            ("field not found", "Missing field in input"),
            ("required field", "Required field missing"),
        ]

        for pattern, description in error_patterns:
            if pattern in content_lower:
                errors.append(description)

        return errors

    def _detect_schema_drift(self, turns: List[TurnSnapshot]) -> Dict[str, Any]:
        """Detect progressive schema drift over workflow execution.

        Schema drift occurs when the JSON structure changes incrementally
        through the workflow, losing or transforming fields.
        """
        if len(turns) < 3:
            return {"detected": False}

        # Track field presence across turns
        all_fields: Set[str] = set()
        field_presence: List[Set[str]] = []

        for turn in turns:
            schema = self._extract_schema(turn.content)
            if schema:
                fields = set(schema.keys())
                all_fields.update(fields)
                field_presence.append(fields)

        if len(field_presence) < 3:
            return {"detected": False}

        # Check for monotonically decreasing field count (data loss)
        lost_fields = []
        for i in range(1, len(field_presence)):
            lost = field_presence[i - 1] - field_presence[i]
            if lost:
                lost_fields.extend(lost)

        # Significant drift if we lost >30% of original fields
        if len(lost_fields) >= len(all_fields) * 0.3:
            return {
                "detected": True,
                "type": "schema_drift",
                "lost_fields": list(set(lost_fields)),
                "original_field_count": len(all_fields),
                "final_field_count": len(field_presence[-1]) if field_presence else 0,
                "turns": [t.turn_number for t in turns],
                "description": f"Schema drift: lost {len(set(lost_fields))} fields over workflow execution",
            }

        return {"detected": False}
