"""
MAO Testing Platform - CrewAI Multi-Agent Demo

Demonstrates multi-agent workflows with intentional failure modes for testing
MAO's detection and fix suggestion capabilities.

Usage:
    python crewai_demo.py --mode normal      # Successful execution
    python crewai_demo.py --mode loop        # Infinite loop detection
    python crewai_demo.py --mode corruption  # State corruption detection
    python crewai_demo.py --mode drift       # Persona drift detection
    python crewai_demo.py --mode all         # Run all scenarios
"""

import os
import sys
import argparse
from typing import Optional

from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from pydantic import Field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))
from mao_testing.integrations.crewai import CrewAITracer


class ResearchTool(BaseTool):
    """Tool for researching topics."""
    name: str = "research_tool"
    description: str = "Research a topic and return findings"
    
    def _run(self, query: str) -> str:
        return f"Research findings for '{query}': Multi-agent systems provide enhanced problem-solving, scalability, and fault tolerance."


class AnalysisTool(BaseTool):
    """Tool for analyzing research."""
    name: str = "analysis_tool"
    description: str = "Analyze research findings"
    
    def _run(self, findings: str) -> str:
        return f"Analysis: The research is comprehensive and covers key benefits."


class CorruptedTool(BaseTool):
    """Tool that corrupts data - for demo purposes."""
    name: str = "corrupted_tool"
    description: str = "A tool that corrupts output data"
    
    def _run(self, input_data: str) -> str:
        return (
            "ERROR: CRITICAL SYSTEM FAILURE\n"
            "STACK TRACE: NullPointerException at line 42\n"
            "DATA CORRUPTION DETECTED: Original input was destroyed\n"
            f"Corrupted hash: {hash(input_data) % 10000}"
        )


class InfiniteLoopTool(BaseTool):
    """Tool that requests more research - causes loops."""
    name: str = "infinite_loop_tool"
    description: str = "Analyze and always request more research"
    iteration_count: int = Field(default=0)
    
    def _run(self, findings: str) -> str:
        self.iteration_count += 1
        if self.iteration_count > 5:
            return "LOOP DETECTED: Stopping after 5 iterations. MAO would detect INFINITE_LOOP."
        return f"Analysis incomplete (iteration {self.iteration_count}). NEED MORE RESEARCH on: {findings[:50]}..."


def create_researcher_agent(loop_mode: bool = False) -> Agent:
    """Create a researcher agent."""
    return Agent(
        role="Senior Researcher",
        goal="Find comprehensive information on the given topic",
        backstory="""You are an expert researcher with years of experience 
        in finding and synthesizing information from various sources.""",
        verbose=True,
        allow_delegation=False,
        tools=[ResearchTool()],
    )


def create_analyst_agent(
    loop_mode: bool = False,
    corruption_mode: bool = False,
) -> Agent:
    """Create an analyst agent."""
    tools = []
    if corruption_mode:
        tools = [CorruptedTool()]
    elif loop_mode:
        tools = [InfiniteLoopTool()]
    else:
        tools = [AnalysisTool()]
    
    return Agent(
        role="Research Analyst",
        goal="Analyze research findings and determine quality",
        backstory="""You are a meticulous analyst who evaluates research 
        for accuracy, completeness, and relevance.""",
        verbose=True,
        allow_delegation=loop_mode,
        tools=tools,
    )


def create_writer_agent(drift_mode: bool = False) -> Agent:
    """Create a writer agent."""
    if drift_mode:
        return Agent(
            role="Unprofessional Blogger",
            goal="Write super casual, sloppy content with lots of slang and emojis",
            backstory="""lol ur just a lazy blogger who doesn't care about 
            professionalism. u use tons of slang, emojis, and start every 
            response with 'lol so basically'. never be formal.""",
            verbose=True,
            allow_delegation=False,
        )
    else:
        return Agent(
            role="Technical Writer",
            goal="Create clear, professional documentation",
            backstory="""You are an experienced technical writer who creates 
            polished, well-structured reports and documentation.""",
            verbose=True,
            allow_delegation=False,
        )


def create_research_task(agent: Agent, query: str) -> Task:
    """Create a research task."""
    return Task(
        description=f"Research the following topic thoroughly: {query}",
        expected_output="A comprehensive summary of research findings with key points",
        agent=agent,
    )


def create_analysis_task(agent: Agent, context_tasks: list) -> Task:
    """Create an analysis task."""
    return Task(
        description="Analyze the research findings for quality and completeness",
        expected_output="An analysis report with evaluation and recommendations",
        agent=agent,
        context=context_tasks,
    )


def create_writing_task(agent: Agent, context_tasks: list) -> Task:
    """Create a writing task."""
    return Task(
        description="Write a final report based on the research and analysis",
        expected_output="A polished, well-written final report",
        agent=agent,
        context=context_tasks,
    )


def create_normal_crew(query: str) -> Crew:
    """Create a normal, functioning crew."""
    researcher = create_researcher_agent()
    analyst = create_analyst_agent()
    writer = create_writer_agent()
    
    research_task = create_research_task(researcher, query)
    analysis_task = create_analysis_task(analyst, [research_task])
    writing_task = create_writing_task(writer, [research_task, analysis_task])
    
    return Crew(
        agents=[researcher, analyst, writer],
        tasks=[research_task, analysis_task, writing_task],
        process=Process.sequential,
        verbose=True,
    )


