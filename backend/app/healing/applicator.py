"""Fix applicator for applying generated fixes to workflows."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
import copy
import secrets

from .models import AppliedFix, FailureCategory


class FixApplicator:
    """Applies fix suggestions to workflow configurations and code."""
    
    def __init__(self):
        self._strategies: Dict[FailureCategory, "ApplicatorStrategy"] = {}
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        self._strategies[FailureCategory.INFINITE_LOOP] = LoopFixApplicator()
        self._strategies[FailureCategory.STATE_CORRUPTION] = CorruptionFixApplicator()
        self._strategies[FailureCategory.PERSONA_DRIFT] = DriftFixApplicator()
        self._strategies[FailureCategory.TIMEOUT] = TimeoutFixApplicator()
        self._strategies[FailureCategory.COORDINATION_DEADLOCK] = DeadlockFixApplicator()
    
    def apply(
        self,
        fix_suggestion: Dict[str, Any],
        workflow_config: Dict[str, Any],
        failure_category: FailureCategory,
    ) -> AppliedFix:
        """Apply a fix suggestion to a workflow configuration."""
        strategy = self._strategies.get(failure_category)
        if not strategy:
            raise ValueError(f"No applicator strategy for {failure_category}")
        
        original_state = copy.deepcopy(workflow_config)
        
        modified_config = strategy.apply(fix_suggestion, workflow_config)
        
        return AppliedFix(
            fix_id=fix_suggestion.get("id", f"fix_{secrets.token_hex(4)}"),
            fix_type=fix_suggestion.get("fix_type", "unknown"),
            applied_at=datetime.now(timezone.utc),
            target_component=fix_suggestion.get("target", "workflow"),
            original_state=original_state,
            modified_state=modified_config,
            rollback_available=True,
        )
    
    def rollback(self, applied_fix: AppliedFix, current_config: Dict[str, Any]) -> Dict[str, Any]:
        """Rollback an applied fix to original state."""
        if not applied_fix.rollback_available:
            raise ValueError("Rollback not available for this fix")
        return copy.deepcopy(applied_fix.original_state)


class ApplicatorStrategy(ABC):
    """Base strategy for applying specific fix types."""
    
    @abstractmethod
    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the fix to the configuration."""
        pass


