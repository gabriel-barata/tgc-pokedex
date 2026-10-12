# Quickstart: validating ownership

## Automated

From `backend/` (Docker running):

```bash
uv run pytest tests/routes/test_cards.py tests/routes/test_sets.py
uv run pytest --cov
uv run ruff check . && uv run ruff format --check . && uv run pyright --warnings
```

From `frontend/`, after any schema change:

```bash
pnpm generate:api && git diff --exit-code openapi.json src/api-schema.gen.ts
pnpm typecheck && pnpm test
```

What the suites prove: the rules tables in [data-model.md](data-model.md) (SC-002), the write
and read paths and rejections in [contracts/api.md](contracts/api.md), ten concurrent
increments ending at 10 (SC-004), and a second owner's rows never read, counted or changed
(SC-003).

## Manual, against the dev stack

From the repo root: `make migrate`, then `uv run tcg sync catalog` in `backend/` if the
database has no catalog yet, and start the backend (`make dev` or the uvicorn command in
`CLAUDE.md`). Pick a card with Normal and Reverse, e.g. `sv01-001`.

```bash
API=http://127.0.0.1:8000/api
curl -s -X POST $API/cards/sv01-001/ownership/normal/increment | jq
# owned true, wanted_version_missing true
curl -s -X PUT $API/cards/sv01-001/ownership/reverse -H 'content-type: application/json' -d '{"quantity": 1}' | jq
# wanted_version_missing false
curl -s $API/sets/sv01/ownership | jq '.completion, (.cards[] | select(.card_id=="sv01-001"))'
# completion.owned 1, so_normal 0
curl -s $API/sets | jq '.[].sets[] | select(.id=="sv01") | .completion'
# same completion as above
curl -s -o /dev/null -w '%{http_code}\n' -X PUT $API/cards/sv01-001/ownership/normal -H 'content-type: application/json' -d '{"quantity": 1000}'
# 422
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/cards/nope/ownership/normal/increment
# 404
```

Restart the backend and repeat the set read: the quantities are unchanged (SC-001). Time the
two reads with `curl -w '%{time_total}\n'`; both should be well under a second (SC-005).

## Docs

`docs/design.md` decisions 13 and 14 and "Open items" state the agreed rule, with a
2026-10-12 (PTCG-017) revision-history entry (FR-016).
