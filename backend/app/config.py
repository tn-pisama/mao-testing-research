from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "MAO Testing Platform"
    debug: bool = False
    
    database_url: str = "postgresql+asyncpg://mao:mao@localhost:5432/mao"
    redis_url: str = "redis://localhost:6379"
    
    jwt_secret: str = Field(..., min_length=32, description="JWT signing secret (required)")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_webhook_secret: str = ""
    clerk_jwt_issuer: str = ""
    jwks_cache_ttl_seconds: int = 3600
    
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    auth_rate_limit_requests: int = 10
    auth_rate_limit_window_seconds: int = 60
    
    embedding_model: str = "all-MiniLM-L6-v2"
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
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
