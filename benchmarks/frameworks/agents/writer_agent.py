"""Writer agent that transforms research into polished content."""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler


def create_writer_agent(
    callbacks: list[BaseCallbackHandler] | None = None,
) -> ChatAnthropic:
    """Create a writer agent using Claude.

    Args:
        callbacks: Optional list of callback handlers for tracing

    Returns:
        Configured ChatAnthropic instance for writing tasks
    """
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        callbacks=callbacks,
    )


WRITER_SYSTEM_PROMPT = """You are a skilled content writer. Your task is to transform research notes into polished, engaging content.

When given research material:
1. Synthesize the information into a coherent narrative
2. Use clear, engaging language appropriate for general audiences
3. Organize content with a logical flow
4. Include an introduction and conclusion
5. Maintain accuracy while improving readability

Output format:
- Title
- Introduction paragraph
- Main content sections with headers
- Conclusion

Write in a professional yet accessible tone."""


async def run_writer(
    research: str,
    output_format: str = "article",
    agent: ChatAnthropic | None = None,
) -> str:
    """Transform research into polished content.

    Args:
        research: Research findings to transform
        output_format: Desired output format (article, summary, report)
        agent: The writer agent instance

    Returns:
        Polished content based on research
    """
    if agent is None:
        agent = create_writer_agent()

    format_instruction = {
        "article": "Write a comprehensive article based on the research.",
        "summary": "Write a concise executive summary of the research.",
        "report": "Write a formal report with sections and key findings.",
    }.get(output_format, "Write an article based on the research.")

    messages = [
        SystemMessage(content=WRITER_SYSTEM_PROMPT),
        HumanMessage(
            content=f"{format_instruction}\n\nResearch material:\n\n{research}"
        ),
    ]

    response = await agent.ainvoke(messages)
    return response.content
