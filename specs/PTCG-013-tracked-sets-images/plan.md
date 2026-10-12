# Implementation Plan: Tracked sets & local image cache

**Branch**: `PTCG-013-tracked-sets-images` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/PTCG-013-tracked-sets-images/spec.md`

## Summary

The owner tracks a set through `PUT /api/sets/{set_id}/tracking`. The app records it,
starts a background `images` run for that set, and returns at once. The run downloads each
card's small and large WebP from TCGdex (pt first, then the English card's image, otherwise
unavailable) into a file directory on a persistent volume and records each card's language
and fetched-at time. `tcg sync images` catches up every tracked set and caches every stored
set's logo and symbol. The app serves all of these from `/api/images/...` with cache headers
and never calls the provider while serving.

The work is a new `image_cache` slice plus two refactors that PTCG-012 anticipated: run
records move to a shared `sync_runs` package (R8), and the TCGdex HTTP policy moves to a
shared `tcgdex` module (R3).

## Technical Context

**Language/Version**: Python 3.13 (backend). The frontend changes only in the regenerated
API files.

**Primary Dependencies**: FastAPI (`BackgroundTasks`, `FileResponse`), SQLAlchemy 2 Core,
psycopg 3, Alembic, Pydantic 2, `httpx2`. All present; no new dependency.

**Storage**: PostgreSQL 17, with new tables `tracked_sets`, `card_images` and `set_artwork` in
migration `0003` (expand-only). Image files go under `TCG_POKEDEX_IMAGE_DIR`, a named volume
`/data/images` in production (R5).

**Testing**: pytest, with Testcontainers Postgres, the TCGdex `MockTransport` route table
(moved to `tests/tcgdex/`, absolute URLs), a 1×1 WebP fixture, `tmp_path` image
directories, `FakeClock` and FastAPI `TestClient`.

**Target Platform**: Linux container on the home server, and the developer machine.

**Project Type**: web service (API routes) + CLI command.

**Performance Goals**: a 250-card set fully cached within 10 minutes of tracking (SC-001).
About 500 requests at 8 in flight is estimated at under 1 minute (R4).

**Constraints**: no provider call at request time (Principle IV). ≤ 8 requests in flight,
3 attempts and an identifying user agent, shared with the catalog sync. Atomic writes,
with both sizes of a card or neither. No deletes. No real network in tests.

**Scale/Scope**: about 92 sets with cards, ~250 cards per set, ~92 KB per card (~1.3 GB if
every set were tracked), and two artwork files per set.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / gate | How this plan complies | Status |
|---|---|---|
| I. TDD | Every behavior lands as a `test:` commit then a `feat:` commit. The two refactors (R3, R8) are `refactor:` commits that keep the existing tests green. Code under `backend/src`, `backend/migrations` and tests under `backend/tests` are already covered by `check-tdd-order.sh`. | ✅ |
| II. DRY | `plan_card` is the only copy of the pt → en → unavailable rule. `run_status` and `EXIT_CODES` exist once in `sync_runs`. The TCGdex retry policy exists once (`tcgdex/http.py`). The `/univ/` → `/pt/` quirk is handled only in the image adapter. API schemas are Pydantic models exported through OpenAPI to the generated client. The fixture route table is shared. | ✅ |
| III. Ports & adapters, slices | `image_cache/` holds `domain.py` (pure), `ports.py`, `fakes.py`, `service.py`, `command.py`, `api/routes.py` and `adapters/`. Ports: `ImageProvider`, `ImageStore`, `ImageCacheRepository`, plus `SyncRunRepository` in `sync_runs/`. One fake each. | ✅ |
| IV. Own the data | Images reach us only during sync runs (command or track-triggered background run). Serving reads files only. `card_images` and `set_artwork` carry `source` and `fetched_at`. A pt upgrade replaces an English image: the current image is not history (same reading as PTCG-012). | ✅ (reading logged) |
| V. Owner-scoped | `tracked_sets` has `owner_id`. The routes take the owner from one dependency, and tests check that one owner's tracking does not show as another's. Images and artwork are shared reference data. | ✅ |
| VI. Test strategy | Domain unit tests (`plan_card`, result builder). Contract suites for all four ports (fake + real). Provider adapter over recorded fixtures. Postgres adapters on a real database. File store on `tmp_path`. Injected clock. P1 end to end in process via `TestClient` (R11). Main behaviors only. | ✅ (reading logged) |
| VII. YAGNI | No flags, no resize, no eviction, no cross-process lock, no list endpoint, no version-stamped URLs. The download registry is a locked `set`. | ✅ |
| Security | No secrets. Path ids are percent-encoded and `.`/`..` are rejected. Provider bodies are checked for WebP and a 5 MB cap. The English card payload is validated by a Pydantic model. `image_dir` is validated by `Settings`. | ✅ |
| Accessibility | No UI. Alt text is PTCG-016's job. | N/A |
| Observability | Structured run result (downloaded, cached, unavailable, failed, duration), JSON log lines per failure, `sync_runs` record for every run, including track-triggered ones. | ✅ |
| Gate 3: lint/types | Strict pyright, ruff. No suppressions planned. | ✅ |
| Gate 4: new deps | None. | ✅ |
| Gate 5: analyze | `/speckit-analyze` before `/speckit-implement`. | pending |

**Post-design re-check (after Phase 1)**: no new violations. The fallback rule sits in the
pure domain and the service, the adapter only reports `Missing` or a failure, and the
in-process registry adds no stale state. The readings below are unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/PTCG-013-tracked-sets-images/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0: R1–R12
├── data-model.md        # Phase 1: domain types, plan_card rule, tables, files
├── quickstart.md        # Phase 1: validation guide
├── contracts/
│   ├── api.md           # tracking and image routes
│   ├── cli.md           # tcg sync images
│   └── ports.md         # SyncRunRepository, ImageProvider, ImageStore, ImageCacheRepository
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── .gitignore / ../.gitignore           # + backend/data/
├── migrations/versions/
│   └── 0003_create_tracked_sets_and_images.py
├── src/tcg_pokedex/
│   ├── app.py                           # + image_cache router, DownloadRegistry, image store
│   ├── cli.py                           # + `sync images`
│   ├── config.py                        # + image_dir
│   ├── schema.py                        # + new tables, sync_runs import moved
│   ├── tcgdex/                          # R3 (refactor)
│   │   ├── __init__.py
│   │   └── http.py                      # TcgdexHttp, RequestFailedError, USER_AGENT
│   ├── sync_runs/                       # R8 (refactor)
│   │   ├── __init__.py
│   │   ├── domain.py                    # SyncKind, RunStatus, SyncRun[R], run_status
│   │   ├── ports.py                     # SyncRunRepository
│   │   ├── fakes.py
│   │   ├── command.py                   # EXIT_CODES, JSON-lines logging set-up
│   │   └── adapters/{tables,postgres}.py
│   ├── catalog_sync/                    # uses tcgdex/ and sync_runs/; behavior unchanged
│   └── image_cache/
│       ├── __init__.py
│       ├── domain.py                    # types, plan_card, ImageResultBuilder
│       ├── ports.py                     # ImageProvider, ImageStore, ImageCacheRepository
│       ├── fakes.py
│       ├── registry.py                  # DownloadRegistry
│       ├── service.py                   # sync_images(..., set_id=None) -> SyncRun
│       ├── command.py                   # composition root of `tcg sync images`
│       ├── api/routes.py                # tracking + image routes, owner dependency
│       └── adapters/
│           ├── __init__.py
│           ├── tcgdex.py                # TcgdexImageProvider
│           ├── files.py                 # FileImageStore
│           ├── tables.py                # tracked_sets, card_images, set_artwork
│           └── postgres.py              # PostgresImageCacheRepository
└── tests/
    ├── tcgdex/fixtures.py               # moved route table, absolute URLs, SleepRecorder
    ├── sync_runs/test_sync_run_repository_contract.py
    ├── catalog_sync/…                   # imports updated only
    └── image_cache/
        ├── fixtures/                    # pixel.webp, en card payloads
        ├── test_domain.py
        ├── test_service.py
        ├── test_tcgdex_image_provider.py
        ├── test_image_provider_contract.py
        ├── test_image_store_contract.py
        ├── test_image_cache_repository_contract.py
        ├── test_command.py              # US3 end to end, exit codes
        └── test_api_end_to_end.py       # US1, US2 through the API (P1 end to end)

frontend/openapi.json, frontend/src/api-schema.gen.ts   # regenerated
Dockerfile                               # /data/images owned by app; TCG_POKEDEX_IMAGE_DIR
deploy/compose.yml                       # images volume at /data/images
deploy/README.md                         # the volume in install/backup notes
.github/workflows/ci.yml                 # image smoke: `tcg sync images --help`
CLAUDE.md                                # Commands: `uv run tcg sync images`, image dir
```

