"""Encryption utilities for sensitive data like API keys."""

import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


def _get_encryption_key() -> bytes:
    """
    Get or derive the encryption key from environment.

    Uses ENCRYPTION_KEY env var directly if set (32 bytes, base64 encoded),
    or derives one from SECRET_KEY using PBKDF2.
    """
    # Try direct encryption key first
    direct_key = os.environ.get("ENCRYPTION_KEY")
    if direct_key:
        return base64.urlsafe_b64decode(direct_key)

    # Derive from SECRET_KEY
    secret_key = os.environ.get("SECRET_KEY", "development-secret-key-change-in-production")

    # Use a fixed salt for derivation (in production, consider per-tenant salts)
    salt = b"mao-testing-platform-salt"

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
    return key


def get_fernet() -> Fernet:
    """Get a Fernet instance for encryption/decryption."""
    return Fernet(_get_encryption_key())


def encrypt_value(plaintext: str) -> str:
    """
    Encrypt a string value.

    Args:
        plaintext: The value to encrypt

    Returns:
        Base64-encoded encrypted value
    """
    fernet = get_fernet()
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_value(encrypted: str) -> str:
    """
    Decrypt an encrypted value.

    Args:
        encrypted: Base64-encoded encrypted value

    Returns:
        Decrypted plaintext
    """
    fernet = get_fernet()
    decrypted = fernet.decrypt(encrypted.encode())
    return decrypted.decode()
