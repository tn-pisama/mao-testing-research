"""Dataset loading fixtures: golden traces, archived traces, MAST, n8n workflows."""

import pytest


@pytest.fixture
def n8n_workflow_files():
    """Load all 4 n8n workflow JSON files from _archived/demo-agent/n8n-workflows/."""
    import json
    from pathlib import Path

    base_path = Path(__file__).parent.parent.parent / "_archived" / "demo-agent" / "n8n-workflows"

    workflows = {}
    for filename in ["research-assistant-normal.json", "research-loop-buggy.json",
                     "research-corruption.json", "research-drift.json"]:
        filepath = base_path / filename
        if filepath.exists():
            with open(filepath) as f:
                workflows[filename.replace(".json", "")] = json.load(f)

    return workflows


@pytest.fixture
def golden_traces():
    """Load golden_traces.jsonl (420 traces)."""
    import json
    from pathlib import Path

    filepath = Path(__file__).parent.parent / "fixtures" / "golden" / "golden_traces.jsonl"

    traces = []
    if filepath.exists():
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    traces.append(json.loads(line))

    return traces


@pytest.fixture
def golden_traces_by_type(golden_traces):
    """Group golden traces by detection type."""
    by_type = {}

    for trace in golden_traces:
        # Detection type is nested in _golden_metadata
        metadata = trace.get("_golden_metadata", {})
        detection_type = metadata.get("detection_type", "unknown")

        if detection_type not in by_type:
            by_type[detection_type] = []
        by_type[detection_type].append(trace)

    return by_type


@pytest.fixture
def archived_traces():
    """Load 4,142 archived traces from all_traces.jsonl."""
    import json
    from pathlib import Path

    filepath = Path(__file__).parent.parent.parent / "_archived" / "traces" / "all_traces.jsonl"

    traces = []
    if filepath.exists():
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    traces.append(json.loads(line))

    return traces


@pytest.fixture
def archived_traces_by_framework(archived_traces):
    """Group archived traces by framework (langchain, autogen, crewai, etc.)."""
    by_framework = {}

    for trace in archived_traces:
        framework = trace.get("framework", "unknown")
        if framework not in by_framework:
            by_framework[framework] = []
        by_framework[framework].append(trace)

    return by_framework


@pytest.fixture
def mast_traces():
    """Load 10 MAST benchmark traces with F1-F14 labels."""
    import json
    from pathlib import Path

    filepath = Path(__file__).parent.parent / "fixtures" / "mast" / "sample_mast.jsonl"

    traces = []
    if filepath.exists():
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    traces.append(json.loads(line))

    return traces


@pytest.fixture
def external_n8n_workflows():
    """Load external n8n workflow templates (sample of 100)."""
    import json
    from pathlib import Path

    base = Path(__file__).parent.parent / "fixtures" / "external" / "n8n"
    workflows = []

    if not base.exists():
        return workflows

    for repo in ["zengfr-templates", "ai-templates"]:
        repo_path = base / repo
        if repo_path.exists():
            for json_file in repo_path.rglob("*.json"):
                if len(workflows) >= 100:
                    break
                try:
                    workflows.append(json.loads(json_file.read_text()))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Skip invalid JSON files
                    continue

    return workflows
