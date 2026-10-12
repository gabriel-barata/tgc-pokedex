# Contract: HTTP API

PTCG-015 (sets page) and PTCG-016 (card grid) consume these routes. The schemas reach the
frontend through `pnpm generate:api` (`openapi.json`, `src/api-schema.gen.ts`).

## Tracking

The API acts as the household owner (`HOUSEHOLD_OWNER_ID`), chosen through a single FastAPI
dependency (FR-001).

### `GET /api/sets/{set_id}/tracking`

`200` with `SetTracking`, or `404` when the set is not in the catalog.

### `PUT /api/sets/{set_id}/tracking`

Tracks the set (FR-002, FR-004). Idempotent.

- The set was untracked → record it, then, unless a download for it is already running,
  start a background `images` run scoped to the set. The response does not wait for it, and
  reports `downloading: true`.
- The set was already tracked → nothing changes, and no download starts (US1-5).
- `200` with `SetTracking`, or `404` for an unknown set.

### `DELETE /api/sets/{set_id}/tracking`

Untracks the set. Idempotent. Deletes no image (FR-015) and does not stop a running
download. `200` with `SetTracking`, or `404` for an unknown set.

### `SetTracking`

```json
{
  "set_id": "sv01",
  "tracked": true,
  "total_cards": 258,
  "cached": 120,
  "unavailable": 0,
  "downloading": true
}
```

| Field | Meaning |
|---|---|
| `tracked` | The owner tracks the set |
| `total_cards` | Cards of the set in the catalog |
| `cached` | Cards with a cached image (pt or English) |
| `unavailable` | Cards with no image in pt or English, as of their last check |
| `downloading` | A track-triggered download for this set is running in this app process |

`total_cards - cached - unavailable` cards are pending.

## Images

No database read and no provider call (FR-014, Principle IV). Responses carry
`Content-Type: image/webp`, `Cache-Control: public, max-age=604800`, `ETag` and
`Last-Modified`. A conditional request with a matching `ETag` gets `304`.

| Route | Path values | `404` when |
|---|---|---|
| `GET /api/images/cards/{card_id}/{size}` | `size`: `small` \| `large` | No cached file (pending, unavailable, unknown card), or `card_id` is `.` or `..` |
| `GET /api/images/sets/{set_id}/{kind}` | `kind`: `logo` \| `symbol` | No cached file |

Any other `size` or `kind` is `422` (FastAPI enum validation). Images stay servable after
the set is untracked (FR-015).
