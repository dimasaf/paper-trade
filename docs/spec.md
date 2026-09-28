# Solana Smart Wallet Discovery and Paper Trading Platform

## Problem Statement

A researcher who watches Solana meme-coin Wallets cannot tell whether apparent historical profitability is genuine, repeatable, independent, or realistically copyable. Public dashboards often conflate transfers with trades, reward one lucky winner, ignore latency and liquidity, use future information in historical analysis, and report idealized prices that a follower could never receive.

The user needs a single local web application that discovers candidate Wallets from historical Token winners, reconstructs their actual trading behavior, measures consistency and Copyability, identifies coordinated activity without double-counting related Wallets, evaluates Token and creator risk, creates explainable Signals, and tests those Signals using realistic Paper Trades.

The product must answer whether an executable Edge remains after detection latency, execution latency, slippage, price impact, liquidity, fees, failed transactions, rugs, and losses. A negative result is a valid outcome. The system must not be tuned to manufacture impressive historical returns.

## Solution

Build a local-first web platform for Solana meme-coin research and Paper Trading. It will maintain a configurable Token universe, work backward from historical winners to discover early buyers, reconstruct Wallet Trades without confusing transfers and airdrops for purchases, calculate point-in-time Wallet intelligence, score Copyability, and maintain a periodically reassessed Smart Wallet Registry.

Confirmed Smart Wallet activity will be monitored in near real time. The platform will detect clusters using Contributing-independent Wallet count, assess Token, creator, holder, and liquidity risk, and issue explainable `IGNORE`, `WATCH`, or `PAPER_BUY` decisions.

A shared Scenario Runner will feed both historical replay and live activity through the same Signal and Paper Trading pipeline. Paper fills will model latency, venue liquidity, price impact, slippage, fees, and failed transactions. Strategy reports will compare idealized and executable performance and apply a pre-registered out-of-sample Edge criterion.

The application will use a Next.js frontend, FastAPI/ARQ backend, PostgreSQL, Redis, and documented provider Adapters. Phase 0/1 will use free provider tiers. No real-money execution or private key is required.

## User Stories

### Research outcome and reproducibility

1. As a researcher, I want the platform to define Edge as positive expected value after realistic execution costs, so that headline returns do not mislead me.
2. As a researcher, I want a fixed evaluation window recorded before a backtest runs, so that the result cannot be improved by moving the goalposts.
3. As a researcher, I want discovery data separated from a held-out recent evaluation period, so that I can detect selection and survivorship bias.
4. As a researcher, I want every strategy run tied to an immutable configuration and data-coverage record, so that I can reproduce its result.
5. As a researcher, I want failed Edge criteria reported honestly, so that “no Edge at this latency” is a valid conclusion.
6. As a researcher, I want ideal and executable results shown side by side, so that I can see exactly where theoretical profit disappears.
7. As a researcher, I want the best trade removable from a strategy result, so that one outlier cannot masquerade as repeatability.
8. As a researcher, I want all derived facts stamped with an as-of time, so that future information cannot leak into historical decisions.

### Token universe and lifecycle

9. As a researcher, I want documented launch-program events to seed the Token universe, so that I do not depend on undocumented frontend endpoints.
10. As a researcher, I want pump.fun and PumpSwap launches detected, so that their Tokens can enter discovery promptly.
11. As a researcher, I want Raydium LaunchLab, Meteora DBC, and Jupiter Studio launches detected, so that the universe covers major launch ecosystems.
12. As a researcher, I want configurable classification rules for whether an SPL mint is a meme Token, so that not every SPL token is assumed relevant.
13. As a researcher, I want minimum liquidity, market-cap, pool, and activity thresholds configurable, so that the universe can change without code edits.
14. As a researcher, I want Token creation time, creator, platform, pools, symbol, and name retained, so that later analysis has provenance.
15. As a researcher, I want Token states such as `NEW`, `ACTIVE`, `MIGRATED`, `ILLIQUID`, `DEAD`, and `SUSPICIOUS`, so that lifecycle changes are explicit.
16. As a researcher, I want bonding-curve migration and pool-creation events retained, so that pre- and post-migration behavior can be compared.
17. As a researcher, I want current and peak market cap and liquidity derived from time-stamped observations, so that winner discovery is auditable.
18. As a researcher, I want unavailable historical price or liquidity marked `UNKNOWN`, so that missing data is never treated as safe.

