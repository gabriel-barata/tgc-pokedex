# Implementation Plan: Catalog sync from TCGdex (sets & cards)

**Branch**: `PTCG-012-catalog-sync` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/PTCG-012-catalog-sync/spec.md`

## Summary

A `tcg sync catalog` console command copies the TCGdex `pt` physical catalog (series, sets,
cards and their variants) into Postgres. It records each run in a generic `sync_runs` table,
prints the closed run as JSON, and exits `0`, `1` or `2` by status.

The work happens in a new `catalog_sync` slice:

- A pure domain decides the Pocket rule, the created/updated/unchanged classification, the
  counts, the 100-failure cap and the status.
- A synchronous service walks series → sets → cards through two ports.
- A TCGdex adapter (`httpx2`, 8 threads, 3 attempts with backoff, Pydantic payload models)
  implements the provider port.
- A Postgres adapter (SQLAlchemy Core, one transaction per set, upserts and no deletes)
  implements the repository port.

## Technical Context

**Language/Version**: Python 3.13 (backend only, no frontend change)

**Primary Dependencies**: SQLAlchemy 2 Core, psycopg 3, Alembic, Pydantic 2 and
pydantic-settings (all present). `httpx2` moves from dev to runtime (R1). The CLI uses
`argparse` and logging uses `logging`, both from the standard library.

**Storage**: PostgreSQL 17. New tables `series`, `sets`, `cards` and `sync_runs` in migration
`0002` (expand-only).

**Testing**: pytest. Postgres via Testcontainers. Provider fixtures via `httpx2.MockTransport`
over recorded JSON. `FakeClock` and an instant sleep recorder.

**Target Platform**: Linux container (production image) and the developer machine
(`uv run`).

**Project Type**: web service backend + CLI command (this feature adds only the CLI part).

**Performance Goals**: a full live sync (about 14,000 requests) in under 15 minutes (SC-006).
Estimated at about 6 minutes (R3).

**Constraints**: ≤ 8 requests in flight, 10 s timeout, 3 attempts, identifying user agent
(FR-027). One transaction per set (FR-023). No deletes (FR-020). No real network in tests.

**Scale/Scope**: 10 to 11 physical series, 114 physical sets (92 with cards), about 13,900
cards, one run per schedule tick (PTCG-014).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / gate | How this plan complies | Status |
|---|---|---|
| I. TDD | Each task pair is a `test:` commit and then a `feat:` commit. `tasks.md` lists tests first. Fixtures live under `backend/tests/` and the code under `backend/src/` and `backend/migrations/`, which the TDD gate already covers, so `check-tdd-order.sh` needs no path change. | ✅ |
| II. DRY | Payload schemas and the provider→domain mapping live in one module (`tcgdex_payloads.py`). The Pocket rule is one function. `SyncRun`/`SyncResult` define both the stored and the printed shape. `Variant` is the only list of variants. Settings are reused. Test fakes and fixture helpers are shared, and assertions stay inline. | ✅ |
| III. Ports & adapters, slices | The `catalog_sync/` slice holds `domain.py` (pure), `ports.py`, `fakes.py` (one fake per port), `service.py`, `command.py` and `adapters/`. Dependencies point inward. `Clock` is reused. | ✅ |
| IV. Own the data | The provider is reached only by the sync command, and every row carries `source` and `fetched_at`. "History appended, never overwritten" is read as applying to time-series data (prices and FX, PTCG-021). Catalog rows hold the current state, and `sync_runs` is the audit trail (FR-019). | ✅ (reading logged below) |
| V. Owner-scoped | Catalog rows and run records are shared reference data, not user-owned (FR-012, FR-036). | ✅ N/A |
| VI. Test strategy | Domain unit tests. Contract suites for `CatalogProvider` (fake + TCGdex over fixtures) and `CatalogRepository` (fake + Postgres). Adapter tests over recorded fixtures and a real Postgres. No real network. Injected clock and sleep. P1 end to end: the in-process command against real Postgres + fixtures (R11). | ✅ (reading logged below) |
| VII. YAGNI | No flags, no incremental mode, no lock, no image or price kinds, no sort key. The test seams are only `transport` and `sleep`. `SyncKind` has only `catalog`. | ✅ |
| Security | No secrets. All provider input is validated by the Pydantic payload models at the boundary. `Settings` validates configuration. | ✅ |
| Observability | One structured JSON result (counts, duration), JSON log lines for every failure, run records. | ✅ |
| Gate 3: lint/types | Strict pyright, ruff. No suppressions planned. | ✅ |
| Gate 4: new deps | `httpx2` becomes a runtime dependency. Justified in R1. No other new package. | ✅ |
| Gate 5: analyze | `/speckit-analyze` runs before `/speckit-implement`. | pending |

**Post-design re-check (after Phase 1)**: no new violations. The design keeps concurrency and
retries inside the adapter. The fakes stay synchronous and deterministic, and the domain
decides every count. Both readings below are unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/PTCG-012-catalog-sync/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0: R1–R11
├── data-model.md        # Phase 1: domain types, tables, mapping
├── quickstart.md        # Phase 1: validation guide
├── contracts/
│   ├── cli.md           # command, stdout JSON, stderr events, exit codes
│   └── ports.md         # CatalogProvider and CatalogRepository contracts
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml                       # httpx2 → runtime deps; [project.scripts] tcg
├── migrations/versions/
│   └── 0002_create_catalog_and_sync_runs.py
├── src/tcg_pokedex/
│   ├── cli.py                           # `tcg` argparse entry point → sync catalog
│   ├── schema.py                        # + catalog_sync tables
│   └── catalog_sync/
│       ├── __init__.py
│       ├── domain.py                    # entities, Variant, is_pocket_series, classify,
│       │                                #   plan_set, ResultBuilder, SyncResult, SyncRun
│       ├── ports.py                     # CatalogProvider, CatalogRepository, ProviderUnavailable
│       ├── fakes.py                     # InMemoryCatalogProvider, InMemoryCatalogRepository
│       ├── service.py                   # sync_catalog(provider, repository, clock) -> SyncRun
│       ├── command.py                   # composition root, JSON logging, exit codes
│       └── adapters/
│           ├── __init__.py
│           ├── tcgdex.py                # TcgdexProvider: client, threads, retries
│           ├── tcgdex_payloads.py       # Pydantic payload models + mapping
│           ├── tables.py                # series, sets, cards, sync_runs
│           └── postgres.py              # PostgresCatalogRepository
└── tests/
    ├── test_migrations.py               # + new tables in the expected schema
    └── catalog_sync/
        ├── tcgdex_fixtures.py           # MockTransport route table + request log
        ├── fixtures/tcgdex/             # recorded + hand-made JSON, README.md
        ├── test_domain.py
        ├── test_service.py
        ├── test_tcgdex_payloads.py
        ├── test_tcgdex_provider.py
        ├── test_catalog_provider_contract.py
        ├── test_catalog_repository_contract.py
        ├── test_command.py              # P1 end to end (US1, US2) + index abort
        └── test_cli.py

.github/workflows/ci.yml                 # image smoke test: `tcg --help`
CLAUDE.md                                # Commands: `uv run tcg sync catalog`
```

