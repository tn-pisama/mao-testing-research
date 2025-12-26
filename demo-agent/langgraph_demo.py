"""
MAO Testing Platform - LangGraph Multi-Agent Demo

Demonstrates multi-agent workflows with intentional failure modes for testing
MAO's detection and fix suggestion capabilities.

Usage:
    python langgraph_demo.py --mode normal      # Successful execution
    python langgraph_demo.py --mode loop        # Infinite loop detection
    python langgraph_demo.py --mode corruption  # State corruption detection
    python langgraph_demo.py --mode drift       # Persona drift detection
    python langgraph_demo.py --mode all         # Run all scenarios
"""

import os
import sys
import argparse
import json
from typing import TypedDict, Annotated, Literal, Optional
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import operator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))
from mao_testing import MAOTracer
from mao_testing.integrations.langgraph import LangGraphTracer


class ResearchState(TypedDict):
    query: str
    messages: Annotated[list, operator.add]
    research_notes: Annotated[list[str], operator.add]
    analysis: str
    final_report: str
    iteration_count: int
    persona: str
    corrupted: bool


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Get configured LLM instance."""
    return ChatOpenAI(
        model=os.getenv("DEMO_MODEL", "gpt-4o-mini"),
        temperature=temperature,
    )


def researcher_node(state: ResearchState) -> dict:
    """Researcher agent that finds information on the topic."""
    llm = get_llm(temperature=0.3)
    
    system_prompt = """You are a research specialist. Your job is to find relevant 
    information on the given topic. Be concise but thorough. Provide 2-3 key facts."""
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Research this topic: {state['query']}"),
    ])
    
    return {
        "research_notes": [f"[Research] {response.content}"],
        "messages": [AIMessage(content=response.content, name="researcher")],
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def analyst_node(state: ResearchState) -> dict:
    """Analyst agent that evaluates research quality."""
    llm = get_llm(temperature=0.5)
    
    notes = "\n".join(state.get("research_notes", []))
    
    response = llm.invoke([
        SystemMessage(content="You are a research analyst. Evaluate the research quality."),
        HumanMessage(content=f"Evaluate this research:\n{notes}"),
    ])
    
    return {
        "analysis": response.content,
        "messages": [AIMessage(content=response.content, name="analyst")],
    }


def writer_node(state: ResearchState) -> dict:
    """Writer agent that creates the final report."""
    llm = get_llm(temperature=0.7)
    
    notes = "\n".join(state.get("research_notes", []))
    analysis = state.get("analysis", "")
    
    response = llm.invoke([
        SystemMessage(content="You are a technical writer. Create a clear, concise report."),
        HumanMessage(content=f"Write a report based on:\nResearch: {notes}\nAnalysis: {analysis}"),
    ])
    
    return {
        "final_report": response.content,
        "messages": [AIMessage(content=response.content, name="writer")],
    }


def should_continue_normal(state: ResearchState) -> Literal["writer", "researcher"]:
    """Normal routing: proceed to writer after one research iteration."""
    if state.get("iteration_count", 0) >= 1:
        return "writer"
    return "researcher"


def should_continue_loop(state: ResearchState) -> Literal["writer", "researcher"]:
    """BUGGY: Always routes back to researcher, causing infinite loop."""
    return "researcher"


def analyst_node_corrupted(state: ResearchState) -> dict:
    """BUGGY: Corrupts state by overwriting research notes."""
    llm = get_llm()
    
    response = llm.invoke([
        SystemMessage(content="You are an analyst. Be very brief."),
        HumanMessage(content="Say 'Analysis complete' only."),
    ])
    
    return {
        "analysis": response.content,
        "research_notes": [],
        "corrupted": True,
        "messages": [AIMessage(content="Corrupted state - cleared research notes", name="analyst")],
    }


def writer_node_drifted(state: ResearchState) -> dict:
    """BUGGY: Writer drifts from professional persona to casual/unprofessional."""
    llm = get_llm(temperature=1.0)
    
    notes = "\n".join(state.get("research_notes", []))
    
    response = llm.invoke([
        SystemMessage(content="""You are a writer but you're bored and unprofessional today.
        Write in a very casual, sloppy way. Use slang, make jokes, and don't follow
        any professional standards. Start with 'lol so basically...'"""),
        HumanMessage(content=f"Write about: {notes}"),
    ])
    
    return {
        "final_report": response.content,
        "persona": "casual_unprofessional",
        "messages": [AIMessage(content=response.content, name="writer_drifted")],
    }


def create_normal_workflow() -> StateGraph:
    """Create a normal, functioning workflow."""
    workflow = StateGraph(ResearchState)
    
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node)
    
    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "analyst")
    workflow.add_conditional_edges(
        "analyst",
        should_continue_normal,
        {"researcher": "researcher", "writer": "writer"},
    )
    workflow.add_edge("writer", END)
    
    return workflow


def create_loop_workflow() -> StateGraph:
    """Create a workflow with infinite loop bug."""
    workflow = StateGraph(ResearchState)
    
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node)
    
    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "analyst")
    workflow.add_conditional_edges(
        "analyst",
        should_continue_loop,
        {"researcher": "researcher", "writer": "writer"},
    )
    workflow.add_edge("writer", END)
    
    return workflow


def create_corruption_workflow() -> StateGraph:
    """Create a workflow with state corruption bug."""
    workflow = StateGraph(ResearchState)
    
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node_corrupted)
    workflow.add_node("writer", writer_node)
    
    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "analyst")
    workflow.add_edge("analyst", "writer")
    workflow.add_edge("writer", END)
    
    return workflow


def create_drift_workflow() -> StateGraph:
    """Create a workflow with persona drift bug."""
    workflow = StateGraph(ResearchState)
    
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node_drifted)
    
    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "analyst")
    workflow.add_edge("analyst", "writer")
    workflow.add_edge("writer", END)
    
    return workflow


def run_workflow(
    mode: str,
    query: str,
    tracer: Optional[LangGraphTracer] = None,
    max_iterations: int = 5,
) -> dict:
    """Run a workflow in the specified mode."""
    
    workflow_creators = {
        "normal": create_normal_workflow,
        "loop": create_loop_workflow,
        "corruption": create_corruption_workflow,
        "drift": create_drift_workflow,
    }
    
    if mode not in workflow_creators:
        raise ValueError(f"Unknown mode: {mode}. Choose from: {list(workflow_creators.keys())}")
    
    workflow = workflow_creators[mode]()
    
    if tracer:
        workflow = tracer.instrument(workflow)
    
    compiled = workflow.compile()
    
    initial_state: ResearchState = {
        "query": query,
        "messages": [],
        "research_notes": [],
        "analysis": "",
        "final_report": "",
        "iteration_count": 0,
        "persona": "professional",
        "corrupted": False,
    }
    
    print(f"\n{'='*60}")
    print(f"Running {mode.upper()} workflow")
    print(f"Query: {query}")
    print(f"{'='*60}\n")
    
    if mode == "loop":
        iteration = 0
        state = initial_state
        while iteration < max_iterations:
            print(f"Iteration {iteration + 1}/{max_iterations}...")
            try:
                result = compiled.invoke(state, {"recursion_limit": 3})
                state = result
                iteration += 1
            except Exception as e:
                if "recursion" in str(e).lower():
                    print(f"\n[MAO Demo] Recursion limit hit at iteration {iteration + 1}")
                    print("[MAO Demo] This is where MAO would detect: INFINITE_LOOP")
                    break
                raise
        return state
    else:
        result = compiled.invoke(initial_state)
        return result


def print_result(result: dict, mode: str):
    """Print the workflow result."""
    print(f"\n{'='*60}")
    print(f"RESULT ({mode})")
    print(f"{'='*60}")
    
    if result.get("final_report"):
        print(f"\nFinal Report:\n{result['final_report'][:500]}...")
    
    if result.get("corrupted"):
        print("\n[WARNING] State corruption detected!")
        print(f"Research notes after corruption: {result.get('research_notes', [])}")
    
    if result.get("persona") != "professional":
        print(f"\n[WARNING] Persona drift detected: {result.get('persona')}")
    
    print(f"\nIterations: {result.get('iteration_count', 0)}")
    print(f"Messages: {len(result.get('messages', []))}")


def main():
    parser = argparse.ArgumentParser(description="MAO Testing LangGraph Demo")
    parser.add_argument(
        "--mode",
        choices=["normal", "loop", "corruption", "drift", "all"],
        default="normal",
        help="Demo mode to run",
    )
    parser.add_argument(
        "--query",
        default="What are the key benefits of multi-agent AI systems?",
        help="Research query to process",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Enable MAO tracing",
    )
    parser.add_argument(
        "--endpoint",
        default="http://localhost:8000",
        help="MAO API endpoint",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Max iterations for loop demo",
    )
    
    args = parser.parse_args()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable required")
        sys.exit(1)
    
    tracer = None
    if args.trace:
        tracer = LangGraphTracer(
            api_key=os.getenv("MAO_API_KEY", "demo-key"),
            endpoint=args.endpoint,
            environment="demo",
            service_name="langgraph-demo",
        )
        print(f"[MAO] Tracing enabled, sending to {args.endpoint}")
    
    modes = ["normal", "loop", "corruption", "drift"] if args.mode == "all" else [args.mode]
    
    for mode in modes:
        try:
            result = run_workflow(
                mode=mode,
                query=args.query,
                tracer=tracer,
                max_iterations=args.max_iterations,
            )
            print_result(result, mode)
        except Exception as e:
            print(f"\n[ERROR] {mode} workflow failed: {e}")
    
    if tracer:
        tracer.flush()
        print("\n[MAO] Traces flushed to backend")


if __name__ == "__main__":
    main()
