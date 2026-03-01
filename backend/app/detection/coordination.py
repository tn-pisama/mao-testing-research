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
        self.max_back_forth_count = 3
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
        for msg in messages:
            communication_matrix[msg.from_agent].add(msg.to_agent)
        
        for agent in agent_ids:
            recipients = communication_matrix.get(agent, set())
            potential_recipients = set(agent_ids) - {agent}
            
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
                r"pass\s+\w+\s+to\b",    # "pass this to", "pass it to"
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
