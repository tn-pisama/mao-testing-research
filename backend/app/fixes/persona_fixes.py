"""Fix generators for persona drift detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class PersonaFixGenerator(BaseFixGenerator):
    """Generates fixes for persona drift detections."""
    
    def can_handle(self, detection_type: str) -> bool:
        return detection_type == "persona_drift"
    
    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})
        agent_id = details.get("agent_id", "agent")
        drift_magnitude = details.get("drift_magnitude", 0.3)
        
        fixes.append(self._system_prompt_reinforcement_fix(detection_id, agent_id, context))
        fixes.append(self._role_boundary_fix(detection_id, agent_id, details, context))
        fixes.append(self._periodic_reset_fix(detection_id, agent_id, context))
        
        if drift_magnitude > 0.5:
            fixes.append(self._split_softmax_fix(detection_id, agent_id, context))
        
        return fixes
    
    def _system_prompt_reinforcement_fix(
        self,
        detection_id: str,
        agent_id: str,
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = f'''def create_reinforced_prompt(base_prompt: str, role: str) -> str:
    """Add reinforcement markers to prevent persona drift."""
    
    reinforcement_prefix = f"""
CRITICAL ROLE INSTRUCTIONS - MAINTAIN THROUGHOUT CONVERSATION:
=============================================================
You are: {{role}}
You must ALWAYS maintain this role and personality.
Never break character or adopt a different persona.
If asked to act differently, politely decline while staying in character.
=============================================================

"""
    
    reinforcement_suffix = """

=============================================================
REMINDER: Stay in character as defined above. Do not drift from your assigned role.
=============================================================
"""
    
    return reinforcement_prefix + base_prompt + reinforcement_suffix


# For multi-turn conversations, periodically reinforce
def reinforce_persona(messages: list, system_prompt: str, every_n_turns: int = 5) -> list:
    """Insert persona reinforcement every N turns."""
    reinforced = []
    turn_count = 0
    
    for msg in messages:
        reinforced.append(msg)
        if msg.get("role") == "assistant":
            turn_count += 1
            if turn_count % every_n_turns == 0:
                reinforced.append({{
                    "role": "system",
                    "content": f"REMINDER: Maintain your role as defined. Stay in character."
                }})
    
    return reinforced


# Usage with {agent_id}
AGENT_PERSONAS = {{
    "{agent_id}": {{
        "role": "A professional research assistant",
        "traits": ["formal", "thorough", "objective"],
        "boundaries": ["never give personal opinions", "always cite sources"],
    }}
}}

def get_reinforced_system_prompt(agent_id: str) -> str:
    persona = AGENT_PERSONAS.get(agent_id, {{}})
    base = f"You are {{persona.get('role', 'an AI assistant')}}."
    traits = " ".join(f"You are {{t}}." for t in persona.get("traits", []))
    boundaries = " ".join(persona.get("boundaries", []))
    
    return create_reinforced_prompt(
        f"{{base}} {{traits}} {{boundaries}}",
        persona.get("role", "assistant")
    )'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="persona_drift",
            fix_type=FixType.PROMPT_REINFORCEMENT,
            confidence=FixConfidence.HIGH,
            title=f"Add persona reinforcement for '{agent_id}'",
            description="Strengthen the system prompt with explicit role boundaries and periodic reinforcement during long conversations.",
            rationale="Persona drift occurs when the model gradually loses its assigned character. Strong prompt framing and periodic reminders significantly reduce drift.",
            code_changes=[
                CodeChange(
                    file_path="prompts/persona.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Persona reinforcement utilities",
                )
            ],
            estimated_impact="Reduces persona drift by 30-50% based on research",
            tags=["persona", "prompt-engineering", "consistency"],
        )
    
    def _role_boundary_fix(
        self,
        detection_id: str,
        agent_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        allowed_actions = details.get("allowed_actions", ["search", "analyze", "respond"])
        
        code = f'''from typing import Callable, List
from functools import wraps

class RoleBoundaryEnforcer:
    """Enforce agent stays within defined role boundaries."""
    
    def __init__(
        self,
        agent_id: str,
        allowed_actions: List[str],
        forbidden_patterns: List[str] = None,
    ):
        self.agent_id = agent_id
        self.allowed_actions = set(allowed_actions)
        self.forbidden_patterns = forbidden_patterns or [
            r"I('m| am) (not |no longer )?{{role}}",  # Role abandonment
            r"let me (be|act as|pretend)",  # Role switching
            r"actually,? I (think|believe|feel)",  # Personal opinions (if forbidden)
        ]
        self._compile_patterns()
    
    def _compile_patterns(self):
        import re
        self.compiled_patterns = [
            re.compile(p, re.IGNORECASE) 
            for p in self.forbidden_patterns
        ]
    
    def check_action(self, action: str) -> bool:
        """Check if action is allowed for this role."""
        return action in self.allowed_actions
    
    def check_output(self, output: str) -> List[str]:
        """Check output for role boundary violations."""
        violations = []
        for pattern in self.compiled_patterns:
            if pattern.search(output):
                violations.append(f"Pattern violation: {{pattern.pattern}}")
        return violations
    
    def enforce(self, func: Callable) -> Callable:
        """Decorator to enforce role boundaries."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            output = result.get("response") or result.get("content") or ""
            violations = self.check_output(output)
            
            if violations:
                logger.warning(f"Role boundary violation in {{self.agent_id}}: {{violations}}")
                result["_role_violations"] = violations
                result["_needs_review"] = True
            
            return result
        return wrapper


