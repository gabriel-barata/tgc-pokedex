# Data Model: Ownership domain & API

## Stored: `ownership` (migration `0004`)

| Column | Type | Rules |
|---|---|---|
| `owner_id` | `uuid`, FK `owners.id` | Primary key part 1. Always the API's owner (Principle V). |
| `card_id` | `text`, FK `cards.id` | Primary key part 2. Any catalog card, tracked set or not (FR-002). |
| `variant` | `text` | Primary key part 3. A `Variant` value the card lists when written (FR-001, FR-005). |
| `quantity` | `integer`, not null | `CHECK (quantity BETWEEN 0 AND MAX_QUANTITY)`, `MAX_QUANTITY = 999`. |

- A missing row means quantity 0. Rows stay at 0; nothing deletes them.
- Tracking and untracking a set (`tracked_sets`) never touch this table (FR-002).
- A row whose `variant` the card no longer lists is kept and ignored by every read
  (spec edge case; PTCG-039).

Existing tables read: `cards` (`id`, `set_id`, `variants` in canonical order), `sets`
(`official_count`, `total_count`), `owners`.

## Derived shapes (`schemas.py`)

| Model | Fields |
|---|---|
| `VariantQuantity` | `variant: Variant`, `quantity: int` (0–999) |
| `CardOwnership` | `card_id: str`, `variants: list[VariantQuantity]` (every listed variant, canonical order, 0 when no row), `owned: bool`, `wanted_version_missing: bool` |
| `SetCompletion` | `owned: int`, `so_normal: int`, `total: int` (all ≥ 0), `complete: bool` |
| `SetOwnership` | `set_id: str`, `completion: SetCompletion`, `cards: list[CardOwnership]` (every card of the set, by card id) |
| `SetEntry` (existing) | + `completion: SetCompletion` |
| `QuantityUpdate` (request) | `quantity: int`, `0 ≤ quantity ≤ MAX_QUANTITY` |

All models are frozen with `extra="forbid"`, like the existing ones.

## Rules (pure functions in `routes/sets.py`)

`card_ownership(card_id, listed, stored) -> CardOwnership`, where `listed` is the card's
variants and `stored` the owner's quantities by variant (rows for unlisted variants are
dropped):

- **owned** (FR-009): some listed variant has quantity > 0.
- **wanted version missing** (FR-010): Normal > 0, every other listed variant is 0, and the
  card lists at least one non-Normal variant.

| Listed | Stored | owned | wanted missing |
|---|---|---|---|
| Normal, Reverse | nothing | no | no |
| Normal | Normal 1 | yes | no |
| Normal, Reverse | Normal 2 | yes | **yes** |
| Normal, Reverse | Reverse 1 (Normal any) | yes | no |
| Holo | Holo 1 | yes | no |
| Normal | Normal 1, Reverse 3 (dropped variant) | yes | no |

`set_completion(total, owned, so_normal) -> SetCompletion` (FR-011–FR-013):

- `owned` is capped at `total`, and `so_normal` at the capped `owned`. *Placeholder until
  PTCG-039* (secret rares beyond the printed count); this is the only place it lives.
- `complete` = `total > 0 and owned == total`. "Só normal" cards still count as owned.
- `total` comes from the existing `card_count(official_count, total_count)`: the printed
  count, or every card when none is printed.

| total | owned (uncapped) | so_normal | → owned | so_normal | complete |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | no |
| 198 | 0 | 0 | 0 | 0 | no |
| 198 | 198 | 7 | 198 | 7 | **yes** |
| 198 | 205 | 9 | 198 | 9 | yes |
| 3 | 5 | 5 | 3 | 3 | yes |
