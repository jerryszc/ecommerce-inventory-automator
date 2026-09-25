import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlmodel import Session, select
from jose import jwt, JWTError
from app.models import User
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings


# In-memory refresh token store (MVP - use Redis in production)
_refresh_tokens: set[str] = set()


def create_user(session: Session, user_data: dict) -> User:
    """Create new user (admin only)."""
    user = User(
        email=user_data["email"],
        hashed_password=hash_password(user_data["password"]),
        role=user_data.get("role", "operator"),
        is_active=user_data.get("is_active", True),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user(session: Session, user_id: int) -> Optional[User]:
    return session.get(User, user_id)


def get_user_by_email(session: Session, email: str) -> Optional[User]:
    return session.exec(select(User).where(User.email == email)).first()


def list_users(session: Session, skip: int = 0, limit: int = 100) -> list[User]:
    return session.exec(select(User).offset(skip).limit(limit)).all()


def update_user(session: Session, user_id: int, data: dict) -> Optional[User]:
    user = session.get(User, user_id)
    if not user:
        return None

    if "email" in data and data["email"] is not None:
        user.email = data["email"]
    if "role" in data and data["role"] is not None:
        user.role = data["role"]
    if "is_active" in data and data["is_active"] is not None:
        user.is_active = data["is_active"]
    if "password" in data and data["password"] is not None:
        user.hashed_password = hash_password(data["password"])

    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def delete_user(session: Session, user_id: int) -> bool:
    user = session.get(User, user_id)
    if not user:
        return False
    session.delete(user)
    session.commit()
    return True


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=7))
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid.uuid4())})
    token = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    _refresh_tokens.add(token)
    return token


def verify_refresh_token(token: str) -> Optional[dict]:
    if token not in _refresh_tokens:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None


def revoke_refresh_token(token: str) -> bool:
    return _refresh_tokens.discard(token) is not None