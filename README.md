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
- Tokens: http://127.0.0.1:3000/tokens
- Token detail: http://127.0.0.1:3000/tokens/{address}
- Research Settings: http://127.0.0.1:3000/settings
- Backend health: http://127.0.0.1:8000/health
- Backend liveness: http://127.0.0.1:8000/live

Inspect logs with `make logs` and stop services with `make down`.

## Versioned research configuration

Settings exposes the active Token, Wallet, cluster, Signal, Paper Trading, risk, and execution assumptions. Edit the complete JSON document and save to create a new immutable version; previous versions remain visible in history. The HTTP interfaces are:

- `GET /research-configurations/active`
- `GET /research-configurations`
- `GET /research-configurations/{version}`
- `POST /research-configurations`

PostgreSQL seeds version 1 on a fresh installation and rejects updates or deletes to stored versions.

## Token universe

The Token universe is seeded from recorded, source-neutral launch events. A
confirmed event from a configured launch source creates one classified Token with
its address, name, symbol, creator, creation time, launch platform, and initial
lifecycle state. Classification reads the active immutable research
configuration and records per-criterion pass/fail evidence together with the
configuration `id` and `version` used. Provider identity, as-of interval,
completeness, commitment, and unknown fields are retained with the Token, and
missing facts stay explicitly `UNKNOWN`.

Registration is idempotent: replaying the identical event does not duplicate the
Token, its lifecycle transition, or its coverage. Events observed at `processed`
commitment never create or transition a Token (ADR-0002). Lifecycle transitions
are stored as evidence with an observed time rather than only a current state.

Every launch Adapter satisfies the `LaunchEventSource` interface and passes the
same deterministic provider contract suite over recorded fixtures. No network
endpoint is called by the deterministic suite. The HTTP interfaces are:

- `GET /tokens`
- `POST /tokens` with `{"event": <launch event>}`
- `GET /tokens/{address}`

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

`make test-stack` uses an isolated Docker Compose project and deletes its test volumes when complete. The real-stack browser journey registers a recorded launch event and reads it back through the Token detail page.

## Health contract

`GET /health` always returns a point-in-time document that distinguishes:

- application readiness;
- PostgreSQL query readiness;
- Redis ping readiness;
- ARQ worker heartbeat readiness.

A failed dependency produces `status: degraded` while the endpoint remains available for the Overview. Responses and request logs carry a correlation ID. Logs use an allowlist of safe fields and do not record authorization headers or connection strings.
