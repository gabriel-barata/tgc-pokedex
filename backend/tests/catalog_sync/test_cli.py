import pytest

from tcg_pokedex import cli
from tcg_pokedex.clock.ports import Clock
from tcg_pokedex.config import Settings


def test_sync_catalog_runs_the_sync_and_exits_with_its_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(_settings: Settings, _clock: Clock) -> int:
        return 1

    monkeypatch.setattr(cli, "run_catalog_sync", fake_run)

    with pytest.raises(SystemExit) as exited:
        cli.main(["sync", "catalog"])

    assert exited.value.code == 1