### Historical winner and Wallet discovery

19. As a researcher, I want configurable initial and peak market-cap ranges for historical winners, so that winner definitions are not hardcoded.
20. As a researcher, I want historical winner cohorts fixed before Wallet scoring, so that future success cannot leak into earlier decisions.
21. As a researcher, I want configurable entry-market-cap buckets, so that I can compare how early each Wallet enters.
22. As a researcher, I want early buyers extracted from each winner with timestamp, amount, price, market cap, liquidity, venue, and signature, so that discovery is evidence-backed.
23. As a researcher, I want time since Token creation recorded for each entry, so that ultra-early behavior can be distinguished from ordinary early entry.
24. As a researcher, I want candidate Wallets discovered automatically across many winners, so that discovery does not depend on hand-picked addresses.
25. As a researcher, I want to inspect why a candidate passed or failed each discovery filter, so that the funnel is explainable.
26. As a researcher, I want the historical discovery funnel summarized from all Wallets to Smart Wallets, so that I can see where candidates are rejected.
27. As a researcher, I want discovery to scale to tens of thousands of historical Wallets, so that results are not based on a tiny hand-selected sample.

### Trade reconstruction and accounting

28. As a researcher, I want Wallet activity normalized into BUY, SELL, TRANSFER_IN, TRANSFER_OUT, AIRDROP, and UNKNOWN, so that transfers are not mistaken for trades.
29. As a researcher, I want each Wallet Trade tied to a Token, quantity, SOL/USD amount, price, slot, time, venue, and transaction signature, so that calculations are traceable.
30. As a researcher, I want multiple buys and DCA represented as separate FIFO lots, so that cost basis is correct.
31. As a researcher, I want partial and repeated sells to consume FIFO lots correctly, so that realized PnL is correct.
32. As a researcher, I want remaining inventory marked to a point-in-time price, so that unrealized PnL is time-correct.
33. As a researcher, I want failed transactions excluded from holdings while remaining observable, so that unsuccessful attempts do not become trades.
34. As a researcher, I want transferred-in and airdropped quantities tagged as contaminated, so that their unknown acquisition cost cannot masquerade as trading skill.
35. As a researcher, I want inclusive and clean PnL shown separately, so that transfer-derived profit remains visible without affecting Smart Wallet Score.
36. As a researcher, I want UNKNOWN activity to remain unclassified until evidence resolves it, so that ambiguity is not silently converted into alpha.
37. As a researcher, I want accounting methodology documented and versioned, so that historical scores remain interpretable after changes.

### Wallet intelligence and consistency

38. As a researcher, I want realized and unrealized PnL over 24H, 7D, 30D, 90D, and all time, so that recent and long-term behavior can be compared.
39. As a researcher, I want ROI, win rate, trade count, winning/losing Tokens, average and median wins/losses, and profit factor, so that Wallet quality is multidimensional.
40. As a researcher, I want position-size and holding-time distributions, so that I can determine whether the Wallet's style is compatible with mine.
41. As a researcher, I want max drawdown and largest win/loss, so that tail risk is visible.
42. As a researcher, I want early-entry rate, entry market cap, entry liquidity, entry time, rug exposure, and migration success, so that meme-specific behavior is measurable.
43. As a researcher, I want Token creation-to-entry latency measured, so that repeated ultra-fast entries can be investigated.
44. As a researcher, I want top-one, top-three, and top-five profit concentration, so that one lucky Token cannot dominate the score.
45. As a researcher, I want profitable days, weeks, and months counted, so that consistency is measured across time.
46. As a researcher, I want descriptive Wallet styles such as EARLY_BUYER, SCALPER, or MOMENTUM_TRADER, so that behavior can be understood without assuming a style is good.
47. As a researcher, I want every suspicious behavior flag backed by evidence, so that labels are reviewable rather than accusatory.
48. As a researcher, I want funding-source, Wallet-age, related-Wallet, creator-proximity, and transfer-pattern evidence, so that insider-like or bot-like behavior can reduce confidence.
49. As a researcher, I want uncertainty preserved in Wallet evidence, so that the system never claims real-world identity or wrongdoing.

