"""Tests for QualityFixApplicator and its 15 strategy classes."""

import copy
import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality.healing.applicator import QualityFixApplicator
from app.enterprise.quality.healing.models import (
    QualityFixSuggestion,
    QualityFixCategory,
    QualityAppliedFix,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_workflow(nodes=None, connections=None, settings=None):
    return {
        "id": "test-wf",
        "name": "Test Workflow",
        "nodes": nodes or [],
        "connections": connections or {},
        "settings": settings or {},
    }


def make_agent_node(node_id="agent-1", name="Test Agent", system_message="You are a helper."):
    return {
        "id": node_id,
        "name": name,
        "type": "@n8n/n8n-nodes-langchain.agent",
        "parameters": {"systemMessage": system_message},
        "position": [0, 0],
    }


def make_code_node(node_id="code-1", name="Code", position=None):
    return {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": "return items;"},
        "position": position or [200, 0],
    }


def make_set_node(node_id="set-1", name="Set", position=None):
    return {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.set",
        "parameters": {},
        "position": position or [400, 0],
    }


def make_disabled_node(node_id="disabled-1", name="Old Node"):
    return {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.set",
        "parameters": {},
        "position": [600, 0],
        "disabled": True,
    }


def make_fix(
    category,
    changes,
    dimension="role_clarity",
    target_type="agent",
    target_id="agent-1",
    title="Test Fix",
    description="A test fix.",
    confidence=0.9,
    expected_improvement=0.1,
):
    return QualityFixSuggestion.create(
        dimension=dimension,
        category=category,
        title=title,
        description=description,
        confidence=confidence,
        expected_improvement=expected_improvement,
        target_type=target_type,
        target_id=target_id,
        changes=changes,
    )


# ---------------------------------------------------------------------------
# TestQualityFixApplicator — general behaviour
# ---------------------------------------------------------------------------

class TestQualityFixApplicator:
    """General tests for the QualityFixApplicator."""

    def test_apply_returns_applied_fix(self):
        """apply() should return a QualityAppliedFix instance."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])
        fix = make_fix(
            category=QualityFixCategory.ROLE_CLARITY,
            changes={
                "action": "modify_parameter",
                "node_id": "agent-1",
                "parameter": "systemMessage",
                "value": "You are a senior analyst.",
                "mode": "set",
            },
        )

        result = applicator.apply(fix, wf)

        assert isinstance(result, QualityAppliedFix)
        assert result.fix_id == fix.id
        assert result.dimension == "role_clarity"
        assert result.rollback_available is True

    def test_apply_preserves_original_state(self):
        """original_state in the result must be a deep copy of the input config."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])
        original_nodes_copy = copy.deepcopy(wf["nodes"])

        fix = make_fix(
            category=QualityFixCategory.ROLE_CLARITY,
            changes={
                "action": "modify_parameter",
                "node_id": "agent-1",
                "parameter": "systemMessage",
                "value": "New prompt.",
                "mode": "set",
            },
        )

        result = applicator.apply(fix, wf)

        # original_state should match what we started with
        assert result.original_state["nodes"] == original_nodes_copy
        # modified_state should differ
        assert result.modified_state != result.original_state
        # Mutating original_state should not affect modified_state
        result.original_state["nodes"].append({"id": "injected"})
        assert len(result.modified_state["nodes"]) == 1

    def test_rollback_restores_original(self):
        """rollback() should return a copy identical to the original state."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])
        original_copy = copy.deepcopy(wf)

        fix = make_fix(
            category=QualityFixCategory.ROLE_CLARITY,
            changes={
                "action": "modify_parameter",
                "node_id": "agent-1",
                "parameter": "systemMessage",
                "value": "New prompt.",
                "mode": "set",
            },
        )

        applied = applicator.apply(fix, wf)
        rolled_back = applicator.rollback(applied)

        assert rolled_back == original_copy

    def test_unknown_category_raises(self):
        """Using a category with no registered strategy should raise ValueError."""
        applicator = QualityFixApplicator()
        # Clear strategies so nothing matches
        applicator._strategies.clear()

        wf = make_workflow(nodes=[make_agent_node()])
        fix = make_fix(
            category=QualityFixCategory.ROLE_CLARITY,
            changes={"action": "modify_parameter"},
        )

        with pytest.raises(ValueError, match="No applicator strategy"):
            applicator.apply(fix, wf)

    def test_all_15_categories_have_strategies(self):
        """Every QualityFixCategory member should have a registered strategy."""
        applicator = QualityFixApplicator()

        for cat in QualityFixCategory:
            assert cat in applicator._strategies, (
                f"Missing strategy for {cat.value}"
            )

    def test_apply_does_not_mutate_input(self):
        """The original workflow dict passed to apply() must not be mutated."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])
        wf_snapshot = copy.deepcopy(wf)

        fix = make_fix(
            category=QualityFixCategory.ROLE_CLARITY,
            changes={
                "action": "modify_parameter",
                "node_id": "agent-1",
                "parameter": "systemMessage",
                "value": "Changed.",
                "mode": "set",
            },
        )

        applicator.apply(fix, wf)

        assert wf == wf_snapshot, "apply() mutated the input workflow config"

    def test_rollback_not_available_raises(self):
        """Attempting rollback when rollback_available is False should raise."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])

        fix = make_fix(
            category=QualityFixCategory.ROLE_CLARITY,
            changes={
                "action": "modify_parameter",
                "node_id": "agent-1",
                "parameter": "systemMessage",
                "value": "x",
                "mode": "set",
            },
        )

        applied = applicator.apply(fix, wf)
        applied.rollback_available = False

        with pytest.raises(ValueError, match="Rollback not available"):
            applicator.rollback(applied)


# ---------------------------------------------------------------------------
# TestRoleClarityApplicator
# ---------------------------------------------------------------------------

class TestRoleClarityApplicator:
    """Tests for the RoleClarityApplicator strategy."""

    def test_modify_parameter_prepend(self):
        """Prepend mode should insert text before the existing systemMessage."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node(system_message="Existing prompt.")])

        fix = make_fix(
            category=QualityFixCategory.ROLE_CLARITY,
            changes={
                "action": "modify_parameter",
                "node_id": "agent-1",
                "parameter": "systemMessage",
                "value": "You are a senior analyst.",
                "mode": "prepend",
            },
        )

        result = applicator.apply(fix, wf)
        agent_node = result.modified_state["nodes"][0]

        assert agent_node["parameters"]["systemMessage"].startswith(
            "You are a senior analyst."
        )
        assert "Existing prompt." in agent_node["parameters"]["systemMessage"]

    def test_modify_parameter_append(self):
        """Append mode should add text after the existing systemMessage."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node(system_message="Existing prompt.")])

        fix = make_fix(
            category=QualityFixCategory.ROLE_CLARITY,
            changes={
                "action": "modify_parameter",
                "node_id": "agent-1",
                "parameter": "systemMessage",
                "value": "Always respond in JSON.",
                "mode": "append",
            },
        )

        result = applicator.apply(fix, wf)
        agent_node = result.modified_state["nodes"][0]

        assert agent_node["parameters"]["systemMessage"].endswith(
            "Always respond in JSON."
        )
        assert "Existing prompt." in agent_node["parameters"]["systemMessage"]

    def test_modify_parameter_set(self):
        """Set mode should replace the systemMessage entirely."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node(system_message="Old.")])

        fix = make_fix(
            category=QualityFixCategory.ROLE_CLARITY,
            changes={
                "action": "modify_parameter",
                "node_id": "agent-1",
                "parameter": "systemMessage",
                "value": "Completely new.",
                "mode": "set",
            },
        )

        result = applicator.apply(fix, wf)
        agent_node = result.modified_state["nodes"][0]

        assert agent_node["parameters"]["systemMessage"] == "Completely new."

    def test_modify_parameter_prepend_on_empty(self):
        """Prepend on a node with no systemMessage should set the value directly."""
        applicator = QualityFixApplicator()
        node = make_agent_node(system_message="")
        node["parameters"]["systemMessage"] = ""
        wf = make_workflow(nodes=[node])

        fix = make_fix(
            category=QualityFixCategory.ROLE_CLARITY,
            changes={
                "action": "modify_parameter",
                "node_id": "agent-1",
                "parameter": "systemMessage",
                "value": "You are X.",
                "mode": "prepend",
            },
        )

        result = applicator.apply(fix, wf)
        msg = result.modified_state["nodes"][0]["parameters"]["systemMessage"]

        assert msg == "You are X."

    def test_node_not_found_returns_unchanged(self):
        """If the target node_id does not exist, config should be returned unchanged."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node(node_id="agent-1")])

        fix = make_fix(
            category=QualityFixCategory.ROLE_CLARITY,
            changes={
                "action": "modify_parameter",
                "node_id": "nonexistent",
                "parameter": "systemMessage",
                "value": "x",
                "mode": "set",
            },
        )

        result = applicator.apply(fix, wf)

        # Config should be unchanged aside from deep-copy identity
        assert result.modified_state["nodes"][0]["parameters"]["systemMessage"] == "You are a helper."


# ---------------------------------------------------------------------------
# TestErrorHandlingApplicator
# ---------------------------------------------------------------------------

class TestErrorHandlingApplicator:
    """Tests for the ErrorHandlingApplicator strategy."""

    def test_modify_settings_continue_on_fail(self):
        """Setting continueOnFail=true should appear in node.settings."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])

        fix = make_fix(
            category=QualityFixCategory.ERROR_HANDLING,
            dimension="error_handling",
            changes={
                "action": "modify_settings",
                "node_id": "agent-1",
                "settings": {"continueOnFail": True},
            },
        )

        result = applicator.apply(fix, wf)
        node = result.modified_state["nodes"][0]

        assert node["settings"]["continueOnFail"] is True

    def test_modify_options_timeout(self):
        """Setting a timeout via modify_options should appear in node.parameters.options."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])

        fix = make_fix(
            category=QualityFixCategory.ERROR_HANDLING,
            dimension="error_handling",
            changes={
                "action": "modify_options",
                "node_id": "agent-1",
                "options": {"timeout": 30000},
            },
        )

        result = applicator.apply(fix, wf)
        node = result.modified_state["nodes"][0]

        assert node["parameters"]["options"]["timeout"] == 30000

    def test_modify_settings_retry(self):
        """Setting retry parameters should appear in node.settings."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])

        fix = make_fix(
            category=QualityFixCategory.ERROR_HANDLING,
            dimension="error_handling",
            changes={
                "action": "modify_settings",
                "node_id": "agent-1",
                "settings": {
                    "retryOnFail": True,
                    "maxRetries": 3,
                    "retryInterval": 1000,
                },
            },
        )

        result = applicator.apply(fix, wf)
        settings = result.modified_state["nodes"][0]["settings"]

        assert settings["retryOnFail"] is True
        assert settings["maxRetries"] == 3
        assert settings["retryInterval"] == 1000


# ---------------------------------------------------------------------------
# TestObservabilityApplicator
# ---------------------------------------------------------------------------

class TestObservabilityApplicator:
    """Tests for the ObservabilityApplicator strategy."""

    def test_add_node(self):
        """add_node action should append a new node to the workflow."""
        applicator = QualityFixApplicator()
        agent = make_agent_node()
        wf = make_workflow(nodes=[agent])

        fix = make_fix(
            category=QualityFixCategory.OBSERVABILITY,
            dimension="observability",
            target_type="orchestration",
            changes={
                "action": "add_node",
                "new_node": {
                    "name": "Checkpoint Logger",
                    "type": "n8n-nodes-base.set",
                    "parameters": {"mode": "manual"},
                },
            },
        )

        result = applicator.apply(fix, wf)
        nodes = result.modified_state["nodes"]

        assert len(nodes) == 2
        added = nodes[1]
        assert added["name"] == "Checkpoint Logger"
        assert added["type"] == "n8n-nodes-base.set"
        assert "id" in added

    def test_add_node_with_connection(self):
        """add_node with connect_after should wire the node into the workflow."""
        applicator = QualityFixApplicator()
        agent = make_agent_node()
        wf = make_workflow(nodes=[agent])

        fix = make_fix(
            category=QualityFixCategory.OBSERVABILITY,
            dimension="observability",
            target_type="orchestration",
            changes={
                "action": "add_node",
                "new_node": {
                    "name": "Error Logger",
                    "type": "n8n-nodes-base.set",
                },
                "connect_after": "Test Agent",
            },
        )

        result = applicator.apply(fix, wf)
        connections = result.modified_state["connections"]

        assert "Test Agent" in connections
        targets = connections["Test Agent"]["main"][0]
        assert any(c["node"] == "Error Logger" for c in targets)


# ---------------------------------------------------------------------------
# TestBestPracticesApplicator
# ---------------------------------------------------------------------------

class TestBestPracticesApplicator:
    """Tests for the BestPracticesApplicator strategy."""

    def test_set_workflow_setting(self):
        """set_workflow_setting action should update workflow.settings."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])

        fix = make_fix(
            category=QualityFixCategory.BEST_PRACTICES,
            dimension="best_practices",
            target_type="orchestration",
            changes={
                "action": "set_workflow_setting",
                "settings": {"executionTimeout": 300},
            },
        )

        result = applicator.apply(fix, wf)

        assert result.modified_state["settings"]["executionTimeout"] == 300

    def test_standardize_settings(self):
        """standardize_settings should apply defaults to all matching agent nodes."""
        applicator = QualityFixApplicator()
        agent1 = make_agent_node(node_id="a1", name="Agent 1")
        agent2 = make_agent_node(node_id="a2", name="Agent 2")
        non_agent = make_set_node()
        wf = make_workflow(nodes=[agent1, agent2, non_agent])

        fix = make_fix(
            category=QualityFixCategory.BEST_PRACTICES,
            dimension="best_practices",
            target_type="orchestration",
            changes={
                "action": "standardize_settings",
                "standard_settings": {
                    "retryOnFail": True,
                    "maxRetries": 2,
                },
            },
        )

        result = applicator.apply(fix, wf)
        nodes = result.modified_state["nodes"]

        # Both agent nodes should get the standard settings
        for node in nodes:
            if node["type"] == "@n8n/n8n-nodes-langchain.agent":
                assert node["settings"]["retryOnFail"] is True
                assert node["settings"]["maxRetries"] == 2

        # The set node should NOT get settings added
        set_node = [n for n in nodes if n["type"] == "n8n-nodes-base.set"][0]
        assert "retryOnFail" not in set_node.get("settings", {})

    def test_standardize_preserves_existing_settings(self):
        """standardize_settings should not overwrite existing node settings."""
        applicator = QualityFixApplicator()
        agent = make_agent_node()
        agent["settings"] = {"maxRetries": 5}
        wf = make_workflow(nodes=[agent])

        fix = make_fix(
            category=QualityFixCategory.BEST_PRACTICES,
            dimension="best_practices",
            target_type="orchestration",
            changes={
                "action": "standardize_settings",
                "standard_settings": {
                    "maxRetries": 2,
                    "retryOnFail": True,
                },
            },
        )

        result = applicator.apply(fix, wf)
        node = result.modified_state["nodes"][0]

        # Existing value should be preserved
        assert node["settings"]["maxRetries"] == 5
        # Missing value should be added
        assert node["settings"]["retryOnFail"] is True


# ---------------------------------------------------------------------------
# TestMaintenanceQualityApplicator
# ---------------------------------------------------------------------------

class TestMaintenanceQualityApplicator:
    """Tests for the MaintenanceQualityApplicator strategy."""

    def test_remove_disabled_nodes(self):
        """remove_nodes action should remove nodes by id."""
        applicator = QualityFixApplicator()
        agent = make_agent_node()
        disabled = make_disabled_node()
        wf = make_workflow(nodes=[agent, disabled])

        fix = make_fix(
            category=QualityFixCategory.MAINTENANCE_QUALITY,
            dimension="maintenance_quality",
            target_type="orchestration",
            changes={
                "action": "remove_nodes",
                "node_ids": ["disabled-1"],
            },
        )

        result = applicator.apply(fix, wf)
        nodes = result.modified_state["nodes"]

        assert len(nodes) == 1
        assert nodes[0]["id"] == "agent-1"

    def test_remove_nodes_cleans_connections(self):
        """Removing a node should also clean up connections referencing it."""
        applicator = QualityFixApplicator()
        agent = make_agent_node()
        disabled = make_disabled_node(node_id="Old Node", name="Old Node")
        wf = make_workflow(
            nodes=[agent, disabled],
            connections={
                "Test Agent": {
                    "main": [[{"node": "Old Node", "type": "main", "index": 0}]]
                }
            },
        )

        fix = make_fix(
            category=QualityFixCategory.MAINTENANCE_QUALITY,
            dimension="maintenance_quality",
            target_type="orchestration",
            changes={
                "action": "remove_nodes",
                "node_ids": ["Old Node"],
            },
        )

        result = applicator.apply(fix, wf)
        connections = result.modified_state["connections"]

        # Connection from Test Agent should have Old Node removed from targets
        targets = connections.get("Test Agent", {}).get("main", [[]])[0]
        assert all(c["node"] != "Old Node" for c in targets)

    def test_update_versions(self):
        """update_versions should bump typeVersion for matching node types."""
        applicator = QualityFixApplicator()
        node = make_code_node()
        node["typeVersion"] = 1
        wf = make_workflow(nodes=[node])

        fix = make_fix(
            category=QualityFixCategory.MAINTENANCE_QUALITY,
            dimension="maintenance_quality",
            target_type="orchestration",
            changes={
                "action": "update_versions",
                "version_map": {"n8n-nodes-base.code": 2},
            },
        )

        result = applicator.apply(fix, wf)

        assert result.modified_state["nodes"][0]["typeVersion"] == 2


# ---------------------------------------------------------------------------
# TestLayoutQualityApplicator
# ---------------------------------------------------------------------------

class TestLayoutQualityApplicator:
    """Tests for the LayoutQualityApplicator strategy."""

    def test_reorganize_layout(self):
        """reorganize_layout should reposition overlapping nodes to a grid."""
        applicator = QualityFixApplicator()
        # Three nodes at overlapping positions
        nodes = [
            make_agent_node(node_id="a1", name="A1"),
            make_code_node(node_id="c1", name="C1", position=[0, 0]),
            make_set_node(node_id="s1", name="S1", position=[0, 0]),
        ]
        wf = make_workflow(nodes=nodes)

        fix = make_fix(
            category=QualityFixCategory.LAYOUT_QUALITY,
            dimension="layout_quality",
            target_type="orchestration",
            changes={
                "action": "reorganize_layout",
                "grid_spacing_x": 250,
                "grid_spacing_y": 150,
                "start_x": 250,
                "start_y": 300,
                "columns": 4,
            },
        )

        result = applicator.apply(fix, wf)
        positions = [n["position"] for n in result.modified_state["nodes"]]

        # All positions should now be distinct
        assert len(set(tuple(p) for p in positions)) == 3

        # First node at (250, 300), second at (500, 300), third at (750, 300)
        assert positions[0] == [250, 300]
        assert positions[1] == [500, 300]
        assert positions[2] == [750, 300]

    def test_reorganize_layout_dict_positions(self):
        """reorganize_layout should handle dict-format positions."""
        applicator = QualityFixApplicator()
        node = make_agent_node()
        node["position"] = {"x": 0, "y": 0}
        wf = make_workflow(nodes=[node])

        fix = make_fix(
            category=QualityFixCategory.LAYOUT_QUALITY,
            dimension="layout_quality",
            target_type="orchestration",
            changes={"action": "reorganize_layout"},
        )

        result = applicator.apply(fix, wf)
        pos = result.modified_state["nodes"][0]["position"]

        # dict format should be preserved
        assert isinstance(pos, dict)
        assert "x" in pos and "y" in pos


# ---------------------------------------------------------------------------
# TestDocumentationQualityApplicator
# ---------------------------------------------------------------------------

class TestDocumentationQualityApplicator:
    """Tests for the DocumentationQualityApplicator strategy."""

    def test_add_sticky_note(self):
        """add_node action should add a sticky note node to the workflow."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])

        fix = make_fix(
            category=QualityFixCategory.DOCUMENTATION_QUALITY,
            dimension="documentation_quality",
            target_type="orchestration",
            changes={
                "action": "add_node",
                "new_node": {
                    "name": "Workflow Documentation",
                    "parameters": {
                        "content": "This workflow processes customer support tickets.",
                        "width": 300,
                        "height": 160,
                    },
                },
            },
        )

        result = applicator.apply(fix, wf)
        nodes = result.modified_state["nodes"]

        assert len(nodes) == 2
        sticky = nodes[1]
        assert sticky["name"] == "Workflow Documentation"
        assert sticky["type"] == "n8n-nodes-base.stickyNote"
        assert "content" in sticky["parameters"]

    def test_set_workflow_description(self):
        """set_workflow_setting should add a description to workflow settings."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])

        fix = make_fix(
            category=QualityFixCategory.DOCUMENTATION_QUALITY,
            dimension="documentation_quality",
            target_type="orchestration",
            changes={
                "action": "set_workflow_setting",
                "settings": {"description": "Customer support automation workflow."},
            },
        )

        result = applicator.apply(fix, wf)

        assert result.modified_state["settings"]["description"] == "Customer support automation workflow."


# ---------------------------------------------------------------------------
# TestDataFlowClarityApplicator
# ---------------------------------------------------------------------------

class TestDataFlowClarityApplicator:
    """Tests for the DataFlowClarityApplicator strategy."""

    def test_rename_nodes(self):
        """rename_nodes action should rename generic node names to descriptive ones."""
        applicator = QualityFixApplicator()
        code_node = make_code_node(node_id="code-1", name="Code")
        agent = make_agent_node()
        wf = make_workflow(
            nodes=[agent, code_node],
            connections={
                "Test Agent": {
                    "main": [[{"node": "Code", "type": "main", "index": 0}]]
                }
            },
        )

        fix = make_fix(
            category=QualityFixCategory.DATA_FLOW_CLARITY,
            dimension="data_flow_clarity",
            target_type="orchestration",
            changes={
                "action": "rename_nodes",
                "renames": {"Code": "Parse Response"},
            },
        )

        result = applicator.apply(fix, wf)
        nodes = result.modified_state["nodes"]
        connections = result.modified_state["connections"]

        # Node should be renamed
        renamed = [n for n in nodes if n["id"] == "code-1"][0]
        assert renamed["name"] == "Parse Response"

        # Connections should reference new name
        targets = connections["Test Agent"]["main"][0]
        assert targets[0]["node"] == "Parse Response"

    def test_rename_updates_connection_source_keys(self):
        """rename_nodes should update connection source keys when a source node is renamed."""
        applicator = QualityFixApplicator()
        code_node = make_code_node(node_id="code-1", name="Code")
        set_node = make_set_node(node_id="set-1", name="Set")
        wf = make_workflow(
            nodes=[code_node, set_node],
            connections={
                "Code": {
                    "main": [[{"node": "Set", "type": "main", "index": 0}]]
                }
            },
        )

        fix = make_fix(
            category=QualityFixCategory.DATA_FLOW_CLARITY,
            dimension="data_flow_clarity",
            target_type="orchestration",
            changes={
                "action": "rename_nodes",
                "renames": {"Code": "Parse Response"},
            },
        )

        result = applicator.apply(fix, wf)
        connections = result.modified_state["connections"]

        # Old key should be gone, new key should be present
        assert "Code" not in connections
        assert "Parse Response" in connections


# ---------------------------------------------------------------------------
# TestOutputConsistencyApplicator
# ---------------------------------------------------------------------------

class TestOutputConsistencyApplicator:
    """Tests for the OutputConsistencyApplicator strategy."""

    def test_append_output_format_instruction(self):
        """modify_parameter with append should add output format guidance."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node(system_message="You are an analyst.")])

        fix = make_fix(
            category=QualityFixCategory.OUTPUT_CONSISTENCY,
            dimension="output_consistency",
            changes={
                "action": "modify_parameter",
                "node_id": "agent-1",
                "parameter": "systemMessage",
                "value": "Always respond with valid JSON.",
                "mode": "append",
            },
        )

        result = applicator.apply(fix, wf)
        msg = result.modified_state["nodes"][0]["parameters"]["systemMessage"]

        assert msg.endswith("Always respond with valid JSON.")
        assert "You are an analyst." in msg

    def test_add_validation_node_after(self):
        """add_node_after should insert a validation node after the target."""
        applicator = QualityFixApplicator()
        agent = make_agent_node()
        wf = make_workflow(nodes=[agent])

        fix = make_fix(
            category=QualityFixCategory.OUTPUT_CONSISTENCY,
            dimension="output_consistency",
            changes={
                "action": "add_node_after",
                "node_id": "agent-1",
                "new_node": {
                    "name": "Validate Output",
                    "type": "n8n-nodes-base.code",
                    "parameters": {"jsCode": "// validate"},
                },
            },
        )

        result = applicator.apply(fix, wf)
        nodes = result.modified_state["nodes"]

        assert len(nodes) == 2
        assert nodes[1]["name"] == "Validate Output"


# ---------------------------------------------------------------------------
# TestToolUsageApplicator
# ---------------------------------------------------------------------------

class TestToolUsageApplicator:
    """Tests for the ToolUsageApplicator strategy."""

    def test_modify_tool_descriptions(self):
        """modify_tools should update tool descriptions on agent nodes."""
        applicator = QualityFixApplicator()
        agent = make_agent_node()
        agent["parameters"]["tools"] = [
            {"name": "search", "description": ""},
            {"name": "calculator", "description": "Calc"},
        ]
        wf = make_workflow(nodes=[agent])

        fix = make_fix(
            category=QualityFixCategory.TOOL_USAGE,
            dimension="tool_usage",
            changes={
                "action": "modify_tools",
                "node_id": "agent-1",
                "tool_updates": {
                    "search": {"description": "Search the web for current information."},
                },
            },
        )

        result = applicator.apply(fix, wf)
        tools = result.modified_state["nodes"][0]["parameters"]["tools"]
        search_tool = [t for t in tools if t["name"] == "search"][0]

        assert search_tool["description"] == "Search the web for current information."


# ---------------------------------------------------------------------------
# TestConfigAppropriatenessApplicator
# ---------------------------------------------------------------------------

class TestConfigAppropriatenessApplicator:
    """Tests for the ConfigAppropriatenessApplicator strategy."""

    def test_modify_temperature(self):
        """Should update temperature in node options."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])

        fix = make_fix(
            category=QualityFixCategory.CONFIG_APPROPRIATENESS,
            dimension="config_appropriateness",
            changes={
                "action": "modify_options",
                "node_id": "agent-1",
                "options": {"temperature": 0.2},
            },
        )

        result = applicator.apply(fix, wf)
        options = result.modified_state["nodes"][0]["parameters"]["options"]

        assert options["temperature"] == 0.2


# ---------------------------------------------------------------------------
# TestComplexityManagementApplicator
# ---------------------------------------------------------------------------

class TestComplexityManagementApplicator:
    """Tests for the ComplexityManagementApplicator strategy."""

    def test_suggest_extraction_adds_sticky(self):
        """suggest_extraction should add a sticky note with suggestions."""
        applicator = QualityFixApplicator()
        wf = make_workflow(nodes=[make_agent_node()])

        fix = make_fix(
            category=QualityFixCategory.COMPLEXITY_MANAGEMENT,
            dimension="complexity_management",
            target_type="orchestration",
            changes={
                "action": "suggest_extraction",
                "note": "Consider extracting the validation logic into a sub-workflow.",
            },
        )

        result = applicator.apply(fix, wf)
        nodes = result.modified_state["nodes"]

        assert len(nodes) == 2
        sticky = nodes[1]
        assert sticky["type"] == "n8n-nodes-base.stickyNote"
        assert "extracting" in sticky["parameters"]["content"]


# ---------------------------------------------------------------------------
# TestAgentCouplingApplicator
# ---------------------------------------------------------------------------

class TestAgentCouplingApplicator:
    """Tests for the AgentCouplingApplicator strategy."""

    def test_add_checkpoint_between_agents(self):
        """add_node_between should insert a checkpoint Set node between two agents."""
        applicator = QualityFixApplicator()
        agent1 = make_agent_node(node_id="a1", name="Agent A")
        agent2 = make_agent_node(node_id="a2", name="Agent B")
        agent2["position"] = [400, 0]
        wf = make_workflow(
            nodes=[agent1, agent2],
            connections={
                "Agent A": {
                    "main": [[{"node": "Agent B", "type": "main", "index": 0}]]
                }
            },
        )

        fix = make_fix(
            category=QualityFixCategory.AGENT_COUPLING,
            dimension="agent_coupling",
            target_type="orchestration",
            changes={
                "action": "add_node_between",
                "from_node": "Agent A",
                "to_node": "Agent B",
                "checkpoint_name": "Checkpoint A-B",
            },
        )

        result = applicator.apply(fix, wf)
        nodes = result.modified_state["nodes"]
        connections = result.modified_state["connections"]

        # Should have 3 nodes now
        assert len(nodes) == 3
        checkpoint = [n for n in nodes if n["name"] == "Checkpoint A-B"][0]
        assert checkpoint["type"] == "n8n-nodes-base.set"

        # Checkpoint should connect to Agent B
        assert "Checkpoint A-B" in connections
        targets = connections["Checkpoint A-B"]["main"][0]
        assert targets[0]["node"] == "Agent B"


# ---------------------------------------------------------------------------
# TestAIArchitectureApplicator
# ---------------------------------------------------------------------------

class TestAIArchitectureApplicator:
    """Tests for the AIArchitectureApplicator strategy."""

    def test_add_validation_node_after_agent(self):
        """add_node_after should add a Code validation node after the target agent."""
        applicator = QualityFixApplicator()
        agent = make_agent_node()
        wf = make_workflow(nodes=[agent])

        fix = make_fix(
            category=QualityFixCategory.AI_ARCHITECTURE,
            dimension="ai_architecture",
            target_type="orchestration",
            changes={
                "action": "add_node_after",
                "node_id": "agent-1",
                "new_node": {
                    "name": "Validate AI Output",
                    "type": "n8n-nodes-base.code",
                    "parameters": {"jsCode": "// validate AI response"},
                },
            },
        )

        result = applicator.apply(fix, wf)
        nodes = result.modified_state["nodes"]
        connections = result.modified_state["connections"]

        assert len(nodes) == 2
        assert nodes[1]["name"] == "Validate AI Output"

        # Should be wired from the agent
        assert "Test Agent" in connections
        targets = connections["Test Agent"]["main"][0]
        assert any(c["node"] == "Validate AI Output" for c in targets)


# ---------------------------------------------------------------------------
# TestTestCoverageApplicator
# ---------------------------------------------------------------------------

class TestTestCoverageApplicator:
    """Tests for the TestCoverageApplicator strategy."""

    def test_add_pin_data(self):
        """add_pin_data should add pinData entries to the workflow."""
        applicator = QualityFixApplicator()
        agent = make_agent_node()
        wf = make_workflow(nodes=[agent])

        fix = make_fix(
            category=QualityFixCategory.TEST_COVERAGE,
            dimension="test_coverage",
            target_type="orchestration",
            changes={
                "action": "add_pin_data",
                "pin_data": {
                    "agent-1": [{"json": {"input": "test", "expected": "result"}}],
                },
            },
        )

        result = applicator.apply(fix, wf)
        pin_data = result.modified_state.get("pinData", {})

        assert "Test Agent" in pin_data
        assert pin_data["Test Agent"][0]["json"]["input"] == "test"
