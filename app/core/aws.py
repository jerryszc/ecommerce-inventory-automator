import json
from functools import cache, lru_cache
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import settings

if TYPE_CHECKING:
    import redis


def _get_client_config(service: str) -> dict:
    """Config comÃºn para LocalStack o AWS real."""
    # boto3 retries five times with exponential backoff by default. Against an
    # endpoint that is not there, one call took ~50s before failing, which made
    # every request that touched a secret unusable. Two attempts, a short
    # backoff and a one-second connect timeout are enough to reach a healthy
    # endpoint and fail fast otherwise.
    retry = {"max_attempts": 2, "mode": "standard"}
    if settings.aws_endpoint_url:
        return {
            "endpoint_url": settings.aws_endpoint_url,
            "region_name": settings.aws_region,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
            "config": Config(retries=retry, connect_timeout=1, read_timeout=2),
        }
    return {
        "region_name": settings.aws_region,
        "config": Config(retries=retry, connect_timeout=1, read_timeout=2),
    }


@lru_cache
def get_secrets_client() -> Any:
    return boto3.client("secretsmanager", **_get_client_config("secretsmanager"))


@lru_cache
def get_sqs_client() -> Any:
    return boto3.client("sqs", **_get_client_config("sqs"))


@lru_cache
def get_s3_client() -> Any:
    return boto3.client("s3", **_get_client_config("s3"))


@lru_cache
def get_logs_client() -> Any:
    return boto3.client("logs", **_get_client_config("logs"))


@lru_cache
def get_redis_client() -> Any:
    import redis

    if settings.redis_url.startswith("redis://localhost") or settings.aws_endpoint_url:
        # LocalStack Redis o local
        return redis.from_url(settings.redis_url, decode_responses=True)
    # AWS ElastiCache (con TLS si es producciÃ³n)
    return redis.from_url(settings.redis_url, decode_responses=True, ssl_cert_reqs=None)


# Helpers de alto nivel
def get_secret(name: str) -> str:
    client = get_secrets_client()
    return client.get_secret_value(SecretId=name)["SecretString"]


def put_secret(name: str, value: str) -> None:
    client = get_secrets_client()
    client.put_secret_value(SecretId=name, SecretString=value)


@cache
def ensure_secret(name: str, default_value: str) -> str:
    """Crea secret si no existe, retorna valor. Si no hay AWS/LocalStack, retorna default.

    Cached: this runs inside the request path (every token operation goes
    through settings.jwt_secret), and a cache miss costs a network round trip
    or a failed connection. The value does not change during a process
    lifetime, so one lookup per name is enough.
    """
    try:
        client = get_secrets_client()
        try:
            return client.get_secret_value(SecretId=name)["SecretString"]
        except client.exceptions.ResourceNotFoundException:
            client.create_secret(Name=name, SecretString=default_value)
            return default_value
    except (EndpointConnectionError, ClientError):
        # LocalStack/AWS no disponible, retornar default
        return default_value


def enqueue_sqs(queue_url: str, message: dict) -> str:
    client = get_sqs_client()
    resp = client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message))
    return resp["MessageId"]


def upload_s3(
    bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream"
) -> str:
    client = get_s3_client()
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    return f"s3://{bucket}/{key}"


def download_s3(bucket: str, key: str) -> bytes:
    client = get_s3_client()
    obj = client.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def get_redis() -> "redis.Redis":
    """Redis client, typed for callers.

    The import is under TYPE_CHECKING: the annotation is a string, so the name
    only has to exist for the type checker, and redis is not needed at import
    time here.
    """
    return get_redis_client()
