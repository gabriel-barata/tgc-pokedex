# Contract: HTTP API

PTCG-018 (mark owned, tile states) and PTCG-019 (completion bar) consume these routes. The
schemas reach the frontend through `pnpm generate:api` (`openapi.json`,
`src/api-schema.gen.ts`). Every route acts as the owner from the `get_owner_id` dependency
and never reads or changes another owner's rows (FR-014). Shapes: [data-model.md](../data-model.md).

## Writes: `routes/cards.py`

`{variant}` is one of `normal`, `reverse`, `holo`, `first_edition`, `w_promo`.

| Route | Effect | Success |
|---|---|---|
| `POST /api/cards/{card_id}/ownership/{variant}/increment` | quantity + 1 | `200 CardOwnership` |
| `POST /api/cards/{card_id}/ownership/{variant}/decrement` | quantity − 1, staying at 0 when already 0 (FR-004) | `200 CardOwnership` |
| `PUT /api/cards/{card_id}/ownership/{variant}` with `{"quantity": n}` | quantity = n | `200 CardOwnership` |

Rejections change nothing (FR-005):

| Status | When |
|---|---|
| `404` | `card_id` is not in the catalog |
| `422` | `variant` is not a known variant, or the card does not list it, or `quantity` is outside 0–999 or not an integer |
| `409` | increment on a variant already at 999 |

Concurrent writes to the same card and variant all apply (FR-007).

### `CardOwnership`

```json
{
  "card_id": "sv01-001",
  "variants": [
    { "variant": "normal", "quantity": 2 },
    { "variant": "reverse", "quantity": 0 }
  ],
  "owned": true,
  "wanted_version_missing": true
}
```

`variants` lists every variant the card has, in canonical order, with 0 where nothing is
stored. The response carries no set completion (FR-006); read it from the set.

## Reads: `routes/sets.py`

### `GET /api/sets/{set_id}/ownership`

`200 SetOwnership`, or `404` when the set is not in the catalog (FR-008).

```json
{
  "set_id": "sv01",
  "completion": { "owned": 43, "so_normal": 7, "total": 198, "complete": false },
  "cards": [
    {
      "card_id": "sv01-001",
      "variants": [
        { "variant": "normal", "quantity": 2 },
        { "variant": "reverse", "quantity": 0 }
      ],
      "owned": true,
      "wanted_version_missing": true
    }
  ]
}
```

`cards` holds every card of the set by card id, including those beyond the printed count.
Only `completion` applies the placeholder cap (FR-013).

### `GET /api/sets` (changed)

Every `SetEntry` gains `completion`, equal to the `completion` of that set's ownership read
(FR-011), for tracked and untracked sets alike.

```json
{ "id": "sv01", "…": "…", "completion": { "owned": 0, "so_normal": 0, "total": 198, "complete": false } }
```

### `SetCompletion`

| Field | Meaning |
|---|---|
| `owned` | Owned cards (any variant), capped at `total` |
| `so_normal` | Owned cards with the wanted version missing, capped at `owned` |
| `total` | The set's displayed card count (`SetEntry.card_count`) |
| `complete` | `total > 0` and `owned == total` |
