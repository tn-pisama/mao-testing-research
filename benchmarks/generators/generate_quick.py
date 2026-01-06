"""Quick trace generation for all frameworks (5 traces per mode, simple only)."""

import asyncio
import os
from pathlib import Path

from src.autogen.trace_generator import AutoGenTraceGenerator
from src.crewai.trace_generator import CrewAITraceGenerator
from src.n8n.trace_generator import N8NTraceGenerator


async def generate_quick_traces(api_key: str):
    """Generate 5 traces per mode for each framework (simple only)."""

    generators = {
        "autogen": AutoGenTraceGenerator(api_key, output_dir="traces"),
        "crewai": CrewAITraceGenerator(api_key, output_dir="traces"),
        "n8n": N8NTraceGenerator(api_key, output_dir="traces"),
    }

    for name, generator in generators.items():
        print(f"\n{'='*50}")
        print(f"Generating {name.upper()} traces (5 per mode)")
        print(f"{'='*50}")

        await generator.generate_all_traces(traces_per_mode=5, complexity="simple")

    print("\nDone!")


if __name__ == "__main__":
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
    else:
        asyncio.run(generate_quick_traces(api_key))
