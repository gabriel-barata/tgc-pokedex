# Feature Specification: Catalog sync from TCGdex (sets & cards)

**Feature Branch**: `PTCG-012-catalog-sync`

**Created**: 2026-10-11

**Status**: Draft

**Input**: `temp/specs/PTCG-012-catalog-sync.md` (grill-me interview, 2026-10-11, 17 decisions).
Trello card: https://trello.com/c/yOSi3NGZ/12-ptcg-012-catalog-sync-from-tcgdex-sets-cards

## Overview

The household operator runs one command, `tcg sync catalog`, which copies the Portuguese (`pt`)
physical Pokémon TCG catalog (series, sets and cards with their available variants) from
TCGdex into our own store. Each run is recorded and reported as a structured result, and
failures are counted, logged and recorded rather than swallowed. A bad card or set does not stop
the run.

This is the first feature that holds data. Every later catalog and collection feature reads
from this store and never calls the provider while serving a request (Principle IV):

| Consumer | Uses from this feature |
|---|---|
| PTCG-013 Tracked sets & image cache | card image URLs, set ids |
| PTCG-014 Sync worker & status page | the `tcg sync catalog` command, sync run records |
| PTCG-015 Browse sets | series, set name, logo/symbol, release date, card counts |
| PTCG-016 Set grid & card detail | card name, collector number, rarity, illustrator, variants, image, set info |
| PTCG-017 Ownership & completion | card ids, variant identity, official vs. total card counts |
| PTCG-020 Filter & search | rarity, variants, name |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Populate the catalog (Priority: P1)

As the household operator, I run `tcg sync catalog`. Afterwards our store holds every `pt`
physical set that has cards, with its series and its cards (variants, rarity, illustrator,
image URL), ready for the catalog and collection features.

**Why this priority**: No catalog or collection feature can work without this data. It is the
MVP of the whole M1 milestone.

**Independent Test**: Run the command against the fixture corpus on an empty store. Every
physical set with cards in the corpus, its series and all its valid cards are stored with
correct attributes. The result reports matching `created` counts and status `succeeded` (or
`partial` when the corpus includes failure fixtures).

**Acceptance Scenarios**:

1. **Given** an empty catalog, **When** the sync runs against a provider whose sets and cards
   are all valid, **Then** every physical set with at least one card is stored with its series
   and cards, every stored row has source `tcgdex` and a fetched-at time equal to the run's
   time, the status is `succeeded`, and the exit code is `0`.
2. **Given** the provider lists the TCG Pocket series (`tcgp`), **When** the sync runs,
   **Then** no request is made for that series or its sets or cards, nothing from it is stored,
   and it appears in no count.
3. **Given** a physical set whose card list is empty, **When** the sync runs, **Then** the set
   is not stored, its cards are not requested, and the result counts it in `sets.skipped`.
4. **Given** a series all of whose sets are skipped or failed, **When** the sync runs, **Then**
   the series is not stored.
5. **Given** a card available as normal and reverse, **When** it is synced, **Then** it is
   stored with variants `{normal, reverse}`.

---

### User Story 2 - Refresh without duplicates (Priority: P1)

As the operator, I can re-run the sync at any time. Changed provider data updates our rows,
unchanged data is reported as unchanged, and nothing is duplicated or deleted.

**Why this priority**: The sync is meant to run repeatedly (PTCG-014 schedules it). A sync that
duplicates or loses data on the second run would corrupt the catalog that ownership records
point at.

**Independent Test**: Run the command twice against the same fixtures. The second run reports
`created = 0` and `updated = 0` for every kind and the same failures as the first run; every
stored attribute is identical and only fetched-at has advanced.

**Acceptance Scenarios**:

1. **Given** a catalog already synced from the same provider data, **When** the sync runs again,
   **Then** every kind reports `created = 0`, `updated = 0` and `unchanged = fetched`, no row is
   duplicated, and every re-fetched row's fetched-at equals the new run's time.
2. **Given** a stored card whose name changed at the provider, **When** the sync runs, **Then**
   the stored name is updated, `cards.updated` counts it, and the other cards count as
   `unchanged`.
3. **Given** a stored card or set that the provider no longer lists, or whose fetch fails,
   **When** the sync runs, **Then** the stored row is left exactly as it was, including its old
   fetched-at.
4. **Given** a set that had cards and now lists none, **When** the sync runs, **Then** it counts
   as `skipped`, and its previously stored rows remain untouched.

---

### User Story 3 - Visible, non-fatal failures (Priority: P2)

As the operator, when something goes wrong (a malformed card, a set that won't load, TCGdex
being down), I see it counted, logged and recorded with a clear status and exit code, and every
valid piece of data is still stored.

