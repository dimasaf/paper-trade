# Architecture

## Status

Proposed architecture for the full Solana Smart Wallet Discovery and Paper Trading Platform. This document incorporates the decisions in `CONTEXT.md`, the provider research, and ADR-0001 through ADR-0004.

## Architectural goal

Build a local-first modular monolith that can answer one question honestly:

> Does activity from historically profitable and realistically copyable Solana meme-coin Wallets produce an Edge after latency, slippage, price impact, liquidity, fees, failed transactions, and losses?

The architecture prioritizes point-in-time correctness, explainability, swappable data sources, and identical strategy behavior in historical replay and live operation. It does not optimize for headline backtest returns.

## System shape

The deployable system consists of:

- a Next.js web application;
- a FastAPI application containing the domain and HTTP interfaces;
- ARQ workers using the same Python domain modules as FastAPI;
- PostgreSQL as the durable source of truth;
- Redis for queues, short-lived coordination, rate limiting, recent event windows, and caches;
- documented external-data Adapters behind three provider Interfaces.

This remains a modular monolith. Modules are separated by Interfaces inside one backend codebase rather than by network calls.

```text
External Solana and market data
            |
            v
Provider Adapters
            |
            v
Token universe and normalized events
            |
            +--> Wallet discovery --> Wallet Analyzer --> Wallet Registry
            |
            +--> Realtime ingestion --> Cluster Detector --> Token Risk
                                                      |          |
                                                      +----+-----+
                                                           v
                                                     Signal Engine
                                                           |
                                                           v
                                                    Scenario Runner
                                                           |
                                                           v
                                                    Paper Portfolio
                                                           |
                                                           v
                                                       Analytics
                                                           |
                                                           v
                                                 FastAPI --> Next.js
```

## Primary deep modules

### Token Universe

The Token Universe owns which Solana mints are tracked and their lifecycle state. Its Interface accepts launch and market events and returns point-in-time Token records and lifecycle transitions.

Initial seeds come from documented events emitted by pump.fun, PumpSwap, Raydium LaunchLab, Meteora DBC, and Jupiter Studio. Configurable classifiers decide whether a mint enters the universe. No SPL mint is assumed to be a meme Token by default.

Lifecycle states are `NEW`, `ACTIVE`, `MIGRATED`, `ILLIQUID`, `DEAD`, and `SUSPICIOUS`.

### Wallet Analyzer

The Wallet Analyzer is the highest seam for wallet intelligence. Given a Wallet, an as-of time, and provider coverage, it returns:

- normalized Wallet Trades;
- reconstructed FIFO lots and holdings;
- clean and transfer-contaminated realized/unrealized PnL;
- ROI, win rate, profit factor, holding-time, concentration, and consistency metrics;
- entry-quality and meme-specific metrics;
- Copyability and Copy Decay scenarios;
- evidence-backed risk flags;
- Smart Wallet Score and breakdown;
- the recommended Registry state.

Callers do not reconstruct trades, calculate PnL, or interpret missing coverage themselves.

### Wallet Registry

The Wallet Registry owns `CANDIDATE`, `WATCHLIST`, `SMART_WALLET`, `SUSPENDED`, and `REJECTED` state. State is periodically recomputed; `SMART_WALLET` is never permanent.

The Registry records score versions, evidence, state transitions, and the as-of time used for each decision.

### Realtime Ingestion

Realtime Ingestion consumes confirmed activity from RPC WebSocket subscriptions and Helius webhooks. It normalizes activity into idempotent wallet and Token events before publishing them internally.

The RealtimeSource Interface permits a future Yellowstone/LaserStream Adapter without changes to domain modules. `processed` commitment cannot trigger a Signal or Paper Trade under ADR-0002.

### Cluster Detector

The Cluster Detector maintains configurable per-Token windows over Wallet buy/sell events. It returns clusters using Contributing-independent Wallet count rather than raw Wallet count.

Independence evidence can include common funding, inter-wallet transfers, highly synchronized activity, transaction-pattern similarity, and Token-history similarity. A relationship is evidence, not a definitive identity claim.

### Token Risk

Token Risk computes a point-in-time risk assessment from Token age, liquidity, supply and holder concentration, authorities, creator behavior, pool state, and distribution evidence.

Every field distinguishes known-safe, known-risky, and `UNKNOWN`. Missing data never becomes safe. Risk output includes reasons, warnings, evidence, coverage, and as-of time.

