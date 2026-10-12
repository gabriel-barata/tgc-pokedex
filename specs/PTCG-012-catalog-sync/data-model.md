# Data Model: Catalog sync from TCGdex

The domain types live in `catalog_sync/domain.py`, the tables in
`catalog_sync/adapters/tables.py`, and the migration is `0002`, which only adds tables
(FR-025). Catalog rows and run records have no owner (FR-012, FR-036).

## Domain types

| Type | Fields | Rules |
|---|---|---|
| `Variant` (enum) | `normal`, `reverse`, `holo`, `first_edition`, `w_promo` | Declaration order is the canonical storage order (FR-009) |
| `Series` | `id`, `name` | Non-empty trimmed text (FR-006, FR-013) |
| `CardSet` | `id`, `series_id`, `name`, `release_date: date`, `official_count: int`, `total_count: int`, `logo_url: str \| None`, `symbol_url: str \| None` | FR-007, FR-018 |
| `Card` | `id`, `set_id`, `collector_number`, `name`, `rarity \| None`, `illustrator \| None`, `image_url \| None`, `variants: frozenset[Variant]` | `variants` non-empty; `collector_number` kept verbatim (FR-008, FR-011, FR-017) |
| `SetListing` | `card_set: CardSet`, `series: Series`, `card_ids: tuple[str, ...]` | What the provider returns for one set. `series` comes from the set payload (FR-005) |
| `Failure` | `kind: "set" \| "card"`, `provider_id`, `reason` | FR-031 |
| `Fetched[T]` | `value: T`, `fetched_at: datetime` | A stored row with its fetch time |
| `StoredCatalog` | `series: Fetched[Series] \| None`, `card_set: Fetched[CardSet] \| None`, `cards: Mapping[str, Fetched[Card]]` | What the store already holds for one set |
| `SetBatch` | `series: Series \| None`, `card_set: CardSet`, `cards: tuple[Card, ...]` | One per-set write; `series` is `None` when this run already wrote it |

The source (`tcgdex`) is a domain constant (`SOURCE`). It is not a field of each entity,
because it never varies. The repository writes it on every row.

### Domain functions

- `is_pocket_series(series_id) -> bool`: `series_id == "tcgp"`. This is the only definition
  of the rule (FR-002).
- `classify(stored: T | None, fetched: T) -> Change`: `CREATED` if nothing is stored,
  `UNCHANGED` if equal, `UPDATED` otherwise. Equality covers every entity field, and source
  and fetched-at are not entity fields (FR-022).
- `plan_set(stored, listing, cards, series_written) -> (SetBatch, changes)`: builds one set's
  write and its per-row classifications. The series is included (and counted) only when it is
  not yet in `series_written` (FR-005, FR-030 "counted once per run").
- `ResultBuilder`: collects counts and failures. It keeps only the first 100 failures, and
  the counts stay exact (FR-031). `status()` returns `succeeded`, `partial` or `failed`
  (FR-029).

## Run record and result

| Type | Fields | Rules |
|---|---|---|
| `SyncKind` (enum) | `catalog` | Later kinds (`images`, `prices`) are added by the PTCG-013 and PTCG-021 PRs |
| `RunStatus` (enum) | `running`, `succeeded`, `partial`, `failed` | |
| `KindCounts` | `fetched`, `created`, `updated`, `unchanged` | Validator: `fetched == created + updated + unchanged` |
| `SetCounts` | `KindCounts` + `skipped`, `failed` | |
| `CardCounts` | `KindCounts` + `failed` | |
| `SyncCounts` | `series: KindCounts`, `sets: SetCounts`, `cards: CardCounts` | FR-030 |
| `SyncResult` | `counts: SyncCounts`, `failures: list[Failure]` (≤ 100) | Pydantic, validated on write and on read (FR-034) |
| `SyncRun` | `id: UUID`, `kind`, `source`, `status`, `started_at`, `finished_at \| None`, `duration_ms \| None`, `result: SyncResult \| None`, `error \| None` | Pydantic. Its JSON form is also the command's stdout (FR-039) |

### Run state transitions

```text
(none) ──start_run──▶ running ──finish_run──▶ succeeded | partial | failed
                         │
                         └── process killed: stays running, finished_at null (crash evidence)
```

- `running`: `finished_at`, `duration_ms`, `result` and `error` are null. It is committed
  before any catalog write (FR-035).
- Closed: `finished_at` and `duration_ms` (clock difference, FR-032) and `result` are set.
  `error` is set only when the status is `failed`. Records are never deleted.

## Tables

All catalog tables carry `source text NOT NULL` and `fetched_at timestamptz NOT NULL`. Their
ids are TCGdex ids (text primary keys). Writes are `INSERT … ON CONFLICT (id) DO UPDATE` and
never `DELETE` (FR-019, FR-020).

### `series`

| Column | Type | Null |
|---|---|---|
| `id` | text PK | no |
| `name` | text | no |
| `source`, `fetched_at` | text, timestamptz | no |

### `sets`

| Column | Type | Null |
|---|---|---|
| `id` | text PK | no |
| `series_id` | text FK → `series.id`, indexed | no |
| `name` | text | no |
| `release_date` | date | no |
| `official_count` | integer | no |
| `total_count` | integer | no |
| `logo_url` | text | yes |
| `symbol_url` | text | yes |
| `source`, `fetched_at` | text, timestamptz | no |

### `cards`

| Column | Type | Null |
|---|---|---|
| `id` | text PK | no |
| `set_id` | text FK → `sets.id`, indexed | no |
| `collector_number` | text | no |
| `name` | text | no |
| `rarity` | text | yes |
| `illustrator` | text | yes |
| `image_url` | text | yes |
| `variants` | text[], `CHECK (cardinality(variants) > 0)` | no |
| `source`, `fetched_at` | text, timestamptz | no |

### `sync_runs`

| Column | Type | Null |
|---|---|---|
| `id` | uuid PK | no |
| `kind` | text | no |
| `source` | text | no |
| `status` | text | no |
| `started_at` | timestamptz | no |
| `finished_at` | timestamptz | yes |
| `duration_ms` | integer | yes |
| `result` | jsonb (`SyncResult`) | yes |
| `error` | text | yes |

## Provider → domain mapping (TCGdex `pt`)

This mapping is defined once, in `catalog_sync/adapters/tcgdex_payloads.py`. Every text value
is trimmed, and blank optional text becomes `None`.

| Domain field | TCGdex field | Endpoint |
|---|---|---|
| series ids | `[].id` | `GET /v2/pt/series` |
| set ids of a series | `sets[].id` | `GET /v2/pt/series/{id}` |
| `CardSet.id`, `name`, `release_date` | `id`, `name`, `releaseDate` | `GET /v2/pt/sets/{id}` |
| `CardSet.official_count`, `total_count` | `cardCount.official`, `cardCount.total` | same |
| `CardSet.logo_url`, `symbol_url` | `logo`, `symbol` (optional) | same |
| `Series.id`, `name`; `CardSet.series_id` | `serie.id`, `serie.name` | same |
| `SetListing.card_ids` | `cards[].id` | same |
| `Card.id`, `collector_number`, `name` | `id`, `localId`, `name` | `GET /v2/pt/cards/{id}` |
| `Card.rarity` | `rarity` (`"None"` → `None`) | same |
| `Card.illustrator`, `image_url` | `illustrator`, `image` (optional) | same |
| `Card.variants` | `variants.{normal, reverse, holo, firstEdition, wPromo}` that are true | same |
| `Card.set_id` | the set being synced; `card.set` is ignored (FR-016) | n/a |
