# Research: Ownership domain & API

No open clarifications came from the Technical Context. These are the design decisions.

## R1. Where the rules and routes live

- **Decision**: the rules `card_ownership` and `set_completion` are pure functions in
  `routes/sets.py`, next to `card_count` and the two reads that use them. The writes go in a
  new `routes/cards.py`, which imports `card_ownership`, `Owner` and `DB` from `sets.py`.
- **Rationale**: Principle III wants pure rules in the module that uses them; `sets.py` uses
  them twice (set read, sets list) and `cards.py` once (write response). The import runs one
  way, so `Owner`, `DB` and `card_count` stay where they are.
- **Alternatives considered**: a `routes/ownership.py` holding everything: `sets.py` would
  import its completion helper while it imports `card_count`, `Owner` and `DB` from
  `sets.py`, a cycle that forces moving those first. A top-level `ownership.py` rules module:
  a new kind of module the constitution does not list.

## R2. API shape

- **Decision**: `POST /api/cards/{card_id}/ownership/{variant}/increment`,
  `POST …/{variant}/decrement` and `PUT /api/cards/{card_id}/ownership/{variant}` with
  `{"quantity": n}`. Quantities are returned as a list of `{variant, quantity}` in canonical
  variant order (Normal → Reverse → Holo → First Edition → W Promo).
- **Rationale**: one route per operation in FR-003 keeps each request self-describing and
  each SQL statement simple. A list keeps the order the variant dots (design decision 13)
  draw in, and generates a plain array type for the frontend.
- **Alternatives considered**: one `PATCH` with `{variant, delta | quantity}`: two optional
  fields to validate against each other. A `{variant: quantity}` map: object key order is not
  part of the JSON contract, and the generated type is a loose record.

## R3. No lost updates (FR-007, SC-004)

- **Decision**: each write is one statement, so Postgres row locking orders concurrent ones:
  - increment: `INSERT … VALUES (…, 1) ON CONFLICT (owner_id, card_id, variant) DO UPDATE
    SET quantity = ownership.quantity + 1 WHERE ownership.quantity < MAX_QUANTITY RETURNING
    quantity`. No row returned → already at the maximum → `409`.
  - decrement: `UPDATE … SET quantity = quantity - 1 WHERE … AND quantity > 0`. No row
    matched means it was already 0, which succeeds (FR-004).
  - set: `INSERT … ON CONFLICT DO UPDATE SET quantity = excluded.quantity`.
- **Rationale**: no read-modify-write in Python, no explicit locks, default READ COMMITTED.
- **Alternatives considered**: `SELECT … FOR UPDATE` then write: two round trips and a lock
  to manage for the same result. Serializable isolation with retries: more code.

## R4. Error statuses

- **Decision**: unknown card → `404`. `variant` not a known variant → `422` (FastAPI path
  validation). Variant the card does not list → `422`. `quantity` outside 0–999 → `422`
  (`QuantityUpdate`). Increment at 999 → `409`.
- **Rationale**: `422` for a request that can never succeed for this card; `409` for a valid
  request blocked by the current state. Every check runs before any write, and the
  increment guard sits in the statement itself, so a rejection changes nothing (FR-005).
- **Alternatives considered**: `422` for the increment at 999 too: it would hide that the same
  request succeeds after a decrement.

## R5. Storage

- **Decision**: one row per (owner, card, variant) with `quantity` 0–999, primary key in that
  order, foreign keys to `owners` and `cards`, and a check constraint on the range built from
  `MAX_QUANTITY`. Rows are not deleted at 0. No `variant` check constraint and no timestamps.
- **Rationale**: the primary key prefix (owner, card) serves both reads. A missing row and a
  0 row mean the same thing, so keeping zeros avoids a delete branch. `variant` is validated
  against the card's listed variants before any write, which a check constraint could not do.
  The catalog sync never deletes cards, so the card foreign key is safe; a variant the sync
  drops leaves its row in place, ignored by reads (spec edge case, PTCG-039).
- **Alternatives considered**: a `jsonb` of quantities per card: the atomic increment becomes
  a `jsonb_set` expression and the range check moves to code. Deleting rows at 0: an extra
  branch for no reader.

## R6. Computing the rules in Python, and speed (SC-005)

- **Decision**: SQL fetches rows; `card_ownership` and `set_completion` compute everything.
  The set read is one query (the set's cards left-joined to the owner's rows). The sets list
  adds one query for the owner's rows with `quantity > 0` joined to their card's `set_id` and
  `variants`.
- **Rationale**: Principle II: a SQL `CASE`/`FILTER` version of "owned only in Normal" would
  be a second copy of the rule. Volumes are small: ~250 cards (≤ 1,250 rows) for a set, and a
  few thousand owned rows at most for the list, all through the primary key.
- **Alternatives considered**: aggregate in SQL: faster on paper, but two copies of the rules
  for no measurable gain at this size.

## R7. The variant enum

- **Decision**: reuse `Variant` as the path value and the response field, and move it from
  `tcgdex.py` to `schemas.py`, next to `ArtworkKind`.
- **Rationale**: it is already the one canonical list and storage order of variants
  (`cards.variants` is written in its order). `schemas.py` holds the enums the routes take
  as path values, and `tcgdex.py` already imports from it, so `schemas.py` importing
  `Variant` from `tcgdex.py` would be an import cycle (found while implementing).
- **Alternatives considered**: keeping it in `tcgdex.py`: the cycle above. A second enum
  in `schemas.py`: two copies of the variant list.

## R8. End-to-end coverage and frontend impact

- **Decision**: the P1 stories run end to end in process (`TestClient` on `create_app`, real
  Postgres), logged in Complexity Tracking. `pnpm generate:api` regenerates the frontend
  files; the set builder in `src/sets/sets-page.test.tsx` gains a `completion` value so the
  typecheck passes. No frontend behaviour changes.
- **Rationale**: there is no screen yet (PTCG-018, PTCG-019). `SetEntry.completion` is a new
  required field, so typed test data must carry it.
- **Alternatives considered**: making `completion` optional: the API always sends it, and an
  optional field would push a pointless null check onto PTCG-019.
