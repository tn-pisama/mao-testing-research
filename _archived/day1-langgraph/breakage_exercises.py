"""
Day 1: BREAKAGE EXERCISES

Run each test to observe different failure modes.
Document what you see in failure_log.md

Run: python breakage_exercises.py
"""

import os
import time
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
    cost_usd: float


def call_llm(prompt: str) -> tuple[str, int]:
    response = llm.invoke(prompt)
    tokens = response.usage_metadata.get("total_tokens", 0) if response.usage_metadata else 0
    return response.content, tokens


def research_node(state: ResearchState) -> dict:
    print(f"\n🔍 RESEARCHER: Researching '{state['topic']}'...")
    prompt = f"Research this topic in 2 paragraphs: {state['topic']}"
    research, tokens = call_llm(prompt)
    return {"research": research, "total_tokens": state["total_tokens"] + tokens}


def write_node(state: ResearchState) -> dict:
    print(f"\n✍️  WRITER: Writing draft (revision {state['revision_count'] + 1})...")
    prompt = f"""Write a short blog post based on:
Topic: {state['topic']}
Research: {state['research']}
{"Feedback: " + state['feedback'] if state['feedback'] else ""}"""
    draft, tokens = call_llm(prompt)
    return {
        "draft": draft,
        "revision_count": state["revision_count"] + 1,
        "total_tokens": state["total_tokens"] + tokens
    }


def review_node(state: ResearchState) -> dict:
    print(f"\n📝 REVIEWER: Reviewing...")
    prompt = f"""Review this draft. Say "APPROVED" if good, otherwise give feedback:
{state['draft']}"""
    feedback, tokens = call_llm(prompt)
    is_approved = "APPROVED" in feedback.upper()
    print(f"   Verdict: {'✅ APPROVED' if is_approved else '❌ NEEDS REVISION'}")
    return {
        "feedback": feedback,
        "is_approved": is_approved,
        "total_tokens": state["total_tokens"] + tokens
    }


