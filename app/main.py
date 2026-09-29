from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlmodel import Session, select, text
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import RequestLoggingMiddleware, configure_logging
from app.core.rate_limit import distributed_rate_limit
from app.core.security import hash_password
from app.db.session import create_db_and_tables, engine
from app.models import Channel, User
from app.routers import alerts, auth, channels, imports, inventory, metrics, products, variants

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
        )
        # CORSMiddleware only answers a preflight that carries
        # Access-Control-Request-Method. A plain OPTIONS without it gets no
        # allowed-methods header, so declare it here for every preflight.
        if request.method == "OPTIONS":
            response.headers.setdefault(
                "Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
        return response


# Custom rate limit dependency
async def rate_limit_dependency(request: Request, response: Response) -> None:
    allowed, headers = distributed_rate_limit(f"rl:{get_remote_address(request)}")
    # On the response, not by poking at the request's internal header list.
    for k, v in headers.items():
        response.headers[k] = v
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Configure logging on startup
    configure_logging()

    create_db_and_tables()
    with Session(engine) as session:
        # Seed channels
        for code, name in [("amazon", "Amazon"), ("shopify", "Shopify")]:
            existing_channel = session.exec(select(Channel).where(Channel.code == code)).first()
            if not existing_channel:
                session.add(Channel(code=code, name=name))
        # Seed users
        for email, password, role in [
            (settings.admin_email, settings.admin_password, "admin"),
            (settings.operator_email, settings.operator_password, "operator"),
        ]:
            existing_user = session.exec(select(User).where(User.email == email)).first()
            if not existing_user:
                session.add(User(email=email, hashed_password=hash_password(password), role=role))
        session.commit()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # Rate limiting
    app.state.limiter = limiter
    # slowapi types its handler as taking RateLimitExceeded, while Starlette
    # types the parameter as Exception. The handler does receive the specific
    # exception at runtime, so the cast documents that rather than hides it.
    app.add_exception_handler(
        RateLimitExceeded,
        cast("Any", _rate_limit_exceeded_handler),
    )

    # CORS
    # credentials off while origins is the wildcard: the CORS spec forbids
    # combining "*" with credentials, and Starlette then reflects whatever
    # origin asked, which is a weaker and less predictable setup than either
    # of the two real options.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/health")
    @limiter.limit("60/minute")
    def health(request: Request) -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    @app.get("/health/detailed")
    @limiter.limit("30/minute")
    def health_detailed(request: Request) -> dict:
        db_status = "ok"
        try:
            with Session(engine) as session:
                # execute, not exec: exec expects a Select and a raw text
                # clause is not one.
                session.execute(text("SELECT 1"))
        except Exception:
            db_status = "error"
        return {
            "status": "ok",
            "env": settings.app_env,
            "database": db_status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    app.include_router(auth.router)
    app.include_router(products.router)
    app.include_router(variants.router)
    app.include_router(channels.router)
    app.include_router(inventory.router)
    app.include_router(imports.router)
    app.include_router(alerts.router)
    app.include_router(metrics.router)

    return app


app = create_app()
