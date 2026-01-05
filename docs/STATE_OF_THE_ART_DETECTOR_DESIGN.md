# State-of-the-Art Multi-Agent Failure Detector Design

Based on comprehensive research from NeurIPS 2025, ICML 2025, and latest academic publications.

## Research Foundation

### Primary Sources

1. **MAST: Multi-Agent System Failure Taxonomy** (NeurIPS 2025 Spotlight)
   - UC Berkeley Sky Computing Lab
   - 14 failure modes, 3 categories, 1600+ annotated traces
   - Inter-annotator kappa: 0.88
   - Source: https://arxiv.org/abs/2503.13657

2. **Who&When: Automated Failure Attribution** (ICML 2025 Spotlight)
   - Penn State, Duke, Google DeepMind
   - 127 MAS systems with fine-grained annotations
   - Best method: 53.5% agent attribution accuracy
   - Source: https://arxiv.org/abs/2505.00212

3. **AgentErrorTaxonomy & AgentErrorBench** (October 2025)
   - 5 failure categories: memory, reflection, planning, action, system
   - AgentDebug achieves 24% higher accuracy
   - Source: https://arxiv.org/abs/2509.25370

4. **Microsoft AI Red Team Taxonomy** (April 2025)
   - Safety vs Security failure modes
   - Novel vs Existing failure patterns
   - Source: Microsoft Security Blog

---

## MAST Failure Mode Mapping

### Category 1: Specification and System Design (FC1)

| Code | Name | Prevalence | Our Detector | Detection Method |
|------|------|------------|--------------|------------------|
| FM-1.1 | Disobey Task Specification | 14% | F1 (TurnAwareSpecificationMismatchDetector) | Semantic similarity between task and output |
| FM-1.2 | Disobey Role Specification | 18% | NEW: RoleViolationDetector | Role boundary keyword detection + semantic drift |
| FM-1.3 | Step Repetition | 16% | F5 (TurnAwareLoopDetector) | Content hash, cosine similarity, n-gram overlap |
| FM-1.4 | Loss of Conversation History | 12% | F7 (TurnAwareContextNeglectDetector) | Reference tracking, entity persistence |
| FM-1.5 | Unaware of Termination Conditions | 40% | F14 (TurnAwareCompletionMisjudgmentDetector) | Completion marker detection + incomplete indicators |

### Category 2: Inter-Agent Misalignment (FC2)

| Code | Name | Prevalence | Our Detector | Detection Method |
|------|------|------------|--------------|------------------|
| FM-2.1 | Conversation Reset | 14% | NEW: ConversationResetDetector | Context discontinuity, topic shift detection |
| FM-2.2 | Fail to Ask for Clarification | 18% | F8 (TurnAwareInformationWithholdingDetector) | Ambiguity markers + no question response |
| FM-2.3 | Task Derailment | 20% | F6 (TurnAwareDerailmentDetector) | Topic drift via embedding distance |
| FM-2.4 | Information Withholding | 12% | F8 (TurnAwareInformationWithholdingDetector) | Information density comparison |
| FM-2.5 | Ignored Other Agent's Input | 10% | NEW: InputIgnoredDetector | Response relevance to prior turn |
| FM-2.6 | Reasoning-Action Mismatch | 26% | NEW: ReasoningActionMismatchDetector | CoT-action consistency verification |

### Category 3: Task Verification and Termination (FC3)

| Code | Name | Prevalence | Our Detector | Detection Method |
|------|------|------------|--------------|------------------|
| FM-3.1 | Premature Termination | 22% | F14 (TurnAwareCompletionMisjudgmentDetector) | Completion claim + incomplete markers |
| FM-3.2 | No/Incomplete Verification | 50% | F12/F13 (OutputValidation/QualityGateBypass) | Quality gate presence detection |
| FM-3.3 | Incorrect Verification | 28% | F12 (TurnAwareOutputValidationDetector) | Error-after-success pattern detection |

---

## State-of-the-Art Detection Techniques

### 1. Embedding-Based Semantic Detection

**Research Basis**: 2025 drift detection research shows 23% variance in GPT-4 response patterns.

```python
class SemanticDriftDetector:
    """
    Uses embedding similarity to detect:
    - Task specification drift (FM-1.1)
    - Topic derailment (FM-2.3)
    - Context neglect (FM-1.4)
    """

    def __init__(self, embedding_model="all-MiniLM-L6-v2"):
        self.embedder = SentenceTransformer(embedding_model)
        self.drift_threshold = 0.65  # Cosine similarity threshold

    def detect_specification_drift(self, task: str, outputs: List[str]) -> float:
        """Compare task embedding to output embeddings."""
        task_emb = self.embedder.encode(task)
        output_embs = self.embedder.encode(outputs)
        similarities = cosine_similarity([task_emb], output_embs)[0]
        return 1.0 - np.mean(similarities)  # Higher = more drift

    def detect_topic_drift(self, turns: List[str]) -> List[int]:
        """Detect turns where topic shifts significantly."""
        embeddings = self.embedder.encode(turns)
        drift_turns = []
        for i in range(1, len(embeddings)):
            sim = cosine_similarity([embeddings[i-1]], [embeddings[i]])[0][0]
            if sim < self.drift_threshold:
                drift_turns.append(i)
        return drift_turns
```

