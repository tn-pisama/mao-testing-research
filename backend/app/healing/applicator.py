"""Fix applicator for applying generated fixes to workflows."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
import copy
import secrets

from typing import Optional

from .models import AppliedFix, FailureCategory, HealingConfig


class FixApplicator:
    """Applies fix suggestions to workflow configurations and code."""

    def __init__(self, config: Optional[HealingConfig] = None):
        self._config = config or HealingConfig()
        self._strategies: Dict[FailureCategory, "ApplicatorStrategy"] = {}
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        self._strategies[FailureCategory.INFINITE_LOOP] = LoopFixApplicator()
        self._strategies[FailureCategory.STATE_CORRUPTION] = CorruptionFixApplicator()
        self._strategies[FailureCategory.PERSONA_DRIFT] = DriftFixApplicator()
        self._strategies[FailureCategory.TIMEOUT] = TimeoutFixApplicator()
        self._strategies[FailureCategory.COORDINATION_DEADLOCK] = DeadlockFixApplicator()
        self._strategies[FailureCategory.HALLUCINATION] = HallucinationFixApplicator()
        self._strategies[FailureCategory.INJECTION] = InjectionFixApplicator()
        self._strategies[FailureCategory.CONTEXT_OVERFLOW] = OverflowFixApplicator()
        self._strategies[FailureCategory.TASK_DERAILMENT] = DerailmentFixApplicator()
        self._strategies[FailureCategory.CONTEXT_NEGLECT] = ContextNeglectFixApplicator()
        self._strategies[FailureCategory.COMMUNICATION_BREAKDOWN] = CommunicationFixApplicator()
        self._strategies[FailureCategory.SPECIFICATION_MISMATCH] = SpecificationFixApplicator()
        self._strategies[FailureCategory.POOR_DECOMPOSITION] = DecompositionFixApplicator()
        self._strategies[FailureCategory.FLAWED_WORKFLOW] = WorkflowFixApplicator()
        self._strategies[FailureCategory.INFORMATION_WITHHOLDING] = WithholdingFixApplicator()
        self._strategies[FailureCategory.COMPLETION_MISJUDGMENT] = CompletionFixApplicator()
        self._strategies[FailureCategory.COST_OVERRUN] = CostFixApplicator()
    
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

        # v1.1: Context-aware timeout — use actual timeout * 1.5 buffer if available
        metadata = fix.get("metadata", {})
        timeout_ms = metadata.get("timeout_ms")
        if timeout_ms is None:
            actual_timeout = metadata.get("actual_timeout_ms", 0)
            if actual_timeout > 0:
                timeout_ms = int(actual_timeout * 1.5)  # 50% buffer over actual
            else:
                timeout_ms = 30000  # Sensible default

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


class HallucinationFixApplicator(ApplicatorStrategy):
    """Applies hallucination prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        if fix_type == "fact_checking":
            result["settings"]["fact_checking"] = {
                "enabled": True,
                "verification_sources": ["internal_knowledge", "grounding_docs"],
                "confidence_threshold": 0.7,
                "on_low_confidence": "flag_and_cite",
            }
        elif fix_type == "source_grounding":
            result["settings"]["source_grounding"] = {
                "enabled": True,
                "require_citations": True,
                "max_unsupported_claims": 0,
                "grounding_strategy": "retrieval_augmented",
            }
        elif fix_type == "confidence_calibration":
            result["settings"]["confidence_calibration"] = {
                "enabled": True,
                "min_confidence": 0.6,
                "require_uncertainty_markers": True,
                "calibration_method": "verbalized_probability",
            }
        else:
            result["settings"]["fact_checking"] = {"enabled": True}

        return result


