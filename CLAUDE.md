# CLAUDE.md

TCG Pokédex is a web app for tracking which Pokémon TCG cards we own or are missing in each set,
with card images and prices.

The constitution (`.specify/memory/constitution.md`) governs this project. This file covers
workflow only. It does not restate the constitution, and it defers to it on any conflict.

## Tickets & Trello

- Tickets live on the Trello board **TCG Pokédex**: https://trello.com/b/AXswhgp4. Read them
  through the Trello MCP. The board is the source of truth for tickets; `temp/` only holds old
  planning notes.
- Ticket codes are `PTCG-NNN`, numbered in dependency order. Card titles are
  `PTCG-NNN · <Name>`.
- Each card description starts with: Milestone, Labels, `spec-kit: yes|no`, Depends on, Branch.
- Lists: `Icebox` → `Backlog` → `Ready` → `In Progress` → `In Review (PR open)` → `Done`.
- Claude moves a card only at two points:
  - `Ready` → `In Progress` when the branch is created.
  - `In Progress` → `In Review (PR open)` when the PR is opened, and comments the PR link on
    the card.
- The user merges the PR and moves the card to `Done`.

## Working on a card

One card = one branch = one PR. `/start-work PTCG-NNN [notes]` (`.claude/skills/start-work/`)
runs steps 1–4 below and stops once the spec is written to `temp/specs/`.

1. Read the card. If a card listed under "Depends on" is not in `Done`, warn the user and ask
   before starting.
2. Move the card to `In Progress`.
3. Create the branch named in the card's **Branch** field (`PTCG-NNN-<short-slug>`) from an
   up-to-date `main`.
4. Then, depending on the card:
   - **`spec-kit: yes`**: first, in its own session, interview the user with the `grill-me`
     skill and write the result to `temp/specs/PTCG-NNN-<short-slug>.md`. Keep both short:
     - Interview: ask only about decisions that change the feature's behavior, one at a time,
       with a recommended answer. Look facts up instead of asking. Leave implementation choices
       (libraries, concurrency, file layout, fixtures) to `/speckit-plan`.
     - Spec: what and why only: user stories with acceptance scenarios, functional
       requirements, key entities, success criteria, out of scope. No provider surveys,
       consumer maps, plan notes or decision log. It should read in a few minutes.

     Then run the spec-kit flow on the ticket branch, feeding that file to
     `/speckit-specify`: `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` →
     `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`. Spec-kit names the artifact folder after the branch,
     `specs/PTCG-NNN-<short-slug>/`, and refuses to run `/speckit-specify` on any other
     branch. `/speckit-analyze` is required before implementing (constitution, Quality
     Gate 5).
   - **`spec-kit: no`** (chores, docs, spikes): agree on the open decisions with the user
     before implementing, one question at a time, each with a recommended answer, and write
     them to a short `temp/specs/PTCG-NNN-<short-slug>.md` (goal, agreed behaviour, done when,
     out of scope). Skip the questions only when the user says the card is unambiguous.
5. Commit, push the branch, open the PR, and move the card to `In Review (PR open)`.

## Commits