### Copyability and Wallet scoring

50. As a researcher, I want follower outcomes simulated at 500 ms, 1 s, 2 s, 3 s, 5 s, and 10 s delays, so that latency sensitivity is measurable.
51. As a researcher, I want leader ROI compared with follower ROI at each delay, so that Copy Decay is explicit.
52. As a researcher, I want follower sizes such as 0.1, 0.25, 0.5, 1, and 2 SOL configurable, so that liquidity-aware Copyability can be evaluated.
53. As a researcher, I want venue-appropriate pool mathematics used when state is available, so that price impact is not replaced with a guess.
54. As a researcher, I want fallback slippage assumptions recorded when pool state is unavailable, so that low-confidence fills are distinguishable.
55. As a researcher, I want a 0–100 Smart Wallet Score with configurable weights, so that scoring can evolve without code changes.
56. As a researcher, I want profitability, consistency, Copyability, risk quality, entry quality, and history quality shown separately, so that the total score is explainable.
57. As a researcher, I want Smart Wallet Score to use clean PnL rather than contaminated PnL, so that transferred Tokens do not inflate status.
58. As a researcher, I want Wallet scores recalculated periodically, so that deteriorating Wallets can be suspended or rejected.
59. As a researcher, I want every Registry transition stored with reasons and an as-of time, so that the Smart Wallet Registry is auditable.
60. As a researcher, I want Copyability visualized on Wallet detail pages, so that I can see where follower returns collapse.

### Realtime tracking and clusters

61. As a researcher, I want `SMART_WALLET` addresses monitored at confirmed commitment, so that live activity is fast enough without acting on rollback-prone events.
62. As a researcher, I want live activity normalized into the same event forms as historical activity, so that downstream logic is shared.
63. As a researcher, I want duplicate and replayed events handled idempotently, so that reconnects cannot create false trades or Signals.
64. As a researcher, I want Wallet buys, sells, transfers in, and transfers out streamed to the web application, so that current behavior is visible.
65. As a researcher, I want multiple Smart Wallet buys aggregated into a Token cluster within a configurable time window, so that one Wallet does not trigger a Paper Trade alone.
66. As a researcher, I want cluster Wallet count, average/weighted score, total SOL, first/last buy, and velocity, so that cluster strength is measurable.
67. As a researcher, I want related Wallets collapsed into a Contributing-independent Wallet count, so that one entity cannot appear as several confirmations.
68. As a researcher, I want funding, transfers, synchronization, transaction patterns, and shared Token history used as relationship evidence, so that cluster independence is explainable.
69. As a researcher, I want cluster updates and invalidations emitted as activity changes, so that a stale cluster does not remain actionable.
70. As a researcher, I want realtime transport replaceable with Geyser-class streaming later, so that sub-second experiments do not require rewriting domain logic.

### Token, creator, holder, and liquidity risk

71. As a researcher, I want a point-in-time Token Risk score with reasons and warnings, so that risky Tokens can be filtered before a Paper Trade.
72. As a researcher, I want Token age, market cap, liquidity, holder count, authorities, concentration, and distribution assessed, so that common rug risks are visible.
73. As a researcher, I want mint and freeze authority states shown, so that centralized controls are explicit.
74. As a researcher, I want pool and system addresses classified separately from ordinary holders, so that concentration metrics are not misleading.
75. As a researcher, I want creator launch history, dead/rug-like outcomes, holdings, sells, transfers, and funding relationships assessed, so that repeated creator behavior affects risk.
76. As a researcher, I want creator and related-cluster holdings shown separately, so that hidden concentration can be investigated.
77. As a researcher, I want major liquidity changes and collapse detected, so that open Paper Positions can react to vanishing exit capacity.
78. As a researcher, I want unavailable holder, creator, or liquidity facts reported as `UNKNOWN`, so that missing coverage never improves a risk score.
79. As a researcher, I want all risk evidence linked to provider coverage and time, so that historical decisions can be reproduced.

### Signals

