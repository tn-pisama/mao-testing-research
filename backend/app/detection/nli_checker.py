"""NLI-based entailment checking for hallucination and grounding detection.

Uses DeBERTa-v3-base-mnli to check if source documents entail output claims.
Framed as Natural Language Inference:
- Premise: source document
- Hypothesis: each output sentence
- Entailment = grounded, Contradiction = hallucination

Cost: $0 (runs locally, ~400MB model)
Latency: ~50ms per sentence pair
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

_nli_model = None
_nli_tokenizer = None


def get_nli_model():
    """Load DeBERTa-v3 NLI model (singleton)."""
    global _nli_model, _nli_tokenizer
    if _nli_model is not None:
        return _nli_model, _nli_tokenizer

    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    model_name = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-docnli-ling-2c"
    logger.info("Loading NLI model: %s", model_name)

    # use_fast=False required for Python 3.14 (fast tokenizer has vocab_file bug)
    _nli_tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
    _nli_model = AutoModelForSequenceClassification.from_pretrained(model_name)
    _nli_model.eval()

    return _nli_model, _nli_tokenizer


def check_entailment(premise: str, hypothesis: str) -> Tuple[str, float]:
    """Check if premise entails hypothesis.

    Returns:
        (label, confidence) where label is 'entailment', 'contradiction', or 'neutral'
    """
    import torch

    model, tokenizer = get_nli_model()

    inputs = tokenizer(
        premise[:512], hypothesis[:512],
        return_tensors="pt", truncation=True, max_length=512,
    )

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)[0]

    # Model labels: 0=entailment, 1=neutral, 2=contradiction
    labels = ["entailment", "neutral", "contradiction"]
    label_idx = probs.argmax().item()
    confidence = probs[label_idx].item()

    return labels[label_idx], confidence


def check_grounding(
    output: str,
    sources: List[str],
    threshold: float = 0.3,
) -> Tuple[bool, float, List[dict]]:
    """Check if output is grounded in source documents.

    Args:
        output: Agent output text
        sources: List of source document texts
        threshold: Fraction of ungrounded sentences to trigger detection

    Returns:
        (detected, confidence, details) where detected=True means hallucination found
    """
    # Split output into sentences
    sentences = [
        s.strip()
        for s in output.replace("\n", ". ").split(".")
        if len(s.strip()) > 10
    ]

    if not sentences or not sources:
        return False, 0.0, []

    # Combine sources, limit length
    source_text = " ".join(s[:500] for s in sources[:5])

    results = []
    ungrounded_count = 0

    for sent in sentences[:20]:  # Limit to 20 sentences
        label, conf = check_entailment(source_text, sent)

        is_grounded = label == "entailment"

        results.append({
            "sentence": sent[:100],
            "label": label,
            "confidence": conf,
            "grounded": is_grounded,
        })

        if not is_grounded:
            ungrounded_count += 1

    ungrounded_ratio = ungrounded_count / len(sentences) if sentences else 0
    detected = ungrounded_ratio > threshold
    confidence = min(1.0, ungrounded_ratio / threshold) if threshold > 0 else 0

    return detected, confidence, results
