# Quickstart: validate the catalog sync

How to show that PTCG-012 works. The behavior is in [spec.md](spec.md), the command's output
in [contracts/cli.md](contracts/cli.md), and the tables in [data-model.md](data-model.md).

## Prerequisites

- Docker running (dev Postgres and Testcontainers).
- `uv` installed; `cd backend && uv sync`.

## 1. Automated checks (CI equivalent)

```bash
cd backend
uv run pytest tests/catalog_sync    # unit, contract, adapter and end-to-end tests
uv run pytest --cov                 # whole suite + 90% branch coverage floor
uv run ruff check . && uv run ruff format --check . && uv run pyright --warnings
cd .. && bash .github/scripts/check-tdd-order.sh origin/main HEAD
```

Expected: everything passes. No test reaches `api.tcgdex.net`: every request goes through
the fixture transport, and an unknown path fails the test.

| Scenario | Proven by |
|---|---|
| US1 populate on an empty store, exit code by status | `test_command.py` (end to end, real Postgres + fixtures) |
| US2 second run: `created = updated = 0`, only `fetched_at` moves | `test_command.py` (end to end) |
| US3 failure levels, statuses, 100-failure cap, run record lifecycle | `test_service.py` (fakes), `test_command.py` (index abort → exit 2) |
| Pocket never requested | `test_command.py` and `test_tcgdex_provider.py` (recorded request paths) |
| Retry, backoff, 404 without retry, 429 `Retry-After`, ≤ 8 in flight, user agent | `test_tcgdex_provider.py` |
| Trimming, `"None"` rarity, blank media, no variants, ignored `card.set` | `test_tcgdex_payloads.py` |
| Fake and real adapter behave alike | `test_catalog_provider_contract.py`, `test_catalog_repository_contract.py` |
| Migration matches the tables, expand-only | `tests/test_migrations.py` (`alembic check`, downgrade to base) |

## 2. Manual live run (SC-006, not in CI)

```bash
make migrate
cd backend
time uv run tcg sync catalog > run.json 2> run.log; echo "exit=$?"
```

Expected:

- It finishes in under 15 minutes, and the exit code is `0` (or `1` if TCGdex served a bad
  card).
- `run.json` is one object with `status`, and `result.counts.sets.skipped` is `22`. Cards
  fetched are about 13,900.
- `run.log` has a `sync.run.started` line, one `sync.failure` line per failure and a
  `sync.run.finished` line.
- In the database: `SELECT count(*) FROM cards;` is about 13,900, `sets` has no `tcgp` series
  set, and `sync_runs` has one closed row matching `run.json`.

Run it a second time. Every kind reports `created = 0` and `updated = 0` (unless TCGdex
changed in between), and the row counts stay the same.

## 3. Inside the production image (FR-037)

```bash
docker build -t tcg-pokedex .
docker run --rm tcg-pokedex tcg --help
docker run --rm --network host -e TCG_POKEDEX_DATABASE_URL=… tcg-pokedex tcg sync catalog
```

Expected: the usage text lists `sync`, and the run behaves as in step 2. CI's `image` job runs
the `--help` check.

## 4. Store unreachable

```bash
TCG_POKEDEX_DATABASE_URL=postgresql+psycopg://x:x@127.0.0.1:1/x uv run tcg sync catalog; echo "exit=$?"
```

Expected: one `sync.run.error` line on stderr, nothing on stdout, `exit=2`, and no request
to TCGdex.
