"""Parse MAST trajectories into structured turns.

Converts raw trajectory text from different multi-agent frameworks
into TurnSnapshot objects for turn-aware detection.
"""

import logging
import re
from typing import List, Optional

from app.detection.turn_aware._base import TurnSnapshot

logger = logging.getLogger(__name__)


def parse_trajectory_to_turns(
    trajectory: str,
    framework: str,
    max_turns: int = 200,
) -> List[TurnSnapshot]:
    """Parse raw MAST trajectory text into structured TurnSnapshots.

    Args:
        trajectory: Raw trajectory text from MAST
        framework: Framework name (ChatDev, MetaGPT, AG2, etc.)
        max_turns: Maximum turns to parse (for performance)

    Returns:
        List of TurnSnapshot objects
    """
    framework_lower = framework.lower()

    if "chatdev" in framework_lower:
        return _parse_chatdev(trajectory, max_turns)
    elif "metagpt" in framework_lower:
        return _parse_metagpt(trajectory, max_turns)
    elif "ag2" in framework_lower or "autogen" in framework_lower:
        return _parse_ag2(trajectory, max_turns)
    elif "crewai" in framework_lower:
        return _parse_crewai(trajectory, max_turns)
    elif "camel" in framework_lower:
        return _parse_camel(trajectory, max_turns)
    else:
        # Generic fallback parser
        return _parse_generic(trajectory, max_turns)


def _parse_chatdev(trajectory: str, max_turns: int) -> List[TurnSnapshot]:
    """Parse ChatDev trajectory format.

    ChatDev format:
    [timestamp INFO] Role Name: **[Start Chat]**

    [Actual message content follows on next lines without timestamp]
    ...

    [timestamp INFO] Next Role: ...
    """
    turns = []
    turn_number = 0

    # Known ChatDev roles that are actual agents (not system)
    agent_roles = {
        "chief executive officer", "ceo",
        "chief product officer", "cpo",
        "chief technology officer", "cto",
        "chief human resources officer",
        "programmer", "code reviewer", "software engineer",
        "designer", "tester", "qa engineer",
        "project manager", "product manager",
        "counselor",
    }

    # Split into lines and process
    lines = trajectory.split('\n')
    i = 0
    while i < len(lines) and turn_number < max_turns:
        line = lines[i]

        # Look for role line: [timestamp INFO] Role Name: **[...]**
        role_match = re.match(
            r'\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+INFO\]\s+'
            r'([A-Za-z][A-Za-z\s]+?):\s*\*\*\[',
            line
        )

        if role_match:
            role = role_match.group(1).strip()
            role_lower = role.lower()

            # Check if this is an actual agent role
            is_agent = any(agent in role_lower for agent in agent_roles)

            if is_agent:
                # Collect content from following lines until next [timestamp INFO]
                content_lines = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    # Stop if we hit another timestamp line
                    if re.match(r'\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+INFO\]', next_line):
                        break
                    # Add non-empty lines
                    if next_line.strip():
                        content_lines.append(next_line)
                    j += 1

                content = '\n'.join(content_lines).strip()

                # Filter out system/config content
                if content and len(content) > 50:
                    # Skip if it's mostly config/parameter tables
                    if "| Parameter |" in content and content.count("|") > 10:
                        i = j
                        continue
                    if content.startswith("ChatGPTConfig") or content.startswith("ChatEnvConfig"):
                        i = j
                        continue

                    meaningful_content = _clean_content(content)
                    if meaningful_content and len(meaningful_content) > 30:
                        turns.append(TurnSnapshot(
                            turn_number=turn_number,
                            participant_type="agent",
                            participant_id=role,
                            content=meaningful_content,
                            turn_metadata={"framework": "ChatDev", "role": role},
                        ))
                        turn_number += 1

                i = j
                continue

        i += 1

    return turns


