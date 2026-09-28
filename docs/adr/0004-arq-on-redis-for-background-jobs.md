# Background jobs use ARQ on Redis

## Context

The backend is async FastAPI with Redis already present for ephemeral state. The realistic candidates were ARQ, Celery, and Dramatiq. Celery is the most battle-tested but is sync-first and heavyweight for an async modular monolith; Dramatiq is a solid middle ground requiring a separate broker story.

## Decision

Use **ARQ**, running on the Redis instance the architecture already requires. The initial repository stays a modular monolith.

## Consequences

- Job definitions are async Python, and Redis is the only additional infrastructure dependency.
- One deployment unit; no separate broker to operate.
- Revisit only if genuinely complex routing, non-Python workers, or heavy scheduled workflows appear — at which point this ADR is superseded rather than silently ignored.
