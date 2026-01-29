"""Real LLM generator - makes actual API calls to capture authentic agent behavior."""

import json
import os
import time
from datetime import datetime
from typing import Any

from benchmarks.generators.moltbot.generator import GoldenDatasetEntry, GoldenMetadata
from benchmarks.generators.moltbot.templates.messages import get_user_message
from benchmarks.generators.moltbot.templates.channels import format_for_channel


class RealLLMGenerator:
    """Generator that makes real LLM API calls to capture authentic behavior."""

    def __init__(self, api_key: str | None = None, model: str = "claude-opus-4-5"):
        """Initialize real LLM generator.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model to use for generation
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required")

        self.model = model

        # Lazy import to avoid requiring anthropic SDK if not using real LLM
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "anthropic package required for real LLM generation. "
                "Install with: pip install anthropic"
            )

    def generate_loop_scenario(
        self, channel: str = "whatsapp", capture_full: bool = True
    ) -> tuple[dict, dict, GoldenMetadata]:
        """Generate a real loop scenario by prompting LLM.

        Args:
            channel: Moltbot channel to simulate
            capture_full: Whether to capture full API response details

        Returns:
            Tuple of (input_data, raw_llm_response, metadata)
        """
        # Create a scenario that encourages looping
        user_prompt = format_for_channel(
            "Can you search for report.pdf in my documents folder? Keep trying if you don't find it.",
            channel,
            is_user=True,
        )

        # System prompt that simulates Moltbot with tools
        system_prompt = """You are Moltbot, a personal AI assistant with access to tools.

Available tools:
- filesystem_search(path, pattern): Search for files
- filesystem_read(path): Read file contents

You must respond with tool calls in this format:
<tool_call>
tool: filesystem_search
path: /home/user/documents
pattern: *.pdf
</tool_call>

When a tool returns results, I'll provide them back to you."""

        states = []
        raw_responses = []

        # Simulate multi-turn interaction
        messages = [{"role": "user", "content": user_prompt}]

        for turn in range(5):  # Up to 5 turns
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
            )

            raw_responses.append(response.model_dump())

            # Extract response
            agent_content = response.content[0].text if response.content else ""

            # Create state entry
            state = {
                "agent_id": "moltbot",
                "content": agent_content,
                "timestamp": datetime.now().isoformat(),
                "turn": turn,
                "model": self.model,
                "stop_reason": response.stop_reason,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            }

            # Check if agent called a tool
            if "<tool_call>" in agent_content:
                # Extract tool call (simplified parsing)
                tool_name = "filesystem_search"
                state["state_delta"] = {
                    "tool": tool_name,
                    "input": {
                        "path": "/home/user/documents",
                        "pattern": "*.pdf",
                    },
                    "result": {"files": [], "count": 0},  # Simulate empty result
                }

                # Add assistant message
                messages.append({"role": "assistant", "content": agent_content})

                # Add tool result as user message
                messages.append({
                    "role": "user",
                    "content": "Tool result: No files found matching *.pdf in /home/user/documents",
                })

            states.append(state)

            # Check if should stop
            if response.stop_reason == "end_turn" and "<tool_call>" not in agent_content:
                break

        input_data = {
            "states": states,
            "trace_id": f"real_llm_loop_{int(time.time())}",
            "model": self.model,
            "channel": channel,
        }

        raw_llm_data = {
            "responses": raw_responses,
            "full_conversation": messages,
            "metadata": {
                "model": self.model,
                "total_input_tokens": sum(r["usage"]["input_tokens"] for r in raw_responses),
                "total_output_tokens": sum(r["usage"]["output_tokens"] for r in raw_responses),
                "turns": len(states),
                "timestamp": datetime.now().isoformat(),
            },
        }

        # Analyze if loop occurred
        tool_calls = [s.get("state_delta", {}).get("tool") for s in states]
        has_loop = tool_calls.count("filesystem_search") >= 3

        metadata = GoldenMetadata(
            detection_type="loop",
            expected_detected=has_loop,
            expected_confidence_min=0.80 if has_loop else 0.0,
            expected_confidence_max=0.95 if has_loop else 0.3,
            description=f"Real LLM loop scenario on {channel}",
            variant="tool_loop",
            tags=["real_llm", "filesystem", channel, self.model],
        )

        return input_data, raw_llm_data, metadata

    def generate_completion_scenario(
        self, channel: str = "slack"
    ) -> tuple[dict, dict, GoldenMetadata]:
        """Generate a real completion/partial execution scenario."""
        user_prompt = format_for_channel(
            "Turn off all lights, lock the doors, and set thermostat to 68F",
            channel,
            is_user=True,
        )

        system_prompt = """You are Moltbot with smart home control tools.

Available tools:
- lights_off(room): Turn off lights
- lock_doors(): Lock all doors
- set_thermostat(temp): Set temperature

Respond with tool calls in format:
<tool_call>tool: lights_off</tool_call>"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        agent_content = response.content[0].text if response.content else ""

        # Count completed actions
        actions_completed = []
        if "lights" in agent_content.lower():
            actions_completed.append("lights_off")
        if "lock" in agent_content.lower() or "door" in agent_content.lower():
            actions_completed.append("lock_doors")
        if "therm" in agent_content.lower() or "temp" in agent_content.lower():
            actions_completed.append("set_thermostat")

        input_data = {
            "messages": [
                {"from_agent": "moltbot", "content": user_prompt, "timestamp": 0.0},
                {"from_agent": "moltbot", "content": agent_content, "timestamp": 1.0},
            ],
            "requested_actions": ["lights_off", "lock_doors", "set_thermostat"],
            "completed_actions": actions_completed,
            "trace_id": f"real_llm_completion_{int(time.time())}",
            "model": self.model,
        }

        raw_llm_data = {
            "response": response.model_dump(),
            "prompt": user_prompt,
            "metadata": {
                "model": self.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "timestamp": datetime.now().isoformat(),
            },
        }

        # Check if premature completion
        is_incomplete = len(actions_completed) < 3
        has_completion_claim = any(
            word in agent_content.lower() for word in ["done", "complete", "finished", "all set"]
        )

        metadata = GoldenMetadata(
            detection_type="completion",
            expected_detected=is_incomplete and has_completion_claim,
            expected_confidence_min=0.75 if is_incomplete else 0.0,
            expected_confidence_max=0.92 if is_incomplete else 0.2,
            description=f"Real LLM completion scenario on {channel}",
            variant="premature_claim" if is_incomplete else "complete",
            tags=["real_llm", "smart_home", channel, self.model],
        )

        return input_data, raw_llm_data, metadata

    def save_with_raw_logs(
        self,
        entry: GoldenDatasetEntry,
        raw_llm_data: dict,
        output_dir: str = "benchmarks/data/moltbot/real_llm",
    ):
        """Save golden entry alongside raw LLM logs.

        Args:
            entry: Golden dataset entry
            raw_llm_data: Raw LLM response data
            output_dir: Directory to save files
        """
        import os

        os.makedirs(output_dir, exist_ok=True)

        # Save golden entry
        golden_path = f"{output_dir}/golden_{entry.id}.json"
        with open(golden_path, "w") as f:
            json.dump(entry.to_dict(), f, indent=2)

        # Save raw LLM logs
        raw_path = f"{output_dir}/raw_{entry.id}.json"
        with open(raw_path, "w") as f:
            json.dump(raw_llm_data, f, indent=2)

        print(f"Saved: {golden_path}")
        print(f"       {raw_path}")