def _parse_metagpt(trajectory: str, max_turns: int) -> List[TurnSnapshot]:
    """Parse MetaGPT trajectory format.

    MetaGPT format:
    ## Role: RoleName
    ### Action: ActionName
    content...
    """
    turns = []
    turn_number = 0

    # Split by role headers
    # Pattern: ## Role: RoleName or similar markdown headers
    sections = re.split(r'(?:^|\n)##\s+([A-Za-z]+):\s*(\w+)', trajectory)

    current_role = None
    for i, section in enumerate(sections):
        if turn_number >= max_turns:
            break

        section = section.strip()
        if not section:
            continue

        # Check if this is a role indicator
        if section in ("Role", "Agent", "Assistant"):
            # Next section is the role name
            if i + 1 < len(sections):
                current_role = sections[i + 1].strip()
            continue

        # If we have a role and this is content
        if current_role and len(section) > 20:
            # Skip if it's a role name
            if len(section) < 50 and re.match(r'^[A-Za-z_]+$', section):
                current_role = section
                continue

            turns.append(TurnSnapshot(
                turn_number=turn_number,
                participant_type="agent",
                participant_id=current_role,
                content=_clean_content(section),
                turn_metadata={"framework": "MetaGPT", "role": current_role},
            ))
            turn_number += 1

    # Fallback: if no turns found, use generic parser
    if not turns:
        return _parse_generic(trajectory, max_turns)

    return turns


def _parse_ag2(trajectory: str, max_turns: int) -> List[TurnSnapshot]:
    """Parse AG2/AutoGen trajectory format.

    AG2 format:
    agent_name (to other_agent):
    content...

    ----------------
    """
    turns = []
    turn_number = 0

    # Pattern: agent_name (to target): or assistant: or user:
    pattern = r'([a-zA-Z_]+(?:\s*\([^)]+\))?)\s*:\s*(.*?)(?=\n[a-zA-Z_]+(?:\s*\([^)]+\))?\s*:|$|-{5,})'

    matches = re.findall(pattern, trajectory, re.DOTALL)

    for agent_spec, content in matches:
        if turn_number >= max_turns:
            break

        agent_spec = agent_spec.strip()
        content = content.strip()

        if not content or len(content) < 10:
            continue

        # Extract agent name from "agent_name (to target)"
        agent_match = re.match(r'([a-zA-Z_]+)', agent_spec)
        agent_name = agent_match.group(1) if agent_match else agent_spec

        # Determine participant type
        if "user" in agent_name.lower() or "human" in agent_name.lower():
            participant_type = "user"
        else:
            participant_type = "agent"

        turns.append(TurnSnapshot(
            turn_number=turn_number,
            participant_type=participant_type,
            participant_id=agent_name,
            content=_clean_content(content),
            turn_metadata={"framework": "AG2", "agent": agent_name},
        ))
        turn_number += 1

    # Fallback
    if not turns:
        return _parse_generic(trajectory, max_turns)

    return turns


def _parse_crewai(trajectory: str, max_turns: int) -> List[TurnSnapshot]:
    """Parse CrewAI trajectory format.

    CrewAI format varies but typically:
    [Agent Name]
    content...
    """
    turns = []
    turn_number = 0

    # Pattern for CrewAI agent markers
    pattern = r'\[([^\]]+)\]\s*(.*?)(?=\[[^\]]+\]|$)'

    matches = re.findall(pattern, trajectory, re.DOTALL)

    for agent, content in matches:
        if turn_number >= max_turns:
            break

        agent = agent.strip()
        content = content.strip()

        if not content or len(content) < 10:
            continue

        turns.append(TurnSnapshot(
            turn_number=turn_number,
            participant_type="agent",
            participant_id=agent,
            content=_clean_content(content),
            turn_metadata={"framework": "CrewAI", "agent": agent},
        ))
        turn_number += 1

    if not turns:
        return _parse_generic(trajectory, max_turns)

    return turns


