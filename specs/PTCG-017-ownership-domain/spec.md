# Feature Specification: Ownership domain & API (variant + quantity)

**Feature Branch**: `PTCG-017-ownership-domain`

**Created**: 2026-10-12

**Status**: Draft

**Input**: `temp/specs/PTCG-017-ownership-domain.md` (grill-me interview).
Trello card: https://trello.com/c/XNXIbSjD/17-ptcg-017-ownership-domain-api-variant-quantity.
Depends on PTCG-012 (catalog sync).

## Overview

The owner records how many copies of each card they own, per variant (Normal, Reverse, Holo,
…). The app then gives one authoritative answer to three questions the screens ask: is this
card owned, do we still want a Reverse/Holo of it, and how complete is this set.

The rule is deliberately generous: owning **any** version of a card counts as owning it, for the
album and for completion. Owning only the Normal of a card that also has a foil version is
reported as "wanted version missing" (the "só normal" count), but that is information only and
never blocks completion.

This feature has no UI. The mark-owned sticker and quantity controls belong to PTCG-018 and the
completion bar to PTCG-019; here the owner works through the API.

## Clarifications

### Session 2026-10-12

- Q: When the owner changes a quantity, what does the response include? → A: The card's
  quantities for all its variants plus its owned and wanted-version-missing flags, the same
  shape as one card in the set read. Set completion is not included; it is read separately.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record copies per variant (Priority: P1)

As the household owner, I add, remove or set the number of copies I own of a card in a given
variant, so that the app knows exactly what is in our binder.

**Why this priority**: Every other ownership feature (album states, completion, duplicates)
reads these quantities.

**Independent Test**: Through the API, increment, decrement and set the quantity of a card's
variants, then read them back after a restart of the app; check that invalid requests are
rejected and leave the stored quantities unchanged.

**Acceptance Scenarios**:

1. **Given** a card with Normal and Reverse variants and nothing owned, **When** the owner
   increments its Reverse, **Then** the response lists the card's quantities for all its
   variants (Normal 0, Reverse 1), owned, and not wanted-missing.
2. **Given** a card owned ×2 in Normal, **When** the owner decrements its Normal, **Then** its
   Normal quantity is 1.
3. **Given** a card with quantity 0 in a variant, **When** the owner decrements that variant,
   **Then** the request succeeds and the quantity stays 0.
4. **Given** any card, **When** the owner sets a variant's quantity to a value from 0 to 999,
   **Then** the quantity becomes exactly that value.
5. **Given** any card, **When** the owner sets a quantity below 0 or above 999, or increments a
   variant already at 999, **Then** the request is rejected and nothing changes.
6. **Given** a card without a Holo variant, **When** the owner changes its Holo quantity,
   **Then** the request is rejected and nothing changes.
7. **Given** a card id that is not in the catalog, **When** the owner changes any quantity,
   **Then** the response is not found.
8. **Given** a card in a set that is not tracked, **When** the owner changes its quantity,
   **Then** it succeeds like any other card.
9. **Given** a tracked set with owned cards, **When** the owner untracks it (and later tracks
   it again), **Then** its quantities are unchanged.

---

### User Story 2 - Read a set's ownership (Priority: P1)

As the household owner, I open a set and see, for each of its cards, how many copies I own per
variant, whether the card is owned, and whether its wanted version is still missing.

**Why this priority**: The album grid (PTCG-018) draws each tile's state from this answer.

**Independent Test**: Seed quantities on a few cards of a set, read the set's ownership through
the API, and check every card's quantities and flags.

**Acceptance Scenarios**:

1. **Given** a set, **When** the owner reads its ownership, **Then** every card in the set is
   listed with a quantity for each of its variants (0 where nothing is owned), its **owned**
   flag and its **wanted version missing** flag.
2. **Given** a card with all quantities at 0, **Then** it is not owned and not wanted-missing.
3. **Given** a card that has only a Normal variant and is owned in Normal, **Then** it is owned
   and not wanted-missing.
4. **Given** a card with Normal and Reverse variants, owned only in Normal, **Then** it is
   owned and wanted-missing.
5. **Given** a card with Normal and Reverse variants, owned in Reverse (with or without
   Normal), **Then** it is owned and not wanted-missing.
6. **Given** a card with only foil variants (e.g. only Holo), owned in one of them, **Then** it
   is owned and not wanted-missing.
7. **Given** an unknown set id, **When** the owner reads its ownership, **Then** the response
   is not found.

---

### User Story 3 - See how complete a set is (Priority: P2)

As the household owner, I see for each set how many of its cards we own, how many of those are
"só normal", and whether the set is complete, both on the sets list and on a single set.

**Why this priority**: The completion bar (PTCG-019) and the sets page's binder covers show
it, but recording and reading ownership is useful without it.

**Independent Test**: Seed ownership in a set, read the set's completion and the sets list, and
check `owned`, `so_normal`, `total` and the complete flag on both.

**Acceptance Scenarios**:

1. **Given** a set, **When** the owner reads its completion, **Then** it reports `owned` (owned
   cards), `so_normal` (owned cards with the wanted version missing), `total` and whether it is
   complete (`owned == total`).
2. **Given** the sets list, **When** the owner reads it, **Then** every set in it carries the
   same completion values as reading that set alone.
3. **Given** a set whose every counted card is owned, some of them only in Normal while a foil
   exists, **Then** the set is complete and `so_normal` reports those cards.
4. **Given** a set where the owner also owns cards beyond its printed count (e.g. secret
   rares), **Then** `owned` never exceeds `total` (placeholder rule, FR-013).
