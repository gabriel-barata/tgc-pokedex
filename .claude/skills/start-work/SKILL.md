---
name: start-work
description: "Start work on a TCG Pokédex ticket (PTCG-NNN): read the Trello card, check its dependencies, create the branch, move the card to In Progress, then either (spec-kit: no) run a deep interview in plan mode and save the approved implementation plan, or (spec-kit: yes) run a short interview and write a behaviour-only spec, to temp/specs/PTCG-NNN-<slug>.md. Use it whenever the user wants to begin a card, e.g. \"start PTCG-013\", \"let's pick up 14\", \"/start-work PTCG-015 keep it phone-first\", even if they don't name the skill."
argument-hint: "PTCG-NNN [notes]"
user-invocable: true
---

# Start work on a card

## Input

```text
$ARGUMENTS
```

The first token is the ticket. Normalise it to `PTCG-NNN` (`13`, `ptcg-13` and `PTCG-013` all mean
`PTCG-013`). Anything after it is the user's notes for this card. Treat the notes as answers
given in advance or as scope limits, and don't ask again about what they already settle. If
there is no ticket, ask for one.

## What this skill produces

A card that is ready to work on (dependencies checked, branch created, card in `In Progress`) and
one file, `temp/specs/<branch-name>.md`, whose content depends on the card's `spec-kit` field:

- **`spec-kit: no`** (the default path): an approved **implementation plan**. The interview goes
  deep: behaviour *and* technology, architecture, data model, libraries, file layout and the core
  decisions. It runs in plan mode, and the session ends when the user approves the plan. A fresh
  session implements it.
- **`spec-kit: yes`**: a short **specification** of the behaviour only (what and why).
  `/speckit-plan` makes the implementation decisions later.

Both must stay short enough to read in a few minutes. The first hand-made spec (PTCG-012) ran to
17 questions and about 400 lines, with provider surveys and a decision log, and the user found it
far too long.

`CLAUDE.md` ("Tickets & Trello", "Working on a card", "Tests") and the constitution
(`.specify/memory/constitution.md`) govern this workflow. If this skill and they disagree, they win.

## Steps

### 1. Read the card

The board is **TCG Pokédex**, https://trello.com/b/AXswhgp4. Find the card through the Trello MCP.
Search is fuzzy: a search for `PTCG-013` also returns cards that merely mention it in "Depends
on". Pick the card whose **title** contains `PTCG-NNN ·`. A title can carry a prefix such as
`[IMPORTANT]`, and titles may come back HTML-escaped (`&amp;`). Listing the whole board once
(`trelloReadCard` `list_by_board`) also gives you every card's list, which you need in step 2.

From the description, read the header fields (Milestone, Labels, `spec-kit`, Depends on, Branch)
and the Goal and Acceptance criteria. Skim the card's comments too.

Stop and ask the user before going on if:
- no card matches;
- the card is already in `In Progress`, `In Review (PR open)` or `Done`;
- `temp/specs/PTCG-NNN-*.md` already exists. Offer to resume from it rather than overwrite it.

### 2. Check dependencies

For each card under "Depends on", check its list. If any is not in `Done`, tell the user which
ones and where they are, and ask whether to start anyway. Don't decide this yourself.

### 3. Create the branch

The branch is the card's **Branch** field, `PTCG-NNN-<short-slug>`. If it is still a placeholder
(`PTCG-NNN-<slug>`, "set when started"), propose a 2–4 word kebab-case slug from the title and
confirm it with the user. Then update the Branch line in the card's description, changing nothing
else.

Create it from an up-to-date `main`:

```bash
git status --porcelain
git switch main && git pull --ff-only
git switch -c PTCG-NNN-<short-slug>
```

If the working tree is dirty or the branch already exists, stop and ask. Never stash, reset or
delete anything to get past it.

### 4. Move the card to `In Progress`

Do this only after the branch exists, since `CLAUDE.md` ties the move to branch creation.
This is the only card move this skill makes.

### 5. Look things up

Before asking anything, read what you need: the card, the constitution, `CLAUDE.md`,
`docs/design.md` (for anything with UI), the code the card touches and, when a provider is
involved, the provider's live API. Local `specs/PTCG-*/` folders (gitignored) may hold the specs
of earlier spec-kit cards. Anything you can look up is a fact, not a question.

