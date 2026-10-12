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
runs steps 1–4 below and stops once the plan (`spec-kit: no`) or spec (`spec-kit: yes`) is
written to `temp/specs/`. Implementation always starts in a new session.

1. Read the card. If a card listed under "Depends on" is not in `Done`, warn the user and ask
   before starting.
2. Move the card to `In Progress`.
3. Create the branch named in the card's **Branch** field (`PTCG-NNN-<short-slug>`) from an
   up-to-date `main`.
4. Then, depending on the card:
   - **`spec-kit: no`** (the default): enter plan mode and interview the user in depth, about
     behaviour and also technology, architecture, data model, dependencies and file layout.
     Each question has a recommended answer; up to 4 independent questions may go in one
     round. The output of this session is the approved plan (context, behaviour, decisions,
     changes, tests, commits, verification, out of scope), saved to
     `temp/specs/PTCG-NNN-<short-slug>.md`. A new session implements it.
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
     `/speckit-tasks` → `/speckit-implement`. Spec-kit names the artifact folder after the
     branch, `specs/PTCG-NNN-<short-slug>/`, and refuses to run `/speckit-specify` on any
     other branch. `specs/` is gitignored: its artifacts stay local and never go in the PR.
     `/speckit-analyze` between tasks and implement is optional. Spec-kit is being phased
     out; new cards default to `spec-kit: no`.
5. Commit, push the branch, open the PR, and move the card to `In Review (PR open)`.

## Tests

Test only the main behaviours: the happy path and the one or two failures that matter, then
stop once the 80% coverage floor passes (constitution, Principle VI). Every plan (and every
spec-kit `tasks.md`) lists the tests it will add, and the user approves that list with the plan.
Don't add tests beyond it. Prefer one parametrized test over near-duplicates and keep fixtures
small. A PR exists so a human can review it; a long test diff defeats that.

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

- UI text: Brazilian Portuguese (pt-BR), with strings centralized in `frontend/src/strings/`.
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
  it, `tcg sync catalog` runs the catalog sync, `tcg sync images` the image sync and
  `tcg sync all` both (e.g.
  `docker run --rm -e TCG_POKEDEX_DATABASE_URL=… tcg-pokedex tcg sync catalog`). Cached
  images live in `/data/images` (`TCG_POKEDEX_IMAGE_DIR`); mount a volume there to keep them.
  `supercronic -passthrough-logs /app/crontab` runs the sync schedule instead of the app.
- `deploy/`: the home-server stack (`compose.yml`: the app, the `worker` that runs the sync
  schedule from `deploy/crontab`, and Postgres) and WUD auto-update (`wud/`). The runbook
  `deploy/README.md` covers install, the schedule, rollback (pin `TCG_POKEDEX_IMAGE_TAG` to a
  commit sha) and the expand/contract-only migration rule.

Backend (run from `backend/`; needs `uv`, which installs Python 3.13, and the `atlas`
standard build, e.g. `brew install ariga/tap/atlas`; `tcg migrate` needs only `atlas migrate
apply`, so the image ships the community build pinned in `Dockerfile`). Layout under
`src/tcg_pokedex/` (constitution, Principle III):
`views/` (API shapes, enums), `models/` (table classes and every query), `controllers/`
(HTTP handlers), `jobs/` (syncs), `providers/` (TCGdex client), `web/` (SPA files), plus
`app.py`, `config.py`, `cli.py` and `database.py`; tests mirror it.

- `uv sync`: install dependencies.
- `uv run uvicorn tcg_pokedex.app:create_app --factory --reload`: dev server on :8000.
  Config comes from `TCG_POKEDEX_*` env vars or `backend/.env` (see `backend/.env.example`).
- `uv run tcg migrate`: upgrade `TCG_POKEDEX_DATABASE_URL` to the latest migration with
  `atlas migrate apply`. A database Alembic built is baselined on its first run. The
  container entrypoint runs the same command.
- `uv run tcg openapi`: print the API's OpenAPI schema as JSON (`pnpm generate:api` uses it).
- `uv run tcg sync catalog`: copy the TCGdex `pt` catalog (series, sets, cards) into
  `TCG_POKEDEX_DATABASE_URL`. Prints the run as JSON on stdout, logs JSON lines on stderr,
  and exits `0`/`1`/`2` for succeeded/partial/failed.
- `uv run tcg sync images`: cache the card images of every tracked set and every set's logo
  and symbol into `TCG_POKEDEX_IMAGE_DIR` (default `data/images`, i.e. `backend/data/images`,
  git-ignored). Same output and exit codes as `tcg sync catalog`. Tracking a set through
  `PUT /api/sets/{set_id}/tracking` also downloads that set's card images in the background.
- `uv run tcg sync all`: `tcg sync catalog`, then `tcg sync images` unless the catalog run
  failed. Prints one JSON line per run and exits with the worse run's code. `POST /api/sync`
  ("Sincronizar agora" on `/status`) starts the same in the background.
- Only one sync runs at a time (a Postgres advisory lock): a `tcg sync` that finds another
  sync or set download running exits `2` without a run, and `POST /api/sync` answers `409`.
- `atlas migrate diff <summary> --env local`: draft a plain-SQL migration in
  `backend/migrations/` from the table classes in `models/` (needs Docker for the dev
  database), review it by hand; `atlas migrate hash` after editing it. CI fails when the
  models and the migrations disagree.
- `uv run pytest`: run the tests. Database tests start Postgres with Testcontainers, so
  Docker must be running.
- `uv run pytest --cov`: run the tests with the coverage gate (branch coverage, 80% floor).
- `uv run ruff check .` and `uv run ruff format --check .`: lint and formatting.
- `uv run pyright --warnings`: strict type check; warnings also fail.

Frontend (run from `frontend/`; needs Node 26+ and pnpm, pinned in `package.json`). Layout
under `src/`, one folder per role: `api/` (the API client, the generated schema and one
hooks file per resource), `pages/` (one per route), `components/` (pieces grouped by area:
`layout/`, `sets/`, `status/`), `strings/` (pt-BR text, one file per area), `ui/` (design
tokens, shadcn components, motifs) and `testing/` (test setup, MSW server, render helper),
plus `main.tsx` and `App.tsx` (the route table). Imports use the `@/` alias for `src/`;
tests sit next to the file they test.

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
- `pnpm dlx shadcn@latest add <component>`: copy a shadcn/ui component into `src/ui/`
  (`components.json`), then restyle it with the tokens in `src/ui/theme.css`, the
  single source of design tokens (`docs/design.md`).
- `pnpm generate:api`: regenerate `openapi.json` and `src/api/schema.gen.ts` from the backend.
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

Spec-kit is patched in place for ticket branches and mandatory test tasks. Its artifacts in
`specs/` are gitignored. The patched files:

- `.specify/scripts/bash/common.sh` and `create-new-feature.sh`
- `.claude/skills/speckit-specify/SKILL.md` and `.claude/skills/speckit-tasks/SKILL.md`
- `.specify/templates/overrides/tasks-template.md`, spec-kit's own override slot, which
  upgrades leave alone

`specify integration upgrade` refuses to overwrite the patched files unless run with
`--force`. If you force it, re-apply the PTCG-002 changes and run the tests above.

## Keeping this file current

A PR that adds a command (build, test, run, migrate…) or changes this workflow updates this
file in the same PR.
