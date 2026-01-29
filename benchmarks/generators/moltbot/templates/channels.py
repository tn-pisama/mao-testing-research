"""Channel-specific formatting for Moltbot messages."""

import random

# Channel characteristics
CHANNEL_CHARACTERISTICS = {
    "whatsapp": {
        "uses_emojis": True,
        "casual_tone": True,
        "short_messages": True,
        "emojis": ["👍", "😊", "✅", "🎉", "🔥", "💡", "📱", "✨"],
    },
    "telegram": {
        "uses_emojis": True,
        "casual_tone": True,
        "short_messages": False,
        "emojis": ["✅", "🚀", "💬", "📊", "⚙️", "🔔"],
    },
    "slack": {
        "uses_emojis": True,
        "casual_tone": False,
        "short_messages": False,
        "emojis": [":white_check_mark:", ":rocket:", ":tada:", ":bell:", ":information_source:"],
    },
    "discord": {
        "uses_emojis": True,
        "casual_tone": True,
        "short_messages": False,
        "emojis": ["✅", "🎮", "💬", "🔥", "⚡"],
    },
    "signal": {
        "uses_emojis": False,
        "casual_tone": False,
        "short_messages": True,
        "emojis": [],
    },
    "matrix": {
        "uses_emojis": False,
        "casual_tone": False,
        "short_messages": False,
        "emojis": [],
    },
    "webchat": {
        "uses_emojis": False,
        "casual_tone": False,
        "short_messages": False,
        "emojis": [],
    },
    "imessage": {
        "uses_emojis": True,
        "casual_tone": True,
        "short_messages": True,
        "emojis": ["👍", "😊", "✅", "🎉", "💯"],
    },
}


def format_for_channel(message: str, channel: str, is_user: bool = False) -> str:
    """Format a message for a specific channel.

    Args:
        message: The base message content
        channel: Channel name (e.g., "whatsapp", "slack")
        is_user: Whether this is a user message (vs agent message)

    Returns:
        Formatted message string
    """
    if channel not in CHANNEL_CHARACTERISTICS:
        return message

    chars = CHANNEL_CHARACTERISTICS[channel]

    # Add emojis if channel uses them
    if chars["uses_emojis"] and not is_user:
        # Add emoji to agent messages (users naturally use emojis)
        if random.random() < 0.3:  # 30% chance
            emoji = random.choice(chars["emojis"])
            message = f"{message} {emoji}"

    # Adjust tone if channel is casual
    if chars["casual_tone"]:
        message = make_casual(message)
    else:
        message = make_formal(message)

    # Shorten if channel prefers short messages
    if chars["short_messages"] and len(message) > 100:
        # Truncate and add ellipsis
        message = message[:97] + "..."

    return message


def make_casual(message: str) -> str:
    """Make a message more casual.

    Args:
        message: Original message

    Returns:
        Casualized message
    """
    # Replace formal phrases with casual ones
    replacements = {
        "I will": "I'll",
        "I have": "I've",
        "cannot": "can't",
        "will not": "won't",
        "should not": "shouldn't",
        "would not": "wouldn't",
        "Please ": "",
        "Thank you": "Thanks",
        "You are welcome": "No problem",
        "I am": "I'm",
        "Let me": "Lemme",
    }

    for formal, casual in replacements.items():
        message = message.replace(formal, casual)

    return message


def make_formal(message: str) -> str:
    """Make a message more formal.

    Args:
        message: Original message

    Returns:
        Formalized message
    """
    # Replace casual phrases with formal ones
    replacements = {
        "I'll": "I will",
        "I've": "I have",
        "can't": "cannot",
        "won't": "will not",
        "shouldn't": "should not",
        "wouldn't": "would not",
        "Thanks": "Thank you",
        "No problem": "You are welcome",
        "I'm": "I am",
        "Lemme": "Let me",
        "gonna": "going to",
        "wanna": "want to",
    }

    for casual, formal in replacements.items():
        message = message.replace(casual, formal)

    return message


def get_channel_metadata(channel: str) -> dict:
    """Get metadata for a channel.

    Args:
        channel: Channel name

    Returns:
        Channel metadata dictionary
    """
    if channel not in CHANNEL_CHARACTERISTICS:
        return {"channel": channel, "platform": "unknown"}

    return {
        "channel": channel,
        "platform": "moltbot",
        "uses_emojis": CHANNEL_CHARACTERISTICS[channel]["uses_emojis"],
        "tone": "casual" if CHANNEL_CHARACTERISTICS[channel]["casual_tone"] else "formal",
    }
