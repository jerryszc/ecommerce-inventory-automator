from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.core.deps import require_admin, require_operator_or_admin
from app.db.session import get_session
from app.models import InventoryLevel, Channel, Variant, Product, User
from app.schemas import InventoryLevelRead, InventorySync, InventorySyncResult
from app.services.sync import sync_inventory, get_inventory

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/", response_model=list[InventoryLevelRead])
def list_inventory(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    variant_id: int | None = Query(None),
    channel_code: str | None = Query(None),
) -> list[InventoryLevel]:
    return get_inventory(session, variant_id=variant_id, channel_code=channel_code)


@router.post("/sync", response_model=InventorySyncResult, status_code=status.HTTP_200_OK)
def sync_stock(
    sync_in: InventorySync,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_admin)],
) -> InventorySyncResult:
    try:
        inv, conflict = sync_inventory(
            session,
            variant_id=sync_in.variant_id,
            channel_code=sync_in.channel_code,
            qty=sync_in.qty,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return InventorySyncResult(
        variant_id=inv.variant_id,
        channel_code=sync_in.channel_code,
        qty=inv.qty,
        updated_at=inv.updated_at,
        conflict_logged=conflict,
    )