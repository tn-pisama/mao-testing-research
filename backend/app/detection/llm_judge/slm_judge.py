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

    Three modes:
    1. Trained LoRA: Load the fine-tuned QLoRA adapter (70% accuracy, $0/judgment)
    2. HuggingFace: Load a full fine-tuned model from disk/hub
    3. Mock: Use rule-based logic for testing (no model needed)

    Auto-detection: checks for trained model at models/pisama-slm-judge-v1/
    """

    DEFAULT_MODEL_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "models", "pisama-slm-judge-v1"
    )

    # Modal endpoint for remote GPU inference
    REMOTE_ENDPOINT = os.environ.get(
        "SLM_JUDGE_URL",
        "https://tuomo--pisama-slm-serve-slmjudgeservice-judge.modal.run",
    )
    REMOTE_HEALTH = os.environ.get(
        "SLM_JUDGE_HEALTH_URL",
        "https://tuomo--pisama-slm-serve-slmjudgeservice-health.modal.run",
    )

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_name: str = "pisama-slm-judge-v1",
        use_mock: bool = False,  # Default to trying real model
        use_remote: bool = True,  # Prefer remote Modal endpoint
    ):
        self.model_name = model_name
        self.model_path = model_path or self.DEFAULT_MODEL_PATH
        self._model = None
        self._tokenizer = None
        self.use_remote = use_remote

        # Priority: remote > local model > mock
        if use_remote:
            self.use_mock = False
            logger.info("SLM judge: using remote Modal endpoint")
        elif os.path.exists(os.path.join(self.model_path, "adapter_config.json")):
            self.use_mock = False
            self.use_remote = False
            logger.info("SLM judge: found trained model at %s", self.model_path)
        else:
            self.use_mock = use_mock if use_mock else True
            self.use_remote = False
            logger.info("SLM judge: no trained model found, using mock mode")

    def _load_model(self):
        """Load the fine-tuned SLM from disk (LoRA or full model)."""
        if self.use_mock or not self.model_path:
            return

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            adapter_config = os.path.join(self.model_path, "adapter_config.json")
            is_lora = os.path.exists(adapter_config)

            if is_lora:
                # Load LoRA adapter on top of base model
                with open(adapter_config) as f:
                    import json
                    config = json.load(f)
                base_model_name = config.get("base_model_name_or_path", "Qwen/Qwen2.5-3B-Instruct")

                logger.info("Loading base model %s with LoRA adapter...", base_model_name)
                from peft import PeftModel

                base = AutoModelForCausalLM.from_pretrained(
                    base_model_name,
                    torch_dtype=torch.float16,
                    device_map="auto",
                    trust_remote_code=True,
                )
                self._model = PeftModel.from_pretrained(base, self.model_path)
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
            else:
                # Load full model
                self._model = AutoModelForCausalLM.from_pretrained(
                    self.model_path, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True,
                )
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)

            self._model.eval()
            logger.info("SLM judge loaded: %s (LoRA=%s)", self.model_path, is_lora)
        except Exception as e:
            logger.warning("Failed to load SLM judge: %s. Falling back to mock.", e)
            self.use_mock = True

    def _remote_judge(self, detection_type: str, input_text: str) -> SLMVerdict:
        """Call the remote Modal GPU endpoint for inference."""
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "detection_type": detection_type,
            "text": input_text[:400],
        }).encode()

        req = urllib.request.Request(
            self.REMOTE_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                return SLMVerdict(
                    detected=result.get("detected", False),
                    confidence=result.get("confidence", 0.15),
                    model_name=result.get("model", self.model_name),
                )
        except (urllib.error.URLError, TimeoutError, Exception) as e:
            logger.warning("Remote SLM call failed: %s. Falling back to mock.", e)
            return self._mock_judge(detection_type, input_text)

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
        elif self.use_remote:
            verdict = self._remote_judge(detection_type, input_text)
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
        """Real model inference using the trained LoRA model."""
        if self._model is None:
            self._load_model()
        if self._model is None:
            return self._mock_judge(detection_type, input_text)

        import torch

        # Format as chat prompt (same format as training)
        prompt = (
            f"<|im_start|>system\nYou are a failure detection judge for multi-agent AI systems. "
            f"Answer YES if the data shows a failure, NO if it's normal behavior.<|im_end|>\n"
            f"<|im_start|>user\nIs this a {detection_type} failure? Analyze the data and answer YES or NO.\n\n"
            f"{input_text[:400]}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=480)
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs, max_new_tokens=5, do_sample=False,
                pad_token_id=self._tokenizer.pad_token_id or self._tokenizer.eos_token_id,
            )

        response = self._tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        ).strip().upper()

        detected = "YES" in response
        confidence = 0.85 if detected else 0.15  # Binary output, fixed confidence

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