80. As a researcher, I want a 0–100 Signal score with configurable component weights, so that decision policy is explicit.
81. As a researcher, I want Wallet quality, Contributing-independent Wallet count, Token Risk, liquidity, entry quality, buy velocity, and market confirmation included, so that Signals are not based on one Wallet.
82. As a researcher, I want each Signal to return `IGNORE`, `WATCH`, or `PAPER_BUY`, so that downstream behavior is deterministic.
83. As a researcher, I want reasons and warnings included with every Signal, so that I understand both supporting and contrary evidence.
84. As a researcher, I want configuration, score versions, source evidence, and as-of time attached to each Signal, so that it can be reproduced.
85. As a researcher, I want Token cooldowns and Signal aggregation, so that repeated events do not create duplicate Paper Positions.
86. As a researcher, I want a Signal invalidated when its cluster, risk, or market evidence changes materially, so that stale recommendations are not acted upon.
87. As a researcher, I want WATCH Signals updated as new evidence arrives, so that uncertain opportunities can mature or disappear.

### Paper Trading and position management

88. As a researcher, I want configurable virtual accounts with no private key, so that no real money can be traded.
89. As a researcher, I want configurable starting balance, position size, maximum position, and maximum simultaneous positions, so that portfolio risk is realistic.
90. As a researcher, I want both percentage and SOL-denominated sizing, so that execution scenarios can reflect different capital bases.
91. As a researcher, I want execution delayed from Signal time by the configured latency, so that the Signal price is never automatically used as the fill price.
92. As a researcher, I want slippage, price impact, venue fees, network fees, priority-fee assumptions, and failed-transaction probability included, so that fills reflect execution costs.
93. As a researcher, I want every fill to identify its pool model or fixed-slippage fallback, so that fill confidence is visible.
94. As a researcher, I want illiquid positions rejected or size-limited, so that the portfolio never assumes infinite liquidity.
95. As a researcher, I want positions to retain Signal and execution prices/times, quantities, costs, highs, current marks, PnL, and exit reason, so that their lifecycle is auditable.
96. As a researcher, I want stop-loss and take-profit exits configurable, so that simple strategies can be compared.
97. As a researcher, I want partial take-profit and trailing-stop rules configurable, so that staged exits can be studied.
98. As a researcher, I want Smart Wallet sell pressure to reduce or close a position, so that leader behavior can inform exits.
99. As a researcher, I want creator sells, liquidity collapse, holder-concentration changes, volume collapse, and maximum holding time available as exit conditions, so that meme-specific risks can be tested.
100. As a researcher, I want each exit rule independently selectable and backtestable, so that strategy comparisons remain interpretable.
101. As a researcher, I want failed entries and exits retained as outcomes, so that transaction failure does not disappear from results.

### Backtesting and analytics

102. As a researcher, I want historical events and live events to pass through the same Scenario Runner, so that backtests do not use privileged strategy logic.
103. As a researcher, I want deterministic replay with a fixed clock and random seed, so that tests and strategy runs are repeatable.
104. As a researcher, I want future price, ATH, liquidity, rug status, and Wallet score unavailable during replay, so that lookahead bias is prevented.
105. As a researcher, I want Wallet scores versioned by as-of time, so that a strategy cannot use reputation earned after a Signal.
106. As a researcher, I want trades, win rate, PnL, ROI, average win/loss, profit factor, expectancy, drawdown, holding time, slippage, price impact, and latency calculated, so that strategy behavior is fully characterized.
107. As a researcher, I want ideal, delayed, delayed-plus-slippage, and fully costed results compared, so that execution decay is obvious.
108. As a researcher, I want multiple immutable strategy configurations compared side by side, so that trade-offs are visible.
109. As a researcher, I want strategy ranking to consider robustness and drawdown rather than only ROI, so that overfit configurations are not automatically selected.
110. As a researcher, I want the ADR-0001 pass/fail verdict included in each held-out evaluation report, so that the central question receives an explicit answer.

### Web application

