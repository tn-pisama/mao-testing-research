"""
Knowledge Bases for MAST Detection.

Provides implicit context that's missing from traces but critical for detection:
- Cost Database: API pricing for F3 (Resource Allocation) detection
- Tool Catalog: Tool signatures for F4 (Tool Provision) detection
- Role Specifications: Role definitions for F9 (Role Usurpation) detection

These knowledge bases augment the LLM prompts with domain knowledge that
traces don't contain but are essential for accurate failure detection.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# COST DATABASE (F3: Resource Allocation)
# =============================================================================

@dataclass
class ModelPricing:
    """Pricing information for an LLM model."""
    model_id: str
    provider: str
    input_cost_per_1k: float  # USD per 1K input tokens
    output_cost_per_1k: float  # USD per 1K output tokens
    context_window: int  # Max tokens
    typical_latency_ms: int  # Typical response latency
    rate_limit_rpm: int = 60  # Requests per minute

    @property
    def cost_ratio(self) -> float:
        """Output/input cost ratio (for detecting expensive outputs)."""
        return self.output_cost_per_1k / self.input_cost_per_1k if self.input_cost_per_1k > 0 else 1.0


class CostDatabase:
    """
    Database of LLM API costs for resource allocation detection.

    Used to detect F3 failures where:
    - Agents use expensive models when cheaper ones suffice
    - Token consumption is excessive for the task
    - Rate limits are being hit due to poor orchestration
    """

    # Pricing as of Dec 2024 (update regularly)
    MODELS: Dict[str, ModelPricing] = {
        # OpenAI
        "gpt-4o": ModelPricing("gpt-4o", "openai", 0.0025, 0.01, 128000, 500),
        "gpt-4o-mini": ModelPricing("gpt-4o-mini", "openai", 0.00015, 0.0006, 128000, 300),
        "gpt-4-turbo": ModelPricing("gpt-4-turbo", "openai", 0.01, 0.03, 128000, 800),
        "gpt-4": ModelPricing("gpt-4", "openai", 0.03, 0.06, 8192, 1000),
        "gpt-3.5-turbo": ModelPricing("gpt-3.5-turbo", "openai", 0.0005, 0.0015, 16385, 200),
        "o1-preview": ModelPricing("o1-preview", "openai", 0.015, 0.06, 128000, 10000),
        "o1-mini": ModelPricing("o1-mini", "openai", 0.003, 0.012, 128000, 3000),

        # Anthropic
        "claude-3-opus": ModelPricing("claude-3-opus", "anthropic", 0.015, 0.075, 200000, 2000),
        "claude-opus-4": ModelPricing("claude-opus-4", "anthropic", 0.015, 0.075, 200000, 2000),
        "claude-3-5-sonnet": ModelPricing("claude-3-5-sonnet", "anthropic", 0.003, 0.015, 200000, 800),
        "claude-sonnet-4": ModelPricing("claude-sonnet-4", "anthropic", 0.003, 0.015, 200000, 800),
        "claude-3-haiku": ModelPricing("claude-3-haiku", "anthropic", 0.00025, 0.00125, 200000, 200),

        # Google
        "gemini-1.5-pro": ModelPricing("gemini-1.5-pro", "google", 0.00125, 0.005, 1000000, 600),
        "gemini-1.5-flash": ModelPricing("gemini-1.5-flash", "google", 0.000075, 0.0003, 1000000, 150),
        "gemini-2.0-flash": ModelPricing("gemini-2.0-flash", "google", 0.0001, 0.0004, 1000000, 100),

        # Mistral
        "mistral-large": ModelPricing("mistral-large", "mistral", 0.002, 0.006, 128000, 400),
        "mistral-small": ModelPricing("mistral-small", "mistral", 0.0002, 0.0006, 32000, 150),
        "codestral": ModelPricing("codestral", "mistral", 0.0002, 0.0006, 32000, 200),

        # Open Source (via Together/Groq)
        "llama-3.1-405b": ModelPricing("llama-3.1-405b", "together", 0.005, 0.015, 128000, 1500),
        "llama-3.1-70b": ModelPricing("llama-3.1-70b", "together", 0.0009, 0.0009, 128000, 300),
        "llama-3.1-8b": ModelPricing("llama-3.1-8b", "together", 0.0002, 0.0002, 128000, 100),
    }

    # Cost thresholds for anomaly detection
    THRESHOLDS = {
        "high_cost_per_request": 0.10,  # $0.10 per request is expensive
        "excessive_token_ratio": 5.0,  # Output > 5x input is suspicious
        "rate_limit_warning_pct": 0.8,  # 80% of rate limit = warning
    }

    @classmethod
    def get_pricing(cls, model_id: str) -> Optional[ModelPricing]:
        """Get pricing for a model, with fuzzy matching."""
        # Exact match
        if model_id in cls.MODELS:
            return cls.MODELS[model_id]

        # Fuzzy match (handle version suffixes like gpt-4-0613)
        model_lower = model_id.lower()
        for key, pricing in cls.MODELS.items():
            if key in model_lower or model_lower.startswith(key.split("-")[0]):
                return pricing

        return None

    @classmethod
    def estimate_cost(cls, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a single LLM call."""
        pricing = cls.get_pricing(model_id)
        if pricing is None:
            logger.warning(f"Unknown model for pricing: {model_id}")
            return 0.0

        input_cost = (input_tokens / 1000) * pricing.input_cost_per_1k
        output_cost = (output_tokens / 1000) * pricing.output_cost_per_1k
        return input_cost + output_cost

    @classmethod
    def is_expensive_for_task(cls, model_id: str, task_complexity: str) -> bool:
        """Check if model is over-spec for task complexity."""
        pricing = cls.get_pricing(model_id)
        if pricing is None:
            return False

        # Define complexity tiers
        complexity_thresholds = {
            "simple": 0.001,  # Simple tasks shouldn't need expensive models
            "moderate": 0.005,
            "complex": 0.015,
            "expert": float("inf"),
        }

        threshold = complexity_thresholds.get(task_complexity, 0.01)
        return pricing.input_cost_per_1k > threshold

    @classmethod
    def to_prompt_context(cls) -> str:
        """Generate context string for LLM prompts."""
        lines = ["## LLM Cost Reference\n"]
        lines.append("| Model | Provider | Input $/1K | Output $/1K | Context |")
        lines.append("|-------|----------|------------|-------------|---------|")
        for model_id, p in sorted(cls.MODELS.items(), key=lambda x: x[1].input_cost_per_1k):
            lines.append(f"| {model_id} | {p.provider} | ${p.input_cost_per_1k:.4f} | ${p.output_cost_per_1k:.4f} | {p.context_window:,} |")
        lines.append("\n**Cost Anomaly Thresholds:**")
        for key, val in cls.THRESHOLDS.items():
            lines.append(f"- {key}: {val}")
        return "\n".join(lines)


