import pytest

from tcg_pokedex import cli
from tcg_pokedex.clock.adapters.system import SystemClock
from tcg_pokedex.clock.ports import Clock
from tcg_pokedex.config import Settings


def test_sync_catalog_runs_the_sync_and_exits_with_its_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Settings, Clock]] = []

    def fake_run(settings: Settings, clock: Clock) -> int:
        calls.append((settings, clock))
        return 1

    monkeypatch.setattr(cli, "run_catalog_sync", fake_run)

    with pytest.raises(SystemExit) as exited:
        cli.main(["sync", "catalog"])

    assert exited.value.code == 1
    assert len(calls) == 1
    settings, clock = calls[0]
    assert settings == Settings()
    assert isinstance(clock, SystemClock)


def test_help_lists_the_sync_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        cli.main(["--help"])

    assert exited.value.code == 0
    assert "sync" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [[], ["sync"], ["sync", "nope"]])
def test_an_incomplete_or_unknown_command_is_a_usage_error(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        cli.main(argv)

    assert exited.value.code == 2
