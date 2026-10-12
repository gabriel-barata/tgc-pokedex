# Feature Specification: Tracked sets & local image cache

**Feature Branch**: `PTCG-013-tracked-sets-images`

**Created**: 2026-10-12

**Status**: Draft

**Input**: `temp/specs/PTCG-013-tracked-sets-images.md` (grill-me interview).
Trello card: https://trello.com/c/p3Njpe6f/13-ptcg-013-tracked-sets-local-image-cache.
Depends on PTCG-012 (catalog sync).

## Overview

The owner marks the sets they collect as **tracked**. The app then downloads those sets' card
images (small and large) from TCGdex into its own storage and serves them itself, so no page
ever loads an image from the provider (Principle IV). A card without a Portuguese image uses its
English one, and a card with no image in either language is reported as unavailable. Set logos
and symbols are cached for every stored set, because the sets page lists all of them.

This feature has no UI. The track toggle belongs to PTCG-015 and the card grid to PTCG-016; here
the owner tracks sets through the API and the operator runs `tcg sync images`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Track a set and get its images served locally (Priority: P1)

As the household owner, I track a set, so that its card images load fast and from our own
server, even when TCGdex is slow or down.

**Why this priority**: The card grid (PTCG-016) cannot show images without it, and serving
provider images at request time would break Principle IV.

**Independent Test**: Against the running app, track a set through the API. Once the set
reports its download finished, every card with an available image is served from the app's
image URL, and no request reached the provider while serving it.

**Acceptance Scenarios**:

1. **Given** an untracked set, **When** the owner tracks it, **Then** the request returns at
   once, the set reports itself as tracked and downloading, and its images download in the
   background.
2. **Given** the background download has finished, **When** a card's small or large image is
   requested from the app, **Then** the app serves it from its own storage with long-lived
   cache headers.
3. **Given** a card with no pt image but an English one, **When** its set downloads, **Then**
   the English image is cached and served, and the card records `en` as its image source.
4. **Given** a card with no image in pt or English, **When** its set downloads, **Then** the
   card counts as unavailable, its image URL returns not found, and the set still finishes.
5. **Given** a set that is already tracked, **When** the owner tracks it again, **Then** nothing
   changes and no second download starts.
6. **Given** a tracked set, **When** the owner reads the set, **Then** it reports total cards,
   images cached, images unavailable and whether a download is running.

---

### User Story 2 - Untrack a set (Priority: P2)

As the household owner, I untrack a set I no longer collect, so that the app stops downloading
its images.

**Why this priority**: It keeps downloads limited to what the household collects, but the MVP
works without it.

**Independent Test**: Untrack a set, run `tcg sync images`, and check that no card image of that
set was requested from the provider.

**Acceptance Scenarios**:

1. **Given** a tracked set, **When** the owner untracks it, **Then** it reports untracked, and
   later sync runs request none of its card images.
2. **Given** an untracked set whose images were cached before, **When** one of them is
   requested, **Then** it is still served. Untracking deletes nothing.
3. **Given** a set that was never tracked, **When** any sync runs, **Then** none of its card
   images are downloaded.

---

### User Story 3 - Catch up all images with one command (Priority: P2)

As the household operator, I run `tcg sync images`, so that every tracked set is complete and
every set has its logo and symbol, including anything a background download missed.

**Why this priority**: It recovers from failed or interrupted downloads and picks up new pt
images. PTCG-014 schedules it.

**Independent Test**: With a provider fake holding a mix of pt, English-only, missing and
failing images, run the command and check the cached files, the run record and the exit code.

**Acceptance Scenarios**:

1. **Given** tracked sets with some images missing from the cache, **When** the command runs,
   **Then** it downloads only the missing ones, and images already cached from pt are not
   downloaded again.
2. **Given** a card cached from English (or unavailable) whose pt image has since appeared in
   the catalog, **When** the command runs, **Then** the pt image replaces it and the source
   becomes `pt`.
3. **Given** one card's download fails, **When** the command runs, **Then** that card is
   counted and logged as failed, the rest continue, the run is `partial` with exit code `1`,
   and the next run retries the card.
4. **Given** stored sets, tracked or not, **When** the command runs, **Then** each set's logo
   and symbol that the provider has are cached and served by the app.
5. **Given** a run ends, **Then** it is recorded as a sync run of kind `images`, with the same
   status, result and exit-code conventions as `tcg sync catalog`.

---

### Edge Cases

- **One size fails**: if a card's small image downloads but its large one fails, the card
  counts as failed and neither size is kept from that attempt; a card is cached in both sizes
  or not at all.
- **Provider down when tracking**: tracking still succeeds; the background run ends `partial`
  or `failed`, the set reports zero (or fewer) cached images, and the next `tcg sync images`
  fills it in.
- **Untrack during a download**: a download already in progress may finish; untracking only
  affects later runs. Whatever it cached stays.
