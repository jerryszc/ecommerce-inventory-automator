from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.core.deps import require_operator_or_admin
from app.db.session import get_session
from app.models import Variant, InventoryLevel, Channel, Product, User
from app.schemas import LowStockAlert

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/low-stock", response_model=list[LowStockAlert])
def get_low_stock(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    channel_code: str | None = Query(None),
) -> list[LowStockAlert]:
    stmt = (
        select(Variant, InventoryLevel, Channel, Product)
        .join(InventoryLevel, InventoryLevel.variant_id == Variant.id)
        .join(Channel, Channel.id == InventoryLevel.channel_id)
        .join(Product, Product.id == Variant.product_id)
        .where(InventoryLevel.qty <= Variant.threshold)
    )
    if channel_code:
        stmt = stmt.where(Channel.code == channel_code)

    results = session.exec(stmt).all()

    alerts = []
    for variant, inv, channel, product in results:
        alerts.append(LowStockAlert(
            variant_id=variant.id,
            variant_sku=variant.sku,
            product_name=product.name,
            size=variant.size,
            color=variant.color,
            channel_code=channel.code,
            qty=inv.qty,
            threshold=variant.threshold,
        ))
    return alerts