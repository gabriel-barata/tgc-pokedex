---

description: "Task list for PTCG-013 tracked sets & local image cache"
---

# Tasks: Tracked sets & local image cache

**Input**: Design documents from `/specs/PTCG-013-tracked-sets-images/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, contracts/cli.md, contracts/ports.md, quickstart.md

**Tests**: Mandatory (constitution, Principles I and VI), for the main behaviours only. Every test task is listed before the implementation task it covers, and its test must fail before that task starts.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are relative to the repository root. Backend commands run from `backend/`.

## Conventions for every task

- Slice: `backend/src/tcg_pokedex/image_cache/`; tests: `backend/tests/image_cache/`. Shared packages: `backend/src/tcg_pokedex/tcgdex/` and `backend/src/tcg_pokedex/sync_runs/`.
- No code or config comments (docstrings are fine); no `type X = …` aliases.
- Lean tests: happy path plus the failure paths that matter; prefer one parametrized test over near-duplicates; fixtures trimmed to the fields the code reads.
- Commits: one `test(PTCG-013): …` / `feat(PTCG-013): …` pair per **TDD cycle** listed at the end of each phase, never one per task or per file. Target: about 20 commits for the whole PR.
- Provider HTTP in tests goes only through `backend/tests/tcgdex/fixtures.py` (`httpx2.MockTransport`; unknown URL raises). Time comes from `FakeClock`; retry waits from `SleepRecorder`. Image directories are `tmp_path`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: the two refactors PTCG-012 anticipated (R3, R8) and the shared test fixtures. Behaviour of `tcg sync catalog` is unchanged; `uv run pytest tests/catalog_sync` stays green after each refactor.

- [X] T001 Move the TCGdex HTTP policy out of `backend/src/tcg_pokedex/catalog_sync/adapters/tcgdex.py` into `backend/src/tcg_pokedex/tcgdex/__init__.py` and `backend/src/tcg_pokedex/tcgdex/http.py` (R3): `USER_AGENT`, `TcgdexHttp` (owns the `httpx2.Client` with timeout, `Limits(max_connections=8)`, user agent; `get(url) -> bytes` with 3 attempts, backoff and `Retry-After` through an injected `sleep`; context manager / `close()`), and public `RequestFailedError(reason, status)` replacing `_RequestFailedError`/`_Retry`. `TcgdexProvider` keeps its public API and builds its URLs on top of `TcgdexHttp`. Commit as `refactor(PTCG-013): share the TCGdex HTTP client`.
- [X] T002 Move `backend/tests/catalog_sync/tcgdex_fixtures.py` to `backend/tests/tcgdex/fixtures.py` and let `FixtureRoutes` match absolute URLs (`https://api.tcgdex.net/v2/{lang}/…`, `https://assets.tcgdex.net/…`) as well as the existing `pt` API paths; add a `Reply` that returns raw bytes with a status. Update imports in `backend/tests/catalog_sync/*.py` only. Commit together with T001.
- [X] T003 Move run records into `backend/src/tcg_pokedex/sync_runs/` (R8): `domain.py` (`SyncKind` with `catalog` and `images`, `RunStatus`, `MAX_FAILURES = 100`, generic `SyncRun[R]` over its `result` model with the same JSON shape, `run_status(aborted: bool, failed: int) -> RunStatus` taken from `ResultBuilder.status`), `ports.py` (`SyncRunRepository`: `start_run`, `finish_run`, `get_run(run_id, result: type[R]) -> SyncRun[R] | None`), `fakes.py` (`InMemorySyncRunRepository`), `adapters/tables.py` (the unchanged `sync_runs` table, imported by `backend/src/tcg_pokedex/schema.py`), `adapters/postgres.py` (`PostgresSyncRunRepository`), `command.py` (`EXIT_CODES`, `STORE_ERROR_EXIT_CODE`, `JsonLineFormatter` and the stderr logging set-up as a context manager). Remove `start_run`/`finish_run`/`get_run` from `CatalogRepository`, its fake and its Postgres adapter; `sync_catalog` and `run_catalog_sync` take/build a `SyncRunRepository`; `ResultBuilder.status` calls `run_status`. Move the run items of `backend/tests/catalog_sync/test_catalog_repository_contract.py` into `backend/tests/sync_runs/test_sync_run_repository_contract.py` (params `fake`, `postgres`). No migration. Commit as `refactor(PTCG-013): move run records to a shared sync_runs package`.
- [X] T004 [P] Add `backend/tests/image_cache/fixtures/`: `pixel.webp` (a valid hand-made 1×1 WebP, a few dozen bytes), `en/swshp-SWSH032.json` (recorded from `https://api.tcgdex.net/v2/en/cards/swshp-SWSH032`, trimmed to `id` and `image`), `en/svp-085.no-image.json` (trimmed to `id`, no `image`), and a 5-line `README.md` naming each file's source URL, recording date and what is hand-made. Commit with the first test commit that uses them (T008).
- [X] T005 [P] Add `backend/data/` to `.gitignore`.