- **Retrack**: tracking a set again after untracking starts a new background download that
  fetches only what is missing.
- **App restarted mid-download**: the background download is not resumed; the set no longer
  reports a download running, and the next `tcg sync images` completes it.
- **Overlapping runs** (a background download and the command on the same set): not prevented
  here (PTCG-014). They are harmless because each image is written whole or not at all.
- **Set without logo or symbol**: it simply has none; this is not a failure.
- **Response that is not an image**: treated as a failed download, with its reason.

## Requirements *(mandatory)*

### Functional Requirements

#### Tracking

- **FR-001**: Tracking is owner-scoped: a tracked set belongs to an owner and a set. In the MVP
  the API acts as the household owner.
- **FR-002**: The API MUST let the owner track and untrack a set. Both are idempotent, and an
  unknown set id returns not found.
- **FR-003**: The API MUST report, for each set, whether the owner tracks it, plus its image
  progress: total cards, images cached, images unavailable, and whether a download is running.
- **FR-004**: Tracking a set that was untracked MUST start that set's image download in the
  background without delaying the response, and MUST record it as an `images` sync run.
- **FR-005**: Card images MUST be downloaded only for sets that at least one owner tracks.

#### Card images

- **FR-006**: Each card image MUST be cached in two sizes, small (grid) and large (detail).
- **FR-007**: A card's image source MUST be its pt image when the catalog has one. Otherwise it
  is the English image of the same card, when TCGdex has one. Otherwise the card is
  unavailable.
- **FR-008**: Each cached card image MUST record its source language (`pt` or `en`) and when it
  was fetched.
- **FR-009**: Images already cached from pt MUST NOT be downloaded again. Cards cached from
  English, and unavailable cards, MUST be re-checked on every run and upgraded to pt when it
  appears.

#### Command and set artwork

- **FR-010**: `tcg sync images` MUST take no flags. It processes every tracked set's card
  images and every stored set's logo and symbol.
- **FR-011**: Set logos and symbols MUST be cached for every stored set, tracked or not. A set
  without a logo or symbol at the provider simply has none. Artwork already cached is not
  downloaded again.

#### Failures and results

- **FR-012**: A failed download (one card, logo or symbol) MUST be counted and logged with its
  reason, MUST NOT stop the run, and MUST leave nothing half-written in the cache.
- **FR-013**: Every image run (command or track-triggered) MUST report counts of downloaded,
  already cached, unavailable and failed images, plus its duration. Its status and exit code
  follow the catalog sync rules: `succeeded`/0, `partial`/1, `failed`/2.

#### Serving and storage

- **FR-014**: The app MUST serve cached card images (both sizes), logos and symbols at its own
  URLs, with long-lived cache headers, and MUST never contact the provider while serving one.
  An image that is not cached returns not found.
- **FR-015**: Untracking MUST NOT delete cached images, and they stay servable.
- **FR-016**: The image cache MUST survive app restarts and image updates in the home-server
  deployment.

### Key Entities

- **Tracked set**: an owner and a set, with the time it was tracked. Owner-scoped
  (Principle V).
- **Card image**: a card's cached image, with its source language (`pt`/`en`), its cached sizes
  and its fetched-at time. A card with no such record is either pending or unavailable.
- **Set artwork**: a set's cached logo and symbol, each with its fetched-at time. Shared
  reference data, not owner-scoped.
- **Sync run** (existing, PTCG-012): reused with kind `images`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the home server, a typical 250-card set is fully cached within 10 minutes of
  being tracked.
- **SC-002**: No sync requests any card image of a set that no owner tracks (asserted in
  tests).
- **SC-003**: A second `tcg sync images` with nothing new downloads no card image already
  cached from pt.
- **SC-004**: Serving any cached image makes no request outside the app (the end-to-end
  suite's origin guard stays green).

## Assumptions

- The catalog (PTCG-012) already holds each card's pt image reference and each set's logo and
  symbol reference; the English image is looked up from TCGdex's English catalog by the same
  card id.
- Counts are per card (one card covers both sizes) and per logo or symbol.
- A run is `failed` (exit `2`) only when it cannot run at all, e.g. the store or the image
  storage is unusable; per-image problems make it `partial`.
- A track-triggered run covers only that set's card images; logos and symbols are handled by
  `tcg sync images`.
- The household owner seeded in PTCG-012 is the owner the API acts as.

## Out of Scope

- Track toggle on the sets page, binder covers → PTCG-015
- Card grid and detail rendering, including the "Imagens sendo sincronizadas" and "Imagem
  indisponível" states → PTCG-016
- Scheduled runs, the worker service, "Sincronizar agora", status page, concurrent-run guard →
  PTCG-014
- Deleting cached images, disk quotas or cache eviction
- Marking English-fallback images in the UI
- Separate profiles per person → PTCG-031
