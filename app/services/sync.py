from datetime import datetime, timezone
from sqlmodel import Session, select

from app.models import InventoryLevel, Channel, ConflictLog, Variant


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sync_inventory(
    session: Session,
    variant_id: int,
    channel_code: str,
    qty: int,
) -> tuple[InventoryLevel, bool]:
    """
    Last-write-wins sync.
    Returns (inventory_level, conflict_logged).
    """
    channel = session.exec(select(Channel).where(Channel.code == channel_code)).first()
    if not channel:
        raise ValueError(f"Channel '{channel_code}' not found")

    variant = session.get(Variant, variant_id)
    if not variant:
        raise ValueError(f"Variant {variant_id} not found")

    existing = session.exec(
        select(InventoryLevel).where(
            InventoryLevel.variant_id == variant_id,
            InventoryLevel.channel_id == channel.id,
        )
    ).first()

    conflict_logged = False
    now = utcnow()

    if existing:
        if existing.qty != qty:
            # Log conflict: old value is the loser
            session.add(ConflictLog(
                variant_id=variant_id,
                channel_id=channel.id,
                old_qty=existing.qty,
                new_qty=qty,
                loser_qty=existing.qty,
            ))
            conflict_logged = True
        existing.qty = qty
        existing.updated_at = now
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing, conflict_logged
    else:
        inv = InventoryLevel(
            variant_id=variant_id,
            channel_id=channel.id,
            qty=qty,
            updated_at=now,
        )
        session.add(inv)
        session.commit()
        session.refresh(inv)
        return inv, False


def get_inventory(
    session: Session,
    variant_id: int | None = None,
    channel_code: str | None = None,
) -> list[InventoryLevel]:
    stmt = select(InventoryLevel)
    if variant_id:
        stmt = stmt.where(InventoryLevel.variant_id == variant_id)
    if channel_code:
        channel = session.exec(select(Channel).where(Channel.code == channel_code)).first()
        if channel:
            stmt = stmt.where(InventoryLevel.channel_id == channel.id)
    return session.exec(stmt).all()