# =============================================================================
# TOOL CATALOG (F4: Tool Provision)
# =============================================================================

@dataclass
class ToolSpec:
    """Specification for an agent tool."""
    name: str
    description: str
    parameters: Dict[str, Any]
    required_params: List[str]
    return_type: str
    category: str  # e.g., "search", "code", "data", "communication"
    constraints: List[str] = field(default_factory=list)
    typical_latency_ms: int = 1000
    cost_per_call: float = 0.0  # If API-based


class ToolCategory(Enum):
    SEARCH = "search"
    CODE = "code"
    DATA = "data"
    COMMUNICATION = "communication"
    FILE = "file"
    BROWSER = "browser"
    CUSTOM = "custom"


class ToolCatalog:
    """
    Catalog of standard agent tools for tool provision detection.

    Used to detect F4 failures where:
    - Required tools are missing from agent configuration
    - Wrong tool is selected for a task
    - Tool parameters are misused
    - Tool constraints are violated
    """

    COMMON_TOOLS: Dict[str, ToolSpec] = {
        # Search Tools
        "web_search": ToolSpec(
            name="web_search",
            description="Search the web for information",
            parameters={"query": "str", "num_results": "int"},
            required_params=["query"],
            return_type="list[SearchResult]",
            category="search",
            constraints=["Query should be specific", "Avoid PII in queries"],
        ),
        "wikipedia": ToolSpec(
            name="wikipedia",
            description="Search Wikipedia for factual information",
            parameters={"query": "str"},
            required_params=["query"],
            return_type="str",
            category="search",
        ),

        # Code Tools
        "python_repl": ToolSpec(
            name="python_repl",
            description="Execute Python code",
            parameters={"code": "str"},
            required_params=["code"],
            return_type="str",
            category="code",
            constraints=["No file system access", "No network access", "Timeout 30s"],
        ),
        "code_interpreter": ToolSpec(
            name="code_interpreter",
            description="Execute code with data analysis capabilities",
            parameters={"code": "str", "files": "list[str]"},
            required_params=["code"],
            return_type="ExecutionResult",
            category="code",
        ),

        # Data Tools
        "sql_query": ToolSpec(
            name="sql_query",
            description="Execute SQL query on connected database",
            parameters={"query": "str", "database": "str"},
            required_params=["query"],
            return_type="DataFrame",
            category="data",
            constraints=["Read-only queries only", "Max 1000 rows returned"],
        ),
        "api_call": ToolSpec(
            name="api_call",
            description="Make HTTP API request",
            parameters={"url": "str", "method": "str", "body": "dict"},
            required_params=["url"],
            return_type="Response",
            category="data",
            constraints=["Allowed domains only", "Rate limited"],
        ),

        # File Tools
        "read_file": ToolSpec(
            name="read_file",
            description="Read contents of a file",
            parameters={"path": "str"},
            required_params=["path"],
            return_type="str",
            category="file",
            constraints=["Sandboxed directory only"],
        ),
        "write_file": ToolSpec(
            name="write_file",
            description="Write contents to a file",
            parameters={"path": "str", "content": "str"},
            required_params=["path", "content"],
            return_type="bool",
            category="file",
            constraints=["Sandboxed directory only", "Max file size 10MB"],
        ),

        # Browser Tools
        "browse_web": ToolSpec(
            name="browse_web",
            description="Browse a webpage and extract content",
            parameters={"url": "str"},
            required_params=["url"],
            return_type="WebPage",
            category="browser",
            constraints=["Allowed domains only"],
            typical_latency_ms=3000,
        ),

        # Communication Tools
        "send_email": ToolSpec(
            name="send_email",
            description="Send an email",
            parameters={"to": "str", "subject": "str", "body": "str"},
            required_params=["to", "subject", "body"],
            return_type="bool",
            category="communication",
            constraints=["Requires approval for external recipients"],
        ),
    }

    # Task to required tools mapping
    TASK_TOOL_MAP: Dict[str, List[str]] = {
        "research": ["web_search", "wikipedia", "browse_web"],
        "data_analysis": ["python_repl", "sql_query", "code_interpreter"],
        "coding": ["python_repl", "code_interpreter", "read_file", "write_file"],
        "information_retrieval": ["web_search", "wikipedia", "read_file"],
        "communication": ["send_email"],
        "web_scraping": ["browse_web", "web_search"],
    }

    @classmethod
    def get_tool(cls, name: str) -> Optional[ToolSpec]:
        """Get tool specification by name."""
        return cls.COMMON_TOOLS.get(name)

    @classmethod
    def get_required_tools(cls, task_type: str) -> List[str]:
        """Get required tools for a task type."""
        return cls.TASK_TOOL_MAP.get(task_type, [])

    @classmethod
    def validate_tool_call(cls, tool_name: str, parameters: Dict[str, Any]) -> List[str]:
        """Validate a tool call and return list of violations."""
        spec = cls.get_tool(tool_name)
        if spec is None:
            return [f"Unknown tool: {tool_name}"]

        violations = []

        # Check required parameters
        for param in spec.required_params:
            if param not in parameters:
                violations.append(f"Missing required parameter: {param}")

        # Check parameter types (basic check)
        for param, value in parameters.items():
            if param in spec.parameters:
                expected_type = spec.parameters[param]
                # Basic type validation
                if expected_type == "str" and not isinstance(value, str):
                    violations.append(f"Parameter {param} should be string")
                elif expected_type == "int" and not isinstance(value, int):
                    violations.append(f"Parameter {param} should be integer")

        return violations

    @classmethod
    def to_prompt_context(cls) -> str:
        """Generate context string for LLM prompts."""
        lines = ["## Available Agent Tools\n"]
        for category in ToolCategory:
            cat_tools = [t for t in cls.COMMON_TOOLS.values() if t.category == category.value]
            if cat_tools:
                lines.append(f"### {category.value.title()}\n")
                for tool in cat_tools:
                    lines.append(f"**{tool.name}**: {tool.description}")
                    lines.append(f"  - Parameters: {json.dumps(tool.parameters)}")
                    lines.append(f"  - Required: {tool.required_params}")
                    if tool.constraints:
                        lines.append(f"  - Constraints: {tool.constraints}")
                    lines.append("")
        return "\n".join(lines)


