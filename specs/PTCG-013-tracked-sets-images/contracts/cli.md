# Contract: `tcg sync images`

PTCG-014's worker and the operator call this command. It follows the conventions of
`tcg sync catalog` (`specs/PTCG-012-catalog-sync/contracts/cli.md`); only the differences are
listed here.

## Invocation

```text
tcg sync images          # inside the image
uv run tcg sync images   # from backend/
```

No flags (FR-010). It reads `TCG_POKEDEX_DATABASE_URL` and `TCG_POKEDEX_IMAGE_DIR`.

## What one run does

1. Check that the image directory can be created and written. If not, the run is `failed`.
2. For each set tracked by at least one owner (FR-005): resolve every card's image by the
   `plan_card` rule (data-model.md).
3. For each stored set, tracked or not: fetch each logo and symbol the catalog references and
   the cache does not hold yet (FR-011).

## Exit codes

| Code | Status | Meaning |
|---|---|---|
| `0` | `succeeded` | No card, logo or symbol failed |
| `1` | `partial` | At least one failed download |
| `2` | `failed` | The image directory is unusable, an unexpected error, or the store is unreachable (no run record) |

"None at the provider" (a 404, or no URL in the catalog) is `unavailable`, never a failure.

## stdout

One JSON object, the closed `SyncRun` with kind `images`:

```json
{
  "id": "6f1d3b9e-2a7c-4c1e-8d0f-1b2c3d4e5f60",
  "kind": "images",
  "source": "tcgdex",
  "status": "partial",
  "started_at": "2026-10-12T12:00:00Z",
  "finished_at": "2026-10-12T12:01:10Z",
  "duration_ms": 70000,
  "result": {
    "set_id": null,
    "counts": {
      "cards":   {"downloaded": 250, "cached": 258, "unavailable": 46, "failed": 1},
      "artwork": {"downloaded": 4, "cached": 180, "unavailable": 44, "failed": 0}
    },
    "failures": [
      {"kind": "card", "provider_id": "sv02-017", "reason": "HTTP 500 after 3 attempts"}
    ]
  },
  "error": null
}
```

A track-triggered run has the same shape with `"set_id": "<id>"` and artwork counts of zero.
It is only recorded and logged; nothing is printed.

## stderr events

JSON lines, as in the catalog sync: `sync.run.started`, `sync.failure` (`kind`, `provider_id`,
`reason`), `sync.run.finished` (`status`, `duration_ms`, `counts`, `error`) and
`sync.run.error`.
