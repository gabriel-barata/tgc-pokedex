# Quickstart: validate tracked sets & the image cache

How to show that PTCG-013 works. Behavior: [spec.md](spec.md). Routes:
[contracts/api.md](contracts/api.md). Command: [contracts/cli.md](contracts/cli.md). Tables
and files: [data-model.md](data-model.md).

## Prerequisites

- Docker running (dev Postgres and Testcontainers).
- `cd backend && uv sync`, and a catalog in the dev database (`make migrate`, then
  `uv run tcg sync catalog`) for the manual run.

## 1. Automated checks (CI equivalent)

```bash
cd backend
uv run pytest tests/image_cache tests/sync_runs tests/catalog_sync
uv run pytest --cov
uv run ruff check . && uv run ruff format --check . && uv run pyright --warnings
cd ../frontend && pnpm generate:api && git diff --exit-code openapi.json src/api-schema.gen.ts
cd .. && bash .github/scripts/check-tdd-order.sh origin/main HEAD
```

Expected: everything passes, with no request to TCGdex (the fixture transport fails on any
unknown URL), and the regenerated API files match the committed ones.

| Scenario | Proven by |
|---|---|
| US1 track → background download → images served, no provider call while serving | `test_api_end_to_end.py` (TestClient, real Postgres, fixtures, temp image dir) |
| US1-3/4 English fallback, unavailable card | `test_domain.py` (`plan_card`), `test_service.py` (fakes) |
| US1-5 track twice: no second download | `test_api_end_to_end.py` |
| US2 untrack: later runs skip the set, images still served | `test_service.py`, `test_api_end_to_end.py` |
| US3 catch-up, pt upgrade, per-card failure → `partial`/exit 1, logos and symbols for untracked sets | `test_service.py`, `test_command.py` |
| Unusable image directory → `failed`/exit 2 | `test_command.py` |
| Both sizes or nothing; atomic writes | `test_image_store_contract.py` |
| 404 vs failure, WebP check, `/univ/` symbol retry | `test_tcgdex_image_provider.py` |
| Fake and real adapters agree | `test_*_contract.py` for each port |
| Catalog sync unchanged after the refactors | `tests/catalog_sync` |
| Migration matches the tables | `tests/test_migrations.py` |

## 2. Manual run against the dev stack (SC-001, SC-003)

```bash
make dev                                            # backend :8000, frontend :5173
curl -s -X PUT localhost:8000/api/sets/sv01/tracking | jq
# {"set_id":"sv01","tracked":true,"total_cards":258,"cached":0,"unavailable":0,"downloading":true}
watch -n5 'curl -s localhost:8000/api/sets/sv01/tracking | jq -c'
# within 10 minutes: cached 258, downloading false
curl -sI localhost:8000/api/images/cards/sv01-001/small   # 200 image/webp, Cache-Control
curl -sI localhost:8000/api/images/cards/sv01-999/small   # 404
```

Then catch up all artwork and confirm a second run downloads no pt card image:

```bash
cd backend
uv run tcg sync images | jq '.status, .result.counts'; echo "exit=$?"
uv run tcg sync images | jq '.result.counts.cards'
# second run: "downloaded": 0 for sv01's pt cards (SC-003)
curl -sI localhost:8000/api/images/sets/sv01/symbol     # 200 (fetched via the /pt/ path)
```

English fallback: track `swshp` and check that its `card_images` rows show `en` for cards such
as `swshp-SWSH032`, and that `svp` reports a non-zero `unavailable` count.

## 3. Home server (FR-016)

After deploying, run `docker compose exec app tcg sync images`, restart and update the
`app` container (`docker compose up -d --force-recreate app`), and check that
`/api/images/sets/sv01/logo` still answers `200` with no new download.
