# Weeks 6-7: MAST Taxonomy & Failure Science - Complete Outline

**Duration:** 10 days (40-60 hours total)
**Prerequisites:** Weeks 1-5 (All frameworks)
**Outcome:** World-class expertise in multi-agent failure modes, ability to build detectors

---

## Why This Section Matters Most

```
┌─────────────────────────────────────────────────────────────────┐
│                  YOUR COMPETITIVE MOAT                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LangSmith team: Knows LangChain deeply                         │
│  Arize team: Knows ML monitoring deeply                         │
│  You: Know FAILURE MODES deeply                                  │
│                                                                  │
│  This is the knowledge that lets you:                           │
│  • Speak authoritatively to prospects                           │
│  • Design detection algorithms                                   │
│  • Build defensible IP                                          │
│  • Publish thought leadership                                    │
│                                                                  │
│  INVEST THE MOST TIME HERE                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Day-by-Day Breakdown

### Day 26: MAST Paper Deep Read
- Full paper read (https://arxiv.org/abs/2503.13657)
- Note-taking methodology
- Understanding the taxonomy structure
- Research methodology critique
- Limitations and open questions
- **Deliverable:** 5-page annotated summary

### Day 27: Category 1 - System Design Failures (F1-F5)
- F1: Specification Mismatch
  - Detection algorithm: Intent embedding comparison
  - Implementation in Python
  - False positive/negative analysis
- F2: Poor Task Decomposition
  - Detection algorithm: Task complexity scoring
  - Subtask dependency analysis
- F3: Resource Misallocation
  - Detection algorithm: Cost/complexity ratio
  - Agent capability matching
- F4: Inadequate Tool Provision
  - Detection algorithm: Tool coverage analysis
  - Missing tool prediction
- F5: Flawed Workflow Design
  - Detection algorithm: Graph analysis for anti-patterns
  - Workflow validation rules
- **Deliverable:** 5 detector implementations

### Day 28: Category 2a - Communication Failures (F6-F8)
- F6: Task Derailment (7.4% of failures)
  - Detection algorithm: Semantic similarity to goal
  - Implementation with embeddings
  - Threshold calibration
  - Real-time detection
- F7: Context Neglect
  - Detection algorithm: Mutual information analysis
  - Upstream data presence checking
  - Attention pattern analysis
- F8: Information Withholding (0.85%)
  - Detection algorithm: Information bottleneck detection
  - Agent output completeness scoring
  - Rare but critical cases
- **Deliverable:** 3 detector implementations with tests

### Day 29: Category 2b - Coordination Failures (F9-F11)
- F9: Role Usurpation
  - Detection algorithm: Output type classification
  - Role boundary enforcement
  - Persona embedding comparison
- F10: Communication Breakdown
  - Detection algorithm: Intent preservation checking
  - Message understanding verification
  - Cross-agent alignment scoring
- F11: Coordination Failure
  - Detection algorithm: Timing analysis
  - Dependency graph validation
  - Sequencing verification
- **Deliverable:** 3 detector implementations

### Day 30: Category 3 - Verification Failures (F12-F14)
- F12: Output Validation Failure
  - Detection algorithm: Schema validation
  - Format checking pipelines
  - Type coercion detection
- F13: Quality Gate Bypass
  - Detection algorithm: Checkpoint execution tracking
  - Workflow completeness verification
- F14: Completion Misjudgment
  - Detection algorithm: Objective criteria evaluation
  - Task completion scoring
  - Partial completion detection
- **Deliverable:** 3 detector implementations

### Day 31: Academic Literature Review
- Related papers:
  1. "Cognitive Architectures for Language Agents" (CoALA)
  2. "AgentBench: Evaluating LLMs as Agents"
  3. "GAIA: A Benchmark for General AI Assistants"
  4. "ReAct: Synergizing Reasoning and Acting"
  5. "ToolBench: Benchmarking Tool Use"
- Comparison to MAST
- Gaps in current research
- Future research directions
- **Deliverable:** Literature review document

### Day 32: Building a Failure Detection Library
- Library architecture design
- Common interfaces
- Plugin system for new detectors
- Configuration management
- Integration with frameworks
- Testing framework for detectors
- **Deliverable:** Library scaffold with 3 working detectors

### Day 33: Automated Root Cause Analysis
- Multi-detector correlation
- Causal chain inference
- Confidence scoring
- Evidence collection
- Report generation
- Integration with alerting
- **Deliverable:** Root cause analyzer prototype

### Day 34: Real-World Case Studies
- Case study 1: Your project-sunrise failures
- Case study 2: Your lorekeeper failures  
- Case study 3: Public incident reports
- Case study 4: Academic benchmarks
- Pattern extraction
- Detection validation
- **Deliverable:** 4 classified case studies

### Day 35: Detection System Integration
- Integration with LangGraph
- Integration with CrewAI
- Integration with AutoGen
- Real-time vs batch detection
- Performance optimization
- Production deployment
- **Deliverable:** Integrated detection system

---

## Detailed: F6 Task Derailment Detection

```python
"""
F6: Task Derailment Detection
=============================

When an agent goes off-topic, working on something other than
its assigned task. One of the most common failures (7.4%).

Detection Approaches:
1. Semantic similarity between task and output
2. Topic modeling comparison
3. Keyword extraction and matching
4. Entailment checking

Implementation below uses embedding-based semantic similarity
with calibrated thresholds.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class DerailmentSeverity(Enum):
    NONE = "none"           # On track
    MINOR = "minor"         # Slight tangent, recoverable
    MODERATE = "moderate"   # Off topic but related
    SEVERE = "severe"       # Completely unrelated
    
@dataclass
class DerailmentResult:
    is_derailed: bool
    severity: DerailmentSeverity
    similarity_score: float
    confidence: float
    evidence: Dict
    recommendation: str

class TaskDerailmentDetector:
    """
    Detect when an agent's output doesn't align with its assigned task.
    
    Uses embedding similarity with adaptive thresholds based on
    task complexity and agent role.
    """
    
    # Thresholds calibrated on MAST benchmark
    THRESHOLDS = {
        "default": {"severe": 0.3, "moderate": 0.5, "minor": 0.7},
        "research": {"severe": 0.25, "moderate": 0.45, "minor": 0.65},  # More tolerance
        "coding": {"severe": 0.35, "moderate": 0.55, "minor": 0.75},    # Less tolerance
    }
    
    def __init__(self, embedding_model: str = "text-embedding-3-small"):
        self.embedding_model = embedding_model
        # In production, use actual embedding model
        # self.embedder = OpenAIEmbeddings(model=embedding_model)
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text. Mock for example."""
        # In production: return self.embedder.embed_query(text)
        # Mock: return random unit vector
        vec = np.random.randn(1536)
        return vec / np.linalg.norm(vec)
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    def _extract_key_concepts(self, text: str) -> List[str]:
        """Extract key concepts from text for additional validation."""
        # In production: use NER, keyword extraction, or LLM
        # Mock: simple word extraction
        words = text.lower().split()
        return [w for w in words if len(w) > 5][:10]
    
    def _calculate_concept_overlap(
        self, 
        task_concepts: List[str], 
        output_concepts: List[str]
    ) -> float:
        """Calculate overlap between task and output concepts."""
        if not task_concepts or not output_concepts:
            return 0.5  # Neutral if can't extract
        
        task_set = set(task_concepts)
        output_set = set(output_concepts)
        
        intersection = len(task_set & output_set)
        union = len(task_set | output_set)
        
        return intersection / union if union > 0 else 0.0
    
    def detect(
        self,
        task_description: str,
        agent_output: str,
        agent_role: str = "default",
        context: Optional[Dict] = None
    ) -> DerailmentResult:
        """
        Detect if agent output has derailed from the task.
        
        Args:
            task_description: The original task given to the agent
            agent_output: What the agent produced
            agent_role: Type of agent (affects thresholds)
            context: Additional context (previous outputs, etc.)
        
        Returns:
            DerailmentResult with detection details
        """
        # Get embeddings
        task_embedding = self._get_embedding(task_description)
        output_embedding = self._get_embedding(agent_output)
        
        # Calculate semantic similarity
        similarity = self._cosine_similarity(task_embedding, output_embedding)
        
        # Extract and compare concepts
        task_concepts = self._extract_key_concepts(task_description)
        output_concepts = self._extract_key_concepts(agent_output)
        concept_overlap = self._calculate_concept_overlap(task_concepts, output_concepts)
        
        # Combined score (weighted)
        combined_score = 0.7 * similarity + 0.3 * concept_overlap
        
        # Get thresholds for this agent role
        thresholds = self.THRESHOLDS.get(agent_role, self.THRESHOLDS["default"])
        
        # Determine severity
        if combined_score < thresholds["severe"]:
            severity = DerailmentSeverity.SEVERE
            is_derailed = True
            recommendation = "Terminate and restart with clarified task"
        elif combined_score < thresholds["moderate"]:
            severity = DerailmentSeverity.MODERATE
            is_derailed = True
            recommendation = "Redirect agent with explicit correction"
        elif combined_score < thresholds["minor"]:
            severity = DerailmentSeverity.MINOR
            is_derailed = True
            recommendation = "Monitor closely, may self-correct"
        else:
            severity = DerailmentSeverity.NONE
            is_derailed = False
            recommendation = "On track, continue"
        
        # Calculate confidence based on score clarity
        # High confidence when clearly above or below thresholds
        distance_from_moderate = abs(combined_score - thresholds["moderate"])
        confidence = min(1.0, distance_from_moderate * 2 + 0.5)
        
        return DerailmentResult(
            is_derailed=is_derailed,
            severity=severity,
            similarity_score=combined_score,
            confidence=confidence,
            evidence={
                "semantic_similarity": similarity,
                "concept_overlap": concept_overlap,
                "task_concepts": task_concepts,
                "output_concepts": output_concepts,
                "thresholds_used": thresholds,
            },
            recommendation=recommendation
        )
    
    def detect_in_conversation(
        self,
        task_description: str,
        conversation: List[Dict[str, str]],
        agent_role: str = "default"
    ) -> List[Tuple[int, DerailmentResult]]:
        """
        Detect derailment across a conversation.
        Returns list of (turn_index, result) for derailed turns.
        """
        results = []
        
        for i, turn in enumerate(conversation):
            if turn.get("role") == "assistant":
                result = self.detect(
                    task_description=task_description,
                    agent_output=turn.get("content", ""),
                    agent_role=agent_role
                )
                if result.is_derailed:
                    results.append((i, result))
        
        return results


