from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict
from functools import lru_cache
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class FrameworkThresholds:
    """Per-framework detection thresholds.

    Different frameworks have different failure patterns:
    - LangGraph: State-heavy, prone to structural loops
    - AutoGen: Multi-agent, prone to conversation circles
    - CrewAI: Task-based, prone to coordination failures
    - LangChain: Chain-based, moderate patterns
    """
    structural_threshold: float
    semantic_threshold: float
    loop_detection_window: int
    min_matches_for_loop: int
    confidence_scaling: float


# Framework-specific threshold configurations
# Tuned based on observed failure patterns per framework
FRAMEWORK_THRESHOLDS: Dict[str, FrameworkThresholds] = {
    # LangGraph: Tight state management, structural patterns are highly reliable
    "langgraph": FrameworkThresholds(
        structural_threshold=0.92,  # Lower - structural matches are reliable
        semantic_threshold=0.88,    # Higher - semantic loops less common
        loop_detection_window=5,    # Shorter - state changes are atomic
        min_matches_for_loop=2,
        confidence_scaling=1.0,
    ),
    # AutoGen: Multi-agent conversations, semantic loops are common
    "autogen": FrameworkThresholds(
        structural_threshold=0.90,
        semantic_threshold=0.80,    # Lower - catch conversation circles
        loop_detection_window=10,   # Longer - multi-turn conversations
        min_matches_for_loop=3,     # More matches needed due to verbosity
        confidence_scaling=0.95,    # Slightly lower - more false positives expected
    ),
    # CrewAI: Task delegation, coordination patterns
    "crewai": FrameworkThresholds(
        structural_threshold=0.88,  # Lower - task handoffs have patterns
        semantic_threshold=0.82,
        loop_detection_window=8,
        min_matches_for_loop=2,
        confidence_scaling=1.0,
    ),
    # LangChain: Standard chain patterns
    "langchain": FrameworkThresholds(
        structural_threshold=0.95,
        semantic_threshold=0.85,
        loop_detection_window=7,
        min_matches_for_loop=2,
        confidence_scaling=1.0,
    ),
    # OpenAI Assistants: Function calling patterns
    "openai": FrameworkThresholds(
        structural_threshold=0.93,
        semantic_threshold=0.86,
        loop_detection_window=6,
        min_matches_for_loop=2,
        confidence_scaling=1.0,
    ),
    # Anthropic/Claude: Similar to OpenAI
    "anthropic": FrameworkThresholds(
        structural_threshold=0.93,
        semantic_threshold=0.86,
        loop_detection_window=6,
        min_matches_for_loop=2,
        confidence_scaling=1.0,
    ),
    # n8n: Workflow automation, very structured
    "n8n": FrameworkThresholds(
        structural_threshold=0.98,  # Very high - n8n is deterministic
        semantic_threshold=0.90,
        loop_detection_window=5,
        min_matches_for_loop=2,
        confidence_scaling=1.1,     # Higher confidence for detected loops
    ),
    # Default/unknown frameworks
    "unknown": FrameworkThresholds(
        structural_threshold=0.95,
        semantic_threshold=0.85,
        loop_detection_window=7,
        min_matches_for_loop=2,
        confidence_scaling=1.0,
    ),
}


def get_framework_thresholds(framework: Optional[str] = None) -> FrameworkThresholds:
    """Get detection thresholds for a specific framework.

    Args:
        framework: Framework name (langgraph, autogen, crewai, etc.)

    Returns:
        FrameworkThresholds for the specified framework
    """
    if framework is None:
        framework = "unknown"
    framework = framework.lower().strip()
    return FRAMEWORK_THRESHOLDS.get(framework, FRAMEWORK_THRESHOLDS["unknown"])


def get_tenant_thresholds(
    tenant_settings: Optional[Dict] = None,
    framework: Optional[str] = None
) -> FrameworkThresholds:
    """Get detection thresholds with tenant overrides.

    Merges tenant-specific threshold settings with framework defaults.
    Tenant settings take precedence over framework defaults.

    Tenant settings format in tenant.settings JSONB:
    {
        "detection_thresholds": {
            "global": {  # Applied to all frameworks
                "structural_threshold": 0.92,
                "semantic_threshold": 0.85,
                ...
            },
            "frameworks": {  # Per-framework overrides
                "langgraph": {
                    "structural_threshold": 0.90,
                    ...
                }
            }
        }
    }

    Args:
        tenant_settings: Tenant's settings dict (from tenant.settings)
        framework: Framework name for framework-specific defaults

    Returns:
        FrameworkThresholds with tenant overrides applied
    """
    # Start with framework defaults
    base = get_framework_thresholds(framework)

    if not tenant_settings:
        return base

    detection_config = tenant_settings.get("detection_thresholds", {})

    # Apply global tenant overrides first
    global_overrides = detection_config.get("global", {})

    # Then apply framework-specific tenant overrides
    framework_key = (framework or "unknown").lower().strip()
    framework_overrides = detection_config.get("frameworks", {}).get(framework_key, {})

    # Merge: base -> global overrides -> framework overrides
    return FrameworkThresholds(
        structural_threshold=framework_overrides.get(
            "structural_threshold",
            global_overrides.get("structural_threshold", base.structural_threshold)
        ),
        semantic_threshold=framework_overrides.get(
            "semantic_threshold",
            global_overrides.get("semantic_threshold", base.semantic_threshold)
        ),
        loop_detection_window=framework_overrides.get(
            "loop_detection_window",
            global_overrides.get("loop_detection_window", base.loop_detection_window)
        ),
        min_matches_for_loop=framework_overrides.get(
            "min_matches_for_loop",
            global_overrides.get("min_matches_for_loop", base.min_matches_for_loop)
        ),
        confidence_scaling=framework_overrides.get(
            "confidence_scaling",
            global_overrides.get("confidence_scaling", base.confidence_scaling)
        ),
    )


