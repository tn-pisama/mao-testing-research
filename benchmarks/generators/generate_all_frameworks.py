"""Generate traces for all multi-agent frameworks.

Generates traces for:
- LangChain/LangGraph (existing)
- AutoGen (Microsoft)
- CrewAI
- n8n

Each framework generates traces with the 14 MAST failure modes.
"""

import asyncio
import os
from pathlib import Path

from src.autogen.trace_generator import AutoGenTraceGenerator
from src.crewai.trace_generator import CrewAITraceGenerator
from src.n8n.trace_generator import N8NTraceGenerator


async def generate_all_framework_traces(
    api_key: str,
    output_dir: str = "traces",
    traces_per_mode: int = 10,
):
    """Generate traces for all frameworks."""

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    frameworks = {
        "autogen": AutoGenTraceGenerator,
        "crewai": CrewAITraceGenerator,
        "n8n": N8NTraceGenerator,
    }

    results = {}

    for name, GeneratorClass in frameworks.items():
        print(f"\n{'='*60}")
        print(f"Generating {name.upper()} traces")
        print(f"{'='*60}")

        generator = GeneratorClass(api_key, output_dir=output_dir)

        for complexity in ["simple", "medium"]:
            print(f"\n  Complexity: {complexity}")
            try:
                traces = await generator.generate_all_traces(
                    traces_per_mode=traces_per_mode,
                    complexity=complexity,
                )
                results[f"{name}_{complexity}"] = {
                    "success": True,
                    "traces_count": sum(len(t) for t in traces.values()),
                    "modes": len(traces),
                }
            except Exception as e:
                print(f"  Error: {e}")
                results[f"{name}_{complexity}"] = {
                    "success": False,
                    "error": str(e),
                }

    return results


async def main():
    """Main entry point."""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Usage: ANTHROPIC_API_KEY=your-key python -m src.generate_all_frameworks")
        return

    print("Multi-Framework Trace Generator")
    print("================================")
    print(f"Frameworks: AutoGen, CrewAI, n8n")
    print(f"Failure modes: 14 (MAST taxonomy)")
    print(f"Traces per mode: 10")
    print(f"Complexity levels: simple, medium")
    print()

    results = await generate_all_framework_traces(
        api_key=api_key,
        traces_per_mode=10,
    )

    print("\n" + "="*60)
    print("GENERATION SUMMARY")
    print("="*60)

    for key, result in results.items():
        status = "✓" if result.get("success") else "✗"
        if result.get("success"):
            print(f"{status} {key}: {result['traces_count']} traces across {result['modes']} modes")
        else:
            print(f"{status} {key}: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
