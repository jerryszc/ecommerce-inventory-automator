from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Channel(SQLModel, table=True):
    __tablename__ = "channel"
    __table_args__ = (UniqueConstraint("code", name="uq_channel_code"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, max_length=50)
    name: str = Field(max_length=100)
    created_at: datetime = Field(default_factory=utcnow)

    inventory_levels: list["InventoryLevel"] = Relationship(back_populates="channel")
    conflict_logs: list["ConflictLog"] = Relationship(back_populates="channel")


class Product(SQLModel, table=True):
    __tablename__ = "product"
    __table_args__ = (UniqueConstraint("sku_base", name="uq_product_sku_base"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    sku_base: str = Field(index=True, max_length=100)
    name: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=utcnow)

    variants: list["Variant"] = Relationship(back_populates="product")


class Variant(SQLModel, table=True):
    __tablename__ = "variant"
    __table_args__ = (UniqueConstraint("sku", name="uq_variant_sku"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    sku: str = Field(index=True, max_length=100)
    size: Optional[str] = Field(default=None, max_length=50)
    color: Optional[str] = Field(default=None, max_length=50)
    ean: Optional[str] = Field(default=None, max_length=50, index=True)
    price: float = Field(default=0.0)
    threshold: int = Field(default=5)
    created_at: datetime = Field(default_factory=utcnow)

    product: Product = Relationship(back_populates="variants")
    inventory_levels: list["InventoryLevel"] = Relationship(back_populates="variant")
    conflict_logs: list["ConflictLog"] = Relationship(back_populates="variant")


class InventoryLevel(SQLModel, table=True):
    __tablename__ = "inventory_level"
    __table_args__ = (
        UniqueConstraint("variant_id", "channel_id", name="uq_inventory_variant_channel"),
    )

    variant_id: int = Field(foreign_key="variant.id", primary_key=True)
    channel_id: int = Field(foreign_key="channel.id", primary_key=True)
    qty: int = Field(default=0)
    updated_at: datetime = Field(default_factory=utcnow)

    variant: Variant = Relationship(back_populates="inventory_levels")
    channel: Channel = Relationship(back_populates="inventory_levels")


class ConflictLog(SQLModel, table=True):
    __tablename__ = "conflict_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    variant_id: int = Field(foreign_key="variant.id", index=True)
    channel_id: int = Field(foreign_key="channel.id", index=True)
    old_qty: int
    new_qty: int
    loser_qty: int
    created_at: datetime = Field(default_factory=utcnow)

    variant: Variant = Relationship(back_populates="conflict_logs")
    channel: Channel = Relationship(back_populates="conflict_logs")


class ImportBatch(SQLModel, table=True):
    __tablename__ = "import_batch"

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(max_length=255)
    total: int = Field(default=0)
    ok: int = Field(default=0)
    errors: int = Field(default=0)
    created_by: Optional[str] = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=utcnow)


class User(SQLModel, table=True):
    __tablename__ = "user"
    __table_args__ = (UniqueConstraint("email", name="uq_user_email"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, max_length=255)
    hashed_password: str = Field(max_length=255)
    role: str = Field(max_length=20, default="operator")  # "admin" or "operator"
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)


# Forward references for relationships
Channel.update_forward_refs()
Product.update_forward_refs()
Variant.update_forward_refs()
InventoryLevel.update_forward_refs()
ConflictLog.update_forward_refs()
ImportBatch.update_forward_refs()
User.update_forward_refs()