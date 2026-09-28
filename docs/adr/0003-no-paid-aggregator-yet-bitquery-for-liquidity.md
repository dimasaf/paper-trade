# No paid data aggregator until the spike requires it; Bitquery is the route to historical liquidity

## Context

Phase 0 research (`docs/data-providers.md`) and cost modelling (`docs/helius-cost-model.md`) established that full decoded wallet history, current price/liquidity/market cap, and token metadata are obtainable at **$0** via Helius Free plus the free tiers of Dexscreener, GeckoTerminal, and Jupiter. Historical **pool balances** — required for a true `LiquidityAtTrade` — are sold only by Bitquery, at roughly $210–400/mo archive. Solana Tracker is cheaper and bundles holders/OHLCV/WebSocket, but its liquidity data is current-snapshot only and its PnL figures use undisclosed methodology.

## Decision

Phase 0/1 runs entirely on free tiers, behind provider ports. No aggregator is purchased until the spike demonstrates the pipeline works and the central question demonstrably requires historical liquidity. When it does, **Bitquery archive** is the route — not Solana Tracker — because only Bitquery answers the liquidity question.

## Consequences

- All external data access sits behind `WalletHistorySource`, `MarketDataSource`, and `RealtimeSource`, each accepting an as-of time and returning explicit `coverage: {from, to, complete}` metadata.
- `LiquidityAtTrade` is `UNKNOWN` wherever the free sources cannot cover it. The risk engine abstains on unknowns and never treats missing data as safe.
- Long-tail price coverage is structurally incomplete (Jupiter omits tokens untraded for ~7 days), so market data needs a documented fallback order from day one.
- Free-tier commercial-use licence terms are unresolved and must be verified before any non-personal use.
