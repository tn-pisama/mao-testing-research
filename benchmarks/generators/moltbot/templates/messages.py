"""Realistic message templates for Moltbot traces."""

import random

MESSAGE_TEMPLATES = {
    # User messages by category
    "user": {
        "browser_request": [
            "Can you navigate to {url} and tell me what you see?",
            "Please check {url} for me",
            "Open {url} in the browser",
            "Go to {url} and grab the {element} for me",
            "Visit {url} and take a screenshot",
        ],
        "file_request": [
            "Can you find {filename} in my documents?",
            "Search for {filename} please",
            "List all {filetype} files in {directory}",
            "Show me the contents of {filename}",
            "Find files matching {pattern}",
        ],
        "email_request": [
            "Send an email to {recipient} about {topic}",
            "Check my inbox for messages from {sender}",
            "Draft an email to {recipient}",
            "Reply to {sender}'s last email",
            "Search my emails for {keyword}",
        ],
        "calendar_request": [
            "Schedule a meeting with {person} for {time}",
            "What's on my calendar today?",
            "Add {event} to my calendar",
            "Cancel my {time} meeting",
            "Move my {event} to {new_time}",
        ],
        "smart_home_request": [
            "Turn off all the lights",
            "Set the thermostat to {temperature}",
            "Lock the front door",
            "Show me the garage camera",
            "Turn on the {room} lights",
        ],
        "multi_step_request": [
            "Schedule a meeting with {person}, send them a confirmation email, and add it to my calendar",
            "Find {filename}, read it, and summarize the key points",
            "Check {url}, extract the {data}, and save it to {file}",
            "Turn off all lights, lock the doors, and set the alarm",
            "Search for {keyword} in my emails and create a summary document",
        ],
    },
    # Agent responses
    "agent": {
        "acknowledgment": [
            "Sure, let me {action} for you",
            "I'll {action} right away",
            "On it! {action}",
            "Let me handle that - {action}",
            "I can help with that. {action}",
        ],
        "completion": [
            "Done! I've {action}",
            "All set - {action}",
            "Completed: {action}",
            "Finished {action}",
            "Task complete: {action}",
        ],
        "partial_completion": [
            "I've {completed_action} but couldn't {incomplete_action}",
            "Done with {completed_action}, but {incomplete_action} failed",
            "{completed_action} is complete",
            "I managed to {completed_action}",
        ],
        "error": [
            "Sorry, I couldn't {action} because {reason}",
            "I encountered an error while {action}: {reason}",
            "Failed to {action} - {reason}",
            "Unable to {action} right now",
        ],
        "thinking": [
            "Let me check {item}...",
            "Looking into {item}...",
            "Processing {item}...",
            "Analyzing {item}...",
            "Searching for {item}...",
        ],
    },
}


def get_user_message(category: str, **kwargs) -> str:
    """Get a random user message template and fill it.

    Args:
        category: Message category (e.g., "browser_request")
        **kwargs: Variables to substitute in template

    Returns:
        Formatted message string
    """
    templates = MESSAGE_TEMPLATES["user"].get(category, [])
    if not templates:
        return f"User message about {category}"

    template = random.choice(templates)
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def get_agent_message(category: str, **kwargs) -> str:
    """Get a random agent message template and fill it.

    Args:
        category: Message category (e.g., "acknowledgment")
        **kwargs: Variables to substitute in template

    Returns:
        Formatted message string
    """
    templates = MESSAGE_TEMPLATES["agent"].get(category, [])
    if not templates:
        return f"Agent message about {category}"

    template = random.choice(templates)
    try:
        return template.format(**kwargs)
    except KeyError:
        return template
