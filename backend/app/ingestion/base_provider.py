"""Base class for provider parsers.

Extracts shared logic from N8nParser, OpenClawParser, and DifyParser:
- Datetime parsing (ISO 8601 with Z-suffix handling)
- Redaction + content filtering pipeline
- State hash computation
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.webhook_security import redact_sensitive_data, compute_state_hash
from app.ingestion.content_filter import strip_content_fields


class BaseProviderParser(ABC):
    """Abstract base for provider-specific parsers.

    Subclasses implement ``parse_raw()`` to convert provider webhook payloads
    into a provider-specific execution dataclass, and ``extract_states()``
    to turn that execution into a list of state dataclass instances.

    Shared utilities (datetime parsing, redaction, hashing) live here so
    they aren't copy-pasted across parsers.
    """

    @abstractmethod
    def parse_raw(self, raw_data: Dict[str, Any]) -> Any:
        """Parse a raw webhook payload into a structured execution/session object."""
        ...

    @abstractmethod
    def extract_states(self, execution: Any, tenant_id: str, ingestion_mode: str = "full") -> List[Any]:
        """Convert a parsed execution into a list of state records."""
        ...

    # ------------------------------------------------------------------
    # Shared utilities
    # ------------------------------------------------------------------

    def _parse_datetime(self, dt_str: Optional[str]) -> datetime:
        """Parse an ISO 8601 datetime string, handling Z-suffix and errors."""
        if not dt_str:
            return datetime.utcnow()
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError):
            return datetime.utcnow()

    def _redact_and_filter(
        self,
        state_delta: dict,
        skip_keys: Optional[List[str]] = None,
        content_keys: Optional[List[str]] = None,
        ingestion_mode: str = "full",
    ) -> dict:
        """Apply redaction and optional content stripping.

        Args:
            state_delta: Raw state data to process.
            skip_keys: Keys whose values should NOT be redacted
                       (e.g., prompts that are intentionally stored).
            content_keys: Keys to strip when ``ingestion_mode == "trace_only"``.
            ingestion_mode: "full" keeps everything, "trace_only" strips content.

        Returns:
            Processed state_delta dict.
        """
        result = redact_sensitive_data(state_delta, skip_keys=skip_keys)

        if ingestion_mode == "trace_only" and content_keys:
            result = strip_content_fields(result, content_keys=content_keys)

        return result

    @staticmethod
    def _compute_hash(state_delta: dict) -> str:
        """Compute a deterministic hash of a state delta."""
        return compute_state_hash(state_delta)