# Usage example
if __name__ == "__main__":
    detector = TaskDerailmentDetector()
    
    # Test case 1: On track
    result = detector.detect(
        task_description="Research the latest developments in quantum computing",
        agent_output="I found several recent papers on quantum error correction and quantum advantage demonstrations by Google and IBM.",
        agent_role="research"
    )
    print(f"Test 1 - Expected: not derailed, Got: {result.severity}")
    
    # Test case 2: Severely derailed
    result = detector.detect(
        task_description="Research the latest developments in quantum computing",
        agent_output="Here's a recipe for chocolate chip cookies: First, preheat your oven to 375°F...",
        agent_role="research"
    )
    print(f"Test 2 - Expected: severe derailment, Got: {result.severity}")
    
    # Test case 3: Minor derailment
    result = detector.detect(
        task_description="Research the latest developments in quantum computing",
        agent_output="Quantum computing is interesting. By the way, classical computing also had major advances this year with new chip designs.",
        agent_role="research"
    )
    print(f"Test 3 - Expected: minor derailment, Got: {result.severity}")
```

---

## Detailed: F11 Coordination Failure Detection

```python
"""
F11: Coordination Failure Detection
====================================

When agents fail to coordinate properly - timing issues, sequencing
errors, or dependency violations.

Detection Approaches:
1. Dependency graph validation
2. Timing analysis
3. State sequence verification
4. Resource contention detection

"""

