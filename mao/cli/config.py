"""CLI configuration management."""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict

from mao.core.security import get_config_dir, get_api_key, store_api_key


@dataclass
class CLIConfig:
    """CLI configuration."""
    endpoint: str = "http://localhost:8000"
    tenant_id: str = "default"
    output_format: str = "table"
    colors: bool = True
    
    @classmethod
    def load(cls) -> "CLIConfig":
        """Load config from file."""
        config_path = get_config_dir() / "config.yaml"
        
        if not config_path.exists():
            return cls()
        
        try:
            data = yaml.safe_load(config_path.read_text())
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()
    
    def save(self) -> None:
        """Save config to file."""
        config_path = get_config_dir() / "config.yaml"
        config_path.write_text(yaml.dump(asdict(self)))
    
    def get_api_key(self) -> Optional[str]:
        """Get API key from secure storage."""
        return get_api_key()
    
    def set_api_key(self, api_key: str) -> None:
        """Store API key securely."""
        store_api_key(api_key)


def load_config() -> CLIConfig:
    """Load CLI configuration."""
    return CLIConfig.load()