def _parse_camel(trajectory: str, max_turns: int) -> List[TurnSnapshot]:
    """Parse CAMEL trajectory format.

    CAMEL format:
    AI User: content
    AI Assistant: content
    """
    turns = []
    turn_number = 0

    # Pattern for CAMEL format
    pattern = r'(AI\s+(?:User|Assistant)|User|Assistant)\s*:\s*(.*?)(?=AI\s+(?:User|Assistant)\s*:|User\s*:|Assistant\s*:|$)'

    matches = re.findall(pattern, trajectory, re.DOTALL | re.IGNORECASE)

    for role, content in matches:
        if turn_number >= max_turns:
            break

        role = role.strip()
        content = content.strip()

        if not content or len(content) < 10:
            continue

        participant_type = "user" if "user" in role.lower() else "agent"

        turns.append(TurnSnapshot(
            turn_number=turn_number,
            participant_type=participant_type,
            participant_id=role,
            content=_clean_content(content),
            turn_metadata={"framework": "CAMEL", "role": role},
        ))
        turn_number += 1

    if not turns:
        return _parse_generic(trajectory, max_turns)

    return turns


def _parse_generic(trajectory: str, max_turns: int) -> List[TurnSnapshot]:
    """Generic fallback parser for unknown formats.

    Tries to identify turn boundaries by:
    1. Double newlines
    2. Role-like prefixes (Name:, [Name], etc.)
    3. Paragraph boundaries
    """
    turns = []
    turn_number = 0

    # First try: Look for role prefixes
    role_pattern = r'(?:^|\n\n)([A-Z][a-zA-Z\s]+):\s*(.*?)(?=\n\n[A-Z][a-zA-Z\s]+:|$)'
    matches = re.findall(role_pattern, trajectory, re.DOTALL)

    if matches:
        for role, content in matches:
            if turn_number >= max_turns:
                break

            role = role.strip()
            content = content.strip()

            if not content or len(content) < 20:
                continue

            participant_type = "user" if any(x in role.lower() for x in ["user", "human", "customer"]) else "agent"

            turns.append(TurnSnapshot(
                turn_number=turn_number,
                participant_type=participant_type,
                participant_id=role,
                content=_clean_content(content),
                turn_metadata={"framework": "unknown"},
            ))
            turn_number += 1

    # Second try: Split by double newlines
    if not turns:
        paragraphs = re.split(r'\n\n+', trajectory)
        for para in paragraphs:
            if turn_number >= max_turns:
                break

            para = para.strip()
            if not para or len(para) < 50:
                continue

            turns.append(TurnSnapshot(
                turn_number=turn_number,
                participant_type="agent",
                participant_id="unknown",
                content=_clean_content(para),
                turn_metadata={"framework": "unknown"},
            ))
            turn_number += 1

    return turns


def _clean_content(content: str) -> str:
    """Clean and normalize turn content.

    Removes:
    - Excessive whitespace
    - Markdown formatting noise
    - Parameter tables
    """
    # Remove markdown tables
    content = re.sub(r'\|[^\n]+\|', '', content)

    # Remove markdown header markers but keep text
    content = re.sub(r'^#{1,6}\s*', '', content, flags=re.MULTILINE)

    # Remove excessive whitespace
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = re.sub(r'[ \t]+', ' ', content)

    # Remove ** markers but keep text
    content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)

    return content.strip()


def extract_task_from_trajectory(trajectory: str, framework: str) -> Optional[str]:
    """Extract the original task/prompt from a trajectory.

    Args:
        trajectory: Raw trajectory text
        framework: Framework name

    Returns:
        Task description if found, None otherwise
    """
    framework_lower = framework.lower()

    if "chatdev" in framework_lower:
        # Look for task_prompt in ChatDev logs
        match = re.search(r'\*\*task_prompt\*\*:\s*([^\n]+)', trajectory)
        if match:
            return match.group(1).strip()

    # Generic: Look for common task patterns
    patterns = [
        r'[Tt]ask:\s*([^\n]+)',
        r'[Pp]rompt:\s*([^\n]+)',
        r'[Rr]equest:\s*([^\n]+)',
        r'[Gg]oal:\s*([^\n]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, trajectory[:2000])  # Check beginning
        if match:
            return match.group(1).strip()

    return None
