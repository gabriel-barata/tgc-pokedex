"""The engine, and `migrate`, which brings a database to the latest Atlas revision."""

import subprocess
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, create_engine, inspect, make_url

CONNECT_TIMEOUT_SECONDS = 3
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
ALEMBIC_TABLE = "alembic_version"
ATLAS_TABLE = "atlas_schema_revisions"


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


def migrate(database_url: str, migrations_dir: Path = MIGRATIONS_DIR) -> None:
    """Apply the pending migrations; a no-op when the database is up to date.

    A database Alembic built, with no Atlas revisions yet, is baselined at the first
    migration instead: that migration is recorded as applied and nothing is run.
    """
    command = [
        "atlas",
        "migrate",
        "apply",
        "--dir",
        f"file://{migrations_dir}",
        "--url",
        _atlas_url(database_url),
    ]
    if _is_alembic_database(database_url):
        command += ["--baseline", _baseline_version(migrations_dir)]
    subprocess.run(command, check=True)  # noqa: S603


def _atlas_url(database_url: str) -> str:
    url = make_url(database_url).set(drivername="postgresql")
    query = {"sslmode": "disable", **url.query, "search_path": "public"}
    return url.set(query=query).render_as_string(hide_password=False)


def _is_alembic_database(database_url: str) -> bool:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        return inspector.has_table(ALEMBIC_TABLE) and not inspector.has_table(
            ATLAS_TABLE
        )
    finally:
        engine.dispose()


def _baseline_version(migrations_dir: Path) -> str:
    first = min(migrations_dir.glob("*.sql"))
    return first.stem.split("_", 1)[0]