### Signal Engine

The Signal Engine consumes a cluster, Wallet quality, Token Risk, liquidity, entry quality, buy velocity, and market confirmation. It returns one explainable decision: `IGNORE`, `WATCH`, or `PAPER_BUY`.

Signals carry score components, reasons, warnings, source evidence, configuration version, and as-of time. Cooldowns, cluster updates, aggregation, and invalidation are part of this module rather than caller behavior.

### Scenario Runner

The Scenario Runner is the primary system seam. It consumes normalized events, a fixed strategy configuration, an execution scenario, a time range, and a clock. It returns Signals, Paper Trades, positions, portfolio state, and strategy metrics.

Historical replay and live paper operation both invoke the same downstream modules. Only the event source and clock differ.

### Paper Portfolio

The Paper Portfolio owns virtual accounts, risk limits, FIFO position lots, simulated fills, partial exits, stops, take profits, trailing stops, and portfolio accounting.

A fill uses venue-appropriate pool mathematics when sufficient point-in-time state exists. Constant-product mathematics is the first implementation for applicable pools; concentrated-liquidity and DLMM implementations arrive with their venue integrations. When pool state is unavailable, a configured fixed-slippage fallback may be used, and the fill records the fallback explicitly.

Every Paper Trade records signal time/price, execution time/price, latency, slippage, price impact, fees, failure outcome, fill model, coverage, and exit reason.

### Analytics

Analytics compares ideal entry, delayed entry, delayed plus slippage, and fully costed execution. It calculates strategy and portfolio metrics without changing strategy configuration after the evaluation window has been observed.

## External provider seams

### WalletHistorySource

Supplies decoded Wallet and Token history, balances, transfers, and transaction metadata. Helius `getTransactionsForAddress` is the initial Adapter because it is available on the free tier and is materially cheaper in credits than a signature-plus-transaction loop.

### MarketDataSource

Supplies point-in-time price, supply, liquidity, market cap, pools, holder distribution, and creator/authority facts.

Initial Adapters use free documented sources such as Jupiter, Dexscreener, GeckoTerminal, Solana RPC/DAS, and the Solana Tracker launch feed. Fallback precedence is explicit, and the chosen source is persisted with every observation.

Bitquery is the designated future Adapter for historical pool balances if the free-tier spike proves that historical `LiquidityAtTrade` is necessary and worth the cost.

### RealtimeSource

Supplies confirmed Wallet, Token, pool, and launch-program activity. Initial Adapters use standard RPC WebSocket subscriptions and Helius webhooks. Geyser-class gRPC is deferred.

### Coverage contract

Every provider response includes:

- requested as-of time or time interval;
- actual `from` and `to` coverage;
- whether coverage is complete;
- provider identity and request metadata;
- freshness and commitment level;
- explicit missing/unknown fields;
- warnings produced during normalization.

Domain modules must not infer safety or absence from incomplete coverage.

## Event and time model

All durable events include Solana signature, slot, block time, observed-at time, provider, commitment, normalization version, and an idempotency key.

The system separates:

- chain time: when Solana recorded the transaction;
- observed time: when this system learned about it;
- evaluation time: the simulation's current as-of time;
- execution time: when the Paper Trade would be submitted or filled.

Historical replay advances a deterministic clock. Any query made by a strategy carries that clock's as-of time. Future data, future score versions, future ATH, future rug status, and future liquidity cannot be read.

## Trade reconstruction and accounting

Normalized movement types are `BUY`, `SELL`, `TRANSFER_IN`, `TRANSFER_OUT`, `AIRDROP`, and `UNKNOWN`.

BUY and SELL events create and consume FIFO lots. Multiple buys, partial sells, DCA, remaining inventory, network fees, and failed transactions are first-class.

TRANSFER_IN and AIRDROP inventory receives zero cost basis for inclusive accounting and a contamination marker. The system reports:

- inclusive realized/unrealized PnL;
- clean realized/unrealized PnL excluding contaminated quantities;
- contamination evidence and quantities.

Smart Wallet Score uses clean PnL. Unknown movements never become trades by assumption.

## Persistence

PostgreSQL owns durable state. Initial table groups are:

- Token universe and time series;
- creators, holders, pools, and relationships;
- Wallets, relationships, events, trades, lots, metrics, scores, and risk flags;
- clusters, Signals, reasons, and warnings;
- Paper Accounts, positions, lots, trades, and equity observations;
- strategy configurations, immutable run manifests, metrics, and artifacts;
- provider observations, coverage, checkpoints, and ingestion errors.

High-volume observations are designed for time-based partitioning. TimescaleDB is deferred until measured query or retention pressure justifies it.

Redis contains no irreplaceable source-of-truth data. It is used for ARQ queues, locks, idempotency windows, recent clusters, Signal cooldowns, latest-price caches, rate limiting, and WebSocket session state.

## Background processing

ARQ jobs cover provider backfills, Token classification, Wallet discovery, Wallet analysis, score refresh, holder snapshots, risk refresh, replay runs, and maintenance.

Jobs are idempotent, checkpointed, retry bounded, and observable. Provider-specific rate limits are enforced centrally by Adapters rather than independently by every caller.

## Web and HTTP interfaces

FastAPI exposes read/write Interfaces for Discovery, Wallets, Tokens, Signals, Paper Trading, Analytics, and Settings. WebSocket endpoints deliver live activity, cluster, Signal, and position updates to Next.js.

Next.js remains a presentation client. It does not reproduce score, risk, accounting, Signal, or paper-execution logic.

The UI exposes reasons, warnings, data coverage, configuration versions, and poor historical periods rather than only headline scores.

## Configuration and reproducibility

Thresholds, score weights, cluster windows, execution delays, slippage scenarios, position sizes, exits, and risk limits are versioned configuration — never hardcoded domain assumptions.

Each strategy run persists an immutable manifest containing:

- code/build identity where available;
- configuration version;
- provider and coverage versions;
- historical time range and held-out range;
- random seed for simulated failures;
- execution scenarios;
- generated metrics and artifacts.

The evaluation window is fixed before inspection. Discovery uses older cohorts, while the most recent fixed 30–90-day interval is held out for evaluation.

## Observability

Structured logs and metrics cover provider/RPC latency and failures, WebSocket reconnects, lag, events received/processed/duplicated, queue latency, Wallet and Token counts, Signals, Paper Trades, coverage gaps, and end-to-end detection/execution latency.

Secrets and complete provider payloads are not logged. Every derived result retains enough source references to explain how it was produced.

## Test seams

### Scenario Runner seam

Deterministic event tapes exercise the complete historical/live strategy pipeline and return externally observable Signals, Paper Trades, portfolio state, and metrics.

### Wallet Analyzer seam

Point-in-time Wallet fixtures exercise reconstruction, FIFO accounting, contamination handling, metrics, Copyability, evidence, scores, and Registry recommendations.

### Provider contract seam

Every Adapter passes the same contract suite for as-of correctness, coverage, missing fields, ordering, normalization, retries, idempotency, and rate-limit behavior.

### Running web application seam

Playwright exercises user-visible journeys against Next.js and FastAPI. Backend behavior is tested through HTTP/WebSocket Interfaces rather than internal implementation details.

## Scale assumptions

The intended order of magnitude is:

- 10,000–100,000 Wallets analyzed historically;
- 250–1,000 Wallets in `SMART_WALLET` and tracked live;
- 1,000–10,000 active Tokens retained in the working universe;
- large historical observations retained in PostgreSQL partitions.

These are planning assumptions, not hard limits. Load tests determine when free-provider, WebSocket, worker, or storage upgrades are justified.

## Delivery phases

1. Provider research and feasibility — complete enough to start; commercial terms remain open.
2. Foundation — full local stack, migrations, modules, provider Interfaces, observability baseline.
3. Token data — launches, metadata, market observations, lifecycle, coverage.
4. Wallet discovery — historical winners, early buyers, candidates.
5. Wallet intelligence — reconstruction, accounting, metrics, risk, Copyability, score, Registry.
6. Wallet web analytics — Discovery, leaderboard, Wallet details.
7. Realtime tracking — subscriptions, normalization, live UI.
8. Cluster and Token Risk — relationships, creator/holder risk, independence.
9. Signal Engine — explanations, cooldowns, `IGNORE`/`WATCH`/`PAPER_BUY`.
10. Paper Trading — execution scenarios, portfolio, entries/exits.
11. Analytics and backtesting — deterministic replay, comparisons, ADR-0001 verdict.

Each phase must install, build, migrate, test, start, verify its HTTP/WebSocket Interfaces and UI, and fix failures before the next phase begins.