from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import time
from collections import defaultdict

class CoordinationFailureType(Enum):
    DEPENDENCY_VIOLATION = "dependency_violation"  # Used before ready
    TIMING_VIOLATION = "timing_violation"          # Too fast/slow
    SEQUENCE_VIOLATION = "sequence_violation"      # Wrong order
    RESOURCE_CONTENTION = "resource_contention"    # Conflict
    MISSING_HANDOFF = "missing_handoff"            # No handoff
    DUPLICATE_WORK = "duplicate_work"              # Same work twice

@dataclass
class CoordinationEvent:
    timestamp: float
    agent_id: str
    action: str
    dependencies: List[str]
    resources: List[str]
    state_snapshot: Dict

@dataclass
class CoordinationFailure:
    failure_type: CoordinationFailureType
    agents_involved: List[str]
    description: str
    evidence: Dict
    severity: str  # "critical", "warning", "info"
    recommendation: str

class CoordinationFailureDetector:
    """
    Detect coordination failures in multi-agent systems.
    
    Monitors agent interactions and detects:
    - Dependency violations
    - Timing anomalies
    - Sequence errors
    - Resource conflicts
    """
    
    def __init__(self):
        self.events: List[CoordinationEvent] = []
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.completed_actions: Set[str] = set()
        self.resource_locks: Dict[str, str] = {}  # resource -> agent
        self.expected_sequence: Optional[List[str]] = None
    
    def set_dependencies(self, dependencies: Dict[str, List[str]]):
        """
        Set expected dependencies between actions.
        
        Args:
            dependencies: {action: [required_prior_actions]}
        """
        for action, deps in dependencies.items():
            self.dependency_graph[action] = set(deps)
    
    def set_expected_sequence(self, sequence: List[str]):
        """Set expected action sequence for sequence violation detection."""
        self.expected_sequence = sequence
    
    def record_event(self, event: CoordinationEvent) -> List[CoordinationFailure]:
        """
        Record an event and check for coordination failures.
        
        Returns list of any failures detected.
        """
        failures = []
        
        # Check dependency violations
        dep_failure = self._check_dependencies(event)
        if dep_failure:
            failures.append(dep_failure)
        
        # Check timing violations
        timing_failure = self._check_timing(event)
        if timing_failure:
            failures.append(timing_failure)
        
        # Check sequence violations
        seq_failure = self._check_sequence(event)
        if seq_failure:
            failures.append(seq_failure)
        
        # Check resource contention
        resource_failure = self._check_resources(event)
        if resource_failure:
            failures.append(resource_failure)
        
        # Record event
        self.events.append(event)
        self.completed_actions.add(event.action)
        
        # Update resource locks
        for resource in event.resources:
            self.resource_locks[resource] = event.agent_id
        
        return failures
    
    def _check_dependencies(self, event: CoordinationEvent) -> Optional[CoordinationFailure]:
        """Check if all dependencies are satisfied."""
        required = self.dependency_graph.get(event.action, set())
        missing = required - self.completed_actions
        
        if missing:
            return CoordinationFailure(
                failure_type=CoordinationFailureType.DEPENDENCY_VIOLATION,
                agents_involved=[event.agent_id],
                description=f"Action '{event.action}' started before dependencies completed: {missing}",
                evidence={
                    "action": event.action,
                    "required": list(required),
                    "completed": list(self.completed_actions),
                    "missing": list(missing)
                },
                severity="critical",
                recommendation=f"Ensure {missing} complete before starting {event.action}"
            )
        return None
    
    def _check_timing(self, event: CoordinationEvent) -> Optional[CoordinationFailure]:
        """Check for timing anomalies."""
        if not self.events:
            return None
        
        # Check time since last event from same agent
        same_agent_events = [e for e in self.events if e.agent_id == event.agent_id]
        
        if same_agent_events:
            last_event = same_agent_events[-1]
            time_diff = event.timestamp - last_event.timestamp
            
            # Too fast (< 0.1s between actions might indicate loop)
            if time_diff < 0.1:
                return CoordinationFailure(
                    failure_type=CoordinationFailureType.TIMING_VIOLATION,
                    agents_involved=[event.agent_id],
                    description=f"Agent '{event.agent_id}' acting too fast ({time_diff:.3f}s between actions)",
                    evidence={
                        "time_diff": time_diff,
                        "last_action": last_event.action,
                        "current_action": event.action
                    },
                    severity="warning",
                    recommendation="Check for infinite loop or missing await"
                )
        
        return None
    
    def _check_sequence(self, event: CoordinationEvent) -> Optional[CoordinationFailure]:
        """Check if actions follow expected sequence."""
        if not self.expected_sequence:
            return None
        
        # Find expected position
        if event.action not in self.expected_sequence:
            return None  # Unknown action, can't check
        
        expected_pos = self.expected_sequence.index(event.action)
        actual_pos = len([e for e in self.events if e.action in self.expected_sequence])
        
        if actual_pos != expected_pos:
            expected_action = self.expected_sequence[actual_pos] if actual_pos < len(self.expected_sequence) else "END"
            return CoordinationFailure(
                failure_type=CoordinationFailureType.SEQUENCE_VIOLATION,
                agents_involved=[event.agent_id],
                description=f"Expected '{expected_action}' but got '{event.action}'",
                evidence={
                    "expected_sequence": self.expected_sequence,
                    "expected_position": actual_pos,
                    "actual_action": event.action,
                    "expected_action": expected_action
                },
                severity="warning",
                recommendation="Review workflow logic"
            )
        
        return None
    
    def _check_resources(self, event: CoordinationEvent) -> Optional[CoordinationFailure]:
        """Check for resource contention."""
        for resource in event.resources:
            if resource in self.resource_locks:
                holding_agent = self.resource_locks[resource]
                if holding_agent != event.agent_id:
                    return CoordinationFailure(
                        failure_type=CoordinationFailureType.RESOURCE_CONTENTION,
                        agents_involved=[event.agent_id, holding_agent],
                        description=f"Resource '{resource}' contention between {event.agent_id} and {holding_agent}",
                        evidence={
                            "resource": resource,
                            "requesting_agent": event.agent_id,
                            "holding_agent": holding_agent
                        },
                        severity="critical",
                        recommendation="Implement resource locking or queue"
                    )
        return None
    
    def analyze_session(self) -> Dict:
        """
        Analyze all recorded events for patterns.
        
        Returns summary statistics and detected patterns.
        """
        if not self.events:
            return {"status": "no_events"}
        
        # Agent activity
        agent_actions = defaultdict(list)
        for event in self.events:
            agent_actions[event.agent_id].append(event.action)
        
        # Detect duplicate work
        all_actions = [e.action for e in self.events]
        duplicates = [a for a in set(all_actions) if all_actions.count(a) > 1]
        
        # Timing analysis
        if len(self.events) > 1:
            time_diffs = [
                self.events[i+1].timestamp - self.events[i].timestamp
                for i in range(len(self.events) - 1)
            ]
            avg_time = sum(time_diffs) / len(time_diffs)
        else:
            avg_time = 0
        
        return {
            "total_events": len(self.events),
            "agents": list(agent_actions.keys()),
            "agent_action_counts": {a: len(actions) for a, actions in agent_actions.items()},
            "duplicate_actions": duplicates,
            "average_time_between_events": avg_time,
            "total_duration": self.events[-1].timestamp - self.events[0].timestamp if self.events else 0
        }


