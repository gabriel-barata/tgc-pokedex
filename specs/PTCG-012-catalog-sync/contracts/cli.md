# Contract: `tcg sync catalog`

PTCG-014's worker and the operator call this command.

## Invocation

```text
tcg sync catalog          # inside the image (/app/.venv/bin on PATH)
uv run tcg sync catalog   # from backend/
```

There are no flags (FR-038). Configuration comes from `Settings` (`TCG_POKEDEX_*` env vars or
`backend/.env`), so only `TCG_POKEDEX_DATABASE_URL` matters here. `tcg --help` and
`tcg sync --help` print argparse usage and exit with `0`.

## Exit codes (FR-041)

| Code | Status | Meaning |
|---|---|---|
| `0` | `succeeded` | Run completed with zero set or card failures |
| `1` | `partial` | Run completed with at least one set or card failure |
| `2` | `failed` | Index failure, unexpected error, or the store was unreachable (no run record) |

argparse usage errors exit with `2`, which is argparse's default.

## stdout (FR-039)

The command prints exactly one JSON object: the closed run record, serialized by `SyncRun`.
Nothing is printed when no run record could be created (store unreachable).

```json
{
  "id": "0b6f6a9e-3c2a-4f0e-9a51-6d1c2b7e4f10",
  "kind": "catalog",
  "source": "tcgdex",
  "status": "partial",
  "started_at": "2026-10-11T12:00:00Z",
  "finished_at": "2026-10-11T12:06:41Z",
  "duration_ms": 401000,
  "result": {
    "counts": {
      "series": {"fetched": 10, "created": 10, "updated": 0, "unchanged": 0},
      "sets":   {"fetched": 92, "created": 92, "updated": 0, "unchanged": 0, "skipped": 22, "failed": 0},
      "cards":  {"fetched": 13906, "created": 13906, "updated": 0, "unchanged": 0, "failed": 1}
    },
    "failures": [
      {"kind": "card", "provider_id": "sv01-999", "reason": "HTTP 404"}
    ]
  },
  "error": null
}
```

- `result` is always present on a closed run, with all-zero counts after an index abort.
- `failures` holds at most 100 entries, in the order they happened. The counts stay exact.
- `error` is a string only when `status` is `failed`, and `null` otherwise.

## stderr (FR-040)

stderr gets one JSON object per line. Every line has `event`, `level` and `time` (UTC ISO
8601).

| `event` | Extra fields | When |
|---|---|---|
| `sync.run.started` | `run_id`, `kind` | After the run record is committed |
| `sync.failure` | `run_id`, `kind`, `provider_id`, `reason` | Every set or card failure, uncapped |
| `sync.run.finished` | `run_id`, `status`, `duration_ms`, `counts`, `error` | After the run record is closed |
| `sync.run.error` | `error` | The store is unreachable at start, or the run record cannot be closed |

## Failure reasons

Reasons are short, stable strings: `HTTP <code>`, `HTTP <code> after 3 attempts`,
`timeout after 3 attempts`, `network error after 3 attempts`,
`invalid payload: <field>: <message>`, `no variants`.
