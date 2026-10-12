# TCG Pokédex Constitution

TCG Pokédex is a web application for tracking which Pokémon TCG cards the owner has or is
missing in each set or collection, showing each card's image and market price (MVP). This
constitution sets principles only. It deliberately names no technologies; the stack is chosen
per feature in `/speckit-plan` and must comply with everything below.

## Core Principles

### I. Test-Driven Development (NON-NEGOTIABLE)

This applies to every change, with no exceptions beyond those listed here.

- Every behavior change MUST start with a failing test and follow Red → Green → Refactor.
- `tasks.md` MUST list each test task before the implementation task it covers.
- A TDD cycle covers one major behaviour, not one file or one small step.
- Each TDD cycle MUST be a commit pair: first a `test:` commit containing the failing test,
  then a `feat:` or `fix:` commit that makes it pass. Tests MUST NOT be committed after the
  code they cover. Commits MUST NOT be split per file.
- The only exemptions are pure configuration, generated code, and throwaway spikes. Spike
  code MUST be deleted and rewritten test-first before merge.
- UI behavior MUST be tested. Visual styling is not unit-tested.

**Rationale**: Writing the test first makes every requirement executable. It keeps the design
driven by use rather than by implementation, and the commit history shows that the process was
followed.

### II. DRY — Single Source of Knowledge

- Every piece of knowledge MUST have exactly one authoritative representation. This includes:
  - domain rules (e.g. ownership, set completion);
  - data shapes, validation, and API contracts, which MUST be derived from one definition and
    never kept as hand-maintained parallel copies across boundaries;
  - provider-to-domain mapping;
  - configuration.
- Code duplication follows the rule of three: extract on the third occurrence, during the
  Refactor step, and not before.
- Tests favor clarity over DRY. Builders, factories, and port fakes MUST be shared, but
  assertions MUST stay explicit inside each test.

**Rationale**: Parallel copies of the same knowledge drift apart and cause silent bugs. Shared
test assertions hide what each test actually checks.

### III. Ports & Adapters, Vertical Slices

- The domain core MUST be pure: no I/O, framework, database, network, or clock dependencies.
- All interaction with the outside world MUST go through ports (persistence, catalog provider,
  price provider, clock). Dependencies MUST point inward only.
- Code MUST be organized by feature slice (e.g. `collection-tracking`, `catalog-sync`,
  `pricing`). Each slice holds its own domain, ports, and adapters; global layer folders are
  not allowed.
- Each port MUST have exactly one shared in-memory fake.

**Rationale**: A pure core can be unit-tested quickly and does not depend on the stack chosen.
Organizing by slice keeps each feature's code together, so a change stays local to it.

### IV. Own the Data, Isolate Providers

- External sources of card, set, and price data MUST be accessed only through adapters, during
  a periodic sync job that writes into the app's own store.
- The app MUST read only from its own store and MUST NOT call a provider at request time.
- All externally sourced data MUST carry its source and fetched-at timestamp. History MUST be
  appended, never overwritten.

**Rationale**: Provider outages, rate limits, and API changes then cannot break the user
experience. Keeping the price history from the start costs little now and would be impossible
to recover later.

### V. Owner-Scoped from Day One

- Every user-owned record (collections, ownership) MUST be scoped to an owner from the start,
  even though the MVP runs single-user.
- Owner scoping MUST be enforced in the application layer and covered by tests.

**Rationale**: Adding ownership to existing data later is a costly and risky migration. Doing
it from the start costs almost nothing.

### VI. Test Strategy

- **Scope**: tests MUST cover the main behaviours of a feature: the happy path and the failure
  paths that matter. They MUST NOT enumerate every edge case or spec scenario. Reaching the
  coverage floor with main-behaviour tests is enough.
- **Coverage**: backend branch coverage MUST be at least 80%.
- **Unit**: all domain logic MUST have unit tests. They run fast, do no I/O, and make up the
  bulk of the suite.
- **Port contract suites**: each port MUST have one shared contract suite, run against BOTH its
  in-memory fake and its real adapter.
- **Provider adapters**: MUST be tested against recorded fixtures, kept to a few payloads
  trimmed to the fields the adapter reads. An optional, separate live-check job MAY detect
  provider API drift; it is not part of the regular suite.
- **Persistence adapters**: MUST have integration tests against the real database engine,
  never a mock of it.
- **End-to-end**: each P1 user story MUST have at least one happy-path test through the real UI,
  using role-based selectors.
- Tests MUST NOT call the real network. Time-dependent logic MUST use an injected clock.

**Rationale**: Contract suites prove that the fakes behave like the real adapters, which makes
it safe to rely on fast fake-backed tests. Role-based selectors also check accessibility. One PR
per ticket exists so a human can review it; a suite that tests every detail defeats that.

### VII. Simplicity (YAGNI)

- Build only what the current spec requires.
- Speculative abstractions, options, or extension points are violations unless justified in
  the plan's Complexity Tracking table.
- YAGNI balances DRY: do not abstract ahead of real duplication (see Principle II).

**Rationale**: Unused flexibility is a cost that is paid now, for a benefit that may never
come.

## Additional Constraints

- **Security**: secrets MUST NOT be stored in the repository or exposed to the client. All
  external input (user requests, provider responses, configuration) MUST be validated at the
  boundary using the single schema definition from Principle II.
- **Accessibility**: every interactive element MUST be keyboard-operable and have an accessible
  name. Card images MUST have alt text giving the card name, set, and number.
- **Observability**: sync jobs MUST emit a structured result with fetched, updated, and failed
  counts and the duration. Failures MUST NOT be swallowed; they are surfaced in that result
  and logged.

## Development Workflow & Quality Gates

The following gates are enforced in CI and block merging:

1. All test levels pass, with backend branch coverage of at least 80%. A skipped test MUST
   reference a linked issue.
2. The commit history shows red-before-green ordering for each TDD cycle (Principle I).
3. Lint, formatting, and type/static checks pass with zero warnings. Every suppression MUST
   carry an inline justification.
4. Every new dependency MUST have a one-line justification in `plan.md` explaining why a few
   lines of our own code would not do.
5. `/speckit-analyze` MUST run before `/speckit-implement`. Any violation it reports MUST be
   either fixed or logged in Complexity Tracking.

## Governance

- This constitution supersedes all other practices and conventions in the project. When
  another document or guidance file conflicts with it, the constitution wins.
- Amendments MUST be made through `/speckit-constitution` and documented with a Sync Impact
  Report, and they MUST include a migration plan for any existing artifacts or code they
  affect.
- Versioning follows semantic versioning:
  - **MAJOR**: a principle or governance rule is removed or redefined in an incompatible way.
  - **MINOR**: a principle or section is added, or guidance is materially expanded.
  - **PATCH**: clarifications, wording, or typo fixes that change no meaning.
- Every plan (Constitution Check), every review, and every pull request MUST verify compliance.
  Any deviation MUST be justified in the plan's Complexity Tracking table; otherwise it is
  rejected.
- Runtime development guidance (e.g. the agent guidance file) MUST stay consistent with this
  constitution and MUST NOT restate or override it.

**Version**: 1.1.0 | **Ratified**: 2026-10-04 | **Last Amended**: 2026-10-12
