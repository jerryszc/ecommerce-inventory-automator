from datetime import UTC, datetime, timedelta
from typing import cast

import bcrypt
from jose import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    # bcrypt has 72-byte limit, truncate if needed
    pw_bytes = password.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pw_bytes = plain.encode("utf-8")[:72]
    hashed_bytes = hashed.encode("utf-8")
    return bcrypt.checkpw(pw_bytes, hashed_bytes)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire})
    return cast(str, jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm))


def decode_token(token: str) -> dict:
    return cast(dict, jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]))
