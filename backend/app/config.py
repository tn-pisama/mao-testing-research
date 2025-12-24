from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "MAO Testing Platform"
    debug: bool = False
    
    database_url: str = "postgresql+asyncpg://mao:mao@localhost:5432/mao"
    redis_url: str = "redis://localhost:6379"
    
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    
    embedding_model: str = "all-MiniLM-L6-v2"
    loop_detection_window: int = 7
    structural_threshold: float = 0.95
    semantic_threshold: float = 0.85
    
    otel_service_name: str = "mao-platform"
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
