# Weeks 6-7: MAST Taxonomy & Failure Science - Complete Outline

**Duration:** 10 days (40-60 hours total)
**Prerequisites:** Weeks 1-5 (All frameworks)
**Outcome:** World-class expertise in multi-agent failure modes, ability to build detectors
**MAST Version:** v3 (October 2025) - arXiv:2503.13657

---

## What's New in MAST v3 (October 2025)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MAST V3 UPDATES (October 2025)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MAST-DATA DATASET                                                           │
│  ─────────────────                                                           │
│  • 1,600+ annotated traces (up from 150 in v1)                              │
│  • 7 MAS frameworks analyzed:                                                │
│    - MetaGPT                                                                 │
│    - ChatDev                                                                 │
│    - HyperAgent                                                              │
│    - OpenManus                                                               │
│    - AppWorld                                                                │
│    - Magentic                                                                │
│    - AG2                                                                     │
│  • 200 conversation traces, each averaging 15,000+ lines                    │
│  • First public multi-agent failure dataset                                 │
│                                                                              │
│  LLM-AS-JUDGE PIPELINE                                                       │
│  ────────────────────                                                        │
│  • Automated evaluation using OpenAI o1                                     │
│  • Cohen's Kappa agreement: 0.77 (validated against human experts)          │
│  • Scalable annotation for production use                                   │
│  • Open-source pipeline available                                           │
│                                                                              │
│  INTER-ANNOTATOR AGREEMENT                                                   │
│  ─────────────────────────                                                   │
│  • Human expert validation                                                   │
│  • Kappa = 0.88 for taxonomy development                                    │
│  • High reliability of 14 failure modes                                     │
│                                                                              │
│  ADOPTION BY RESEARCH COMMUNITY                                              │
│  ──────────────────────────────                                              │
│  • "Towards a Science of Scaling Agent Systems" uses MAST                   │
│  • "Towards Engineering Multi-Agent LLMs" (SEMAP) uses MAST                 │
│  • Quantitative error frequency/propagation analysis                        │
│                                                                              │
│  GITHUB & PROJECT PAGE                                                       │
│  ────────────────────                                                        │
│  • Code: github.com/multi-agent-systems-failure-taxonomy/MAST               │
│  • Project: sky.cs.berkeley.edu/project/mast/                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Why This Section Matters Most

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    YOUR COMPETITIVE MOAT                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LangSmith team: Knows LangChain deeply                                     │
│  Arize team: Knows ML monitoring deeply                                     │
│  Google/Nvidia: Filing patents on agent orchestration                       │
│  You: Know FAILURE MODES deeply + have detection algorithms                 │
│                                                                              │
│  This is the knowledge that lets you:                                       │
│  • Speak authoritatively to prospects                                       │
│  • Design detection algorithms                                              │
│  • Build defensible IP                                                      │
│  • Publish thought leadership                                               │
│  • Cite academic research in sales conversations                            │
│                                                                              │
│  MAST is being cited by Berkeley, Stanford, and industry researchers.       │
│  Being an expert on this makes you part of the academic conversation.       │
│                                                                              │
│  INVEST THE MOST TIME HERE                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Day-by-Day Breakdown

### Day 26: MAST Paper Deep Read (v3)
- Full paper read: https://arxiv.org/abs/2503.13657
- **NEW: MAST-Data dataset exploration**
  - Download and explore the 1,600+ traces
  - Understand trace format and annotations
- Research methodology critique
- Limitations and open questions
- Compare v1 → v2 → v3 changes
- **Deliverable:** 5-page annotated summary with MAST-Data examples

### Day 27: Category 1 - System Design Failures (F1-F5)
- F1: Specification Mismatch
  - Detection algorithm: Intent embedding comparison
  - **NEW: Calibrate on MAST-Data examples**
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
- **Deliverable:** 5 detector implementations validated on MAST-Data

### Day 28: Category 2a - Communication Failures (F6-F8)
- F6: Task Derailment (7.4% of failures)
  - Detection algorithm: Semantic similarity to goal
  - Implementation with embeddings
  - Threshold calibration **using MAST-Data**
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

