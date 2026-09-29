from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, col, select

from app.core.deps import require_operator_or_admin
from app.db.session import get_session
from app.models import Channel, InventoryLevel, Product, User, Variant
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
        # col() around the compared column: SQLModel types a == b between two
        # columns as bool, which SQLAlchemy does not accept as a join condition.
        .join(InventoryLevel, col(InventoryLevel.variant_id) == col(Variant.id))
        .join(Channel, col(Channel.id) == col(InventoryLevel.channel_id))
        .join(Product, col(Product.id) == col(Variant.product_id))
        .where(InventoryLevel.qty <= Variant.threshold)
    )
    if channel_code:
        stmt = stmt.where(Channel.code == channel_code)

    results = session.exec(stmt).all()

    alerts = []
    for variant, inv, channel, product in results:
        alerts.append(
            LowStockAlert(
                variant_id=cast(int, variant.id),
                variant_sku=variant.sku,
                product_name=product.name,
                size=variant.size,
                color=variant.color,
                channel_code=channel.code,
                qty=inv.qty,
                threshold=variant.threshold,
            )
        )
    return alerts