111. As a user, I want an Overview showing tracked Smart Wallets, candidates, active Signals, paper equity, PnL, win rate, and drawdown, so that I can assess system health quickly.
112. As a user, I want a live Smart Wallet activity feed with cluster events, so that coordinated activity is visible as it happens.
113. As a user, I want a Discovery page with the complete Wallet funnel, so that I can inspect pass/fail reasons.
114. As a user, I want a sortable Smart Wallet leaderboard with recent and long-term metrics, so that poor periods are not hidden.
115. As a user, I want Wallet detail pages with score breakdown, PnL, trades, entry distribution, Copyability, risk flags, funding, and relationships, so that each Registry decision is explainable.
116. As a user, I want Token detail pages with price, market cap, liquidity, age, creator, holders, Smart Wallet activity, and risk evidence, so that Token quality is reviewable.
117. As a user, I want Signal pages showing score, decision, cluster, liquidity, risks, reasons, warnings, and coverage, so that no Signal is a black box.
118. As a user, I want a Paper Trading page with account equity, realized/unrealized PnL, positions, exits, and sell pressure, so that simulated execution is visible.
119. As a user, I want an Analytics page comparing strategy configurations and execution scenarios, so that robustness can be evaluated.
120. As a user, I want a Settings page for strategy, scoring, execution, risk, and provider-safe configuration, so that assumptions can change without code edits.
121. As a user, I want live pages updated over WebSocket, so that I do not need to poll manually.
122. As a user, I want warnings and unknown coverage shown prominently, so that a polished score cannot conceal weak data.

### Operations and observability

123. As an operator, I want the entire stack to start locally through Docker Compose, so that the application is reproducible on one machine.
124. As an operator, I want migrations to create and evolve the durable schema, so that environment setup is deterministic.
125. As an operator, I want background jobs idempotent, checkpointed, and retry-bounded, so that provider failures do not corrupt state.
126. As an operator, I want provider rate limiting centralized, so that workers cannot accidentally exhaust quotas independently.
127. As an operator, I want RPC/provider latency, failures, reconnects, queue lag, duplicates, processing latency, and coverage gaps measured, so that data quality problems are observable.
128. As an operator, I want structured logs without secrets, so that failures can be investigated safely.
129. As an operator, I want free-tier usage and credit consumption visible, so that an experiment does not unexpectedly require a paid plan.
130. As an operator, I want each phase installed, built, tested, started, and manually verified before the next begins, so that the platform never advances while broken.

## Implementation Decisions

### Product and delivery

- Build the full platform in ordered phases as a local-first, single-user research application.
- Keep real-money trading, private keys, and transaction submission out of the product.
- Build the web application from the beginning rather than treating the system as a notebook-only research project.
- Treat a negative research verdict as a successful product outcome.
- Use the glossary terms from `CONTEXT.md`; Smart Wallet is an operational Registry state, not an identity or skill claim.

### System architecture

- Use a modular monolith: Next.js frontend, FastAPI backend, ARQ workers, PostgreSQL, and Redis.
- Keep domain behavior in Python modules shared by FastAPI and ARQ. The frontend does not duplicate scoring, risk, accounting, or execution logic.
- PostgreSQL is the durable source of truth. Redis is restricted to queues, caches, locks, rate limiting, cooldowns, recent windows, and connection state.
- Design time-series tables for native PostgreSQL partitioning. Do not require TimescaleDB initially.
- Keep one primary system seam, Scenario Runner, with Wallet Analyzer, provider contracts, and the running web application as supporting seams.

### Provider and data policy

- Begin at $0/month using Helius Free, documented Solana RPC/DAS, Jupiter, Dexscreener, GeckoTerminal, and a free launch feed where appropriate.
- Use Helius `getTransactionsForAddress` for decoded historical backfill. Do not implement the more expensive and incomplete signature-plus-transaction loop as the default.
- Do not buy Bitquery, Solana Tracker Pro, or a Geyser stream before the free-tier spike demonstrates a need.
- If point-in-time historical pool balances become necessary, Bitquery archive is the selected route under ADR-0003.
- Hide providers behind `WalletHistorySource`, `MarketDataSource`, and `RealtimeSource` Interfaces.
- Require every provider result to declare provider, as-of interval, completeness, freshness, commitment, and unknown fields.
- Persist source identity for observations and derived facts. Fallback behavior must be explicit and observable.
- Use only official/documented APIs and on-chain programs. Do not rely on undocumented GMGN or pump.fun frontend endpoints.
- Verify free-tier commercial-use terms before any commercial distribution.