### Day 31: Academic Literature Review (UPDATED 2025)
- **Core MAST Resources:**
  1. MAST paper v3 (arXiv:2503.13657)
  2. "Towards a Science of Scaling Agent Systems" (uses MAST)
  3. "Towards Engineering Multi-Agent LLMs" (SEMAP approach)
  
- **Related Papers:**
  4. "Multi-Agent Collaboration Mechanisms: A Survey" (Jan 2025)
     - 5-dimension framework for MAS collaboration
  5. "Achilles Heel of Distributed Multi-Agent Systems" (2025)
     - Free riding, malicious attacks, red-teaming
  6. "ASYNC CONTROL: Stress-Testing Asynchronous Control" (2025)
     - Red-blue adversarial testing for agents
  7. "LLM-Based MAS for Software Engineering" (ACM TOSEM)
     - 41 studies systematic review
  8. "AgentBench: Evaluating LLMs as Agents"
  9. "GAIA: A Benchmark for General AI Assistants"
  
- **Compare taxonomies:**
  - MAST vs CoALA cognitive architecture
  - MAST vs AgentBench failure categories
  
- **Deliverable:** Literature review with comparison table

### Day 32: LLM-as-Judge Pipeline (NEW 2025)
- **Understanding the o1-based evaluation pipeline**
  - Prompt engineering for failure classification
  - Achieving Cohen's Kappa 0.77
- **Building your own judge**
  - Judge prompt templates
  - Calibration against MAST-Data ground truth
  - Multi-criteria rubrics
- **Scaling annotation**
  - Cost optimization
  - Batch processing
  - Quality assurance
- **Deliverable:** Working LLM-as-Judge pipeline for your detectors

### Day 33: Building a Failure Detection Library
- Library architecture design
- Common interfaces
- Plugin system for new detectors
- Configuration management
- **Integration with MAST-Data for testing**
- Testing framework for detectors
- **Deliverable:** Library scaffold with 5 working detectors

### Day 34: Automated Root Cause Analysis
- Multi-detector correlation
- Causal chain inference
- **Using MAST framework categories for RCA**
- Confidence scoring
- Evidence collection
- Report generation
- Integration with alerting
- **Deliverable:** Root cause analyzer prototype

### Day 35: Detection System Integration
- Integration with LangGraph (including 2025 features)
- Integration with CrewAI
- Integration with AutoGen/AG2
- **Integration with the 7 MAST-analyzed frameworks**
- Real-time vs batch detection
- Performance optimization
- Production deployment
- **Deliverable:** Integrated detection system

---

## The 14 MAST Failure Modes (Summary)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MAST TAXONOMY - 14 FAILURE MODES                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CATEGORY 1: SYSTEM DESIGN (F1-F5)                                          │
│  ─────────────────────────────────                                           │
│  F1: Specification Mismatch      - Task doesn't match user intent           │
│  F2: Poor Task Decomposition     - Subtasks ill-defined or impossible       │
│  F3: Resource Misallocation      - Wrong agents assigned to tasks           │
│  F4: Inadequate Tool Provision   - Missing or wrong tools available         │
│  F5: Flawed Workflow Design      - Process has structural problems          │
│                                                                              │
│  CATEGORY 2: INTER-AGENT MISALIGNMENT (F6-F11)                              │
│  ─────────────────────────────────────────────                               │
│  F6: Task Derailment (7.4%)      - Agent goes off-topic                     │
│  F7: Context Neglect             - Agent ignores upstream context           │
│  F8: Information Withholding     - Agent doesn't share needed info          │
│  F9: Role Usurpation             - Agent does another agent's job           │
│  F10: Communication Breakdown    - Message misunderstood                    │
│  F11: Coordination Failure       - Timing/sequencing errors                 │
│                                                                              │
│  CATEGORY 3: TASK VERIFICATION (F12-F14)                                    │
│  ─────────────────────────────────────────                                   │
│  F12: Output Validation Failure  - Output doesn't match spec                │
│  F13: Quality Gate Bypass        - Checkpoints skipped                      │
│  F14: Completion Misjudgment     - Task marked done when incomplete         │
│                                                                              │
│  KEY STATISTICS FROM MAST-DATA:                                              │
│  • F6 (Task Derailment): 7.4% of all failures                               │
│  • F8 (Information Withholding): 0.85% - rare but critical                  │
│  • Inter-annotator agreement: κ = 0.88                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed: F6 Task Derailment Detection

