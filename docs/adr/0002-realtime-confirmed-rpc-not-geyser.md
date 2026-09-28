# Real-time ingestion uses confirmed RPC streams, not processed Geyser

## Context

Sub-second activity requires Geyser-class gRPC streaming ($200–500/mo: Helius LaserStream, Solana Tracker Yellowstone, QuickNode). Plain RPC WebSocket subscriptions and webhooks cost effectively nothing but add latency. Separately, acting on `processed` commitment is fastest but can be rolled back — a paper trade fired on a reorged transaction is fiction.

## Decision

`RealtimeSource` is implemented first with RPC WebSocket (`logsSubscribe` / `accountSubscribe`) plus Helius webhooks, at **`confirmed`** commitment. **`processed` is disqualified for trade triggering.** The port is designed so Yellowstone/LaserStream gRPC can replace the transport without touching domain logic.

## Consequences

- Latency assumptions (500 ms–10 s) are strategy configuration, so the same experiments run on the cheap transport; no sub-second spend is needed to answer the central question.
- If sub-second triggering is ever required, that is a new decision with its own ADR, plus explicit reorg/rollback and idempotency handling.
