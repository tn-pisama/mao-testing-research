"""Detection factories for E2E testing."""

import secrets
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


class DetectionFactory:
    """Factory for creating test detection scenarios."""
    
    @staticmethod
    def infinite_loop(
        confidence: float = 0.92,
        loop_length: int = 7,
        agents: Optional[List[str]] = None,
        method: str = "structural"
    ) -> Dict[str, Any]:
        """Create infinite loop detection."""
        return {
            "id": f"det_loop_{secrets.token_hex(6)}",
            "detection_type": "infinite_loop",
            "confidence": confidence,
            "method": method,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {
                "loop_length": loop_length,
                "affected_agents": agents or ["researcher", "analyst"],
                "message": f"Node sequence cycles detected. State hash repeated {loop_length} times.",
                "iteration_count": loop_length,
                "max_iterations": 3,
            }
        }
    
    @staticmethod
    def state_corruption(
        corrupted_fields: Optional[List[str]] = None,
        null_injection: bool = True,
        data_loss: bool = True,
        confidence: float = 0.88
    ) -> Dict[str, Any]:
        """Create state corruption detection."""
        return {
            "id": f"det_corruption_{secrets.token_hex(6)}",
            "detection_type": "state_corruption",
            "confidence": confidence,
            "method": "hash_comparison",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {
                "corrupted_fields": corrupted_fields or ["research_notes", "analysis"],
                "null_injection": null_injection,
                "data_loss": data_loss,
                "message": "Original response was destroyed. Null values injected into state.",
                "node_name": "corrupted_processor",
            }
        }
    
    @staticmethod
    def persona_drift(
        agent_name: str = "writer",
        expected_tone: str = "professional",
        actual_tone: str = "casual_unprofessional",
        drift_score: float = 0.85,
        confidence: float = 0.85
    ) -> Dict[str, Any]:
        """Create persona drift detection."""
        return {
            "id": f"det_drift_{secrets.token_hex(6)}",
            "detection_type": "persona_drift",
            "confidence": confidence,
            "method": "style_analysis",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {
                "drift_score": drift_score,
                "expected_tone": expected_tone,
                "actual_tone": actual_tone,
                "agent_name": agent_name,
                "emojis_detected": True,
                "slang_detected": True,
                "message": f"Tone mismatch detected. Expected {expected_tone}, got {actual_tone}.",
            }
        }
    
    @staticmethod
    def timeout(
        timeout_ms: int = 30000,
        node_name: str = "slow_processor",
        confidence: float = 0.95
    ) -> Dict[str, Any]:
        """Create timeout detection."""
        return {
            "id": f"det_timeout_{secrets.token_hex(6)}",
            "detection_type": "timeout",
            "confidence": confidence,
            "method": "execution_monitoring",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {
                "timeout_ms": timeout_ms,
                "node_name": node_name,
                "message": f"Node {node_name} exceeded timeout of {timeout_ms}ms",
            }
        }
    
    def create_detection(self, failure_mode: str, **kwargs) -> Dict[str, Any]:
        """Create detection for specified failure mode."""
        factories = {
            "infinite_loop": self.infinite_loop,
            "loop": self.infinite_loop,
            "state_corruption": self.state_corruption,
            "corruption": self.state_corruption,
            "persona_drift": self.persona_drift,
            "drift": self.persona_drift,
            "timeout": self.timeout,
        }
        factory_fn = factories.get(failure_mode, self.infinite_loop)
        return factory_fn(**kwargs)