class InjectionFixApplicator(ApplicatorStrategy):
    """Applies injection prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        if fix_type == "input_filtering":
            result["settings"]["input_filtering"] = {
                "enabled": True,
                "filter_patterns": ["ignore previous", "system:", "jailbreak"],
                "sanitize_mode": "escape_and_flag",
                "block_on_detection": True,
            }
        elif fix_type == "safety_boundary":
            result["settings"]["safety_boundary"] = {
                "enabled": True,
                "boundary_type": "instruction_hierarchy",
                "system_prompt_priority": "highest",
                "reject_conflicting_instructions": True,
            }
        elif fix_type == "permission_gate":
            result["settings"]["permission_gate"] = {
                "enabled": True,
                "require_approval_for": ["code_execution", "data_access", "external_calls"],
                "approval_timeout_ms": 30000,
            }
        else:
            result["settings"]["input_filtering"] = {"enabled": True}

        return result


class OverflowFixApplicator(ApplicatorStrategy):
    """Applies context overflow prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        # v1.1: Context-aware token limits from fix metadata
        metadata = fix.get("metadata", {})
        context_window = metadata.get("context_window", 128000)
        # Target 60% of context window for pruning, or 4000 min
        max_context_tokens = max(4000, int(context_window * 0.6))
        trigger_threshold = max(3000, int(context_window * 0.5))
        window_size = max(4096, int(context_window * 0.4))

        if fix_type == "context_pruning":
            result["settings"]["context_pruning"] = {
                "enabled": True,
                "max_context_tokens": max_context_tokens,
                "pruning_strategy": "relevance_weighted",
                "preserve_system_prompt": True,
            }
        elif fix_type == "summarization":
            result["settings"]["summarization"] = {
                "enabled": True,
                "trigger_threshold_tokens": trigger_threshold,
                "summary_target_tokens": max(500, int(trigger_threshold * 0.15)),
                "preserve_recent_turns": 3,
            }
        elif fix_type == "window_management":
            result["settings"]["window_management"] = {
                "enabled": True,
                "window_type": "sliding",
                "max_window_size": window_size,
                "overlap_tokens": max(200, int(window_size * 0.05)),
            }
        else:
            result["settings"]["context_pruning"] = {"enabled": True}

        result["settings"]["executionTimeout"] = result["settings"].get("executionTimeout", 300)

        return result


class DerailmentFixApplicator(ApplicatorStrategy):
    """Applies task derailment prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        if fix_type == "task_anchoring":
            result["settings"]["task_anchoring"] = {
                "enabled": True,
                "anchor_frequency": "every_turn",
                "include_original_goal": True,
                "deviation_threshold": 0.3,
            }
        elif fix_type == "goal_tracking":
            result["settings"]["goal_tracking"] = {
                "enabled": True,
                "track_subtask_completion": True,
                "alert_on_drift": True,
                "max_off_topic_turns": 2,
            }
        elif fix_type == "progress_monitoring":
            result["settings"]["progress_monitoring"] = {
                "enabled": True,
                "checkpoint_interval": 5,
                "report_progress": True,
            }
        else:
            result["settings"]["task_anchoring"] = {"enabled": True}

        return result


class ContextNeglectFixApplicator(ApplicatorStrategy):
    """Applies context neglect prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        if fix_type == "checkpoint_recovery":
            result["settings"]["context_injection"] = {
                "enabled": True,
                "inject_at": "every_turn",
                "include_key_facts": True,
                "max_injection_tokens": 500,
            }
        elif fix_type in ("retrieval_enhancement", "retrieval_verification"):
            result["settings"]["retrieval_verification"] = {
                "enabled": True,
                "verify_context_used": True,
                "min_context_coverage": 0.8,
                "flag_ignored_context": True,
            }
        else:
            result["settings"]["context_injection"] = {"enabled": True}

        result["settings"]["checkpointing"] = result["settings"].get("checkpointing", {"enabled": True})

        return result


class CommunicationFixApplicator(ApplicatorStrategy):
    """Applies communication breakdown prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        if fix_type == "message_schema":
            result["settings"]["message_schema"] = {
                "enabled": True,
                "schema_version": "1.0",
                "required_fields": ["sender", "recipient", "content", "timestamp"],
                "validate_on_send": True,
            }
        elif fix_type == "handoff_protocol":
            result["settings"]["handoff_protocol"] = {
                "enabled": True,
                "require_acknowledgment": True,
                "handoff_timeout_ms": 15000,
                "include_context_summary": True,
            }
        elif fix_type == "retry_limit":
            result["settings"]["retry"] = {
                "enabled": True,
                "max_retries": 3,
                "backoff_ms": 1000,
            }
        else:
            result["settings"]["message_schema"] = {"enabled": True}

        return result


class SpecificationFixApplicator(ApplicatorStrategy):
    """Applies specification mismatch prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        if fix_type == "spec_validation":
            result["settings"]["spec_validation"] = {
                "enabled": True,
                "validate_output_format": True,
                "validate_required_fields": True,
                "on_mismatch": "retry_with_feedback",
            }
        elif fix_type == "output_constraint":
            result["settings"]["output_constraints"] = {
                "enabled": True,
                "max_length": fix.get("metadata", {}).get("max_length", 4096),
                "required_sections": [],
                "forbidden_patterns": [],
            }
        elif fix_type == "schema_enforcement":
            result["settings"]["schema_enforcement"] = {
                "enabled": True,
                "strict_mode": True,
                "reject_unknown_fields": False,
                "coerce_types": True,
            }
        else:
            result["settings"]["spec_validation"] = {"enabled": True}

        return result