- Format: `type: summary` (Conventional Commits, scoped with the ticket code).
- Types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`, `ci`, `build`.
- Ordering of test and implementation commits: see Principle I in the constitution.

## Pull requests

- Title: `[PTCG-NNN] summary`. PRs are squash-merged, so the title becomes the commit on
  `main`.
- Body: follow `.github/pull_request_template.md`. `gh pr create --body …` does not apply the
  template, so build the body from it.
- On the ticket branch, Claude commits, pushes and opens the PR without asking each time.
  Claude's job ends when the PR is open: never push to `main`, never merge a PR.

## Visual direction

- `docs/design.md` sets the UI's visual direction (pillars, invariants, tokens, key
  behaviors). Screens follow it; a PR that changes the direction updates it and adds a
  revision-history entry. The mockups in `docs/design/mockups/` are reference only.

## Language

- UI text: Brazilian Portuguese (pt-BR), with strings centralized per slice.
- Everything else (code, commits, specs, cards, docs): English.

## Commands

- `bash .specify/tests/ptcg-customizations.test.sh`: tests for the spec-kit customizations
  below (needs `git` and `jq`).
- `bash .github/scripts/ci-gates.test.sh`: tests for the CI gate scripts (needs `git`).
- `bash .github/scripts/check-tdd-order.sh origin/main HEAD`: run the TDD-order gate on the
  branch before pushing.
- `bash .github/scripts/check-skipped-tests.sh`: check that every skipped, xfail or todo
  test names its ticket (`PTCG-NNN`) on the same line.

Whole stack (run from the repo root; needs Docker):

- `make db`: start the dev Postgres 17 from `compose.dev.yml` on 127.0.0.1:5432.
- `make migrate`: `make db`, then upgrade the dev database to the latest migration.
- `make dev`: `make migrate`, then the backend and frontend dev servers; Ctrl-C stops both.
- `make test`: backend tests with the coverage gate, then frontend tests.
- `make e2e`: build the production image, start it with a throwaway Postgres from
  `compose.e2e.yml` (app on 127.0.0.1:8001), run the Playwright tests, then tear the stack
  down. Needs Chromium once: `pnpm exec playwright install chromium` in `frontend/`.
- `docker build -t tcg-pokedex .`: build the production image (`Dockerfile`). It serves the
  SPA and the API on :8000, runs migrations on start and needs `TCG_POKEDEX_DATABASE_URL`,
  e.g. `docker run --rm -p 8000:8000 -e TCG_POKEDEX_DATABASE_URL=… tcg-pokedex`. Inside
  it, `tcg sync catalog` runs the catalog sync (e.g. `docker run --rm -e
  TCG_POKEDEX_DATABASE_URL=… tcg-pokedex tcg sync catalog`).
- `deploy/`: the home-server stack (`compose.yml`) and WUD auto-update (`wud/`). The runbook
  `deploy/README.md` covers install, rollback (pin `TCG_POKEDEX_IMAGE_TAG` to a commit sha)
  and the expand/contract-only migration rule.

Backend (run from `backend/`; needs `uv`, which installs Python 3.13):

- `uv sync`: install dependencies.
- `uv run uvicorn tcg_pokedex.app:create_app --factory --reload`: dev server on :8000.
  Config comes from `TCG_POKEDEX_*` env vars or `backend/.env` (see `backend/.env.example`).
- `uv run python -m tcg_pokedex.migrations`: upgrade `TCG_POKEDEX_DATABASE_URL` to the latest
  migration. The container entrypoint runs the same command.
- `uv run tcg sync catalog`: copy the TCGdex `pt` catalog (series, sets, cards) into
  `TCG_POKEDEX_DATABASE_URL`. Prints the run as JSON on stdout, logs JSON lines on stderr,
  and exits `0`/`1`/`2` for succeeded/partial/failed.
- `uv run alembic revision --autogenerate -m "<summary>"`: draft a migration from the tables
  in `tcg_pokedex/schema.py` (dev database at head first), then review it by hand.
- `uv run pytest`: run the tests. Database tests start Postgres with Testcontainers, so
  Docker must be running.
- `uv run pytest --cov`: run the tests with the coverage gate (branch coverage, 80% floor).
- `uv run ruff check .` and `uv run ruff format --check .`: lint and formatting.
- `uv run pyright --warnings`: strict type check; warnings also fail.

Frontend (run from `frontend/`; needs Node 26+ and pnpm, pinned in `package.json`):

- `pnpm install`: install dependencies.
- `pnpm dev`: dev server on :5173. It proxies `/api` and `/healthz` to the backend on :8000.
- `pnpm test`: run the tests.
- `pnpm test:e2e`: run the Playwright tests in `e2e/` against a stack already started with
  `docker compose -f ../compose.e2e.yml up -d --build --wait`. Specs import `test` and
  `expect` from `e2e/test.ts`, which fails any test whose browser requests leave the app
  origin, and use role-based selectors. Before the tests, `e2e/global-setup.ts` loads
  `e2e/fixtures/*.sql` into the database in name order, so fixtures must be idempotent when
  rerun against the same stack.
- `pnpm lint`, `pnpm format:check` and `pnpm typecheck`: lint, formatting and strict type
  check; warnings also fail.
- `pnpm generate:api`: regenerate `openapi.json` and `src/api-schema.gen.ts` from the backend.
  Run it after any backend API change and commit both files; never edit them by hand.

## CI and branch protection

- `.github/workflows/ci.yml` runs on every PR and on push to `main`. Its jobs are `backend`,
  `frontend`, `openapi-drift` (fails when `pnpm generate:api` changes the committed files),
  `shell-tests`, `commit-gates`, `image` (builds the production image and smoke-tests it
  against Postgres), `e2e` (runs the Playwright tests in Chromium against the image from
  `compose.e2e.yml`) and `publish`. `publish` runs only on push to `main`, after every other
  job passes, and pushes `ghcr.io/<owner>/tcg-pokedex:latest` and `:<full commit sha>`.
  `.github/workflows/pr-title.yml` runs `pr-title`.
- `commit-gates` fails a `feat`/`fix` commit that changes source with no `test` commit (one
  that changes test files) since the previous `feat`/`fix`. The source and test paths are
  listed in `.github/scripts/check-tdd-order.sh`; update them when a new source or test
  location appears.
- The `main` ruleset requires a PR, squash merges only, and eight checks (every job above
  except `publish`); it blocks force pushes and deletion, with no bypass.
  `.github/rulesets/main.json` is its source: after editing it, apply it with
  `gh api --method PUT repos/{owner}/{repo}/rulesets/<id> --input .github/rulesets/main.json`
  (`gh api repos/{owner}/{repo}/rulesets` lists the id). A renamed CI job must be renamed
  in the ruleset in the same PR.

## spec-kit customizations

Spec-kit is patched in place for ticket branches and mandatory test tasks:

- `.specify/scripts/bash/common.sh` and `create-new-feature.sh`
- `.claude/skills/speckit-specify/SKILL.md` and `.claude/skills/speckit-tasks/SKILL.md`
- `.specify/templates/overrides/tasks-template.md`, spec-kit's own override slot, which
  upgrades leave alone

`specify integration upgrade` refuses to overwrite the patched files unless run with
`--force`. If you force it, re-apply the PTCG-002 changes and run the tests above.

## Keeping this file current

A PR that adds a command (build, test, run, migrate…) or changes this workflow updates this
file in the same PR.
