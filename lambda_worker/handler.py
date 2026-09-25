import json
import logging
from app.services.aws_sqs import process_import_job
from app.db.session import engine
from sqlmodel import Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def handler(event, context):
    """Lambda handler para procesar jobs de SQS."""
    logger.info("lambda_started", records=len(event.get("Records", [])))

    results = []
    for record in event["Records"]:
        try:
            body = json.loads(record["body"])
            result = process_import_job(body)
            results.append({"status": "success", "batch_id": result.get("batch_id")})
        except Exception as e:
            logger.error("job_failed", error=str(e), record=record)
            results.append({"status": "error", "error": str(e)})

    return {"statusCode": 200, "body": json.dumps({"results": results})}