### Token universe

- Seed from documented launch-program events for pump.fun, PumpSwap, Raydium LaunchLab, Meteora DBC, and Jupiter Studio.
- Classify Tokens using versioned configuration, including launch source, pool existence, liquidity, market cap, and activity.
- Store lifecycle transitions rather than only current status.
- Derive peak market cap and peak liquidity from time-stamped observations; they are not trusted as vendor-provided truth.
- Keep pool/system addresses distinguishable from holders and creators.

### Point-in-time and event model

- Use one normalized event model for historical replay and live operation.
- Separate chain time, observed time, evaluation time, and simulated execution time.
- Trigger Signals only from `confirmed` data. `processed` commitment is disqualified under ADR-0002.
- Give every event an idempotency key and retain signature, slot, provider, commitment, and normalization version.
- Inject a deterministic clock into historical replay. Every strategy lookup is constrained by its as-of time.
- Store score/configuration versions and event-source coverage with every decision.

### Wallet reconstruction and accounting

- Normalize Wallet activity as BUY, SELL, TRANSFER_IN, TRANSFER_OUT, AIRDROP, or UNKNOWN.
- Use FIFO lots for buys, sells, partial exits, and remaining holdings.
- Calculate realized and unrealized PnL from point-in-time prices and include applicable fees.
- Assign transferred-in/airdropped quantities zero cost basis for inclusive accounting, mark them contaminated, and also produce clean PnL excluding them.
- Use clean PnL for Smart Wallet Score. Preserve inclusive PnL and contamination evidence for review.
- Never promote UNKNOWN movements to trades without evidence.

### Wallet intelligence and Registry

- Calculate all general and meme-specific metrics requested in the starter, including concentration, consistency, timing, liquidity, rug exposure, and migration outcomes.
- Store evidence for every risk flag and behavioral classification.
- Treat creator/funding proximity as evidence, never proof of identity or wrongdoing.
- Make score weights versioned configuration. Store every score component and explanation.
- Recalculate Registry state periodically and retain state-transition history.
- Plan for 10,000–100,000 Wallets in historical analysis and 250–1,000 live Smart Wallets.

### Copyability

- Simulate multiple delays and follower sizes as versioned scenarios.
- Compare leader and follower ROI at each delay to calculate Copy Decay.
- Use point-in-time liquidity and venue-appropriate pool mathematics where available.
- Begin with constant-product mathematics for applicable pools; add concentrated-liquidity/DLMM implementations with their venue integrations.
- Permit a fixed-slippage fallback only when pool state is unavailable, record its use, and expose it in reports.

### Realtime and clusters

- Begin with standard RPC WebSocket subscriptions plus Helius webhooks at `confirmed` commitment.
- Keep RealtimeSource replaceable by Yellowstone/LaserStream later.
- Normalize realtime events before domain processing and handle reconnect/replay idempotently.
- Count Contributing-independent Wallets rather than raw Wallets in clusters.
- Store relationship evidence and confidence. Do not make definitive control/identity claims.
- Make cluster windows, minimum counts, weighting, cooldowns, updates, and invalidation configurable.

### Token Risk and Signals

- Represent unknown risk facts explicitly. Missing data can never lower risk by default.
- Score Token, creator, holder, authority, distribution, relationship, liquidity, and lifecycle evidence point-in-time.
- Produce only `IGNORE`, `WATCH`, or `PAPER_BUY` Signal decisions.
- Include score components, reasons, warnings, evidence, coverage, configuration version, and as-of time.
- Apply aggregation and cooldown at the Signal module rather than in the UI or job caller.

### Paper execution and positions

- Use virtual accounts only; never require or accept a private key.
- Separate Signal time/price from execution time/price.
- Include latency, slippage, price impact, venue fees, network/priority fees, and deterministic failed-transaction simulation.
- Use venue pool mathematics when available and an explicitly marked fallback otherwise.
- Enforce configurable position sizing, liquidity limits, portfolio exposure, and maximum open positions.
- Support fixed stops/take profits, partial take profits, trailing stops, Smart Wallet exits, creator sells, liquidity collapse, concentration changes, volume collapse, and maximum holding time.
- Make exit rules independently selectable and backtestable.

