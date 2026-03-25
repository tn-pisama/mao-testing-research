"""SLM Judge — Distilled Detection using Small Language Models.

Interface for a fine-tuned 3B model (Phi-3-mini, Llama-3.2-3B) that
makes detection judgments at 90% cost reduction vs Claude.

This file defines the interface and data export. Actual model training
requires the exported training data + fine-tuning script.

Cost comparison:
- Claude Haiku 4.5: $1/1M input tokens
- Local 3B SLM: $0 after training (inference on CPU/GPU)
- Savings: 90-100% on Tier 1/2 judgments
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SLMVerdict:
    """Result from the SLM judge."""
    detected: bool
    confidence: float
    model_name: str
    latency_ms: int = 0


class SLMJudge:
    """Small Language Model judge for cost-effective detection.

    Interface matches the existing LLM judge API so it can be used
    as a drop-in replacement for Tier 1/2 judgments.

    Two modes:
    1. HuggingFace: Load a fine-tuned model from disk/hub
    2. Mock: Use rule-based logic for testing (no model needed)
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_name: str = "pisama-slm-judge-v1",
        use_mock: bool = True,
    ):
        self.model_name = model_name
        self.model_path = model_path
        self._model = None
        self._tokenizer = None
        self.use_mock = use_mock

    def _load_model(self):
        """Load the fine-tuned SLM from disk."""
        if self.use_mock or not self.model_path:
            return

        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_path)
            self._model.eval()
            logger.info("SLM judge loaded: %s", self.model_path)
        except Exception as e:
            logger.warning("Failed to load SLM judge: %s. Falling back to mock.", e)
            self.use_mock = True

    def judge(
        self,
        detection_type: str,
        input_text: str,
    ) -> SLMVerdict:
        """Run SLM judgment on input text.

        Args:
            detection_type: What failure to check for
            input_text: Formatted input (prompt + trace data)

        Returns:
            SLMVerdict with detected/confidence
        """
        import time
        start = time.monotonic()

        if self.use_mock:
            verdict = self._mock_judge(detection_type, input_text)
        else:
            verdict = self._model_judge(detection_type, input_text)

        verdict.latency_ms = int((time.monotonic() - start) * 1000)
        return verdict

    def _mock_judge(self, detection_type: str, input_text: str) -> SLMVerdict:
        """Mock judge using keyword heuristics (for testing without a model)."""
        text_lower = input_text.lower()

        # Simple keyword scoring per detection type
        scores = {
            "hallucination": ["fabricat", "unsupport", "no source", "made up", "incorrect"],
            "injection": ["ignore", "system prompt", "jailbreak", "dan", "override"],
            "loop": ["repeat", "identical", "same output", "stuck", "infinite"],
            "corruption": ["type change", "null", "missing field", "regression"],
            "derailment": ["off topic", "irrelevant", "unrelated", "recipe"],
        }

        keywords = scores.get(detection_type, [])
        matches = sum(1 for kw in keywords if kw in text_lower)
        confidence = min(1.0, matches * 0.25)
        detected = confidence > 0.4

        return SLMVerdict(
            detected=detected,
            confidence=round(confidence, 4),
            model_name=f"{self.model_name}-mock",
        )

    def _model_judge(self, detection_type: str, input_text: str) -> SLMVerdict:
        """Real model inference (requires loaded model)."""
        if self._model is None:
            self._load_model()
        if self._model is None:
            return self._mock_judge(detection_type, input_text)

        import torch

        inputs = self._tokenizer(
            input_text[:512],
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )

        with torch.no_grad():
            outputs = self._model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)[0]

        # Assume binary classification: [not_detected, detected]
        detected = probs[1].item() > 0.5
        confidence = probs[1].item() if detected else probs[0].item()

        return SLMVerdict(
            detected=detected,
            confidence=round(confidence, 4),
            model_name=self.model_name,
        )


def export_training_data(
    golden_data_path: str,
    output_path: str,
    max_text_length: int = 512,
) -> int:
    """Export golden dataset as SLM training data (JSONL format).

    Each line: {"text": "...", "label": 0/1, "detection_type": "...", "confidence": 0.X}

    Args:
        golden_data_path: Path to golden_dataset_external.json
        output_path: Path for output .jsonl file
        max_text_length: Max chars per training example

    Returns:
        Number of entries exported
    """
    with open(golden_data_path) as f:
        data = json.load(f)

    entries = data.get("entries", data) if isinstance(data, dict) else data
    exported = 0

    with open(output_path, "w") as out:
        for entry in entries:
            det_type = entry.get("detection_type", "")
            expected = entry.get("expected_detected", False)
            input_data = entry.get("input_data", {})

            # Format input as text
            text_parts = []
            text_parts.append(f"Detection type: {det_type}")
            for key, value in input_data.items():
                val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                text_parts.append(f"{key}: {val_str[:200]}")

            text = "\n".join(text_parts)[:max_text_length]

            out.write(json.dumps({
                "text": text,
                "label": 1 if expected else 0,
                "detection_type": det_type,
            }) + "\n")
            exported += 1

    logger.info("Exported %d training entries to %s", exported, output_path)
    return exported


# Singleton
slm_judge = SLMJudge()
