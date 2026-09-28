# Solana Meme Coin Smart Wallet Discovery & Paper Trading Platform

You are a senior full-stack engineer, Solana blockchain engineer, quantitative developer, and data engineer.

Build a production-oriented **web-based Solana Meme Coin Smart Wallet Discovery, Tracking, Signal Generation, and Paper Trading Platform**.

The platform should discover consistently profitable and realistically copyable wallets trading Solana meme coins, monitor their activity, detect coordinated or clustered smart-wallet activity, evaluate token risk, generate explainable trading signals, and validate those signals through realistic paper trading.

The initial system must NOT execute real-money trades.

The primary research question is:

> Can activity from historically profitable and realistically copyable Solana meme-coin wallets produce a repeatable trading edge after accounting for latency, slippage, liquidity, fees, price impact, rugs, failed transactions, and other real-world execution conditions?

Do not optimize the system to produce impressive historical returns.

Optimize it to determine whether an actual executable edge exists.

---

# 1. PRODUCT SCOPE

The platform is specifically designed for:

**Solana meme coins.**

Initially prioritize meme-token activity occurring through major Solana token-launch and DEX ecosystems such as:

- Pump.fun / PumpSwap
- Raydium
- Meteora
- Jupiter-routed swaps

However:

- Research current protocols before implementing integrations.
- Use official/documented APIs and on-chain program data where possible.
- Never invent endpoints.
- Never bypass API restrictions.
- Do not rely on undocumented GMGN endpoints.

GMGN may be used as a reference for useful analytics concepts, but the application must own its wallet discovery, scoring, signal, and paper-trading logic.

---

# 2. CORE PRODUCT FLOW

The complete system should eventually support:

```text
SOLANA BLOCKCHAIN DATA
        ↓
MEME TOKEN DISCOVERY
        ↓
HISTORICAL WINNER ANALYSIS
        ↓
EARLY BUYER EXTRACTION
        ↓
WALLET DISCOVERY
        ↓
WALLET TRADE RECONSTRUCTION
        ↓
WALLET INTELLIGENCE
        ↓
SMART WALLET SCORE
        ↓
SMART WALLET REGISTRY
        ↓
REAL-TIME WALLET TRACKER
        ↓
CLUSTER DETECTION
        ↓
TOKEN / DEV / LIQUIDITY RISK
        ↓
SIGNAL ENGINE
        ↓
PAPER TRADE ENGINE
        ↓
POSITION MONITOR
        ↓
STRATEGY ANALYTICS
```

---

# 3. TECHNOLOGY STACK

Choose technologies based on engineering suitability, not personal preference.

Recommended starting architecture:

## Frontend

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- Lightweight Charts or another suitable financial charting library

## Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

## Background Processing

Use an appropriate Python background-job/event-processing solution.

Candidates may include:

- ARQ
- Celery
- Dramatiq

Research the tradeoffs before selecting one.

## Storage

- PostgreSQL
- Redis

## Realtime

- WebSockets
- Solana WebSocket/RPC subscriptions where appropriate

## Infrastructure

- Docker
- Docker Compose

## Testing

- pytest
- Playwright

Start as a **modular monolith**.

Do NOT prematurely split everything into microservices.

The initial repository can approximately follow:

```text
/apps
    /web
    /api

/workers

/packages
    /domain
    /blockchain
    /analytics

/infrastructure

/docs
```

Adjust if another structure is demonstrably cleaner.

---

# 4. DATA PROVIDER RESEARCH — DO THIS FIRST

Before implementing blockchain ingestion, research currently available Solana data providers.

We need reliable access to:

```text
Historical wallet transactions
Decoded swaps
Token creation events
Token metadata
Token creator information

Historical token prices
Current token prices

Historical liquidity
Current liquidity

Market capitalization

Token holders
Holder distribution

DEX trades

Wallet balances

Transaction timestamps

Real-time wallet activity
```

Compare suitable current providers and/or direct Solana RPC access.

Evaluate:

```text
API capability
WebSocket capability
Historical depth
Latency
Rate limits
Pricing
Reliability
Commercial/programmatic usage
Decoded transaction quality
```

