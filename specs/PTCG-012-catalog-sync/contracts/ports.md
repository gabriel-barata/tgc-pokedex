# Contract: catalog-sync ports

These are the ports in `catalog_sync/ports.py` (Protocols). Each has one shared in-memory fake
in `catalog_sync/fakes.py`, and one contract suite that runs against the fake and the real
adapter (Principle III, Principle VI). Types are defined in [data-model.md](../data-model.md).

## `CatalogProvider`

Real adapter: `TcgdexProvider` (`adapters/tcgdex.py`), tested over recorded fixtures through
`httpx2.MockTransport`. Fake: `InMemoryCatalogProvider`, seeded with domain objects and
scripted failures.

| Method | Returns | Raises |
|---|---|---|
| `list_series_ids() -> list[str]` | Every series id the provider lists, Pocket included, in provider order | `ProviderUnavailable(reason)` |
| `list_set_ids(series_id) -> list[str]` | The set ids in that series' detail, in provider order | `ProviderUnavailable(reason)` |
| `fetch_set(set_id) -> SetListing \| Failure` | The validated set with its series ref and card ids, or a `set` failure | none |
| `fetch_cards(set_id, card_ids) -> list[Card \| Failure]` | One outcome per requested id, in request order. Every `Card.set_id == set_id` | none |

Contract (both implementations):

1. The provider does not filter Pocket ids. Filtering is the caller's job (`is_pocket_series`).
2. An index failure raises `ProviderUnavailable`. It never returns a partial list.
3. A set or card failure is returned as `Failure(kind, provider_id, reason)`. It is never
   raised.
4. `fetch_cards` returns exactly `len(card_ids)` outcomes, aligned with `card_ids`.
5. A card's `set_id` is the `set_id` argument, whatever the payload says (FR-016).
6. A set with an empty card list is returned as a `SetListing` with `card_ids == ()`. Skipping
   it is the caller's job.

Real-adapter-only behavior (tested in `test_tcgdex_provider.py`): the base URL
`https://api.tcgdex.net/v2/pt`, the user agent, the 10 s timeout, at most 8 requests in
flight, the 3 attempts and backoff (R4), no retry on non-429 4xx, and payload hygiene (R5).

## `CatalogRepository`

Real adapter: `PostgresCatalogRepository` (`adapters/postgres.py`), tested against Postgres 17
through Testcontainers. Fake: `InMemoryCatalogRepository`.

| Method | Effect |
|---|---|
| `start_run(run: SyncRun) -> None` | Inserts a `running` record and commits it |
| `finish_run(run: SyncRun) -> None` | Updates that record to its closed state |
| `get_run(run_id) -> SyncRun \| None` | Reads a record back, validated by `SyncRun` |
| `load_stored(series_id, set_id, card_ids) -> StoredCatalog` | Returns the stored series, set and cards (by id) with their fetched-at |
| `save_set(batch: SetBatch, fetched_at) -> None` | Upserts the batch's series (when present), set and cards in one transaction, stamping `source` and `fetched_at` |

Contract (both implementations):

1. `save_set` is all or nothing. If any row fails, none of the batch is visible.
2. `save_set` never deletes. Rows that are not in the batch keep every column, including
   `fetched_at`.
3. Upserting an existing id replaces every attribute and `fetched_at`.
4. `load_stored` returns `None`, or omits the id, for rows that do not exist.
5. `variants` round-trip as the same `frozenset[Variant]`.
6. `get_run` returns what the last `start_run` or `finish_run` wrote, including a `result`
   equal to the one saved.
