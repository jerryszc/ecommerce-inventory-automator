from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from sqlmodel import SQLModel


class ChannelBase(SQLModel):
    code: str = Field(max_length=50)
    name: str = Field(max_length=100)


class ChannelCreate(ChannelBase):
    pass


class ChannelRead(ChannelBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProductBase(SQLModel):
    sku_base: str = Field(max_length=100)
    name: str = Field(max_length=255)


class ProductCreate(ProductBase):
    pass


class ProductRead(ProductBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class VariantBase(SQLModel):
    sku: str = Field(max_length=100)
    size: Optional[str] = Field(default=None, max_length=50)
    color: Optional[str] = Field(default=None, max_length=50)
    ean: Optional[str] = Field(default=None, max_length=50)
    price: float = Field(default=0.0, ge=0)
    threshold: int = Field(default=5, ge=0)


class VariantCreate(VariantBase):
    product_id: int


class VariantRead(VariantBase):
    id: int
    product_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class VariantWithProduct(VariantRead):
    product: ProductRead


class InventoryLevelBase(SQLModel):
    variant_id: int
    channel_id: int
    qty: int = Field(ge=0)


class InventoryLevelRead(InventoryLevelBase):
    updated_at: datetime

    class Config:
        from_attributes = True


class InventorySync(SQLModel):
    variant_id: int
    channel_code: str
    qty: int = Field(ge=0)


class InventorySyncResult(SQLModel):
    variant_id: int
    channel_code: str
    qty: int
    updated_at: datetime
    conflict_logged: bool


class ImportBatchCreate(SQLModel):
    filename: str


class ImportBatchRead(SQLModel):
    id: int
    filename: str
    total: int
    ok: int
    errors: int
    created_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ImportErrorRow(SQLModel):
    row: int
    sku: Optional[str]
    error: str


class ImportResult(SQLModel):
    batch_id: int
    total: int
    ok: int
    errors: int
    error_rows: list[ImportErrorRow]


class LowStockAlert(SQLModel):
    variant_id: int
    variant_sku: str
    product_name: str
    size: Optional[str]
    color: Optional[str]
    channel_code: str
    qty: int
    threshold: int


class UserRead(SQLModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(SQLModel):
    access_token: str
    token_type: str