#!/usr/bin/env bash
set -euo pipefail

project_name="paper-trade-test"
export POSTGRES_PORT="${POSTGRES_PORT:-55432}"
export REDIS_PORT="${REDIS_PORT:-56379}"
export API_PORT="${API_PORT:-58000}"
export WEB_PORT="${WEB_PORT:-53000}"
export NEXT_PUBLIC_API_URL="http://127.0.0.1:${API_PORT}"
export PAPER_TRADE_WEB_ORIGIN="http://127.0.0.1:${WEB_PORT}"
compose=(docker compose -p "$project_name")

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup
"${compose[@]}" up --build --detach --wait

# Alembic upgrade must be safe when the schema is already current.
"${compose[@]}" run --rm migrate
"${compose[@]}" run --rm migrate

curl --fail --silent "http://127.0.0.1:${API_PORT}/health" >/tmp/paper-trade-stack-health.json
STACK_E2E=1 \
  PLAYWRIGHT_EXTERNAL_SERVER=1 \
  PLAYWRIGHT_BASE_URL="http://127.0.0.1:${WEB_PORT}" \
  pnpm exec playwright test tests/e2e/stack.spec.ts tests/e2e/wallets.spec.ts