**TDD cycles**: none (T001–T003 are `refactor:` commits that keep the existing tests green; T004 lands in a `test:` commit).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the pure domain, and the three image ports, each with its fake, real adapter and contract suite. The schema for tracking lives here because every story reads it.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests (write first) ⚠️

- [X] T006 [P] Unit tests in `backend/tests/image_cache/test_domain.py`: one parametrized test over the full `plan_card` table of data-model.md (`pt`+files → `skip`; `en`+files+no pt URL → `skip`; `en`+files+pt URL → `try_pt_keep_en`; no row / unavailable / files missing + pt URL → `try_pt_then_en`; same without pt URL → `try_en`); `ImageResultBuilder` counts card and artwork outcomes separately, keeps only the first 100 failures while counts stay exact, and its status is `succeeded` with 0 failures, `partial` with ≥ 1, `failed` when aborted; `ImageSyncResult` round-trips through `SyncRun[ImageSyncResult]` JSON with `kind="images"`.
- [X] T007 [P] Contract suite in `backend/tests/image_cache/test_image_store_contract.py`, params `fake` and `file` (`FileImageStore(tmp_path)`): `put_card` then `has_card` is true and both sizes read back; `has_card` is false when only one size exists; `put_artwork` stores a logo; `check_writable` raises `ImageStoreUnavailableError` on a read-only directory. File-only cases in the same module: `card_path`/`artwork_path` return `None` for absent files and for the ids `.` and `..`; an id with `/` is percent-encoded and stays under `image_dir`; a write that fails mid-way leaves no file at the final path.
- [X] T008 [P] Contract suite in `backend/tests/image_cache/test_image_cache_repository_contract.py`, params `fake` and `postgres` (seed `owners`, one series, two sets, cards through SQL or the catalog tables): `set_exists`; `track` returns `True` then `False`; `untrack` is idempotent; `progress` reports `tracked`, `total_cards`, `cached` (rows with a language), `unavailable` (rows with NULL language) and `downloading=False`, and another owner's tracking does not show (Principle V); `tracked_set_ids` lists sets tracked by any owner, once, in catalog order; `cards_to_resolve` returns each card's pt URL and stored row; `save_card_images` upserts (an `en` row becomes `pt`); `artwork_to_fetch` lists every stored set × `logo`/`symbol` with its URL and `cached` flag; `save_artwork` upserts. Commit `backend/tests/image_cache/fixtures/` (T004) here.
- [X] T009 Extend `backend/tests/test_migrations.py`: upgrade also creates `tracked_sets`, `card_images` and `set_artwork`; `command.check` still passes; downgrade to base leaves only `alembic_version`.
- [X] T010 [P] Contract suite in `backend/tests/image_cache/test_image_provider_contract.py`, params `fake` and `tcgdex` (`TcgdexImageProvider` over `FixtureRoutes`): `fetch_card_images` returns `CardImages` when both sizes answer, `Missing` when either answers 404, `ImageFailure(kind="card")` on a 500 ×3; `english_image_url` returns the `image` base, or `None` for a 404 or a payload without `image`; `fetch_artwork` returns bytes, or `Missing` on 404. Adapter-only cases in `backend/tests/image_cache/test_tcgdex_image_provider.py`: requests go to `{base}/low.webp` and `{base}/high.webp` with the shared user agent; a `200` HTML body is `ImageFailure` with reason `not an image`; a body over 5 MB is `too large`.