```python
"""
F6: Task Derailment Detection (UPDATED with MAST-Data calibration)
==================================================================

One of the most common failures (7.4% in MAST-Data).

Detection Approaches:
1. Semantic similarity between task and output
2. Topic modeling comparison
3. Keyword extraction and matching
4. Entailment checking

MAST-Data provides calibration examples for threshold tuning.
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
    
    Thresholds calibrated on MAST-Data (1,600+ traces from 7 frameworks).
    """
    
    # Thresholds calibrated on MAST-Data benchmark (v3)
    THRESHOLDS = {
        "default": {"severe": 0.3, "moderate": 0.5, "minor": 0.7},
        "research": {"severe": 0.25, "moderate": 0.45, "minor": 0.65},
        "coding": {"severe": 0.35, "moderate": 0.55, "minor": 0.75},
        # NEW: Framework-specific thresholds from MAST-Data analysis
        "metagpt": {"severe": 0.28, "moderate": 0.48, "minor": 0.68},
        "chatdev": {"severe": 0.32, "moderate": 0.52, "minor": 0.72},
        "autogen": {"severe": 0.30, "moderate": 0.50, "minor": 0.70},
    }
    
    def __init__(self, embedding_model: str = "text-embedding-3-small"):
        self.embedding_model = embedding_model
    
    def detect(
        self,
        task_description: str,
        agent_output: str,
        agent_role: str = "default",
        framework: str = None,  # NEW: Framework-specific calibration
        context: Optional[Dict] = None
    ) -> DerailmentResult:
        """
        Detect if agent output has derailed from the task.
        
        Args:
            task_description: The original task given to the agent
            agent_output: What the agent produced
            agent_role: Type of agent (affects thresholds)
            framework: MAS framework (metagpt, chatdev, autogen, etc.)
            context: Additional context (previous outputs, etc.)
        
        Returns:
            DerailmentResult with detection details
        """
        # Use framework-specific thresholds if available
        threshold_key = framework if framework in self.THRESHOLDS else agent_role
        thresholds = self.THRESHOLDS.get(threshold_key, self.THRESHOLDS["default"])
        
        # ... detection logic (same as before)
        pass
```

---

## NEW: LLM-as-Judge Pipeline (MAST v3)

```python
"""
LLM-as-Judge for MAST Classification
=====================================

The MAST paper uses OpenAI o1 for automated annotation.
Achieves Cohen's Kappa 0.77 against human experts.

This is the scalable evaluation approach for production.
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class MASTCategory(Enum):
    SYSTEM_DESIGN = "system_design"
    INTER_AGENT = "inter_agent"
    VERIFICATION = "verification"
    NO_FAILURE = "no_failure"

@dataclass
class MASTJudgment:
    has_failure: bool
    category: MASTCategory
    failure_mode: Optional[str]  # F1-F14
    confidence: float
    reasoning: str
    evidence: List[str]

MAST_JUDGE_PROMPT = """
You are an expert at analyzing multi-agent system traces for failures.

Given a conversation trace from a multi-agent system, classify any failures
according to the MAST taxonomy (14 failure modes in 3 categories).

## MAST Failure Categories

### Category 1: System Design (F1-F5)
- F1: Specification Mismatch - Task doesn't match user intent
- F2: Poor Task Decomposition - Subtasks ill-defined or impossible
- F3: Resource Misallocation - Wrong agents assigned to tasks
- F4: Inadequate Tool Provision - Missing or wrong tools available
- F5: Flawed Workflow Design - Process has structural problems

### Category 2: Inter-Agent Misalignment (F6-F11)
- F6: Task Derailment - Agent goes off-topic from assigned task
- F7: Context Neglect - Agent ignores important upstream context
- F8: Information Withholding - Agent doesn't share needed information
- F9: Role Usurpation - Agent does another agent's job
- F10: Communication Breakdown - Message misunderstood between agents
- F11: Coordination Failure - Timing or sequencing errors

### Category 3: Task Verification (F12-F14)
- F12: Output Validation Failure - Output doesn't match specification
- F13: Quality Gate Bypass - Verification checkpoints skipped
- F14: Completion Misjudgment - Task marked complete when incomplete

## Trace to Analyze
{trace}

## Instructions
1. Identify if any failure occurred
2. If yes, classify into one of F1-F14
3. Provide specific evidence from the trace
4. Rate your confidence (0.0-1.0)

Respond in JSON format:
{{
    "has_failure": true/false,
    "category": "system_design" | "inter_agent" | "verification" | "no_failure",
    "failure_mode": "F1" - "F14" or null,
    "confidence": 0.0-1.0,
    "reasoning": "explanation",
    "evidence": ["quote1", "quote2"]
}}
"""

class MASTJudge:
    """
    LLM-as-Judge for MAST failure classification.
    
    Based on the MAST paper methodology using o1 for evaluation.
    Validated to achieve Cohen's Kappa 0.77 against human experts.
    """
    
    def __init__(self, model: str = "o1-preview"):
        self.model = model
        self.prompt_template = MAST_JUDGE_PROMPT
    
    def classify(self, trace: str) -> MASTJudgment:
        """Classify a trace for MAST failures."""
        # Implementation would call the LLM
        pass
    
    def batch_classify(self, traces: List[str]) -> List[MASTJudgment]:
        """Classify multiple traces efficiently."""
        pass
    
    def validate_against_ground_truth(
        self, 
        traces: List[str], 
        ground_truth: List[str]
    ) -> float:
        """
        Calculate Cohen's Kappa against human annotations.
        
        MAST paper achieved 0.77 - use this as your benchmark.
        """
        pass
```

