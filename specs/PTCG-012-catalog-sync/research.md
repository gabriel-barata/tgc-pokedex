# Research: Catalog sync from TCGdex

Phase 0 of `/speckit-plan`. Each entry records a decision, why it was made, and what was
rejected. Provider facts come from the spec (checked 2026-10-11) and a re-check of the payload
shapes on the same day.

## R1. HTTP client

- **Decision**: `httpx2` (`httpx2.Client`), moved from the backend's dev dependencies to its
  runtime dependencies.
- **Rationale**: It is already in the lockfile (Starlette's `TestClient` needs it), it gives
  connection pooling, per-request timeouts and `Limits(max_connections=8)`, and it ships
  `httpx2.MockTransport`, which is the seam the fixture tests need.
- **Alternatives**: `urllib.request` (no pooling, no transport seam: we would write both);
  `requests` (a new dependency, no built-in mock transport); `aiohttp` (async only, a new
  dependency).
- **Quality Gate 4 justification**: `httpx2` provides pooling, timeouts and a mock transport
  that `urllib` lacks, and it is already locked for the test client.

## R2. Fixture-based HTTP tests (instead of `respx`)

- **Decision**: no new dependency. Tests build the adapter's client on an
  `httpx2.MockTransport` whose handler serves fixture files from an explicit route table
  (path → list of responses, consumed in order). An unknown path raises `AssertionError`,
  which the adapter does not catch, so the test fails. The handler records every requested
  path so tests can assert that no `tcgp` endpoint was hit.
- **Rationale**: `respx` patches the `httpx` package; the project uses the `httpx2` fork, so
  `respx` would not intercept its requests. The route table is about 20 lines of test helper.
  The explicit table enforces the spec's "every request has an explicit fixture, no
  catch-all".
- **Alternatives**: `respx` (does not cover `httpx2`); `pytest-httpserver` (a new dependency
  and a real local socket, for no gain).

## R3. Concurrency model (8 requests in flight)

- **Decision**: threads, inside the TCGdex adapter. `fetch_cards(set_id, card_ids)` maps the
  card requests over a `ThreadPoolExecutor(max_workers=8)` sharing one `httpx2.Client` with
  `Limits(max_connections=8)`. Index and set requests are made one at a time. Only card
  fetches overlap, so at most 8 requests are ever in flight.
- **Rationale**: The rest of the stack is synchronous (SQLAlchemy Core with psycopg, a
  synchronous command). Keeping concurrency inside the adapter keeps the port, the fake, the
  service and the tests synchronous, with no async test plugin. Per-set batching matches the
  per-set commit (FR-023): a set's cards are fetched, then written.
- **Throughput**: about 14,000 card requests at 8 in flight and roughly 0.2 s each is about
  6 minutes, plus about 130 sequential index and set requests. This fits SC-006 (under
  15 minutes).
- **Alternatives**: `asyncio` with `httpx2.AsyncClient` and a semaphore (needs an async test
  plugin or `anyio` markers everywhere, and mixes an event loop with a synchronous database);
  concurrency in the service (would put a provider limit outside the adapter, against
  FR-027).

## R4. Retries, backoff and instant waits in tests

- **Decision**: the adapter makes up to 3 attempts. It retries `httpx2.TransportError`
  (network errors and timeouts), 5xx and 429, and waits 1 s and then 2 s between attempts. A
  429 or 503 with an integer `Retry-After` header waits that many seconds instead. Any other
  4xx fails at once. The wait function is injected (`sleep: Callable[[float], None] =
  time.sleep`), and tests pass a recorder that returns at once and keeps the requested
  delays.
- **Rationale**: "Up to 3 attempts" means two waits, so the third step of the spec's "about
  1 s, 2 s, 4 s" never happens. The fixtures ("500 three times") confirm 3 attempts in
  total. An injected sleep is the smallest seam, and tests can still assert the backoff
  values.
- **Failure reasons** are short, stable strings: `HTTP 404`, `HTTP 500 after 3 attempts`,
  `timeout after 3 attempts`, `network error after 3 attempts`,
  `invalid payload: <field>: <message>`, `no variants`.
- **Alternatives**: `tenacity` or `stamina` (a new dependency for about 25 lines of loop);
  `httpx2.HTTPTransport(retries=…)` (connection errors only, no 5xx/429).

## R5. Boundary validation and mapping

- **Decision**: one Pydantic model per TCGdex payload shape (series list item, series
  detail, set detail with card briefs, card detail), with `extra="ignore"` and
  `str_strip_whitespace=True`. They live in one adapter module together with the functions
  that map them to domain objects. Required text fields use `min_length=1`. Optional text
  fields (rarity, illustrator, logo, symbol, image) go through one shared "blank → None"
  validator. Rarity also maps the literal `"None"` to absent. The card model requires at
  least one true variant flag and fails with reason `no variants`. A card payload with no
  `variants` object at all also counts as `no variants`.
- **Rationale**: This is one place for every hygiene rule (FR-013 to FR-018), validated at
  the boundary (Principle II and the Security constraint). Trimming is a model setting, not
  code repeated for each field.
- **Set payload validity**: a set missing a field from FR-018, or with a card brief that has
  no `id`, is an invalid set. Without the id its cards cannot be requested.
- **Card identity**: the card's id comes from its own payload (FR-017 requires it). Its set
  is always the set being synced (FR-016): the mapping takes `set_id` as an argument and
  ignores `card.set`.

## R6. Where the domain rules live

- **Decision**: `catalog_sync/domain.py` is pure. It holds the entities, `Variant`, the Pocket
  rule `is_pocket_series` (FR-002, its only definition), change classification
  (created/updated/unchanged, comparing every attribute except source and fetched-at), the
  per-set write plan (including "write the series once per run"), the result builder (counts,
  the 100-failure cap) and the status rule (FR-029). The application service
  `catalog_sync/service.py` walks the index, calls the ports and the domain, and logs.
- **Rationale**: Principle III. The interesting decisions get fast unit tests, and the
  service is tested against the two fakes.
- **Pydantic in the domain**: the run result and run record are Pydantic models, so their
  shape is defined once and validated on write and on read (FR-034). Pydantic is a pure
  validation library with no I/O, so the core stays pure.

## R7. Persistence

- **Decision**: SQLAlchemy Core tables on the shared `metadata`: `series`, `sets`, `cards`
  and `sync_runs`, created by one Alembic migration (`0002`, expand-only: new tables only).
  Writes use `INSERT … ON CONFLICT (id) DO UPDATE`. One `save_set` call is one transaction
  (FR-023). Before writing, the service loads the stored rows for the set's series, the set
  and its card ids (`id = ANY(...)`), and the domain classifies each row.
- **Variants** are stored as `text[]` in the canonical `Variant` order, with a
  `CHECK (cardinality(variants) > 0)`. The allowed values are enforced by the domain enum on
  write and on read, not by a second list in the database (Principle II).
- **Run records**: `sync_runs.result` is `jsonb` holding the validated `SyncResult`. `kind`
  and `status` are plain text, validated by domain enums, so PTCG-013 and PTCG-021 can add
  kinds without a constraint change.
- **Alternatives**: a `card_variants` child table (more joins, and an update that removes a
  variant would need a delete, against FR-020's spirit); a Postgres enum array (`ALTER TYPE`
  churn for every new kind or variant); upserts that decide created/updated in SQL with
  `RETURNING xmax` (moves a domain decision into the database, against Principle III).
- **Read/write race**: classification reads outside the write transaction. Overlapping runs
  are out of scope (PTCG-014), and a race could only skew counts, never data.

## R8. Command wiring and test seams

- **Decision**: a `tcg` console script (`[project.scripts] tcg = "tcg_pokedex.cli:main"`),
  built with `argparse`, with one subcommand path `sync catalog`. `cli.py` sits at the
  package root, like `migrations.py`, because later slices add `sync images` and
  `sync prices`. It dispatches to `catalog_sync/command.py`, the composition root:
  `run_catalog_sync(settings, clock, transport=None, sleep=time.sleep) -> int` builds the
  engine, the adapters and the service, prints the run JSON and returns the exit code.
  `uv sync` installs the script, so `uv run tcg …` works locally, and `/app/.venv/bin/tcg` is
  on the image's `PATH`.
- **Rationale**: no new dependency (as decided in the interview). The optional `transport`
  and `sleep` arguments are the only test seams, and they are the standard httpx-family
  pattern.
- **Image check**: the CI `image` job's smoke test gains `docker run --rm tcg-pokedex:ci tcg
  --help`, which proves FR-037 inside the image.

## R9. Output and logging

- **Decision**: stdout gets one JSON object, the closed `SyncRun` serialized by its Pydantic
  model (`model_dump_json`), so the printed and stored shapes come from one definition.
  stderr gets JSON lines from a stdlib `logging` handler with a small JSON formatter,
  attached to the `tcg_pokedex` logger only, at INFO. `httpx2`'s per-request log lines stay
  silent because the root logger is not configured. Events are `sync.run.started`,
  `sync.failure` and `sync.run.finished`, plus `sync.run.error` when the store is unreachable
  or a run cannot be closed.
- **Alternatives**: `structlog` or `python-json-logger` (new dependencies for about 10 lines);
  `print` to stderr (cannot be captured with `caplog`, and has no levels).

## R10. Version and user agent

- **Decision**: `User-Agent: tcg-pokedex/<version> (+https://github.com/gabriel-barata/tgc-pokedex)`,
  where `<version>` is `importlib.metadata.version("tcg-pokedex")`. Both are constants in the
  adapter.

## R11. P1 end-to-end tests

- **Decision**: for US1 and US2, `test_command.py` calls `run_catalog_sync` in-process with
  a real Postgres (Testcontainers, migrated to head), the recorded fixture transport, a fake
  clock and an instant sleep. It asserts the stored rows, the printed JSON, the run record and
  the exit code. A separate small test checks that `cli.main(["sync", "catalog"])` dispatches
  to it.
- **Rationale**: this follows the spec's reading of Principle VI for a feature with no UI. It
  is logged in Complexity Tracking.