Then follow **6a** for `spec-kit: no` or **6b** for `spec-kit: yes`.

### 6a. `spec-kit: no`: deep interview in plan mode

**Enter plan mode** (`EnterPlanMode`) and interview the user there.

**Ask about everything that shapes the implementation**: behaviour the user sees or relies on,
the scope line, and the technical decisions (architecture, data model and migrations, libraries
and new dependencies, file and module layout, how the pieces talk to each other, rollout on the
homelab). The goal is that the implementation session has nothing left to decide.

**Each question comes with a recommended answer** and a one-line reason, recommended option
first in `AskUserQuestion`. To keep it fast, batch up to 4 *independent* questions in one
`AskUserQuestion` call; ask dependent ones in a later round. If the obvious default is one the
user would almost certainly accept, don't ask: put it in the plan, where they will review it.
Data edge cases that need real research go to a new card, not more questions.

**Write the plan** to the plan file with this shape, well under 150 lines:

```markdown
# PTCG-NNN · <Card name>: plan

- **Card:** <card URL>
- **Branch:** `PTCG-NNN-<short-slug>`
- **Depends on:** <codes, or none>

## Context
<Why this change: the problem, what prompted it, the intended outcome.>

## Agreed behaviour
- <what the user or the system will do, as bullets>

## Decisions
- **<topic>:** <choice>, because <one line>. New dependencies carry their justification
  (Quality Gate 4).

## Changes
- `<path>`: <what changes>. Describe a pattern that repeats across files once, with a few
  representative paths.

## Tests
- <behaviour>: <the happy-path test, plus the one or two failures that matter>
<Stop at what the 80% floor needs. Docs/config-only cards: "none, exempt (Principle I)".>

## Commits
1. `test(PTCG-NNN): …` / `feat(PTCG-NNN): …` pairs per major behaviour; `docs:`/`chore:` for
   exempt work.

## Verification
- <commands to run and what they must show>

## Deviations
<Constitution deviations and why, or "none".>

## Out of scope
- <thing> → <card that owns it, if any>
```

**Get approval** with `ExitPlanMode`. If the user asks for changes, revise and ask again.

**Once approved**, copy the plan to `temp/specs/<branch-name>.md` (`temp/` is gitignored), then
hand off (step 7). Don't implement in this session.

### 6b. `spec-kit: yes`: short interview, behaviour-only spec

**Ask only about decisions that change behaviour**: what the user sees or relies on, edge cases
whose outcome is a real choice, where the scope line falls, and what "done" means when the
acceptance criteria are vague. Leave implementation choices (libraries, layout, test approach) to
`/speckit-plan`. One question at a time, each with a recommended answer. Most cards need 3–6
questions; past about 8 you are drifting into planning.

Write `temp/specs/<branch-name>.md` in English (UI text the user agreed on stays in pt-BR):

```markdown
# PTCG-NNN · <Card name>: specification

- **Card:** <card URL>
- **Branch:** `PTCG-NNN-<short-slug>`
- **Depends on:** <codes, or none>

## Summary
<2–4 sentences: what the feature does and why.>

## User stories

### US1 · <title> (P1)
As <who>, I <do what>, so that <why>.

**Independent test:** <how this story is checked on its own>

Acceptance scenarios:
1. **Given** …, **when** …, **then** …

## Functional requirements
- **FR-001** <a behaviour the system MUST have, testable, without saying how it's built>

## Key entities
- **<Entity>:** <what it represents and the attributes that matter to the behaviour>

## Success criteria
- **SC-001** <measurable outcome>

## Out of scope
- <thing> → <card that owns it, if any>
```

Drop "Key entities" when the feature adds no data. P1 stories need an end-to-end happy path
(constitution). Keep out provider surveys, decision logs, plan notes and test designs. Aim for
well under 150 lines.

### 7. Hand off

Show the user the path and a 3–5 line summary. Then name the next step and stop:

- `spec-kit: no`: in a new session, "implement `temp/specs/<branch-name>.md`", then `CLAUDE.md`
  step 5 (commit, push, PR, move the card to `In Review (PR open)`).
- `spec-kit: yes`: in a new session, `/speckit-specify temp/specs/<branch-name>.md`, then the
  rest of the spec-kit flow in `CLAUDE.md`.
