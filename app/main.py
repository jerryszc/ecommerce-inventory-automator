from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import engine, create_db_and_tables
from app.models import Channel, User
from app.routers import products, variants, channels, inventory, imports, alerts, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(auth.router)
    app.include_router(products.router)
    app.include_router(variants.router)
    app.include_router(channels.router)
    app.include_router(inventory.router)
    app.include_router(imports.router)
    app.include_router(alerts.router)

    return app


app = create_app()