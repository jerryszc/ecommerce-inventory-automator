import pytest
from sqlmodel import Session, select
from app.db.session import engine
from app.models import Channel, Product, Variant, InventoryLevel, User
from app.core.security import hash_password, verify_password


def test_hash_verify_password():
    pw = "test-password-123"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)


def test_seed_channels_exist():
    with Session(engine) as session:
        channels = session.exec(select(Channel)).all()
        codes = {c.code for c in channels}
        assert "amazon" in codes
        assert "shopify" in codes


def test_seed_users_exist():
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        emails = {u.email for u in users}
        assert "admin@example.com" in emails
        assert "operator@example.com" in emails
        for u in users:
            assert u.is_active is True
            assert u.role in ("admin", "operator")


def _unique_sku(base: str) -> str:
    import uuid
    return f"{base}-{uuid.uuid4().hex[:8]}"


def test_create_product_variant_inventory():
    with Session(engine) as session:
        sku_base = _unique_sku("TEST")
        product = Product(sku_base=sku_base, name="Test Product")
        session.add(product)
        session.commit()
        session.refresh(product)

        variant = Variant(
            product_id=product.id,
            sku=f"{sku_base}-M-RED",
            size="M",
            color="RED",
            price=29.99,
            threshold=10,
        )
        session.add(variant)
        session.commit()
        session.refresh(variant)

        channel = session.exec(select(Channel).where(Channel.code == "amazon")).first()
        inv = InventoryLevel(variant_id=variant.id, channel_id=channel.id, qty=5)
        session.add(inv)
        session.commit()
        session.refresh(inv)

        assert inv.qty == 5
        assert inv.variant_id == variant.id
        assert inv.channel_id == channel.id


def test_variant_threshold_default():
    with Session(engine) as session:
        sku_base = _unique_sku("THR")
        product = Product(sku_base=sku_base, name="Threshold Test")
        session.add(product)
        session.commit()
        session.refresh(product)

        variant = Variant(product_id=product.id, sku=f"{sku_base}-S-BLU", price=10.0)
        session.add(variant)
        session.commit()
        session.refresh(variant)

        assert variant.threshold == 5