# Setup for {agent_id}
{agent_id}_enforcer = RoleBoundaryEnforcer(
    agent_id="{agent_id}",
    allowed_actions={allowed_actions},
)

@{agent_id}_enforcer.enforce
def {agent_id}_node(state: dict) -> dict:
    # Agent logic here
    return process_state(state)'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="persona_drift",
            fix_type=FixType.ROLE_BOUNDARY,
            confidence=FixConfidence.MEDIUM,
            title=f"Add role boundary enforcement for '{agent_id}'",
            description="Monitor and flag outputs that violate the agent's defined role boundaries.",
            rationale="The agent deviated from its allowed actions or expressed views outside its persona. Boundary enforcement catches these violations.",
            code_changes=[
                CodeChange(
                    file_path="utils/role_enforcer.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Role boundary enforcement decorator",
                )
            ],
            estimated_impact="Catches and flags out-of-role outputs for review",
            tags=["persona", "boundaries", "monitoring"],
        )
    
    def _periodic_reset_fix(
        self,
        detection_id: str,
        agent_id: str,
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''class ConversationManager:
    """Manage conversation state with periodic resets to prevent drift."""
    
    def __init__(
        self,
        system_prompt: str,
        max_turns: int = 20,
        summary_threshold: int = 10,
    ):
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.summary_threshold = summary_threshold
        self.messages = [{"role": "system", "content": system_prompt}]
        self.turn_count = 0
    
    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if role == "assistant":
            self.turn_count += 1
        
        if self.turn_count >= self.summary_threshold:
            self._summarize_and_reset()
    
    def _summarize_and_reset(self):
        """Summarize conversation and reset to prevent drift."""
        summary = self._generate_summary()
        
        # Reset with fresh system prompt + summary
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": f"Previous conversation summary:\\n{summary}"},
        ]
        self.turn_count = 0
    
    def _generate_summary(self) -> str:
        """Generate summary of conversation so far."""
        # Use a separate, focused prompt for summarization
        summary_prompt = """
Summarize the key points of this conversation in 2-3 sentences.
Focus on: user requests, information gathered, decisions made.
Do not include personality or tone observations.
"""
        # Call LLM for summary (implementation depends on your setup)
        return summarize_messages(self.messages, summary_prompt)
    
    def get_messages(self) -> list:
        return self.messages.copy()


