.PHONY: db migrate dev test

COMPOSE = docker compose -f compose.dev.yml

db:
	$(COMPOSE) up -d --wait

migrate: db
	cd backend && uv run python -m tcg_pokedex.migrations

dev: migrate
	trap 'kill 0' INT TERM; \
	(cd backend && uv run uvicorn tcg_pokedex.app:create_app --factory --reload) & \
	(cd frontend && pnpm dev) & \
	wait

test:
	cd backend && uv run pytest --cov
	cd frontend && pnpm test
