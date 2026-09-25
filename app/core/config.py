from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "E-Commerce Inventory Automator"
    app_env: str = "dev"
    
    # Database
    _database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/inventory"
    
    # JWT
    _jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    
    # Seed users
    admin_email: str = "admin@example.com"
    admin_password: str = "admin123!"
    operator_email: str = "operator@example.com"
    operator_password: str = "operator123!"

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # CORS
    cors_origins: List[str] = ["*"]

    # ========== AWS / LocalStack ==========
    aws_region: str = "us-east-1"
    aws_endpoint_url: Optional[str] = None          # LocalStack: http://localhost:4566
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    
    # Secrets Manager
    secrets_arn_jwt: str = "prod/jwt-secret"
    secrets_arn_db: str = "prod/database-url"
    
    # SQS
    sqs_queue_url: str = ""
    
    # S3
    s3_bucket_imports: str = "ecommerce-inventory-imports"
    
    # Redis / ElastiCache
    redis_url: str = "redis://localhost:6379/0"
    
    # ECS Deploy
    ecs_cluster: str = "production"
    ecr_repository: str = ""
    ecs_cluster_arn: str = ""

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    
    # CORS
    cors_origins: List[str] = ["*"]


    @property
    def jwt_secret(self) -> str:
        """Obtiene JWT secret de Secrets Manager (o default local)."""
        if self.app_env == "local" and not self.aws_endpoint_url:
            return self._jwt_secret
        from app.core.aws import ensure_secret
        return ensure_secret(self.secrets_arn_jwt, self._jwt_secret)
    
    @property
    def database_url(self) -> str:
        """Obtiene DB URL de Secrets Manager (o default local)."""
        if self.app_env == "local" and not self.aws_endpoint_url:
            return self._database_url
        from app.core.aws import ensure_secret
        return ensure_secret(self.secrets_arn_db, self._database_url)


settings = Settings()