# Default threshold config for new tenants
DEFAULT_TENANT_THRESHOLD_CONFIG = {
    "detection_thresholds": {
        "global": {},  # No global overrides by default
        "frameworks": {},  # No per-framework overrides by default
    }
}


class FeatureFlags(BaseSettings):
    """Feature flags for ICP vs Enterprise feature separation.

    ICP (Startup) features are always enabled.
    Enterprise features require explicit opt-in via these flags.
    """
    # Master switch - enables all enterprise features
    enterprise_enabled: bool = Field(
        default=False,
        description="Master switch for all enterprise features"
    )

    # Individual enterprise feature flags
    ml_detection: bool = Field(
        default=False,
        description="ML-based detection (tiered, orchestrator, golden dataset)"
    )
    otel_ingestion: bool = Field(
        default=False,
        description="OTEL native ingestion (vs SDK/export only)"
    )
    chaos_engineering: bool = Field(
        default=False,
        description="Chaos injection and resilience testing"
    )
    trace_replay: bool = Field(
        default=False,
        description="Trace replay and what-if simulation"
    )
    regression_testing: bool = Field(
        default=False,
        description="Regression testing framework"
    )
    advanced_evals: bool = Field(
        default=False,
        description="Advanced evaluation framework"
    )
    audit_logging: bool = Field(
        default=False,
        description="Compliance audit logging"
    )
    quality_assessment: bool = Field(
        default=False,
        description="Quality assessment for n8n workflows and agents"
    )

    def is_enabled(self, feature: str) -> bool:
        """Check if a specific feature is enabled.

        Enterprise features require both:
        1. The master enterprise_enabled flag
        2. The specific feature flag
        """
        if not self.enterprise_enabled:
            return False
        return getattr(self, feature, False)

    model_config = ConfigDict(
        env_prefix="FEATURE_",
        env_file=".env",
        extra="ignore",  # Ignore non-FEATURE_ prefixed env vars
    )


class Settings(BaseSettings):
    app_name: str = "MAO Testing Platform"
    debug: bool = False

    # Feature flags (loaded as nested config)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    
    database_url: str = "postgresql+asyncpg://mao:mao@localhost:5432/mao"
    redis_url: str = "redis://localhost:6379"
    
    jwt_secret: str = Field(..., min_length=32, description="JWT signing secret (required)")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_webhook_secret: str = ""
    clerk_jwt_issuer: str = ""
    clerk_jwt_audience: str = ""  # Optional: Clerk Frontend API URL for audience verification
    jwks_cache_ttl_seconds: int = 3600

    # Google OAuth settings
    google_client_id: str = ""
    google_client_secret: str = ""
    
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    auth_rate_limit_requests: int = 10
    auth_rate_limit_window_seconds: int = 60
    
    # BGE-M3: +2.5% MTEB over e5-large-v2, same 1024d, no prefix required
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimensions: int = 1024
    embedding_instruction_prefix: bool = False  # BGE-M3 doesn't need prefixes
    loop_detection_window: int = 7
    structural_threshold: float = 0.95
    semantic_threshold: float = 0.85
    
    otel_service_name: str = "mao-platform"
    cors_origins: str = "http://localhost:3000,https://dashboard.mao-testing.com"
    
    @field_validator('jwt_secret')
    @classmethod
    def validate_jwt_secret(cls, v):
        weak_patterns = [
            "change-me", "changeme", "secret", "password", "test", "dev", "demo",
            "123456", "qwerty", "admin", "default", "example"
        ]
        v_lower = v.lower()
        for pattern in weak_patterns:
            if pattern in v_lower:
                raise ValueError(f"JWT_SECRET contains weak pattern '{pattern}'. Use a secure random secret.")
        if len(set(v)) < 8:
            raise ValueError("JWT_SECRET has insufficient entropy. Use a more random value.")
        return v

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
