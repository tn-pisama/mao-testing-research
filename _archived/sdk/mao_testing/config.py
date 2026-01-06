"""MAO Testing SDK configuration."""

import os
from dataclasses import dataclass, field
from typing import Optional, List, Callable
from .errors import ConfigError


@dataclass
class SamplingRule:
    """Rule for conditional trace sampling."""
    condition: str
    rate: float
    
    def matches(self, context: dict) -> bool:
        if self.condition.startswith("status =="):
            status = self.condition.split("==")[1].strip().strip("'\"")
            return context.get("status") == status
        if self.condition.startswith("duration >"):
            threshold = self.condition.split(">")[1].strip().rstrip("s")
            return context.get("duration_s", 0) > float(threshold)
        if self.condition.startswith("cost >"):
            threshold = float(self.condition.split(">")[1].strip())
            return context.get("cost", 0) > threshold
        if self.condition.startswith("tag:"):
            tag = self.condition.split(":")[1].strip()
            return tag in context.get("tags", [])
        return False


@dataclass
class MAOConfig:
    """Configuration for MAO Testing SDK."""
    
    api_key: Optional[str] = None
    endpoint: str = "https://api.mao-testing.com"
    environment: str = "development"
    service_name: str = "mao-agent-system"
    sample_rate: float = 1.0
    batch_size: int = 100
    flush_interval: float = 5.0
    on_error: str = "log"
    sampling_rules: List[SamplingRule] = field(default_factory=list)
    enabled: bool = True
    
    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.environ.get("MAO_API_KEY")
        
        if self.endpoint == "https://api.mao-testing.com":
            env_endpoint = os.environ.get("MAO_ENDPOINT")
            if env_endpoint:
                self.endpoint = env_endpoint
        
        if not 0.0 <= self.sample_rate <= 1.0:
            raise ConfigError(f"sample_rate must be between 0.0 and 1.0, got {self.sample_rate}")
        
        if self.on_error not in ("log", "raise", "ignore"):
            raise ConfigError(f"on_error must be 'log', 'raise', or 'ignore', got {self.on_error}")
    
    @classmethod
    def from_env(cls) -> "MAOConfig":
        """Create config from environment variables."""
        return cls(
            api_key=os.environ.get("MAO_API_KEY"),
            endpoint=os.environ.get("MAO_ENDPOINT", "https://api.mao-testing.com"),
            environment=os.environ.get("MAO_ENVIRONMENT", "development"),
            service_name=os.environ.get("MAO_SERVICE_NAME", "mao-agent-system"),
            sample_rate=float(os.environ.get("MAO_SAMPLE_RATE", "1.0")),
        )