### Backtesting and research verdict

- Run historical and live events through the same Scenario Runner and downstream modules.
- Persist immutable run manifests and deterministic random seeds.
- Perform discovery/scoring on older Token cohorts and hold out a fixed recent 30–90-day period for evaluation.
- Finalize exact date boundaries before viewing evaluation outcomes.
- Apply ADR-0001 without post-hoc re-tuning: positive fully costed expectancy, positive pessimistic scenario, held-out success, profit factor above 1.2 over at least 100 trades, and success after removing the best trade.
- Always compare ideal, delayed, delayed-plus-slippage, and fully costed results.
- Rank robustness, drawdown, concentration, and coverage alongside ROI.

### HTTP and user interface

- Expose Discovery, Wallet, Token, Signal, Paper Trading, Analytics, Settings, and health/observability data through FastAPI.
- Use WebSocket updates for live activity, cluster changes, Signals, and position changes.
- Implement Overview, Discovery, Smart Wallets, Live Activity, Signals, Tokens, Paper Trading, Analytics, and Settings navigation.
- Show reasons, warnings, score components, coverage gaps, source provenance, and poor historical periods.
- Keep configuration edits versioned so existing runs retain their original assumptions.

### Delivery phases

1. Finish provider feasibility and unresolved commercial/retention checks.
2. Establish the full local stack, migrations, module shells, provider Interfaces, and observability baseline.
3. Build Token launch discovery, metadata, market observations, lifecycle, and historical snapshots.
4. Build historical winner, early-buyer, and candidate-Wallet discovery.
5. Build Wallet reconstruction, accounting, intelligence, Copyability, scoring, and Registry.
6. Build Discovery, leaderboard, and Wallet detail experiences.
7. Build confirmed realtime tracking and live activity.
8. Build relationships, clusters, Token/creator/holder risk, and independence analysis.
9. Build explainable Signal decisions and cooldown/update behavior.
10. Build Paper Accounts, execution simulation, positions, and exits.
11. Build replay, scenario comparison, analytics, and the ADR-0001 verdict.

Every phase must install, migrate, compile/build, run deterministic tests, start services, verify HTTP/WebSocket behavior, verify the web journey, and fix failures before proceeding.

## Testing Decisions

### Testing philosophy

- Test externally observable behavior through module Interfaces, HTTP/WebSocket Interfaces, and browser journeys rather than testing private implementation details.
- Prefer the highest seam that produces a useful failure. The Scenario Runner is the primary behavior seam.
- Use deterministic fixtures, clocks, provider fakes, and random seeds. Tests must never depend on live market outcomes.
- Test both successful results and explicit uncertainty/coverage behavior.
- No prior test patterns exist because the repository is greenfield.

### Scenario Runner tests

- Replay the same normalized event tape through historical and live event sources and require equivalent Signals and Paper Trades.
- Verify the strategy cannot access prices, liquidity, rug outcomes, Wallet scores, or holder data newer than the evaluation clock.
- Compare ideal, latency-only, latency-plus-slippage, and fully costed scenarios.
- Verify deterministic failed-transaction simulation.
- Exercise entries, duplicate cooldowns, cluster updates, invalidations, exits, portfolio limits, and final metrics.
- Verify the ADR-0001 verdict, including held-out period, minimum trade count, profit factor, pessimistic scenario, and best-trade removal.

### Wallet Analyzer tests

- Reconstruct one buy/one sell, multiple buys, DCA, partial sells, multiple sells, remaining holdings, and fee-adjusted lots.
- Distinguish BUY/SELL from TRANSFER_IN/TRANSFER_OUT/AIRDROP/UNKNOWN.
- Verify inclusive versus clean PnL for contaminated holdings.
- Verify realized/unrealized PnL, ROI, win rate, profit factor, drawdown, holding time, and concentration metrics.
- Verify Copyability across delays and sizes, including missing-liquidity fallback.
- Verify evidence-backed risk flags, score components, and Registry recommendation.
- Verify point-in-time scores do not use later Wallet performance.

