from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.core.deps import require_admin, require_operator_or_admin
from app.db.session import get_session
from app.models import Channel, User
from app.schemas import ChannelCreate, ChannelRead

router = APIRouter(prefix="/channels", tags=["channels"])


@router.post("/", response_model=ChannelRead, status_code=status.HTTP_201_CREATED)
def create_channel(
    channel_in: ChannelCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_admin)],
) -> Channel:
    existing = session.exec(
        select(Channel).where(Channel.code == channel_in.code)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Channel code already exists")
    channel = Channel.model_validate(channel_in)
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel


@router.get("/", response_model=list[ChannelRead])
def list_channels(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[Channel]:
    return session.exec(select(Channel).offset(skip).limit(limit)).all()


@router.get("/{channel_id}", response_model=ChannelRead)
def get_channel(
    channel_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> Channel:
    channel = session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    channel = session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    session.delete(channel)
    session.commit()