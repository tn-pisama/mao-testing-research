"""Applicator that applies quality fixes to workflow configurations."""

from abc import ABC, abstractmethod
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
import copy
import secrets

from .models import QualityFixSuggestion, QualityFixCategory, QualityAppliedFix


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_node(config: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    """Find a node in the workflow config by id or name."""
    for node in config.get("nodes", []):
        if node.get("id") == node_id or node.get("name") == node_id:
            return node
    return None


def _next_position(config: Dict[str, Any], offset_x: int = 0, offset_y: int = 200) -> Dict[str, int]:
    """Calculate the next available position below existing nodes."""
    nodes = config.get("nodes", [])
    if not nodes:
        return {"x": 250, "y": 300}

    max_y = max(
        (n.get("position", [0, 0])[1] if isinstance(n.get("position"), list)
         else n.get("position", {}).get("y", 0))
        for n in nodes
    )
    avg_x = sum(
        (n.get("position", [0, 0])[0] if isinstance(n.get("position"), list)
         else n.get("position", {}).get("x", 0))
        for n in nodes
    ) // max(len(nodes), 1)

    return {"x": avg_x + offset_x, "y": max_y + offset_y}


def _make_node_id() -> str:
    """Generate a unique node id."""
    return secrets.token_hex(8)


def _node_position_tuple(node: Dict[str, Any]) -> tuple:
    """Return (x, y) tuple regardless of position format."""
    pos = node.get("position", [0, 0])
    if isinstance(pos, list):
        return (pos[0], pos[1])
    return (pos.get("x", 0), pos.get("y", 0))


# ---------------------------------------------------------------------------
# Base strategy
# ---------------------------------------------------------------------------

class QualityApplicatorStrategy(ABC):
    """Base strategy for applying quality fixes to workflow config."""

    @abstractmethod
    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the fix to a workflow configuration. Returns modified config."""
        pass


# ---------------------------------------------------------------------------
# Agent dimension strategies
# ---------------------------------------------------------------------------

class RoleClarityApplicator(QualityApplicatorStrategy):
    """Modifies node parameters.systemMessage for role clarity fixes."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "modify_parameter")

        if action == "modify_parameter":
            node = _find_node(config, changes.get("node_id", fix.target_id))
            if not node:
                return config

            params = node.setdefault("parameters", {})
            param_name = changes.get("parameter", "systemMessage")

            # Backward compat: detect legacy "prepend"/"append" key format
            if "prepend" in changes and "mode" not in changes:
                mode = "prepend"
                value = changes["prepend"]
            elif "append" in changes and "mode" not in changes:
                mode = "append"
                value = changes["append"]
            else:
                value = changes.get("value", "")
                mode = changes.get("mode", "set")

            current = params.get(param_name, "")
            if mode == "prepend":
                params[param_name] = value + "\n" + current if current else value
            elif mode == "append":
                params[param_name] = current + "\n" + value if current else value
            else:  # set
                params[param_name] = value

        return config


class OutputConsistencyApplicator(QualityApplicatorStrategy):
    """Adds output schema enforcement or validation nodes."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "modify_parameter")

        if action == "modify_parameter":
            node = _find_node(config, changes.get("node_id", fix.target_id))
            if not node:
                return config
            params = node.setdefault("parameters", {})
            param_name = changes.get("parameter", "systemMessage")

            # Backward compat: detect legacy "prepend"/"append" key format
            if "prepend" in changes and "mode" not in changes:
                mode = "prepend"
                value = changes["prepend"]
            elif "append" in changes and "mode" not in changes:
                mode = "append"
                value = changes["append"]
            else:
                value = changes.get("value", "")
                mode = changes.get("mode", "append")

            current = params.get(param_name, "")
            if mode == "prepend":
                params[param_name] = value + "\n" + current if current else value
            elif mode == "append":
                params[param_name] = current + "\n" + value if current else value
            else:
                params[param_name] = value

        elif action == "add_node_after":
            target_node = _find_node(config, changes.get("node_id", fix.target_id))
            if not target_node:
                return config

            new_node = changes.get("new_node", {})
            new_node_id = new_node.get("id", _make_node_id())
            new_node.setdefault("id", new_node_id)
            new_node.setdefault("name", f"Validate Output {new_node_id[:6]}")
            new_node.setdefault("type", "n8n-nodes-base.code")
            new_node.setdefault("typeVersion", 1)

            pos = _node_position_tuple(target_node)
            new_node.setdefault("position", [pos[0] + 200, pos[1]])

            config.setdefault("nodes", []).append(new_node)

            # Add connection from target to new node
            from_name = target_node.get("name", "")
            connections = config.setdefault("connections", {})
            if from_name not in connections:
                connections[from_name] = {"main": [[]]}
            main = connections[from_name].setdefault("main", [[]])
            if not main:
                main.append([])
            main[0].append({
                "node": new_node["name"],
                "type": "main",
                "index": 0,
            })

        return config


class ErrorHandlingApplicator(QualityApplicatorStrategy):
    """Modifies node settings for error handling (retry, timeout, continueOnFail)."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "modify_settings")

        if action == "modify_settings":
            node = _find_node(config, changes.get("node_id", fix.target_id))
            if not node:
                return config
            settings = node.setdefault("settings", {})
            for key, value in changes.get("settings", {}).items():
                settings[key] = value

        elif action == "modify_options":
            node = _find_node(config, changes.get("node_id", fix.target_id))
            if not node:
                return config
            options = node.setdefault("parameters", {}).setdefault("options", {})
            for key, value in changes.get("options", {}).items():
                options[key] = value

        return config


class ToolUsageApplicator(QualityApplicatorStrategy):
    """Modifies tool definitions and descriptions on agent nodes."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "modify_tools")

        if action == "modify_tools":
            node = _find_node(config, changes.get("node_id", fix.target_id))
            if not node:
                return config

            params = node.setdefault("parameters", {})
            tools = params.get("tools", [])

            tool_updates = changes.get("tool_updates", {})
            for tool in tools:
                tool_name = tool.get("name", "")
                if tool_name in tool_updates:
                    for key, value in tool_updates[tool_name].items():
                        tool[key] = value

            # Also allow replacing the entire tools list
            if "tools_replacement" in changes:
                params["tools"] = changes["tools_replacement"]

        return config


class ConfigAppropriatenessApplicator(QualityApplicatorStrategy):
    """Modifies model configuration options (temperature, maxTokens, model)."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "modify_options")

        if action == "modify_options":
            node = _find_node(config, changes.get("node_id", fix.target_id))
            if not node:
                return config

            options = node.setdefault("parameters", {}).setdefault("options", {})
            for key, value in changes.get("options", {}).items():
                options[key] = value

        return config


# ---------------------------------------------------------------------------
# Orchestration dimension strategies
# ---------------------------------------------------------------------------

class DataFlowClarityApplicator(QualityApplicatorStrategy):
    """Renames nodes or adds explicit data mapping Set nodes."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "rename_nodes")

        if action == "rename_nodes":
            rename_map = changes.get("renames", {})
            connections = config.get("connections", {})

            for node in config.get("nodes", []):
                old_name = node.get("name", "")
                if old_name in rename_map:
                    new_name = rename_map[old_name]
                    node["name"] = new_name

                    # Update connections referencing old name
                    if old_name in connections:
                        connections[new_name] = connections.pop(old_name)
                    for _src, conn_data in connections.items():
                        for output_group in conn_data.get("main", []):
                            for conn in output_group:
                                if conn.get("node") == old_name:
                                    conn["node"] = new_name

        elif action == "add_expression_mappings":
            # Add Set nodes for explicit data flow between agents
            mappings = changes.get("mappings", [])
            for mapping in mappings:
                set_node = {
                    "id": _make_node_id(),
                    "name": mapping.get("name", f"Map Data {_make_node_id()[:4]}"),
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 3,
                    "position": mapping.get("position", list(_next_position(config).values())),
                    "parameters": {
                        "mode": "manual",
                        "assignments": mapping.get("assignments", []),
                    },
                }
                config.setdefault("nodes", []).append(set_node)

        return config


class ComplexityManagementApplicator(QualityApplicatorStrategy):
    """Advisory-only: adds sticky notes with extraction suggestions."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "suggest_extraction")

        if action == "suggest_extraction":
            pos = _next_position(config, offset_x=-200)
            sticky = {
                "id": _make_node_id(),
                "name": f"Complexity Note {_make_node_id()[:4]}",
                "type": "n8n-nodes-base.stickyNote",
                "typeVersion": 1,
                "position": [pos["x"], pos["y"]],
                "parameters": {
                    "content": changes.get(
                        "note",
                        f"Suggestion: {fix.description}",
                    ),
                    "width": 300,
                    "height": 160,
                },
            }
            config.setdefault("nodes", []).append(sticky)

        return config


class AgentCouplingApplicator(QualityApplicatorStrategy):
    """Inserts checkpoint Set nodes between tightly coupled agent chains."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "add_node_between")

        if action == "add_node_between":
            from_name = changes.get("from_node")
            to_name = changes.get("to_node")
            if not from_name or not to_name:
                return config

            from_node = _find_node(config, from_name)
            to_node = _find_node(config, to_name)
            if not from_node or not to_node:
                return config

            from_pos = _node_position_tuple(from_node)
            to_pos = _node_position_tuple(to_node)
            mid_x = (from_pos[0] + to_pos[0]) // 2
            mid_y = (from_pos[1] + to_pos[1]) // 2

            checkpoint_name = changes.get(
                "checkpoint_name",
                f"Checkpoint {from_name[:8]}-{to_name[:8]}",
            )
            checkpoint = {
                "id": _make_node_id(),
                "name": checkpoint_name,
                "type": "n8n-nodes-base.set",
                "typeVersion": 3,
                "position": [mid_x, mid_y],
                "parameters": {
                    "mode": "manual",
                    "assignments": changes.get("assignments", []),
                },
            }
            config.setdefault("nodes", []).append(checkpoint)

            # Re-wire: from_node -> checkpoint -> to_node
            connections = config.setdefault("connections", {})
            from_node_name = from_node.get("name", from_name)

            # Remove direct from -> to connection
            if from_node_name in connections:
                for output_group in connections[from_node_name].get("main", []):
                    connections[from_node_name]["main"] = [
                        [c for c in group if c.get("node") != to_node.get("name", to_name)]
                        for group in connections[from_node_name].get("main", [])
                    ]
                    break

            # Add from -> checkpoint
            if from_node_name not in connections:
                connections[from_node_name] = {"main": [[]]}
            main = connections[from_node_name].setdefault("main", [[]])
            if not main:
                main.append([])
            main[0].append({
                "node": checkpoint_name,
                "type": "main",
                "index": 0,
            })

            # Add checkpoint -> to
            connections[checkpoint_name] = {
                "main": [[{"node": to_node.get("name", to_name), "type": "main", "index": 0}]]
            }

        return config


class ObservabilityApplicator(QualityApplicatorStrategy):
    """Adds observability nodes (checkpoints, error triggers, webhooks)."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "add_node")

        if action == "add_node":
            new_node = changes.get("new_node", {})
            new_node.setdefault("id", _make_node_id())
            new_node.setdefault("typeVersion", 1)

            if "position" not in new_node:
                pos = _next_position(config)
                new_node["position"] = [pos["x"], pos["y"]]

            config.setdefault("nodes", []).append(new_node)

            # Optionally wire the node
            connect_after = changes.get("connect_after")

            # Auto-detect connection point if not specified
            if not connect_after:
                ai_types = [
                    "@n8n/n8n-nodes-langchain.agent",
                    "@n8n/n8n-nodes-langchain.chainLlm",
                    "n8n-nodes-base.openAi",
                    "@n8n/n8n-nodes-langchain.lmChatOpenAi",
                    "@n8n/n8n-nodes-langchain.lmChatAnthropic",
                ]
                for node in reversed(config.get("nodes", [])):
                    if node.get("type") in ai_types:
                        connect_after = node.get("name")
                        break
                # Fallback: connect after the last node
                if not connect_after and config.get("nodes"):
                    connect_after = config["nodes"][-1].get("name")

            if connect_after:
                from_name = connect_after
                connections = config.setdefault("connections", {})
                if from_name not in connections:
                    connections[from_name] = {"main": [[]]}
                main = connections[from_name].setdefault("main", [[]])
                if not main:
                    main.append([])
                main[0].append({
                    "node": new_node["name"],
                    "type": "main",
                    "index": 0,
                })

        return config


class BestPracticesApplicator(QualityApplicatorStrategy):
    """Modifies workflow-level settings or standardises agent node settings."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "set_workflow_setting")

        if action == "set_workflow_setting":
            settings = config.setdefault("settings", {})
            for key, value in changes.get("settings", {}).items():
                settings[key] = value

        elif action == "standardize_settings":
            standard_settings = changes.get("standard_settings", {})
            agent_types = changes.get("agent_types", [
                "@n8n/n8n-nodes-langchain.agent",
                "@n8n/n8n-nodes-langchain.chainLlm",
                "@n8n/n8n-nodes-langchain.openAi",
            ])
            for node in config.get("nodes", []):
                if node.get("type") in agent_types:
                    node_settings = node.setdefault("settings", {})
                    for key, value in standard_settings.items():
                        if key not in node_settings:
                            node_settings[key] = value

        return config


class DocumentationQualityApplicator(QualityApplicatorStrategy):
    """Sets workflow description or adds sticky note documentation."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "set_workflow_setting")

        if action == "set_workflow_setting":
            settings = config.setdefault("settings", {})
            for key, value in changes.get("settings", {}).items():
                settings[key] = value

        elif action == "add_node":
            sticky = changes.get("new_node", {})
            sticky.setdefault("id", _make_node_id())
            sticky.setdefault("type", "n8n-nodes-base.stickyNote")
            sticky.setdefault("typeVersion", 1)

            if "position" not in sticky:
                pos = _next_position(config, offset_x=-300)
                sticky["position"] = [pos["x"], pos["y"]]

            config.setdefault("nodes", []).append(sticky)

        return config


class AIArchitectureApplicator(QualityApplicatorStrategy):
    """Adds validation Code nodes after AI agent nodes."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "add_node_after")

        if action == "add_node_after":
            target_node = _find_node(config, changes.get("node_id", fix.target_id))
            if not target_node:
                return config

            new_node = changes.get("new_node", {})
            new_node_id = new_node.get("id", _make_node_id())
            new_node.setdefault("id", new_node_id)
            new_node.setdefault("name", f"Validate AI {new_node_id[:6]}")
            new_node.setdefault("type", "n8n-nodes-base.code")
            new_node.setdefault("typeVersion", 1)

            pos = _node_position_tuple(target_node)
            new_node.setdefault("position", [pos[0] + 250, pos[1]])

            config.setdefault("nodes", []).append(new_node)

            # Wire target -> validation node
            target_name = target_node.get("name", "")
            new_name = new_node.get("name", "")
            connections = config.setdefault("connections", {})
            conn = connections.setdefault(target_name, {"main": [[]]})
            conn["main"][0].append({"node": new_name, "type": "main", "index": 0})

        elif action == "add_ai_connection":
            from_name = changes.get("from_node")
            to_name = changes.get("to_node")
            output_type = changes.get("output_type", "ai_outputParser")
            if from_name and to_name:
                connections = config.setdefault("connections", {})
                conn = connections.setdefault(from_name, {})
                ai_outputs = conn.setdefault(output_type, [[]])
                ai_outputs[0].append({"node": to_name, "type": output_type, "index": 0})

        return config


class MaintenanceQualityApplicator(QualityApplicatorStrategy):
    """Removes disabled nodes or updates outdated type versions."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "remove_nodes")

        if action == "remove_nodes":
            remove_ids = set(changes.get("node_ids", []))
            if remove_ids:
                config["nodes"] = [
                    n for n in config.get("nodes", [])
                    if n.get("id") not in remove_ids and n.get("name") not in remove_ids
                ]
                # Clean up connections referencing removed nodes
                removed_names = remove_ids
                connections = config.get("connections", {})
                for src in list(connections.keys()):
                    if src in removed_names:
                        del connections[src]
                        continue
                    for output_group in connections[src].get("main", []):
                        connections[src]["main"] = [
                            [c for c in group if c.get("node") not in removed_names]
                            for group in connections[src].get("main", [])
                        ]

        elif action == "update_versions":
            version_map = changes.get("version_map", {})
            for node in config.get("nodes", []):
                node_type = node.get("type", "")
                if node_type in version_map:
                    node["typeVersion"] = version_map[node_type]

        return config


class TestCoverageApplicator(QualityApplicatorStrategy):
    """Adds pinData to nodes for testing."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "add_pin_data")

        if action == "add_pin_data":
            pin_data_entries = changes.get("pin_data", {})
            workflow_pin_data = config.setdefault("pinData", {})

            for node_name, data in pin_data_entries.items():
                node = _find_node(config, node_name)
                if node:
                    actual_name = node.get("name", node_name)
                    workflow_pin_data[actual_name] = data

        return config


class LayoutQualityApplicator(QualityApplicatorStrategy):
    """Reorganises node positions for grid alignment."""

    def apply(self, fix: QualityFixSuggestion, config: Dict[str, Any]) -> Dict[str, Any]:
        changes = fix.changes
        action = changes.get("action", "reorganize_layout")

        if action == "reorganize_layout":
            grid_spacing_x = changes.get("grid_spacing_x", 250)
            grid_spacing_y = changes.get("grid_spacing_y", 150)
            start_x = changes.get("start_x", 250)
            start_y = changes.get("start_y", 300)
            columns = changes.get("columns", 4)

            nodes = config.get("nodes", [])
            for idx, node in enumerate(nodes):
                col = idx % columns
                row = idx // columns
                new_x = start_x + col * grid_spacing_x
                new_y = start_y + row * grid_spacing_y

                # Preserve position format
                if isinstance(node.get("position"), dict):
                    node["position"] = {"x": new_x, "y": new_y}
                else:
                    node["position"] = [new_x, new_y]

        return config


# ---------------------------------------------------------------------------
# Main applicator
# ---------------------------------------------------------------------------

class QualityFixApplicator:
    """Applies quality fix suggestions to workflow configurations."""

    def __init__(self):
        self._strategies: Dict[QualityFixCategory, QualityApplicatorStrategy] = {}
        self._register_default_strategies()

    def _register_default_strategies(self):
        # Agent dimension strategies
        self._strategies[QualityFixCategory.ROLE_CLARITY] = RoleClarityApplicator()
        self._strategies[QualityFixCategory.OUTPUT_CONSISTENCY] = OutputConsistencyApplicator()
        self._strategies[QualityFixCategory.ERROR_HANDLING] = ErrorHandlingApplicator()
        self._strategies[QualityFixCategory.TOOL_USAGE] = ToolUsageApplicator()
        self._strategies[QualityFixCategory.CONFIG_APPROPRIATENESS] = ConfigAppropriatenessApplicator()
        # Orchestration dimension strategies
        self._strategies[QualityFixCategory.DATA_FLOW_CLARITY] = DataFlowClarityApplicator()
        self._strategies[QualityFixCategory.COMPLEXITY_MANAGEMENT] = ComplexityManagementApplicator()
        self._strategies[QualityFixCategory.AGENT_COUPLING] = AgentCouplingApplicator()
        self._strategies[QualityFixCategory.OBSERVABILITY] = ObservabilityApplicator()
        self._strategies[QualityFixCategory.BEST_PRACTICES] = BestPracticesApplicator()
        self._strategies[QualityFixCategory.DOCUMENTATION_QUALITY] = DocumentationQualityApplicator()
        self._strategies[QualityFixCategory.AI_ARCHITECTURE] = AIArchitectureApplicator()
        self._strategies[QualityFixCategory.MAINTENANCE_QUALITY] = MaintenanceQualityApplicator()
        self._strategies[QualityFixCategory.TEST_COVERAGE] = TestCoverageApplicator()
        self._strategies[QualityFixCategory.LAYOUT_QUALITY] = LayoutQualityApplicator()

    def apply(
        self,
        fix_suggestion: QualityFixSuggestion,
        workflow_config: Dict[str, Any],
    ) -> QualityAppliedFix:
        """Apply a single fix suggestion to the workflow config."""
        strategy = self._strategies.get(fix_suggestion.category)
        if not strategy:
            raise ValueError(f"No applicator strategy for {fix_suggestion.category}")

        original_state = copy.deepcopy(workflow_config)
        modified_config = strategy.apply(fix_suggestion, copy.deepcopy(workflow_config))

        return QualityAppliedFix(
            fix_id=fix_suggestion.id,
            dimension=fix_suggestion.dimension,
            applied_at=datetime.now(UTC),
            target_component=fix_suggestion.target_id,
            original_state=original_state,
            modified_state=modified_config,
            rollback_available=True,
        )

    def rollback(self, applied_fix: QualityAppliedFix) -> Dict[str, Any]:
        """Rollback an applied fix by returning the original state."""
        if not applied_fix.rollback_available:
            raise ValueError("Rollback not available for this fix")
        return copy.deepcopy(applied_fix.original_state)
