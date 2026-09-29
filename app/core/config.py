from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    # App
    app_name: str = "E-Commerce Inventory Automator"
    app_env: str = "dev"

    # Database
    # Named db_url_config rather than _database_url: pydantic v2 rejects
    # underscore-prefixed fields outright, and it ignores them silently in
    # older versions, which is why DATABASE_URL from the environment was never
    # read. The property database_url below is what callers use.
    db_url_config: str = Field(
        default="postgresql+psycopg://postgres:postgres@db:5432/inventory",
        validation_alias=AliasChoices("DATABASE_URL", "db_url_config"),
    )

    # JWT
    jwt_secret_config: str = Field(
        default="change-me-in-env",
        validation_alias=AliasChoices("JWT_SECRET", "jwt_secret_config"),
    )
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
    cors_origins: list[str] = ["*"]

    # ========== AWS / LocalStack ==========
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None  # LocalStack: http://localhost:4566
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

    def _secret(self, arn: str, fallback: str) -> str:
        """Resolve a secret, preferring the local value when one exists.

        The original condition was `app_env == "local" and not
        aws_endpoint_url`, which meant the local path could never be taken
        while LocalStack was configured: having an endpoint is exactly the
        situation where the short local path should be used. Any endpoint
        present is a local or test double, so it is safe to read from.
        """
        from app.core.aws import ensure_secret

        if self.app_env == "local" or self.aws_endpoint_url:
            return ensure_secret(arn, fallback)
        return fallback

    @property
    def jwt_secret(self) -> str:
        """Obtiene JWT secret de Secrets Manager (o default local)."""
        return self._secret(self.secrets_arn_jwt, self.jwt_secret_config)

    @property
    def database_url(self) -> str:
        """Obtiene DB URL de Secrets Manager (o default local)."""
        return self._secret(self.secrets_arn_db, self.db_url_config)


settings = Settings()
