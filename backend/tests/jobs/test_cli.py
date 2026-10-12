import pytest

from tcg_pokedex import cli
from tcg_pokedex.config import Settings


@pytest.mark.parametrize("target", ["catalog", "images", "all"])
def test_tcg_sync_runs_the_target_and_exits_with_its_code(
    monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    calls: list[str] = []

    def fake_run(chosen: str, _settings: Settings) -> int:
        calls.append(chosen)
        return 1

    monkeypatch.setattr(cli, "run_sync", fake_run)

    with pytest.raises(SystemExit) as exited:
        cli.main(["sync", target])

    assert exited.value.code == 1
    assert calls == [target]
