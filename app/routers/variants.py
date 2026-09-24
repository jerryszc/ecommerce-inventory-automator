from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.core.deps import get_current_user, require_admin, require_operator_or_admin
from app.db.session import get_session
from app.models import Product, Variant, User
from app.schemas import VariantCreate, VariantRead, VariantWithProduct

router = APIRouter(prefix="/variants", tags=["variants"])


@router.post("/", response_model=VariantRead, status_code=status.HTTP_201_CREATED)
def create_variant(
    variant_in: VariantCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_admin)],
) -> Variant:
    product = session.get(Product, variant_in.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    existing = session.exec(
        select(Variant).where(Variant.sku == variant_in.sku)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Variant SKU already exists")
    variant = Variant.model_validate(variant_in)
    session.add(variant)
    session.commit()
    session.refresh(variant)
    return variant


@router.get("/", response_model=list[VariantRead])
def list_variants(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    product_id: int | None = Query(None),
    size: str | None = Query(None),
    color: str | None = Query(None),
    low_stock: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[Variant]:
    stmt = select(Variant)
    if product_id:
        stmt = stmt.where(Variant.product_id == product_id)
    if size:
        stmt = stmt.where(Variant.size == size)
    if color:
        stmt = stmt.where(Variant.color == color)
    if low_stock:
        stmt = stmt.where(Variant.threshold > 0)
    return session.exec(stmt.offset(skip).limit(limit)).all()


@router.get("/{variant_id}", response_model=VariantWithProduct)
def get_variant(
    variant_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> Variant:
    variant = session.get(Variant, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return variant


@router.delete("/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(
    variant_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    variant = session.get(Variant, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    session.delete(variant)
    session.commit()