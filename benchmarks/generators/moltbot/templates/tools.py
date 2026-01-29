"""Tool call and result templates for Moltbot traces."""

import random
from typing import Any

TOOL_TEMPLATES = {
    "browser": {
        "navigate": {
            "input": lambda: {
                "url": random.choice([
                    "https://example.com",
                    "https://news.ycombinator.com",
                    "https://github.com",
                    "https://stackoverflow.com",
                    "https://reddit.com",
                ])
            },
            "output": lambda url: {
                "status": 200,
                "title": f"Page: {url}",
                "content_length": random.randint(5000, 50000),
            },
        },
        "click": {
            "input": lambda: {"selector": random.choice(["#submit", ".btn-primary", "button[type=submit]"])},
            "output": lambda: {"success": True, "clicked": True},
        },
        "screenshot": {
            "input": lambda: {},
            "output": lambda: {
                "success": True,
                "path": f"/tmp/screenshot_{random.randint(1000, 9999)}.png",
                "size": random.randint(100000, 500000),
            },
        },
    },
    "filesystem": {
        "read": {
            "input": lambda: {
                "path": random.choice([
                    "/home/user/documents/report.pdf",
                    "/home/user/notes.txt",
                    "/home/user/data.json",
                ])
            },
            "output": lambda path: {"content": f"Contents of {path}", "size": random.randint(1000, 100000)},
        },
        "search": {
            "input": lambda: {
                "path": "/home/user/documents",
                "pattern": random.choice(["*.pdf", "*.txt", "*.docx"]),
            },
            "output": lambda: {
                "files": [
                    f"file{i}.{random.choice(['pdf', 'txt', 'docx'])}"
                    for i in range(random.randint(0, 5))
                ],
                "count": random.randint(0, 5),
            },
        },
        "write": {
            "input": lambda: {
                "path": f"/home/user/output_{random.randint(1000, 9999)}.txt",
                "content": "Generated content...",
            },
            "output": lambda path: {"success": True, "path": path, "bytes_written": random.randint(100, 10000)},
        },
    },
    "email": {
        "send": {
            "input": lambda: {
                "to": random.choice(["john@example.com", "team@company.com", "support@service.com"]),
                "subject": "Meeting confirmation",
                "body": "Email body content...",
            },
            "output": lambda: {"success": True, "message_id": f"<{random.randint(1000000, 9999999)}@mail>"},
        },
        "search": {
            "input": lambda: {"query": random.choice(["meeting", "invoice", "update"])},
            "output": lambda: {
                "results": [
                    {"from": "sender@example.com", "subject": "RE: Query", "date": "2026-01-29"}
                    for _ in range(random.randint(0, 10))
                ],
                "count": random.randint(0, 10),
            },
        },
    },
    "calendar": {
        "create_event": {
            "input": lambda: {
                "title": random.choice(["Team Meeting", "1:1 with John", "Project Review"]),
                "start": "2026-01-30T14:00:00Z",
                "end": "2026-01-30T15:00:00Z",
                "attendees": ["john@example.com"],
            },
            "output": lambda: {
                "success": True,
                "event_id": f"evt_{random.randint(100000, 999999)}",
                "created": True,
            },
        },
        "list_events": {
            "input": lambda: {"date": "2026-01-30"},
            "output": lambda: {
                "events": [
                    {"id": f"evt_{i}", "title": f"Event {i}", "time": f"{9+i}:00"}
                    for i in range(random.randint(0, 5))
                ],
                "count": random.randint(0, 5),
            },
        },
    },
    "smart_home": {
        "lights": {
            "input": lambda: {"room": random.choice(["living_room", "bedroom", "kitchen"]), "state": "off"},
            "output": lambda: {"success": True, "state": "off"},
        },
        "thermostat": {
            "input": lambda: {"temperature": random.randint(65, 75)},
            "output": lambda temp: {"success": True, "temperature": temp, "mode": "heat"},
        },
        "locks": {
            "input": lambda: {"door": "front_door", "state": "locked"},
            "output": lambda: {"success": True, "state": "locked", "verified": True},
        },
    },
    "memory": {
        "store": {
            "input": lambda: {
                "key": f"preference_{random.choice(['timezone', 'theme', 'language'])}",
                "value": random.choice(["America/New_York", "dark", "en"]),
            },
            "output": lambda: {"success": True, "stored": True},
        },
        "retrieve": {
            "input": lambda: {"key": f"preference_{random.choice(['timezone', 'theme', 'language'])}"},
            "output": lambda key: {"value": "stored_value", "found": True},
        },
    },
}


def get_tool_call(category: str, action: str) -> dict[str, Any]:
    """Get a realistic tool call input.

    Args:
        category: Tool category (e.g., "browser")
        action: Tool action (e.g., "navigate")

    Returns:
        Tool input dictionary
    """
    if category not in TOOL_TEMPLATES:
        return {"tool": category, "action": action}

    if action not in TOOL_TEMPLATES[category]:
        return {"tool": category, "action": action}

    input_fn = TOOL_TEMPLATES[category][action]["input"]
    return input_fn()


def get_tool_result(category: str, action: str, input_data: dict[str, Any]) -> dict[str, Any]:
    """Get a realistic tool result output.

    Args:
        category: Tool category (e.g., "browser")
        action: Tool action (e.g., "navigate")
        input_data: The input data used for the call

    Returns:
        Tool output dictionary
    """
    if category not in TOOL_TEMPLATES:
        return {"success": True, "result": "completed"}

    if action not in TOOL_TEMPLATES[category]:
        return {"success": True, "result": "completed"}

    output_fn = TOOL_TEMPLATES[category][action]["output"]

    # Try to pass relevant input data to output function
    try:
        if "url" in input_data:
            return output_fn(input_data["url"])
        elif "path" in input_data:
            return output_fn(input_data["path"])
        elif "temperature" in input_data:
            return output_fn(input_data["temperature"])
        else:
            return output_fn()
    except TypeError:
        # Output function doesn't take arguments
        return output_fn()
