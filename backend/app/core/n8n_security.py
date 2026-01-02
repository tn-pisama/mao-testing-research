import hmac
import hashlib
import time
import re
import urllib.parse
from ipaddress import ip_address, IPv4Address, IPv6Address
from typing import Optional
from fastapi import HTTPException

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}  # nosec B104 - blocking, not binding
BLOCKED_PORTS = {22, 25, 445, 3306, 5432, 6379, 27017}
TIMESTAMP_TOLERANCE_SECONDS = 30

SENSITIVE_PATTERNS = [
    re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    re.compile(r'\bsk-[a-zA-Z0-9]{32,}\b'),
    re.compile(r'\bxai-[a-zA-Z0-9]{32,}\b'),
    re.compile(r'\bAIza[a-zA-Z0-9_-]{35}\b'),
    re.compile(r'\bghp_[a-zA-Z0-9]{36}\b'),
]


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
    timestamp: str,
) -> bool:
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid timestamp format")
    
    if abs(time.time() - ts) > TIMESTAMP_TOLERANCE_SECONDS:
        raise HTTPException(status_code=401, detail="Webhook timestamp expired")
    
    message = f"{timestamp}.{payload.decode()}"
    expected = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, f"sha256={expected}"):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    return True


def validate_n8n_url(url: str) -> str:
    if not url:
        raise ValueError("n8n URL is required")
    
    parsed = urllib.parse.urlparse(url)
    
    if parsed.scheme not in ("https", "http"):
        raise ValueError("n8n URL must use HTTP or HTTPS")
    
    if not parsed.hostname:
        raise ValueError("Invalid n8n URL")
    
    hostname = parsed.hostname.lower()
    
    if hostname in BLOCKED_HOSTS:
        raise ValueError("Internal hosts not allowed")
    
    if hostname.endswith(".internal") or hostname.endswith(".local"):
        raise ValueError("Internal domains not allowed")
    
    try:
        ip = ip_address(hostname)
    except ValueError:
        pass
    else:
        if isinstance(ip, (IPv4Address, IPv6Address)):
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                raise ValueError("Private/internal IPs not allowed")
    
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port in BLOCKED_PORTS:
        raise ValueError(f"Port {port} not allowed")
    
    return url


def redact_sensitive_data(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            redacted = value
            for pattern in SENSITIVE_PATTERNS:
                redacted = pattern.sub("[REDACTED]", redacted)
            result[key] = redacted
        elif isinstance(value, dict):
            result[key] = redact_sensitive_data(value)
        elif isinstance(value, list):
            result[key] = [
                redact_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


def compute_state_hash(state_delta: dict) -> str:
    import json
    normalized = json.dumps(state_delta, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