Prefer official and documented access.

Create:

```text
docs/data-providers.md
```

Explain the selected provider(s) and tradeoffs.

All providers MUST be hidden behind interfaces.

Example conceptually:

```python
class BlockchainProvider:
    ...

class TransactionProvider:
    ...

class MarketDataProvider:
    ...

class TokenMetadataProvider:
    ...

class TokenRiskDataProvider:
    ...
```

Business logic must not depend directly on one provider.

---

# 5. MEME TOKEN UNIVERSE

We need a continuously maintained universe of Solana meme tokens.

Store:

```text
token address
symbol
name

creator

creation timestamp
creation platform

current market cap
peak market cap

current liquidity
peak liquidity

holder count

DEX pools

status
```

Possible statuses:

```text
NEW
ACTIVE
MIGRATED
ILLIQUID
DEAD
SUSPICIOUS
```

Where relevant, detect lifecycle events such as:

```text
token created
bonding curve activity
migration
liquidity pool creation
major liquidity changes
```

Do not assume every SPL token is a meme coin.

Design a configurable classification mechanism.

---

# 6. HISTORICAL WINNER DISCOVERY

The wallet discovery system should work backwards from historically successful meme coins.

Example configurable definition:

```text
Initial MC:
$20k - $500k

Later Peak MC:
>= $1m
```

Do NOT hardcode these numbers.

Example:

```text
TOKEN A

creation
    ↓
$35k MC
    ↓
$100k
    ↓
$500k
    ↓
$2m
    ↓
$8m
```

Identify wallets entering during early stages.

Example entry buckets:

```text
< $50k MC
$50k-$100k
$100k-$250k
$250k-$500k
$500k-$1m
> $1m
```

These buckets must be configurable.

---

# 7. EARLY BUYER EXTRACTION

For each historical winner:

Identify wallets that bought during early phases.

Collect:

```text
wallet
token
timestamp

SOL spent
token amount

entry price
estimated entry MC
liquidity at entry

time since token creation

transaction signature
DEX / launch platform
```

Then observe subsequent behavior.

Did the wallet:

```text
sell?
hold?
partial sell?
buy more?
transfer tokens?
```

---

# 8. DO NOT CONFUSE TRANSFERS WITH TRADES

Incoming tokens must NOT automatically be treated as purchases.

Differentiate:

```text
BUY
SELL
TRANSFER_IN
TRANSFER_OUT
AIRDROP
UNKNOWN
```

This matters because some apparently profitable wallets may receive tokens without buying them.

Profit calculations must not treat free transferred tokens as normal trading alpha.

---

# 9. WALLET TRADE RECONSTRUCTION

Normalize wallet activity into:

```text
WalletTrade

wallet
token

side

quantity

solAmount
usdAmount

price

marketCapAtTrade
liquidityAtTrade

timestamp
slot
transactionSignature

venue
```

Support:

```text
multiple buys
DCA buys
partial sells
multiple sells
remaining holdings
transfers
```

Calculate both:

```text
realized PnL
unrealized PnL
```

Avoid naive PnL calculations.

Document the accounting methodology.

---

# 10. WALLET ANALYTICS

For every candidate wallet calculate:

```text
Realized PnL
Unrealized PnL

ROI

Win Rate

Total Trades

Winning Tokens
Losing Tokens

Average Win
Median Win

Average Loss
Median Loss

Profit Factor

Average Position Size
Median Position Size

Average Holding Time
Median Holding Time

Largest Win
Largest Loss

Max Drawdown
```

Calculate for:

```text
24H
7D
30D
90D
ALL TIME
```

---

# 11. MEME-COIN-SPECIFIC WALLET METRICS

Add:

```text
Early Entry Rate

Median Entry Market Cap

Median Entry Liquidity

Median Entry Time After Token Creation

Sub-$100k Entry Rate

Sub-$500k Entry Rate

Rug Exposure Rate

Dead Token Exposure Rate

Migration Success Rate

Average Tokens Traded Per Day
```

Also measure:

```text
token creation → wallet entry latency
```

Example:

```text
Token created:
14:01:00

Wallet bought:
14:01:04

Entry latency:
4 seconds
```

Repeated ultra-fast entries may require special risk analysis.

---

# 12. PROFIT CONSISTENCY

Do not reward wallets purely for total PnL.

Calculate:

```text
largest winner / total profit

top 3 winners / total profit

top 5 winners / total profit
```

Example:

```text
Wallet profit:
$100,000

One token:
+$92,000
```

This wallet should receive a significant consistency penalty.

Track:

```text
profitable days
profitable weeks
profitable months
```

Example:

```text
Profitable weeks:
9 / 12

Profitable months:
5 / 6
```

---

# 13. WALLET BEHAVIOR CLASSIFICATION

Attempt to classify wallets into behavioral categories.

Possible labels:

```text
EARLY_BUYER

SCALPER

SWING_TRADER

MOMENTUM_TRADER

HIGH_FREQUENCY

LOW_CAP_HUNTER

LARGE_CAP_MEME_TRADER

DIAMOND_HAND

UNKNOWN
```

These classifications are descriptive.

Do not assume a particular style is automatically good.

---

# 14. SUSPICIOUS / NON-COPYABLE BEHAVIOR

Create evidence-based risk flags.

Examples:

```text
EXTREME_ENTRY_SPEED

BOT_LIKE

TRANSFER_HEAVY

INSIDER_LIKE_PATTERN

CREATOR_CONNECTED_PATTERN

HIGH_PNL_CONCENTRATION

LOW_LIQUIDITY_TRADER

HIGH_RUG_EXPOSURE

NEW_WALLET

HIGH_FREQUENCY

UNREALISTIC_COPYABILITY
```

These labels represent detected patterns, not definitive accusations.

Store evidence for every flag.

---

# 15. WALLET FUNDING ANALYSIS

Where practical, analyze:

```text
wallet creation/activity age

initial funding source

SOL transfers

related wallets

repeated common funding sources
```

This may help detect groups of wallets controlled by related entities.

Do NOT make definitive identity claims.

Use it only as behavioral/risk evidence.

---

# 16. CREATOR / DEV RELATIONSHIP ANALYSIS

For tokens traded by a wallet, investigate whether the wallet repeatedly appears unusually close to:

```text
token creation

creator wallet activity

initial liquidity

initial distribution

funding sources
```

Store relationship evidence.

Example:

```text
Wallet X

12 tokens traded

8 entries within 10 seconds of creation

5 share related funding paths
```

Flag for review.

Do not automatically classify this as malicious behavior.

---

# 17. WALLET COPYABILITY — CRITICAL

A profitable wallet is useless to this system if its trades cannot realistically be followed.

Create:

```text
CopyabilityScore
```

Model:

```text
leader transaction
       ↓
blockchain detection latency
       ↓
system processing
       ↓
hypothetical execution delay
       ↓
follower execution price
```

Configurable delays:

```text
500ms
1s
2s
3s
5s
10s
```

Backtest follower performance under each.

Example:

```text
Leader Entry:
$80k MC

Follower @ 1 sec:
$92k

Follower @ 3 sec:
$140k

Follower @ 5 sec:
$220k
```

Calculate:

```text
Leader ROI

Follower ROI @ 1s
Follower ROI @ 2s
Follower ROI @ 3s
Follower ROI @ 5s
Follower ROI @ 10s
```

Then:

```text
CopyDecay
```

Example:

```text
Leader ROI       +240%

Follower 1s      +180%
Follower 3s       +72%
Follower 5s        +8%
```

This wallet is highly latency-sensitive.

That must reduce its copyability score.

---

# 18. LIQUIDITY-AWARE COPYABILITY

Do not assume we can buy at the wallet's price.

Estimate:

```text
liquidity

trade size

price impact

slippage
```

Test several follower sizes:

```text
0.1 SOL
0.25 SOL
0.5 SOL
1 SOL
2 SOL
```

Make these configurable.

A wallet trading extremely illiquid tokens may have high PnL but terrible copyability.

---

# 19. SMART WALLET SCORE

Create:

