"""Security utilities for MAO."""

import os
import re
import sys
import getpass
import base64
from pathlib import Path
from typing import Optional

from .errors import ValidationError


def validate_trace_id(trace_id: str) -> str:
    """Validate trace ID format to prevent injection."""
    if not trace_id:
        raise ValidationError("Trace ID cannot be empty")
    
    if not re.match(r'^[a-zA-Z0-9_-]{1,128}$', trace_id):
        raise ValidationError(f"Invalid trace ID format: {trace_id}")
    
    return trace_id


def validate_detection_id(detection_id: str) -> str:
    """Validate detection ID format."""
    if not detection_id:
        raise ValidationError("Detection ID cannot be empty")
    
    if not re.match(r'^[a-zA-Z0-9_-]{1,128}$', detection_id):
        raise ValidationError(f"Invalid detection ID format: {detection_id}")
    
    return detection_id


def validate_file_path(file_path: str, project_root: Path) -> Path:
    """Validate file path is within project and safe."""
    path = Path(file_path).resolve()
    project_root = project_root.resolve()
    
    if not str(path).startswith(str(project_root)):
        raise ValidationError("File path outside project directory")
    
    allowed_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java'}
    if path.suffix not in allowed_extensions:
        raise ValidationError(f"File type not allowed: {path.suffix}")
    
    return path


def get_config_dir() -> Path:
    """Get MAO config directory."""
    config_dir = Path.home() / ".mao"
    config_dir.mkdir(mode=0o700, exist_ok=True)
    return config_dir


def get_credentials_path() -> Path:
    """Get path to credentials file."""
    return get_config_dir() / "credentials.enc"


def store_api_key(api_key: str) -> None:
    """Store API key securely."""
    if sys.platform in ("darwin", "win32"):
        try:
            import keyring
            keyring.set_password("mao", "api_key", api_key)
            return
        except ImportError:
            pass
    
    _store_api_key_encrypted(api_key)


def _store_api_key_encrypted(api_key: str) -> None:
    """Store API key in encrypted file."""
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError:
        cred_path = get_credentials_path()
        cred_path.write_text(api_key)
        cred_path.chmod(0o600)
        return
    
    password = getpass.getpass("Create password to protect credentials: ")
    salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    fernet = Fernet(key)
    encrypted = fernet.encrypt(api_key.encode())
    
    cred_path = get_credentials_path()
    cred_path.write_bytes(salt + encrypted)
    cred_path.chmod(0o600)


def get_api_key() -> Optional[str]:
    """Retrieve stored API key."""
    if sys.platform in ("darwin", "win32"):
        try:
            import keyring
            key = keyring.get_password("mao", "api_key")
            if key:
                return key
        except ImportError:
            pass
    
    return _get_api_key_encrypted()


def _get_api_key_encrypted() -> Optional[str]:
    """Get API key from encrypted file."""
    cred_path = get_credentials_path()
    if not cred_path.exists():
        return None
    
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError:
        return cred_path.read_text().strip()
    
    data = cred_path.read_bytes()
    salt = data[:16]
    encrypted = data[16:]
    
    password = getpass.getpass("Enter password to decrypt credentials: ")
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    fernet = Fernet(key)
    return fernet.decrypt(encrypted).decode()
