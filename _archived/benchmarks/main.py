"""Main entry point for the multi-agent system."""

import asyncio
import os

from dotenv import load_dotenv

from src.graph.workflow import run_workflow
from src.tracing import OpenTelemetryCallbackHandler, setup_tracing


async def main() -> None:
    """Run the multi-agent workflow with OpenTelemetry tracing."""
    # Load environment variables
    load_dotenv()

    # Get configuration from environment
    service_name = os.getenv("OTEL_SERVICE_NAME", "langchain-agents")
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    # Initialize OpenTelemetry tracing
    tracer = setup_tracing(
        service_name=service_name,
        otlp_endpoint=otlp_endpoint,
        use_console=True,  # Always show traces in console
    )

    # Create the callback handler
    otel_handler = OpenTelemetryCallbackHandler(tracer=tracer)

    # Example topic to research and write about
    topic = """
    The impact of artificial intelligence on software development practices,
    including code generation, testing automation, and developer productivity.
    """

    print(f"Starting multi-agent workflow...")
    print(f"Topic: {topic.strip()}")
    print("-" * 60)

    # Run the workflow with tracing
    with tracer.start_as_current_span("workflow.research_and_write") as span:
        span.set_attribute("workflow.topic", topic.strip())
        span.set_attribute("workflow.output_format", "article")

        result = await run_workflow(
            topic=topic,
            output_format="article",
            otel_handler=otel_handler,
        )

        span.set_attribute("workflow.success", True)

    print("\n" + "=" * 60)
    print("GENERATED CONTENT:")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
