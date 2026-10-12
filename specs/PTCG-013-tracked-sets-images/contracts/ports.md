# Contract: ports

Each port has one in-memory fake (`fakes.py`) and one contract suite run against the fake and
the real adapter (Principle VI). Types are in [../data-model.md](../data-model.md).

## `SyncRunRepository` (`sync_runs/ports.py`, moved from `CatalogRepository`)

| Method | Contract |
|---|---|
| `start_run(run)` | Insert the open run and commit it |
| `finish_run(run)` | Update the run to its closed state |
| `get_run(run_id, result: type[R]) -> SyncRun[R] \| None` | Read it back, validating `result` as `R` |

Adapter: `PostgresSyncRunRepository`. `CatalogRepository` keeps only its catalog methods.

## `ImageProvider` (`image_cache/ports.py`)

Never raises for one asset; every outcome is a value. Adapter: `TcgdexImageProvider` on the
shared `TcgdexHttp` (retries, ≤ 8 in flight, user agent). Thread-safe.

| Method | Contract |
|---|---|
| `fetch_card_images(base_url) -> CardImages \| Missing \| ImageFailure` | Requests `{base_url}/low.webp` and `{base_url}/high.webp`. `Missing` when either answers 404. `ImageFailure` (kind `card`) on any other error, or when a body is not WebP or is over 5 MB |
| `english_image_url(card_id) -> str \| None \| ImageFailure` | `GET /v2/en/cards/{card_id}`. The `image` base, or None when the card is not found (404) or has no image |
| `fetch_artwork(set_id, kind, url) -> bytes \| Missing \| ImageFailure` | Requests `{url}.webp`; for a `symbol` under `/univ/` that answers 404, retries once under `/pt/` (research R1) |

## `ImageStore` (`image_cache/ports.py`)

Adapter: `FileImageStore(image_dir)`. Thread-safe; every write is atomic.

| Method | Contract |
|---|---|
| `check_writable()` | Create the directory if needed; raise `ImageStoreUnavailableError` when it cannot be written |
| `has_card(card_id) -> bool` | Both sizes are stored |
| `put_card(card_id, images)` | Store both sizes, replacing older ones |
| `put_artwork(set_id, kind, content)` | Store one logo or symbol |
| `card_path(card_id, size) -> Path \| None` / `artwork_path(set_id, kind) -> Path \| None` | The file to serve, or None when absent or the id is `.`/`..`. Only the real adapter needs this; the routes use it directly |

## `ImageCacheRepository` (`image_cache/ports.py`)

Adapter: `PostgresImageCacheRepository`.

| Method | Contract |
|---|---|
| `set_exists(set_id) -> bool` | The set is in the catalog |
| `track(owner_id, set_id, at) -> bool` | Insert the tracking row; `True` only when it was not there |
| `untrack(owner_id, set_id)` | Delete the row if present |
| `progress(owner_id, set_id) -> SetTracking` | All fields except `downloading` (always `False` here) |
| `tracked_set_ids() -> list[str]` | Sets tracked by any owner, in catalog order (FR-005) |
| `cards_to_resolve(set_id) -> list[CardToResolve]` | Each card's pt image URL and stored row; `files_present` is filled in by the service from `ImageStore.has_card` |
| `save_card_images(rows: Sequence[tuple[card_id, Language \| None]], fetched_at)` | Upsert in one transaction |
| `artwork_to_fetch() -> list[ArtworkToFetch]` | Every stored set × kind with its catalog URL and whether a row exists |
| `save_artwork(set_id, kind, fetched_at)` | Upsert one row |

## Not ports

- `DownloadRegistry`: an in-process, thread-safe set of set ids with running downloads. Plain
  class, no I/O.
- `Clock`: reused from `clock/`.