### Implementation

- [X] T011 Implement `backend/src/tcg_pokedex/image_cache/__init__.py` and `backend/src/tcg_pokedex/image_cache/domain.py` per data-model.md: enums `Language` (`pt`, `en`), `CardSize` (`small`, `large`), `ArtworkKind` (`logo`, `symbol`), `CardPlan` (`skip`, `try_pt_keep_en`, `try_pt_then_en`, `try_en`); frozen `StoredCardImage` (`language: Language | None` — None = unavailable, `fetched_at`), `CardToResolve` (`card_id`, `pt_image_url: str | None`, `stored: StoredCardImage | None`, `files_present: bool`), `CardImages` (`small: bytes`, `large: bytes`), `Missing`, `ArtworkToFetch` (`set_id`, `kind`, `url: str | None`, `cached: bool`), `CardOutcome`; Pydantic `ImageFailure` (`kind: card | logo | symbol`, `provider_id`, `reason`), `ImageCounts` (`downloaded`, `cached`, `unavailable`, `failed`, all `≥ 0`), `ImageSyncResult` (`set_id: str | None`, `counts: {cards, artwork}`, `failures` ≤ 100), `SetTracking` (`set_id`, `tracked`, `total_cards`, `cached`, `unavailable`, `downloading`); `plan_card` (the only copy of the rule) and `ImageResultBuilder` using `run_status` and `MAX_FAILURES` from `sync_runs`. Makes T006 pass.
- [X] T012 Define `backend/src/tcg_pokedex/image_cache/ports.py` exactly as contracts/ports.md (`ImageProvider`, `ImageStore`, `ImageCacheRepository` Protocols, `ImageStoreUnavailableError`), then implement `InMemoryImageStore` in `backend/src/tcg_pokedex/image_cache/fakes.py` and `FileImageStore` in `backend/src/tcg_pokedex/image_cache/adapters/files.py` (layout `cards/{quote(card_id, safe="")}/small.webp|large.webp`, `sets/{quote(set_id, safe="")}/logo.webp|symbol.webp`; reject `.`/`..`; each file written to a temp file in the same directory, `fsync`, `os.replace`; `put_card` writes only after both sizes are in memory). Makes T007 pass.
- [X] T013 Add `backend/src/tcg_pokedex/image_cache/adapters/tables.py` on the shared `metadata` and import it in `backend/src/tcg_pokedex/schema.py`: `tracked_sets` (`owner_id uuid NOT NULL FK owners.id`, `set_id text NOT NULL FK sets.id, indexed`, PK `(owner_id, set_id)`, `tracked_at timestamptz NOT NULL`); `card_images` (`card_id text PK FK cards.id`, `language text NULL` with `CHECK (language IN ('pt','en'))`, `source text NOT NULL`, `fetched_at timestamptz NOT NULL`); `set_artwork` (`set_id text NOT NULL FK sets.id`, `kind text NOT NULL` with `CHECK (kind IN ('logo','symbol'))`, PK `(set_id, kind)`, `source text NOT NULL`, `fetched_at timestamptz NOT NULL`). Write `backend/migrations/versions/0003_create_tracked_sets_and_images.py` (`down_revision = "0002"`, expand-only; downgrade drops the three tables) and confirm with `uv run alembic revision --autogenerate` that nothing is left over. Implement `InMemoryImageCacheRepository` in `backend/src/tcg_pokedex/image_cache/fakes.py` and `PostgresImageCacheRepository` in `backend/src/tcg_pokedex/image_cache/adapters/postgres.py` (`save_card_images` in one transaction, `source = "tcgdex"`). Makes T008 and T009 pass.
- [X] T014 Implement `InMemoryImageProvider` in `backend/src/tcg_pokedex/image_cache/fakes.py` (seeded per base URL / card id / artwork URL with bytes, `Missing` or a failure; records every request; thread-safe) and `TcgdexImageProvider` in `backend/src/tcg_pokedex/image_cache/adapters/tcgdex.py` on `TcgdexHttp`: `{base}/low.webp` + `{base}/high.webp` both fetched before returning, 404 → `Missing`, `RequestFailedError` → `ImageFailure` with its reason, RIFF/WEBP magic check, 5 MB cap; `english_image_url` validates `https://api.tcgdex.net/v2/en/cards/{quote(card_id)}` with a Pydantic model (`image: str | None`); `fetch_artwork` requests `{url}.webp` (no `/univ/` handling yet, see T029). Never raises for one asset. Makes T010 pass.