```text
SmartWalletScore = 0-100
```

Initial configurable weighting:

```text
Profitability       20%
Consistency         20%
Copyability         25%
Risk Quality        15%
Entry Quality       10%
History Quality     10%
```

Weights must live in configuration/database.

Return breakdown:

```json
{
  "wallet": "ABC...XYZ",

  "score": 91,

  "components": {
    "profitability": 94,
    "consistency": 87,
    "copyability": 96,
    "riskQuality": 89,
    "entryQuality": 93,
    "historyQuality": 84
  }
}
```

Also explain WHY.

---

# 20. SMART WALLET REGISTRY

Wallet states:

```text
CANDIDATE

WATCHLIST

SMART_WALLET

SUSPENDED

REJECTED
```

Recalculate wallet scores periodically.

Wallet quality can deteriorate.

Do not permanently classify a wallet as smart.

---

# 21. REAL-TIME SMART WALLET TRACKING

Track wallets in:

```text
SMART_WALLET
```

state.

Prefer WebSocket/event-driven ingestion where possible.

Generate:

```text
WALLET_BUY
WALLET_SELL
WALLET_TRANSFER_IN
WALLET_TRANSFER_OUT
```

Example:

```json
{
  "type": "WALLET_BUY",

  "wallet": "ABC...XYZ",

  "walletScore": 92,

  "token": "TOKEN_ADDRESS",

  "solAmount": 2.1,

  "price": 0.000032,

  "marketCap": 185000,

  "liquidity": 72000,

  "timestamp": "..."
}
```

---

# 22. CLUSTER DETECTION

Do not paper-buy because ONE smart wallet bought.

Detect multi-wallet activity.

Example:

```text
14:01 Wallet A BUY TOKEN
14:02 Wallet F BUY TOKEN
14:02 Wallet X BUY TOKEN
14:04 Wallet K BUY TOKEN
```

Generate:

```text
SmartWalletCluster
```

Track:

```text
token

wallet count

average wallet score

weighted wallet score

total SOL bought

first buy timestamp

last buy timestamp

buy velocity
```

Example:

```text
4 wallets
avg score 89

12.4 SOL total buy

window:
3m 12s
```

---

# 23. WALLET ENTITY DEDUPLICATION

Four wallets controlled by one entity must not automatically count as four independent smart-wallet confirmations.

Create infrastructure for wallet relationship detection.

Possible signals:

```text
same funding source

frequent transfers between wallets

highly synchronized trades

same transaction patterns

similar token history
```

Calculate something conceptually like:

```text
IndependentWalletCount
```

rather than blindly using raw wallet count.

---

# 24. TOKEN RISK ENGINE

Meme coins require strong token screening.

Calculate:

```text
TokenRiskScore
```

Analyze where available:

```text
token age

market cap

liquidity

holder count

top 10 concentration

top 20 concentration

creator holdings

creator activity

mint authority

freeze authority

supply concentration

liquidity concentration

wallet clustering

suspicious distribution

token transfers

DEX activity
```

Unknown information must return:

```text
UNKNOWN
```

Never:

```text
missing data = safe
```

---

# 25. DEV / CREATOR ANALYSIS

Track token creator behavior.

Possible metrics:

```text
tokens created historically

creator token success rate

creator rug/dead token history

creator holdings

creator selling

creator transfers

creator funding relationships
```

Example:

```text
Creator:

Tokens launched: 18

Dead/Rug-like:
14

Still active:
2

Successful:
2
```

This should materially affect token risk.

---

# 26. HOLDER ANALYSIS

Analyze concentration.

Example:

```text
Top 10:
22%

Creator:
3%

Smart Wallets:
8%

Known related cluster:
12%
```

Be careful to exclude or separately classify known pool/system addresses where appropriate.

---

# 27. SIGNAL ENGINE

Create:

```text
SignalScore = 0-100
```

Initial configurable weighting:

```text
Wallet Quality       25%

Independent Wallets  20%

Token Risk           20%

Liquidity            10%

Entry Quality        10%

Buy Velocity         10%

Market Confirmation   5%
```

Possible decisions:

