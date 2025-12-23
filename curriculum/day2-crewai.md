# Day 2: CrewAI

**Key difference from LangGraph:** CrewAI = **Role-Playing Agents** vs LangGraph = **State Machines**

---

## The Mental Model

```
LANGGRAPH                          CREWAI
──────────────────────────────────────────────────────
State flows through               Agents CONVERSE
a graph                           like a team meeting

┌───┐ → ┌───┐ → ┌───┐            🧑‍🔬 "I found this data"
│ A │   │ B │   │ C │                    ↓
└───┘   └───┘   └───┘            🧑‍💻 "I'll write the code"
                                         ↓
Explicit edges                   🧑‍🎨 "I'll make it pretty"
Typed state                      
Checkpoints                      Implicit flow
                                 Role-based delegation
                                 Memory & backstory
```

---

## Core Concepts

```python
# AGENT = A persona with a role, goal, and backstory
Agent(
    role="Senior Research Analyst",           # Job title
    goal="Find accurate, cutting-edge data",  # What they optimize for
    backstory="20 years at McKinsey...",      # Personality/expertise
    tools=[SearchTool, ScrapeTool],           # What they can do
    allow_delegation=True                     # Can ask others for help
)

# TASK = A specific job to complete
Task(
    description="Research AI testing market",
    expected_output="Report with sources",
    agent=researcher,                         # Who does it
    context=[previous_task]                   # Dependencies
)

# CREW = The team that executes
Crew(
    agents=[researcher, writer, editor],
    tasks=[research_task, write_task, edit_task],
    process=Process.sequential                # or hierarchical
)
```

---

## CrewAI Failure Modes

### 1. Circular Delegation

```
┌────────┐  "You do it"  ┌────────┐
│Agent A │ ────────────► │Agent B │
└────────┘ ◄──────────── └────────┘
             "No, you"
```

**MAST:** F11 Coordination Failure

### 2. Conflicting Goals

```
Writer: "Make it longer!"
Editor: "Make it shorter!"
Result: Infinite revision loop
```

**MAST:** F5 Flawed Workflow Design

### 3. Role Confusion (Backstory Bleed)

```
Researcher backstory: "Former journalist"
Behavior: Starts WRITING articles instead of research
```

**MAST:** F9 Role Usurpation

### 4. Context Dependency Failure

```
Task B needs Task A output
Task A fails silently
Task B hallucinates based on nothing
```

**MAST:** F7 Context Neglect

---

## CrewAI vs LangGraph

| Aspect | LangGraph | CrewAI |
|--------|-----------|--------|
| **Control** | Explicit (you define every edge) | Implicit (agents figure it out) |
| **Debugging** | Inspect state at checkpoints | Read conversation logs |
| **Best for** | Deterministic workflows | Creative/exploratory tasks |
| **Failure risk** | State corruption | Role confusion, loops |

---

## Crews vs Flows (New in CrewAI)

```
CREWS (Original)                 FLOWS (New - More Controllable)
─────────────────────────────────────────────────────────────────
Agents coordinate               Deterministic orchestration
autonomously                    layer on top

crew.kickoff()                  @flow
     │                          def my_flow():
     ▼                              research = research_crew()
  [magic happens]                   if research.quality > 0.8:
     │                                  return write_crew(research)
     ▼                              else:
  result                                return retry_research()

Less control                    More control
More emergent                   More predictable
Harder to test                  Easier to test
```

---

## Key Vocabulary

| Term | Definition | Use in Conversation |
|------|------------|---------------------|
| **Crew** | Group of agents working together | "How many agents in your largest crew?" |
| **Kickoff** | Starting crew execution | "What happens when kickoff fails mid-task?" |
| **Delegation** | Agent asking another for help | "Have you seen circular delegation loops?" |
| **Backstory** | Agent personality/history | "Do your backstories ever conflict with goals?" |
| **Process** | Sequential vs hierarchical | "Which process type has more failures?" |

---

## Reading

1. **CrewAI Core Concepts** (30 min)
   - https://docs.crewai.com/core-concepts/agents/
   - https://docs.crewai.com/core-concepts/crews/

2. **Crews vs Flows** (15 min)
   - https://docs.crewai.com/core-concepts/flows/
