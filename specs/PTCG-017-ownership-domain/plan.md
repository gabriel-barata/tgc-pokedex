# Implementation Plan: Ownership domain & API (variant + quantity)

**Branch**: `PTCG-017-ownership-domain` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/PTCG-017-ownership-domain/spec.md`

## Summary

The owner records copies per card and variant through three write routes under
`/api/cards/{card_id}/ownership/{variant}` (increment, decrement, set). Each write is one
atomic SQL statement on a new `ownership` table (owner, card, variant, quantity 0–999), so
concurrent clicks never lose an update, and returns the card's ownership. `GET
/api/sets/{set_id}/ownership` returns every card of a set with its quantities and its
**owned** and **wanted version missing** flags, plus the set's completion. `GET /api/sets`
gains the same completion on every set.

The rules live once, as two pure functions in `routes/sets.py`: `card_ownership` (flags) and
`set_completion` (owned/so_normal/total/complete, with the PTCG-039 placeholder cap). Both
reads and the write response go through them, so SQL only fetches rows and never restates a
rule. `docs/design.md` decisions 13 and 14 record the agreed rule.

## Technical Context

**Language/Version**: Python 3.13 (backend). The frontend changes only in the regenerated
API files and one test builder.

**Primary Dependencies**: FastAPI, SQLAlchemy 2 Core, psycopg 3, Alembic, Pydantic 2. All
present; no new dependency.

**Storage**: PostgreSQL 17. New table `ownership` in migration `0004` (expand-only).

**Testing**: pytest with Testcontainers Postgres and FastAPI `TestClient` on `create_app`;
the existing `seed`/`set_row`/`card_row` builders in `tests/helpers.py`. Pure rules get
parametrized unit tests.

**Target Platform**: Linux container on the home server, and the developer machine.

**Project Type**: web service (API routes only).

**Performance Goals**: reading a 250-card set's ownership, or the sets list with completion,
well under a second (SC-005). Each read is one or two indexed queries (research R6).

**Constraints**: owner from the single `get_owner_id` dependency (Principle V). No lost
updates under concurrent writes (FR-007). A rejected request changes nothing (FR-005).

**Scale/Scope**: one owner, ~92 sets × ~250 cards, at most a few thousand ownership rows.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / gate | How this plan complies | Status |
|---|---|---|
| I. TDD | One `test:` → `feat:` pair per major behaviour: record quantities (US1), set ownership read with flags (US2), completion on both reads (US3). The design doc and regenerated API files are docs/generated code. | ✅ |
| II. DRY | `card_ownership` and `set_completion` are the only copies of the owned, wanted-missing and completion rules; the write response, the set read and the sets list all call them. `MAX_QUANTITY` exists once in `tables.py` (check constraint, schema bound, increment guard). `card_count` stays the one total rule. Shapes reach the frontend through OpenAPI. | ✅ |
| III. Flat structure | Writes in a new `routes/cards.py`; the set read and the rules in `routes/sets.py`; the table in `tables.py`; shapes in `schemas.py`. No new layer. | ✅ |
| IV. Own the data | No provider call. Ownership is user data, not provider data, so it carries no source/fetched-at. | ✅ |
| V. Owner-scoped | `ownership.owner_id` is in the primary key. Every query filters on the `Owner` dependency. A test seeds a second owner's rows directly and proves no read returns or counts them and no write changes them (FR-014). | ✅ |
| VI. Test strategy | Unit tests for the two rules (rules table, SC-002). Route tests on real Postgres for the main write/read paths and the rejections that matter. One concurrency test (SC-004). P1 end to end in process through the API (Complexity Tracking). | ✅ (reading logged) |
| VII. YAGNI | No history of changes, no bulk write, no per-variant default, no variant check constraint, no caching. | ✅ |
| Security | Path values validated by FastAPI (`Variant` enum); body by `QuantityUpdate` (0–999). Nothing secret. | ✅ |
| Accessibility | No UI. | N/A |
| Observability | No sync job. | N/A |
| Gate 3: lint/types | Strict pyright, ruff. No suppressions planned. | ✅ |
| Gate 4: new deps | None. | ✅ |

**Post-design re-check (after Phase 1)**: no new violations. Keeping the rules in Python
rather than SQL costs one extra row fetch for the sets list (R6) and keeps one source of
truth. The e2e reading is unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/PTCG-017-ownership-domain/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0: R1–R8
├── data-model.md        # Phase 1: table, derived shapes, rules
├── quickstart.md        # Phase 1: validation guide
├── contracts/
│   └── api.md           # ownership writes, set ownership read, sets list completion
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── migrations/versions/
│   └── 0004_create_ownership.py           # ownership table, expand-only
├── src/tcg_pokedex/
│   ├── app.py                             # + cards router
│   ├── tables.py                          # + ownership, MAX_QUANTITY
│   ├── schemas.py                         # + VariantQuantity, CardOwnership, SetCompletion,
│   │                                      #   SetOwnership, QuantityUpdate; SetEntry.completion
│   └── routes/
│       ├── cards.py                       # new: increment, decrement, set
│       └── sets.py                        # + card_ownership, set_completion (pure),
│                                          #   GET /{set_id}/ownership, completion in list
└── tests/routes/
    ├── test_cards.py                      # new: US1, concurrency, second owner
    └── test_sets.py                       # + rules unit tests, US2, US3

frontend/openapi.json, frontend/src/api-schema.gen.ts   # regenerated
frontend/src/sets/sets-page.test.tsx       # set builder gains `completion`
docs/design.md                             # decisions 13, 14, open items, revision history
```

**Structure Decision**: the writes act on a card, so they go in a new `routes/cards.py`. The
set read is a sets route, and the rules sit with it in `routes/sets.py`, which is the module
that uses them most (set read and sets list). `cards.py` imports `card_ownership`, `Owner` and
`DB` from `sets.py`; the import goes one way, so nothing moves (R1).

## Request flow (reference for tasks)

Write (`routes/cards.py`), one transaction:

1. Load the card's `variants` for `card_id`; none → `404`.
2. `variant` not in the card's variants → `422`.
3. Run the one statement for the operation (R3). Increment returning no row → `409`.
4. Read the card's stored quantities for the owner and return
   `card_ownership(card_id, variants, quantities)`.

Set read (`GET /api/sets/{set_id}/ownership`): load the set (`404` if none), then every card
of the set left-joined to the owner's ownership rows, grouped per card in Python →
`card_ownership` per card → counts → `set_completion(card_count(official, total), owned,
so_normal)`.

Sets list: one more query, the owner's rows with `quantity > 0` joined to their cards'
`set_id` and `variants`, grouped per card → `card_ownership` → per-set counts →
`set_completion` for every set (0/0 for sets without rows).

## Complexity Tracking

| Deviation / reading | Why needed | Simpler alternative rejected because |
|---|---|---|
| Principle VI end to end "through the real UI" for the P1 stories: met in process with `TestClient` on `create_app` and real Postgres | The feature has no screen (sticker and quantity controls are PTCG-018, the bar PTCG-019). Its user surface is the API. Same reading as PTCG-013. | Playwright would have no page to drive. PTCG-018 adds the UI e2e. |
