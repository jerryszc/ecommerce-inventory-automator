"""Test fixtures for the inventory automator.

The suite runs against the same PostgreSQL instance the app uses in
development, so the test database has to be set up the same way the app sets
it up: tables created from the SQLModel metadata, and the two users the rest
of the suite logs in with already present.

Point DATABASE_URL at a database you do not mind losing before running this.
"""

import os
import uuid
from collections.abc import Iterator

import boto3
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

# boto3 refuses to build a client without credentials, and it does not look at
# the app settings. LocalStack accepts any value, so these are set before the
# AWS helpers are imported anywhere in the suite.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_SESSION_TOKEN", "test")

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import engine
from app.main import app
from app.models import Channel, User

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123!"
OPERATOR_EMAIL = "operator@example.com"
OPERATOR_PASSWORD = "operator123!"

# The suite reads and writes inventory against these two channels by code, so
# they have to exist before the first test runs.
CHANNELS = (("amazon", "Amazon"), ("shopify", "Shopify"))


def _create_tables() -> None:
    SQLModel.metadata.create_all(engine)


def _seed_users(session: Session) -> None:
    """Insert the admin and operator accounts the suite logs in with."""
    for email, password, role in (
        (ADMIN_EMAIL, ADMIN_PASSWORD, "admin"),
        (OPERATOR_EMAIL, OPERATOR_PASSWORD, "operator"),
    ):
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing is not None:
            continue
        session.add(User(email=email, hashed_password=hash_password(password), role=role))
    session.commit()


def _seed_channels(session: Session) -> None:
    """Insert the sales channels the inventory tests sync against."""
    for code, name in CHANNELS:
        existing = session.exec(select(Channel).where(Channel.code == code)).first()
        if existing is None:
            session.add(Channel(code=code, name=name))
    session.commit()


def _startup() -> None:
    """Run the app lifespan once at import time.

    Each test module builds its own ``TestClient(app)`` at module level, which
    never triggers the lifespan, so the tables would not exist. Running the
    startup path here is what makes those module-level clients usable.
    """
    _create_tables()
    with Session(engine) as session:
        _seed_users(session)
        _seed_channels(session)


def _ensure_bucket(client, bucket: str) -> None:
    """Create the S3 bucket if it is missing.

    LocalStack keeps state between runs, but a fresh container has no buckets,
    and an import writes to S3 before it does anything else.
    """
    from botocore.exceptions import ClientError

    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)


def _seed_aws() -> None:
    """Bring up the LocalStack resources the suite writes to."""
    endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
    try:
        _ensure_bucket(
            boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1"),
            settings.s3_bucket_imports,
        )
    except Exception:  # noqa: BLE001 - no LocalStack is fine, AWS tests skip
        pass


_startup()
_seed_aws()


@pytest.fixture(autouse=True)
def _clean_users() -> Iterator[None]:
    """Remove the per-test accounts so each test starts from the same state.

    The seeded admin and operator are kept: the suite logs in with them. Only
    the throwaway accounts created by individual tests are removed, which is
    what the duplicate-email and delete tests depend on.
    """
    yield
    with Session(engine) as session:
        seeded = (ADMIN_EMAIL, OPERATOR_EMAIL)
        for user in session.exec(select(User)).all():
            if user.email not in seeded:
                session.delete(user)
        session.commit()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """A TestClient with the app lifespan run, for tests that want one."""
    with TestClient(app) as test_client:
        yield test_client


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"
