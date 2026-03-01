"""
RAG Poisoning Detection for Dify Workflows
===========================================

Detects prompt injection and poisoning patterns in knowledge retrieval
node outputs. Checks whether retrieved documents contain injection
payloads and whether downstream LLM nodes echo injected content.

Dify-specific: targets knowledge_retrieval node type and its
outputs.documents[].content structure.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from app.detection.turn_aware._base import (
    TurnAwareDetector,
    TurnAwareDetectionResult,
    TurnAwareSeverity,
    TurnSnapshot,
)

logger = logging.getLogger(__name__)

# Injection patterns grouped by category
INJECTION_PATTERNS: Dict[str, List[re.Pattern]] = {
    "system_override": [
        re.compile(r"SYSTEM\s*:", re.IGNORECASE),
        re.compile(r"ignore\s+(all\s+)?previous", re.IGNORECASE),
        re.compile(r"new\s+instructions", re.IGNORECASE),
        re.compile(r"disregard", re.IGNORECASE),
        re.compile(r"forget\s+everything", re.IGNORECASE),
    ],
    "role_hijack": [
        re.compile(r"you\s+are\s+now", re.IGNORECASE),
        re.compile(r"act\s+as", re.IGNORECASE),
        re.compile(r"pretend\s+to\s+be", re.IGNORECASE),
    ],
    "model_specific": [
        re.compile(r"\[INST\]", re.IGNORECASE),
        re.compile(r"<<SYS>>", re.IGNORECASE),
        re.compile(r"</s>"),
    ],
    "zero_width_injection": [
        re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]"),
    ],
    "hidden_override": [
        re.compile(r"SYSTEM_OVERRIDE", re.IGNORECASE),
        re.compile(r"ADMIN_OVERRIDE", re.IGNORECASE),
        re.compile(r"REVEAL_SYSTEM_PROMPT", re.IGNORECASE),
        re.compile(r"skip\s+all\s+validation", re.IGNORECASE),
        re.compile(r"bypass\s+(all\s+)?access\s+control", re.IGNORECASE),
        re.compile(r"bypass\s+auth", re.IGNORECASE),
    ],
    "credential_exposure": [
        re.compile(r"API_KEY\s*=\s*\S+", re.IGNORECASE),
        re.compile(r"DB_PASSWORD\s*=\s*\S+", re.IGNORECASE),
        re.compile(r"ADMIN_TOKEN\s*=\s*\S+", re.IGNORECASE),
        re.compile(r"sk-prod-[a-zA-Z0-9]+"),
        re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
        re.compile(r"(?:password|passwd|pwd)\s*[=:]\s*\S+", re.IGNORECASE),
        re.compile(r"SECRET_KEY\s*=\s*\S+", re.IGNORECASE),
        re.compile(r"(?:access_token|auth_token)\s*=\s*\S+", re.IGNORECASE),
    ],
    "malicious_redirect": [
        re.compile(r"https?://[^\s]*(?:exfil|malicious|attacker|steal)[^\s]*", re.IGNORECASE),
        re.compile(r"\?ref=malicious", re.IGNORECASE),
    ],
    "fabricated_authority": [
        # Specific expert at institution (Dr./Prof. FirstName LastName from/at Institution)
        re.compile(
            r"(?:dr\.?|prof\.?|professor)\s+\w+\s+\w+"
            r"(?:\s*,\s*[\w\s]+)?"
            r"\s+(?:from|at|of)\s+"
            r"(?:MIT|Stanford|Harvard|Johns\s+Hopkins|Mayo\s+Clinic|Goldman\s+Sachs|"
            r"Gartner|McKinsey|Forrester|NIST|Oxford|Cambridge|Yale|Princeton|"
            r"WHO|FDA|CDC|NIH|IEEE|ACM|Deloitte|BCG|Bain|JPMorgan|Morgan\s+Stanley)",
            re.IGNORECASE,
        ),
        # "according to Dr./Prof. FirstName LastName" (no institution needed)
        re.compile(
            r"according\s+to\s+(?:dr\.?|prof\.?|professor)\s+\w+\s+\w+",
            re.IGNORECASE,
        ),
        # Prof Name (Institution, Year) parenthetical
        re.compile(
            r"(?:prof\.?|professor|dr\.?)\s+\w+\s+\w+\s*\(\s*"
            r"(?:MIT|Stanford|Harvard|Johns\s+Hopkins|Mayo\s+Clinic|Oxford|Cambridge|Yale|Princeton)",
            re.IGNORECASE,
        ),
        # Firm analyst/expert Name pattern (e.g. "Gartner analyst John Smith")
        re.compile(
            r"(?:Gartner|McKinsey|Goldman\s+Sachs|Forrester|Deloitte|BCG|Bain|JPMorgan|Morgan\s+Stanley)"
            r"(?:'s)?\s+(?:analyst|expert|researcher|director|partner|strategist)\s+\w+\s+\w+",
            re.IGNORECASE,
        ),
        # analyst/expert Name from/at firm
        re.compile(
            r"(?:analyst|expert|researcher|officer|director|strategist)\s+\w+\s+\w+"
            r"\s+(?:from|at|of)\s+"
            r"(?:Gartner|McKinsey|Goldman\s+Sachs|Forrester|MIT|Stanford|Harvard|NIST|Deloitte)",
            re.IGNORECASE,
        ),
        # Celebrity/famous person quote fabrication
        re.compile(
            r"(?:according\s+to|stated?\s+by|says)\s+"
            r"(?:Warren\s+Buffett|Elon\s+Musk|Jeff\s+Bezos|Mark\s+Zuckerberg|Tim\s+Cook|Bill\s+Gates|"
            r"Jamie\s+Dimon|Larry\s+Fink|Ray\s+Dalio|Janet\s+Yellen)",
            re.IGNORECASE,
        ),
        # Percentage claims with superlative metrics
        re.compile(
            r"(?:99\.9{1,3}|100)\s*%\s*(?:uptime|accuracy|success|reliability|"
            r"satisfaction|effective|proven|guaranteed|certified|compliance)",
            re.IGNORECASE,
        ),
        # Institution claims without specific expert
        re.compile(
            r"(?:study|research|report|analysis|paper)\s+(?:by|from|at|published\s+by)\s+"
            r"(?:MIT|Stanford|Harvard|Johns\s+Hopkins|Mayo\s+Clinic|Goldman\s+Sachs|"
            r"Gartner|McKinsey|Forrester|NIST|Oxford|Cambridge|Yale|Princeton|"
            r"WHO|FDA|CDC|NIH|IEEE|ACM)",
            re.IGNORECASE,
        ),
        # Claims with "scientifically proven" or "clinically proven"
        re.compile(
            r"(?:scientifically|clinically|medically)\s+(?:proven|verified|validated|confirmed)",
            re.IGNORECASE,
        ),
        # Endorsement by fabricated authority
        re.compile(
            r"(?:endorsed|recommended|approved|certified)\s+by\s+"
            r"(?:the\s+)?(?:board|committee|council|association|institute|foundation)",
            re.IGNORECASE,
        ),
        # Contact info for fake expert
        re.compile(
            r"contact\s+(?:dr\.?|prof\.?|professor)\s+\w+\s+\w+\s+at\s+(?:extension|ext\.?|phone|\d)",
            re.IGNORECASE,
        ),
    ],
    "hidden_content": [
        re.compile(r"\[HIDDEN:?\s*[^\]]*\]", re.IGNORECASE),
        re.compile(r"INSTRUCTION_OVERRIDE", re.IGNORECASE),
        re.compile(r"<!--\s*(?:inject|override|system|admin)", re.IGNORECASE),
        re.compile(r"\[CONFIDENTIAL\s*(?:OVERRIDE|INSTRUCTION)\]", re.IGNORECASE),
        re.compile(r"<\s*(?:hidden|invisible|secret)\s*>", re.IGNORECASE),
    ],
    "fabricated_citation": [
        # Fake case law
        re.compile(
            r"(?:v\.\s+\w+.*?\d{4}|Case\s+No\.\s*\d+[-/]\d+)",
            re.IGNORECASE,
        ),
        # Fake regulatory references
        re.compile(
            r"(?:SEC|FTC|EPA|OSHA)\s+(?:ruling|regulation|directive|order)\s+(?:No\.\s*)?\d+",
            re.IGNORECASE,
        ),
        # Fake DOI or paper references
        re.compile(
            r"doi:\s*10\.\d{4,}/[^\s]+",
            re.IGNORECASE,
        ),
    ],
    "dangerous_advice": [
        # Medical cure claims
        re.compile(
            r"(?:cure|treat|heal|remedy)\s+(?:for\s+)?(?:cancer|diabetes|HIV|AIDS|autism|"
            r"alzheimer|depression|anxiety|ADHD)",
            re.IGNORECASE,
        ),
        # Financial guarantee claims
        re.compile(
            r"(?:guaranteed|risk[- ]?free)\s+(?:return|profit|income|investment)",
            re.IGNORECASE,
        ),
        # Dangerous substance/action instructions
        re.compile(
            r"(?:mix|combine|ingest|inject|consume)\s+(?:\w+\s+){0,3}"
            r"(?:bleach|chlorine|ammonia|mercury|cyanide)",
            re.IGNORECASE,
        ),
    ],
}


class DifyRagPoisoningDetector(TurnAwareDetector):
    """Detects prompt injection payloads in Dify knowledge retrieval outputs.

    Scans knowledge_retrieval node documents for injection patterns and
    checks if downstream LLM nodes reproduce injected content, indicating
    successful poisoning.
    """

    name = "DifyRagPoisoningDetector"
    version = "1.1"
    supported_failure_modes = ["F6"]  # Prompt injection

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Delegate to detect_workflow_run if metadata contains workflow_run."""
        workflow_run = (conversation_metadata or {}).get("workflow_run", {})
        if workflow_run:
            return self.detect_workflow_run(workflow_run)
        return TurnAwareDetectionResult(
            detected=False,
            severity=TurnAwareSeverity.NONE,
            confidence=0.0,
            failure_mode=None,
            explanation="No workflow_run data provided",
            detector_name=self.name,
        )

    def detect_workflow_run(self, workflow_run: dict) -> TurnAwareDetectionResult:
        """Analyze Dify workflow run for RAG poisoning.

        Args:
            workflow_run: Dify workflow_run dict with nodes list.

        Returns:
            Detection result with injection findings.
        """
        nodes = workflow_run.get("nodes", [])
        if not nodes:
            return self._no_detection("No nodes in workflow run")

        # Find knowledge_retrieval nodes and LLM nodes
        retrieval_nodes = [n for n in nodes if n.get("node_type") == "knowledge_retrieval"]
        llm_nodes = [n for n in nodes if n.get("node_type") == "llm"]

        if not retrieval_nodes:
            return self._no_detection("No knowledge_retrieval nodes found")

        issues: List[Dict[str, Any]] = []
        affected_node_ids: List[str] = []
        pattern_count = 0

        for node in retrieval_nodes:
            node_id = node.get("node_id", "unknown")
            outputs = node.get("outputs", {})
            documents = outputs.get("documents", [])

            for doc_idx, doc in enumerate(documents):
                content = doc.get("content", "") if isinstance(doc, dict) else str(doc)
                found_patterns = self._scan_for_injections(content)

                if found_patterns:
                    pattern_count += len(found_patterns)
                    affected_node_ids.append(node_id)
                    issues.append({
                        "type": "rag_injection",
                        "node_id": node_id,
                        "node_title": node.get("title", ""),
                        "document_index": doc_idx,
                        "patterns_found": found_patterns,
                        "content_preview": content[:200],
                    })

        # Check if downstream LLM echoes injected content
        if issues:
            echo_issues = self._check_llm_echo(issues, llm_nodes)
            issues.extend(echo_issues)
            for ei in echo_issues:
                affected_node_ids.append(ei.get("llm_node_id", ""))

        if not issues:
            return self._no_detection("No injection patterns in retrieved documents")

        # Confidence: 0.6 base + 0.1 per pattern, max 0.95
        confidence = min(0.95, 0.6 + pattern_count * 0.1)

        has_echo = any(i.get("type") == "llm_echo" for i in issues)
        if has_echo:
            severity = TurnAwareSeverity.SEVERE
        elif pattern_count >= 3:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F6",
            explanation=(
                f"RAG poisoning: {pattern_count} injection pattern(s) found in "
                f"{len(retrieval_nodes)} retrieval node(s)"
                + ("; LLM echoed injected content" if has_echo else "")
            ),
            affected_turns=list(range(len(affected_node_ids))),
            evidence={
                "issues": issues,
                "total_retrieval_nodes": len(retrieval_nodes),
                "pattern_count": pattern_count,
                "llm_echo_detected": has_echo,
            },
            suggested_fix=(
                "Sanitize retrieved documents before passing to LLM nodes. "
                "Add content filtering between knowledge_retrieval and llm nodes. "
                "Consider using Dify's sensitive word filter or a guardrail node."
            ),
            detector_name=self.name,
        )

    def _scan_for_injections(self, content: str) -> List[Dict[str, str]]:
        """Scan text for injection patterns. Returns list of matches."""
        found = []
        for category, patterns in INJECTION_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(content)
                if match:
                    found.append({
                        "category": category,
                        "matched": match.group(),
                        "position": match.start(),
                    })
        return found

    def _check_llm_echo(
        self,
        injection_issues: List[Dict[str, Any]],
        llm_nodes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Check if LLM nodes echo injected patterns in their outputs."""
        echo_issues = []
        # Collect unique matched strings from injections
        injected_strings = set()
        for issue in injection_issues:
            for pat in issue.get("patterns_found", []):
                injected_strings.add(pat["matched"].lower())

        for llm_node in llm_nodes:
            llm_output = str(llm_node.get("outputs", {}))
            llm_output_lower = llm_output.lower()
            echoed = [s for s in injected_strings if s in llm_output_lower]
            if echoed:
                echo_issues.append({
                    "type": "llm_echo",
                    "llm_node_id": llm_node.get("node_id", ""),
                    "llm_node_title": llm_node.get("title", ""),
                    "echoed_patterns": echoed,
                    "output_preview": llm_output[:200],
                })
        return echo_issues

    def _no_detection(self, reason: str) -> TurnAwareDetectionResult:
        return TurnAwareDetectionResult(
            detected=False,
            severity=TurnAwareSeverity.NONE,
            confidence=0.0,
            failure_mode=None,
            explanation=reason,
            detector_name=self.name,
        )