```text
IGNORE

WATCH

PAPER_BUY
```

Every signal MUST be explainable.

Example:

```json
{
  "token": "TOKEN_ADDRESS",

  "score": 92,

  "decision": "PAPER_BUY",

  "reasons": [
    "5 high-quality smart wallets bought",
    "4 appear behaviorally independent",
    "average wallet score 91",
    "cluster formed within 184 seconds",
    "liquidity above configured threshold",
    "holder concentration within configured threshold"
  ],

  "warnings": [
    "token age below 15 minutes"
  ]
}
```

---

# 28. SIGNAL COOLDOWN

Prevent:

```text
14:01 BUY SIGNAL
14:02 BUY SIGNAL
14:03 BUY SIGNAL
```

for the same token movement.

Implement:

```text
token cooldown

signal aggregation

cluster update

signal invalidation
```

---

# 29. PAPER TRADING ENGINE

NO REAL MONEY.

NO PRIVATE KEY REQUIRED.

Create configurable virtual accounts.

Example:

```text
Starting Balance:

$10,000
```

When:

```text
SignalScore >= configured threshold
```

simulate execution.

---

# 30. REALISTIC EXECUTION

Do NOT use the signal price as the execution price.

Example:

```text
Signal:

14:05:00

Price:
$0.000031


Simulated execution:

14:05:03

Price:
$0.000034
```

The paper trade enters at:

```text
$0.000034
```

Include:

```text
latency

slippage

price impact

network fees

priority fee assumptions

failed transaction probability
```

where appropriate.

---

# 31. PAPER EXECUTION SCENARIOS

Allow strategy testing under different execution conditions.

Example:

```text
Scenario A

Latency:
1 second

Slippage:
1%


Scenario B

Latency:
3 seconds

Slippage:
3%


Scenario C

Latency:
5 seconds

Slippage:
5%
```

This lets us answer:

> Does the strategy still work under worse execution conditions?

---

# 32. POSITION SIZING

Support configurable sizing.

Example:

```text
Paper balance:
$10,000

Default position:
1%

Maximum position:
3%

Maximum simultaneous positions:
10
```

Also support SOL-denominated sizing.

Never assume infinite liquidity.

---

# 33. PAPER POSITION MODEL

Store:

```text
token

signal

signal timestamp

signal price

execution timestamp

execution price

position size

quantity

slippage

price impact

fees

stop loss

take profit

highest price

current price

realized PnL

unrealized PnL

exit reason

status
```

---

# 34. EXIT STRATEGIES

Support configurable strategies.

Simple initial strategy:

```text
SL:
-15%

TP:
+30%
```

Then support:

```text
Partial Take Profit

+25% → sell 25%

+50% → sell 25%

+100% → sell 25%

remaining:
trailing stop
```

Also support smart-wallet behavior exits.

Example:

```text
Original cluster:
5 wallets

3/5 wallets sell

→ reduce/close paper position
```

Another:

```text
Smart-wallet sell pressure > configured threshold

→ exit
```

---

# 35. MEME-COIN EXIT CONDITIONS

Support research into conditions such as:

```text
liquidity collapse

creator sell

large holder sell

smart-wallet cluster exit

rapid holder concentration increase

volume collapse

maximum holding time

stop loss

trailing stop
```

Each strategy must be configurable and independently backtestable.

---

# 36. BACKTEST ENGINE

Historical events and live events should use the same strategy pipeline.

Design:

```text
Historical Event
       │
       ▼
Signal Engine
       │
       ▼
Paper Execution
```

and:

```text
Live Event
       │
       ▼
Signal Engine
       │
       ▼
Paper Execution
```

Do NOT maintain completely separate strategy logic for historical and live paper trading.

---

# 37. AVOID LOOKAHEAD BIAS

Critical.

Historical analysis must only use information available at the simulated timestamp.

Example:

At:

```text
14:05
```

the strategy must NOT know:

```text
future ATH

future liquidity

future wallet PnL

future rug status

future wallet score
```

Implement point-in-time evaluation.

Document protections against:

```text
lookahead bias

survivorship bias

selection bias
```