### 2. Self-Consistency Verification

**Research Basis**: CISC (2025) reduces required samples by 40% using confidence weighting.

```python
class SelfConsistencyDetector:
    """
    Uses multiple sampling to verify output reliability.
    Based on Confidence-Informed Self-Consistency (CISC).
    """

    def detect_inconsistent_reasoning(
        self,
        reasoning_traces: List[str],
        final_answers: List[str]
    ) -> Dict[str, Any]:
        """
        Detect inconsistencies across multiple reasoning paths.
        High variance indicates unreliable reasoning.
        """
        # Cluster answers semantically
        answer_embeddings = self.embedder.encode(final_answers)
        clusters = self._cluster_answers(answer_embeddings)

        # Calculate entropy of answer distribution
        entropy = self._calculate_entropy(clusters)

        return {
            "detected": entropy > self.entropy_threshold,
            "confidence": 1.0 - entropy,
            "num_clusters": len(set(clusters)),
            "dominant_answer_ratio": max(Counter(clusters).values()) / len(clusters)
        }
```

### 3. Reasoning-Action Mismatch Detection (FM-2.6 - 26% prevalence)

**Research Basis**: ReAct framework analysis shows thought-action divergence as key failure pattern.

```python
class ReasoningActionMismatchDetector:
    """
    Detects discrepancy between stated reasoning and actual actions.
    This is the highest-prevalence FC2 failure (26%).
    """

    # Action verbs that should match reasoning
    ACTION_INDICATORS = {
        "search": ["searching", "looking for", "finding", "querying"],
        "write": ["writing", "creating", "generating", "composing"],
        "read": ["reading", "examining", "analyzing", "reviewing"],
        "execute": ["running", "executing", "calling", "invoking"],
        "calculate": ["computing", "calculating", "determining", "figuring"],
    }

    def detect(self, thought: str, action: str, observation: str) -> Dict:
        """
        Compare ReAct-style thought with action taken.
        """
        # Extract intended action from thought
        intended_actions = self._extract_intentions(thought)

        # Extract actual action performed
        actual_action = self._parse_action(action)

        # Check alignment
        mismatches = []
        for intended in intended_actions:
            if not self._actions_align(intended, actual_action):
                mismatches.append({
                    "intended": intended,
                    "actual": actual_action,
                    "severity": self._calculate_severity(intended, actual_action)
                })

        return {
            "detected": len(mismatches) > 0,
            "mismatches": mismatches,
            "confidence": min(0.9, 0.5 + len(mismatches) * 0.2)
        }
```

### 4. Termination Condition Awareness (FM-1.5 - 40% prevalence in FC1)

**Research Basis**: Highest prevalence failure in system design category.

```python
class TerminationAwarenessDetector:
    """
    Detects when agents are unaware of termination conditions.
    40% of FC1 failures - critical to address.
    """

    TERMINATION_SIGNALS = [
        "TERMINATE", "DONE", "COMPLETE", "FINISHED",
        "task complete", "goal achieved", "mission accomplished",
        "all done", "nothing more", "that's all"
    ]

    CONTINUATION_AFTER_TERMINATION = [
        "but wait", "actually", "one more thing",
        "let me also", "additionally", "furthermore"
    ]

    def detect(self, turns: List[TurnSnapshot]) -> TurnAwareDetectionResult:
        """Detect failure to recognize termination conditions."""
        issues = []

        for i, turn in enumerate(turns):
            # Check if termination was signaled
            if self._has_termination_signal(turn.content):
                # Check if conversation continues inappropriately
                if i < len(turns) - 1:
                    next_turn = turns[i + 1]
                    if self._is_continuation(next_turn.content):
                        issues.append({
                            "type": "ignored_termination",
                            "turn": i,
                            "signal": self._extract_signal(turn.content)
                        })

        # Also check for endless processing without termination
        if len(turns) > 20 and not any(
            self._has_termination_signal(t.content) for t in turns[-5:]
        ):
            issues.append({
                "type": "missing_termination",
                "turn": len(turns),
                "description": "Long conversation without termination signal"
            })

        return self._build_result(issues)
```

### 5. Verification Quality Detection (FM-3.2 - 50% prevalence in FC3)

**Research Basis**: Dominant failure mode in task verification category.

