---
name: start-work
description: "Start work on a TCG Pokédex ticket (PTCG-NNN): read the Trello card, check its dependencies, create the branch, move the card to In Progress, then run a short interview and write a behaviour-only spec to temp/specs/PTCG-NNN-<slug>.md. Use it whenever the user wants to begin a card, e.g. \"start PTCG-013\", \"let's pick up 14\", \"/start-work PTCG-015 keep it phone-first\", even if they don't name the skill."
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

## What this skill produces, and what it does not

It produces a card that is ready to work on (dependencies checked, branch created, card in
`In Progress`) and a short **specification** of the behaviour the user wants. The spec says
*what* the feature does and *why*. It is not an implementation plan. `/speckit-plan` (for
`spec-kit: yes` cards) or the implementation session (for `spec-kit: no` cards) makes the
implementation decisions later, with the codebase in front of it.

This matters because the first time this was done by hand (PTCG-012), the interview ran to 17
questions and the spec to about 400 lines, with provider surveys, a consumer map, plan notes and
a decision log. The user found both too long. The aim is a few focused questions and a spec that
reads in a few minutes.

`CLAUDE.md` ("Tickets & Trello", "Working on a card") and the constitution
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

### 5. Interview

**Look up what you need first.** The card, the constitution, `docs/design.md` (for anything with
UI), the merged specs of the cards it builds on (`specs/PTCG-*/spec.md`), the relevant code and,
when a provider is involved, the provider's live API. Anything you can look up is a fact, not a
question. If a fact constrains behaviour (say, some sets have no cards in `pt`), the question is
what the feature should *do* about it. Ask that, and don't report the survey.

**Ask only about decisions that change behaviour**: what the user sees or relies on, edge cases
whose outcome is a real choice, where the scope line falls, and what "done" means when the
acceptance criteria are vague. Leave implementation choices alone (libraries, concurrency, data
types, file and module layout, ports, fixtures, test approach). That is `/speckit-plan`'s job.
If you catch yourself asking "how should we build X?", drop the question.

**One question at a time, each with a recommended answer** and a one-line reason, so the user can
mostly confirm. Use `AskUserQuestion` with the recommended option first when the choices are
discrete. If the obvious default is one the user would almost certainly accept, don't ask. Write
it into the spec, where they will review it anyway.

**Keep it short.** Most cards need 3–6 questions; a small chore may need none. Past about 8, you
are probably drifting into planning. Stop, look at what's left, and keep only what changes
behaviour.

Stop when every acceptance criterion can be turned into a concrete scenario and the
behaviour-changing edge cases are settled.

### 6. Write the spec

Write `temp/specs/<branch-name>.md`. `temp/` is gitignored, so the spec stays local and is not
committed. Write it in English. UI text the user agreed on stays in pt-BR, as it will appear.

**`spec-kit: yes` cards** use this shape:

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

Drop "Key entities" when the feature adds no data. Priorities follow the constitution: P1 stories
need an end-to-end happy path.

**`spec-kit: no` cards** (chores, docs, spikes) use a lighter shape: header, **Goal**, **Agreed
behaviour** (bullets), **Done when** (checkable bullets) and **Out of scope**.

Keep out of both: provider or API surveys, consumer maps, decision logs, notes for the plan,
library or layout choices, fixture lists and test designs. If a decision matters, it already
appears as a requirement or scenario, and a log only repeats it. Aim for well under 150 lines;
a chore fits in 30.

### 7. Hand off

Show the user the path and a 3–5 line summary of the spec, and ask for corrections. Edit the file
if they give any. Then name the next step and stop. Don't run it in this session:

- `spec-kit: yes`: in a new session, `/speckit-specify temp/specs/<branch-name>.md`, then the
  rest of the spec-kit flow in `CLAUDE.md`.
- `spec-kit: no`: in a new session, implement from the spec, then follow `CLAUDE.md` step 5
  (commit, push, PR, move the card to `In Review (PR open)`).
