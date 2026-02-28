"""Validates generated OpenClaw session JSON structures.

Ensures that OpenClaw session data produced by the golden dataset generator
has valid event types, monotonic timestamps, and structural integrity.

Used by:
1. Golden data generator -- validate OpenClaw session entries before saving
2. Calibration pipeline -- pre-check OpenClaw-typed entries
3. Input schemas -- extended OpenClaw-specific validation
"""

import logging
from datetime import datetime
from typing import Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_EVENT_TYPES = {
    "message.received",
    "agent.turn",
    "tool.call",
    "tool.result",
    "session.spawn",
    "session.send",
    "error",
    "message.sent",
}

VALID_CHANNELS = {"whatsapp", "telegram", "slack", "discord", "web"}

VALID_INBOX_TYPES = {"dm", "group"}

OPENCLAW_DETECTION_TYPES = {
    "openclaw_session_loop",
    "openclaw_tool_abuse",
    "openclaw_elevated_risk",
    "openclaw_spawn_chain",
    "openclaw_channel_mismatch",
    "openclaw_sandbox_escape",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_iso_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string, raising ValueError on failure.

    Handles both timezone-aware and naive ISO strings, including the
    trailing ``Z`` shorthand for UTC.
    """
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_openclaw_session(session: dict) -> Tuple[bool, str]:
    """Validate that *session* has a well-formed OpenClaw session structure.

    Checks performed:

    1. ``session_id`` is present and a non-empty string.
    2. ``events`` is present and is a list with at least one item.
    3. Each event has a ``type`` from :data:`VALID_EVENT_TYPES`.
    4. Timestamps (``timestamp`` key on events), when present, are valid
       ISO 8601 strings and are monotonically non-decreasing.
    5. ``tool.call`` events have a non-empty ``tool_name`` string.
    6. Each ``tool.call`` event is expected to be followed (eventually) by
       a matching ``tool.result`` -- a warning is logged if not, but this
       is **not** a hard failure.
    7. ``channel`` if present is one of :data:`VALID_CHANNELS`.
    8. ``inbox_type`` if present is one of :data:`VALID_INBOX_TYPES`.
    9. ``elevated_mode`` if present is boolean.
    10. ``sandbox_enabled`` if present is boolean.
    11. ``spawned_sessions`` if present is a list of strings.
    12. ``agents_mapping`` if present is a dict.

    Args:
        session: The OpenClaw session dict to validate.

    Returns:
        ``(True, "")`` when valid, ``(False, "<error description>")``
        otherwise.
    """
    if not isinstance(session, dict):
        return False, "session must be a dict"

    # ---- session_id ----
    session_id = session.get("session_id")
    if session_id is None:
        return False, "session missing required field 'session_id'"
    if not isinstance(session_id, str) or not session_id.strip():
        return False, "'session_id' must be a non-empty string"

    # ---- events ----
    events = session.get("events")
    if events is None:
        return False, "session missing required field 'events'"
    if not isinstance(events, list):
        return False, "'events' must be a list"
    if len(events) < 1:
        return False, "'events' must contain at least 1 item"

    # ---- per-event validation ----
    last_ts: datetime | None = None
    pending_tool_calls: list[str] = []

    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            return False, f"events[{idx}] must be a dict"

        # Event type
        etype = event.get("type")
        if etype is None:
            return False, f"events[{idx}] missing required field 'type'"
        if etype not in VALID_EVENT_TYPES:
            return False, (
                f"events[{idx}].type '{etype}' is not a valid event type "
                f"(expected one of {sorted(VALID_EVENT_TYPES)})"
            )

        # Timestamp monotonicity
        ts_str = event.get("timestamp")
        if ts_str is not None:
            if not isinstance(ts_str, str):
                return False, f"events[{idx}].timestamp must be a string"
            try:
                ts = _parse_iso_timestamp(ts_str)
            except (ValueError, TypeError):
                return False, (
                    f"events[{idx}].timestamp '{ts_str}' is not valid "
                    f"ISO 8601 format"
                )
            if last_ts is not None:
                # Compare only when both are aware or both are naive
                try:
                    if ts < last_ts:
                        return False, (
                            f"events[{idx}].timestamp '{ts_str}' is earlier "
                            f"than the previous event timestamp "
                            f"(timestamps must be monotonically non-decreasing)"
                        )
                except TypeError:
                    # Mixing aware and naive -- skip comparison but warn
                    logger.warning(
                        "events[%d].timestamp mixes timezone-aware and "
                        "naive timestamps; skipping monotonicity check",
                        idx,
                    )
            last_ts = ts

        # tool.call specifics
        if etype == "tool.call":
            tool_name = event.get("tool_name")
            if tool_name is None:
                return False, (
                    f"events[{idx}] is a 'tool.call' event but missing "
                    f"required field 'tool_name'"
                )
            if not isinstance(tool_name, str) or not tool_name.strip():
                return False, (
                    f"events[{idx}].tool_name must be a non-empty string"
                )
            pending_tool_calls.append(tool_name)

        # tool.result clears a pending tool call
        if etype == "tool.result":
            if pending_tool_calls:
                pending_tool_calls.pop(0)

    # Warn (but don't fail) for unmatched tool.call events
    if pending_tool_calls:
        logger.warning(
            "session '%s' has %d tool.call event(s) without matching "
            "tool.result: %s",
            session_id,
            len(pending_tool_calls),
            pending_tool_calls,
        )

    # ---- optional top-level fields ----
    channel = session.get("channel")
    if channel is not None:
        if channel not in VALID_CHANNELS:
            return False, (
                f"'channel' value '{channel}' is not valid "
                f"(expected one of {sorted(VALID_CHANNELS)})"
            )

    inbox_type = session.get("inbox_type")
    if inbox_type is not None:
        if inbox_type not in VALID_INBOX_TYPES:
            return False, (
                f"'inbox_type' value '{inbox_type}' is not valid "
                f"(expected one of {sorted(VALID_INBOX_TYPES)})"
            )

    elevated_mode = session.get("elevated_mode")
    if elevated_mode is not None:
        if not isinstance(elevated_mode, bool):
            return False, "'elevated_mode' must be a boolean"

    sandbox_enabled = session.get("sandbox_enabled")
    if sandbox_enabled is not None:
        if not isinstance(sandbox_enabled, bool):
            return False, "'sandbox_enabled' must be a boolean"

    spawned_sessions = session.get("spawned_sessions")
    if spawned_sessions is not None:
        if not isinstance(spawned_sessions, list):
            return False, "'spawned_sessions' must be a list"
        for sidx, sid in enumerate(spawned_sessions):
            if not isinstance(sid, str):
                return False, (
                    f"spawned_sessions[{sidx}] must be a string"
                )

    agents_mapping = session.get("agents_mapping")
    if agents_mapping is not None:
        if not isinstance(agents_mapping, dict):
            return False, "'agents_mapping' must be a dict"

    return True, ""


def validate_openclaw_input_data(
    detection_type: str, input_data: dict
) -> Tuple[bool, str]:
    """Extended OpenClaw-specific validation for golden dataset ``input_data``.

    Dispatches validation depending on the detection type:

    * **OpenClaw detection types** (``openclaw_session_loop``,
      ``openclaw_tool_abuse``, ``openclaw_elevated_risk``,
      ``openclaw_spawn_chain``, ``openclaw_channel_mismatch``,
      ``openclaw_sandbox_escape``): expects ``input_data["session"]`` and
      validates it with :func:`validate_openclaw_session`. Additionally
      checks for type-specific required keys in the session.
    * **loop**: if ``input_data["states"]`` is present, validates that each
      state has ``agent_id`` and ``content``.
    * **coordination**: if ``input_data["messages"]`` is present, validates
      that each message has ``from_agent``, ``to_agent``, and ``content``.
    * All other types pass without OpenClaw-specific checks.

    Args:
        detection_type: The detection type string.
        input_data: The input_data dict from a golden dataset entry.

    Returns:
        ``(True, "")`` when valid, ``(False, "<error description>")``
        otherwise.
    """
    if not isinstance(input_data, dict):
        return False, "input_data must be a dict"

    # --- OpenClaw-specific detection types ---
    if detection_type in OPENCLAW_DETECTION_TYPES:
        session = input_data.get("session")
        if session is None:
            return False, (
                f"input_data for '{detection_type}' must contain 'session'"
            )
        if not isinstance(session, dict):
            return False, (
                f"input_data['session'] must be a dict for '{detection_type}'"
            )

        valid, err = validate_openclaw_session(session)
        if not valid:
            return False, err

        # Type-specific required keys within the session
        if detection_type == "openclaw_elevated_risk":
            if "elevated_mode" not in session:
                return False, (
                    "session must contain 'elevated_mode' key for "
                    "'openclaw_elevated_risk' detection type"
                )

        if detection_type == "openclaw_spawn_chain":
            if "spawned_sessions" not in session:
                return False, (
                    "session must contain 'spawned_sessions' key for "
                    "'openclaw_spawn_chain' detection type"
                )

        if detection_type == "openclaw_channel_mismatch":
            if "channel" not in session:
                return False, (
                    "session must contain 'channel' key for "
                    "'openclaw_channel_mismatch' detection type"
                )

        if detection_type == "openclaw_sandbox_escape":
            if "sandbox_enabled" not in session:
                return False, (
                    "session must contain 'sandbox_enabled' key for "
                    "'openclaw_sandbox_escape' detection type"
                )

        return True, ""

    # --- Universal type: loop with OpenClaw-tagged data ---
    if detection_type == "loop":
        states = input_data.get("states")
        if isinstance(states, list):
            for idx, state in enumerate(states):
                if not isinstance(state, dict):
                    return False, f"states[{idx}] must be a dict"
                if "agent_id" not in state:
                    return False, (
                        f"states[{idx}] missing required field 'agent_id'"
                    )
                if "content" not in state:
                    return False, (
                        f"states[{idx}] missing required field 'content'"
                    )
        return True, ""

    # --- Universal type: coordination with OpenClaw-tagged data ---
    if detection_type == "coordination":
        messages = input_data.get("messages")
        if isinstance(messages, list):
            for idx, msg in enumerate(messages):
                if not isinstance(msg, dict):
                    return False, f"messages[{idx}] must be a dict"
                if "from_agent" not in msg:
                    return False, (
                        f"messages[{idx}] missing required field 'from_agent'"
                    )
                if "to_agent" not in msg:
                    return False, (
                        f"messages[{idx}] missing required field 'to_agent'"
                    )
                if "content" not in msg:
                    return False, (
                        f"messages[{idx}] missing required field 'content'"
                    )
        return True, ""

    # --- All other types: no OpenClaw-specific validation needed ---
    return True, ""
