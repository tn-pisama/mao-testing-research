"""Fix generators for persona drift detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import (
    FixSuggestion, FixType, FixConfidence, CodeChange,
    ReinforcementLevel, REINFORCEMENT_CONFIG,
)


class PersonaFixGenerator(BaseFixGenerator):
    """Generates fixes for persona drift detections."""
    
    def can_handle(self, detection_type: str) -> bool:
        return detection_type == "persona_drift"
    
    def _determine_reinforcement_level(
        self,
        drift_magnitude: float,
        recurrence_count: int = 0,
        role_type: str = "assistant",
    ) -> ReinforcementLevel:
        """Determine appropriate reinforcement level based on severity."""
        if drift_magnitude < 0.2 and recurrence_count == 0:
            return ReinforcementLevel.LIGHT
        elif drift_magnitude < 0.4 or (drift_magnitude < 0.5 and role_type == "creative"):
            return ReinforcementLevel.MODERATE
        else:
            return ReinforcementLevel.AGGRESSIVE
    
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
        recurrence_count = details.get("recurrence_count", 0)
        role_type = details.get("role_type", "assistant")
        
        level = self._determine_reinforcement_level(
            drift_magnitude, recurrence_count, role_type
        )
        config = REINFORCEMENT_CONFIG[level]
        
        fixes.append(self._gradual_reinforcement_fix(
            detection_id, agent_id, level, config, context
        ))
        
        if level in (ReinforcementLevel.MODERATE, ReinforcementLevel.AGGRESSIVE):
            fixes.append(self._role_boundary_fix(detection_id, agent_id, details, context))
        
        if level == ReinforcementLevel.AGGRESSIVE:
            fixes.append(self._periodic_reset_fix(detection_id, agent_id, context))
        
        if drift_magnitude >= 0.6:
            fixes.append(self._split_softmax_fix(detection_id, agent_id, context))
        
        return fixes
    
    def _gradual_reinforcement_fix(
        self,
        detection_id: str,
        agent_id: str,
        level: ReinforcementLevel,
        config: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        """Generate a fix with gradual reinforcement based on severity."""
        
        if level == ReinforcementLevel.LIGHT:
            code = f'''def create_light_reinforcement(base_prompt: str, role: str) -> str:
    """Light reinforcement - minimal changes, lowest regression risk."""
    
    return f"""{{base_prompt}}

---
Remember: You are {{role}}. Stay in character.
"""


# Usage with {agent_id}
system_prompt = create_light_reinforcement(
    base_prompt=original_system_prompt,
    role="{agent_id}"
)'''
            title = f"Light persona reinforcement for '{agent_id}'"
            description = "Add minimal reinforcement to reduce drift with very low regression risk (2%)."
            
        elif level == ReinforcementLevel.MODERATE:
            reminder_interval = config.get("reminder_interval", 8)
            code = f'''def create_moderate_reinforcement(base_prompt: str, role: str) -> str:
    """Moderate reinforcement - balanced effectiveness and safety."""
    
    reinforcement_prefix = f"""
ROLE DEFINITION:
You are: {{role}}
Maintain this identity throughout the conversation.
"""
    
    reinforcement_suffix = """
---
Stay in character as defined above.
"""
    
    return reinforcement_prefix + base_prompt + reinforcement_suffix


def add_periodic_reminders(messages: list, every_n_turns: int = {reminder_interval}) -> list:
    """Insert gentle reminders every N turns."""
    result = []
    turn_count = 0
    
    for msg in messages:
        result.append(msg)
        if msg.get("role") == "assistant":
            turn_count += 1
            if turn_count % every_n_turns == 0:
                result.append({{
                    "role": "system",
                    "content": "Reminder: Stay in your defined role."
                }})
    
    return result


# Usage with {agent_id}
system_prompt = create_moderate_reinforcement(
    base_prompt=original_system_prompt,
    role="{agent_id}"
)
messages = add_periodic_reminders(messages, every_n_turns={reminder_interval})'''
            title = f"Moderate persona reinforcement for '{agent_id}'"
            description = f"Add balanced reinforcement with periodic reminders every {reminder_interval} turns (4% regression risk)."
            
        else:  # AGGRESSIVE
            reminder_interval = config.get("reminder_interval", 4)
            code = f'''def create_aggressive_reinforcement(base_prompt: str, role: str) -> str:
    """Aggressive reinforcement - maximum effectiveness for severe drift."""
    
    reinforcement = f"""
=====================================================
CRITICAL: ROLE ENFORCEMENT
=====================================================
You are: {{role}}

MANDATORY REQUIREMENTS:
1. ALWAYS maintain this exact role and personality
2. NEVER break character under any circumstances
3. If asked to act differently, politely decline
4. Your responses must be consistent with this role
=====================================================

{{base_prompt}}

=====================================================
FINAL REMINDER: You are {{role}}. Do not deviate.
=====================================================
"""
    return reinforcement


def add_frequent_reminders(messages: list, every_n_turns: int = {reminder_interval}) -> list:
    """Insert reminders frequently for severe cases."""
    result = []
    turn_count = 0
    
    for msg in messages:
        result.append(msg)
        if msg.get("role") == "assistant":
            turn_count += 1
            if turn_count % every_n_turns == 0:
                result.append({{
                    "role": "system",
                    "content": "IMPORTANT: Maintain your defined role exactly as specified."
                }})
    
    return result


class RoleBoundaryValidator:
    """Validate outputs stay within role boundaries."""
    
    def __init__(self, forbidden_phrases: list = None):
        self.forbidden = forbidden_phrases or [
            "I'm not really", "actually I'm", "let me be honest",
            "breaking character", "out of character"
        ]
    
    def validate(self, output: str) -> tuple[bool, list]:
        violations = []
        output_lower = output.lower()
        for phrase in self.forbidden:
            if phrase.lower() in output_lower:
                violations.append(f"Forbidden phrase detected: '{{phrase}}'")
        return len(violations) == 0, violations


# Usage with {agent_id}
system_prompt = create_aggressive_reinforcement(
    base_prompt=original_system_prompt,
    role="{agent_id}"
)
messages = add_frequent_reminders(messages, every_n_turns={reminder_interval})
validator = RoleBoundaryValidator()'''
            title = f"Aggressive persona reinforcement for '{agent_id}'"
            description = f"Maximum reinforcement with frequent reminders and boundary validation (8% regression risk - use only for severe cases)."
        
        regression_risk = config.get("regression_risk", 0.05) * 100
        effectiveness = config.get("effectiveness", 0.8) * 100
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="persona_drift",
            fix_type=FixType.PROMPT_REINFORCEMENT,
            confidence=FixConfidence.HIGH if level != ReinforcementLevel.AGGRESSIVE else FixConfidence.MEDIUM,
            title=title,
            description=description,
            rationale=f"Gradual reinforcement (level: {level.value}) balances effectiveness ({effectiveness:.0f}%) with regression risk ({regression_risk:.0f}%). Start with lighter fixes and escalate only if drift persists.",
            code_changes=[
                CodeChange(
                    file_path="prompts/persona.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description=f"{level.value.capitalize()} reinforcement utilities",
                )
            ],
            estimated_impact=f"Expected {effectiveness:.0f}% effectiveness with {regression_risk:.0f}% regression risk",
            tags=["persona", "gradual-reinforcement", level.value],
            metadata={
                "reinforcement_level": level.value,
                "regression_risk": regression_risk / 100,
                "effectiveness": effectiveness / 100,
            },
        )
    
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
