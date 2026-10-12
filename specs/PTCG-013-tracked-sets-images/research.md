# Research: Tracked sets & local image cache

Phase 0 of `/speckit-plan`. Each entry records a decision, why it was made, and what was
rejected. Provider facts were probed live on 2026-10-12.

## R1. Provider asset facts

- **Card images**: the catalog's `image_url` (e.g. `https://assets.tcgdex.net/pt/sv/sv01/001`)
  is a base. `…/low.webp` is the small size (~19 KB) and `…/high.webp` the large one
  (~73 KB). A missing asset answers `404`.
- **English fallback**: `GET https://api.tcgdex.net/v2/en/cards/{card_id}` returns the card
  with its own `image` base (e.g. `https://assets.tcgdex.net/en/swsh/swshp/SWSH032`), or
  `404` when TCGdex has no English card with that id. The image field may also be absent.
- **Who needs it**: regular pt sets sampled (sv01, swsh1, sm1, sv08, me01, bw1, xy1) have an
  image for every card. Promo sets do not: `svp` 46 of 218 and `swshp` 271 of 302 cards
  have no pt image. `swshp-SWSH032` has an English image; `svp-085` has none, so it becomes
  unavailable.
- **Logos**: `{logo_url}.webp` works (~15 KB).
- **Symbols**: every catalog `symbol_url` is under `/univ/` (e.g.
  `https://assets.tcgdex.net/univ/sv/sv01/symbol`), and **every `/univ/…/symbol.webp` probed
  answers 404** (base1, xy1, swsh1, sm1, sv01, sv10, me01). The same path under `/pt/` (and
  `/en/`) answers 200.
- **Decision**: the adapter requests `{url}.webp`. For a symbol URL under `/univ/` that
  answers 404, it retries once with `/univ/` replaced by `/pt/`. This TCGdex quirk lives
  only in the image adapter. A 404 after that means "the provider has none" (FR-011), not a
  failure. Flagged as **FIX-1** in plan.md so it gets its own test + fix pair.
