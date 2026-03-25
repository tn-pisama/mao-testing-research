"""Fix generators for grounding detections (ungrounded claims)."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class GroundingFixGenerator(BaseFixGenerator):
    """Generates fixes for grounding detections — output claims not supported by sources."""

    def can_handle(self, detection_type: str) -> bool:
        return detection_type == "grounding"

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._source_citation_fix(detection_id, details, context))
        fixes.append(self._retrieval_augmentation_fix(detection_id, details, context))
        fixes.append(self._claim_extraction_fix(detection_id, details, context))

        return fixes

    def _source_citation_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="grounding",
            fix_type=FixType.SOURCE_GROUNDING,
            confidence=FixConfidence.HIGH,
            title="Add mandatory source citation to agent output",
            description=(
                "Require the agent to cite specific source documents for every factual "
                "claim. Add a post-processing step that strips uncited claims and appends "
                "a 'Sources' section with document references."
            ),
            rationale=(
                "Ungrounded claims occur when the agent generates text without anchoring "
                "it to retrieved documents. Mandatory citation forces the agent to link "
                "each claim to a source, making hallucinated content immediately visible."
            ),
            code_changes=[CodeChange(original_code=None,
                file_path="agent_config.py",
                language="python",
                suggested_code="""+ # Grounding fix: require source citations
+ SYSTEM_PROMPT += \"\"\"
+ IMPORTANT: Every factual claim in your response MUST cite its source.
+ Use [Source N] format. If you cannot cite a source for a claim, do not include it.
+ End your response with a Sources section listing all referenced documents.
+ \"\"\"
""",
            )],
            estimated_impact="Eliminates uncited claims; may reduce response fluency slightly",
            breaking_changes=False,
            requires_testing=True,
            tags=["grounding", "citation", "source_anchoring"],
        )

    def _retrieval_augmentation_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="grounding",
            fix_type=FixType.SOURCE_GROUNDING,
            confidence=FixConfidence.MEDIUM,
            title="Add retrieval step before generation",
            description=(
                "Insert a retrieval-augmented generation (RAG) step that fetches relevant "
                "documents before the agent generates output. The agent's context window "
                "is populated with source material, reducing the chance of fabrication."
            ),
            rationale=(
                "Agents hallucinate when they lack source material in context. "
                "Pre-populating with relevant documents gives the agent real content "
                "to ground its claims against."
            ),
            code_changes=[CodeChange(original_code=None,
                file_path="pipeline.py",
                language="python",
                suggested_code="""+ # Grounding fix: add retrieval step
+ from retrieval import search_documents
+
+ def augmented_generate(query, agent):
+     docs = search_documents(query, top_k=5)
+     context = "\\n".join(f"[Source {i+1}]: {d.content}" for i, d in enumerate(docs))
+     return agent.generate(query, context=context)
""",
            )],
            estimated_impact="Significantly reduces ungrounded claims; adds retrieval latency",
            breaking_changes=False,
            requires_testing=True,
            tags=["grounding", "rag", "retrieval"],
        )

    def _claim_extraction_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="grounding",
            fix_type=FixType.FACT_CHECKING,
            confidence=FixConfidence.MEDIUM,
            title="Post-generation claim verification against sources",
            description=(
                "After the agent generates output, extract all factual claims and verify "
                "each against the source documents using NLI entailment checking. "
                "Remove or flag claims that are not entailed by any source."
            ),
            rationale=(
                "Even with source material in context, agents can still generate claims "
                "not supported by the sources. Post-generation verification catches these "
                "using the same NLI model (DeBERTa-v3-MNLI) used in Pisama detection."
            ),
            code_changes=[CodeChange(original_code=None,
                file_path="post_process.py",
                language="python",
                suggested_code="""+ # Grounding fix: verify claims against sources
+ from pisama.detection.nli_checker import check_entailment
+
+ def verify_claims(output, sources):
+     sentences = output.split('.')
+     verified = []
+     for sent in sentences:
+         if len(sent.strip()) < 10:
+             verified.append(sent)
+             continue
+         source_text = ' '.join(s[:500] for s in sources)
+         label, conf = check_entailment(source_text, sent.strip())
+         if label == 'entailment' or conf < 0.5:
+             verified.append(sent)
+         else:
+             verified.append(f'[UNVERIFIED] {sent}')
+     return '.'.join(verified)
""",
            )],
            estimated_impact="High precision ungrounded claim detection; adds ~50ms per sentence",
            breaking_changes=False,
            requires_testing=True,
            tags=["grounding", "nli", "post_verification"],
        )
