# Paper Trade

A local-first Solana Smart Wallet discovery and Paper Trading research platform. The initial workspace proves that the web application, backend, PostgreSQL, Redis, and ARQ worker can communicate before domain features are added.

## Requirements

- Docker with Docker Compose
- Node.js 24+ with pnpm 10+
- Python 3.9+ for local backend checks

No wallet, private key, or authentication is required.

## Start the complete workspace

```bash
make up
```

This builds the applications, waits for PostgreSQL and Redis, applies Alembic migrations, starts FastAPI and the ARQ worker, and waits for the Next.js application.

Open:

- Overview: http://127.0.0.1:3000
- Backend health: http://127.0.0.1:8000/health
- Backend liveness: http://127.0.0.1:8000/live

Inspect logs with `make logs` and stop services with `make down`.

## Migrations

Migrations run automatically during startup. Running them again is safe:

```bash
make migrate
make migrate
```

## Local test dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -e 'apps/api[test]'
pnpm install
pnpm exec playwright install chromium
```

## Test commands

```bash
make test-api     # FastAPI health behavior
make test-web     # TypeScript, ESLint, and formatting
make test-e2e     # Deterministic browser behavior with a recorded health response
make test-stack   # Fresh Docker stack, repeated migrations, real browser smoke journey
make test         # Everything above
```

`make test-stack` uses an isolated Docker Compose project and deletes its test volumes when complete.

## Health contract

`GET /health` always returns a point-in-time document that distinguishes:

- application readiness;
- PostgreSQL query readiness;
- Redis ping readiness;
- ARQ worker heartbeat readiness.

A failed dependency produces `status: degraded` while the endpoint remains available for the Overview. Responses and request logs carry a correlation ID. Logs use an allowlist of safe fields and do not record authorization headers or connection strings.