### Provider contract tests

- Run every Adapter against a shared suite for ordering, pagination, deduplication, idempotency, as-of behavior, commitment, explicit missing values, and coverage metadata.
- Use recorded/canonical provider responses rather than live-provider calls in the main test suite.
- Keep optional smoke tests for authenticated provider sandboxes separate from deterministic CI.
- Verify rate-limit handling, bounded retry/backoff, checkpointing, and resume behavior.
- Verify provider omission does not become a safe/default value.

### Domain module tests

- Token Universe: classification, launch deduplication, migrations, lifecycle transitions, and snapshot-derived peaks.
- Cluster Detector: windows, weighted scores, buy velocity, relationships, independence collapse, updates, and invalidation.
- Token Risk: authority, creator, holder, liquidity, concentration, and `UNKNOWN` handling.
- Signal Engine: score weighting, explanations, warnings, cooldown, WATCH updates, and decision thresholds.
- Paper Portfolio: sizing, liquidity constraints, fees, fills, failures, partial exits, stops, trailing stops, portfolio equity, and drawdown.
- Analytics: strategy comparisons, best-trade removal, profitable periods, concentration, and reproducible run manifests.

### HTTP and browser tests

- Test FastAPI behavior through HTTP/WebSocket Interfaces, including validation, pagination, filtering, configuration versioning, and error semantics.
- Run Playwright against the complete local stack.
- Cover Overview, Discovery funnel, Wallet leaderboard/detail, Token detail, Signal explanation, Paper Position lifecycle, Analytics comparison, and Settings changes.
- Verify unknown coverage and warnings are visible rather than hidden.
- Verify live WebSocket updates do not duplicate events after reconnect.

### Non-functional tests

- Load-test historical throughput at the stated 10,000–100,000 Wallet planning scale using synthetic/recorded data.
- Load-test confirmed WebSocket tracking for 250–1,000 Smart Wallets.
- Measure provider-credit consumption and ensure the Phase 0/1 workload stays within the configured free-tier budget.
- Test recovery from PostgreSQL/Redis/provider interruption without duplicate trades or Signals.
- Verify structured logs contain no secrets.

## Out of Scope

- Real-money trading, transaction submission, private-key custody, wallet signing, or automated on-chain execution.
- Multi-user accounts, authentication, authorization, billing, or tenancy.
- Cloud production deployment, high availability, or multi-region operation during the initial build.
- Mobile-native applications.
- Microservices or independent network deployment for internal modules.
- Undocumented GMGN or pump.fun frontend endpoints and any bypass of provider restrictions.
- Definitive claims that Wallets share a human owner, are insiders, bots, or malicious.
- Automatic strategy optimization for maximum historical ROI.
- Black-box ML scoring that cannot explain its evidence and point-in-time inputs.
- Purchasing a paid aggregator or Geyser stream before measured free-tier limits justify it.
- Tax reporting, regulatory reporting, or brokerage accounting.
- Copying vendor PnL or risk values as ground truth without reconstructing or qualifying their methodology.

## Further Notes

- Domain vocabulary is defined in `CONTEXT.md`.
- The pre-registered research verdict is recorded in ADR-0001.
- Realtime commitment and transport are recorded in ADR-0002.
- Provider spending and Bitquery's role are recorded in ADR-0003.
- ARQ is recorded in ADR-0004.
- Current provider research is in `docs/data-providers.md`; free-tier arithmetic is in `docs/helius-cost-model.md`; system structure is in `docs/architecture.md`.
- Historical liquidity remains the main data gap. Before paying for Bitquery, validate the free pipeline on a small Token sample and measure how often missing liquidity changes the verdict.
- Helius Free commercial-use terms, Solana Tracker retention/licensing, and GeckoTerminal OHLCV depth remain external facts to verify before commercial use.
- Exact discovery and held-out calendar dates must be frozen before the first official evaluation run.
- The specification is published as [GitHub issue #1](https://github.com/dimasaf/paper-trade/issues/1), labelled `ready-for-agent`.
- Its 29 dependency-linked tracer-bullet tickets are published as issues [#2–#30](https://github.com/dimasaf/paper-trade/issues), each labelled `ready-for-agent`.
