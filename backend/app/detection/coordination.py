from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, Any
from collections import defaultdict


@dataclass
class Message:
    from_agent: str
    to_agent: str
    content: str
    timestamp: float
    acknowledged: bool = False


@dataclass
class CoordinationIssue:
    issue_type: str
    agents_involved: List[str]
    message: str
    severity: str


@dataclass
class CoordinationAnalysisResult:
    healthy: bool
    issues: List[CoordinationIssue]
    metrics: Dict[str, float]
    detected: bool = False
    confidence: float = 0.0
    issue_count: int = 0
    raw_score: Optional[float] = None
    calibration_info: Optional[Dict[str, Any]] = None


class CoordinationAnalyzer:
    def __init__(self, confidence_scaling: float = 1.0):
        self.message_timeout_seconds = 30.0
        self.max_back_forth_count = 5  # v1.3: raised from 3 (normal ack protocols need 4+)
        self.confidence_scaling = confidence_scaling
    
    def analyze_coordination(
        self,
        messages: List[Message],
        agent_ids: List[str],
    ) -> CoordinationAnalysisResult:
        issues = []

        issues.extend(self._detect_ignored_messages(messages))
        issues.extend(self._detect_information_withholding(messages, agent_ids))
        issues.extend(self._detect_excessive_back_forth(messages))
        issues.extend(self._detect_circular_delegation(messages))
        # v1.4: New detection methods
        issues.extend(self._detect_conflicting_instructions(messages))
        issues.extend(self._detect_duplicate_dispatch(messages))
        issues.extend(self._detect_data_corruption_relay(messages))
        issues.extend(self._detect_ordering_violations(messages))
        issues.extend(self._detect_excessive_delegation(messages))
        issues.extend(self._detect_resource_contention(messages))
        issues.extend(self._detect_rapid_instruction_change(messages))
        issues.extend(self._detect_response_delay(messages))
        issues.extend(self._detect_indirect_delegation(messages))

        metrics = self._compute_metrics(messages, agent_ids)

        return CoordinationAnalysisResult(
            healthy=len([i for i in issues if i.severity in ["high", "critical"]]) == 0,
            issues=issues,
            metrics=metrics,
        )
    
    def analyze_coordination_with_confidence(
        self,
        messages: List[Message],
        agent_ids: List[str],
    ) -> CoordinationAnalysisResult:
        issues = []

        issues.extend(self._detect_ignored_messages(messages))
        issues.extend(self._detect_information_withholding(messages, agent_ids))
        issues.extend(self._detect_excessive_back_forth(messages))
        issues.extend(self._detect_circular_delegation(messages))
        # v1.4: New detection methods
        issues.extend(self._detect_conflicting_instructions(messages))
        issues.extend(self._detect_duplicate_dispatch(messages))
        issues.extend(self._detect_data_corruption_relay(messages))
        issues.extend(self._detect_ordering_violations(messages))
        issues.extend(self._detect_excessive_delegation(messages))
        issues.extend(self._detect_resource_contention(messages))
        issues.extend(self._detect_rapid_instruction_change(messages))
        issues.extend(self._detect_response_delay(messages))
        issues.extend(self._detect_indirect_delegation(messages))

        metrics = self._compute_metrics(messages, agent_ids)
        
        max_severity = "low"
        severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        
        for issue in issues:
            sev = issue.severity
            if sev in severity_counts:
                severity_counts[sev] += 1
            if self._severity_rank(sev) > self._severity_rank(max_severity):
                max_severity = sev
        
        raw_score = self._calculate_raw_score(issues, severity_counts, metrics)
        confidence, calibration_info = self._calibrate_confidence(
            issues=issues,
            severity_counts=severity_counts,
            max_severity=max_severity,
            metrics=metrics,
            raw_score=raw_score,
        )
        
        healthy = len([i for i in issues if i.severity in ["high", "critical"]]) == 0
        
        return CoordinationAnalysisResult(
            healthy=healthy,
            issues=issues,
            metrics=metrics,
            detected=len(issues) > 0,
            confidence=confidence,
            issue_count=len(issues),
            raw_score=raw_score,
            calibration_info=calibration_info,
        )
    
    def _severity_rank(self, severity: str) -> int:
        ranks = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        return ranks.get(severity, 0)
    
    def _calculate_raw_score(
        self,
        issues: List[CoordinationIssue],
        severity_counts: Dict[str, int],
        metrics: Dict[str, float],
    ) -> float:
        if not issues:
            return 0.0
        
        issue_score = (
            severity_counts.get("low", 0) * 0.1 +
            severity_counts.get("medium", 0) * 0.25 +
            severity_counts.get("high", 0) * 0.4 +
            severity_counts.get("critical", 0) * 0.6
        )
        
        ack_rate = metrics.get("acknowledgment_rate", 1.0)
        health_penalty = (1.0 - ack_rate) * 0.2
        
        return min(1.0, issue_score + health_penalty)
    
    def _calibrate_confidence(
        self,
        issues: List[CoordinationIssue],
        severity_counts: Dict[str, int],
        max_severity: str,
        metrics: Dict[str, float],
        raw_score: float,
    ) -> Tuple[float, Dict[str, Any]]:
        if not issues:
            return 0.0, {
                "issue_count": 0,
                "severity_counts": severity_counts,
                "max_severity": "none",
                "raw_score": 0.0,
                "confidence_scaling": self.confidence_scaling,
            }
        
        severity_weight = {
            "low": 0.4,
            "medium": 0.6,
            "high": 0.8,
            "critical": 0.95,
        }.get(max_severity, 0.5)

        issue_types = set(i.issue_type for i in issues)
        diversity_factor = min(1.0, len(issue_types) / 4)

        issue_factor = min(0.25, len(issues) * 0.05)

        ack_rate = metrics.get("acknowledgment_rate", 1.0)
        health_factor = (1.0 - ack_rate) * 0.15

        # v1.1: Boosted weights — many true positives were getting low confidence
        # causing them to fall below the optimized threshold.
        base_confidence = (
            severity_weight * 0.40 +
            raw_score * 0.35 +
            diversity_factor * 0.10 +
            issue_factor +
            health_factor
        )
        # v1.1: Floor by severity — clear failures should never have very low confidence
        severity_floor = {"low": 0.25, "medium": 0.35, "high": 0.55, "critical": 0.70}
        base_confidence = max(base_confidence, severity_floor.get(max_severity, 0.25))
        
        calibrated = min(0.99, base_confidence * self.confidence_scaling)
        
        calibration_info = {
            "issue_count": len(issues),
            "severity_counts": severity_counts,
            "max_severity": max_severity,
            "severity_weight": severity_weight,
            "diversity_factor": round(diversity_factor, 4),
            "issue_types": list(issue_types),
            "acknowledgment_rate": ack_rate,
            "raw_score": round(raw_score, 4),
            "confidence_scaling": self.confidence_scaling,
        }
        
        return round(calibrated, 4), calibration_info
    
    def _detect_ignored_messages(self, messages: List[Message]) -> List[CoordinationIssue]:
        issues = []

        for msg in messages:
            if not msg.acknowledged:
                later_messages = [
                    m for m in messages
                    if m.timestamp > msg.timestamp and m.from_agent == msg.to_agent
                ]
                if not later_messages:
                    issues.append(CoordinationIssue(
                        issue_type="ignored_message",
                        agents_involved=[msg.from_agent, msg.to_agent],
                        message=f"Message from {msg.from_agent} to {msg.to_agent} was not acknowledged",
                        severity="medium",
                    ))

        # v1.1: Detect content-based ignored messages — receiver asks for the
        # same information that was already sent to them (message was lost/ignored
        # despite being "acknowledged").
        for i, msg in enumerate(messages):
            later_from_recipient = [
                m for m in messages
                if m.timestamp > msg.timestamp and m.from_agent == msg.to_agent
            ]
            for reply in later_from_recipient:
                reply_lower = reply.content.lower()
                msg_lower = msg.content.lower()
                # If reply asks for what was already provided, it's a lost message
                request_phrases = ["please provide", "requesting", "still waiting",
                                   "no .* received", "where is", "send me",
                                   "need the", "waiting for"]
                import re as _re
                is_repeat_request = any(_re.search(p, reply_lower) for p in request_phrases)
                # Check content overlap — is the reply asking about the same topic?
                msg_words = set(w for w in msg_lower.split() if len(w) > 4)
                reply_words = set(w for w in reply_lower.split() if len(w) > 4)
                if msg_words and reply_words:
                    overlap = len(msg_words & reply_words) / min(len(msg_words), len(reply_words))
                else:
                    overlap = 0
                if is_repeat_request and overlap > 0.2:
                    issues.append(CoordinationIssue(
                        issue_type="message_lost",
                        agents_involved=[msg.from_agent, msg.to_agent],
                        message=f"Message from {msg.from_agent} appears lost — {msg.to_agent} re-requests same info",
                        severity="high",
                    ))
                    break  # One detection per message pair

        return issues
    
    def _detect_information_withholding(
        self,
        messages: List[Message],
        agent_ids: List[str],
    ) -> List[CoordinationIssue]:
        issues = []

        communication_matrix: Dict[str, Set[str]] = defaultdict(set)
        # v1.3: Also track which agents have sent at least one message
        # and which agents have been addressed by others.
        agents_that_sent: Set[str] = set()
        agents_addressed: Dict[str, Set[str]] = defaultdict(set)
        for msg in messages:
            communication_matrix[msg.from_agent].add(msg.to_agent)
            agents_that_sent.add(msg.from_agent)
            agents_addressed[msg.to_agent].add(msg.from_agent)

        for agent in agent_ids:
            # v1.3: Only flag agents that have sent at least one message.
            # Agents that only receive (terminal nodes in pipelines, fan-out
            # receivers, pub/sub subscribers) should not be penalized for
            # limited communication breadth.
            if agent not in agents_that_sent:
                continue

            recipients = communication_matrix.get(agent, set())
            potential_recipients = set(agent_ids) - {agent}

            # v1.3: Also skip if the agent has been addressed by at most 1
            # other agent (pipeline topology: each agent talks to next in chain).
            addressed_by = agents_addressed.get(agent, set())
            if len(addressed_by) <= 1 and len(recipients) >= 1:
                continue

            if len(recipients) < len(potential_recipients) * 0.5 and len(potential_recipients) > 1:
                missing = potential_recipients - recipients
                issues.append(CoordinationIssue(
                    issue_type="limited_communication",
                    agents_involved=[agent] + list(missing),
                    message=f"Agent {agent} has not communicated with: {missing}",
                    severity="low",
                ))

        return issues
    
    def _detect_excessive_back_forth(self, messages: List[Message]) -> List[CoordinationIssue]:
        issues = []
        
        pair_exchanges: Dict[tuple, int] = defaultdict(int)
        for msg in messages:
            pair = tuple(sorted([msg.from_agent, msg.to_agent]))
            pair_exchanges[pair] += 1
        
        for pair, count in pair_exchanges.items():
            if count > self.max_back_forth_count:
                issues.append(CoordinationIssue(
                    issue_type="excessive_back_forth",
                    agents_involved=list(pair),
                    message=f"Agents {pair[0]} and {pair[1]} have exchanged {count} messages (threshold: {self.max_back_forth_count})",
                    severity="medium",
                ))
        
        return issues
    
    def _detect_circular_delegation(self, messages: List[Message]) -> List[CoordinationIssue]:
        issues = []
        
        import re as _re
        delegation_graph: Dict[str, List[str]] = defaultdict(list)
        for msg in messages:
            content_lower = msg.content.lower()
            # v1.1: Use both exact substring and regex for delegation detection.
            # Regex handles cases like "pass this to" or "hand it off to".
            delegation_phrases = [
                "delegate", "hand off", "handoff", "take over",
                "your turn", "assign to", "forward to", "escalate to",
                "handle this", "proceed with", "can you handle",
                "please take", "transfer to", "route to",
            ]
            delegation_regexes = [
                r"pass\s+(?:\w+\s+)?to\b",  # "pass to", "pass this to", "pass it to"
                r"hand\s+\w+\s+off\b",    # "hand it off"
                r"delegat\w*\s+(?:this|it|to)\b",  # "delegating to", "delegated this"
            ]
            has_delegation = (
                any(phrase in content_lower for phrase in delegation_phrases) or
                any(_re.search(pat, content_lower) for pat in delegation_regexes)
            )
            if has_delegation:
                delegation_graph[msg.from_agent].append(msg.to_agent)
        
        for start_agent in delegation_graph:
            visited = set()
            stack = [start_agent]
            
            while stack:
                current = stack.pop()
                if current in visited:
                    issues.append(CoordinationIssue(
                        issue_type="circular_delegation",
                        agents_involved=list(visited),
                        message=f"Circular delegation detected involving {visited}",
                        severity="high",
                    ))
                    break
                visited.add(current)
                stack.extend(delegation_graph.get(current, []))
        
        return issues
    
    # ── v1.4: New detection methods ────────────────────────────────────────

    def _detect_conflicting_instructions(self, messages: List[Message]) -> List[CoordinationIssue]:
        """v1.4: Detect when multiple agents send contradictory instructions to the same agent."""
        issues = []
        # Group messages by recipient within short time windows
        by_recipient: Dict[str, List[Message]] = defaultdict(list)
        for msg in messages:
            by_recipient[msg.to_agent].append(msg)

        _CONFLICT_PAIRS = [
            ({"update", "set", "change", "enable", "activate", "start", "add"},
             {"delete", "remove", "disable", "deactivate", "stop", "drop"}),
            ({"create", "insert", "save", "write", "open"},
             {"delete", "remove", "destroy", "close", "drop"}),
            ({"lock"}, {"unlock"}),
            ({"approve", "accept"}, {"reject", "deny", "decline"}),
        ]

        for recipient, msgs in by_recipient.items():
            for i in range(len(msgs)):
                for j in range(i + 1, len(msgs)):
                    m1, m2 = msgs[i], msgs[j]
                    if m1.from_agent == m2.from_agent:
                        continue  # Same sender — might be an update, not conflict
                    if abs(m1.timestamp - m2.timestamp) > 5.0:
                        continue  # Too far apart in time
                    w1 = set(m1.content.lower().split())
                    w2 = set(m2.content.lower().split())
                    for pos_set, neg_set in _CONFLICT_PAIRS:
                        if (w1 & pos_set and w2 & neg_set) or (w1 & neg_set and w2 & pos_set):
                            issues.append(CoordinationIssue(
                                issue_type="conflicting_instructions",
                                agents_involved=[m1.from_agent, m2.from_agent, recipient],
                                message=f"Conflicting instructions to {recipient}: '{m1.content[:50]}' vs '{m2.content[:50]}'",
                                severity="high",
                            ))
                            break
        return issues

    def _detect_duplicate_dispatch(self, messages: List[Message]) -> List[CoordinationIssue]:
        """v1.4: Detect when the same task is dispatched to multiple agents."""
        issues = []
        # Group by sender
        by_sender: Dict[str, List[Message]] = defaultdict(list)
        for msg in messages:
            by_sender[msg.from_agent].append(msg)

        for sender, msgs in by_sender.items():
            for i in range(len(msgs)):
                for j in range(i + 1, len(msgs)):
                    m1, m2 = msgs[i], msgs[j]
                    if m1.to_agent == m2.to_agent:
                        continue  # Same recipient — not a duplicate dispatch
                    if abs(m1.timestamp - m2.timestamp) > 2.0:
                        continue
                    # Check content similarity
                    w1 = set(m1.content.lower().split())
                    w2 = set(m2.content.lower().split())
                    if not w1 or not w2:
                        continue
                    overlap = len(w1 & w2) / min(len(w1), len(w2))
                    if overlap >= 0.7:
                        issues.append(CoordinationIssue(
                            issue_type="duplicate_dispatch",
                            agents_involved=[sender, m1.to_agent, m2.to_agent],
                            message=f"Same task dispatched to {m1.to_agent} and {m2.to_agent}: '{m1.content[:50]}'",
                            severity="medium",
                        ))
        return issues

    def _detect_data_corruption_relay(self, messages: List[Message]) -> List[CoordinationIssue]:
        """v1.4: Detect when data values change during relay between agents."""
        issues = []
        import re as _re
        # Find relay chains: A→B then B→C with overlapping topic (C must differ from A)
        for i, m1 in enumerate(messages):
            for m2 in messages:
                if m2.timestamp <= m1.timestamp:
                    continue
                if m2.from_agent != m1.to_agent:
                    continue  # Not a relay
                if m2.to_agent == m1.from_agent:
                    continue  # Reply, not relay to third party
                # Check topic overlap
                w1 = set(w for w in m1.content.lower().split() if len(w) > 3)
                w2 = set(w for w in m2.content.lower().split() if len(w) > 3)
                if not w1 or not w2:
                    continue
                topic_overlap = len(w1 & w2) / min(len(w1), len(w2))
                if topic_overlap < 0.2:
                    continue  # Different topic — not a relay

                # Extract key-value pairs or named entities
                kv1 = dict(_re.findall(r'(\w+):\s*(\w+)', m1.content))
                kv2 = dict(_re.findall(r'(\w+):\s*(\w+)', m2.content))
                if kv1 and kv2:
                    shared_keys = set(kv1.keys()) & set(kv2.keys())
                    for key in shared_keys:
                        if kv1[key] != kv2[key]:
                            issues.append(CoordinationIssue(
                                issue_type="data_corruption_relay",
                                agents_involved=[m1.from_agent, m1.to_agent, m2.to_agent],
                                message=f"Data corrupted in relay: {key} changed from '{kv1[key]}' to '{kv2[key]}'",
                                severity="high",
                            ))
                            return issues  # One detection per chain

                # Also check for proper noun substitution (names)
                # Only match names NOT at the start of a sentence to avoid
                # false positives from sentence-initial capitalization
                def _extract_names(text: str) -> Set[str]:
                    # Find capitalized words that aren't the first word
                    # of the message or following sentence-ending punctuation
                    names = set()
                    for m in _re.finditer(r'\b[A-Z][a-z]+\b', text):
                        pos = m.start()
                        if pos == 0:
                            continue  # First word of message
                        before = text[max(0, pos - 3):pos].strip()
                        if before and before[-1] in '.!?':
                            continue  # First word of sentence
                        names.add(m.group())
                    return names
                names1 = _extract_names(m1.content)
                names2 = _extract_names(m2.content)
                if names1 and names2 and topic_overlap > 0.3:
                    changed_names = names1 - names2
                    new_names = names2 - names1
                    if changed_names and new_names:
                        issues.append(CoordinationIssue(
                            issue_type="data_corruption_relay",
                            agents_involved=[m1.from_agent, m1.to_agent, m2.to_agent],
                            message=f"Name changed in relay: {changed_names} became {new_names}",
                            severity="high",
                        ))
                        return issues
        return issues

    def _detect_ordering_violations(self, messages: List[Message]) -> List[CoordinationIssue]:
        """v1.4: Detect when sequential steps complete out of order."""
        issues = []
        import re as _re
        # Find orchestrator dispatching sequential steps
        step_dispatches: Dict[str, List[Tuple[Message, int]]] = defaultdict(list)
        for msg in messages:
            # Look for step/phase numbering in content
            match = _re.search(r'\b(?:step|phase|task)\s*(\d+)', msg.content, _re.IGNORECASE)
            if match:
                step_num = int(match.group(1))
                step_dispatches[msg.from_agent].append((msg, step_num))

        for sender, dispatches in step_dispatches.items():
            dispatches.sort(key=lambda x: x[1])  # Sort by step number
            for i in range(len(dispatches) - 1):
                msg_early, step_early = dispatches[i]
                msg_late, step_late = dispatches[i + 1]
                # Check if the later step's recipient responded before the earlier step's
                early_response = next(
                    (m for m in messages if m.from_agent == msg_early.to_agent
                     and m.timestamp > msg_early.timestamp),
                    None,
                )
                late_response = next(
                    (m for m in messages if m.from_agent == msg_late.to_agent
                     and m.timestamp > msg_late.timestamp),
                    None,
                )
                if late_response and (not early_response or late_response.timestamp < early_response.timestamp):
                    issues.append(CoordinationIssue(
                        issue_type="ordering_violation",
                        agents_involved=[sender, msg_early.to_agent, msg_late.to_agent],
                        message=f"Step {step_late} completed before step {step_early}",
                        severity="medium",
                    ))
        return issues

    def _detect_excessive_delegation(self, messages: List[Message]) -> List[CoordinationIssue]:
        """v1.4: Detect when a task is forwarded through a chain without being worked on."""
        issues = []
        # Build forwarding chains: A→B, B→C, C→D with similar content
        chains: List[List[Message]] = []
        for msg in messages:
            # Try to extend an existing chain
            extended = False
            for chain in chains:
                last = chain[-1]
                if msg.from_agent == last.to_agent and msg.timestamp > last.timestamp:
                    w_last = set(last.content.lower().split())
                    w_msg = set(msg.content.lower().split())
                    if w_last and w_msg:
                        overlap = len(w_last & w_msg) / min(len(w_last), len(w_msg))
                        if overlap >= 0.6:
                            chain.append(msg)
                            extended = True
                            break
            if not extended:
                chains.append([msg])

        for chain in chains:
            if len(chain) >= 3:  # 3+ forwards = excessive
                agents = [chain[0].from_agent] + [m.to_agent for m in chain]
                issues.append(CoordinationIssue(
                    issue_type="excessive_delegation",
                    agents_involved=agents,
                    message=f"Task forwarded through {len(chain)} agents without work: {' → '.join(agents)}",
                    severity="medium",
                ))
        return issues

    def _detect_resource_contention(self, messages: List[Message]) -> List[CoordinationIssue]:
        """v1.4: Detect when multiple agents compete for the same resource."""
        issues = []
        import re as _re
        _RESOURCE_VERBS = {"lock", "acquire", "reserve", "claim", "allocate", "write"}
        # Find messages requesting resource access
        resource_requests: List[Tuple[Message, str]] = []
        for msg in messages:
            lower = msg.content.lower()
            has_verb = any(v in lower for v in _RESOURCE_VERBS)
            if has_verb:
                # Extract resource name (word after verb, or common patterns)
                for v in _RESOURCE_VERBS:
                    match = _re.search(v + r'\s+(?:to\s+)?(?:resource\s+)?(\w+)', lower)
                    if match:
                        resource_requests.append((msg, match.group(1)))
                        break

        # Check for contention: different agents requesting same resource
        for i in range(len(resource_requests)):
            for j in range(i + 1, len(resource_requests)):
                m1, r1 = resource_requests[i]
                m2, r2 = resource_requests[j]
                if r1 == r2 and m1.from_agent != m2.from_agent:
                    if abs(m1.timestamp - m2.timestamp) < 5.0:
                        issues.append(CoordinationIssue(
                            issue_type="resource_contention",
                            agents_involved=[m1.from_agent, m2.from_agent],
                            message=f"Resource contention: {m1.from_agent} and {m2.from_agent} both requesting '{r1}'",
                            severity="high",
                        ))
        return issues

    def _detect_rapid_instruction_change(self, messages: List[Message]) -> List[CoordinationIssue]:
        """v1.4: Detect when an agent cancels/overrides a recent instruction."""
        issues = []
        _CANCEL_WORDS = {"cancel", "instead", "disregard", "ignore", "scratch", "stop",
                         "abort", "nevermind", "never mind", "actually"}
        # Group by (from_agent, to_agent) pair
        by_pair: Dict[Tuple[str, str], List[Message]] = defaultdict(list)
        for msg in messages:
            by_pair[(msg.from_agent, msg.to_agent)].append(msg)

        for pair, msgs in by_pair.items():
            msgs_sorted = sorted(msgs, key=lambda m: m.timestamp)
            for i in range(len(msgs_sorted) - 1):
                m1, m2 = msgs_sorted[i], msgs_sorted[i + 1]
                if m2.timestamp - m1.timestamp > 3.0:
                    continue  # Not rapid
                lower2 = m2.content.lower()
                if any(w in lower2 for w in _CANCEL_WORDS):
                    issues.append(CoordinationIssue(
                        issue_type="rapid_instruction_change",
                        agents_involved=list(pair),
                        message=f"Rapid instruction change from {pair[0]} to {pair[1]}: '{m2.content[:50]}'",
                        severity="low",
                    ))
        return issues

    def _detect_response_delay(self, messages: List[Message]) -> List[CoordinationIssue]:
        """v1.4: Detect unusually long delays between request and response."""
        issues = []
        # Find request-response pairs
        for msg in messages:
            responses = [
                m for m in messages
                if m.from_agent == msg.to_agent and m.to_agent == msg.from_agent
                and m.timestamp > msg.timestamp
            ]
            if responses:
                first_response = min(responses, key=lambda m: m.timestamp)
                delay = first_response.timestamp - msg.timestamp
                if delay > 10.0:  # 10 seconds threshold
                    issues.append(CoordinationIssue(
                        issue_type="slow_response",
                        agents_involved=[msg.from_agent, msg.to_agent],
                        message=f"Slow response from {msg.to_agent}: {delay:.0f}s delay",
                        severity="low",
                    ))
        return issues

    def _detect_indirect_delegation(self, messages: List[Message]) -> List[CoordinationIssue]:
        """v1.4: Detect when an intermediary re-delegates and response bypasses them."""
        issues = []
        # Pattern: A→B, B→C, C→A (B is bypassed in the response)
        for m1 in messages:
            for m2 in messages:
                if m2.timestamp <= m1.timestamp:
                    continue
                if m2.from_agent != m1.to_agent:
                    continue  # m2 must be from m1's recipient
                if m2.to_agent == m1.from_agent:
                    continue  # Direct response, not re-delegation
                # m1: A→B, m2: B→C — check if C replies to A
                for m3 in messages:
                    if m3.timestamp <= m2.timestamp:
                        continue
                    if m3.from_agent == m2.to_agent and m3.to_agent == m1.from_agent:
                        # C→A: bypassing B — the triangle pattern itself is
                        # strong evidence. Use prefix matching for topic check
                        # (handles summarize/summary, deploy/deployment, etc.)
                        w1 = set(w[:5] for w in m1.content.lower().split() if len(w) > 3)
                        w3 = set(w[:5] for w in m3.content.lower().split() if len(w) > 3)
                        prefix_overlap = len(w1 & w3)
                        if prefix_overlap > 0 or len(messages) <= 4:
                            issues.append(CoordinationIssue(
                                issue_type="indirect_delegation",
                                agents_involved=[m1.from_agent, m1.to_agent, m2.to_agent],
                                message=f"{m1.to_agent} re-delegated to {m2.to_agent} who replied directly to {m1.from_agent}",
                                severity="low",
                            ))
                            return issues  # One per trace
        return issues

    def _compute_metrics(
        self,
        messages: List[Message],
        agent_ids: List[str],
    ) -> Dict[str, float]:
        if not messages or not agent_ids:
            return {}
        
        total_messages = len(messages)
        acknowledged = sum(1 for m in messages if m.acknowledged)
        
        unique_pairs = len(set(
            tuple(sorted([m.from_agent, m.to_agent])) for m in messages
        ))
        max_pairs = len(agent_ids) * (len(agent_ids) - 1) / 2
        
        return {
            "acknowledgment_rate": acknowledged / total_messages if total_messages > 0 else 0,
            "communication_density": unique_pairs / max_pairs if max_pairs > 0 else 0,
            "messages_per_agent": total_messages / len(agent_ids) if agent_ids else 0,
        }


coordination_analyzer = CoordinationAnalyzer()
