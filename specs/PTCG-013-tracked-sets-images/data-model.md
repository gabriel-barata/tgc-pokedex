# Data model: Tracked sets & local image cache

Domain types live in `image_cache/domain.py` (pure) and the shared run types in
`sync_runs/domain.py`. Tables are added by migration `0003` (expand-only).

## Domain types

### Image cache (`image_cache/domain.py`)

| Type | Fields | Rules |
|---|---|---|
| `Language` (enum) | `pt`, `en` | |
| `CardSize` (enum) | `small`, `large` | Provider file: `low.webp`, `high.webp` |
| `ArtworkKind` (enum) | `logo`, `symbol` | |
| `CardToResolve` | `card_id`, `pt_image_url: str \| None`, `stored: StoredCardImage \| None`, `files_present: bool` | Read model for one card of a tracked set |
| `StoredCardImage` | `language: Language \| None`, `fetched_at` | `language` None = unavailable |
| `CardPlan` (enum) | `skip`, `try_pt_keep_en`, `try_pt_then_en`, `try_en` | From `plan_card` |
| `CardImages` | `small: bytes`, `large: bytes` | Both sizes or nothing |
| `Missing` | — | The provider has no such asset (404) |
| `ImageFailure` | `kind: card \| logo \| symbol`, `provider_id`, `reason` | Pydantic, stored in the run result |
| `CardOutcome` | `card_id`, `result: downloaded(language) \| cached \| unavailable \| failed(reason)` | One per card per run |
| `ArtworkToFetch` | `set_id`, `kind`, `url: str \| None`, `cached: bool` | One per stored set and kind |
| `ImageCounts` | `downloaded`, `cached`, `unavailable`, `failed` (all ≥ 0) | FR-013 |
| `ImageSyncResult` | `set_id: str \| None`, `counts: {cards: ImageCounts, artwork: ImageCounts}`, `failures: tuple[ImageFailure, ...]` (≤ 100) | `set_id` set only on a track-triggered run |
| `SetTracking` | `set_id`, `tracked: bool`, `total_cards`, `cached`, `unavailable`, `downloading: bool` | API body (FR-003) |

**`plan_card(card) -> CardPlan`** (FR-007, FR-009), the only copy of the rule:

| Stored row | Both files present | pt URL in catalog | Plan |
|---|---|---|---|
| `pt` | yes | any | `skip` → counted `cached` |
| `en` | yes | no | `skip` → counted `cached` |
| `en` | yes | yes | `try_pt_keep_en` |
| anything else (no row, unavailable, or files missing) | — | yes | `try_pt_then_en` |
| anything else | — | no | `try_en` |

Steps behind each plan, in the service:

- `try_pt_then_en`: fetch pt; `Missing` → `try_en`.
- `try_pt_keep_en`: fetch pt; `Missing` → `cached` (keep English, no download).
- `try_en`: look up the English image URL; none → `unavailable`; fetch it; `Missing` →
  `unavailable`.
- Any `ImageFailure` on the way → `failed`; nothing is written and the stored row is left
  as it was, so the next run retries (US3-3).

**`ImageResultBuilder`**: counts outcomes per category, keeps the first 100 failures, and
gets its status from the shared `run_status(aborted, failed)`.

### Run records (`sync_runs/domain.py`, moved from `catalog_sync`)

| Type | Change |
|---|---|
| `SyncKind` | adds `images` |
| `RunStatus` | moved, unchanged |
| `SyncRun[R]` | moved; generic over its `result` model (`SyncResult` for catalog, `ImageSyncResult` for images). Same JSON shape as before |
| `run_status(aborted, failed) -> RunStatus` | the failed / partial / succeeded rule, taken from `ResultBuilder.status` |
| `MAX_FAILURES` | moved (100) |
| `EXIT_CODES` | moved from `catalog_sync/command.py` |

## Tables (migration `0003_create_tracked_sets_and_images`)

`sync_runs` is unchanged; its table definition moves to `sync_runs/adapters/tables.py`.

### `tracked_sets` (owner-scoped, Principle V)

| Column | Type | Null | Notes |
|---|---|---|---|
| `owner_id` | uuid | no | FK `owners.id`, PK part |
| `set_id` | text | no | FK `sets.id`, PK part, indexed |
| `tracked_at` | timestamptz | no | From the injected clock |

Untracking deletes the row (tracking is user state, not provider data). FR-005 reads
`SELECT DISTINCT set_id FROM tracked_sets`.

### `card_images`

| Column | Type | Null | Notes |
|---|---|---|---|
| `card_id` | text | no | PK, FK `cards.id` |
| `language` | text | yes | `pt`, `en`, or NULL = unavailable; check constraint |
| `source` | text | no | `tcgdex` |
| `fetched_at` | timestamptz | no | When the image was downloaded or the card was last found unavailable |

Upserted by card id. A `cached` outcome (skip or keep English) writes nothing.

### `set_artwork`

| Column | Type | Null | Notes |
|---|---|---|---|
| `set_id` | text | no | FK `sets.id`, PK part |
| `kind` | text | no | `logo` \| `symbol`, PK part; check constraint |
| `source` | text | no | `tcgdex` |
| `fetched_at` | timestamptz | no | |

Only cached artwork has a row. "None at the provider" leaves no row and is checked again on
the next run (two requests per set at most).

### Progress query (FR-003)

For one set: `total_cards` = cards in `cards` for the set; `cached` = `card_images` rows with
a language; `unavailable` = rows with NULL language; `tracked` = a `tracked_sets` row for the
owner; `downloading` comes from the in-process `DownloadRegistry`, not the database.

## Files (`Settings.image_dir`)

```text
{image_dir}/
├── cards/{quote(card_id)}/small.webp
├── cards/{quote(card_id)}/large.webp
├── sets/{quote(set_id)}/logo.webp
└── sets/{quote(set_id)}/symbol.webp
```

Written atomically (temp file in the same directory, `fsync`, `os.replace`). Never deleted by
this feature (FR-015).

## Configuration

| Setting | Env var | Default | Production |
|---|---|---|---|
| `image_dir: Path` | `TCG_POKEDEX_IMAGE_DIR` | `data/images` (relative to the working directory; `backend/data/` is git-ignored) | `/data/images`, a named volume |
