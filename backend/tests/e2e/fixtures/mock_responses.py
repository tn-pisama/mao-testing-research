"""Mock LLM responses for deterministic E2E testing."""

from typing import Dict, Any, Optional
from contextlib import contextmanager


class MockLLMResponses:
    """Manages mock LLM responses for deterministic testing."""
    
    NORMAL_RESPONSES = {
        "researcher": "Based on comprehensive research, multi-agent AI systems provide distributed intelligence, improved scalability, and fault tolerance through redundancy.",
        "analyst": "Analysis of the research findings indicates three key benefits: 1) Enhanced problem-solving through collaboration, 2) Modular architecture for scalability, 3) Built-in redundancy for reliability.",
        "writer": "Multi-agent AI systems represent a significant advancement in artificial intelligence architecture, offering enterprises a robust framework for complex task automation.",
        "default": "Task completed successfully with professional output.",
    }
    
    LOOP_RESPONSES = {
        "researcher": "I need the analyst to review this data before I can proceed further.",
        "analyst": "This requires additional research. Sending back to researcher for more data.",
        "default": "Need more research. Requesting additional analysis.",
    }
    
    CORRUPTION_RESPONSES = {
        "processor": "ERROR: CRITICAL_FAILURE\nNullPointerException at line 42\nOriginal data was destroyed",
        "default": "ERROR: DATA_CORRUPTION_DETECTED",
    }
    
    DRIFT_RESPONSES = {
        "writer": "lol so basically these AI agent thingies are like super cool robots working together ya know? 🤖💯 They're like a squad of brainy bots doing teamwork n stuff haha",
        "default": "omg this is like totally awesome tbh 😂🔥",
    }
    
    def get_response(
        self,
        node_type: str,
        failure_mode: str = "normal"
    ) -> str:
        """Get deterministic response based on node type and failure mode."""
        response_maps = {
            "normal": self.NORMAL_RESPONSES,
            "loop": self.LOOP_RESPONSES,
            "infinite_loop": self.LOOP_RESPONSES,
            "corruption": self.CORRUPTION_RESPONSES,
            "state_corruption": self.CORRUPTION_RESPONSES,
            "drift": self.DRIFT_RESPONSES,
            "persona_drift": self.DRIFT_RESPONSES,
        }
        
        responses = response_maps.get(failure_mode, self.NORMAL_RESPONSES)
        return responses.get(node_type, responses.get("default", "Response generated."))
    
    def create_workflow_execution_result(
        self,
        workflow: Dict[str, Any],
        failure_mode: str = "normal",
        iteration_count: int = 1
    ) -> Dict[str, Any]:
        """Create a simulated workflow execution result."""
        nodes = workflow.get("nodes", [])
        executed_nodes = []
        final_state = {}
        
        for node in nodes:
            node_id = node.get("id", node.get("name", "unknown"))
            executed_nodes.append(node_id)
            
            response = self.get_response(node_id, failure_mode)
            final_state[f"{node_id}_output"] = response
        
        result = {
            "executed_nodes": executed_nodes,
            "iteration_count": iteration_count,
            "final_state": final_state,
            "completed": failure_mode == "normal",
            "_loop_terminated": failure_mode in ("loop", "infinite_loop"),
        }
        
        if failure_mode in ("corruption", "state_corruption"):
            result["final_state"]["corrupted"] = True
            result["final_state"]["ERROR"] = "CRITICAL_FAILURE"
        
        if failure_mode in ("drift", "persona_drift"):
            result["final_state"]["persona"] = "casual_unprofessional"
            result["final_state"]["emojis_detected"] = True
        
        return result
