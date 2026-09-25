from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.core.deps import get_current_user, require_admin, create_access_token
from app.core.security import verify_password
from app.db.session import get_session
from app.models import User
from app.schemas import UserRead, Token, UserCreate, UserUpdate, UserRead, TokenRefresh, TokenPair
from app.services.user import (
    create_user, get_user, get_user_by_email, list_users, update_user, delete_user,
    create_refresh_token, verify_refresh_token, revoke_refresh_token
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session),
) -> Token:
    user = session.exec(select(User).where(User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    return Token(access_token=access_token, token_type="bearer")


@router.post("/refresh", response_model=Token)
def refresh_token(
    token_data: TokenRefresh,
    session: Session = Depends(get_session),
) -> Token:
    payload = verify_refresh_token(token_data.refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or revoked refresh token")

    user = get_user_by_email(session, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    revoke_refresh_token(token_data.refresh_token)
    access_token = create_access_token(data={"sub": user.email})
    new_refresh_token = create_refresh_token(data={"sub": user.email})

    return Token(access_token=access_token, token_type="bearer")


@router.post("/logout")
def logout(token_data: TokenRefresh) -> dict:
    revoked = revoke_refresh_token(token_data.refresh_token)
    return {"message": "Logged out" if revoked else "Token already invalid"}


@router.get("/me", response_model=UserRead)
def read_me(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


# User Management (Admin only)

@router.post("/users/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    user_in: UserCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> User:
    if get_user_by_email(session, user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    return create_user(session, user_in.model_dump())


@router.get("/users/", response_model=list[UserRead])
def list_users_endpoint(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[User]:
    return list_users(session, skip, limit)


@router.get("/users/{user_id}", response_model=UserRead)
def get_user_endpoint(
    user_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> User:
    user = get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user_endpoint(
    user_id: int,
    user_in: UserUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> User:
    user = update_user(session, user_id, user_in.model_dump(exclude_unset=True))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_endpoint(
    user_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> None:
    if not delete_user(session, user_id):
        raise HTTPException(status_code=404, detail="User not found")