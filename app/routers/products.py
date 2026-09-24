from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.core.deps import get_current_user, require_admin, require_operator_or_admin
from app.db.session import get_session
from app.models import Product, User
from app.schemas import ProductCreate, ProductRead

router = APIRouter(prefix="/products", tags=["products"])


@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: ProductCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_admin)],
) -> Product:
    existing = session.exec(
        select(Product).where(Product.sku_base == product_in.sku_base)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU base already exists")
    product = Product.model_validate(product_in)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.get("/", response_model=list[ProductRead])
def list_products(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[Product]:
    return session.exec(select(Product).offset(skip).limit(limit)).all()


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> Product:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    session.delete(product)
    session.commit()