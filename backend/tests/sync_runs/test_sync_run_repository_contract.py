"""Contract every SyncRunRepository must honour, run on the fake and the real one."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tcg_pokedex.catalog_sync.domain import (
    CardCounts,
    Failure,
    KindCounts,
    SetCounts,
    SyncCounts,
    SyncResult,
)
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.migrations import upgrade_to_head
from tcg_pokedex.sync_runs.adapters.postgres import PostgresSyncRunRepository
from tcg_pokedex.sync_runs.domain import RunStatus, SyncKind, SyncRun
from tcg_pokedex.sync_runs.fakes import InMemorySyncRunRepository
from tcg_pokedex.sync_runs.ports import SyncRunRepository

STARTED_AT = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def make_fake_repository(_request: pytest.FixtureRequest) -> SyncRunRepository:
    return InMemorySyncRunRepository()


def make_postgres_repository(request: pytest.FixtureRequest) -> SyncRunRepository:
    database_url: str = request.getfixturevalue("empty_database_url")
    upgrade_to_head(database_url)
    engine = create_database_engine(database_url)
    request.addfinalizer(engine.dispose)
    return PostgresSyncRunRepository(engine)


@pytest.fixture(
    params=[make_fake_repository, make_postgres_repository], ids=["fake", "postgres"]
)
def repository(request: pytest.FixtureRequest) -> SyncRunRepository:
    factory: Callable[[pytest.FixtureRequest], SyncRunRepository] = request.param
    return factory(request)


def test_a_run_is_stored_open_then_closed(repository: SyncRunRepository) -> None:
    run = SyncRun[SyncResult](
        id=uuid4(),
        kind=SyncKind.CATALOG,
        status=RunStatus.RUNNING,
        started_at=STARTED_AT,
    )
    closed = run.model_copy(
        update={
            "status": RunStatus.PARTIAL,
            "finished_at": STARTED_AT + timedelta(seconds=2),
            "duration_ms": 2000,
            "result": SyncResult(
                counts=SyncCounts(
                    series=KindCounts(fetched=1, created=1, updated=0, unchanged=0),
                    sets=SetCounts(
                        fetched=1,
                        created=1,
                        updated=0,
                        unchanged=0,
                        skipped=0,
                        failed=0,
                    ),
                    cards=CardCounts(
                        fetched=1, created=1, updated=0, unchanged=0, failed=1
                    ),
                ),
                failures=(
                    Failure(kind="card", provider_id="sv01-003", reason="HTTP 404"),
                ),
            ),
        }
    )

    repository.start_run(run)
    assert repository.get_run(run.id, SyncResult) == run

    repository.finish_run(closed)
    assert repository.get_run(run.id, SyncResult) == closed
    assert repository.get_run(uuid4(), SyncResult) is None
