---

description: "Task list for PTCG-012 catalog sync from TCGdex"
---

# Tasks: Catalog sync from TCGdex (sets & cards)

**Input**: Design documents from `/specs/PTCG-012-catalog-sync/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, contracts/ports.md, quickstart.md

**Tests**: Mandatory (constitution, Principle I). Every test task is listed before the implementation task it covers, and its test must fail before that task starts.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are relative to the repository root. Backend commands run from `backend/`.

## Conventions for every task

- Slice: `backend/src/tcg_pokedex/catalog_sync/`; tests: `backend/tests/catalog_sync/`.
- No code or config comments (docstrings are fine); no `type X = …` aliases.
- Commits: `test(PTCG-012): …` with the failing test, then `feat(PTCG-012): …` that makes it pass.
  Each phase lists its TDD cycles as `tests → implementation` so `check-tdd-order.sh` passes.
- Provider HTTP in tests only goes through `tcgdex_fixtures.py` (no real network, SC-004).
  Time comes from `FakeClock`; retry waits go through the injected `sleep` recorder.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dependency, slice skeleton and the shared test corpus and helpers

- [X] T001 Move `httpx2>=2.13.1` from `[dependency-groups].dev` to `[project].dependencies` in `backend/pyproject.toml` and refresh `backend/uv.lock` with `uv lock` (justification R1, Quality Gate 4). Commit as `build(PTCG-012): …`.
- [X] T002 Create the empty packages `backend/src/tcg_pokedex/catalog_sync/__init__.py` and `backend/src/tcg_pokedex/catalog_sync/adapters/__init__.py`, plus `backend/tests/catalog_sync/` (no `__init__.py` needed: pytest runs with `--import-mode=importlib`). Commit as `chore(PTCG-012): …`.
- [X] T003 [P] Record the real TCGdex `pt` payloads into `backend/tests/catalog_sync/fixtures/tcgdex/`, one JSON file per endpoint, named after its path (e.g. `series.json`, `series/sv.json`, `sets/sv01.json`, `cards/sv01-001.json`). Keep payloads verbatim except: `series.json` trimmed to the curated series plus `tcgp`; each series detail's `sets` trimmed to the curated sets; each set's `cards` trimmed to a few cards. The curated corpus MUST cover (choose concrete ids while recording): a modern set (e.g. `sv01`) with cards whose variants are `{normal, reverse}`; a promo set with non-numeric collector numbers (e.g. `swshp` with `SWSH158`, or `svp`); a card whose rarity is the literal `"None"` (e.g. in `xy0`); a card brief with no `image`; an empty physical set (e.g. `base1`, `cards: []`); the `tcgp` series and one Pocket set (e.g. `A1`) in `series.json` and `series/tcgp.json` only, with no set or card fixtures behind them; a whitespace-padded name on a set or card that is stored (hand-edit one recorded payload if no live one fits, and mark it in the README).
- [X] T004 [P] Add the hand-made failure fixtures in `backend/tests/catalog_sync/fixtures/tcgdex/`: a series detail variant (e.g. `series/sv.with-failures.json`) that also lists a failing set and a hand-made set whose card list holds the failure cards; a card missing `name`; a card whose five variant flags are all `false`; a card answered 404; a card answered 500 then 200; a set answered 500 three times. The "series index 500 three times" case needs no file (route table only).
- [X] T005 [P] Write `backend/tests/catalog_sync/fixtures/tcgdex/README.md`: for every real fixture its endpoint (`https://api.tcgdex.net/v2/pt/...`) and recording date (2026-10-11 or the day recorded) and what was trimmed; every hand-made fixture marked as hand-made with the case it covers.
- [X] T006 Create `backend/tests/catalog_sync/tcgdex_fixtures.py`: a `FixtureRoutes` handler for `httpx2.MockTransport` built from an explicit route table (path → list of responses consumed in order, each a fixture file + status, or a raised `httpx2` exception, or headers such as `Retry-After`); an unknown path or an exhausted response list raises `AssertionError`; a thread-safe log of every requested path and its headers and timeout extension; three tables: `HAPPY` (curated real corpus, all valid), `WITH_FAILURES` (`HAPPY` plus the T004 overrides), `INDEX_DOWN` (`/series` answered 500 three times); and `SleepRecorder`, a callable that returns at once and keeps the requested delays.
- [X] T007 [P] Create `backend/tests/catalog_sync/builders.py` with shared domain builders (`make_series`, `make_set`, `make_card`, `make_listing`) with sensible defaults overridable by keyword. It imports from `tcg_pokedex.catalog_sync.domain`, so write it together with T008 and commit it with the T008 tests.

