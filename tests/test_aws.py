import json
import uuid

import boto3
import pytest

from app.core.aws import (
    download_s3,
    enqueue_sqs,
    ensure_secret,
    get_redis,
    get_secret,
    upload_s3,
)


@pytest.fixture(scope="session")
def aws_creds():
    """Credenciales para LocalStack."""
    return {
        "endpoint_url": "http://localhost:4566",
        "region_name": "us-east-1",
        "aws_access_key_id": "test",
        "aws_secret_access_key": "test",
    }


class TestSecretsManager:
    def test_put_and_get_secret(self, aws_creds):
        client = boto3.client("secretsmanager", **aws_creds)
        # Unique name per run: a fixed one makes the test fail on the second
        # run, because LocalStack keeps state between runs.
        name = f"test/secret-{uuid.uuid4().hex[:8]}"
        client.create_secret(Name=name, SecretString="test-value")

        value = get_secret(name)
        assert value == "test-value"

    def test_ensure_secret_creates_if_missing(self):
        # Unique name for the same reason as above.
        name = f"test/auto-create-{uuid.uuid4().hex[:8]}"
        value = ensure_secret(name, "default-value")
        assert value == "default-value"

        # Segunda llamada debe retornar existente
        value2 = ensure_secret(name, "other-value")
        assert value2 == "default-value"


class TestSQS:
    def test_enqueue_and_receive(self):
        # Crear queue
        client = boto3.client("sqs", endpoint_url="http://localhost:4566", region_name="us-east-1")
        queue = client.create_queue(QueueName="test-queue")
        queue_url = queue["QueueUrl"]

        # Enqueue
        msg_id = enqueue_sqs(queue_url, {"test": "data"})
        assert msg_id

        # Receive
        resp = boto3.client("sqs", endpoint_url="http://localhost:4566").receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=1
        )
        assert len(resp.get("Messages", [])) == 1
        body = json.loads(resp["Messages"][0]["Body"])
        assert body["test"] == "data"


class TestS3:
    def test_upload_and_download(self):
        client = boto3.client("s3", endpoint_url="http://localhost:4566")
        client.create_bucket(Bucket="test-bucket")

        data = b"test content"
        upload_s3("test-bucket", "test-key.txt", data, "text/plain")

        downloaded = download_s3("test-bucket", "test-key.txt")
        assert downloaded == b"test content"


class TestRedis:
    def test_redis_connection(self):
        r = get_redis()
        r.set("test_key", "test_value")
        assert r.get("test_key") == "test_value"
        r.delete("test_key")


class TestDistributedRateLimit:
    def test_rate_limit_allows_under_limit(self):
        from app.core.rate_limit import distributed_rate_limit

        allowed, headers = distributed_rate_limit("test_key_1")
        assert allowed is True
        assert headers["X-RateLimit-Limit"] == "100"

    def test_rate_limit_blocks_over_limit(self):
        from app.core.rate_limit import _distributed_limiter

        # Unique key: a fixed one means the counter is already over the limit
        # on the second run and the test stops testing anything.
        key = f"test_limit_key_{uuid.uuid4().hex[:8]}"
        limit = _distributed_limiter.limit

        # The sliding window counts the stored entries and then adds the
        # current request, so the first request is always allowed. Drive it
        # past the limit rather than assuming the exact cut-off point.
        first_allowed, _ = _distributed_limiter.is_allowed(key)
        assert first_allowed is True

        allowed = True
        headers = {}
        for _ in range(limit + 1):
            allowed, headers = _distributed_limiter.is_allowed(key)

        assert allowed is False
        assert int(headers["X-RateLimit-Remaining"]) == 0