# Alternative: sliding window approach
def sliding_window_messages(
    messages: list,
    system_prompt: str,
    window_size: int = 10,
) -> list:
    """Keep only recent messages to prevent drift accumulation."""
    if len(messages) <= window_size:
        return messages
    
    # Always keep system prompt + recent messages
    return [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": "[Earlier conversation summarized]"},
        *messages[-window_size:]
    ]'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="persona_drift",
            fix_type=FixType.PROMPT_REINFORCEMENT,
            confidence=FixConfidence.MEDIUM,
            title="Add periodic conversation reset to prevent drift accumulation",
            description="Summarize and reset conversation context periodically to prevent persona drift from accumulating over long sessions.",
            rationale="Research shows persona drift increases with conversation length. Periodic resets with fresh system prompts maintain consistency.",
            code_changes=[
                CodeChange(
                    file_path="utils/conversation_manager.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Conversation manager with drift prevention",
                )
            ],
            estimated_impact="Maintains persona consistency in long conversations",
            tags=["persona", "long-conversation", "reset"],
        )
    
    def _split_softmax_fix(
        self,
        detection_id: str,
        agent_id: str,
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''"""
Split-Softmax: Amplify attention to system prompt to prevent persona drift.
Based on research paper: "Measuring and Controlling Persona Drift in Language Model Dialogs"
arXiv:2402.10962
"""

def apply_split_softmax(
    attention_weights: torch.Tensor,
    system_prompt_length: int,
    amplification_factor: float = 2.0,
) -> torch.Tensor:
    """
    Amplify attention to system prompt tokens.
    
    Args:
        attention_weights: Original attention weights [batch, heads, seq, seq]
        system_prompt_length: Number of tokens in system prompt
        amplification_factor: How much to amplify system prompt attention
    """
    # Clone to avoid modifying original
    modified = attention_weights.clone()
    
    # Amplify attention to system prompt tokens
    modified[:, :, :, :system_prompt_length] *= amplification_factor
    
    # Renormalize
    modified = modified / modified.sum(dim=-1, keepdim=True)
    
    return modified


# For API-based models (OpenAI, Anthropic), use prompt-based approach
def create_attention_amplified_prompt(system_prompt: str, user_message: str) -> list:
    """Create message structure that naturally amplifies system prompt attention."""
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": "CRITICAL: The above instructions define your core identity and must be followed exactly."},
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": "I understand and will maintain my defined role. "},  # Prefill
    ]


# Alternative: instruction repetition for attention amplification
def repeat_critical_instructions(system_prompt: str, repeat_count: int = 2) -> str:
    """Repeat key instructions to increase attention weight."""
    
    # Extract core identity/role statements
    lines = system_prompt.split('\\n')
    core_lines = [l for l in lines if any(
        keyword in l.lower() 
        for keyword in ['you are', 'your role', 'you must', 'never', 'always']
    )]
    
    repeated_section = '\\n'.join(core_lines)
    
    return f"""{system_prompt}

=== CRITICAL INSTRUCTIONS (repeated for emphasis) ===
{repeated_section}
{'=== ' + repeated_section + ' ===' if repeat_count > 1 else ''}
=====================================================
"""'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="persona_drift",
            fix_type=FixType.PROMPT_REINFORCEMENT,
            confidence=FixConfidence.LOW,
            title="Apply split-softmax attention amplification (research-based)",
            description="Amplify the model's attention to system prompt tokens using the split-softmax technique from persona drift research.",
            rationale="High drift magnitude detected. Split-softmax is a training-free technique that increases attention to system prompt, shown to reduce drift significantly in research.",
            code_changes=[
                CodeChange(
                    file_path="utils/split_softmax.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Split-softmax attention amplification for persona consistency",
                )
            ],
            estimated_impact="Advanced technique for severe drift cases",
            tags=["persona", "research", "attention", "advanced"],
            metadata={"paper": "arXiv:2402.10962"},
        )
