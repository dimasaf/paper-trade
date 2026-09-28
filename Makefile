.PHONY: up down logs migrate test-api test-web test-e2e test-stack test

up:
	docker compose up --build --detach --wait

down:
	docker compose down

logs:
	docker compose logs --follow

migrate:
	docker compose run --rm migrate

test-api:
	.venv/bin/ruff check apps/api
	.venv/bin/mypy apps/api/src
	.venv/bin/pytest apps/api/tests

test-web:
	pnpm typecheck
	pnpm lint
	pnpm format:check
	pnpm build

test-e2e:
	pnpm e2e

test-stack:
	./scripts/test-stack.sh

test: test-api test-web test-e2e test-stack
