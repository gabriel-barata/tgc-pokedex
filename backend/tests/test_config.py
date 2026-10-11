from pathlib import Path

import pytest
from pydantic import ValidationError

from tcg_pokedex.config import Settings


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Run each test in an empty directory (no .env) with no TCG_POKEDEX_* set."""
    monkeypatch.delenv("TCG_POKEDEX_ENVIRONMENT", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_environment_defaults_to_dev() -> None:
    assert Settings().environment == "dev"


def test_environment_is_read_from_prefixed_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TCG_POKEDEX_ENVIRONMENT", "prod")

    assert Settings().environment == "prod"


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TCG_POKEDEX_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        Settings()


def test_dotenv_file_is_read_and_unrelated_keys_are_ignored(
    isolated_config: Path,
) -> None:
    (isolated_config / ".env").write_text(
        "POSTGRES_PASSWORD=unrelated\nTCG_POKEDEX_ENVIRONMENT=prod\n"
    )

    assert Settings().environment == "prod"