class LoopFixApplicator(ApplicatorStrategy):
    """Applies loop prevention fixes."""
    
    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")
        
        if fix_type == "retry_limit":
            result = self._apply_retry_limit(fix, result)
        elif fix_type == "circuit_breaker":
            result = self._apply_circuit_breaker(fix, result)
        elif fix_type == "exponential_backoff":
            result = self._apply_backoff(fix, result)
        else:
            result = self._apply_generic_loop_fix(fix, result)
        
        return result
    
    def _apply_retry_limit(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        max_retries = fix.get("metadata", {}).get("max_retries", 5)
        
        if "settings" not in config:
            config["settings"] = {}
        config["settings"]["max_iterations"] = max_retries
        config["settings"]["loop_prevention"] = {
            "enabled": True,
            "max_retries": max_retries,
            "on_limit_exceeded": "terminate_gracefully",
        }
        
        if "nodes" in config:
            for node in config["nodes"]:
                if node.get("type") in ["conditional", "router", "loop"]:
                    if "parameters" not in node:
                        node["parameters"] = {}
                    node["parameters"]["max_iterations"] = max_retries
        
        return config
    
    def _apply_circuit_breaker(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        if "settings" not in config:
            config["settings"] = {}
        config["settings"]["circuit_breaker"] = {
            "enabled": True,
            "failure_threshold": 5,
            "recovery_timeout_seconds": 60,
            "half_open_requests": 1,
        }
        return config
    
    def _apply_backoff(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        if "settings" not in config:
            config["settings"] = {}
        config["settings"]["backoff"] = {
            "enabled": True,
            "type": "exponential",
            "base_delay_ms": 1000,
            "max_delay_ms": 60000,
            "jitter": True,
        }
        return config
    
    def _apply_generic_loop_fix(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        if "settings" not in config:
            config["settings"] = {}
        config["settings"]["loop_prevention"] = {"enabled": True, "max_iterations": 10}
        return config


class CorruptionFixApplicator(ApplicatorStrategy):
    """Applies state corruption prevention fixes."""
    
    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")
        
        if fix_type == "state_validation":
            result = self._apply_state_validation(fix, result)
        elif fix_type == "schema_enforcement":
            result = self._apply_schema_enforcement(fix, result)
        elif fix_type == "checkpoint_recovery":
            result = self._apply_checkpoint(fix, result)
        else:
            result = self._apply_generic_corruption_fix(fix, result)
        
        return result
    
    def _apply_state_validation(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        if "settings" not in config:
            config["settings"] = {}
        config["settings"]["state_validation"] = {
            "enabled": True,
            "validate_on_node_entry": True,
            "validate_on_node_exit": True,
            "required_fields": fix.get("metadata", {}).get("required_fields", []),
            "on_validation_failure": "rollback_to_checkpoint",
        }
        return config
    
    def _apply_schema_enforcement(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        if "settings" not in config:
            config["settings"] = {}
        config["settings"]["schema_enforcement"] = {
            "enabled": True,
            "strict_mode": True,
            "reject_unknown_fields": False,
            "coerce_types": True,
        }
        return config
    
    def _apply_checkpoint(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        if "settings" not in config:
            config["settings"] = {}
        config["settings"]["checkpointing"] = {
            "enabled": True,
            "checkpoint_interval": 1,
            "max_checkpoints": 5,
            "auto_rollback_on_corruption": True,
        }
        return config
    
    def _apply_generic_corruption_fix(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        if "settings" not in config:
            config["settings"] = {}
        config["settings"]["state_protection"] = {"enabled": True}
        return config


class DriftFixApplicator(ApplicatorStrategy):
    """Applies persona drift prevention fixes."""
    
    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")
        
        if fix_type == "prompt_reinforcement":
            result = self._apply_prompt_reinforcement(fix, result)
        elif fix_type == "role_boundary":
            result = self._apply_role_boundary(fix, result)
        else:
            result = self._apply_generic_drift_fix(fix, result)
        
        return result
    
    def _apply_prompt_reinforcement(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        metadata = fix.get("metadata", {})
        reinforcement_level = metadata.get("reinforcement_level", "moderate")
        
        if "settings" not in config:
            config["settings"] = {}
        config["settings"]["persona_enforcement"] = {
            "enabled": True,
            "reinforcement_level": reinforcement_level,
            "periodic_reminder": True,
            "reminder_interval": 5,
        }
        
        if "nodes" in config:
            for node in config["nodes"]:
                if node.get("type") in ["llm", "openai", "chat"]:
                    if "parameters" not in node:
                        node["parameters"] = {}
                    if "messages" not in node["parameters"]:
                        node["parameters"]["messages"] = {"values": []}
                    
                    system_msg = node["parameters"]["messages"].get("values", [])
                    reinforcement = {
                        "role": "system",
                        "content": "IMPORTANT: Maintain professional tone. No slang, no emojis, formal language only."
                    }
                    if reinforcement not in system_msg:
                        system_msg.insert(0, reinforcement)
        
        return config
    
    def _apply_role_boundary(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        if "settings" not in config:
            config["settings"] = {}
        config["settings"]["role_boundaries"] = {
            "enabled": True,
            "strict_persona": True,
            "output_validation": True,
            "block_on_violation": True,
        }
        return config
    
    def _apply_generic_drift_fix(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        if "settings" not in config:
            config["settings"] = {}
        config["settings"]["persona_enforcement"] = {"enabled": True}
        return config


class TimeoutFixApplicator(ApplicatorStrategy):
    """Applies timeout fixes."""
    
    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        
        timeout_ms = fix.get("metadata", {}).get("timeout_ms", 30000)
        
        if "settings" not in result:
            result["settings"] = {}
        result["settings"]["timeouts"] = {
            "enabled": True,
            "default_timeout_ms": timeout_ms,
            "per_node_timeouts": {},
            "on_timeout": "terminate_and_report",
        }
        
        return result


class DeadlockFixApplicator(ApplicatorStrategy):
    """Applies deadlock prevention fixes."""
    
    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        
        if "settings" not in result:
            result["settings"] = {}
        result["settings"]["deadlock_prevention"] = {
            "enabled": True,
            "detection_interval_ms": 5000,
            "resolution_strategy": "preempt_lowest_priority",
            "max_wait_time_ms": 30000,
        }
        
        return result