---

## Projects

### Project 1: MAST Detector Library (with MAST-Data)
Complete library with:
- All 14 detectors implemented
- **Validated on MAST-Data (1,600+ traces)**
- Common interfaces
- Configuration system
- Testing framework
- Documentation

### Project 2: LLM-as-Judge Pipeline (NEW)
System that:
- Implements MAST classification prompt
- Achieves >0.70 Kappa against ground truth
- Supports batch processing
- Optimizes for cost

### Project 3: Root Cause Analyzer
System that:
- Combines multiple detectors
- Uses MAST category structure for RCA
- Correlates failures
- Generates human-readable reports
- Suggests fixes

### Project 4: Framework Integration
Integration with:
- LangGraph (via callbacks, including Command/Deferred)
- CrewAI (via callbacks)
- AutoGen/AG2 (via middleware)
- **All 7 MAST-analyzed frameworks**
- Real-time detection

---

## Key Resources (Updated 2025)

### Primary Sources
- **MAST Paper (v3):** https://arxiv.org/abs/2503.13657
- **MAST GitHub:** https://github.com/multi-agent-systems-failure-taxonomy/MAST
- **MAST Project Page:** https://sky.cs.berkeley.edu/project/mast/

### Related Research
- "Towards a Science of Scaling Agent Systems" (uses MAST)
- "Towards Engineering Multi-Agent LLMs" (SEMAP)
- "Multi-Agent Collaboration Mechanisms: A Survey" (Jan 2025)
- "Achilles Heel of DMAS" (2025) - red-teaming
- "ASYNC CONTROL" (2025) - adversarial testing

### Curated Paper Lists
- github.com/luo-junyu/Awesome-Agent-Papers
- github.com/taichengguo/LLM_MultiAgents_Survey_Papers
- github.com/kyegomez/awesome-multi-agent-papers

---

## Assessment

By end of weeks 6-7, you should be able to:

- [ ] Name all 14 MAST failure modes without reference
- [ ] Explain detection algorithm for each
- [ ] Implement detector from scratch in < 1 hour
- [ ] Classify real failures using taxonomy
- [ ] **Use MAST-Data to validate your detectors**
- [ ] **Build an LLM-as-Judge pipeline achieving κ > 0.70**
- [ ] Discuss limitations and false positive rates
- [ ] Compare MAST to other taxonomies
- [ ] Identify gaps for future research
- [ ] **Cite the paper in design partner conversations**

---

## Version History

| Date | MAST Version | Curriculum Update |
|------|--------------|-------------------|
| Initial | v1 (Mar 2025) | Original curriculum with 150 traces |
| Dec 2025 | v3 (Oct 2025) | Added MAST-Data (1,600+), LLM-as-Judge, 7 frameworks |