**Why this priority**: A sync that silently drops data, or that one bad card can block, would
leave the catalog quietly incomplete. It ranks below P1 because the happy path delivers value on
its own.

**Independent Test**: Run the command against fixtures that include a malformed card, a card
with no variants, a card returning "not found", a set failing with repeated server errors, and
(separately) a series index failing with repeated server errors. Check the counts, the recorded
failures, the status, the exit code, and that valid data is stored.

**Acceptance Scenarios**:

1. **Given** a card payload missing its name, **When** the sync runs, **Then** that card counts
   in `cards.failed` with a reason, is logged and listed in the run's failures, its set and the
   other cards are stored, the status is `partial`, and the exit code is `1`.
2. **Given** a card whose five variant flags are all false, **When** the sync runs, **Then** it
   counts as failed with reason "no variants" and is not stored.
3. **Given** a card request answered with "not found" (404), **When** the sync runs, **Then**
   the card fails immediately with no retry.
4. **Given** a card request answered with a server error once and then successfully, **When**
   the sync runs, **Then** the card is stored and nothing counts as failed.
5. **Given** a set request answered with a server error on every attempt, **When** the sync
   runs, **Then** the set counts in `sets.failed`, none of its cards are requested, and the
   other sets are synced.
6. **Given** the series index request answered with a server error on every attempt, **When**
   the sync runs, **Then** the run aborts with status `failed` and an error message, no catalog
   row is written or changed, and the exit code is `2`.
7. **Given** any run, **When** it starts, **Then** a run record with status `running` exists
   before any catalog write; **When** it ends, normally or through an unexpected error, **Then**
   the record is closed with its final status, finish time, duration, and result or error.

---

### Edge Cases

- **Empty sets**: 22 physical sets list zero cards in `pt` although their declared total is
  non-zero (base1–3, ex1, ex7–ex10, dp1–3, hgss1–4, col1, dv1, bw11, g1, sma, sm115, cel25cc).
  They are skipped (FR-003).
- **Partial sets**: `30th` lists 2 of 128 cards; `smp`, `swshp` and `svp` miss a few. They are
  synced with exactly the cards listed (FR-004).
- **Non-numeric collector numbers**: `75a`, `TG25`, `SWSH158`, `SV037` are stored verbatim.
- **Placeholder rarity**: some cards (e.g. in `xy0`, `30th`) carry the literal rarity `"None"`,
  which is stored as no rarity.
- **Missing media**: about 1,161 card briefs have no image, 77 sets have no logo and 20 have no
  symbol. These are stored as absent, not as errors.
- **Padded names**: names with leading or trailing whitespace (e.g.
  `"EX O Retorno da Equipe Rocket "`) are trimmed.
- **Card claims another set**: a card's own set reference is ignored; it belongs to the set
  whose card list contained it (FR-016).
- **Rate limiting**: a "too many requests" (429) answer is retried, honouring the provider's
  requested wait when given.
- **More than 100 failures**: the stored and printed failure list keeps the first 100; counts
  and log lines stay complete (FR-031).
- **Unexpected error mid-run**: sets already committed stay fully written, the set in progress
  is not written at all, and the run record is closed as `failed` (FR-023, FR-035).
- **Process killed outright**: the run record stays `running` with no finish time, which serves
  as evidence of the crash.
- **Store unreachable at start**: no run record can be created; the command logs the error and
  exits with code `2` without contacting the provider.
- **Overlapping runs**: not prevented in this feature (PTCG-014); they are harmless because
  writes are idempotent and committed per set.

## Requirements *(mandatory)*

### Functional Requirements

#### Scope and filtering

- **FR-001**: The sync MUST read the TCGdex Portuguese (`pt`) catalog only. The `pt-br`
  catalog (TCG Pocket only) is never used.
- **FR-002**: A set belongs to TCG Pocket when its series id is `tcgp`; this rule MUST be
  defined in exactly one place. Pocket series, sets and cards MUST never be requested, stored
  or counted.
- **FR-003**: A physical set whose provider card list is empty MUST be skipped: not stored, its
  cards not requested, and counted in `sets.skipped`.
- **FR-004**: A partial set MUST be synced with exactly the cards the provider lists.
- **FR-005**: A series MUST be stored only when at least one of its sets is stored in the same
  run. Its attributes come from the series reference in the set's payload.

#### Domain model

Every catalog row MUST carry its source (the constant `tcgdex`) and its fetched-at time (UTC,
from the injected clock).