**TDD cycles**: T003–T006 are test-only (`test(PTCG-012): add the TCGdex fixture corpus and route helper`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the pure domain, the ports with their fakes and contract suites, and the tables

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests (write first) ⚠️

- [X] T008 [P] Unit tests for the domain types in `backend/tests/catalog_sync/test_domain.py`: `Variant` declaration order is `normal, reverse, holo, first_edition, w_promo`; `is_pocket_series("tcgp")` is true and `is_pocket_series("sv")` false; `SOURCE == "tcgdex"`; `Card` with empty `variants` raises `ValueError`; `KindCounts` rejects `fetched != created + updated + unchanged`; `SetCounts`/`CardCounts` add `skipped`/`failed`; `SyncResult` rejects more than 100 failures; `SyncRun` round-trips through `model_dump_json`/`model_validate_json` with UTC datetimes and `kind="catalog"`, `source="tcgdex"`.
- [X] T009 Unit tests for the domain rules in `backend/tests/catalog_sync/test_domain.py` (after T008, same file): `classify(None, x) is CREATED`, `classify(x, x) is UNCHANGED`, `classify(x, y) is UPDATED` for a change in any one field (including `variants`); `plan_set` includes the series and its change when the series id is not in `series_written` and sets `SetBatch.series = None` (no series change) when it is; `plan_set` classifies the set and each card against `StoredCatalog`, and every card in the batch has `set_id == listing.card_set.id`; `ResultBuilder` counts per kind, keeps only the first 100 failures in order while counts stay exact, yields zero counts when nothing happened, and `status()` is `succeeded` with zero failures, `partial` with ≥ 1 set or card failure, and `failed` when marked aborted (FR-029).
- [X] T010 [P] Contract suite for `CatalogProvider` in `backend/tests/catalog_sync/test_catalog_provider_contract.py`, run against `InMemoryCatalogProvider` through a parametrized scenario fixture (ids `["fake"]`; later tasks add `"tcgdex"`): contract items 1–6 of `contracts/ports.md` (Pocket ids listed, not filtered; index failure raises `ProviderUnavailable` and never returns a partial list; set/card failures returned as `Failure(kind, provider_id, reason)`, never raised; `fetch_cards` returns exactly `len(card_ids)` outcomes aligned with `card_ids`; every `Card.set_id` equals the `set_id` argument; an empty set is a `SetListing` with `card_ids == ()`).
- [X] T011 [P] Contract suite for `CatalogRepository` in `backend/tests/catalog_sync/test_catalog_repository_contract.py`, parametrized (ids `["fake"]`; US1 adds `"postgres"`): items 1, 4, 5, 6 of `contracts/ports.md` (`save_set` all or nothing: a batch whose set's series is neither in the batch nor stored raises and leaves nothing visible; `load_stored` returns `None`/omits missing ids; `variants` round-trip as the same `frozenset[Variant]`; `get_run` returns what `start_run`/`finish_run` last wrote, including an equal `result`), plus `load_stored` returning stored rows with their `fetched_at`. Items 2 and 3 are added in US2.
- [X] T012 [P] Extend `backend/tests/test_migrations.py`: upgrade creates `{"alembic_version", "owners", "series", "sets", "cards", "sync_runs"}`; `command.check` still passes; downgrade to base leaves only `alembic_version`; the module run creates `cards`.

### Implementation

- [X] T013 Implement the domain types in `backend/src/tcg_pokedex/catalog_sync/domain.py` per data-model.md: `SOURCE = "tcgdex"`, `Variant` (enum, declaration order is the canonical storage order), `is_pocket_series` (only definition of the rule, FR-002), frozen entities `Series`, `CardSet`, `Card` (`variants: frozenset[Variant]`, non-empty), `SetListing`, `Fetched[T]`, `StoredCatalog`, `SetBatch`; Pydantic models `Failure` (`kind: "set" | "card"`, `provider_id`, `reason`), `SyncKind` (`catalog` only), `RunStatus` (`running`, `succeeded`, `partial`, `failed`), `KindCounts` (validator `fetched == created + updated + unchanged`), `SetCounts`, `CardCounts`, `SyncCounts`, `SyncResult` (`failures` ≤ 100), `SyncRun` (`id: UUID`, `kind`, `source`, `status`, `started_at`, `finished_at | None`, `duration_ms | None`, `result: SyncResult | None`, `error | None`). Makes T008 pass.
- [X] T014 Implement `Change`, `classify`, `plan_set(stored, listing, cards, series_written) -> (SetBatch, changes)` and `ResultBuilder` (counts, 100-failure cap, `status()`, `build() -> SyncResult`) in `backend/src/tcg_pokedex/catalog_sync/domain.py`. No I/O, no clock. Makes T009 pass.
- [X] T015 Define the ports in `backend/src/tcg_pokedex/catalog_sync/ports.py` per `contracts/ports.md`: `ProviderUnavailable(reason)` exception, `CatalogProvider` and `CatalogRepository` Protocols with the exact method signatures listed there.
- [X] T016 Implement `backend/src/tcg_pokedex/catalog_sync/fakes.py`: `InMemoryCatalogProvider` seeded with series → set ids, a `SetListing` per set and a `Card` per card id, with scripted failures (index raises `ProviderUnavailable`, a set or card returns a `Failure`), recording every requested series, set and card id in order; `InMemoryCatalogRepository` holding runs and `Fetched` rows in dicts, recording calls in order (`start_run`, `save_set`, `finish_run`), with `save_set` validating the whole batch before writing any of it. Makes T010 and T011 pass.
- [X] T017 Add the tables in `backend/src/tcg_pokedex/catalog_sync/adapters/tables.py` on the shared `metadata`, import them in `backend/src/tcg_pokedex/schema.py`, and write `backend/migrations/versions/0002_create_catalog_and_sync_runs.py` (`down_revision = "0001"`, expand-only: new tables only; downgrade drops `cards`, `sets`, `sync_runs`, `series`), then confirm with `uv run alembic revision --autogenerate` that nothing is left over. Columns exactly as data-model.md: every catalog table has `id text PK`, `source text NOT NULL`, `fetched_at timestamptz NOT NULL`; `series.name text NOT NULL`; `sets.series_id text NOT NULL FK → series.id, indexed`, `name text NOT NULL`, `release_date date NOT NULL`, `official_count integer NOT NULL`, `total_count integer NOT NULL`, `logo_url text NULL`, `symbol_url text NULL`; `cards.set_id text NOT NULL FK → sets.id, indexed`, `collector_number text NOT NULL`, `name text NOT NULL`, `rarity text NULL`, `illustrator text NULL`, `image_url text NULL`, `variants text[] NOT NULL` with `CHECK (cardinality(variants) > 0)`; `sync_runs`: `id uuid PK`, `kind text NOT NULL`, `source text NOT NULL`, `status text NOT NULL`, `started_at timestamptz NOT NULL`, `finished_at timestamptz NULL`, `duration_ms integer NULL`, `result jsonb NULL`, `error text NULL`. No enum or value-list constraints on `kind`, `status` or `variants` values (R7). Makes T012 pass.

**TDD cycles**: (T007, T008 → T013), (T009 → T014), (T010, T011 → T015, T016), (T012 → T017).

**Checkpoint**: domain, ports, fakes and schema ready; user stories can start.

---

## Phase 3: User Story 1 - Populate the catalog (Priority: P1) 🎯 MVP

**Goal**: `tcg sync catalog` on an empty store stores every `pt` physical set with cards, its series and its valid cards, records the run and exits `0`.

**Independent Test**: `run_catalog_sync` against a migrated empty Postgres and the `HAPPY` route table stores exactly the expected series, sets and cards, prints one `succeeded` run JSON with matching `created` counts, and returns `0`; no `tcgp` path is requested.

### Tests for User Story 1 (write first) ⚠️

- [X] T018 [P] [US1] Payload mapping tests in `backend/tests/catalog_sync/test_tcgdex_payloads.py` over the recorded fixtures: series list → ids in provider order; series detail → set ids; set detail → `SetListing` (`CardSet` id, name, `release_date` from `releaseDate`, `official_count`/`total_count` from `cardCount`, optional `logo_url`/`symbol_url`, `Series` from `serie.id`/`serie.name`, `card_ids` from `cards[].id`); card detail → `Card` (`collector_number` from `localId` verbatim, e.g. `SWSH158`; rarity; illustrator; `image_url`; variants with `firstEdition → first_edition` and `wPromo → w_promo`); every text trimmed (the padded-name fixture); rarity `"None"` → `None`; absent, empty or whitespace-only rarity, illustrator, logo, symbol, image → `None`; URLs stored verbatim with no suffix; `card.set` ignored (the `set_id` argument wins, FR-016).
- [X] T019 [P] [US1] Adapter tests in `backend/tests/catalog_sync/test_tcgdex_provider.py` using `FixtureRoutes(HAPPY)`: requests go to `https://api.tcgdex.net/v2/pt/series`, `/series/{id}`, `/sets/{id}`, `/cards/{id}`; every request carries `User-Agent: tcg-pokedex/<importlib.metadata.version("tcg-pokedex")> (+https://github.com/gabriel-barata/tgc-pokedex)` and a 10 s timeout (request `timeout` extension); `fetch_cards` returns outcomes aligned with the requested ids; with a set of ≥ 9 cards, the handler's peak in-flight count (tracked under a lock while the handler briefly blocks) is > 1 and ≤ 8.
- [X] T020 [US1] Add the `"tcgdex"` scenario to the happy-path tests of `backend/tests/catalog_sync/test_catalog_provider_contract.py` (contract items 1, 4, 5, 6), built from `TcgdexProvider(transport=MockTransport(FixtureRoutes(HAPPY)), sleep=SleepRecorder())`.
- [X] T021 [P] [US1] Add the `"postgres"` parameter to `backend/tests/catalog_sync/test_catalog_repository_contract.py`, building `PostgresCatalogRepository` on `empty_database_url` upgraded with `upgrade_to_head` (engine disposed after the test), so every T011 test runs against both.
- [X] T022 [P] [US1] Service tests in `backend/tests/catalog_sync/test_service.py` with the two fakes, `builders.py` and `FakeClock`: an empty store ends with every physical set with cards, its series and its cards; every `save_set` gets `fetched_at == run.started_at`; counts report `created` for each kind and `fetched == created`; status `succeeded`; `start_run` is recorded before the first `save_set` and the run is closed with `finished_at` and `duration_ms` from the clock (wrap the provider so `fetch_cards` advances the clock 1.5 s and assert `duration_ms == 1500`); `tcgp` sets and cards are never requested, stored or counted; an empty set is counted in `sets.skipped` and its cards are not requested; a series whose sets are all skipped is not stored; a series with two stored sets is written once and counted once; a `{normal, reverse}` card is stored with those variants; `sync.run.started` and `sync.run.finished` are logged on the `tcg_pokedex` logger (`caplog`).
- [X] T023 [P] [US1] End-to-end tests (Principle VI reading, R11) in `backend/tests/catalog_sync/test_command.py`: `run_catalog_sync(Settings(database_url=<migrated empty db>), FakeClock(...), transport=MockTransport(FixtureRoutes(HAPPY)), sleep=SleepRecorder())` returns `0`; stdout is exactly one JSON object that validates as `SyncRun` with status `succeeded` and the expected `created` counts for the corpus; the `series`, `sets` and `cards` rows match the corpus (spot-check a `{normal, reverse}` card, a non-numeric collector number, the `"None"` rarity stored as `NULL`, the card without image stored with `image_url NULL`, the trimmed padded name, absent logo/symbol as `NULL`); every row has `source = 'tcgdex'` and `fetched_at` equal to the clock's start; the `sync_runs` row equals the printed JSON; no requested path contains `tcgp` or a Pocket set id; stderr holds JSON lines with `event`, `level`, `time` for `sync.run.started` and `sync.run.finished` (contracts/cli.md).
- [X] T024 [P] [US1] CLI tests in `backend/tests/catalog_sync/test_cli.py`: `cli.main(["sync", "catalog"])` calls `run_catalog_sync` with `Settings()` and a `SystemClock` and exits with its return code (monkeypatch `run_catalog_sync` to return `1`, assert `SystemExit.code == 1`); `main(["--help"])` exits `0` and its usage mentions `sync`; `main([])` and `main(["sync", "nope"])` exit `2`.

### Implementation for User Story 1

- [X] T025 [US1] Implement `backend/src/tcg_pokedex/catalog_sync/adapters/tcgdex_payloads.py` (R5): one Pydantic model per payload shape (series list item, series detail, set detail with card briefs, card detail) with `extra="ignore"` and `str_strip_whitespace=True`; required text fields `min_length=1`; one shared "blank → None" validator for rarity, illustrator, logo, symbol, image, with rarity also mapping `"None"` to `None`; mapping functions to the domain types (card mapping takes `set_id` and ignores `card.set`). This module is the only provider-to-domain mapping (Principle II). Makes T018 pass.
- [X] T026 [US1] Implement `TcgdexProvider(transport: httpx2.BaseTransport | None = None, sleep: Callable[[float], None] = time.sleep)` in `backend/src/tcg_pokedex/catalog_sync/adapters/tcgdex.py`: one `httpx2.Client` with base URL `https://api.tcgdex.net/v2/pt`, the R10 user agent, `timeout=10`, `Limits(max_connections=8)`; index and set requests one at a time; `fetch_cards` maps over a `ThreadPoolExecutor(max_workers=8)` and returns outcomes in request order; payloads parsed through `tcgdex_payloads.py`; a context-manager or `close()` to release the client. Retries and failures come in US3. Makes T019 and T020 pass.
- [X] T027 [US1] Implement `PostgresCatalogRepository(engine)` in `backend/src/tcg_pokedex/catalog_sync/adapters/postgres.py` with SQLAlchemy Core on the T017 tables: `start_run` inserts and commits; `finish_run` updates the closed fields; `get_run` reads and validates through `SyncRun` (`result` stored as `SyncResult` JSON); `load_stored` reads the series, the set and the cards (`id = ANY(:ids)`) as `Fetched` values with variants parsed back into `frozenset[Variant]`; `save_set` writes the batch's series (when present), set and cards in one transaction, stamping `source = SOURCE` and `fetched_at`, variants as `text[]` in canonical `Variant` order (plain `INSERT` here; US2 turns it into an upsert). Makes T021 pass.
- [X] T028 [US1] Implement `sync_catalog(provider, repository, clock) -> SyncRun` in `backend/src/tcg_pokedex/catalog_sync/service.py` following plan.md "Service flow" steps 1–3 and 5 for the happy path: create and `start_run` a `running` run; read the whole index (series ids, then set ids of every non-Pocket series) before any catalog write; per set: `fetch_set` → skip when `card_ids` is empty → `fetch_cards` → `load_stored` → `plan_set` → `save_set(batch, fetched_at=run.started_at)` → apply the changes to the `ResultBuilder`; close the run with `finished_at`, `duration_ms` and the result; `finish_run`; log `sync.run.started` (after `start_run`) and `sync.run.finished` with the fields in contracts/cli.md through `logging.getLogger("tcg_pokedex.catalog_sync")`. Makes T022 pass.
- [X] T029 [US1] Implement the composition root `run_catalog_sync(settings, clock, transport=None, sleep=time.sleep) -> int` in `backend/src/tcg_pokedex/catalog_sync/command.py`: attach a stderr handler with a small JSON formatter (`event`, `level`, `time` in UTC ISO 8601, plus the record's extra fields) to the `tcg_pokedex` logger at INFO, without configuring the root logger; build the engine with `create_database_engine`, `PostgresCatalogRepository` and `TcgdexProvider`; run `sync_catalog`; print `run.model_dump_json()` to stdout; dispose the engine and close the provider; return `0`/`1`/`2` for `succeeded`/`partial`/`failed` (FR-041). Makes T023 pass.
- [X] T030 [US1] Implement `backend/src/tcg_pokedex/cli.py` (`main(argv: Sequence[str] | None = None) -> NoReturn`) with `argparse`: program `tcg`, required subcommand `sync`, required subcommand `catalog` with no flags, dispatching to `run_catalog_sync(Settings(), SystemClock())` and exiting with its code; add `[project.scripts] tcg = "tcg_pokedex.cli:main"` to `backend/pyproject.toml` and run `uv sync` so `uv run tcg sync catalog` works. Makes T024 pass.

**TDD cycles**: (T018 → T025), (T019, T020 → T026), (T021 → T027), (T022 → T028), (T023 → T029), (T024 → T030).

**Checkpoint**: US1 is fully functional: a first run populates the catalog end to end.

---

## Phase 4: User Story 2 - Refresh without duplicates (Priority: P1)

**Goal**: re-running the sync updates changed rows, reports unchanged ones, refreshes `fetched_at`, and never duplicates or deletes.

**Independent Test**: two `run_catalog_sync` calls against the same `HAPPY` fixtures and database: the second returns `0`, reports `created = 0` and `updated = 0` for every kind, and every stored column except `fetched_at` is identical.

### Tests for User Story 2 (write first) ⚠️

- [X] T031 [P] [US2] Add contract items 2 and 3 to `backend/tests/catalog_sync/test_catalog_repository_contract.py` (fake and postgres): saving a batch for one set leaves rows of other sets and of cards not in the batch with every column unchanged, including `fetched_at`; saving an existing series, set and card id with changed attributes (name, rarity to `None`, variants `{normal}` → `{normal, reverse}`) and a later `fetched_at` replaces every attribute and `fetched_at`, with no duplicate row.
- [X] T032 [P] [US2] Refresh tests in `backend/tests/catalog_sync/test_service.py`: a second run over the same provider data reports `created = 0`, `updated = 0`, `unchanged = fetched` for every kind, and every re-fetched row's `fetched_at` equals the second run's start; a card renamed at the provider is updated and counts in `cards.updated` while the others count as `unchanged`; a card or set the provider no longer lists keeps its stored row unchanged, including its old `fetched_at`; a set that had cards and now lists none counts as `skipped` and its stored set and cards stay untouched; a series seen again counts as `unchanged` once.
- [X] T033 [P] [US2] End-to-end refresh test in `backend/tests/catalog_sync/test_command.py`: run `run_catalog_sync` twice on one migrated database with the `HAPPY` routes (fresh `FixtureRoutes` each run), advancing the `FakeClock` by one hour between runs; the second returns `0`, prints `created = 0` and `updated = 0` for every kind and `unchanged == fetched`; row counts in `series`, `sets` and `cards` are equal after both runs; every column except `fetched_at` is identical, and `fetched_at` equals the second start; `sync_runs` holds two closed rows.

### Implementation for User Story 2

- [X] T034 [US2] Turn `save_set` in `backend/src/tcg_pokedex/catalog_sync/adapters/postgres.py` into `INSERT … ON CONFLICT (id) DO UPDATE` (`sqlalchemy.dialects.postgresql.insert`) setting every non-key column from `excluded`, including `source` and `fetched_at`, still one transaction per batch and never a `DELETE` (FR-019, FR-020). Makes T031 and T033 pass. T032 is expected to pass already on the fakes; commit it as a test-only commit if so.

**TDD cycles**: (T031, T032, T033 → T034).

**Checkpoint**: US1 and US2 both work: the sync can run repeatedly without corrupting the catalog.

---

## Phase 5: User Story 3 - Visible, non-fatal failures (Priority: P2)

**Goal**: failures are retried where allowed, counted at the right level, logged, recorded in the run, and reflected in status and exit code, while every valid row is still stored.

**Independent Test**: `run_catalog_sync` with the `WITH_FAILURES` routes returns `1` with each failure fixture counted and listed and all valid data stored; with `INDEX_DOWN` it returns `2`, writes no catalog row and closes the run as `failed`.

### Tests for User Story 3 (write first) ⚠️

- [X] T035 [P] [US3] Invalid payload tests in `backend/tests/catalog_sync/test_tcgdex_payloads.py`: the card fixture missing `name` maps to `Failure("card", <id>, "invalid payload: name: <message>")`; a card missing `id` or `localId`, or whose name is whitespace only, is an invalid card; the all-false variants fixture and a card with no `variants` object map to `Failure("card", <id>, "no variants")`; a set payload missing any of `id`, `name`, `serie.id`, `serie.name`, `releaseDate`, `cardCount.official`, `cardCount.total`, or with a card brief lacking `id`, maps to a `set` failure with an `invalid payload: …` reason (FR-017, FR-018).
- [X] T036 [P] [US3] Retry and failure tests in `backend/tests/catalog_sync/test_tcgdex_provider.py` (R4, reasons per contracts/cli.md): card 500 then 200 → `Card`, sleeps `[1.0]`; set 500 three times → `Failure("set", id, "HTTP 500 after 3 attempts")`, 3 requests, sleeps `[1.0, 2.0]`, and no card requested; card 404 → `Failure("card", id, "HTTP 404")` after exactly one request and no sleep; 429 with `Retry-After: 5` then 200 → sleeps `[5.0]`; 503 with `Retry-After: 3` honoured the same way; a non-integer `Retry-After` falls back to the backoff delay; `httpx2.ReadTimeout` three times → `"timeout after 3 attempts"`; `httpx2.ConnectError` three times → `"network error after 3 attempts"`; an invalid card payload fails with no retry; `/series` 500 three times, a series detail 500 three times, or an invalid index payload → `ProviderUnavailable`.
- [X] T037 [US3] Add the `"tcgdex"` scenario to the failure tests of `backend/tests/catalog_sync/test_catalog_provider_contract.py` (contract items 2 and 3), using `INDEX_DOWN` and `WITH_FAILURES`.
- [X] T038 [P] [US3] Failure tests in `backend/tests/catalog_sync/test_service.py` with the fakes: a card failure counts in `cards.failed`, is listed in `result.failures` and logged as one `sync.failure` line (`run_id`, `kind`, `provider_id`, `reason`), while its set and the other cards are stored and the status is `partial`; a set failure counts in `sets.failed`, its cards are never requested, the other sets are synced; a valid set whose card fetches all fail is still stored with its series (FR-024); `ProviderUnavailable` from `list_series_ids` or `list_set_ids` closes the run as `failed` with `error` set to the reason, all-zero counts, no `save_set` call, and no set fetched; an unexpected exception from `save_set` on the second set leaves the first set saved, closes the run as `failed` with `error == str(exc)` and still calls `finish_run`; 105 card failures keep the first 100 in order in `result.failures`, `cards.failed == 105`, and 105 `sync.failure` lines are logged.
- [X] T039 [P] [US3] End-to-end failure tests in `backend/tests/catalog_sync/test_command.py`: `WITH_FAILURES` returns `1`, prints status `partial` with every failure fixture in `failures` at the right kind, the `sync_runs` row matches, the 500-then-200 card is stored, and the valid sets and cards are stored; `INDEX_DOWN` returns `2`, prints status `failed` with `error` set and all-zero counts, leaves `series`, `sets` and `cards` empty, and closes the run record; an unreachable store (`database_url` pointing at `127.0.0.1:1`) returns `2`, prints nothing to stdout, logs one `sync.run.error` line, and the fixture handler is never called; a `finish_run` that raises (monkeypatched on `PostgresCatalogRepository`) logs `sync.run.error` and returns `2`.

### Implementation for User Story 3

- [X] T040 [US3] In `backend/src/tcg_pokedex/catalog_sync/adapters/tcgdex_payloads.py`, map payload `ValidationError`s to `Failure` with reason `invalid payload: <field>: <message>` (first error, dotted field path) and enforce "at least one true variant flag", including a missing `variants` object, with reason `no variants`. Makes T035 pass.
- [X] T041 [US3] Add the retry loop to `backend/src/tcg_pokedex/catalog_sync/adapters/tcgdex.py`: up to 3 attempts; retry `httpx2.TransportError`, 5xx and 429; waits `1.0` then `2.0` through the injected `sleep`, or the integer `Retry-After` seconds on 429/503; any other 4xx fails at once; set/card failures returned as `Failure` with the stable reasons; index failures (request or payload) raised as `ProviderUnavailable(reason)`. Makes T036 and T037 pass.
- [X] T042 [US3] Add failure handling to `backend/src/tcg_pokedex/catalog_sync/service.py` (plan.md flow steps 2–4): record and log each set/card `Failure`; skip `fetch_cards` for failed sets; store a valid set even when all its cards failed; on `ProviderUnavailable` close the run as `failed` with the reason before any catalog write; on any other exception close the run as `failed` with `str(exc)`; always call `finish_run` with the closed run. Makes T038 pass.
- [X] T043 [US3] In `backend/src/tcg_pokedex/catalog_sync/command.py`, when `start_run` or `finish_run` raises, log one `sync.run.error` line with the error, print nothing, never call the provider after a failed `start_run`, and return `2`. Makes T039 pass.

**TDD cycles**: (T035 → T040), (T036, T037 → T041), (T038 → T042), (T039 → T043).

**Checkpoint**: all user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: image check, docs and the quality gates

- [X] T044 [P] Add `docker run --rm tcg-pokedex:ci tcg --help` to the "Smoke test the image" step of the `image` job in `.github/workflows/ci.yml` (FR-037). Commit as `ci(PTCG-012): …`.
- [X] T045 [P] Update `CLAUDE.md` Commands: in the backend list, `uv run tcg sync catalog` (copies the TCGdex `pt` catalog into the configured database; exit `0`/`1`/`2` for succeeded/partial/failed); in the whole-stack list, `tcg sync catalog` inside the production image. Commit as `docs(PTCG-012): …`.
- [X] T046 Confirm `.github/scripts/check-tdd-order.sh` already covers the new locations (`backend/src/*`, `backend/migrations/*`, `backend/tests/*`); change it only if a file landed elsewhere.
- [X] T047 Run the gates from `backend/`: `uv run pytest --cov` (90% branch floor), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --warnings`; from the root: `bash .github/scripts/check-skipped-tests.sh` and `bash .github/scripts/check-tdd-order.sh origin/main HEAD`. Fix any finding with its own test-first cycle.
- [X] T048 Run quickstart.md sections 2–4 by hand (live run under 15 minutes with `sets.skipped == 22` and about 13,900 cards; second live run with `created = updated = 0`; `tcg --help` in the image; store unreachable → exit 2) and record the timings and counts in the PR body (SC-006).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T007 is written alongside T008 because it imports the domain.
- **Foundational (Phase 2)**: depends on Setup; blocks every user story.
- **US1 (Phase 3)**: depends on Foundational.
- **US2 (Phase 4)**: depends on US1 (it upgrades the US1 Postgres adapter and reruns the US1 end-to-end path).
- **US3 (Phase 5)**: depends on US1 (it extends the US1 adapter, service and command); independent of US2.
- **Polish (Phase 6)**: depends on all stories.

### Within Each Phase

- Tests are written and fail before the implementation task they cover (TDD cycles listed per phase).
- Payload models (T025) before the provider (T026); repository (T027) and provider before the command (T029); service (T028) before the command; command before the CLI (T030).

### Parallel Opportunities

- Setup: T003, T004 and T005 in parallel.
- Foundational: T008, T010, T011 and T012 are separate test files; T013/T014 (domain), T016 (fakes) and T017 (tables) touch separate files once their tests exist.
- US1: tests T018, T019, T021, T022, T023, T024 in parallel; T025 and T027 in parallel.
- US2 and US3 can run in parallel after US1 (they touch `postgres.py` vs. `tcgdex*.py`, `service.py`, `command.py`), but both add tests to `test_service.py` and `test_command.py`, so merge those edits carefully.

---

## Parallel Example: User Story 1

```bash
# Write the US1 tests together:
Task: "Payload mapping tests in backend/tests/catalog_sync/test_tcgdex_payloads.py"
Task: "Adapter tests in backend/tests/catalog_sync/test_tcgdex_provider.py"
Task: "Postgres parameter in backend/tests/catalog_sync/test_catalog_repository_contract.py"
Task: "Service tests in backend/tests/catalog_sync/test_service.py"
Task: "End-to-end tests in backend/tests/catalog_sync/test_command.py"
Task: "CLI tests in backend/tests/catalog_sync/test_cli.py"

# Then the independent adapters together:
Task: "TCGdex payload models in backend/src/tcg_pokedex/catalog_sync/adapters/tcgdex_payloads.py"
Task: "PostgresCatalogRepository in backend/src/tcg_pokedex/catalog_sync/adapters/postgres.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup.
2. Phase 2: Foundational (blocks all stories).
3. Phase 3: US1.
4. **Stop and validate**: `uv run pytest tests/catalog_sync`, then a manual `uv run tcg sync catalog` against `make migrate`.

### Incremental Delivery

1. Setup + Foundational → domain, ports, fakes and schema ready.
2. US1 → first run populates the catalog (MVP).
3. US2 → safe re-runs (needed before PTCG-014 schedules the sync).
4. US3 → failures counted, logged and reflected in status and exit code.
5. Polish → image check, docs, gates, live run. All in one PR for PTCG-012.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps the task to its user story.
- Verify each test fails before implementing; commit each TDD cycle as a `test(PTCG-012):` commit, then a `feat(PTCG-012):` commit (constitution, Principle I).
- A test that already passes when written (e.g. T032 on the fakes) is committed as a test-only commit with no `feat:` partner.
- Never skip a test without its ticket code on the same line (`check-skipped-tests.sh`).
