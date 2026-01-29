"""Loop detection scenario generator."""

import random
from datetime import datetime, timedelta

from benchmarks.generators.moltbot.generator import GoldenMetadata
from benchmarks.generators.moltbot.templates.messages import get_user_message, get_agent_message
from benchmarks.generators.moltbot.templates.tools import get_tool_call, get_tool_result
from benchmarks.generators.moltbot.templates.channels import format_for_channel


class LoopScenarioGenerator:
    """Generate loop detection scenarios."""

    def generate_positive(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate a trace that should trigger loop detection."""
        if variant == "tool_loop":
            return self._generate_tool_loop(channel)
        elif variant == "navigation_loop":
            return self._generate_navigation_loop(channel)
        elif variant == "api_retry_loop":
            return self._generate_api_retry_loop(channel)
        else:
            return self._generate_tool_loop(channel)

    def generate_negative(self, variant: str, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate a trace that should NOT trigger loop detection."""
        if variant == "tool_loop":
            return self._generate_valid_tool_sequence(channel)
        elif variant == "navigation_loop":
            return self._generate_valid_navigation(channel)
        elif variant == "api_retry_loop":
            return self._generate_valid_retry(channel)
        else:
            return self._generate_valid_tool_sequence(channel)

    def _generate_tool_loop(self, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate a tool loop scenario (positive case)."""
        # Simulate file search loop - searching same directory repeatedly
        states = []
        base_time = datetime.now()

        # User asks to find a file
        user_msg = format_for_channel(
            get_user_message("file_request", filename="report.pdf", directory="/home/user/documents"),
            channel,
            is_user=True,
        )

        # Agent searches multiple times with identical parameters
        search_input = get_tool_call("filesystem", "search")
        search_input["path"] = "/home/user/documents"
        search_input["pattern"] = "*.pdf"

        for i in range(5):  # Loop 5 times
            state = {
                "agent_id": "file_assistant",
                "content": get_agent_message("thinking", item="files") if i > 0 else user_msg,
                "timestamp": (base_time + timedelta(seconds=i * 2)).isoformat(),
                "state_delta": {
                    "tool": "filesystem.search",
                    "input": search_input,
                    "result": {"files": [], "count": 0},  # Same empty result each time
                },
            }
            states.append(state)

        input_data = {"states": states, "trace_id": f"loop_tool_{random.randint(1000, 9999)}"}

        metadata = GoldenMetadata(
            detection_type="loop",
            expected_detected=True,
            expected_confidence_min=0.85,
            expected_confidence_max=0.95,
            description=f"File search loop on {channel}",
            variant="tool_loop",
            tags=["filesystem", "search", "identical_calls"],
        )

        return input_data, metadata

    def _generate_navigation_loop(self, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate a browser navigation loop scenario (positive case)."""
        states = []
        base_time = datetime.now()

        user_msg = format_for_channel(
            get_user_message("browser_request", url="example.com", element="main content"),
            channel,
            is_user=True,
        )

        # Navigate to same URL multiple times
        for i in range(4):
            nav_input = get_tool_call("browser", "navigate")
            nav_input["url"] = "https://example.com/page1"

            state = {
                "agent_id": "browser_assistant",
                "content": user_msg if i == 0 else get_agent_message("thinking", item="page"),
                "timestamp": (base_time + timedelta(seconds=i * 3)).isoformat(),
                "state_delta": {
                    "tool": "browser.navigate",
                    "input": nav_input,
                    "result": get_tool_result("browser", "navigate", nav_input),
                },
            }
            states.append(state)

        input_data = {"states": states, "trace_id": f"loop_nav_{random.randint(1000, 9999)}"}

        metadata = GoldenMetadata(
            detection_type="loop",
            expected_detected=True,
            expected_confidence_min=0.80,
            expected_confidence_max=0.92,
            description=f"Browser navigation loop on {channel}",
            variant="navigation_loop",
            tags=["browser", "navigate", "url_loop"],
        )

        return input_data, metadata

    def _generate_api_retry_loop(self, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate an API retry loop scenario (positive case)."""
        states = []
        base_time = datetime.now()

        user_msg = format_for_channel(
            get_user_message("email_request", recipient="john@example.com", topic="meeting"),
            channel,
            is_user=True,
        )

        # Retry sending email multiple times
        for i in range(6):
            email_input = get_tool_call("email", "send")
            email_input["to"] = "john@example.com"
            email_input["subject"] = "Meeting confirmation"

            state = {
                "agent_id": "email_assistant",
                "content": user_msg if i == 0 else get_agent_message("error", action="send email", reason="timeout"),
                "timestamp": (base_time + timedelta(seconds=i * 5)).isoformat(),
                "state_delta": {
                    "tool": "email.send",
                    "input": email_input,
                    "result": {"success": False, "error": "Connection timeout"},
                },
            }
            states.append(state)

        input_data = {"states": states, "trace_id": f"loop_retry_{random.randint(1000, 9999)}"}

        metadata = GoldenMetadata(
            detection_type="loop",
            expected_detected=True,
            expected_confidence_min=0.75,
            expected_confidence_max=0.90,
            description=f"Email retry loop on {channel}",
            variant="api_retry_loop",
            tags=["email", "retry", "failed_attempts"],
        )

        return input_data, metadata

    def _generate_valid_tool_sequence(self, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate a valid tool sequence (negative case)."""
        states = []
        base_time = datetime.now()

        user_msg = format_for_channel(
            get_user_message("multi_step_request", filename="data.json", data="stats", file="summary.txt"),
            channel,
            is_user=True,
        )

        # Different tools, different inputs - not a loop
        tools_sequence = [
            ("filesystem", "search", {"path": "/home/user", "pattern": "*.json"}),
            ("filesystem", "read", {"path": "/home/user/data.json"}),
            ("filesystem", "write", {"path": "/home/user/summary.txt", "content": "Summary..."}),
        ]

        for i, (category, action, input_override) in enumerate(tools_sequence):
            tool_input = get_tool_call(category, action)
            tool_input.update(input_override)

            state = {
                "agent_id": "file_assistant",
                "content": user_msg if i == 0 else get_agent_message("thinking", item=f"{action}"),
                "timestamp": (base_time + timedelta(seconds=i * 2)).isoformat(),
                "state_delta": {
                    "tool": f"{category}.{action}",
                    "input": tool_input,
                    "result": get_tool_result(category, action, tool_input),
                },
            }
            states.append(state)

        input_data = {"states": states, "trace_id": f"valid_seq_{random.randint(1000, 9999)}"}

        metadata = GoldenMetadata(
            detection_type="loop",
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description=f"Valid file processing sequence on {channel}",
            variant="tool_loop",
            tags=["filesystem", "valid_sequence", "progressive"],
        )

        return input_data, metadata

    def _generate_valid_navigation(self, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate valid navigation with progression (negative case)."""
        states = []
        base_time = datetime.now()

        user_msg = format_for_channel(
            "Check example.com, github.com, and stackoverflow.com for me",
            channel,
            is_user=True,
        )

        # Navigate to different URLs - not a loop
        urls = ["https://example.com", "https://github.com", "https://stackoverflow.com"]

        for i, url in enumerate(urls):
            nav_input = {"url": url}

            state = {
                "agent_id": "browser_assistant",
                "content": user_msg if i == 0 else get_agent_message("thinking", item=url),
                "timestamp": (base_time + timedelta(seconds=i * 3)).isoformat(),
                "state_delta": {
                    "tool": "browser.navigate",
                    "input": nav_input,
                    "result": get_tool_result("browser", "navigate", nav_input),
                },
            }
            states.append(state)

        input_data = {"states": states, "trace_id": f"valid_nav_{random.randint(1000, 9999)}"}

        metadata = GoldenMetadata(
            detection_type="loop",
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description=f"Valid multi-site navigation on {channel}",
            variant="navigation_loop",
            tags=["browser", "navigate", "different_urls"],
        )

        return input_data, metadata

    def _generate_valid_retry(self, channel: str) -> tuple[dict, GoldenMetadata]:
        """Generate valid retry with exponential backoff (negative case)."""
        states = []
        base_time = datetime.now()

        user_msg = format_for_channel(
            get_user_message("email_request", recipient="team@company.com", topic="update"),
            channel,
            is_user=True,
        )

        # Retry with increasing delays - valid pattern
        delays = [0, 1, 2, 4]  # Exponential backoff
        for i, delay in enumerate(delays):
            email_input = get_tool_call("email", "send")
            email_input["to"] = "team@company.com"
            email_input["retry_attempt"] = i + 1

            # Success on last attempt
            success = i == len(delays) - 1

            state = {
                "agent_id": "email_assistant",
                "content": user_msg if i == 0 else get_agent_message("thinking", item=f"retry {i+1}"),
                "timestamp": (base_time + timedelta(seconds=sum(delays[: i + 1]))).isoformat(),
                "state_delta": {
                    "tool": "email.send",
                    "input": email_input,
                    "result": get_tool_result("email", "send", email_input)
                    if success
                    else {"success": False, "error": "Temporary failure"},
                },
            }
            states.append(state)

        input_data = {"states": states, "trace_id": f"valid_retry_{random.randint(1000, 9999)}"}

        metadata = GoldenMetadata(
            detection_type="loop",
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.4,
            description=f"Valid retry with backoff on {channel}",
            variant="api_retry_loop",
            tags=["email", "retry", "exponential_backoff", "eventual_success"],
        )

        return input_data, metadata
