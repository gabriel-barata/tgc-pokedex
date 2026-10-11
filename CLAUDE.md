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

One card = one branch = one PR.

1. Read the card. If a card listed under "Depends on" is not in `Done`, warn the user and ask
   before starting.
2. Move the card to `In Progress`.
3. Create the branch named in the card's **Branch** field (`PTCG-NNN-<short-slug>`) from an
   up-to-date `main`.
4. Then, depending on the card:
   - **`spec-kit: yes`**: run the spec-kit flow, `/speckit-specify` → `/speckit-clarify` →
     `/speckit-plan` → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`, on the
     ticket branch. Spec-kit names the artifact folder after the branch,
     `specs/PTCG-NNN-<short-slug>/`, and refuses to run `/speckit-specify` on any other
     branch. `/speckit-analyze` is required before implementing (constitution, Quality
     Gate 5).
   - **`spec-kit: no`** (chores, docs, spikes): agree on the open decisions with the user
     before implementing, one question at a time, each with a recommended answer. Skip this
     only when the user says the card is unambiguous.
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

## Language

- UI text: Brazilian Portuguese (pt-BR), with strings centralized per slice.
- Everything else (code, commits, specs, cards, docs): English.

## Commands

- `bash .specify/tests/ptcg-customizations.test.sh`: tests for the spec-kit customizations
  below (needs `git` and `jq`).

Backend (run from `backend/`; needs `uv`, which installs Python 3.13):

- `uv sync`: install dependencies.
- `uv run uvicorn tcg_pokedex.app:create_app --factory --reload`: dev server on :8000.
  Config comes from `TCG_POKEDEX_*` env vars or `backend/.env`.
- `uv run pytest`: run the tests.
- `uv run pytest --cov`: run the tests with the coverage gate (branch coverage, 90% floor).
- `uv run ruff check .` and `uv run ruff format --check .`: lint and formatting.
- `uv run pyright --warnings`: strict type check; warnings also fail.

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
