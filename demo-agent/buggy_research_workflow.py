"""
Demo agent with intentional infinite loop bug.
Used for live demos to show MAO Testing Platform detection capabilities.
"""
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
import operator


class ResearchState(TypedDict):
    query: str
    research_notes: Annotated[list[str], operator.add]
    analysis: str
    final_report: str
    iteration_count: int


def researcher_node(state: ResearchState) -> ResearchState:
    """Researcher agent that finds information."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    response = llm.invoke(f"Research the following topic briefly: {state['query']}")
    
    return {
        "research_notes": [response.content],
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def analyst_node(state: ResearchState) -> ResearchState:
    """
    Analyst agent with INTENTIONAL BUG:
    Always asks for more research, creating an infinite loop.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    response = llm.invoke(
        f"Analyze these research notes and determine if more research is needed:\n"
        f"{state['research_notes']}\n\n"
        f"IMPORTANT: Always say you need more detailed information."
    )
    
    return {
        "analysis": response.content,
    }


def should_continue(state: ResearchState) -> Literal["researcher", "writer"]:
    """
    INTENTIONAL BUG: Always routes back to researcher.
    In production, this should check if research is sufficient.
    """
    return "researcher"


def writer_node(state: ResearchState) -> ResearchState:
    """Writer agent that creates the final report."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    response = llm.invoke(
        f"Write a final report based on:\n"
        f"Research: {state['research_notes']}\n"
        f"Analysis: {state['analysis']}"
    )
    
    return {"final_report": response.content}


def create_buggy_workflow():
    """Create the research workflow with infinite loop bug."""
    workflow = StateGraph(ResearchState)
    
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node)
    
    workflow.set_entry_point("researcher")
    
    workflow.add_edge("researcher", "analyst")
    workflow.add_conditional_edges(
        "analyst",
        should_continue,
        {
            "researcher": "researcher",
            "writer": "writer",
        }
    )
    workflow.add_edge("writer", END)
    
    return workflow.compile()


if __name__ == "__main__":
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.langchain import LangchainInstrumentor
    
    provider = TracerProvider()
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:8000/api/v1/traces/ingest"))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    
    LangchainInstrumentor().instrument()
    
    workflow = create_buggy_workflow()
    
    print("Starting buggy research workflow...")
    print("This will loop infinitely until MAO Testing Platform detects it!")
    
    result = workflow.invoke({
        "query": "What are the benefits of multi-agent systems?",
        "research_notes": [],
        "analysis": "",
        "final_report": "",
        "iteration_count": 0,
    })
