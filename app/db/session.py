from collections.abc import Iterator
from sqlmodel import SQLModel, Session, create_engine
from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def create_db_and_tables() -> None:
    # Phase 1: no models yet; creates nothing but validates metadata wiring.
    SQLModel.metadata.create_all(engine)
