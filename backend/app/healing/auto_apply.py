"""Auto-apply service for hands-off self-healing.

Provides rate-limited automatic fix application with safety controls
for solo developers running n8n workflows.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict

from .models import HealingResult, AppliedFix, FixRiskLevel, get_fix_risk_level

logger = logging.getLogger(__name__)


@dataclass
class AutoApplyConfig:
    """Configuration for auto-apply behavior."""
    enabled: bool = True
    max_fixes_per_hour: int = 5
    require_git_backup: bool = True
    rollback_on_failure: bool = True
    cooldown_after_rollback_seconds: int = 300  # 5 min cooldown after rollback
    max_consecutive_failures: int = 3
    # Healing loop detection: halt after this many healings in the time window
    healing_loop_threshold: int = 5
    healing_loop_window_minutes: int = 60
    # Risk-based auto-apply control
    auto_apply_max_risk: FixRiskLevel = FixRiskLevel.MEDIUM


@dataclass
class ApplyResult:
    """Result of an auto-apply operation."""
    success: bool
    healing_id: str
    workflow_id: str
    fix_id: Optional[str] = None
    backup_commit_sha: Optional[str] = None
    error: Optional[str] = None
    applied_at: Optional[datetime] = None
    rolled_back: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "healing_id": self.healing_id,
            "workflow_id": self.workflow_id,
            "fix_id": self.fix_id,
            "backup_commit_sha": self.backup_commit_sha,
            "error": self.error,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "rolled_back": self.rolled_back,
        }


class RateLimiter:
    """Simple in-memory rate limiter for fix applications."""

    def __init__(self, max_per_hour: int = 5):
        self.max_per_hour = max_per_hour
        self._timestamps: Dict[str, List[datetime]] = defaultdict(list)

    def check(self, key: str) -> bool:
        """Check if an action is allowed under the rate limit."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)

        # Clean old timestamps
        self._timestamps[key] = [
            ts for ts in self._timestamps[key] if ts > cutoff
        ]

        return len(self._timestamps[key]) < self.max_per_hour

    def record(self, key: str) -> None:
        """Record that an action was taken."""
        self._timestamps[key].append(datetime.now(timezone.utc))

    def remaining(self, key: str) -> int:
        """Get remaining actions allowed in the current hour."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)
        self._timestamps[key] = [
            ts for ts in self._timestamps[key] if ts > cutoff
        ]
        return max(0, self.max_per_hour - len(self._timestamps[key]))

    def reset_time(self, key: str) -> Optional[datetime]:
        """Get when the rate limit will reset (oldest timestamp expires)."""
        if not self._timestamps[key]:
            return None
        return min(self._timestamps[key]) + timedelta(hours=1)


class AutoApplyService:
    """
    Service for automatically applying fixes to n8n workflows.

    Features:
    - Rate limiting per workflow to prevent fix storms
    - Git backup integration before applying fixes
    - Automatic rollback on validation failure
    - Cooldown period after failures

    Usage:
        config = AutoApplyConfig(max_fixes_per_hour=5)
        service = AutoApplyService(config)

        result = await service.apply_fix(
            fix=fix_suggestion,
            workflow_id="workflow_123",
            n8n_api=n8n_client,
            git_backup=git_service,
        )
    """

    def __init__(self, config: Optional[AutoApplyConfig] = None):
        self.config = config or AutoApplyConfig()
        self._rate_limiter = RateLimiter(self.config.max_fixes_per_hour)
        self._failure_counts: Dict[str, int] = defaultdict(int)
        self._cooldowns: Dict[str, datetime] = {}
        self._apply_history: List[ApplyResult] = []
        # Track healing attempts per workflow for loop detection
        self._healing_timestamps: Dict[str, List[datetime]] = defaultdict(list)

    def check_rate_limit(self, workflow_id: str) -> bool:
        """Check if we can apply a fix to this workflow."""
        if not self.config.enabled:
            return False

        # Check cooldown
        if workflow_id in self._cooldowns:
            if datetime.now(timezone.utc) < self._cooldowns[workflow_id]:
                logger.info(f"Workflow {workflow_id} is in cooldown until {self._cooldowns[workflow_id]}")
                return False
            else:
                del self._cooldowns[workflow_id]

        # Check consecutive failures
        if self._failure_counts[workflow_id] >= self.config.max_consecutive_failures:
            logger.warning(f"Workflow {workflow_id} has too many consecutive failures")
            return False

        # Check healing loop
        if self.detect_healing_loop(workflow_id):
            logger.warning(
                f"Healing loop detected for workflow {workflow_id}: "
                f">{self.config.healing_loop_threshold} healings in "
                f"{self.config.healing_loop_window_minutes} minutes. "
                "Auto-apply halted — escalate to human."
            )
            return False

        # Check rate limit
        return self._rate_limiter.check(workflow_id)

    def detect_healing_loop(self, workflow_id: str) -> bool:
        """Detect if a workflow is being healed too frequently.

        Returns True if the number of healing attempts in the configured
        time window exceeds the threshold, indicating a healing loop.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self.config.healing_loop_window_minutes)

        # Clean old timestamps
        self._healing_timestamps[workflow_id] = [
            ts for ts in self._healing_timestamps[workflow_id] if ts > cutoff
        ]

        return len(self._healing_timestamps[workflow_id]) >= self.config.healing_loop_threshold

    def check_fix_risk(self, fix_type: str) -> Optional[str]:
        """Check if a fix type is allowed under the current risk policy.

        Returns None if allowed, or an error message if blocked.
        """
        risk = get_fix_risk_level(fix_type)
        max_risk = self.config.auto_apply_max_risk

        risk_order = {FixRiskLevel.SAFE: 0, FixRiskLevel.MEDIUM: 1, FixRiskLevel.DANGEROUS: 2}
        if risk_order[risk] > risk_order[max_risk]:
            return (
                f"Fix type '{fix_type}' has risk level '{risk.value}' which exceeds "
                f"auto-apply maximum '{max_risk.value}'. Manual approval required."
            )
        return None

    async def apply_fix(
        self,
        fix: Dict[str, Any],
        workflow_id: str,
        healing_id: str,
        n8n_client: Any,
        git_backup: Optional[Any] = None,
    ) -> ApplyResult:
        """
        Apply a fix to an n8n workflow.

        Args:
            fix: The fix suggestion to apply
            workflow_id: n8n workflow ID
            healing_id: ID of the healing operation
            n8n_client: n8n API client for applying changes
            git_backup: Optional GitBackupService for backup

        Returns:
            ApplyResult with success status and details
        """
        result = ApplyResult(
            success=False,
            healing_id=healing_id,
            workflow_id=workflow_id,
            fix_id=fix.get("id"),
        )

        # Check if auto-apply is enabled
        if not self.config.enabled:
            result.error = "Auto-apply is disabled"
            return result

        # Check fix risk level
        fix_type = fix.get("fix_type", fix.get("type", ""))
        risk_error = self.check_fix_risk(fix_type)
        if risk_error:
            result.error = risk_error
            logger.warning(f"Fix blocked by risk policy: {risk_error}")
            return result

        # Check rate limit (includes healing loop detection)
        if not self.check_rate_limit(workflow_id):
            remaining = self._rate_limiter.remaining(workflow_id)
            reset_time = self._rate_limiter.reset_time(workflow_id)
            if self.detect_healing_loop(workflow_id):
                result.error = (
                    f"Healing loop detected: >{self.config.healing_loop_threshold} "
                    f"attempts in {self.config.healing_loop_window_minutes} minutes. "
                    "Escalate to human."
                )
            else:
                result.error = f"Rate limited. Remaining: {remaining}, Resets: {reset_time}"
            return result

        # Create Git backup if required
        backup_sha = None
        if self.config.require_git_backup and git_backup:
            try:
                backup_sha = await git_backup.backup_workflow(workflow_id, n8n_client)
                result.backup_commit_sha = backup_sha
                logger.info(f"Created backup {backup_sha} for workflow {workflow_id}")
            except Exception as e:
                result.error = f"Failed to create backup: {e}"
                logger.error(f"Backup failed for workflow {workflow_id}: {e}")
                return result

        # Apply the fix
        try:
            await self._apply_fix_to_n8n(fix, workflow_id, n8n_client)

            result.success = True
            result.applied_at = datetime.now(timezone.utc)

            # Record the action
            self._rate_limiter.record(workflow_id)
            self._healing_timestamps[workflow_id].append(datetime.now(timezone.utc))
            self._failure_counts[workflow_id] = 0  # Reset failure count on success

            logger.info(f"Successfully applied fix {fix.get('id')} to workflow {workflow_id}")

        except Exception as e:
            result.error = str(e)
            self._failure_counts[workflow_id] += 1

            logger.error(f"Failed to apply fix to workflow {workflow_id}: {e}")

            # Rollback if we have a backup
            if self.config.rollback_on_failure and backup_sha and git_backup:
                try:
                    await git_backup.rollback_to(backup_sha, workflow_id, n8n_client)
                    result.rolled_back = True
                    logger.info(f"Rolled back workflow {workflow_id} to {backup_sha}")
                except Exception as rollback_error:
                    logger.error(f"Rollback failed for workflow {workflow_id}: {rollback_error}")

                # Set cooldown after rollback
                self._cooldowns[workflow_id] = (
                    datetime.now(timezone.utc) +
                    timedelta(seconds=self.config.cooldown_after_rollback_seconds)
                )

        self._apply_history.append(result)
        return result

    async def _apply_fix_to_n8n(
        self,
        fix: Dict[str, Any],
        workflow_id: str,
        n8n_client: Any,
    ) -> None:
        """Apply the fix to n8n workflow via API."""
        fix_type = fix.get("fix_type", fix.get("type"))

        if fix_type == "loop_breaker":
            await self._apply_loop_breaker(fix, workflow_id, n8n_client)
        elif fix_type == "timeout_adjustment":
            await self._apply_timeout_adjustment(fix, workflow_id, n8n_client)
        elif fix_type == "state_reset":
            await self._apply_state_reset(fix, workflow_id, n8n_client)
        elif fix_type == "prompt_modification":
            await self._apply_prompt_modification(fix, workflow_id, n8n_client)
        else:
            # Generic fix application via workflow update
            await self._apply_generic_fix(fix, workflow_id, n8n_client)

    async def _apply_loop_breaker(
        self,
        fix: Dict[str, Any],
        workflow_id: str,
        n8n_client: Any,
    ) -> None:
        """Apply a loop breaker fix (add iteration limit)."""
        # Get current workflow
        workflow = await n8n_client.get_workflow(workflow_id)

        # Find the loop node and add iteration limit
        target_node = fix.get("target_component", fix.get("node_name"))
        max_iterations = fix.get("parameters", {}).get("max_iterations", 10)

        for node in workflow.get("nodes", []):
            if node.get("name") == target_node or node.get("type") == "n8n-nodes-base.loopOver":
                if "parameters" not in node:
                    node["parameters"] = {}
                node["parameters"]["maxIterations"] = max_iterations

        # Update workflow
        await n8n_client.update_workflow(workflow_id, workflow)

    async def _apply_timeout_adjustment(
        self,
        fix: Dict[str, Any],
        workflow_id: str,
        n8n_client: Any,
    ) -> None:
        """Apply a timeout adjustment fix."""
        workflow = await n8n_client.get_workflow(workflow_id)

        target_node = fix.get("target_component")
        new_timeout = fix.get("parameters", {}).get("timeout", 30000)

        for node in workflow.get("nodes", []):
            if node.get("name") == target_node:
                if "parameters" not in node:
                    node["parameters"] = {}
                node["parameters"]["timeout"] = new_timeout

        await n8n_client.update_workflow(workflow_id, workflow)

    async def _apply_state_reset(
        self,
        fix: Dict[str, Any],
        workflow_id: str,
        n8n_client: Any,
    ) -> None:
        """Apply a state reset fix (clear corrupted state)."""
        # For n8n, this typically means resetting workflow execution state
        await n8n_client.clear_execution_data(workflow_id)

    async def _apply_prompt_modification(
        self,
        fix: Dict[str, Any],
        workflow_id: str,
        n8n_client: Any,
    ) -> None:
        """Apply a prompt modification fix to an AI node."""
        workflow = await n8n_client.get_workflow(workflow_id)

        target_node = fix.get("target_component")
        prompt_changes = fix.get("parameters", {}).get("prompt_changes", {})

        for node in workflow.get("nodes", []):
            if node.get("name") == target_node:
                params = node.get("parameters", {})

                # Apply prompt changes
                if "system_prompt" in prompt_changes:
                    params["systemMessage"] = prompt_changes["system_prompt"]
                if "user_prompt_prefix" in prompt_changes:
                    current = params.get("promptMessages", [])
                    if current:
                        current[0]["text"] = prompt_changes["user_prompt_prefix"] + current[0].get("text", "")

                node["parameters"] = params

        await n8n_client.update_workflow(workflow_id, workflow)

    async def _apply_generic_fix(
        self,
        fix: Dict[str, Any],
        workflow_id: str,
        n8n_client: Any,
    ) -> None:
        """Apply a generic fix by updating workflow parameters."""
        workflow = await n8n_client.get_workflow(workflow_id)

        modified_state = fix.get("modified_state", {})
        if modified_state:
            # Deep merge the modified state into the workflow
            workflow = self._deep_merge(workflow, modified_state)

        await n8n_client.update_workflow(workflow_id, workflow)

    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    async def apply_fix_generic(
        self,
        fix: Dict[str, Any],
        entity_id: str,
        healing_id: str,
        framework: str,
        client: Any,
        git_backup: Optional[Any] = None,
    ) -> ApplyResult:
        """
        Apply a fix to any supported framework.

        Args:
            fix: The fix suggestion to apply
            entity_id: Framework entity ID (assistant_id, app_id, agent_id)
            healing_id: ID of the healing operation
            framework: Framework name (langgraph, dify, openclaw)
            client: Framework API client
            git_backup: Optional GitBackupService for backup
        """
        result = ApplyResult(
            success=False,
            healing_id=healing_id,
            workflow_id=entity_id,
            fix_id=fix.get("id"),
        )

        if not self.config.enabled:
            result.error = "Auto-apply is disabled"
            return result

        fix_type = fix.get("fix_type", fix.get("type", ""))
        risk_error = self.check_fix_risk(fix_type)
        if risk_error:
            result.error = risk_error
            return result

        if not self.check_rate_limit(entity_id):
            remaining = self._rate_limiter.remaining(entity_id)
            reset_time = self._rate_limiter.reset_time(entity_id)
            if self.detect_healing_loop(entity_id):
                result.error = (
                    f"Healing loop detected: >{self.config.healing_loop_threshold} "
                    f"attempts in {self.config.healing_loop_window_minutes} minutes. "
                    "Escalate to human."
                )
            else:
                result.error = f"Rate limited. Remaining: {remaining}, Resets: {reset_time}"
            return result

        backup_sha = None
        if self.config.require_git_backup and git_backup:
            try:
                backup_sha = await git_backup.backup_entity(entity_id, framework, client)
                result.backup_commit_sha = backup_sha
            except Exception as e:
                result.error = f"Failed to create backup: {e}"
                return result

        try:
            dispatch = {
                "langgraph": self._apply_fix_to_langgraph,
                "dify": self._apply_fix_to_dify,
                "openclaw": self._apply_fix_to_openclaw,
            }
            applicator = dispatch.get(framework)
            if not applicator:
                result.error = f"Unsupported framework: {framework}"
                return result

            await applicator(fix, entity_id, client)

            result.success = True
            result.applied_at = datetime.now(timezone.utc)
            self._rate_limiter.record(entity_id)
            self._healing_timestamps[entity_id].append(datetime.now(timezone.utc))
            self._failure_counts[entity_id] = 0

        except Exception as e:
            result.error = str(e)
            self._failure_counts[entity_id] += 1

            if self.config.rollback_on_failure and backup_sha and git_backup:
                try:
                    await git_backup.rollback_entity(backup_sha, entity_id, framework, client)
                    result.rolled_back = True
                except Exception as rollback_error:
                    logger.error(f"Rollback failed for {framework}/{entity_id}: {rollback_error}")

                self._cooldowns[entity_id] = (
                    datetime.now(timezone.utc) +
                    timedelta(seconds=self.config.cooldown_after_rollback_seconds)
                )

        self._apply_history.append(result)
        return result

    # ── LangGraph fix applicators ───────────────────────────────────

    async def _apply_fix_to_langgraph(
        self,
        fix: Dict[str, Any],
        assistant_id: str,
        client: Any,
    ) -> None:
        """Apply a fix to a LangGraph assistant."""
        fix_type = fix.get("fix_type", fix.get("type"))

        if fix_type in ("circuit_breaker", "recursion_guard"):
            await self._apply_langgraph_recursion_guard(fix, assistant_id, client)
        elif fix_type == "state_validation":
            await self._apply_langgraph_state_validation(fix, assistant_id, client)
        elif fix_type in ("step_validator", "edge_fix"):
            await self._apply_langgraph_edge_fix(fix, assistant_id, client)
        else:
            await self._apply_langgraph_generic_fix(fix, assistant_id, client)

    async def _apply_langgraph_recursion_guard(
        self, fix: Dict[str, Any], assistant_id: str, client: Any,
    ) -> None:
        """Add recursion limit to graph config."""
        assistant = await client.get_assistant(assistant_id)
        config = assistant.get("config", {})
        configurable = config.get("configurable", {})
        configurable["recursion_limit"] = fix.get("parameters", {}).get("recursion_limit", 25)
        config["configurable"] = configurable
        await client.update_assistant(assistant_id, {"config": config})

    async def _apply_langgraph_state_validation(
        self, fix: Dict[str, Any], assistant_id: str, client: Any,
    ) -> None:
        """Add state validation metadata to graph config."""
        assistant = await client.get_assistant(assistant_id)
        metadata = assistant.get("metadata", {})
        metadata["state_validation"] = {
            "enabled": True,
            "strict_types": fix.get("parameters", {}).get("strict_types", True),
            "immutable_keys": fix.get("parameters", {}).get("immutable_keys", []),
        }
        await client.update_assistant(assistant_id, {"metadata": metadata})

    async def _apply_langgraph_edge_fix(
        self, fix: Dict[str, Any], assistant_id: str, client: Any,
    ) -> None:
        """Fix conditional edge routing in graph config."""
        assistant = await client.get_assistant(assistant_id)
        metadata = assistant.get("metadata", {})
        metadata["edge_validation"] = {
            "enabled": True,
            "dead_end_detection": True,
        }
        await client.update_assistant(assistant_id, {"metadata": metadata})

    async def _apply_langgraph_generic_fix(
        self, fix: Dict[str, Any], assistant_id: str, client: Any,
    ) -> None:
        """Apply a generic fix by updating assistant config."""
        assistant = await client.get_assistant(assistant_id)
        modified_state = fix.get("modified_state", {})
        if modified_state:
            merged = self._deep_merge(assistant, modified_state)
            await client.update_assistant(assistant_id, merged)

    # ── Dify fix applicators ────────────────────────────────────────

    async def _apply_fix_to_dify(
        self,
        fix: Dict[str, Any],
        app_id: str,
        client: Any,
    ) -> None:
        """Apply a fix to a Dify app."""
        fix_type = fix.get("fix_type", fix.get("type"))

        if fix_type == "circuit_breaker":
            await self._apply_dify_iteration_limit(fix, app_id, client)
        elif fix_type == "input_filtering":
            await self._apply_dify_input_filter(fix, app_id, client)
        elif fix_type in ("input_sanitization", "schema_enforcement"):
            await self._apply_dify_node_config(fix, app_id, client)
        else:
            await self._apply_dify_generic_fix(fix, app_id, client)

    async def _apply_dify_iteration_limit(
        self, fix: Dict[str, Any], app_id: str, client: Any,
    ) -> None:
        """Set iteration bounds on Dify workflow."""
        config = await client.get_app_config(app_id)
        nodes = config.get("nodes", config.get("graph", {}).get("nodes", []))
        max_iterations = fix.get("parameters", {}).get("max_iterations", 10)

        for node in nodes:
            node_type = node.get("data", {}).get("type", "")
            if node_type in ("iteration", "loop"):
                node.setdefault("data", {})["max_iterations"] = max_iterations

        await client.update_app_config(app_id, config)

    async def _apply_dify_input_filter(
        self, fix: Dict[str, Any], app_id: str, client: Any,
    ) -> None:
        """Add input sanitization to Dify RAG nodes."""
        config = await client.get_app_config(app_id)
        nodes = config.get("nodes", config.get("graph", {}).get("nodes", []))

        for node in nodes:
            node_type = node.get("data", {}).get("type", "")
            if node_type in ("knowledge-retrieval", "retrieval"):
                node.setdefault("data", {})["input_filter"] = {
                    "enabled": True,
                    "block_injection_patterns": True,
                }

        await client.update_app_config(app_id, config)

    async def _apply_dify_node_config(
        self, fix: Dict[str, Any], app_id: str, client: Any,
    ) -> None:
        """Update specific node configuration in Dify workflow."""
        config = await client.get_app_config(app_id)
        target_node = fix.get("target_component")
        params = fix.get("parameters", {})
        nodes = config.get("nodes", config.get("graph", {}).get("nodes", []))

        for node in nodes:
            node_id = node.get("id", node.get("data", {}).get("title", ""))
            if node_id == target_node:
                node.setdefault("data", {}).update(params)

        await client.update_app_config(app_id, config)

    async def _apply_dify_generic_fix(
        self, fix: Dict[str, Any], app_id: str, client: Any,
    ) -> None:
        """Apply a generic fix by updating Dify app config."""
        config = await client.get_app_config(app_id)
        modified_state = fix.get("modified_state", {})
        if modified_state:
            merged = self._deep_merge(config, modified_state)
            await client.update_app_config(app_id, merged)

    # ── OpenClaw fix applicators ────────────────────────────────────

    async def _apply_fix_to_openclaw(
        self,
        fix: Dict[str, Any],
        agent_id: str,
        client: Any,
    ) -> None:
        """Apply a fix to an OpenClaw agent."""
        fix_type = fix.get("fix_type", fix.get("type"))

        if fix_type == "circuit_breaker":
            await self._apply_openclaw_loop_guard(fix, agent_id, client)
        elif fix_type in ("retry_limit", "permission_gate"):
            await self._apply_openclaw_tool_limits(fix, agent_id, client)
        elif fix_type == "safety_boundary":
            await self._apply_openclaw_sandbox_enforcement(fix, agent_id, client)
        elif fix_type == "output_constraint":
            await self._apply_openclaw_channel_config(fix, agent_id, client)
        else:
            await self._apply_openclaw_generic_fix(fix, agent_id, client)

    async def _apply_openclaw_loop_guard(
        self, fix: Dict[str, Any], agent_id: str, client: Any,
    ) -> None:
        """Add loop/spawn chain limits to agent config."""
        agent = await client.get_agent(agent_id)
        limits = agent.get("limits", {})
        limits["max_iterations"] = fix.get("parameters", {}).get("max_iterations", 50)
        limits["max_spawn_depth"] = fix.get("parameters", {}).get("max_spawn_depth", 3)
        agent["limits"] = limits
        await client.update_agent(agent_id, agent)

    async def _apply_openclaw_tool_limits(
        self, fix: Dict[str, Any], agent_id: str, client: Any,
    ) -> None:
        """Add tool rate limits and permission restrictions."""
        agent = await client.get_agent(agent_id)
        limits = agent.get("limits", {})
        limits["max_tool_calls_per_session"] = fix.get("parameters", {}).get("max_tool_calls", 100)
        agent["limits"] = limits

        # Restrict sensitive tools if specified
        restricted = fix.get("parameters", {}).get("restricted_tools", [])
        if restricted:
            permissions = agent.get("permissions", {})
            permissions["restricted_tools"] = restricted
            agent["permissions"] = permissions

        await client.update_agent(agent_id, agent)

    async def _apply_openclaw_sandbox_enforcement(
        self, fix: Dict[str, Any], agent_id: str, client: Any,
    ) -> None:
        """Enforce sandbox boundaries on agent."""
        agent = await client.get_agent(agent_id)
        sandbox = agent.get("sandbox", {})
        sandbox["enabled"] = True
        sandbox["strict_mode"] = True
        sandbox["blocked_operations"] = fix.get("parameters", {}).get(
            "blocked_operations", ["file_write", "network_external", "process_spawn"]
        )
        agent["sandbox"] = sandbox
        await client.update_agent(agent_id, agent)

    async def _apply_openclaw_channel_config(
        self, fix: Dict[str, Any], agent_id: str, client: Any,
    ) -> None:
        """Configure channel-aware formatting."""
        agent = await client.get_agent(agent_id)
        metadata = agent.get("metadata", {})
        metadata["channel_adaptation"] = {
            "enabled": True,
            "format_by_channel": fix.get("parameters", {}).get("format_rules", {}),
        }
        agent["metadata"] = metadata
        await client.update_agent(agent_id, agent)

    async def _apply_openclaw_generic_fix(
        self, fix: Dict[str, Any], agent_id: str, client: Any,
    ) -> None:
        """Apply a generic fix by updating agent config."""
        agent = await client.get_agent(agent_id)
        modified_state = fix.get("modified_state", {})
        if modified_state:
            merged = self._deep_merge(agent, modified_state)
            await client.update_agent(agent_id, merged)

    # ── Dedicated per-framework apply methods ────────────────────────

    async def apply_fix_langgraph(
        self,
        fix: Dict[str, Any],
        assistant_id: str,
        healing_id: str,
        langgraph_client: Any,
        git_backup: Optional[Any] = None,
    ) -> ApplyResult:
        """Apply a fix to a LangGraph assistant with safety controls."""
        return await self._apply_fix_for_framework(
            fix=fix,
            entity_id=assistant_id,
            healing_id=healing_id,
            framework="langgraph",
            client=langgraph_client,
            git_backup=git_backup,
            applicator=self._apply_fix_to_langgraph,
        )

    async def apply_fix_dify(
        self,
        fix: Dict[str, Any],
        app_id: str,
        healing_id: str,
        dify_client: Any,
        git_backup: Optional[Any] = None,
    ) -> ApplyResult:
        """Apply a fix to a Dify app with safety controls."""
        return await self._apply_fix_for_framework(
            fix=fix,
            entity_id=app_id,
            healing_id=healing_id,
            framework="dify",
            client=dify_client,
            git_backup=git_backup,
            applicator=self._apply_fix_to_dify,
        )

    async def apply_fix_openclaw(
        self,
        fix: Dict[str, Any],
        agent_id: str,
        healing_id: str,
        openclaw_client: Any,
        git_backup: Optional[Any] = None,
    ) -> ApplyResult:
        """Apply a fix to an OpenClaw agent with safety controls."""
        return await self._apply_fix_for_framework(
            fix=fix,
            entity_id=agent_id,
            healing_id=healing_id,
            framework="openclaw",
            client=openclaw_client,
            git_backup=git_backup,
            applicator=self._apply_fix_to_openclaw,
        )

    async def _apply_fix_for_framework(
        self,
        fix: Dict[str, Any],
        entity_id: str,
        healing_id: str,
        framework: str,
        client: Any,
        git_backup: Optional[Any],
        applicator,
    ) -> ApplyResult:
        """Shared implementation for per-framework apply with safety controls."""
        result = ApplyResult(
            success=False,
            healing_id=healing_id,
            workflow_id=entity_id,
            fix_id=fix.get("id"),
        )

        if not self.config.enabled:
            result.error = "Auto-apply is disabled"
            return result

        fix_type = fix.get("fix_type", fix.get("type", ""))
        risk_error = self.check_fix_risk(fix_type)
        if risk_error:
            result.error = risk_error
            logger.warning(f"[{framework}] Fix blocked by risk policy: {risk_error}")
            return result

        if not self.check_rate_limit(entity_id):
            remaining = self._rate_limiter.remaining(entity_id)
            reset_time = self._rate_limiter.reset_time(entity_id)
            if self.detect_healing_loop(entity_id):
                result.error = (
                    f"Healing loop detected: >{self.config.healing_loop_threshold} "
                    f"attempts in {self.config.healing_loop_window_minutes} minutes. "
                    "Escalate to human."
                )
            else:
                result.error = f"Rate limited. Remaining: {remaining}, Resets: {reset_time}"
            return result

        backup_sha = None
        if self.config.require_git_backup and git_backup:
            try:
                backup_sha = await git_backup.backup_entity(entity_id, framework, client)
                result.backup_commit_sha = backup_sha
                logger.info(f"[{framework}] Created backup {backup_sha} for {entity_id}")
            except Exception as e:
                result.error = f"Failed to create backup: {e}"
                logger.error(f"[{framework}] Backup failed for {entity_id}: {e}")
                return result

        try:
            await applicator(fix, entity_id, client)

            result.success = True
            result.applied_at = datetime.now(timezone.utc)
            self._rate_limiter.record(entity_id)
            self._healing_timestamps[entity_id].append(datetime.now(timezone.utc))
            self._failure_counts[entity_id] = 0

            logger.info(f"[{framework}] Successfully applied fix {fix.get('id')} to {entity_id}")

        except Exception as e:
            result.error = str(e)
            self._failure_counts[entity_id] += 1
            logger.error(f"[{framework}] Failed to apply fix to {entity_id}: {e}")

            if self.config.rollback_on_failure and backup_sha and git_backup:
                try:
                    await git_backup.rollback_entity(backup_sha, entity_id, framework, client)
                    result.rolled_back = True
                    logger.info(f"[{framework}] Rolled back {entity_id} to {backup_sha}")
                except Exception as rollback_error:
                    logger.error(f"[{framework}] Rollback failed for {entity_id}: {rollback_error}")

                self._cooldowns[entity_id] = (
                    datetime.now(timezone.utc) +
                    timedelta(seconds=self.config.cooldown_after_rollback_seconds)
                )

        self._apply_history.append(result)
        return result

    # ── Per-framework rollback methods ─────────────────────────────

    async def rollback(
        self,
        apply_result: ApplyResult,
        git_backup: Any,
        n8n_client: Any,
    ) -> bool:
        """Rollback a previously applied fix to an n8n workflow."""
        if not apply_result.backup_commit_sha:
            logger.error("Cannot rollback: no backup commit SHA")
            return False

        try:
            await git_backup.rollback_to(
                apply_result.backup_commit_sha,
                apply_result.workflow_id,
                n8n_client,
            )
            logger.info(f"Rolled back workflow {apply_result.workflow_id}")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    async def rollback_langgraph(
        self,
        apply_result: ApplyResult,
        git_backup: Any,
        langgraph_client: Any,
    ) -> bool:
        """Rollback a previously applied fix to a LangGraph assistant."""
        if not apply_result.backup_commit_sha:
            logger.error("Cannot rollback LangGraph: no backup commit SHA")
            return False

        try:
            await git_backup.rollback_entity(
                apply_result.backup_commit_sha,
                apply_result.workflow_id,
                "langgraph",
                langgraph_client,
            )
            logger.info(f"Rolled back LangGraph assistant {apply_result.workflow_id}")
            return True
        except Exception as e:
            logger.error(f"LangGraph rollback failed: {e}")
            return False

    async def rollback_dify(
        self,
        apply_result: ApplyResult,
        git_backup: Any,
        dify_client: Any,
    ) -> bool:
        """Rollback a previously applied fix to a Dify app."""
        if not apply_result.backup_commit_sha:
            logger.error("Cannot rollback Dify: no backup commit SHA")
            return False

        try:
            await git_backup.rollback_entity(
                apply_result.backup_commit_sha,
                apply_result.workflow_id,
                "dify",
                dify_client,
            )
            logger.info(f"Rolled back Dify app {apply_result.workflow_id}")
            return True
        except Exception as e:
            logger.error(f"Dify rollback failed: {e}")
            return False

    async def rollback_openclaw(
        self,
        apply_result: ApplyResult,
        git_backup: Any,
        openclaw_client: Any,
    ) -> bool:
        """Rollback a previously applied fix to an OpenClaw agent."""
        if not apply_result.backup_commit_sha:
            logger.error("Cannot rollback OpenClaw: no backup commit SHA")
            return False

        try:
            await git_backup.rollback_entity(
                apply_result.backup_commit_sha,
                apply_result.workflow_id,
                "openclaw",
                openclaw_client,
            )
            logger.info(f"Rolled back OpenClaw agent {apply_result.workflow_id}")
            return True
        except Exception as e:
            logger.error(f"OpenClaw rollback failed: {e}")
            return False

    def get_apply_history(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ApplyResult]:
        """Get history of apply operations."""
        results = self._apply_history[-limit:]
        if workflow_id:
            results = [r for r in results if r.workflow_id == workflow_id]
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about auto-apply operations."""
        total = len(self._apply_history)
        if total == 0:
            return {"total": 0}

        successful = sum(1 for r in self._apply_history if r.success)
        rolled_back = sum(1 for r in self._apply_history if r.rolled_back)

        return {
            "total": total,
            "successful": successful,
            "failed": total - successful,
            "rolled_back": rolled_back,
            "success_rate": successful / total if total > 0 else 0,
        }