# Usage example
if __name__ == "__main__":
    detector = CoordinationFailureDetector()
    
    # Set up dependencies: write depends on research, review depends on write
    detector.set_dependencies({
        "write": ["research"],
        "review": ["write"],
        "publish": ["review"]
    })
    
    detector.set_expected_sequence(["research", "write", "review", "publish"])
    
    # Simulate events
    base_time = time.time()
    
    # Good event
    failures = detector.record_event(CoordinationEvent(
        timestamp=base_time,
        agent_id="researcher",
        action="research",
        dependencies=[],
        resources=["search_api"],
        state_snapshot={}
    ))
    print(f"After research: {len(failures)} failures")
    
    # Dependency violation - write before research complete... 
    # (research is complete now, so this should be fine)
    failures = detector.record_event(CoordinationEvent(
        timestamp=base_time + 1,
        agent_id="writer",
        action="write",
        dependencies=["research"],
        resources=["document"],
        state_snapshot={}
    ))
    print(f"After write: {len(failures)} failures")
    
    # Sequence violation - publish before review
    failures = detector.record_event(CoordinationEvent(
        timestamp=base_time + 2,
        agent_id="publisher",
        action="publish",
        dependencies=["review"],
        resources=["website"],
        state_snapshot={}
    ))
    print(f"After premature publish: {len(failures)} failures")
    for f in failures:
        print(f"  - {f.failure_type.value}: {f.description}")
    
    # Session analysis
    analysis = detector.analyze_session()
    print(f"\nSession analysis: {analysis}")
```

---

## Projects

### Project 1: MAST Detector Library
Complete library with:
- All 14 detectors implemented
- Common interfaces
- Configuration system
- Testing framework
- Documentation

### Project 2: Root Cause Analyzer
System that:
- Combines multiple detectors
- Correlates failures
- Generates human-readable reports
- Suggests fixes

### Project 3: Framework Integration
Integration with:
- LangGraph (via callbacks)
- CrewAI (via callbacks)
- AutoGen (via middleware)
- Real-time detection

---

## Assessment

By end of weeks 6-7, you should be able to:

- [ ] Name all 14 MAST failure modes without reference
- [ ] Explain detection algorithm for each
- [ ] Implement detector from scratch in < 1 hour
- [ ] Classify real failures using taxonomy
- [ ] Discuss limitations and false positive rates
- [ ] Compare MAST to other taxonomies
- [ ] Identify gaps for future research
