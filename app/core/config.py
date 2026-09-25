from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "E-Commerce Inventory Automator"
    app_env: str = "dev"
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/inventory"
    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    admin_email: str = "admin@example.com"
    admin_password: str = "admin123!"
    operator_email: str = "operator@example.com"
    operator_password: str = "operator123!"

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # CORS
    cors_origins: List[str] = ["*"]


settings = Settings()
