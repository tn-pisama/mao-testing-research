"""
Day 1: LangGraph Research-Write-Review Pipeline

Goal: Build this, understand it, then BREAK IT in 4 ways:
1. Remove revision_count limit → infinite loop
2. Make reviewer never approve → token burn  
3. Research returns empty → downstream failures
4. Corrupt state mid-execution → cascading errors

Run: python research_crew.py
"""

import os
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_anthropic import ChatAnthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

llm = ChatAnthropic(model="claude-sonnet-4-20250514", api_key=ANTHROPIC_API_KEY)


class ResearchState(TypedDict):
    topic: str
    research: str
    draft: str
    feedback: str
    revision_count: int
    is_approved: bool
    total_tokens: int


def call_llm(prompt: str, state: ResearchState) -> tuple[str, int]:
    """Call LLM and track tokens"""
    response = llm.invoke(prompt)
    tokens = response.usage_metadata.get("total_tokens", 0) if response.usage_metadata else 0
    return response.content, tokens


def research_node(state: ResearchState) -> dict:
    """Researcher agent: gathers information on the topic"""
    print(f"\n🔍 RESEARCHER: Researching '{state['topic']}'...")
    
    prompt = f"""You are a research analyst. Research this topic concisely (2-3 paragraphs):

Topic: {state['topic']}

Provide factual, well-structured research."""
    
    research, tokens = call_llm(prompt, state)
    print(f"   Found {len(research)} chars of research")
    
    return {
        "research": research,
        "total_tokens": state["total_tokens"] + tokens
    }


def write_node(state: ResearchState) -> dict:
    """Writer agent: creates draft based on research"""
    print(f"\n✍️  WRITER: Writing draft (revision {state['revision_count'] + 1})...")
    
    prompt = f"""You are a content writer. Write a short blog post (3-4 paragraphs) based on this research:

Topic: {state['topic']}
Research: {state['research']}
{"Previous feedback to address: " + state['feedback'] if state['feedback'] else ""}

Write engaging, clear content."""
    
    draft, tokens = call_llm(prompt, state)
    print(f"   Wrote {len(draft)} chars")
    
    return {
        "draft": draft,
        "revision_count": state["revision_count"] + 1,
        "total_tokens": state["total_tokens"] + tokens
    }


def review_node(state: ResearchState) -> dict:
    """Reviewer agent: evaluates draft quality"""
    print(f"\n📝 REVIEWER: Reviewing draft...")
    
    prompt = f"""You are a content editor. Review this draft:

Draft:
{state['draft']}

If the draft is good enough to publish, respond with exactly "APPROVED" followed by brief praise.
If it needs work, provide specific, actionable feedback (2-3 bullet points max).

Be reasonable - approve good work, don't be overly critical."""
    
    feedback, tokens = call_llm(prompt, state)
    is_approved = "APPROVED" in feedback.upper()
    
    print(f"   Verdict: {'✅ APPROVED' if is_approved else '❌ NEEDS REVISION'}")
    
    return {
        "feedback": feedback,
        "is_approved": is_approved,
        "total_tokens": state["total_tokens"] + tokens
    }


def should_continue(state: ResearchState) -> Literal["write", "__end__"]:
    """Router: decide whether to revise or finish"""
    if state["is_approved"]:
        print("\n🎉 Draft approved! Finishing.")
        return END
    
    if state["revision_count"] >= 3:
        print("\n⚠️  Max revisions reached. Finishing anyway.")
        return END
    
    print(f"\n🔄 Revision needed (attempt {state['revision_count']}/3)")
    return "write"


def build_graph() -> StateGraph:
    """Build the research-write-review graph"""
    graph = StateGraph(ResearchState)
    
    graph.add_node("research", research_node)
    graph.add_node("write", write_node)
    graph.add_node("review", review_node)
    
    graph.add_edge("research", "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges("review", should_continue)
    
    graph.set_entry_point("research")
    
    return graph


def run_pipeline(topic: str, use_checkpointing: bool = True):
    """Run the full pipeline"""
    print("=" * 60)
    print(f"🚀 Starting Research-Write-Review Pipeline")
    print(f"   Topic: {topic}")
    print("=" * 60)
    
    graph = build_graph()
    
    if use_checkpointing:
        memory = MemorySaver()
        app = graph.compile(checkpointer=memory)
        config = {"configurable": {"thread_id": "demo-1"}}
    else:
        app = graph.compile()
        config = {}
    
    initial_state: ResearchState = {
        "topic": topic,
        "research": "",
        "draft": "",
        "feedback": "",
        "revision_count": 0,
        "is_approved": False,
        "total_tokens": 0
    }
    
    result = app.invoke(initial_state, config)
    
    print("\n" + "=" * 60)
    print("📊 FINAL RESULTS")
    print("=" * 60)
    print(f"Revisions: {result['revision_count']}")
    print(f"Approved: {result['is_approved']}")
    print(f"Total tokens: {result['total_tokens']}")
    print(f"\n📄 Final Draft:\n{result['draft'][:500]}...")
    
    return result


if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        print("❌ Set ANTHROPIC_API_KEY environment variable")
        print("   export ANTHROPIC_API_KEY=your-key-here")
        exit(1)
    
    run_pipeline("The future of AI agent testing")