```python
class VerificationQualityDetector:
    """
    Detects incomplete or missing verification.
    50% of FC3 failures - most critical verification issue.
    """

    VERIFICATION_KEYWORDS = [
        "verified", "checked", "validated", "confirmed",
        "tested", "passed", "approved", "works correctly"
    ]

    INCOMPLETE_VERIFICATION_SIGNALS = [
        "should work", "seems correct", "looks good",
        "probably fine", "appears to", "i think it works",
        "assuming", "hopefully", "might be"
    ]

    PROPER_VERIFICATION_PATTERNS = [
        r"test.*pass", r"all.*check", r"verification.*complete",
        r"validated.*against", r"confirmed.*with"
    ]

    def detect(self, turns: List[TurnSnapshot]) -> TurnAwareDetectionResult:
        """Detect missing or incomplete verification."""
        verification_present = False
        verification_quality = "none"
        issues = []

        for turn in turns:
            content_lower = turn.content.lower()

            # Check for verification attempts
            if any(kw in content_lower for kw in self.VERIFICATION_KEYWORDS):
                verification_present = True

                # Check verification quality
                if any(signal in content_lower for signal in self.INCOMPLETE_VERIFICATION_SIGNALS):
                    verification_quality = "incomplete"
                    issues.append({
                        "type": "incomplete_verification",
                        "turn": turn.turn_number,
                        "evidence": self._extract_signal(turn.content)
                    })
                elif any(re.search(pat, content_lower) for pat in self.PROPER_VERIFICATION_PATTERNS):
                    verification_quality = "proper"

        # Missing verification entirely is worst case
        if not verification_present:
            issues.append({
                "type": "missing_verification",
                "description": "No verification steps detected in conversation"
            })

        return self._build_result(issues, verification_quality)
```

---

## Implementation Priority

Based on MAST prevalence data and detection feasibility:

### P0 - Critical (>25% prevalence or high impact)
1. **FM-3.2: No/Incomplete Verification** (50% of FC3) - Enhance F12/F13
2. **FM-1.5: Unaware of Termination** (40% of FC1) - New detector
3. **FM-2.6: Reasoning-Action Mismatch** (26% of FC2) - New detector

### P1 - High Priority (15-25% prevalence)
4. **FM-3.3: Incorrect Verification** (28% of FC3) - Enhance F12
5. **FM-3.1: Premature Termination** (22% of FC3) - Enhance F14
6. **FM-2.3: Task Derailment** (20% of FC2) - Enhance F6
7. **FM-2.2: Fail to Ask Clarification** (18% of FC2) - New detector
8. **FM-1.2: Disobey Role Specification** (18% of FC1) - New detector

### P2 - Medium Priority (10-15% prevalence)
9. **FM-1.3: Step Repetition** (16% of FC1) - Already implemented (F5)
10. **FM-1.1: Disobey Task Specification** (14% of FC1) - Already implemented (F1)
11. **FM-2.1: Conversation Reset** (14% of FC2) - New detector
12. **FM-2.4: Information Withholding** (12% of FC2) - Already implemented (F8)
13. **FM-1.4: Loss of Conversation History** (12% of FC1) - Already implemented (F7)
14. **FM-2.5: Ignored Other Agent's Input** (10% of FC2) - New detector

---

## Detection Method Comparison

| Method | Accuracy | Speed | Interpretability | Use Case |
|--------|----------|-------|------------------|----------|
| Keyword-based | Low (15-30% F1) | Very Fast | High | Initial filtering |
| Embedding similarity | Medium (40-60% F1) | Fast | Medium | Drift/derailment |
| Self-consistency | High (60-80% F1) | Slow | High | Verification |
| LLM-as-Judge | High (70-85% F1) | Very Slow | Medium | Complex patterns |
| Hybrid (tiered) | Highest (75-90% F1) | Medium | High | Production use |

---

## Recommended Architecture: Tiered Detection

```
Input Trace
    │
    ▼
┌─────────────────────────────────────┐
│  Tier 1: Fast Keyword Detectors     │  <1ms per trace
│  - Loop patterns (F5)               │
│  - Quality gate bypass (F13)        │
│  - Completion markers (F14)         │
└───────────────┬─────────────────────┘
                │ Flagged traces
                ▼
┌─────────────────────────────────────┐
│  Tier 2: Embedding-Based Analysis   │  ~50ms per trace
│  - Task specification drift (F1)    │
│  - Topic derailment (F6)            │
│  - Context neglect (F7)             │
└───────────────┬─────────────────────┘
                │ Uncertain cases
                ▼
┌─────────────────────────────────────┐
│  Tier 3: LLM Verification           │  ~500ms per trace
│  - Reasoning-action mismatch        │
│  - Verification quality assessment  │
│  - Complex multi-turn patterns      │
└─────────────────────────────────────┘
```

---

## References

1. Cemri, M., Pan, M.Z., Yang, S., et al. (2025). "Why Do Multi-Agent LLM Systems Fail?" NeurIPS 2025. https://arxiv.org/abs/2503.13657

2. Zhang, S., Yin, M., Zhang, J., et al. (2025). "Which Agent Causes Task Failures and When?" ICML 2025. https://arxiv.org/abs/2505.00212

3. Zhu, K., et al. (2025). "Where LLM Agents Fail and How They Can Learn From Failures." https://arxiv.org/abs/2509.25370

4. Microsoft AI Red Team. (2025). "Taxonomy of Failure Modes in Agentic AI Systems." Microsoft Security Blog.

5. Invariant Labs. (2025). "Loop Detection Guardrails." https://explorer.invariantlabs.ai/docs/guardrails/loops/

6. Various. (2025). "Self-Consistency and Uncertainty Estimation in LLMs." ACL/NAACL 2025.