---

# 38. STRATEGY PERFORMANCE

Calculate:

```text
Trades

Win Rate

Gross Profit

Gross Loss

Net PnL

ROI

Average Win

Average Loss

Profit Factor

Expectancy

Max Drawdown

Average Holding Time

Average Slippage

Average Price Impact

Average Detection Latency

Average Execution Latency
```

---

# 39. COMPARE RAW VS EXECUTABLE PERFORMANCE

Always compare:

```text
Ideal Entry

vs

Delayed Entry

vs

Delayed + Slippage

vs

Delayed + Slippage + Fees
```

Example:

```text
Ideal strategy:

+84%


3 sec delay:

+49%


3 sec + slippage:

+31%


3 sec + slippage + fees:

+24%
```

This comparison is a core feature.

---

# 40. WEB APPLICATION

This MUST be a web-based application.

Build the frontend from the beginning.

Primary navigation:

```text
Overview

Discovery

Smart Wallets

Live Activity

Signals

Tokens

Paper Trading

Analytics

Settings
```

---

# 41. OVERVIEW DASHBOARD

Display:

```text
Tracked Smart Wallets

New Wallet Candidates

Active Signals

Paper Portfolio Equity

24H Paper PnL

7D Paper PnL

Win Rate

Current Drawdown
```

Also show:

```text
Live Smart Money Feed
```

Example:

```text
14:32 Wallet A BUY TOKEN X  2.4 SOL

14:32 Wallet B BUY TOKEN X  1.8 SOL

14:33 Wallet C BUY TOKEN X  3.1 SOL


⚡ CLUSTER DETECTED

TOKEN X

Signal:
91/100
```

---

# 42. DISCOVERY PAGE

This is one of the core screens.

Show:

```text
Tokens Analyzed

Wallets Found

Candidate Wallets

Profitable Wallets

Consistent Wallets

Copyable Wallets

Smart Wallets
```

Example funnel:

```text
82,419 wallets
     ↓
19,281 profitable
     ↓
4,812 consistent
     ↓
824 copyable
     ↓
247 smart wallets
```

Allow users to inspect why wallets passed or failed filters.

---

# 43. SMART WALLET LEADERBOARD

Show:

```text
Wallet

Smart Score

30D ROI

90D ROI

Win Rate

Realized PnL

Copyability

Median Entry MC

Median Hold Time

Risk Level

Last Activity
```

Allow filtering and sorting.

Do not hide poor historical periods.

---

# 44. WALLET DETAIL PAGE

Display:

```text
Smart Wallet Score

Score Breakdown

PnL Chart

ROI

Win Rate

Trade History

Token History

Entry Market Cap Distribution

Holding Time Distribution

Copyability

Copy Decay

Risk Flags

Funding Analysis

Related Wallets
```

Example:

```text
COPYABILITY

Leader ROI:
+180%

Follower @ 1s:
+142%

Follower @ 3s:
+88%

Follower @ 5s:
+31%

Follower @ 10s:
-4%
```

This visualization is extremely important.

---

# 45. TOKEN DETAIL PAGE

Display:

```text
Price chart

Market cap

Liquidity

Volume

Token age

Creator

Holder concentration

Creator history

Smart wallets holding

Smart wallets buying

Smart wallets selling

Risk Score

Risk reasons
```

Also display smart-wallet timeline.

---

# 46. SIGNAL PAGE

Show:

```text
Token

Signal Score

Decision

Smart Wallet Count

Independent Wallet Count

Average Wallet Score

Total SOL Bought

Cluster Window

Market Cap

Liquidity

Token Risk

Creator Risk

Signal Reasons

Warnings
```

---

# 47. PAPER TRADING PAGE

Display:

```text
Starting Balance

Current Equity

Realized PnL

Unrealized PnL

Return %

Win Rate

Profit Factor

Max Drawdown
```

Then:

```text
OPEN POSITIONS

Token

Signal Score

Entry

Current Price

PnL

Holding Time

Smart Wallet Sell Pressure
```

---

# 48. ANALYTICS PAGE

Allow comparing strategy configurations.

Example:

```text
Strategy A

min wallets:
3

signal threshold:
80

latency:
1s


Strategy B

min wallets:
4

signal threshold:
85

latency:
3s
```

Compare:

```text
ROI

PnL

Win Rate

Profit Factor

Max Drawdown

Trade Count

Average Slippage
```

Do NOT automatically optimize only for maximum historical ROI.

---

# 49. DATABASE

Design PostgreSQL schema for at least:

```text
tokens

token_snapshots

token_creators

token_holders

wallets

wallet_relationships

wallet_trades

wallet_metrics

wallet_scores

wallet_risk_flags

wallet_events

smart_wallet_clusters

signals

signal_reasons

paper_accounts

paper_positions

paper_trades

strategy_configs

strategy_runs

strategy_metrics
```

Store time-sensitive data appropriately.

---

# 50. REDIS

Use Redis for appropriate ephemeral state:

```text
recent wallet events

cluster windows

token cooldown

latest prices

latest wallet status

WebSocket state

distributed locks

rate limiting
```

PostgreSQL remains the durable source of truth.

---

# 51. API

Implement APIs supporting the frontend.

Examples:

```text
/api/discovery

/api/wallets

/api/wallets/{wallet}

/api/wallets/{wallet}/trades

/api/wallets/{wallet}/metrics

/api/wallets/{wallet}/copyability


/api/tokens

/api/tokens/{token}

/api/tokens/{token}/risk


/api/signals

/api/signals/{signal}


/api/paper/account

/api/paper/positions

/api/paper/trades

/api/paper/performance


/api/analytics/strategies
```

---

# 52. OBSERVABILITY

Track:

```text
RPC latency

provider latency

provider failures

WebSocket reconnects

events received

events processed

duplicate events

wallets tracked

tokens tracked

signals generated

paper trades

processing latency
```

Use structured logs.

Never log secrets.

---

# 53. TESTING

Create comprehensive tests for:

```text
trade reconstruction

multiple buys

partial sells

transfers

PnL

ROI

wallet scoring

consistency

PnL concentration

copyability

latency simulation

slippage

price impact

cluster detection

wallet deduplication

token risk

signal scoring

cooldowns

paper entries

paper exits

stop losses

take profits

portfolio accounting

lookahead prevention
```

Tests must be deterministic.

---

# 54. CONFIGURATION

Do not hardcode strategy assumptions.

Example:

```yaml
wallet:
  minimum_score: 80
  minimum_trades: 20

discovery:
  max_entry_market_cap: 500000

cluster:
  minimum_wallets: 3
  window_seconds: 300

signal:
  minimum_score: 80
  cooldown_seconds: 900

paper:
  starting_balance: 10000
  position_size_percent: 1
  max_open_positions: 10

execution:
  latency_ms: 3000
  base_slippage_percent: 2

risk:
  stop_loss_percent: 15
  take_profit_percent: 30
```

Allow editing relevant strategy configuration from the web Settings page.

---

# 55. DEVELOPMENT PHASES

Do NOT build everything at once.

## PHASE 0 — RESEARCH

Research:

```text
Solana data providers

Solana RPC providers

transaction indexing

historical price sources

historical liquidity

Pump.fun / PumpSwap data

Raydium data

Meteora data

Jupiter data

token holder data

real-time wallet monitoring
```

Produce:

```text
docs/data-providers.md
```

No invented APIs.

---

## PHASE 1 — FOUNDATION

Build:

```text
Next.js frontend

FastAPI backend

PostgreSQL

Redis

Docker Compose

migrations

provider interfaces

domain models
```

The entire stack must start locally.

---

## PHASE 2 — TOKEN DATA

Implement:

```text
token discovery

token metadata

token creation

market data

liquidity data

historical snapshots
```

---

## PHASE 3 — WALLET DISCOVERY

Implement:

```text
historical winner discovery

early buyer extraction

candidate wallet discovery
```

---

## PHASE 4 — WALLET INTELLIGENCE

Implement:

```text
trade reconstruction

PnL

ROI

win rate

consistency

entry behavior

risk flags

copyability

Smart Wallet Score
```

