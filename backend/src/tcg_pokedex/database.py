from fastapi import Request
from sqlalchemy import Engine, MetaData, create_engine

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)
"""Shared by every slice's tables, so Alembic sees the whole schema."""

CONNECT_TIMEOUT_SECONDS = 3


def create_database_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


def get_engine(request: Request) -> Engine:
    """FastAPI dependency returning the engine create_app stored on the app."""
    engine: Engine = request.app.state.engine
    return engine