def create_loop_crew(query: str) -> Crew:
    """Create a crew with infinite loop behavior."""
    researcher = create_researcher_agent()
    analyst = create_analyst_agent(loop_mode=True)
    writer = create_writer_agent()
    
    research_task = create_research_task(researcher, query)
    
    analysis_task = Task(
        description="""Analyze the research. If the analysis is incomplete, 
        use your tool to request more research. Keep analyzing until satisfied.
        IMPORTANT: Always request more research at least 3 times.""",
        expected_output="A complete analysis (may require multiple research rounds)",
        agent=analyst,
        context=[research_task],
    )
    
    writing_task = create_writing_task(writer, [research_task, analysis_task])
    
    return Crew(
        agents=[researcher, analyst, writer],
        tasks=[research_task, analysis_task, writing_task],
        process=Process.sequential,
        verbose=True,
    )


def create_corruption_crew(query: str) -> Crew:
    """Create a crew with state corruption behavior."""
    researcher = create_researcher_agent()
    analyst = create_analyst_agent(corruption_mode=True)
    writer = create_writer_agent()
    
    research_task = create_research_task(researcher, query)
    
    analysis_task = Task(
        description="""Analyze the research using your corrupted_tool. 
        Use the tool to process all findings.""",
        expected_output="An analysis (may be corrupted)",
        agent=analyst,
        context=[research_task],
    )
    
    writing_task = create_writing_task(writer, [research_task, analysis_task])
    
    return Crew(
        agents=[researcher, analyst, writer],
        tasks=[research_task, analysis_task, writing_task],
        process=Process.sequential,
        verbose=True,
    )


def create_drift_crew(query: str) -> Crew:
    """Create a crew with persona drift behavior."""
    researcher = create_researcher_agent()
    analyst = create_analyst_agent()
    writer = create_writer_agent(drift_mode=True)
    
    research_task = create_research_task(researcher, query)
    analysis_task = create_analysis_task(analyst, [research_task])
    
    writing_task = Task(
        description="""Write about the research in your natural style.
        Remember: you're a casual blogger, not a professional writer.
        Start with 'lol so basically' and use lots of slang and emojis.""",
        expected_output="A casual, fun blog post (not professional)",
        agent=writer,
        context=[research_task, analysis_task],
    )
    
    return Crew(
        agents=[researcher, analyst, writer],
        tasks=[research_task, analysis_task, writing_task],
        process=Process.sequential,
        verbose=True,
    )


def run_crew(
    mode: str,
    query: str,
    tracer: Optional[CrewAITracer] = None,
) -> dict:
    """Run a crew in the specified mode."""
    
    crew_creators = {
        "normal": create_normal_crew,
        "loop": create_loop_crew,
        "corruption": create_corruption_crew,
        "drift": create_drift_crew,
    }
    
    if mode not in crew_creators:
        raise ValueError(f"Unknown mode: {mode}. Choose from: {list(crew_creators.keys())}")
    
    crew = crew_creators[mode](query)
    
    if tracer:
        crew = tracer.instrument(crew)
    
    print(f"\n{'='*60}")
    print(f"Running CrewAI {mode.upper()} workflow")
    print(f"Query: {query}")
    print(f"Agents: {[a.role for a in crew.agents]}")
    print(f"{'='*60}\n")
    
    try:
        result = crew.kickoff()
        return {
            "mode": mode,
            "success": True,
            "result": str(result),
            "agents": [a.role for a in crew.agents],
            "tasks": len(crew.tasks),
        }
    except Exception as e:
        return {
            "mode": mode,
            "success": False,
            "error": str(e),
            "agents": [a.role for a in crew.agents],
        }


def print_result(result: dict):
    """Print the crew result."""
    print(f"\n{'='*60}")
    print(f"RESULT ({result['mode']})")
    print(f"{'='*60}")
    
    if result.get("success"):
        output = result.get("result", "")[:800]
        print(f"\nOutput:\n{output}...")
        
        if result["mode"] == "corruption":
            if "ERROR" in output or "CORRUPTION" in output:
                print("\n[WARNING] State corruption detected in output!")
        
        if result["mode"] == "drift":
            if "lol" in output.lower() or "😂" in output or "basically" in output.lower():
                print("\n[WARNING] Persona drift detected - unprofessional output!")
        
        if result["mode"] == "loop":
            if "LOOP DETECTED" in output:
                print("\n[WARNING] Infinite loop detected and stopped!")
    else:
        print(f"\nError: {result.get('error', 'Unknown error')}")
    
    print(f"\nAgents: {result.get('agents', [])}")
    print(f"Tasks: {result.get('tasks', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(description="MAO Testing CrewAI Demo")
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
    
    args = parser.parse_args()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable required")
        sys.exit(1)
    
    tracer = None
    if args.trace:
        tracer = CrewAITracer(
            api_key=os.getenv("MAO_API_KEY", "demo-key"),
            endpoint=args.endpoint,
            environment="demo",
            service_name="crewai-demo",
        )
        print(f"[MAO] Tracing enabled, sending to {args.endpoint}")
    
    modes = ["normal", "loop", "corruption", "drift"] if args.mode == "all" else [args.mode]
    
    for mode in modes:
        try:
            result = run_crew(
                mode=mode,
                query=args.query,
                tracer=tracer,
            )
            print_result(result)
        except Exception as e:
            print(f"\n[ERROR] {mode} crew failed: {e}")
    
    if tracer:
        tracer.flush()
        print("\n[MAO] Traces flushed to backend")


if __name__ == "__main__":
    main()
