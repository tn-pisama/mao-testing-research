"""Workflow factories for E2E testing."""

import secrets
from typing import Dict, Any, List, Optional


class LangGraphWorkflowFactory:
    """Factory for creating LangGraph test workflows."""
    
    @staticmethod
    def create_research_workflow() -> Dict[str, Any]:
        """Standard research workflow: researcher -> analyst -> writer."""
        return {
            "name": f"research_workflow_{secrets.token_hex(4)}",
            "framework": "langgraph",
            "nodes": [
                {
                    "id": "researcher",
                    "name": "Researcher",
                    "type": "llm",
                    "parameters": {
                        "model": "gpt-4o-mini",
                        "messages": {
                            "values": [{"role": "system", "content": "You are a research specialist."}]
                        }
                    }
                },
                {
                    "id": "analyst",
                    "name": "Analyst",
                    "type": "llm",
                    "parameters": {"model": "gpt-4o-mini"}
                },
                {
                    "id": "writer",
                    "name": "Writer",
                    "type": "llm",
                    "parameters": {
                        "model": "gpt-4o-mini",
                        "messages": {
                            "values": [{"role": "system", "content": "You are a professional technical writer."}]
                        }
                    }
                }
            ],
            "connections": {
                "researcher": [{"node": "analyst"}],
                "analyst": [{"node": "writer"}]
            },
            "settings": {}
        }
    
    @staticmethod
    def create_loop_prone_workflow() -> Dict[str, Any]:
        """Workflow with circular dependency prone to infinite loops."""
        workflow = LangGraphWorkflowFactory.create_research_workflow()
        workflow["connections"]["analyst"].append({"node": "researcher"})
        workflow["name"] = f"loop_prone_{secrets.token_hex(4)}"
        return workflow
    
    @staticmethod
    def create_complex_workflow(num_agents: int = 5) -> Dict[str, Any]:
        """Complex workflow with multiple agents in a chain."""
        nodes = []
        connections = {}
        
        for i in range(num_agents):
            node_id = f"agent_{i}"
            nodes.append({
                "id": node_id,
                "name": f"Agent {i}",
                "type": "llm",
                "parameters": {"model": "gpt-4o-mini"}
            })
            if i < num_agents - 1:
                connections[node_id] = [{"node": f"agent_{i+1}"}]
        
        return {
            "name": f"complex_workflow_{num_agents}",
            "framework": "langgraph",
            "nodes": nodes,
            "connections": connections,
            "settings": {}
        }


class CrewAIWorkflowFactory:
    """Factory for CrewAI test workflows."""
    
    @staticmethod
    def create_content_crew() -> Dict[str, Any]:
        """Standard content creation crew."""
        return {
            "name": f"content_crew_{secrets.token_hex(4)}",
            "framework": "crewai",
            "nodes": [
                {
                    "id": "researcher",
                    "name": "Senior Researcher",
                    "type": "agent",
                    "parameters": {
                        "role": "Research Specialist",
                        "goal": "Conduct comprehensive research",
                        "backstory": "Expert researcher with academic background"
                    }
                },
                {
                    "id": "analyst",
                    "name": "Research Analyst",
                    "type": "agent",
                    "parameters": {
                        "role": "Data Analyst",
                        "goal": "Analyze research findings",
                        "backstory": "Senior analyst with expertise in synthesis"
                    }
                },
                {
                    "id": "writer",
                    "name": "Technical Writer",
                    "type": "agent",
                    "parameters": {
                        "role": "Content Writer",
                        "goal": "Create professional content",
                        "backstory": "Award-winning technical writer"
                    }
                }
            ],
            "connections": {
                "researcher": [{"node": "analyst"}],
                "analyst": [{"node": "writer"}]
            },
            "settings": {"process": "sequential"}
        }
    
    @staticmethod
    def create_loop_prone_crew() -> Dict[str, Any]:
        """Crew prone to infinite delegation loops."""
        crew = CrewAIWorkflowFactory.create_content_crew()
        crew["settings"]["allow_delegation"] = True
        crew["connections"]["analyst"].append({"node": "researcher"})
        crew["name"] = f"loop_prone_crew_{secrets.token_hex(4)}"
        return crew


class N8nWorkflowFactory:
    """Factory for n8n test workflows."""
    
    @staticmethod
    def create_research_workflow() -> Dict[str, Any]:
        """Standard n8n research workflow."""
        return {
            "name": f"n8n_research_{secrets.token_hex(4)}",
            "framework": "n8n",
            "nodes": [
                {
                    "id": "webhook",
                    "name": "Webhook Trigger",
                    "type": "n8n-nodes-base.webhook",
                    "parameters": {"httpMethod": "POST", "path": "research"}
                },
                {
                    "id": "openai",
                    "name": "OpenAI Research",
                    "type": "n8n-nodes-base.openAi",
                    "parameters": {"model": "gpt-4o-mini"}
                },
                {
                    "id": "processor",
                    "name": "Data Processor",
                    "type": "n8n-nodes-base.code",
                    "parameters": {}
                },
                {
                    "id": "respond",
                    "name": "Send Response",
                    "type": "n8n-nodes-base.respondToWebhook",
                    "parameters": {}
                }
            ],
            "connections": {
                "webhook": [{"node": "openai"}],
                "openai": [{"node": "processor"}],
                "processor": [{"node": "respond"}]
            },
            "settings": {}
        }
    
    @staticmethod
    def create_loop_workflow() -> Dict[str, Any]:
        """n8n workflow with loop behavior."""
        workflow = N8nWorkflowFactory.create_research_workflow()
        workflow["nodes"].append({
            "id": "check",
            "name": "Check Completion",
            "type": "n8n-nodes-base.if",
            "parameters": {"conditions": {"boolean": [{"value1": True}]}}
        })
        workflow["connections"]["processor"] = [{"node": "check"}]
        workflow["connections"]["check"] = [{"node": "openai"}, {"node": "respond"}]
        workflow["name"] = f"n8n_loop_{secrets.token_hex(4)}"
        return workflow


class WorkflowFactory:
    """Unified workflow factory for all frameworks."""
    
    def __init__(self):
        self.langgraph = LangGraphWorkflowFactory()
        self.crewai = CrewAIWorkflowFactory()
        self.n8n = N8nWorkflowFactory()
    
    def create_workflow(
        self,
        framework: str,
        workflow_type: str = "normal",
        num_agents: int = 3
    ) -> Dict[str, Any]:
        """Create a workflow for the specified framework and type."""
        factories = {
            "langgraph": {
                "normal": self.langgraph.create_research_workflow,
                "loop": self.langgraph.create_loop_prone_workflow,
                "complex": lambda: self.langgraph.create_complex_workflow(num_agents),
            },
            "crewai": {
                "normal": self.crewai.create_content_crew,
                "loop": self.crewai.create_loop_prone_crew,
            },
            "n8n": {
                "normal": self.n8n.create_research_workflow,
                "loop": self.n8n.create_loop_workflow,
            }
        }
        
        framework_factories = factories.get(framework, factories["langgraph"])
        factory_fn = framework_factories.get(workflow_type, framework_factories["normal"])
        return factory_fn()
