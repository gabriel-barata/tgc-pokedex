import json
import runpy
from typing import Any

import pytest


def run_openapi_module(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    runpy.run_module("tcg_pokedex.openapi", run_name="__main__")
    return json.loads(capsys.readouterr().out)


def test_module_prints_the_openapi_schema(capsys: pytest.CaptureFixture[str]) -> None:
    schema = run_openapi_module(capsys)

    assert "/healthz" in schema["paths"]


def test_schema_is_printed_even_when_prod_hides_api_docs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TCG_POKEDEX_ENVIRONMENT", "prod")

    schema = run_openapi_module(capsys)

    assert "/healthz" in schema["paths"]
