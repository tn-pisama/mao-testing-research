"""
Model Fingerprint - Detects model version changes.

Identifies when underlying models have been updated,
which may cause behavioral changes in agents.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelFingerprint:
    model_id: str
    version: Optional[str]
    provider: str
    fingerprint_hash: str
    detected_at: datetime
    
    context_window: Optional[int] = None
    known_cutoff: Optional[str] = None
    
    is_preview: bool = False
    is_deprecated: bool = False


class ModelFingerprinter:
    """
    Detects and tracks model versions across providers.
    """
    
    MODEL_PATTERNS = {
        "openai": {
            "gpt-4o": r"gpt-4o(-\d{4}-\d{2}-\d{2})?",
            "gpt-4-turbo": r"gpt-4-turbo(-\d{4}-\d{2}-\d{2})?(-preview)?",
            "gpt-4": r"gpt-4(-\d{4})?(-\d{2}-\d{2})?",
            "gpt-3.5-turbo": r"gpt-3\.5-turbo(-\d{4})?(-\d{2}-\d{2})?",
            "o1": r"o1(-preview|-mini)?",
        },
        "anthropic": {
            "claude-3-opus": r"claude-3-opus(-\d{8})?",
            "claude-3-sonnet": r"claude-3(-\d+)?-sonnet(-\d{8})?",
            "claude-3-haiku": r"claude-3(-\d+)?-haiku(-\d{8})?",
            "claude-opus-4": r"claude-opus-4(-\d+)?",
        },
        "google": {
            "gemini-pro": r"gemini-(\d+\.?\d*)-pro(-\d+)?",
            "gemini-flash": r"gemini-(\d+\.?\d*)-flash(-\d+)?",
        },
    }
    
    KNOWN_VERSIONS = {
        "gpt-4o-2024-08-06": {"context": 128000, "cutoff": "Oct 2023"},
        "gpt-4o-2024-11-20": {"context": 128000, "cutoff": "Oct 2023"},
        "gpt-4-turbo-2024-04-09": {"context": 128000, "cutoff": "Dec 2023"},
        "claude-3-opus-20240229": {"context": 200000, "cutoff": "Aug 2023"},
        "claude-3-5-sonnet-20241022": {"context": 200000, "cutoff": "Apr 2024"},
        "claude-opus-4-20250514": {"context": 200000, "cutoff": "Jan 2025"},
    }

    def __init__(self):
        self.known_fingerprints: dict[str, ModelFingerprint] = {}
        self.version_history: list[tuple[str, str, datetime]] = []

    def fingerprint(self, model_id: str) -> ModelFingerprint:
        provider = self._detect_provider(model_id)
        version = self._extract_version(model_id)
        
        fingerprint_hash = hashlib.sha256(
            f"{model_id}:{version or 'latest'}".encode()
        ).hexdigest()[:16]
        
        known = self.KNOWN_VERSIONS.get(model_id, {})
        
        fp = ModelFingerprint(
            model_id=model_id,
            version=version,
            provider=provider,
            fingerprint_hash=fingerprint_hash,
            detected_at=datetime.utcnow(),
            context_window=known.get("context"),
            known_cutoff=known.get("cutoff"),
            is_preview="preview" in model_id.lower(),
            is_deprecated=self._is_deprecated(model_id),
        )
        
        self.known_fingerprints[model_id] = fp
        return fp

    def _detect_provider(self, model_id: str) -> str:
        model_lower = model_id.lower()
        
        if "gpt" in model_lower or "o1" in model_lower:
            return "openai"
        if "claude" in model_lower:
            return "anthropic"
        if "gemini" in model_lower:
            return "google"
        if "llama" in model_lower:
            return "meta"
        if "mistral" in model_lower or "mixtral" in model_lower:
            return "mistral"
        
        return "unknown"

    def _extract_version(self, model_id: str) -> Optional[str]:
        date_pattern = r"(\d{4}-\d{2}-\d{2}|\d{8})"
        match = re.search(date_pattern, model_id)
        if match:
            return match.group(1)
        
        version_pattern = r"-(\d+(\.\d+)?)"
        match = re.search(version_pattern, model_id)
        if match:
            return match.group(1)
        
        return None

    def _is_deprecated(self, model_id: str) -> bool:
        deprecated = [
            "gpt-4-0314", "gpt-4-0613",
            "gpt-3.5-turbo-0301", "gpt-3.5-turbo-0613",
            "claude-2", "claude-instant",
        ]
        return any(d in model_id for d in deprecated)

    def detect_version_change(
        self,
        model_id: str,
        previous_fingerprint: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        current = self.fingerprint(model_id)
        
        if previous_fingerprint:
            if current.fingerprint_hash != previous_fingerprint:
                self.version_history.append(
                    (model_id, current.fingerprint_hash, datetime.utcnow())
                )
                return True, f"Model version changed: {previous_fingerprint} -> {current.fingerprint_hash}"
        
        if model_id in self.known_fingerprints:
            stored = self.known_fingerprints[model_id]
            if stored.fingerprint_hash != current.fingerprint_hash:
                return True, f"Model {model_id} has been updated"
        
        return False, None

    def get_version_history(self, model_id: Optional[str] = None) -> list[tuple[str, str, datetime]]:
        if model_id:
            return [(m, h, t) for m, h, t in self.version_history if m == model_id]
        return self.version_history

    def compare_models(self, model_a: str, model_b: str) -> dict:
        fp_a = self.fingerprint(model_a)
        fp_b = self.fingerprint(model_b)
        
        return {
            "same_provider": fp_a.provider == fp_b.provider,
            "same_family": self._same_family(model_a, model_b),
            "version_a": fp_a.version,
            "version_b": fp_b.version,
            "context_diff": (fp_a.context_window or 0) - (fp_b.context_window or 0),
            "a_newer": self._is_newer(fp_a, fp_b),
        }

    def _same_family(self, model_a: str, model_b: str) -> bool:
        families = ["gpt-4", "gpt-3.5", "claude-3", "claude-opus", "gemini"]
        for family in families:
            if family in model_a.lower() and family in model_b.lower():
                return True
        return False

    def _is_newer(self, fp_a: ModelFingerprint, fp_b: ModelFingerprint) -> Optional[bool]:
        if fp_a.version and fp_b.version:
            return fp_a.version > fp_b.version
        return None


model_fingerprinter = ModelFingerprinter()
