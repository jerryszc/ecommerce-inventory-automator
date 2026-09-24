from typing import Annotated
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel import Session, select

from app.core.deps import require_admin, require_operator_or_admin
from app.db.session import get_session
from app.models import ImportBatch, User
from app.schemas import ImportBatchRead, ImportResult
from app.services.importer import import_stock

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/upload", response_model=ImportResult, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: Annotated[UploadFile, File(...)],
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_admin)],
    created_by: str | None = None,
) -> ImportResult:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    file_bytes = await file.read()
    return import_stock(session, file.filename, file_bytes, created_by)


@router.get("/", response_model=list[ImportBatchRead])
def list_imports(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> list[ImportBatch]:
    return session.exec(select(ImportBatch).order_by(ImportBatch.created_at.desc())).all()


@router.get("/{batch_id}", response_model=ImportBatchRead)
def get_import(
    batch_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> ImportBatch:
    batch = session.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return batch