**Structure Decision**: one `image_cache` slice holds both tracking and the cache. In this
ticket tracking exists only to choose which sets to download, and splitting it would need a
cross-slice port for "tracked set ids" and the progress read. PTCG-017 (ownership) can still
build its own `collection_tracking` slice. `tcgdex/` and `sync_runs/` are shared packages
like `clock/` and `owners/`.

## Service flow (reference for tasks)

`sync_images(provider, store, repository, runs, clock, set_id=None) -> SyncRun`:

1. Open an `images` run (`runs.start_run`) and log `sync.run.started`.
2. `store.check_writable()`. `ImageStoreUnavailableError` closes the run as `failed`.
3. Sets = `[set_id]` if given, else `repository.tracked_set_ids()`. For each set:
   `repository.cards_to_resolve(set)`, fill `files_present` from `store.has_card`, apply
   `plan_card`, and resolve the non-skipped cards on the pool (R4). A card that resolves
   writes its files with `store.put_card` in the worker. After the set, call
   `repository.save_card_images(downloaded + unavailable, fetched_at=run.started_at)`
   and record the outcomes.
4. Only when `set_id` is None: for each `artwork_to_fetch()` entry with a URL and no row,
   `provider.fetch_artwork`, then `store.put_artwork` + `repository.save_artwork`, then
   record the outcome.
