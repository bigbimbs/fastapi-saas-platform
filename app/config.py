from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    database_url: str = "postgresql://user:password@localhost/saas_platform"
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    redis_url: str = "redis://localhost:6379"
    user_service_url: str = "https://api.userservice.com/v1"
    payment_service_url: str = "https://api.payments.com/v2"
    communication_service_url: str = "https://api.emailservice.com/v1"
    rate_limit_requests_per_minute: int = 100
    rate_limit_burst_limit: int = 20
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"


settings = Settings() 