class DecompositionFixApplicator(ApplicatorStrategy):
    """Applies poor decomposition prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        if fix_type == "task_decomposer":
            result["settings"]["task_decomposition"] = {
                "enabled": True,
                "max_subtask_depth": 3,
                "min_subtasks": 2,
                "require_completion_criteria": True,
            }
        elif fix_type == "subtask_validator":
            result["settings"]["subtask_validation"] = {
                "enabled": True,
                "validate_completeness": True,
                "validate_ordering": True,
                "check_dependencies": True,
            }
        elif fix_type == "progress_monitoring":
            result["settings"]["progress_monitoring"] = {
                "enabled": True,
                "checkpoint_interval": 5,
                "report_progress": True,
            }
        else:
            result["settings"]["task_decomposition"] = {"enabled": True}

        return result


class WorkflowFixApplicator(ApplicatorStrategy):
    """Applies flawed workflow prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        if fix_type == "workflow_guard":
            result["settings"]["workflow_guards"] = {
                "enabled": True,
                "validate_transitions": True,
                "max_steps": 50,
                "on_guard_failure": "halt_and_report",
            }
        elif fix_type == "step_validator":
            result["settings"]["step_validation"] = {
                "enabled": True,
                "validate_input": True,
                "validate_output": True,
                "log_step_results": True,
            }
        elif fix_type == "circuit_breaker":
            result["settings"]["circuit_breaker"] = {
                "enabled": True,
                "failure_threshold": 5,
                "recovery_timeout_seconds": 60,
            }
        else:
            result["settings"]["workflow_guards"] = {"enabled": True}

        if not result["settings"].get("errorWorkflow"):
            result["settings"]["errorWorkflow"] = "error_handler"

        return result


class WithholdingFixApplicator(ApplicatorStrategy):
    """Applies information withholding prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        if fix_type == "transparency_enforcer":
            result["settings"]["transparency"] = {
                "enabled": True,
                "require_reasoning": True,
                "expose_confidence": True,
                "cite_sources": True,
            }
        elif fix_type == "information_completeness":
            result["settings"]["completeness_check"] = {
                "enabled": True,
                "min_response_coverage": 0.8,
                "flag_omissions": True,
                "require_explicit_unknowns": True,
            }
        elif fix_type == "source_grounding":
            result["settings"]["source_grounding"] = {
                "enabled": True,
                "require_citations": True,
            }
        else:
            result["settings"]["transparency"] = {"enabled": True}

        return result


class CompletionFixApplicator(ApplicatorStrategy):
    """Applies completion misjudgment prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        if fix_type == "completion_gate":
            result["settings"]["completion_gate"] = {
                "enabled": True,
                "require_all_subtasks": True,
                "quality_threshold": 0.8,
                "review_before_finalize": True,
            }
        elif fix_type == "quality_checkpoint":
            result["settings"]["quality_checkpoint"] = {
                "enabled": True,
                "checkpoint_frequency": "after_each_subtask",
                "min_quality_score": 0.7,
                "block_on_failure": True,
            }
        elif fix_type == "progress_monitoring":
            result["settings"]["progress_monitoring"] = {
                "enabled": True,
                "checkpoint_interval": 5,
                "report_progress": True,
            }
        else:
            result["settings"]["completion_gate"] = {"enabled": True}

        return result


class CostFixApplicator(ApplicatorStrategy):
    """Applies cost overrun prevention fixes."""

    def apply(self, fix: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(config)
        fix_type = fix.get("fix_type", "")

        if "settings" not in result:
            result["settings"] = {}

        if fix_type == "budget_limiter":
            result["settings"]["budget_limit"] = {
                "enabled": True,
                "max_tokens": fix.get("metadata", {}).get("max_tokens", 100000),
                "max_cost_usd": fix.get("metadata", {}).get("max_cost_usd", 1.0),
                "on_limit_exceeded": "terminate_gracefully",
            }
        elif fix_type == "cost_monitor":
            result["settings"]["cost_monitoring"] = {
                "enabled": True,
                "track_tokens": True,
                "track_api_calls": True,
                "alert_threshold_pct": 80,
            }
        elif fix_type == "token_optimizer":
            result["settings"]["token_optimizer"] = {
                "enabled": True,
                "optimize_prompts": True,
                "cache_responses": True,
                "deduplicate_context": True,
            }
        else:
            result["settings"]["budget_limit"] = {"enabled": True}

        result["settings"]["executionTimeout"] = result["settings"].get("executionTimeout", 300)

        return result
