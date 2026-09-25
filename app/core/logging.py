import structlog
import logging
import sys
import watchtower
import boto3
from app.core.config import settings


def _try_cloudwatch_handler():
    """Try to create CloudWatch handler, return None if not available."""
    try:
        handler = watchtower.CloudWatchLogHandler(
            log_group="ecommerce-api",
            stream_name="api-logs",
            boto3_client=boto3.client(
                "logs",
                endpoint_url=settings.aws_endpoint_url,
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            ),
            create_log_group=True,
        )
        # Test connection
        handler._ensure_log_group()
        return handler
    except Exception:
        # CloudWatch not available (LocalStack not running, no AWS creds, etc.)
        return None


def configure_logging() -> None:
    """Configure structured logging with structlog + optional CloudWatch."""
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    # Console handler (always available)
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
        foreign_pre_chain=shared_processors,
    )
    console_handler.setFormatter(console_formatter)

    # CloudWatch handler (optional)
    cw_handler = None
    if settings.aws_endpoint_url or settings.app_env != "local":
        cw_handler = _try_cloudwatch_handler()
        if cw_handler:
            cw_formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer(),
                foreign_pre_chain=shared_processors,
            )
            cw_handler.setFormatter(cw_formatter)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handlers = [console_handler]
    if cw_handler:
        handlers.append(cw_handler)

    root_logger = logging.getLogger()
    root_logger.handlers = handlers
    root_logger.setLevel(logging.INFO)

    # Reduce noise from noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("watchtower").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class RequestLoggingMiddleware:
    """Middleware to log requests with structured logging."""

    def __init__(self, app):
        self.app = app
        self.logger = get_logger("request")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import time
        start_time = time.time()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                process_time = time.time() - start_time
                self.logger.info(
                    "http_request",
                    method=scope.get("method"),
                    path=scope.get("path"),
                    status_code=message.get("status"),
                    process_time_ms=round(process_time * 1000, 2),
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)