---

## PHASE 5 — WEB WALLET ANALYTICS

Implement:

```text
Discovery UI

Wallet leaderboard

Wallet detail page

PnL charts

Copyability visualization
```

---

## PHASE 6 — REAL-TIME TRACKER

Implement:

```text
wallet subscriptions

event normalization

live activity

WebSocket frontend updates
```

---

## PHASE 7 — CLUSTER + TOKEN RISK

Implement:

```text
cluster detection

wallet independence analysis

token risk

creator analysis

holder analysis
```

---

## PHASE 8 — SIGNAL ENGINE

Implement:

```text
signal score

signal reasons

warnings

IGNORE

WATCH

PAPER_BUY
```

---

## PHASE 9 — PAPER TRADING

Implement:

```text
virtual portfolio

execution simulation

latency

slippage

price impact

fees

position management

TP

SL

smart-wallet exits
```

---

## PHASE 10 — ANALYTICS + BACKTESTING

Implement:

```text
historical replay

strategy comparison

performance metrics

drawdown

execution scenario comparison
```

---

# 56. MVP SUCCESS CRITERIA

The MVP is complete when I can open the web application and:

1. See Solana meme tokens being analyzed.

2. See wallets discovered automatically from historical token activity.

3. See reconstructed wallet trades.

4. See wallet historical PnL.

5. See wallet consistency metrics.

6. See wallet risk indicators.

7. See Copyability Score.

8. See Smart Wallet Score and understand why the wallet received it.

9. View a Smart Wallet leaderboard.

10. Track selected Smart Wallets in near real time.

11. See their buys and sells in the web UI.

12. Detect multiple independent Smart Wallets buying the same meme coin.

13. Inspect token, creator, liquidity, and holder risk.

14. Generate an explainable signal.

15. Automatically execute a simulated paper trade.

16. Monitor the simulated position.

17. Automatically simulate exits.

18. See overall portfolio performance.

19. Compare realistic execution against ideal historical execution.

20. Backtest different strategy configurations without lookahead bias.

---

# 57. MOST IMPORTANT QUESTIONS

The application should ultimately answer:

### Wallet

```text
Is this wallet actually consistently profitable?

Or did one lucky meme coin create most of its PnL?
```

### Copyability

```text
If we detect this wallet's trade 1-5 seconds later,
is there still an edge?
```

### Cluster

```text
Are several genuinely independent high-quality wallets
buying the same meme coin?
```

### Token

```text
Does the token have acceptable liquidity,
holder distribution,
creator behavior,
and risk characteristics?
```

### Execution

```text
Can we realistically enter without destroying
the theoretical edge through slippage and latency?
```

### Strategy

```text
After latency,
slippage,
price impact,
fees,
rugs,
failed trades,
and losses:

IS THE STRATEGY STILL PROFITABLE?
```

That question matters more than headline wallet PnL.

---

# 58. AGENT WORKING INSTRUCTIONS

Do not immediately generate hundreds of files.

Start by:

1. Inspecting the repository.

2. Researching current Solana data providers.

3. Understanding how current Solana meme-coin trading flows work.

4. Producing:

```text
docs/architecture.md
docs/data-providers.md
docs/wallet-discovery.md
docs/wallet-scoring.md
docs/copyability.md
docs/signal-engine.md
docs/paper-trading.md
```

5. Propose the database schema.

6. Propose provider interfaces.

7. Identify data availability limitations.

8. Identify expensive API/data requirements.

9. Identify assumptions.

10. Produce an implementation plan.

Then begin Phase 1.

After EVERY phase:

```text
install

compile/build

run tests

start services

verify APIs

verify frontend

fix failures
```

Do not proceed with a broken phase.

When uncertain about Solana behavior, DEX behavior, launchpad behavior, or external APIs:

**research and verify rather than guessing.**

For important technical decisions document:

```text
Decision
Reason
Tradeoff
```

Keep a list of unresolved assumptions.

Do not implement real-money trading.

The final deliverable for this stage ends at:

**historical discovery + real-time wallet tracking + signals + realistic paper trading + analytics.**
