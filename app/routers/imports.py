from typing import Annotated
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel import Session, select

from app.core.config import settings
from app.core.deps import require_admin, require_operator_or_admin
from app.db.session import get_session
from app.models import ImportBatch, User
from app.schemas import ImportBatchRead, ImportResult, ImportErrorRow
from app.services.importer import import_stock
from app.services.aws_sqs import upload_s3, enqueue_import_job

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
    
    # Subir a S3 primero
    s3_key = f"raw/{file.filename}"
    upload_s3(settings.s3_bucket_imports, s3_key, file_bytes)
    
    # Encolar job asíncrono (user_id=1 como admin por defecto)
    from app.services.aws_sqs import enqueue_import_job
    enqueue_import_job(s3_key, file.filename, user_id=1)
    
    return ImportResult(
        batch_id=0,
        total=0,
        ok=0,
        errors=0,
        error_rows=[ImportErrorRow(row=0, sku=None, error="Procesamiento encolado, revisa /imports/ para resultado")]
    )


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