"""Tests for webhook security utilities (webhook_security.py).

Covers: HMAC signature verification, instance URL validation (SSRF protection),
sensitive data redaction, state hash computation, API key hashing.
"""
import hashlib
import hmac as hmac_mod
import time

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from app.core.webhook_security import (
    verify_webhook_signature,
    validate_instance_url,
    redact_sensitive_data,
    compute_state_hash,
    hash_api_key,
)


# ===================================================================
# verify_webhook_signature
# ===================================================================

class TestVerifyWebhookSignature:

    def _compute_valid_signature(self, payload: bytes, secret: str, timestamp: str) -> str:
        """Compute the expected HMAC-SHA256 signature for a payload."""
        message = f"{timestamp}.{payload.decode()}"
        digest = hmac_mod.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def test_valid_signature(self):
        """Valid HMAC signature and fresh timestamp passes."""
        now = str(int(time.time()))
        payload = b'{"event": "test"}'
        secret = "webhook-secret-42"
        sig = self._compute_valid_signature(payload, secret, now)

        result = verify_webhook_signature(payload, sig, secret, now)
        assert result is True

    def test_invalid_timestamp_format(self):
        """Non-numeric timestamp raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(b"{}", "sha256=abc", "s", "not-a-number")
        assert exc_info.value.status_code == 401
        assert "timestamp" in exc_info.value.detail.lower()

    def test_expired_timestamp(self):
        """Timestamp older than 30 seconds raises 401."""
        old_ts = str(int(time.time()) - 60)
        payload = b'{"data": 1}'
        secret = "sec"
        sig = self._compute_valid_signature(payload, secret, old_ts)

        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(payload, sig, secret, old_ts)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_wrong_signature(self):
        """Incorrect signature raises 401."""
        now = str(int(time.time()))
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(b'{"ok": true}', "sha256=deadbeef", "sec", now)
        assert exc_info.value.status_code == 401
        assert "signature" in exc_info.value.detail.lower()

    def test_signature_format_sha256_prefix(self):
        """Signature must include the sha256= prefix to match."""
        now = str(int(time.time()))
        payload = b'{"x": 1}'
        secret = "s"
        sig = self._compute_valid_signature(payload, secret, now)
        # Ensure the prefix is present in our computed sig
        assert sig.startswith("sha256=")

        # Passing the raw hex without prefix should fail
        raw_hex = sig.replace("sha256=", "")
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(payload, raw_hex, secret, now)
        assert exc_info.value.status_code == 401


# ===================================================================
# validate_instance_url
# ===================================================================

class TestValidateInstanceUrl:

    def test_accepts_valid_https_url(self):
        result = validate_instance_url("https://my-instance.example.com/api")
        assert result == "https://my-instance.example.com/api"

    def test_accepts_valid_http_url(self):
        result = validate_instance_url("http://provider.example.com:8080")
        assert result == "http://provider.example.com:8080"

    def test_rejects_empty_url(self):
        with pytest.raises(ValueError, match="required"):
            validate_instance_url("")

    def test_rejects_localhost(self):
        with pytest.raises(ValueError):
            validate_instance_url("http://localhost:8080")

    def test_rejects_127_0_0_1(self):
        with pytest.raises(ValueError):
            validate_instance_url("http://127.0.0.1/admin")

    def test_rejects_private_ip_10(self):
        with pytest.raises(ValueError, match="Private"):
            validate_instance_url("http://10.0.0.1/api")

    def test_rejects_private_ip_192_168(self):
        with pytest.raises(ValueError, match="Private"):
            validate_instance_url("http://192.168.1.1/api")

    @pytest.mark.parametrize("port", [22, 3306, 5432])
    def test_rejects_blocked_ports(self, port):
        with pytest.raises(ValueError, match="not allowed"):
            validate_instance_url(f"http://example.com:{port}/api")

    def test_rejects_internal_domain(self):
        with pytest.raises(ValueError, match="Internal"):
            validate_instance_url("https://service.internal/api")

    def test_rejects_local_domain(self):
        with pytest.raises(ValueError, match="Internal"):
            validate_instance_url("https://printer.local/api")


# ===================================================================
# redact_sensitive_data
# ===================================================================

class TestRedactSensitiveData:

    def test_redacts_email_addresses(self):
        data = {"contact": "admin@example.com", "role": "owner"}
        result = redact_sensitive_data(data)
        assert result["contact"] == "[REDACTED]"
        assert result["role"] == "owner"

    def test_redacts_api_keys(self):
        keys = {
            "openai": "sk-" + "a" * 40,
            "xai": "xai-" + "b" * 40,
            "google": "AIza" + "c" * 35,
            "github": "ghp_" + "d" * 36,
        }
        result = redact_sensitive_data(keys)
        for key, val in result.items():
            assert val == "[REDACTED]", f"Expected redaction for {key}, got {val}"

    def test_handles_nested_dicts(self):
        data = {
            "outer": "safe",
            "nested": {
                "email": "secret@corp.io",
                "value": 42,
            },
        }
        result = redact_sensitive_data(data)
        assert result["nested"]["email"] == "[REDACTED]"
        assert result["nested"]["value"] == 42

    def test_skip_keys_parameter(self):
        data = {"prompt": "contact admin@example.com", "note": "admin@example.com"}
        result = redact_sensitive_data(data, skip_keys=["prompt"])
        # Skipped key preserves original value
        assert "admin@example.com" in result["prompt"]
        # Non-skipped key is redacted
        assert result["note"] == "[REDACTED]"

    def test_non_dict_input_returned_as_is(self):
        assert redact_sensitive_data("plain string") == "plain string"
        assert redact_sensitive_data(42) == 42
        assert redact_sensitive_data(None) is None


# ===================================================================
# compute_state_hash
# ===================================================================

class TestComputeStateHash:

    def test_deterministic_output(self):
        state = {"agent_id": "a1", "status": "running", "step": 3}
        hash1 = compute_state_hash(state)
        hash2 = compute_state_hash(state)
        assert hash1 == hash2

    def test_different_inputs_differ(self):
        hash1 = compute_state_hash({"key": "value1"})
        hash2 = compute_state_hash({"key": "value2"})
        assert hash1 != hash2

    def test_returns_16_char_hex(self):
        h = compute_state_hash({"a": 1})
        assert len(h) == 16
        # Must be valid hex
        int(h, 16)


# ===================================================================
# hash_api_key
# ===================================================================

class TestHashApiKey:

    def test_returns_sha256_hex_digest(self):
        key = "my-secret-api-key"
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert hash_api_key(key) == expected

    def test_deterministic(self):
        assert hash_api_key("same") == hash_api_key("same")
        assert hash_api_key("a") != hash_api_key("b")
