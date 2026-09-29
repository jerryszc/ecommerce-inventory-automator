from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import desc
from sqlmodel import Session, select

from app.core.config import settings
from app.core.deps import require_admin, require_operator_or_admin
from app.db.session import get_session
from app.models import ImportBatch, User
from app.schemas import ImportBatchRead, ImportResult
from app.services.aws_sqs import upload_s3
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

    # Keep a copy in S3 as the raw record of what arrived, then import the
    # bytes directly so the caller gets the real per-row result. The queue is
    # used by the worker path for large files; enqueueing here as well would
    # mean importing the same file twice.
    s3_key = f"raw/{file.filename}"
    upload_s3(settings.s3_bucket_imports, s3_key, file_bytes)

    result = import_stock(session, file.filename, file_bytes)
    session.commit()

    return result


@router.get("/", response_model=list[ImportBatchRead])
def list_imports(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> list[ImportBatch]:
    return session.exec(select(ImportBatch).order_by(desc(ImportBatch.created_at))).all()


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