- **Alternatives**: PNG (3–4× larger, no benefit for a grid); building symbol URLs ourselves
  from series/set ids (a second copy of the provider's URL scheme, Principle II); treating
  the 404 as "no symbol" (every set would lose its symbol on PTCG-015's sets page).

## R2. Format and validation

- **Decision**: WebP is the preferred format. Request and store WebP only, exactly as
  received, served as `image/webp`. A response is
  accepted only when it is `200`, has the RIFF/WEBP magic bytes, and is at most 5 MB.
  Anything else is a failed download with its reason (`not an image`, `too large`,
  `HTTP 500 after 3 attempts`, …). No re-encoding.
- **Rationale**: every browser the household uses decodes WebP. Checking magic bytes is a
  few lines and covers "a response that is not an image" (an HTML error page answered with
  `200`). The size cap guards the disk.
- **Alternatives**: Pillow to verify or resize (a new dependency for no requirement).

## R3. One shared TCGdex HTTP client

- **Decision**: move the client construction, user agent, timeout, connection limit, retry
  and `Retry-After` handling from `catalog_sync/adapters/tcgdex.py` into a shared module,
  `tcg_pokedex/tcgdex/http.py` (`TcgdexHttp.get(url) -> bytes`, raising
  `RequestFailedError(reason, status)`). The catalog adapter and the new image adapter both
  use it. A refactor commit before the image work; the catalog tests stay green unchanged.
- **Rationale**: the provider access policy (8 in flight, 3 attempts, backoff, identifying
  user agent) is knowledge, and Principle II wants one copy of it. A second copy would also
  let the two jobs drift apart in politeness toward TCGdex.
- **Alternatives**: the image adapter imports the catalog adapter's private helpers (a
  cross-slice dependency on internals); a copy of `_get` (two retry policies).

## R4. Concurrency

- **Decision**: card images of one set are resolved on a `ThreadPoolExecutor(max_workers=8)`
  owned by the image service, one task per card (pt attempt → English lookup → English
  download). Artwork runs on the same pool. Requests share one `TcgdexHttp` client with
  `Limits(max_connections=8)`, so at most 8 are in flight. Database writes happen on the
  calling thread after each set's tasks finish.
- **Rationale**: the pt → en fallback is a domain rule (FR-007), so it must sit in the
  service, not inside the adapter. A 250-card set is ~500 requests: about 30–60 s at 8 in
  flight, well inside SC-001 (10 min).
- **Alternatives**: concurrency inside the adapter (would push the fallback rule into it);
  `asyncio` (the rest of the backend is synchronous).

## R5. Image storage

- **Decision**: files on disk under `Settings.image_dir` (`TCG_POKEDEX_IMAGE_DIR`, default
  `data/images` relative to `backend/`, git-ignored). Layout:
  `cards/{card_id}/small.webp`, `cards/{card_id}/large.webp`, `sets/{set_id}/logo.webp`,
  `sets/{set_id}/symbol.webp`. Ids are percent-encoded (`quote(id, safe="")`); the ids `.`
  and `..` are rejected.
- **Atomic writes**: each file is written to a temporary file in the same directory, then
  `fsync`ed and moved into place with `os.replace`. A card's two sizes are both downloaded
  and validated in memory before either is written, so a card is stored in both sizes or not
  at all (edge case "one size fails"). Overlapping runs write identical files whole.
- **Deployment (FR-016)**: `deploy/compose.yml` mounts a named volume `images` at
  `/data/images`; the Dockerfile creates `/data/images` owned by the `app` user (so a fresh
  named volume inherits the owner) and sets `TCG_POKEDEX_IMAGE_DIR=/data/images`.
  `compose.e2e.yml` needs nothing (the directory lives in the container).
- **Disk**: ~92 KB per card, ~23 MB for a 250-card set; tracking all 92 sets would be ~1.3 GB.
- **Alternatives**: Postgres `bytea` (bloats the database and its backups, and serving needs
  a query); object storage (a new service for a home server).

## R6. What the database records

- **Decision**: `card_images` holds one row per card that was resolved: `language` (`pt`,
  `en`, or NULL when unavailable), `source` (`tcgdex`) and `fetched_at`. `set_artwork` holds
  one row per cached logo or symbol. The files are the content; the rows are provenance
  (Principle IV) and progress (FR-003).
- **Skip rule (FR-009, SC-003)**: a card is skipped only when its row says `pt` **and** both
  files exist. Checking the files is two `stat` calls and means a lost volume refills itself
  on the next run instead of being skipped forever.
- **Unavailable cards** need a row, because FR-003 reports their count and TCGdex's English
  answer is not in our catalog.
- **Alternatives**: files only (no source or fetched-at, Principle IV); rows only as truth
  (a lost volume is never repaired).

## R7. Background download on track

- **Decision**: `PUT /api/sets/{set_id}/tracking` adds a FastAPI `BackgroundTasks` task when
  the set was not tracked before and no download for it is running. The task runs
  `sync_images` scoped to that set in the app process (Starlette runs sync tasks on its
  thread pool after the response is sent).
- **"Download running" (FR-003)**: an in-process `DownloadRegistry` (a set of set ids behind
  a lock) on `app.state`. `start(set_id)` returns `False` when one is already running, which
  also stops a second download (US1-5, retrack). After a restart the registry is empty, so
  the set no longer reports a download (edge case "app restarted").
- **Rationale**: no scheduler or worker exists until PTCG-014. An in-process flag cannot go
  stale; a `running` `sync_runs` row would stay `running` forever after a crash.
- **Known limit**: a `tcg sync images` run in another process is not reported as "a download
  running". PTCG-014 owns the cross-process run guard and status page.
- **Alternatives**: a `running` row per set in the database (goes stale after a crash);
  a thread started by hand (BackgroundTasks already does that and TestClient waits for it,
  which makes the end-to-end test deterministic).

## R8. Run records shared by both syncs

- **Decision**: move the run record out of `catalog_sync` into a `sync_runs/` package, as
  PTCG-012 planned once a second slice writes runs: `SyncKind` (`catalog`, `images`),
  `RunStatus`, `SyncRun[R]` (Pydantic generic over the result model), `run_status(aborted,
  failed)`, `EXIT_CODES`, the `sync_runs` table, a `SyncRunRepository` port with its fake and
  Postgres adapter and one contract suite, and the JSON-lines logging set-up used by both
  commands. `CatalogRepository` loses `start_run`/`finish_run`/`get_run`; `sync_catalog`
  takes a `SyncRunRepository`. A refactor commit, no schema change.
- **Rationale**: status rules, exit codes and the stored shape are one piece of knowledge
  (Principle II).
- **Alternatives**: the image slice imports from `catalog_sync` (wrong dependency
  direction); a second run table (two audits of the same thing).

## R9. Serving

- **Decision**: `GET /api/images/cards/{card_id}/{size}` (`small` | `large`) and
  `GET /api/images/sets/{set_id}/{kind}` (`logo` | `symbol`) return the file with
  Starlette's `FileResponse` (`image/webp`, `ETag`, `Last-Modified`) and
  `Cache-Control: public, max-age=604800`. A missing file is `404`. No database read and no
  provider call.
- **Rationale**: one week is long-lived for a household app, and the `ETag` makes
  revalidation cheap. A card upgraded from English to pt keeps its URL, so `immutable`
  would pin the old image.
- **Alternatives**: `max-age` of a year with a version query string (needs every consumer to
  know the fetched-at stamp, which no endpoint exposes yet); `StaticFiles` mount (no
  per-route cache header, no id validation).

## R10. API shape for tracking

- **Decision**: `GET`, `PUT` and `DELETE` on `/api/sets/{set_id}/tracking`, each returning
  the same `SetTracking` body (tracked, total cards, cached, unavailable, downloading). `PUT`
  and `DELETE` are idempotent; an unknown set id is `404`. The owner is
  `HOUSEHOLD_OWNER_ID`, chosen in the route through one dependency, so PTCG-031 replaces
  only that dependency.
- **Rationale**: PTCG-015 owns the sets list endpoint and can add these fields per set; this
  ticket exposes the per-set resource it needs to test US1–US2.
- **Alternatives**: `POST /track` and `POST /untrack` (not idempotent by HTTP semantics); a
  `GET /api/sets` list here (PTCG-015's scope).

## R11. End-to-end test for the P1 story

- **Decision**: as in PTCG-012, the P1 end-to-end test runs in process: FastAPI `TestClient`
  on `create_app` with real Postgres (Testcontainers), a temporary image directory and the
  TCGdex `MockTransport` fixtures. It tracks a set, waits for the background task (TestClient
  runs it before returning), then fetches each image and asserts that the transport saw no
  request while serving. Logged in Complexity Tracking.
- **Rationale**: the feature has no screen, so a Playwright test has nothing to drive, and
  the e2e stack has no fake TCGdex to download from. SC-004 is covered by the existing e2e
  origin guard staying green and by the serving test above.

## R12. Test fixtures

- **Decision**: move `tests/catalog_sync/tcgdex_fixtures.py` to `tests/tcgdex/` and let its
  route table also take absolute URLs, so it serves both hosts (`api.tcgdex.net`, any
  language, and `assets.tcgdex.net`). Image bodies are a tiny hand-made WebP
  (a valid 1×1 file, a few dozen bytes) checked in once and reused. Recorded English card
  payloads are trimmed to `id` and `image`, plus one without `image`.
- **Rationale**: Principle VI (recorded fixtures, no network); one helper for both slices.
