from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select, text
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.security import hash_password
from app.core.logging import configure_logging, RequestLoggingMiddleware
from app.core.rate_limit import distributed_rate_limit
from app.db.session import engine, create_db_and_tables
from app.models import Channel, User
from app.routers import products, variants, channels, inventory, imports, alerts, auth, metrics


# Rate limiter
limiter = Limiter(key_func=get_remote_address)


# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
        return response


# Custom rate limit dependency
async def rate_limit_dependency(request: Request):
    allowed, headers = distributed_rate_limit(f"rl:{get_remote_address(request)}")
    for k, v in headers.items():
        request.headers.__dict__["_list"].append((k.lower().encode(), v.encode()))
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure logging on startup
    configure_logging()

    create_db_and_tables()
    with Session(engine) as session:
        # Seed channels
        for code, name in [("amazon", "Amazon"), ("shopify", "Shopify")]:
            existing = session.exec(select(Channel).where(Channel.code == code)).first()
            if not existing:
                session.add(Channel(code=code, name=name))
        # Seed users
        for email, password, role in [
            (settings.admin_email, settings.admin_password, "admin"),
            (settings.operator_email, settings.operator_password, "operator"),
        ]:
            existing = session.exec(select(User).where(User.email == email)).first()
            if not existing:
                session.add(User(email=email, hashed_password=hash_password(password), role=role))
        session.commit()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
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
                session.exec(text("SELECT 1"))
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