5. Any unexpected exception aborts the run (`failed`, `str(exc)`). Work already saved stays.
6. Close the run (`runs.finish_run`), log `sync.run.finished`, and return it.

Track route: `set_exists` (404 if not) → `track` → if newly tracked and
`registry.start(set_id)`, add a background task that runs step 1–6 for the set and calls
`registry.finish(set_id)` in a `finally` → return `progress` with `downloading` taken from
the registry.

## Flagged for implementation

- **FIX-1: catalog symbol URLs answer 404 (research R1).** Every `symbol_url` the catalog
  stores is under `/univ/` (e.g. `https://assets.tcgdex.net/univ/sv/sv01/symbol`), and every
  `/univ/…/symbol.webp` probed on 2026-10-12 answered `404`. The same path under `/pt/`
  answers `200`. `/speckit-tasks` MUST give this its own test + fix pair:
  `TcgdexImageProvider.fetch_artwork` retries a `symbol` under `/univ/` that answers 404 once
  under `/pt/`, a recorded-fixture test proves it, and the manual run checks
  `/api/images/sets/sv01/symbol` answers `200`. Re-probe TCGdex at implementation time in
  case they have fixed `/univ/`.
- **Format: WebP is the preferred format.** Card images (`low.webp`, `high.webp`), logos and
  symbols are all requested as `.webp` (research R2). No other format is requested or stored.

## Complexity Tracking

| Deviation / reading | Why needed | Simpler alternative rejected because |
|---|---|---|
| Principle VI end to end "through the real UI" for the P1 story: met in process with `TestClient` on `create_app`, real Postgres, a temp image directory and fixture TCGdex responses | The feature has no screen (the toggle is PTCG-015, the grid PTCG-016). Its user surface is the API. | Playwright would have no page to drive, and the e2e stack has no fake TCGdex to download from. SC-004 stays covered by the e2e origin guard. |
| Principle IV "history appended, never overwritten" read as not applying to the current image: an English image is replaced by the pt one when it appears | The cached image is the current state of reference data, as with catalog rows (PTCG-012). `sync_runs` keeps the audit trail. | Keeping every superseded image would grow the disk for data nobody views. |
| Two refactors of PTCG-012 code (shared `sync_runs`, shared `tcgdex` HTTP) inside this ticket | A second writer of run records and a second TCGdex client appear here. Principle II wants one copy of each. PTCG-012's plan named this ticket as the moment to move run records. | Duplicating them now and extracting later would mean two retry policies and two status rules in the meantime. |
