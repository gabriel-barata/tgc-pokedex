---

description: "Task list for PTCG-017 Ownership domain & API (variant + quantity)"
---

# Tasks: Ownership domain & API (variant + quantity)

**Input**: Design documents from `/specs/PTCG-017-ownership-domain/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Mandatory (constitution, Principles I and VI), for the main behaviours only. Every test task is listed before the implementation task it covers, and its test must fail before that task starts.

**Organization**: Tasks are grouped by user story. Each phase's test tasks land as one `test:` commit and its implementation tasks as the following `feat:` commit (four pairs in all, then one `docs:` commit).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are from the repo root. Backend code is under `backend/src/tcg_pokedex/`, its tests under `backend/tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm a green baseline on the ticket branch. No new dependency or project structure.

- [X] T001 From `backend/` with Docker running, run `uv sync`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright --warnings`; all must pass on `PTCG-017-ownership-domain` before any change

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `ownership` table, the card-level shapes and the single `card_ownership` rule that the writes (US1) and the set read (US2) both return.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

Commit pair: `test: card ownership rules` → `feat: ownership table and card ownership rules`.

### Tests (write first) ⚠️

- [X] T002 [P] Add a seeding helper `own(engine, card_id, variant, quantity, owner_id=HOUSEHOLD_OWNER_ID)` to `backend/tests/helpers.py` that inserts one row into `ownership` (imported from `tcg_pokedex.tables`), for the route tests of US1–US3
- [X] T003 [P] Add a parametrized unit test of `card_ownership(card_id, listed, stored)` (imported from `tcg_pokedex.routes.sets`) to `backend/tests/routes/test_sets.py`, one case per row of the data-model rules table: Normal+Reverse/nothing → not owned, not wanted-missing; Normal/Normal 1 → owned, not missing; Normal+Reverse/Normal 2 → owned, **missing**; Normal+Reverse/Reverse 1 (with and without Normal) → owned, not missing; Holo/Holo 1 → owned, not missing; Normal/Normal 1 + Reverse 3 (dropped variant) → owned, not missing. Also assert `variants` lists every listed variant in canonical order with quantity 0 where nothing is stored, and never the dropped variant

### Implementation

- [X] T004 [P] In `backend/src/tcg_pokedex/tables.py` add `MAX_QUANTITY = 999` and the `ownership` table: `owner_id` `Uuid` FK `owners.id`, `card_id` `Text` FK `cards.id`, `variant` `Text`, primary key `(owner_id, card_id, variant)` in that order, `quantity` `Integer` `nullable=False` with `CheckConstraint` "`quantity BETWEEN 0 AND MAX_QUANTITY`" built from the constant (name `quantity_in_range`). No `variant` check constraint, no timestamps (research R5)
- [X] T005 Draft `backend/migrations/versions/0004_create_ownership.py` with `uv run alembic revision --autogenerate -m "create ownership"` (dev database at head, `make migrate`), then review it by hand to match `0003`'s style: revision `"0004"`, down_revision `"0003"`, expand-only `create_table`, `downgrade` drops the table. `tests/test_migrations.py` (migrations match tables, downgrade to base) must pass (depends on T004)
- [X] T006 [P] In `backend/src/tcg_pokedex/schemas.py` add `VariantQuantity` (`variant: Variant` from `tcg_pokedex.tcgdex`, `quantity: int = Field(ge=0, le=MAX_QUANTITY)`) and `CardOwnership` (`card_id: str`, `variants: list[VariantQuantity]`, `owned: bool`, `wanted_version_missing: bool`), both `ConfigDict(frozen=True, extra="forbid")` with a one-line docstring
- [X] T007 In `backend/src/tcg_pokedex/routes/sets.py` add the pure function `card_ownership(card_id: str, listed: Sequence[Variant], stored: Mapping[Variant, int]) -> CardOwnership`: drop stored rows for unlisted variants; **owned** = some listed variant has quantity > 0 (FR-009); **wanted version missing** = Normal > 0, every other listed variant is 0, and the card lists at least one non-Normal variant (FR-010). This is the only copy of both rules (depends on T006)

**Checkpoint**: `uv run pytest tests/routes/test_sets.py tests/test_migrations.py` passes; user stories can start

---

## Phase 3: User Story 1 - Record copies per variant (Priority: P1) 🎯 MVP

**Goal**: The owner increments, decrements and sets a card's quantity per variant through the API; each change returns the card's `CardOwnership`.

**Independent Test**: Through the API, increment, decrement and set quantities of a card's variants; invalid requests are rejected and leave stored quantities unchanged; ten concurrent increments end at 10.

Commit pair: `test: record ownership quantities per variant` → `feat: record ownership quantities per variant`.

### Tests for User Story 1 (write first) ⚠️

- [X] T008 [US1] Create `backend/tests/routes/test_cards.py` with an `app`/`client` fixture like `test_sets.py` (`create_app` on the migrated database, `seed` with set `sv01` and cards `sv01-001` (`["normal", "reverse"]`) and a Normal-only card, no tracked sets, and a second owner inserted into `owners` with `own(..., "sv01-001", "normal", 5, owner_id=OTHER_OWNER_ID)`). Route tests, each asserting the response body and the stored rows:
  - `POST /api/cards/sv01-001/ownership/reverse/increment` → `200`, `variants` `[normal 0, reverse 1]`, `owned` true, `wanted_version_missing` false (scenario 1; the set is untracked, scenario 8)
  - decrement from 2 → 1, and decrement at 0 → `200` and stays 0 (scenarios 2, 3; FR-004)
  - `PUT …/ownership/normal` with `{"quantity": 0}` and `{"quantity": 999}` sets exactly that value (scenario 4)
  - rejections change nothing (scenarios 5–7, FR-005): `PUT` with `-1` or `1000` → `422`; increment at 999 → `409`; `holo` on a card without Holo → `422`; an unknown variant in the path → `422`; unknown card `nope` → `404`
  - deleting the set's tracking (`DELETE /api/sets/sv01/tracking`, after inserting a `tracked_sets` row) leaves the quantities unchanged (scenario 9, FR-002)
  - the second owner's row stays at 5 after every write and never appears in a response (FR-014, SC-003)
- [X] T009 [US1] In `backend/tests/routes/test_cards.py` add the concurrency test: ten `POST …/sv01-001/ownership/normal/increment` calls run in parallel threads (`concurrent.futures.ThreadPoolExecutor`, one `TestClient` request each) leave the Normal quantity at exactly 10 (FR-007, SC-004)

### Implementation for User Story 1

- [X] T010 [US1] In `backend/src/tcg_pokedex/schemas.py` add the request model `QuantityUpdate` with `quantity: int = Field(ge=0, le=MAX_QUANTITY)` ("`0 ≤ quantity ≤ MAX_QUANTITY`"), `ConfigDict(frozen=True, extra="forbid")`
- [X] T011 [US1] Create `backend/src/tcg_pokedex/routes/cards.py` (module docstring, `router = APIRouter(prefix="/api/cards")`, `Owner`, `DB` and `card_ownership` imported from `tcg_pokedex.routes.sets`) with `POST /{card_id}/ownership/{variant}/increment`, `POST /{card_id}/ownership/{variant}/decrement` and `PUT /{card_id}/ownership/{variant}` (body `QuantityUpdate`), `variant: Variant`, each returning `CardOwnership`. One `engine.begin()` transaction per request, following plan "Request flow": (1) load the card's `variants`, none → `404 "Unknown card"`; (2) `variant` not listed → `422`; (3) one statement (research R3): increment = `postgresql.insert(ownership)` `.values(quantity=1)` `ON CONFLICT (owner_id, card_id, variant) DO UPDATE SET quantity = ownership.quantity + 1 WHERE ownership.quantity < MAX_QUANTITY RETURNING quantity`, no row → `409`; decrement = `UPDATE … SET quantity = quantity - 1 WHERE owner/card/variant AND quantity > 0` (no row is success); set = upsert with `quantity = excluded.quantity`; (4) read the owner's stored quantities for the card and return `card_ownership(...)`. Document `404`/`409` in `responses=` like `UNKNOWN_SET`
- [X] T012 [US1] Register `cards.router` in `backend/src/tcg_pokedex/app.py` (depends on T011)
- [X] T013 [US1] From `frontend/`, run `pnpm generate:api` and include `frontend/openapi.json` and `frontend/src/api-schema.gen.ts` in the `feat:` commit (FR-015)

**Checkpoint**: `uv run pytest tests/routes/test_cards.py` passes; quantities can be recorded through the API

---

## Phase 4: User Story 2 - Read a set's ownership (Priority: P1)

**Goal**: `GET /api/sets/{set_id}/ownership` returns every card of the set with its quantity per variant and its two flags.

**Independent Test**: Seed quantities on a few cards of a set with `own`, read the set's ownership, and check every card's quantities and flags.

Commit pair: `test: read a set's ownership` → `feat: read a set's ownership`.

### Tests for User Story 2 (write first) ⚠️

- [X] T014 [US2] In `backend/tests/routes/test_sets.py` add route tests for `GET /api/sets/{set_id}/ownership`, seeding with `own`: cards covering the rules (nothing owned; Normal-only card owned; Normal+Reverse owned only in Normal; Normal+Reverse owned in Reverse; Holo-only owned), a card numbered beyond the printed count, a card of another set, and a second owner's rows on the same cards. Assert: `set_id`; `cards` holds every card of the set and only those, by card id, each with every listed variant (0 where none stored) and the expected `owned`/`wanted_version_missing` (scenarios 1–6, FR-008); the second owner's quantities never show (FR-014); an unknown set → `404` (scenario 7); after a write through `POST /api/cards/…/increment`, a fresh `create_app` on the same database reads the new quantity (SC-001)

### Implementation for User Story 2

- [X] T015 [P] [US2] In `backend/src/tcg_pokedex/schemas.py` add `SetOwnership` (`set_id: str`, `cards: list[CardOwnership]`), frozen, `extra="forbid"` (`completion` is added in US3)
- [X] T016 [US2] In `backend/src/tcg_pokedex/routes/sets.py` add `GET /{set_id}/ownership` (`responses=UNKNOWN_SET`) returning `SetOwnership`: `_require_set`, then one query of the set's cards (`id`, `variants`) left-outer-joined to `ownership` on `card_id` and `owner_id == owner_id`, ordered by card id; group rows per card in Python and build each with `card_ownership` (depends on T015)
- [X] T017 [US2] From `frontend/`, run `pnpm generate:api` and include the regenerated `frontend/openapi.json` and `frontend/src/api-schema.gen.ts` in the `feat:` commit

**Checkpoint**: US1 and US2 tests pass; the album grid (PTCG-018) has its data source

---

## Phase 5: User Story 3 - See how complete a set is (Priority: P2)

**Goal**: `completion` (`owned`, `so_normal`, `total`, `complete`) on the set ownership read and on every set of `GET /api/sets`, from one `set_completion` rule.

**Independent Test**: Seed ownership in a set, read the set's ownership and the sets list, and check `owned`, `so_normal`, `total` and `complete` on both.

Commit pair: `test: set completion` → `feat: set completion on the set read and the sets list`.

### Tests for User Story 3 (write first) ⚠️

- [X] T018 [US3] In `backend/tests/routes/test_sets.py` add a parametrized unit test of `set_completion(total, owned, so_normal)` with the five rows of the data-model completion table: (0,0,0) → 0/0, not complete; (198,0,0) → 0/0, not complete; (198,198,7) → 198/7, **complete**; (198,205,9) → 198/9, complete; (3,5,5) → 3/3, complete
- [X] T019 [US3] In `backend/tests/routes/test_sets.py` add route tests: for a set with owned cards (some "só normal") and a set with none, `completion` on `GET /api/sets/{set_id}/ownership` matches the expected values and equals that set's `completion` in `GET /api/sets` (scenarios 1, 2, 5); a set whose every counted card is owned, some only in Normal, is `complete` with `so_normal` > 0 (scenario 3); owned cards beyond the printed count leave `owned` ≤ `total` (scenario 4); an untracked set carries completion too; a second owner's rows are not counted (FR-014). Update the expected payload of `test_sets_are_listed_by_series_newest_first_with_the_owners_tracking` with each set's `completion`

### Implementation for User Story 3

- [X] T020 [P] [US3] In `backend/src/tcg_pokedex/schemas.py` add `SetCompletion` (`owned`, `so_normal`, `total`: `int = Field(ge=0)`, `complete: bool`), frozen, `extra="forbid"`; add the required field `completion: SetCompletion` to `SetEntry` and to `SetOwnership`
- [X] T021 [US3] In `backend/src/tcg_pokedex/routes/sets.py` add the pure function `set_completion(total: int, owned: int, so_normal: int) -> SetCompletion`: cap `owned` at `total` and `so_normal` at the capped `owned`, `complete = total > 0 and owned == total` (FR-011–FR-013). Its docstring marks the cap as the placeholder until PTCG-039; it is the only place the cap lives (depends on T020)
- [X] T022 [US3] In `backend/src/tcg_pokedex/routes/sets.py` give the set ownership read its `completion`: load the set's `official_count`/`total_count`, count owned and wanted-missing cards from the `card_ownership` results, and call `set_completion(card_count(official_count, total_count), owned, so_normal)` (depends on T021)
- [X] T023 [US3] In `backend/src/tcg_pokedex/routes/sets.py` add `completion` to every `SetEntry` in `list_sets`: one extra query for the owner's `ownership` rows with `quantity > 0` joined to their card's `set_id` and `variants`, grouped per card → `card_ownership` → per-set owned/so_normal counts → `set_completion(card_count(...), …)` for every set, 0/0 for sets without rows (research R6; depends on T021)
- [X] T024 [US3] From `frontend/`, run `pnpm generate:api`, add `completion: { owned: 0, so_normal: 0, total: 182, complete: false }` to the `makeSet` builder in `frontend/src/sets/sets-page.test.tsx` (keep `total` equal to `card_count` where overridden), then `pnpm typecheck && pnpm test`; include all three files in the `feat:` commit

**Checkpoint**: all three stories pass independently; PTCG-019 has its completion data

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Design record and the full quality gates.

- [X] T025 [P] Update `docs/design.md` (commit `docs: record the ownership and completion rule`): decision 13 ("Card tile states") and decision 14 ("Completion") state that owning any version counts as owned, "só normal" is information only, and a set is complete when every card is owned (the bar has no track left); resolve the matching entries under "Open items for feature cards"; add a 2026-10-12 (PTCG-017) entry to "Revision history" (FR-016)
- [X] T026 Run the gates from `quickstart.md` "Automated": in `backend/`, `uv run pytest --cov` (80% branch floor), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --warnings`; in `frontend/`, `pnpm generate:api && git diff --exit-code openapi.json src/api-schema.gen.ts`, `pnpm lint`, `pnpm format:check`, `pnpm typecheck`, `pnpm test`; from the repo root, `bash .github/scripts/check-tdd-order.sh origin/main HEAD` and `bash .github/scripts/check-skipped-tests.sh`
- [X] T027 Run `quickstart.md` "Manual" against the dev stack: the curl sequence on `sv01-001`, a backend restart showing unchanged quantities (SC-001), and `curl -w '%{time_total}\n'` on the set ownership read and the sets list, both well under a second (SC-005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none
- **Foundational (Phase 2)**: after Setup; blocks every story (table, `CardOwnership`, `card_ownership`)
- **US1 (Phase 3)** and **US2 (Phase 4)**: after Foundational; independent of each other (US2 seeds rows with `own`, it does not need the write routes, except its SC-001 restart check, which uses one increment)
- **US3 (Phase 5)**: after US2 (it adds `completion` to `SetOwnership` and reuses the set read's query)
- **Polish (Phase 6)**: T025 any time; T026–T027 after every story

### Within Each Phase

- Test tasks first, committed as `test:`, and failing; then the implementation tasks, committed as `feat:`
- Schemas → pure rules → routes → app registration → `pnpm generate:api`

### Parallel Opportunities

- Phase 2: T002 ∥ T003 (different test files); T004 ∥ T006 (tables vs schemas)
- Phase 3: T008–T009 share `test_cards.py`, and T011 imports `QuantityUpdate` from T010, so the phase is sequential
- Phase 4 can run alongside Phase 3 once Phase 2 is done (different route modules), except both regenerate the API files: run `pnpm generate:api` once both are in
- T025 ∥ any phase (docs only)

---

## Parallel Example: Foundational phase

```bash
# Tests together:
Task: "Add own() seeding helper in backend/tests/helpers.py"
Task: "Parametrized card_ownership unit test in backend/tests/routes/test_sets.py"

# Then table and schemas together:
Task: "ownership table and MAX_QUANTITY in backend/src/tcg_pokedex/tables.py"
Task: "VariantQuantity and CardOwnership in backend/src/tcg_pokedex/schemas.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 → Phase 2 (table, shapes, `card_ownership`)
2. Phase 3: the write routes
3. **STOP and VALIDATE**: `uv run pytest tests/routes/test_cards.py`, then the first curl lines of the quickstart

### Incremental Delivery

1. Foundational → US1 (record) → US2 (read a set) → US3 (completion) → docs
2. Each `test:`/`feat:` pair leaves the suite green; the PR carries four pairs and one `docs:` commit

---

## Notes

- [P] tasks = different files, no dependencies
- Keep tests to the main behaviours listed; data edge cases beyond them are PTCG-039
- Commit each TDD cycle as a `test:` commit with the failing test, then a `feat:` commit (constitution, Principle I); `check-tdd-order.sh` counts `backend/migrations/*` as source, so the migration lands in the Foundational `feat:` commit after its `test:` commit
- No code comments; docstrings are fine