**TDD cycles**: (T006 → T011), (T007 → T012), (T008, T009 → T013), (T010 → T014).

**Checkpoint**: domain, ports, fakes, adapters and schema ready; user stories can start.

---

## Phase 3: User Story 1 - Track a set and get its images served locally (Priority: P1) 🎯 MVP

**Goal**: `PUT /api/sets/{set_id}/tracking` records the set, starts a background `images` run for it and returns at once; the run caches each card's small and large WebP (pt, else English, else unavailable); the app serves them from `/api/images/cards/...` without calling the provider.

**Independent Test**: `test_api_end_to_end.py`: TestClient on `create_app`, real Postgres, temp image dir, fixture TCGdex. Track a set, then fetch every card image: `200 image/webp` with cache headers, and the transport saw no request while serving.

### Tests for User Story 1 (write first) ⚠️

- [X] T015 [P] [US1] Service tests in `backend/tests/image_cache/test_service.py` on the fakes and `FakeClock`, calling `sync_images(provider, store, repository, runs, clock, set_id="sv01")`: one set with a pt card, an English-only card, a card with no image anywhere and a card whose pt fetch fails → store holds the first two in both sizes, `save_card_images` gets `pt`, `en` and `None` rows with `fetched_at = run.started_at`, the failed card gets no row and no file, run is `partial` with `cards = {downloaded: 2, unavailable: 1, failed: 1}`, `result.set_id == "sv01"`, artwork counts zero and no artwork request; a second run requests nothing for the pt card (counted `cached`, SC-003) and retries the failed one; `check_writable` raising closes the run as `failed` with the error.
- [X] T016 [US1] End-to-end tests in `backend/tests/image_cache/test_api_end_to_end.py` (catalog seeded through `PostgresCatalogRepository.save_set` or SQL; `create_app(Settings(database_url=…, image_dir=tmp_path))` with the app's provider built on the fixture transport): `PUT /api/sets/sv01/tracking` → `200` `SetTracking` with `tracked: true`; after the response (TestClient runs the background task) `GET /api/sets/sv01/tracking` reports `cached` = cards with images, `unavailable` = the rest, `downloading: false`; `GET /api/images/cards/{id}/small` and `/large` → `200`, `image/webp`, `Cache-Control: public, max-age=604800`, an `ETag`, and a matching `If-None-Match` → `304`; the fixture transport logged no request during serving; a second `PUT` starts no download (no new provider request, no new `sync_runs` row); unavailable card image, unknown size → `422`, card id `..` → `404`; unknown set on `GET`/`PUT` → `404`; a run of kind `images` was recorded. Add the `image_dir` case to `backend/tests/test_config.py` (default `data/images`, read from `TCG_POKEDEX_IMAGE_DIR`).

### Implementation for User Story 1

- [X] T017 [US1] Implement `sync_images(provider, store, repository, runs, clock, set_id: str | None = None) -> SyncRun[ImageSyncResult]` in `backend/src/tcg_pokedex/image_cache/service.py`, following plan.md "Service flow" steps 1–3, 5, 6 for a given `set_id`: open the `images` run and log `sync.run.started`; `check_writable`; `cards_to_resolve`, fill `files_present` from `store.has_card`, apply `plan_card`; resolve non-skipped cards on a `ThreadPoolExecutor(max_workers=8)` (`try_pt_then_en`, `try_pt_keep_en`, `try_en` exactly as data-model.md; `put_card` in the worker); after the set, `save_card_images(downloaded + unavailable, fetched_at=run.started_at)`; log `sync.failure` per failure; an unexpected exception closes the run `failed` with `str(exc)`; `finish_run`, log `sync.run.finished`. Makes T015 pass.
- [X] T018 [US1] Add `image_dir: Path = Path("data/images")` to `Settings` in `backend/src/tcg_pokedex/config.py`; implement `DownloadRegistry` (`start(set_id) -> bool`, `finish(set_id)`, `is_running(set_id)`, a `set` behind a `threading.Lock`) in `backend/src/tcg_pokedex/image_cache/registry.py`.
- [X] T019 [US1] Implement `backend/src/tcg_pokedex/image_cache/api/__init__.py` and `backend/src/tcg_pokedex/image_cache/api/routes.py` per contracts/api.md: an `owner_id` dependency returning `HOUSEHOLD_OWNER_ID`; `GET` and `PUT /api/sets/{set_id}/tracking` returning `SetTracking` (`404` when `set_exists` is false; `PUT` tracks, and when newly tracked and `registry.start(set_id)` adds a `BackgroundTasks` task that runs `sync_images(..., set_id=set_id)` and calls `registry.finish` in a `finally`; `downloading` from the registry); `GET /api/images/cards/{card_id}/{size}` (`CardSize`) and `GET /api/images/sets/{set_id}/{kind}` (`ArtworkKind`) returning `FileResponse(media_type="image/webp")` with `Cache-Control: public, max-age=604800`, `404` when the store returns `None`, no database read. Wire the router, `FileImageStore(settings.image_dir)`, `DownloadRegistry` and a provider factory (overridable with a transport, as `run_catalog_sync` does) into `create_app` in `backend/src/tcg_pokedex/app.py`. Makes T016 pass.
- [X] T020 [US1] Run `pnpm generate:api` in `frontend/` and commit `frontend/openapi.json` and `frontend/src/api-schema.gen.ts` in the T019 `feat:` commit (generated code, never edited by hand).

**TDD cycles**: (T015 → T017), (T016 → T018, T019, T020).

**Checkpoint**: tracking a set through the API caches and serves its card images. MVP.

---

## Phase 4: User Story 2 - Untrack a set (Priority: P2)

**Goal**: `DELETE /api/sets/{set_id}/tracking` untracks the set; later runs request none of its card images, and its cached images stay servable.

**Independent Test**: untrack a set, run `sync_images()` with no `set_id`, and check that no card image of that set was requested while its cached images still answer `200`.

### Tests for User Story 2 (write first) ⚠️

- [X] T021 [P] [US2] In `backend/tests/image_cache/test_service.py`: `sync_images(...)` with no `set_id` resolves cards only for `tracked_set_ids()`; the provider fake recorded no request for a card of an untracked set (SC-002).
- [X] T022 [P] [US2] In `backend/tests/image_cache/test_api_end_to_end.py`: track, then `DELETE /api/sets/sv01/tracking` → `200` with `tracked: false`; a second `DELETE` → `200`; cached card images still answer `200`; unknown set → `404`.

### Implementation for User Story 2

- [X] T023 [US2] In `backend/src/tcg_pokedex/image_cache/service.py`, when `set_id` is None loop over `repository.tracked_set_ids()` (plan.md step 3). Makes T021 pass.
- [X] T024 [US2] Add `DELETE /api/sets/{set_id}/tracking` to `backend/src/tcg_pokedex/image_cache/api/routes.py` (untrack, delete no file, do not touch the registry), and regenerate `frontend/openapi.json` and `frontend/src/api-schema.gen.ts` with `pnpm generate:api` in the same commit. Makes T022 pass.

**TDD cycles**: (T021, T022 → T023, T024).

**Checkpoint**: tracking and untracking both work through the API.

---

## Phase 5: User Story 3 - Catch up all images with one command (Priority: P2)

**Goal**: `tcg sync images` (no flags) completes every tracked set, upgrades English images to pt, caches every stored set's logo and symbol, records an `images` run and exits `0`/`1`/`2`.

**Independent Test**: `test_command.py`: real Postgres, temp image dir, fixture TCGdex with pt, English-only, missing and failing images; check files, run record, stdout JSON and exit code.

### Tests for User Story 3 (write first) ⚠️

- [X] T025 [P] [US3] In `backend/tests/image_cache/test_service.py`: with no `set_id`, logos and symbols of every stored set (tracked or not) are fetched and saved, cached artwork is not requested again, a set without a symbol URL or with a `Missing` symbol counts `unavailable` (not failed), a failing logo counts `failed`; a card stored `en` whose pt URL now answers is replaced and saved as `pt`, while one whose pt answers `Missing` stays `en` with no download (US3-2).
- [X] T026 [P] [US3] End-to-end command tests in `backend/tests/image_cache/test_command.py` calling `run_image_sync(settings, clock, transport, sleep)`: tracked set with one card failing → files cached for the rest, `sync_runs` row of kind `images` with status `partial`, stdout is the closed run JSON (contracts/cli.md shape, `set_id: null`), exit `1`; with the failure fixed a second run exits `0` and downloads no pt card again; an image dir that cannot be written → run `failed`, exit `2`. In `backend/tests/catalog_sync/test_cli.py` (or a new `backend/tests/image_cache/test_cli.py`): `tcg sync images` calls `run_image_sync` and exits with its code.
- [X] T027 [US3] FIX-1 test in `backend/tests/image_cache/test_tcgdex_image_provider.py`: first re-probe `https://assets.tcgdex.net/univ/sv/sv01/symbol.webp` and `…/pt/sv/sv01/symbol.webp` with `curl -sI` and record the result in the test module docstring; then, over `FixtureRoutes`, a `symbol` whose `/univ/…/symbol.webp` answers 404 is fetched from `/pt/…/symbol.webp`, a `logo` under `/univ/` answering 404 is `Missing` with no retry, and a symbol answering 404 under both is `Missing`. If TCGdex has fixed `/univ/`, keep the test and the fix anyway (the catalog still stores `/univ/` URLs).

### Implementation for User Story 3

- [X] T028 [US3] Add plan.md step 4 to `backend/src/tcg_pokedex/image_cache/service.py`: only when `set_id` is None, for each `artwork_to_fetch()` entry with a URL and `cached` false, `fetch_artwork` on the pool, then `put_artwork` + `save_artwork(fetched_at=run.started_at)`; no URL or `Missing` → `unavailable`; failure → `failed`. Makes T025 pass (the pt upgrade passes through T017's `try_pt_keep_en` path; fix it here if it does not).
- [X] T029 [US3] Implement `run_image_sync(settings, clock, transport=None, sleep=time.sleep) -> int` in `backend/src/tcg_pokedex/image_cache/command.py` with the `sync_runs/command.py` logging set-up and `EXIT_CODES` (print the closed run as one JSON object; on store error print nothing, log `sync.run.error`, return 2), and add the `images` subcommand to `backend/src/tcg_pokedex/cli.py` next to `catalog`. Makes T026 pass.
- [X] T030 [US3] FIX-1 in `backend/src/tcg_pokedex/image_cache/adapters/tcgdex.py`: in `fetch_artwork`, a `symbol` URL containing `/univ/` that answers 404 is retried once with `/univ/` replaced by `/pt/`. Commit as `fix(PTCG-013): fetch set symbols from /pt/ when /univ/ answers 404`. Makes T027 pass.

**TDD cycles**: (T025 → T028), (T026 → T029), (T027 → T030).

**Checkpoint**: all three stories work; `tcg sync images` catches up cards and artwork.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: persistent image volume in deployment (FR-016), docs, and the pre-PR checks

- [X] T031 [P] In `Dockerfile`, create `/data/images` owned by `app` before `USER app` and set `TCG_POKEDEX_IMAGE_DIR=/data/images`; in `deploy/compose.yml`, mount a named volume `images` at `/data/images` on the app service and declare it; in `.github/workflows/ci.yml` image smoke step, also run `tcg sync images --help` in the image. Commit as `build(PTCG-013): …`.
- [X] T032 [P] Update `deploy/README.md` (the `images` volume in install and backup notes, `docker compose exec app tcg sync images`) and `CLAUDE.md` Commands (`uv run tcg sync images`, `TCG_POKEDEX_IMAGE_DIR` / `backend/data/images`, Docker `tcg sync images`). Commit as `docs(PTCG-013): …`.
- [X] T033 Run the automated checks of `specs/PTCG-013-tracked-sets-images/quickstart.md` §1 (`uv run pytest --cov` ≥ 80% branch, ruff, `pyright --warnings`, `pnpm generate:api` with no diff, `bash .github/scripts/check-tdd-order.sh origin/main HEAD`) and fix anything red.
- [X] T034 Run quickstart.md §2 against the dev stack: track `sv01`, watch it reach `cached: 258` and `downloading: false` within 10 minutes (SC-001), `tcg sync images` twice (second run downloads no pt card, SC-003), `/api/images/sets/sv01/symbol` answers `200` (FIX-1), `swshp` shows `en` rows and `svp` a non-zero `unavailable`.
- [X] T035 Check the PR size (`git diff --stat origin/main...HEAD`, commit count) before opening it, and flag it to the user if it is far beyond a reviewable size.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T001/T002 before T003 (both touch the catalog adapter and tests).
- **Foundational (Phase 2)**: depends on Setup (uses `TcgdexHttp`, `sync_runs`, moved fixtures). BLOCKS all user stories.
- **US1 (Phase 3)**: depends on Foundational.
- **US2 (Phase 4)**: depends on US1 (extends `service.py` and `routes.py`).
- **US3 (Phase 5)**: depends on US1 (`service.py`); T027 → T030 (FIX-1) depends only on T014 and can run any time after Phase 2.
- **Polish (Phase 6)**: T031–T032 any time after T029; T033–T035 last.

### User Story Dependencies

- **US1 (P1)**: after Foundational. No dependency on other stories.
- **US2 (P2)**: after US1; independently testable through `DELETE` and an unscoped `sync_images()`.
- **US3 (P2)**: after US1; independent of US2 except that both edit `service.py` (do them in sequence).

### Within Each User Story

- Tests MUST be written and FAIL before the implementation task they cover
- Service before routes; routes before the generated API files
- Story complete before moving to the next priority

### Parallel Opportunities

- Phase 1: T004, T005 alongside T001–T003.
- Phase 2: test tasks T006, T007, T008, T010 are separate files; implementations T011, T012, T014 touch separate adapter files but share `fakes.py`, so land them one cycle at a time.
- US1: T015 and T016 in parallel (different files).
- US3: T025, T026, T027 in parallel; FIX-1 (T027 → T030) is independent of the rest of US3.
- Polish: T031 and T032 in parallel.

---

## Parallel Example: User Story 1

```bash
# Write both US1 test files together:
Task: "Service tests in backend/tests/image_cache/test_service.py"
Task: "End-to-end tests in backend/tests/image_cache/test_api_end_to_end.py"
```

## Parallel Example: User Story 3

```bash
Task: "Artwork and pt-upgrade service tests in backend/tests/image_cache/test_service.py"
Task: "Command tests in backend/tests/image_cache/test_command.py"
Task: "FIX-1 symbol retry test in backend/tests/image_cache/test_tcgdex_image_provider.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 refactors (catalog tests stay green).
2. Phase 2: domain, ports, adapters, migration.
3. Phase 3: service + tracking API + image routes.
4. **STOP and VALIDATE**: `uv run pytest tests/image_cache`, then quickstart §2 tracking `sv01`.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → set tracked through the API, images served locally (MVP).
3. US2 → untrack.
4. US3 → `tcg sync images` catch-up, artwork, FIX-1.
5. Polish → volume, docs, checks, PR.

### Commit budget

2 refactor commits, 4 foundational pairs, 2 US1 pairs, 1 US2 pair, 3 US3 pairs (one `test:`/`fix:` for FIX-1), 1 `build:`, 1 `docs:`: about 22 commits.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit each TDD cycle as a `test:` commit with the failing test, then a `feat:`/`fix:` commit (constitution, Principle I)
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
