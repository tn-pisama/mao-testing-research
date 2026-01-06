"""Research agent that gathers information on a topic."""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler


def create_research_agent(
    callbacks: list[BaseCallbackHandler] | None = None,
) -> ChatAnthropic:
    """Create a research agent using Claude.

    Args:
        callbacks: Optional list of callback handlers for tracing

    Returns:
        Configured ChatAnthropic instance for research tasks
    """
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        callbacks=callbacks,
    )


RESEARCH_SYSTEM_PROMPT = """You are a research assistant. Your task is to analyze and research topics thoroughly.

When given a topic:
1. Break down the topic into key aspects
2. Provide factual, well-organized information
3. Include relevant context and background
4. Highlight important points and insights
5. Note any areas of uncertainty or debate

Format your research as structured notes with clear sections.
Be thorough but concise. Focus on accuracy and relevance."""


async def run_research(
    topic: str,
    agent: ChatAnthropic,
) -> str:
    """Execute research on a given topic.

    Args:
        topic: The topic to research
        agent: The research agent instance

    Returns:
        Research findings as structured text
    """
    messages = [
        SystemMessage(content=RESEARCH_SYSTEM_PROMPT),
        HumanMessage(content=f"Research the following topic thoroughly:\n\n{topic}"),
    ]

    response = await agent.ainvoke(messages)
    return response.content