**Structure Decision**: the slice follows `clock/` and `owners/`. Tables sit in
`adapters/tables.py` and are imported into `schema.py`. `cli.py` sits at the package root,
like `migrations.py`, because later slices (PTCG-013, PTCG-021) add their own `sync`
subcommands. The run-record code stays in `catalog_sync` until a second slice writes it
(FR-036).

## Service flow (reference for tasks)

1. `run = SyncRun(running, started_at=clock.now())` → `repository.start_run(run)`. If this
   fails, the command logs `sync.run.error` and exits `2`, and the provider is never called.
2. Read the whole index: `list_series_ids()` → for each id that is not
   `is_pocket_series(id)` → `list_set_ids(id)`. `ProviderUnavailable` closes the run as
   `failed` with zero counts and no catalog writes.
3. For each set id:
   - `fetch_set` → if it returns a `Failure`, record it and go on.
   - If `card_ids` is empty, count the set as `skipped`.
   - Otherwise `fetch_cards`, then record the card failures, then `load_stored`, then
     `plan_set`, then `save_set(batch, fetched_at=run.started_at)`, and only then apply the
     classifications to the counts.
4. Any unexpected exception closes the run as `failed` with `str(exc)`. Sets already
   committed stay committed.
5. `repository.finish_run(closed run)`, then log `sync.run.finished`, print the run JSON, and
   exit with the code for its status.

## Complexity Tracking

| Deviation / reading | Why needed | Simpler alternative rejected because |
|---|---|---|
| Principle VI end to end "through the real UI" for P1 stories: met by running the `tcg` command in-process against real Postgres + recorded fixtures (no browser) | The feature has no UI. Its user surface is a command, its stdout JSON and its exit code. | A Playwright test would have no screen to drive. A subprocess test of the installed script would need network isolation for TCGdex that the in-process fixture transport already gives. The image check covers the installed script. |
| Principle IV "history appended, never overwritten" read as applying to time-series data. Catalog rows are upserted to current state (FR-019) | Catalog corrections are not history. Ownership (PTCG-017) points at the current card ids. `sync_runs` keeps the audit of each sync. | Versioned catalog rows would double the read paths of every catalog feature for data nobody needs, which is a YAGNI violation. |