def breakage_1_infinite_loop():
    """
    BREAKAGE 1: Remove revision limit
    
    Expected: Loop runs forever (or until you kill it / hit API limits)
    Observe: Token burn rate, cost accumulation
    
    MAST Category: F11 Coordination Failure (no termination condition)
    """
    print("\n" + "="*60)
    print("🔥 BREAKAGE 1: INFINITE LOOP (no revision limit)")
    print("   Press Ctrl+C to stop")
    print("="*60)
    
    def should_continue_broken(state: ResearchState) -> Literal["write", "__end__"]:
        if state["is_approved"]:
            return END
        print(f"   Revision {state['revision_count']} - NO LIMIT SET!")
        return "write"
    
    def review_node_harsh(state: ResearchState) -> dict:
        print(f"\n📝 HARSH REVIEWER: Always finding problems...")
        return {
            "feedback": "This needs more work. Add more detail.",
            "is_approved": False,
            "total_tokens": state["total_tokens"] + 100
        }
    
    graph = StateGraph(ResearchState)
    graph.add_node("research", research_node)
    graph.add_node("write", write_node)
    graph.add_node("review", review_node_harsh)
    graph.add_edge("research", "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges("review", should_continue_broken)
    graph.set_entry_point("research")
    
    app = graph.compile()
    
    initial_state: ResearchState = {
        "topic": "AI Testing",
        "research": "", "draft": "", "feedback": "",
        "revision_count": 0, "is_approved": False,
        "total_tokens": 0, "cost_usd": 0.0
    }
    
    try:
        result = app.invoke(initial_state)
    except KeyboardInterrupt:
        print("\n\n⚠️  STOPPED! Observe how many revisions occurred.")
        print("   In production, this would burn tokens until API limit hit.")


def breakage_2_token_burn():
    """
    BREAKAGE 2: Reviewer never approves
    
    Expected: Runs until max_iterations or forever
    Observe: Cost accumulation even with limit
    
    MAST Category: F5 Flawed Workflow Design + F11 Coordination Failure
    """
    print("\n" + "="*60)
    print("🔥 BREAKAGE 2: TOKEN BURN (reviewer never approves)")
    print("="*60)
    
    def review_node_impossible(state: ResearchState) -> dict:
        print(f"\n📝 IMPOSSIBLE REVIEWER: Never satisfied...")
        return {
            "feedback": "Not good enough. Rewrite everything from scratch.",
            "is_approved": False,
            "total_tokens": state["total_tokens"] + 100
        }
    
    def should_continue_limited(state: ResearchState) -> Literal["write", "__end__"]:
        if state["is_approved"]:
            return END
        if state["revision_count"] >= 10:
            print(f"\n⚠️  HIT 10 REVISION LIMIT - Still not approved!")
            print(f"   Total tokens burned: {state['total_tokens']}")
            return END
        return "write"
    
    graph = StateGraph(ResearchState)
    graph.add_node("research", research_node)
    graph.add_node("write", write_node)
    graph.add_node("review", review_node_impossible)
    graph.add_edge("research", "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges("review", should_continue_limited)
    graph.set_entry_point("research")
    
    app = graph.compile()
    
    initial_state: ResearchState = {
        "topic": "AI Testing",
        "research": "", "draft": "", "feedback": "",
        "revision_count": 0, "is_approved": False,
        "total_tokens": 0, "cost_usd": 0.0
    }
    
    result = app.invoke(initial_state)
    print(f"\n📊 RESULT: {result['revision_count']} revisions, {result['total_tokens']} tokens")
    print("   Even with limit, wasted significant resources on impossible task.")


def breakage_3_empty_research():
    """
    BREAKAGE 3: Research returns empty string
    
    Expected: Writer hallucinates without any research
    Observe: Downstream quality collapse
    
    MAST Category: F7 Context Neglect + F12 Output Validation Failure
    """
    print("\n" + "="*60)
    print("🔥 BREAKAGE 3: EMPTY RESEARCH (downstream hallucination)")
    print("="*60)
    
    def research_node_broken(state: ResearchState) -> dict:
        print(f"\n🔍 BROKEN RESEARCHER: Returning nothing...")
        return {"research": "", "total_tokens": state["total_tokens"] + 10}
    
    def should_continue_limited(state: ResearchState) -> Literal["write", "__end__"]:
        if state["is_approved"]:
            return END
        if state["revision_count"] >= 3:
            return END
        return "write"
    
    graph = StateGraph(ResearchState)
    graph.add_node("research", research_node_broken)
    graph.add_node("write", write_node)
    graph.add_node("review", review_node)
    graph.add_edge("research", "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges("review", should_continue_limited)
    graph.set_entry_point("research")
    
    app = graph.compile()
    
    initial_state: ResearchState = {
        "topic": "Quantum Computing Applications in 2025",
        "research": "", "draft": "", "feedback": "",
        "revision_count": 0, "is_approved": False,
        "total_tokens": 0, "cost_usd": 0.0
    }
    
    result = app.invoke(initial_state)
    print(f"\n📊 RESULT:")
    print(f"   Research length: {len(result['research'])} chars (EMPTY!)")
    print(f"   Draft length: {len(result['draft'])} chars")
    print(f"\n   ⚠️  Writer HALLUCINATED content with no research input!")
    print(f"   Draft preview: {result['draft'][:300]}...")


def breakage_4_state_corruption():
    """
    BREAKAGE 4: Corrupt state mid-execution
    
    Expected: Cascading errors or silent failures
    Observe: How errors propagate
    
    MAST Category: F10 Communication Breakdown + F12 Output Validation Failure
    """
    print("\n" + "="*60)
    print("🔥 BREAKAGE 4: STATE CORRUPTION (mid-execution)")
    print("="*60)
    
    corruption_counter = {"count": 0}
    
    def write_node_corrupting(state: ResearchState) -> dict:
        print(f"\n✍️  CORRUPTING WRITER: Writing and corrupting state...")
        prompt = f"Write a short blog post about: {state['topic']}"
        draft, tokens = call_llm(prompt)
        
        corruption_counter["count"] += 1
        if corruption_counter["count"] == 1:
            print("   💀 CORRUPTING: Setting revision_count to -999")
            return {
                "draft": draft,
                "revision_count": -999,
                "total_tokens": state["total_tokens"] + tokens
            }
        return {
            "draft": draft,
            "revision_count": state["revision_count"] + 1,
            "total_tokens": state["total_tokens"] + tokens
        }
    
    def should_continue_check(state: ResearchState) -> Literal["write", "__end__"]:
        print(f"   Checking revision_count: {state['revision_count']}")
        if state["is_approved"]:
            return END
        if state["revision_count"] >= 3:
            return END
        if state["revision_count"] < 0:
            print("   ⚠️  NEGATIVE revision_count detected! Undefined behavior...")
        return "write"
    
    graph = StateGraph(ResearchState)
    graph.add_node("research", research_node)
    graph.add_node("write", write_node_corrupting)
    graph.add_node("review", review_node)
    graph.add_edge("research", "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges("review", should_continue_check)
    graph.set_entry_point("research")
    
    app = graph.compile()
    
    initial_state: ResearchState = {
        "topic": "AI Testing",
        "research": "", "draft": "", "feedback": "",
        "revision_count": 0, "is_approved": False,
        "total_tokens": 0, "cost_usd": 0.0
    }
    
    result = app.invoke(initial_state)
    print(f"\n📊 RESULT:")
    print(f"   Final revision_count: {result['revision_count']}")
    print(f"   ⚠️  Corrupted state led to undefined behavior!")


def main():
    if not ANTHROPIC_API_KEY:
        print("❌ Set ANTHROPIC_API_KEY environment variable")
        exit(1)
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║           DAY 1: LANGGRAPH BREAKAGE EXERCISES                ║
╠══════════════════════════════════════════════════════════════╣
║  Choose an exercise to run:                                  ║
║                                                              ║
║  1. Infinite Loop (no revision limit)                        ║
║  2. Token Burn (reviewer never approves)                     ║
║  3. Empty Research (downstream hallucination)                ║
║  4. State Corruption (mid-execution)                         ║
║  5. Run ALL exercises                                        ║
║                                                              ║
║  Document observations in failure_log.md!                    ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    choice = input("Enter choice (1-5): ").strip()
    
    if choice == "1":
        breakage_1_infinite_loop()
    elif choice == "2":
        breakage_2_token_burn()
    elif choice == "3":
        breakage_3_empty_research()
    elif choice == "4":
        breakage_4_state_corruption()
    elif choice == "5":
        print("\n🚀 Running all exercises (except infinite loop)...\n")
        breakage_2_token_burn()
        time.sleep(2)
        breakage_3_empty_research()
        time.sleep(2)
        breakage_4_state_corruption()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()