# =============================================================================
# ROLE SPECIFICATIONS (F9: Role Usurpation)
# =============================================================================

@dataclass
class RoleSpec:
    """Specification for an agent role."""
    name: str
    description: str
    responsibilities: List[str]
    capabilities: List[str]  # Tools/actions this role can use
    prohibited_actions: List[str]
    escalation_targets: List[str]  # Roles this can escalate to
    authority_level: int  # 1-10, higher = more authority


class RoleSpecs:
    """
    Role specifications for multi-agent systems.

    Used to detect F9 failures where:
    - An agent acts outside its defined role
    - Unauthorized decision-making occurs
    - Role boundaries are violated
    - Authority hierarchies are bypassed
    """

    # Common roles across multi-agent frameworks
    ROLES: Dict[str, RoleSpec] = {
        # ChatDev / MetaGPT style roles
        "product_manager": RoleSpec(
            name="Product Manager",
            description="Defines product requirements and priorities",
            responsibilities=[
                "Gather and document requirements",
                "Prioritize features",
                "Communicate with stakeholders",
                "Define acceptance criteria",
            ],
            capabilities=["requirement_doc", "user_story", "prioritization"],
            prohibited_actions=["write_code", "deploy", "access_production"],
            escalation_targets=["ceo", "cto"],
            authority_level=6,
        ),
        "architect": RoleSpec(
            name="Software Architect",
            description="Designs system architecture and technical approach",
            responsibilities=[
                "Design system architecture",
                "Select technologies",
                "Define interfaces",
                "Review designs",
            ],
            capabilities=["design_doc", "tech_selection", "interface_definition"],
            prohibited_actions=["deploy", "access_production_data"],
            escalation_targets=["cto"],
            authority_level=7,
        ),
        "developer": RoleSpec(
            name="Developer",
            description="Implements code based on specifications",
            responsibilities=[
                "Write code",
                "Fix bugs",
                "Write unit tests",
                "Code review",
            ],
            capabilities=["write_code", "read_file", "python_repl"],
            prohibited_actions=["deploy", "change_requirements", "access_production"],
            escalation_targets=["architect", "tech_lead"],
            authority_level=4,
        ),
        "qa_engineer": RoleSpec(
            name="QA Engineer",
            description="Tests and validates software quality",
            responsibilities=[
                "Write test cases",
                "Execute tests",
                "Report bugs",
                "Validate fixes",
            ],
            capabilities=["test_execution", "bug_report", "read_code"],
            prohibited_actions=["write_production_code", "deploy"],
            escalation_targets=["qa_lead", "product_manager"],
            authority_level=4,
        ),
        "devops": RoleSpec(
            name="DevOps Engineer",
            description="Manages infrastructure and deployments",
            responsibilities=[
                "Manage CI/CD",
                "Deploy applications",
                "Monitor systems",
                "Manage infrastructure",
            ],
            capabilities=["deploy", "infrastructure", "monitoring"],
            prohibited_actions=["change_business_logic", "approve_requirements"],
            escalation_targets=["sre", "cto"],
            authority_level=6,
        ),

        # Supervisor / Orchestrator roles
        "supervisor": RoleSpec(
            name="Supervisor",
            description="Coordinates and delegates tasks to workers",
            responsibilities=[
                "Assign tasks",
                "Monitor progress",
                "Resolve conflicts",
                "Aggregate results",
            ],
            capabilities=["task_delegation", "status_monitoring", "result_aggregation"],
            prohibited_actions=["execute_worker_tasks", "override_specialist_decisions"],
            escalation_targets=["human"],
            authority_level=8,
        ),
        "worker": RoleSpec(
            name="Worker",
            description="Executes assigned tasks",
            responsibilities=[
                "Execute assigned task",
                "Report results",
                "Request clarification",
            ],
            capabilities=["task_execution", "result_reporting"],
            prohibited_actions=["assign_tasks", "override_supervisor", "access_other_tasks"],
            escalation_targets=["supervisor"],
            authority_level=3,
        ),

        # Research / Analysis roles
        "researcher": RoleSpec(
            name="Researcher",
            description="Conducts research and gathers information",
            responsibilities=[
                "Search for information",
                "Analyze sources",
                "Synthesize findings",
                "Cite sources",
            ],
            capabilities=["web_search", "wikipedia", "browse_web", "read_file"],
            prohibited_actions=["make_decisions", "take_actions", "modify_data"],
            escalation_targets=["analyst", "supervisor"],
            authority_level=3,
        ),
        "analyst": RoleSpec(
            name="Analyst",
            description="Analyzes data and provides insights",
            responsibilities=[
                "Analyze data",
                "Generate reports",
                "Identify patterns",
                "Recommend actions",
            ],
            capabilities=["sql_query", "python_repl", "data_visualization"],
            prohibited_actions=["make_business_decisions", "modify_production_data"],
            escalation_targets=["decision_maker", "supervisor"],
            authority_level=5,
        ),
    }

    # Framework-specific role mappings
    FRAMEWORK_ROLES: Dict[str, Dict[str, str]] = {
        "chatdev": {
            "Chief Executive Officer": "supervisor",
            "Chief Product Officer": "product_manager",
            "Counselor": "analyst",
            "Chief Technology Officer": "architect",
            "Programmer": "developer",
            "Code Reviewer": "qa_engineer",
            "Software Test Engineer": "qa_engineer",
        },
        "metagpt": {
            "ProductManager": "product_manager",
            "Architect": "architect",
            "ProjectManager": "supervisor",
            "Engineer": "developer",
            "QaEngineer": "qa_engineer",
        },
        "autogen": {
            "assistant": "worker",
            "user_proxy": "supervisor",
            "groupchat_manager": "supervisor",
        },
        "crewai": {
            "researcher": "researcher",
            "writer": "developer",
            "analyst": "analyst",
        },
    }

    @classmethod
    def get_role(cls, name: str) -> Optional[RoleSpec]:
        """Get role specification by name."""
        return cls.ROLES.get(name.lower().replace(" ", "_"))

    @classmethod
    def map_framework_role(cls, framework: str, role_name: str) -> Optional[RoleSpec]:
        """Map framework-specific role name to standard role."""
        framework_map = cls.FRAMEWORK_ROLES.get(framework.lower(), {})
        standard_role = framework_map.get(role_name)
        if standard_role:
            return cls.get_role(standard_role)
        return None

    @classmethod
    def check_authority(cls, actor_role: str, action: str, target_role: Optional[str] = None) -> Dict[str, Any]:
        """
        Check if a role has authority to perform an action.

        Returns dict with:
        - authorized: bool
        - reason: str
        - violation_type: str (if not authorized)
        """
        role_spec = cls.get_role(actor_role)
        if role_spec is None:
            return {"authorized": False, "reason": f"Unknown role: {actor_role}", "violation_type": "unknown_role"}

        # Check prohibited actions
        if action in role_spec.prohibited_actions:
            return {
                "authorized": False,
                "reason": f"{actor_role} is prohibited from {action}",
                "violation_type": "prohibited_action",
            }

        # Check authority over target role
        if target_role:
            target_spec = cls.get_role(target_role)
            if target_spec and target_spec.authority_level >= role_spec.authority_level:
                return {
                    "authorized": False,
                    "reason": f"{actor_role} (level {role_spec.authority_level}) cannot override {target_role} (level {target_spec.authority_level})",
                    "violation_type": "authority_violation",
                }

        return {"authorized": True, "reason": "Action within role boundaries"}

    @classmethod
    def to_prompt_context(cls) -> str:
        """Generate context string for LLM prompts."""
        lines = ["## Agent Role Specifications\n"]
        for name, role in cls.ROLES.items():
            lines.append(f"### {role.name} (Authority Level: {role.authority_level}/10)\n")
            lines.append(f"*{role.description}*\n")
            lines.append("**Responsibilities:**")
            for r in role.responsibilities:
                lines.append(f"- {r}")
            lines.append("\n**Capabilities:**")
            lines.append(f"- {', '.join(role.capabilities)}")
            lines.append("\n**Prohibited Actions:**")
            lines.append(f"- {', '.join(role.prohibited_actions)}")
            lines.append("\n**Can Escalate To:**")
            lines.append(f"- {', '.join(role.escalation_targets)}")
            lines.append("")
        return "\n".join(lines)


# =============================================================================
# KNOWLEDGE AUGMENTATION FOR LLM PROMPTS
# =============================================================================

def get_knowledge_context(failure_modes: List[str]) -> str:
    """
    Get relevant knowledge base context for given failure modes.

    Args:
        failure_modes: List of MAST failure mode IDs (e.g., ["F3", "F4", "F9"])

    Returns:
        Formatted context string for LLM prompt augmentation
    """
    contexts = []

    for mode in failure_modes:
        if mode == "F3":  # Resource Allocation
            contexts.append(CostDatabase.to_prompt_context())
        elif mode == "F4":  # Tool Provision
            contexts.append(ToolCatalog.to_prompt_context())
        elif mode == "F9":  # Role Usurpation
            contexts.append(RoleSpecs.to_prompt_context())

    if not contexts:
        return ""

    return "\n\n---\n\n".join(contexts)


def get_full_knowledge_context() -> str:
    """Get full knowledge base context for all modes."""
    return get_knowledge_context(["F3", "F4", "F9"])