- **FR-006**: A **Series** has an id (provider id, e.g. `sv`) and a name.
- **FR-007**: A **Set** has an id (e.g. `sv01`), its series, a name, a release date, an
  official card count, a total card count, and an optional logo URL and symbol URL.
- **FR-008**: A **Card** has an id (e.g. `sv01-001`), its set, a collector number (text, kept
  verbatim), a name, an optional rarity, an optional illustrator, an optional image URL, and its
  variants.
- **FR-009**: A **Variant** is one of `normal`, `reverse`, `holo`, `first_edition`, `w_promo`,
  mapped from the provider flags `normal`, `reverse`, `holo`, `firstEdition` and `wPromo`. A
  card's variants are the non-empty set of variants whose flag is true. This is the variant
  identity that ownership (PTCG-017) uses. Stamps, foil patterns and sizes are not modelled.
- **FR-010**: No other provider fields are stored (category, HP, types, attacks, legality, dex
  ids, regulation mark, third-party data, pricing, provider update time, detailed variants).
- **FR-011**: No collector-number sort key is derived here; ordering belongs to PTCG-016.
- **FR-012**: Catalog data is shared reference data, not user-owned. It has no owner, and
  Principle V does not apply to it.

#### Boundary validation and hygiene

Every provider payload MUST be validated at the boundary against one schema per payload shape,
and the provider-to-domain mapping MUST live in exactly one place (Principle II, Security
constraint).

- **FR-013**: Every text value MUST be trimmed of leading and trailing whitespace.
- **FR-014**: An optional text field (rarity, illustrator, logo, symbol, image) that is absent,
  empty or whitespace-only MUST be stored as absent. A rarity of `"None"` MUST be stored as
  absent. Other rarity labels are stored as given (after trimming), with no translation or
  fixed list.
- **FR-015**: Image, logo and symbol URLs MUST be stored exactly as the provider gives them
  (base URLs without quality or extension suffix).
- **FR-016**: A card's set MUST be the set being synced, the one whose card list contained it.
  The set reference inside the card payload is ignored.
- **FR-017**: A card MUST be treated as invalid (counted as failed, not stored) when it lacks
  an id, collector number or name, or when no variant flag is true (reason "no variants").
- **FR-018**: A set MUST be treated as invalid (counted as failed, its cards not requested, not
  stored) when it lacks an id, name, series id, series name, release date, official card count
  or total card count.

#### Persistence

- **FR-019**: Rows MUST be inserted or updated by provider id, so the store holds the current
  state. The constitution's "history MUST be appended, never overwritten" (Principle IV) is read
  as applying to time-series data (prices and exchange rates, PTCG-021); catalog corrections
  are not history, and the sync run records are the audit trail for catalog syncs.
- **FR-020**: Nothing MUST ever be deleted. A stored row that a run does not see (removed by the
  provider, failed to fetch, or its set now skipped) MUST be left exactly as it was, including
  its fetched-at.
- **FR-021**: Fetched-at MUST be set to the run's time on every successful fetch of that
  entity, even when no other attribute changed.
- **FR-022**: A row counts as `updated` only when at least one stored attribute other than
  fetched-at changed; otherwise it counts as `unchanged`.
- **FR-023**: Writes MUST be committed per set: the series (when new or changed), the set and
  its valid cards are written together, all or nothing, after that set's card fetches finish. A
  crash leaves every completed set fully written and no set half-written.
- **FR-024**: When a set is valid but all its card fetches fail, the set (and its series) MUST
  still be stored.
- **FR-025**: Schema changes MUST be expand-only, per the migration rule in
  `deploy/README.md`.

#### Run semantics

- **FR-026**: Every run MUST be a full sync. There is no incremental mode, per-set filter or dry
  run.
- **FR-027**: Provider traffic MUST respect these limits, fixed in the provider adapter (not
  user configuration):
  - at most 8 requests in flight;
  - a 10-second timeout per request;
  - up to 3 attempts with exponential backoff (about 1 s, 2 s, 4 s), only on network errors,
    server errors (5xx) and "too many requests" (429), honouring a provider-requested wait when
    present;
  - any other client error (4xx) fails immediately with no retry;
  - an identifying user agent: `tcg-pokedex/<version> (+<repository URL>)`.
