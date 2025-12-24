from dataclasses import dataclass
from typing import List, Dict, Optional, Set
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


class CoordinationAnalyzer:
    def __init__(self):
        self.message_timeout_seconds = 30.0
        self.max_back_forth_count = 5
    
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
        
        delegation_graph: Dict[str, List[str]] = defaultdict(list)
        for msg in messages:
            if "delegate" in msg.content.lower() or "pass to" in msg.content.lower():
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
