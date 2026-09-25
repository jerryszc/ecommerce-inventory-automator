import json
from app.core.aws import get_sqs_client, get_s3_client, upload_s3, download_s3, enqueue_sqs
from app.services.importer import import_from_file_path
from app.db.session import engine
from app.models import ImportBatch
from sqlmodel import Session
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def enqueue_import_job(s3_key: str, filename: str, user_id: int) -> str:
    """Encola job de importación en SQS."""
    return enqueue_sqs(
        settings.sqs_queue_url,
        {
            "s3_key": s3_key,
            "filename": filename,
            "user_id": user_id,
        }
    )


def process_import_job(message_body: dict) -> dict:
    """Procesa un job de importación (ejecutado por Lambda worker)."""
    s3_key = message_body["s3_key"]
    filename = message_body["filename"]
    user_id = message_body["user_id"]

    logger.info("processing_import_job", s3_key=s3_key, filename=filename)

    # 1. Descargar de S3
    bucket = settings.s3_bucket_imports
    file_bytes = download_s3(bucket, s3_key)

    # 2. Procesar (reutiliza lógica existente)
    from io import BytesIO
    with Session(engine) as session:
        result = import_from_file_path(session, filename, file_bytes, user_id)

    # 3. Mover a processed/
    processed_key = s3_key.replace("raw/", "processed/")
    upload_s3(
        settings.s3_bucket_imports,
        processed_key,
        download_s3(settings.s3_bucket_imports, s3_key),
        content_type="text/csv"
    )

    # 4. Borrar original
    get_s3_client().delete_object(Bucket=settings.s3_bucket_imports, Key=s3_key)

    logger.info("import_job_completed", batch_id=result.batch_id, ok=result.ok, errors=result.errors)
    return result.model_dump()