- **FR-028**: Failures MUST be handled at three levels, after retries:

  | Level | Trigger | Effect |
  |---|---|---|
  | Index (series list, or a series' set list) | request fails or payload invalid | run aborts with `failed`; no catalog writes |
  | Set | request fails or payload invalid (FR-018) | `sets.failed` + 1; its cards not requested; run continues |
  | Card | request fails or payload invalid (FR-017) | `cards.failed` + 1; run continues |

  The whole index (the series list and every physical series' set list) MUST be read before
  any catalog write, so an index failure writes nothing. There is no failure-ratio abort
  threshold; continuing is safe because of FR-020.
- **FR-029**: Run status MUST be `succeeded` when the run completes with zero failures,
  `partial` when it completes with at least one set or card failure, and `failed` when it aborts
  at the index level or through an unexpected error.
- **FR-030**: The result MUST report counts per kind, with `fetched = created + updated +
  unchanged`:
  - series: `fetched`, `created`, `updated`, `unchanged`
  - sets: `fetched`, `created`, `updated`, `unchanged`, `skipped`, `failed`
  - cards: `fetched`, `created`, `updated`, `unchanged`, `failed`

  `fetched` means valid payloads received and stored; skipped and failed entities are not in
  it. A series is counted once per run, however many of its sets are stored.
- **FR-031**: Each failure MUST be recorded as kind, provider id and reason, and logged as one
  structured line. The run's stored and printed result keeps the first 100 failures; the counts
  stay exact.
- **FR-032**: Duration MUST be measured with the injected clock, from run start to close.

#### Sync run records

- **FR-033**: Each run MUST be recorded with: an id, a kind (`catalog`; later `images` and
  `prices`), a source (`tcgdex`), a status (`running`, `succeeded`, `partial`, `failed`), a
  start time, and, once closed, a finish time, a duration in milliseconds, the result (FR-030
  counts and FR-031 failures) and an error message (only for `failed`). The record format is
  generic so that image (PTCG-013) and price (PTCG-021) syncs can reuse it.
- **FR-034**: The result's shape MUST be defined once and validated both when written and when
  read.
- **FR-035**: The run record MUST be created with status `running`, and committed, before any
  catalog write, and closed in a separate write at the end. On an unexpected error the record
  MUST still be closed as `failed` with the error. Run records are never deleted.
- **FR-036**: Run records have no owner. Their code lives in the catalog-sync slice until a
  second slice writes them.

#### Command

- **FR-037**: The command MUST be `tcg sync catalog`, available both in the local development
  environment and inside the production image (PTCG-014's worker relies on it).
- **FR-038**: The command takes no flags. Configuration comes from the existing application
  settings (including the database URL).
- **FR-039**: On completion, standard output MUST carry exactly one JSON object with: run id,
  kind, status, start time, finish time, duration in milliseconds, counts (FR-030), failures
  (FR-031) and, when failed, the error.
- **FR-040**: Standard error MUST carry structured JSON log lines: run start, each failure, run
  end.
- **FR-041**: Exit codes MUST be `0` for `succeeded`, `1` for `partial` and `2` for `failed`.

### Key Entities *(include if feature involves data)*

- **Series**: a group of sets published together (e.g. Scarlet & Violet). Identified by the
  provider id; stored only when one of its sets is stored.
- **Set**: one expansion, identified by the provider id, belonging to one series. Holds name,
  release date, official and total card counts, and optional logo and symbol.
- **Card**: one card in one set, identified by the provider id. Holds collector number, name,
  optional rarity, illustrator and image, and its variants.
- **Variant**: one of five printings a card can exist in (`normal`, `reverse`, `holo`,
  `first_edition`, `w_promo`); a card has at least one.
- **Sync Run**: one execution of a sync, with kind, source, status, timing and its result or
  error. Generic across catalog, image and price syncs.
- **Sync Result**: the per-kind counts plus up to 100 failures, each with kind, provider id and
  reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On an empty store, one run against the fixture corpus stores exactly the expected
  series, sets and cards with correct attributes, and exits with the code its status implies.
- **SC-002**: A second run against the same fixtures reports `created = 0` and `updated = 0` for
  every kind and leaves every stored attribute except fetched-at identical.
- **SC-003**: Every failure fixture is counted at the right level, appears in the stored
  failures and in the log, and never prevents valid data from being stored (except index
  aborts, which write nothing).
- **SC-004**: No automated test reaches the real provider, and no TCG Pocket endpoint is ever
  requested.
- **SC-005**: Every run leaves a run record whose status, counts and duration match the printed
  result.
- **SC-006**: A full live run against TCGdex (about 14,000 requests) completes in minutes, not
  hours (expected under 15 minutes). This is checked manually, not in CI.

## Assumptions

- **Provider facts** (checked against the live API on 2026-10-11): `pt` has 12 series, of which
  `tcgp` (11 sets) is TCG Pocket. 114 physical sets list 13,907 cards. A set's detail returns
  card briefs only (id, collector number, name, optional image); rarity, variants and
  illustrator come from each card's own detail, so a full sync makes about 14,000 requests. The
  flat set list does not say which series a set belongs to; each series' detail lists its sets.
  Every physical set has a release date, a series reference and both card counts.
- **"Run's time"** for fetched-at is the run's start time from the injected clock, so every row
  written by one run carries the same timestamp.
- **"All sets and cards"** in the card's acceptance criteria means every physical set and card in
  the fixture corpus.
- **Fixture corpus**: real recorded payloads (kept verbatim except for trimmed card lists and a
  series index trimmed to the curated series plus `tcgp`) and hand-made failure cases. Every
  request the tests make has an explicit fixture, with no catch-all. A README beside the
  fixtures records each real fixture's endpoint and recording date and marks the hand-made ones.
  There is no recording script. The corpus covers: a modern set with `{normal, reverse}` cards;
  a promo set with non-numeric collector numbers; a `"None"` rarity; a card brief without an
  image; an empty set; the `tcgp` series and a Pocket set (asserted never requested); a card
  missing its name; a card with no variants; a card returning 404; a card returning 500 then
  200; a set returning 500 three times; a series index returning 500 three times; a
  whitespace-padded name.
- **P1 end-to-end test** (Principle VI): this feature has no UI. The "through the real UI" rule
  is read as applying to stories with a UI surface. For US1 and US2 the end-to-end test runs the
  `tcg` command in-process against the real database engine and the recorded fixtures, and
  checks the stored data, the printed JSON and the exit code.
- **Tests** use an injected fake clock, and retry backoff waits do not slow them down.
- **Dependencies**: PTCG-005 (database foundation) and PTCG-006 (CI) are merged. The existing
  clock port and application settings are reused.

## Out of Scope

- A guard against overlapping runs → PTCG-014 (scheduler and the "Sincronizar agora" button).
  Preferred approach there: a database advisory lock held for the run, not a check for a
  `running` record, which a crash would leave stale.
- Scheduling and the worker service → PTCG-014.
- Image download, English image fallback and serving images → PTCG-013.
- Prices → PTCG-021.
- An English-language fallback for the 22 empty sets (no Icebox card for now).
- Stamped, foil-pattern and jumbo variants.
- Rarity normalization or translation.
- Incremental sync, a per-set filter, dry run or any other command flags.
- Reporting rows a run did not see, and deleting data the provider removed.
- A live provider drift-check job.

## Planning Inputs

Decisions from the interview that belong to `/speckit-plan`, recorded here so they are not lost.
They are not behavior requirements.

- **Command wiring**: a console script named `tcg`, built with the standard library's argument
  parser (no new dependency), runnable as `uv run tcg sync catalog` and as `tcg sync catalog` in
  the image.
- **Run record storage**: a generic `sync_runs` table (UUID id; `result` as JSON; nullable
  `finished_at`, `duration_ms`, `result`, `error`). New tables are imported into
  `tcg_pokedex/schema.py` so Alembic sees them.
- **Validation**: one Pydantic model per provider payload shape and one for the run result.
- **Ports**: a `CatalogProvider` port (TCGdex adapter + one shared in-memory fake), a catalog
  repository port with run-record persistence (Postgres adapter + one shared fake), and the
  existing `Clock`. The domain core (counts, created/updated/unchanged decisions, status) is
  pure. Each port has one contract suite run against the fake and the real adapter.
- **HTTP and fixtures**: the backend's dev dependency is `httpx2` (a fork) and the card names
  `respx`; confirm `respx` works with the adapter's client or pick an equivalent. Any new
  dependency needs a one-line justification (Quality Gate 4).
- **Traversal**: series list → each non-`tcgp` series' detail → set detail → card detail.
- **Concurrency model** for 8 requests in flight (async or threads) and how to make backoff
  waits instant in tests (e.g. an injectable sleep) are plan decisions.
- **Slice layout**: follow `clock/` and `owners/`: a `catalog_sync/` slice with domain, ports,
  fakes, adapters (TCGdex, Postgres) and the command.
- **TDD gate**: update the source and test paths in `.github/scripts/check-tdd-order.sh` if the
  command or fixtures add a new location.
- **Docs in the same PR**: CLAUDE.md's Commands section gains `uv run tcg sync catalog`. (The
  spec-kit interview step is already committed on this branch.)
- **Constitution Check entries**: the FR-019 reading (append-only applies to prices and
  exchange rates), FR-012/FR-036 (catalog and run records are not owner-scoped), and the P1
  end-to-end reading above. If `/speckit-analyze` still flags the end-to-end reading, log it in
  Complexity Tracking.
