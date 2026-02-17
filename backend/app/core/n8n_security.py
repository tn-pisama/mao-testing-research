"""Backward-compatibility shim. Use app.core.webhook_security instead."""

from app.core.webhook_security import *  # noqa: F401, F403
from app.core.webhook_security import (  # noqa: F401 — explicit re-exports
    verify_webhook_signature,
    validate_instance_url,
    validate_n8n_url,
    redact_sensitive_data,
    compute_state_hash,
    encrypt_api_key,
)
