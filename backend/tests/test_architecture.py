"""Architecture dependency validation tests.

Ensures module layers respect dependency direction rules,
following harness engineering principles (OpenAI Codex pattern).

Layer hierarchy (imports must flow downward only):

    detection/  ->  detection_enterprise/  ->  enterprise/quality/healing/
      (core)         (calibration/ML)          (healing pipeline)

Running:
    pytest backend/tests/test_architecture.py -v
"""

import ast
import os
import pytest
from pathlib import Path

BACKEND_ROOT = Path(__file__).parent.parent / "app"

# Files allowed to break layer rules (test harnesses that bridge layers by design)
ALLOWED_EXCEPTIONS = {
    "detection": {
        "golden_test_harness.py",  # Test harness bridges detection ↔ detection_enterprise
    },
}

# Layer rules: {directory_prefix: [forbidden_import_prefixes]}
DEPENDENCY_RULES = {
    "detection": [
        "app.detection_enterprise",
        "app.enterprise",
        "app.healing",
        "app.api",
    ],
    "detection_enterprise": [
        "app.enterprise.quality.healing",
        "app.api",
    ],
    "fixes": [
        "app.api",
    ],
}


def _extract_imports(filepath: Path) -> list[str]:
    """Extract all import module paths from a Python file using AST.

    Parses the file into an AST and walks all nodes to collect
    Import and ImportFrom module strings. Files with syntax errors
    are silently skipped (returns empty list).
    """
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _find_violations(
    layer: str, forbidden_prefixes: list[str]
) -> list[tuple[str, str, str]]:
    """Find forbidden imports in a module layer.

    Scans all .py files under the layer directory and checks each
    import against the forbidden prefix list.

    Returns:
        List of (relative_file_path, import_path, violated_rule) tuples.
    """
    layer_dir = BACKEND_ROOT / layer
    if not layer_dir.exists():
        return []

    exceptions = ALLOWED_EXCEPTIONS.get(layer, set())
    violations = []
    for py_file in sorted(layer_dir.rglob("*.py")):
        if py_file.name in exceptions:
            continue
        rel_path = str(py_file.relative_to(BACKEND_ROOT.parent))
        imports = _extract_imports(py_file)
        for imp in imports:
            for forbidden in forbidden_prefixes:
                if imp.startswith(forbidden):
                    violations.append((rel_path, imp, forbidden))
    return violations


class TestArchitectureDependencies:
    """Validate that module layers respect dependency direction rules."""

    @pytest.mark.parametrize("layer,forbidden", DEPENDENCY_RULES.items())
    def test_no_forbidden_imports(self, layer, forbidden):
        """Layer should not import from forbidden modules."""
        violations = _find_violations(layer, forbidden)
        if violations:
            msg = f"Forbidden imports in '{layer}/' layer:\n"
            for file, imp, rule in violations:
                msg += f"  {file}: imports '{imp}' (violates rule: no {rule})\n"
            pytest.fail(msg)

    def test_detection_core_is_self_contained(self):
        """Core detection modules should only import from stdlib, detection, and third-party.

        This is a softer structural check: detection/ is allowed to reference
        other app.detection.* submodules (itself), but should not reach into
        enterprise, healing, or api layers.
        """
        layer_dir = BACKEND_ROOT / "detection"
        if not layer_dir.exists():
            pytest.skip("detection/ directory not found")

        internal_deps = set()
        for py_file in sorted(layer_dir.rglob("*.py")):
            for imp in _extract_imports(py_file):
                if imp.startswith("app.") and not imp.startswith("app.detection"):
                    internal_deps.add(imp)

        # Filter to only the hard-forbidden prefixes
        hard_forbidden_prefixes = ["app.enterprise", "app.healing", "app.api"]
        actual_violations = {
            d
            for d in internal_deps
            if any(d.startswith(p) for p in hard_forbidden_prefixes)
        }

        assert not actual_violations, (
            f"detection/ has forbidden cross-layer imports: {sorted(actual_violations)}"
        )
