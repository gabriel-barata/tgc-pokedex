"""What every `tcg sync …` command shares: exit codes and JSON-lines logging."""

import json
import logging
import sys
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime

from tcg_pokedex.sync_runs.domain import RunStatus

EXIT_CODES = {RunStatus.SUCCEEDED: 0, RunStatus.PARTIAL: 1, RunStatus.FAILED: 2}
STORE_ERROR_EXIT_CODE = EXIT_CODES[RunStatus.FAILED]

app_logger = logging.getLogger("tcg_pokedex")


class JsonLineFormatter(logging.Formatter):
    """One JSON object per record: `event`, `level`, `time` and the record's fields."""

    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, object] = record.__dict__.get("fields", {})
        return json.dumps(
            {
                "event": record.getMessage(),
                "level": record.levelname,
                "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
                **fields,
            },
            ensure_ascii=False,
        )


@contextmanager
def json_lines_on_stderr() -> Generator[None]:
    """Send the app's log only to stderr, as JSON lines, while the block runs."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonLineFormatter())
    previous_level, previous_propagate = app_logger.level, app_logger.propagate
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    try:
        yield
    finally:
        app_logger.removeHandler(handler)
        app_logger.setLevel(previous_level)
        app_logger.propagate = previous_propagate