5. **Given** a set with no owned cards, **Then** `owned` and `so_normal` are 0 and it is not
   complete.

---

### Edge Cases

- **Second owner** (Principle V): another owner's quantities, set into the store directly, are
  never returned by any read, never counted in completion, and never changed by any write.
- **Concurrent clicks**: two increments on the same card and variant in quick succession both
  count; the result is the sum, not a lost update.
- **Variant dropped by a later catalog sync**: a quantity stored for a variant the card no
  longer lists is kept but ignored by reads, flags and completion until the variant returns.
  Deeper handling is parked for PTCG-039.
- **Set with no printed count** (e.g. promos): `total` is every card in the set, as on the sets
  page.
- **Empty or unsynced set**: a set with no cards has `total` 0. It is not reported as complete
  (see FR-012).

## Requirements *(mandatory)*

### Functional Requirements

#### Ownership records

- **FR-001**: Ownership MUST be a whole-number quantity, from 0 to 999, per owner, card and
  variant. A card's variants are the ones the catalog lists for it (PTCG-012 FR-009).
- **FR-002**: Any catalog card MUST be ownable, whether or not its set is tracked. Tracking or
  untracking a set MUST NOT change any quantity.
- **FR-003**: The API MUST let the owner, on one card and variant, increment by 1, decrement by
  1, and set a quantity.
- **FR-004**: Decrementing a quantity of 0 MUST succeed and leave it at 0.
- **FR-005**: A quantity below 0 or above 999 (set directly or reached by incrementing) MUST be
  rejected. A variant the card does not list MUST be rejected. An unknown card MUST return not
  found. A rejected request MUST change nothing.
- **FR-006**: Every successful change MUST return the card's resulting ownership in the same
  shape as one card in the set read (FR-008): its quantities for all its variants and its
  owned and wanted-version-missing flags. It does not return set completion.
- **FR-007**: Concurrent changes to the same card and variant MUST NOT lose updates.

#### Reading

- **FR-008**: The API MUST return, for a set, every card in it with its quantity per variant
  (0 when none is stored) and its two flags (FR-009, FR-010). An unknown set returns not found.

#### Rules (single source, Principle II)

- **FR-009**: A card is **owned** when its quantity is above 0 in at least one of its variants.
- **FR-010**: A card has its **wanted version missing** when it is owned only in Normal (Normal
  above 0, every other listed variant at 0) and it lists at least one non-Normal variant. This
  is information only: it MUST NOT affect whether a card is owned or a set is complete.
- **FR-011**: A set's **completion** MUST report `owned` (owned cards), `so_normal` (owned cards
  with the wanted version missing) and `total`, for a single set and for every set in the sets
  list.
- **FR-012**: A set MUST be reported **complete** when `total` is above 0 and `owned` equals
  `total`.
- **FR-013**: *Placeholder until PTCG-039:* `total` MUST be the set's displayed card count (its
  printed count, or every card when none is printed, the same number the sets page shows), and
  `owned` MUST be capped at `total` (and `so_normal` at `owned`). This rule MUST live in one
  place so PTCG-039 can replace it.

#### Owner scoping (Principle V)

- **FR-014**: Every read and write MUST act only on the API's owner. Another owner's quantities
  MUST never be returned, counted or changed. A test MUST prove it through the API.

#### Contract and docs

- **FR-015**: The published API description and the generated frontend client MUST include the
  new ownership and completion shapes.
- **FR-016**: `docs/design.md` decisions 13 and 14 and its "Open items" MUST state the agreed
  rule: owning any version counts as owned, "só normal" is information only, and a set is
  complete when every card is owned (the bar has no track left), with a revision-history
  entry.

### Key Entities

- **Ownership**: an owner, a card and a variant, with a quantity (0–999). Owner-scoped
  (Principle V). A missing record means quantity 0.
- **Card ownership** (derived): a card's quantities for all its variants plus its owned and
  wanted-version-missing flags.
- **Set completion** (derived): `owned`, `so_normal`, `total` and complete, for one set.
- **Card**, **Set**, **Variant** (existing, PTCG-012) and **Owner** (existing, the household
  owner).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Any change to a card's quantity is reflected in the next read of its set and of
  the sets list, and survives an app restart.
- **SC-002**: For every case in the rules table (zero quantities, Normal-only card, Normal owned
  with a foil available, foil-only card, owned secret rares beyond the printed count), the
  owned, wanted-missing and completion answers match the rules above (asserted in unit tests).
- **SC-003**: No read or write through the API returns or alters a second owner's quantities
  (asserted in tests).
- **SC-004**: Ten rapid increments on the same card and variant leave its quantity at exactly
  10.
- **SC-005**: Reading the ownership of a typical 250-card set, or the sets list with
  completion, feels instant on the home server (well under a second).

## Assumptions

- The household owner seeded in PTCG-012 is the owner the API acts as.
- "Non-Normal variant" means any listed variant other than Normal (Reverse, Holo, First
  Edition, W Promo).
- Completion is reported for every set in the sets list, tracked or not; untracked sets usually
  show 0 owned.
- The read for a set covers all of its cards, including those beyond the printed count; only
  completion applies the placeholder cap.

## Out of Scope

- Which cards make up the completion total (secret rares, `88a`/`TG01` numbering, catalog
  gaps, variants dropped by the catalog) → PTCG-039
- Ownership UI (sticker, quantity controls, tile states) and the completion bar → PTCG-018,
  PTCG-019
- The default variant toggled by the sticker → PTCG-018
- Separate profiles per person → PTCG-031
- The card's "port + fake + contract suite" wording: superseded by the flat backend
  (PTCG-038); ownership follows `tables.py` / `routes/` like the rest.
