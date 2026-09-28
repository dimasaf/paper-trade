# Solana Data Providers — Phase 0 Evaluation Brief

**Repo:** paper-trade (Solana memecoin wallet-intelligence + paper-trading platform)
**Prepared:** research pass run late September 2026 (date anchored from CoinDesk 2026-09-28 datelines; see Sources)
**Scope:** which *currently available, documented* Solana data sources can satisfy the 10 required capabilities, and what cannot be obtained at all.
**Method:** official docs/pricing pages fetched directly (not blog summaries). Prices are as published on the pages linked below; re-verify before purchase — several vendors change tiers frequently.

### Verification limitations (read first)
- **Birdeye** and **Dune** pricing pages are behind bot protection (Cloudflare 403 / JS-only). Their numbers here come from search-engine extracts of the official pages and are marked **low–medium confidence**; a human must open the page.
- A `source_check` validation attempt on Birdeye pricing returned `missing-evidence` (fetches blocked). Birdeye pricing below is therefore **unvalidated**.
- A `source_check` on the Helius `getTransactionsForAddress` claim retrieved the correct official sources but ran no automated support assessment; that claim was instead verified by reading the official docs page directly.
- **Triton One** per-call rates come from a third-party price aggregator; only the $125 prepay minimum is confirmed on triton.one.
- **Syndica** does not publish self-serve pricing; only marketing pages were reachable.
- No endpoint was invented here. Program IDs quoted below are from official vendor repos/docs.

---

## 1. Summary recommendation

**Phase 0 (0–$50/mo, prove the design):** one Helius **Developer ($49)** endpoint for everything transaction-level, plus free tiers of **Dexscreener** (price/liquidity/mcap snapshots), **Jupiter Price API v3** (USD pricing), **GeckoTerminal** (OHLCV), and **Solana Tracker Memescope** free (launch feed). Build raw-RPC behind an interface from day one.

**Phase 1 — historical discovery / backfill (the expensive part):** Helius `getTransactionsForAddress` (unlimited mainnet retention, 1,000 full decoded txs per call, ascending pagination) is the cheapest credible full-history decoder. Where indexed market history is needed, add exactly one aggregator: **Solana Tracker Data API Pro/Premium (€200–€397)** for token-level trades + holders + OHLCV + WebSocket, or **Bitquery** (archive add-on $210–$400/mo for Solana) if you need SQL-like joins and per-trade market cap. Do not pay for both at Phase 1.

**Phase 2 — real-time wallet tracking:** streaming must come from Geyser-class infra, not the public RPC. Cheapest credible options: **Helius LaserStream gRPC** (mainnet requires the $499 Business tier), **Solana Tracker Yellowstone gRPC (€200/mo standalone)** or **QuickNode Solana gRPC** ($499/mo add-on below Scale). Pure WebSocket `logsSubscribe`/`accountSubscribe` from a normal paid RPC works for low volume but is slower and easier to miss.

**Phase 3 — production hardening:** second RPC vendor for failover (Chainstack Unlimited Node flat-rate for predictable cost, or Alchemy PAYG at $0.525/1M CU), plus a market-data vendor with holders + liquidity depth (Vybe or Solana Tracker).

**Do not build on:** Flipside (blockchain data business sold to SonarX, May 2026), undocumented pump.fun frontend endpoints, Shyft's deprecated token/NFT APIs, Covalent's old docs domain, or the free public RPC in production.

---

## 2. Comparison table

### 2a. Provider-level (RPC / infra)

| Provider | Type | Decoded-tx quality | Historical depth | Streaming | Entry price | Verified notes |
|---|---|---|---|---|---|---|
| **Helius** | Solana RPC + enhanced APIs | Highest of the RPC vendors: parsed events, `getTransactionsForAddress`, Wallet API, DAS | **Unlimited mainnet retention** for `getTransactionsForAddress` | LaserStream gRPC + WSS (`transactionSubscribe`), Webhooks, Shreds, Preconfs | $0 / **$49** / $499 / $999 | gRPC mainnet needs Business+; identity & funded-by endpoints need any paid plan; parsed events 10 credits/req, parsed streams 1 credit/event. [pricing](https://www.helius.dev/pricing) · [plans](https://www.helius.dev/docs/billing/plans) · [gTxForAddress](https://www.helius.dev/docs/rpc/gettransactionsforaddress) |
| **QuickNode** | Multi-chain RPC | Standard RPC; DAS add-on for assets | Archive data included on all paid | Streams, Webhooks, Solana gRPC (Scale+) | $0 trial / **$49** / $249 / $499 / $999+ | Solana gRPC is a **$499/mo add-on** on Build/Accelerate, included from Scale; limits 10–25 concurrent streams, 10–50 accounts/stream. [pricing](https://www.quicknode.com/pricing.md) · [DAS](https://www.quicknode.com/docs/solana/solana-das-api) |
| **Triton One** | Solana RPC + Yellowstone | Standard RPC; DAS/Metaplex | Ledger queries + archival | Dragon's Mouth gRPC (Yellowstone), Program Data Streams (Vixen) | **$125 prepay** (12 mo) + PAYG | Confirmed: no tiers, all products on every account, prepaid non-refundable deposit. Per-call rates (~$10/M calls, $0.08/GB) are third-party. [pricing](https://www.triton.one/pricing) · [gRPC](https://docs.triton.one/project-yellowstone/dragons-mouth-grpc-subscriptions) |
| **Chainstack** | Solana + multi-chain RPC | Standard RPC | Archive = 2 RU/request | Node WebSockets (no Geyser vending) | **$49** Growth → **$499** Business | 1 RU = 1 request (no method multipliers); Business = 200M RU, 600 RPS, 20 nodes; Unlimited Node add-on = flat monthly fee by RPS tier (25–1000 RPS). [pricing](https://chainstack.com/pricing/) · [RUs](https://docs.chainstack.com/docs/request-units) · [Unlimited Node](https://docs.chainstack.com/docs/unlimited-node) |
| **Alchemy (Solana)** | Solana RPC + DAS + gRPC | DAS v2 asset/metadata; standard RPC for txs | Full archive claimed | PubSub WebSocket, dedicated streaming endpoint, **Yellowstone gRPC** | PAYG: **$0.525/1M CU**, 300 RPS included | Yellowstone gRPC restricted to PAYG/Enterprise teams; DAS v2 price_info cached up to 600 s and limited to top ~10k tokens by 24h volume. [pricing](https://www.alchemy.com/pricing) · [gRPC](https://www.alchemy.com/docs/reference/yellowstone-grpc-overview) · [DAS v2](https://www.alchemy.com/docs/reference/alchemy-das-apis-for-solana-v2) |
| **Syndica** | Solana RPC + ChainStream | Not documented publicly | Unknown | ChainStream (claimed) | Not published | docs.syndica.io is currently **staking-focused**; product page advertises RPC/ChainStream/elastic nodes; a title tag claims "10M free RPC requests". **Low confidence — needs vendor contact.** [docs](https://docs.syndica.io/) · [product](https://syndica.io/product) |
| **Shyft** | Solana RPC + gRPC | Many token/NFT APIs marked **deprecated** | Unknown | Multi-region Yellowstone gRPC + "RabbitStream" shred-accelerated | Not verified in this pass | Alive and selling infra, but the legacy data APIs are explicitly deprecated in docs. Treat as streaming infra only. [site](https://shyft.to/) · [deprecated APIs](https://docs.shyft.to/solana-apis/fungible-tokens.md) |
| **Public RPC + Geyser** | Free shared RPC / validator plugin | None (raw) | Archive limits, no SLA | Geyser plugin = self-hosted only | $0 | Official docs: public endpoints are shared, rate-limited, no SLA, "not intended for production applications"; Geyser is a **validator plugin**, not a hosted service. [RPC](https://solana.com/docs/rpc) · [clusters](https://solana.com/docs/references/clusters) · [gRPC indexing](https://github.com/solana-foundation/solana-com/blob/main/apps/docs/content/docs/en/payments/accept-payments/indexing.mdx) |

### 2b. Provider-level (market data / indexed analytics)

| Provider | Covers | Historical depth | Streaming | Entry price | Verified notes |
|---|---|---|---|---|---|
| **Birdeye** | Price, trades, holders, liquidity, new listings, OHLCV | Multi-month+; enablement per endpoint | WebSocket on higher tiers | Free Standard (~30k CU, 1 rps) → $39 / $99 / $199+ / $699 | **Unvalidated** (403 + failed source_check). FAQ vs pricing page disagree (Premium 15M vs 20M CU; Business 70M vs 100M CU). [pricing](https://birdeye.so/data-api/pricing) · [FAQ](https://docs.birdeye.so/docs/faq) · [blog](https://birdeye.so/data-api/blog/detail/use-more-pay-less-with-bds-business-plan) |
| **Dexscreener** | Pairs: price, liquidity, FDV, mcap, txns, volume | **Current snapshot only** (no OHLCV endpoint) | None documented | Free (per-endpoint rate limits) | Terms allow commercial + non-commercial use; rate limits differ by endpoint (60/min on profiles/boosts/ads/metas; 300/min on pairs/token-pairs/search per third-party summaries). [reference](https://docs.dexscreener.com/api/reference) · [terms](https://docs.dexscreener.com/api/api-terms-and-conditions) |
| **GeckoTerminal** | Pools, tokens, trades, **OHLCV**, mcap | Unknown maximum lookback | None (websockets/webhooks on paid CoinGecko plans) | Free keyless (~10 calls/min) | Keyless pool is IP-shared and documented as unsuitable for production; higher limits come via CoinGecko paid plans. [docs](https://apiguide.geckoterminal.com/) · [keyless limits](https://docs.coingecko.com/docs/keyless-public-api) |
| **Jupiter** | Price v3 (≤50 ids), Swap quote, Tokens | Price only (last swap price); no history | None documented | Free key 1 RPS; $25 / $100 / $500 per mo | Tokens not traded in ~7 days are **omitted entirely** from price responses; keyless 0.5 RPS. [price](https://developers.jup.ag/docs/price) · [rate limits](https://developers.jup.ag/docs/portal/rate-limits) · [plans](https://dev.jup.ag/docs/portal/plans) |
| **Bitquery** | DEX trades, **first-class per-trade mcap/supply**, DEX pools & liquidity, pump.fun bonding curve, transfers, balances | Self-serve = rolling 30-day trades / 4–8 h on-chain; **archive is a paid add-on** | WebSocket, Kafka, **gRPC (CoreCast)** | **$39** Personal (no commercial license, no streaming) → $79 Pro (commercial) → $239 Scale | Solana archive packs: **$210/mo** (OHLCV & price only) or **$400/mo** (transfers & txns). [pricing](https://bitquery.io/pricing) · [Solana](https://docs.bitquery.io/docs/blockchain/Solana/) · [DEXPools](https://docs.bitquery.io/docs/blockchain/Solana/Solana-DexPools-API/) |
| **Solana Tracker** | 70+ REST: token data, trades, holders, OHLCV, PnL, risk; **Memescope** launch feed | Long history (unspecified depth) | Datastream WebSocket (Premium+), Yellowstone gRPC €200/mo | Free 10k req/3 rps → **€50 / €200 / €397** / €599 / €1,499 | Datastream needs Premium+; rooms for PnL, live transactions, holder updates, price feeds; no per-message fees. [pricing](https://docs.solanatracker.io/pricing) · [data API](https://www.solanatracker.io/data-api) |
| **Vybe** | 41 endpoints: tokens, markets, candles, trades, transfers, top holders, holders-count-ts, trader activity, wallet PnL, counterparties | **Free tier = 48 h only**; paid depth unspecified | WebSocket on Pro/Business; gRPC "coming soon" | Free → $49 / $149 / **$299** / $599 | Wallets' token balances & DeFi positions are a **separate $999+ "Portfolio" package**. WebSocket billed 1 credit/300 KB. [plans](https://docs.vybenetwork.com/docs/plans-rate-limits) · [WS pricing](https://docs.vybenetwork.com/docs/pricing) |
| **Solscan Pro** | Token meta, token price, **token holders / top holders**, decoded transactions, DeFi activities, historical market data | Not documented as bounded | **None documented** | **$199 / $399 / $1,099** per mo (150M / 500M / 1.5B CU; 1k / 2k / 3k req per 60 s) | All endpoints flat 100 CU. Good "gap filler" for metadata + holders + decoded txs without a full analytics contract. [endpoints](https://docs.solscan.io/solscan-api/solscan-pro-api-endpoints) · [Pro docs](https://pro-api.solscan.io/pro-api-docs/v2.0) |
| **Moralis** | Solana Data API (Solana-native) + Streams + Data Feeds | Archived RPC claimed; **historical backfill billed separately** | Streams + real-time Data Feeds | $149 Starter / $249 Pro / **$749** Business | Attribution required on Starter/Pro; Solana-specific endpoint depth not verified in this pass. [pricing](https://moralis.io/pricing/) · [Solana](https://docs.moralis.com/web3-data-api/solana) |
| **Dune** | SQL over Solana raw + **IDL-decoded** tables; API executions | Full chain history (warehouse) | No push streaming (poll executions) | Free / $65 Analyst / $349 Plus (per search extract) | Credit-based; **dune.com/pricing returned 403** to automated fetch → verify manually. [Solana catalog](https://docs.dune.com/data-catalog/solana/overview) · [IDL tables](https://docs.dune.com/data-catalog/solana/idl-tables) |
| **GoldRush (Covalent)** | Foundational API: SPL balances, historical transactions/wallet activity; DEX markets; decoded swaps to warehouse | Historical transactions advertised | None documented | **$10/mo** → $250/mo production | `docs.covalenthq.com` **does not resolve (DNS)** — new docs live at goldrush.dev. [Solana](https://goldrush.dev/docs/chains/solana) · [pricing](https://goldrush.dev/pricing/) |
| **Flipside** | Was SQL over curated Solana datasets | — | — | — | **Vendor changed:** Flipside sold its blockchain data business to **SonarX** (19 May 2026); existing contracts transfer to SonarX. Do not start new work here without checking SonarX terms. [Flipside notice](https://flipside-3887e776.mintlify.app/updates) · [SonarX](https://www.sonarx.com/blog/sonarx-acquires-flipside-crypto-blockchain-data-business) |

---

## 3. Per-category findings

Legend: **cheap/free** = ≤$50/mo or free tier; **expensive** = requires ≥$200/mo contract; **missing** = not obtainable from any documented source evaluated.

### 3.1 Historical wallet transactions (decoded swaps) — by wallet
- **Best value:** Helius `getTransactionsForAddress` — 1,000 full decoded transactions per call, ascending order for backfill, slot/time/status filters, `tokenAccounts: balanceChanged` to include ATA activity, **unlimited mainnet retention**, mainnet+devnet (devnet 2 weeks). Metering: 10 credits per 100 returned full transactions. Source: [Helius docs](https://www.helius.dev/docs/rpc/gettransactionsforaddress). **Confidence: high (direct doc evidence).**
- **Important limitation (direct evidence):** the `tokenAccounts` filter does **not** cover pre-December-2022 activity (depends on token-transfer metadata from slot 111,491,819). For memecoin-age wallets this rarely matters.
- **Cheap/free alternatives:** Solscan Pro (Account Transactions / Account DeFi Activities / decoded tx, $199+), Vybe `/v4/wallets/{addr}/pnl`, `/counterparties`, `/transfer-volume-usd` (Pro $299), Bitquery transfers/balance updates.
- **Free-at-small-scale:** Helius Wallet API `/v1/wallet/{wallet}/history` and `/transfers` are available on the **Free** plan; `identity` and `funded-by` require any paid plan (403 on Free). Source: [Wallet API](https://www.helius.dev/docs/wallet-api). **Confidence: high.**
- **Inference (not vendor-stated):** a full backfill of thousands of wallets scales with credits, so unit cost is dominated by credits, not by per-call limits — budget it as a metered job, not a fixed subscription.

### 3.2 Historical token trades (decoded swaps) — by token, with buyer/seller
- **Cheap/medium:** Solana Tracker Data API (trades + wallet analytics + PnL; €200 Pro) and Vybe `/v4/trades` (80 credits/call; Pro $299) both return per-trade data with wallets. Sources: [Solana Tracker pricing](https://docs.solanatracker.io/pricing), [Vybe plans](https://docs.vybenetwork.com/docs/plans-rate-limits).
- **Richest evidence (expensive):** Bitquery `Trading.Trades` / `DEXTrades` returns MEV-filtered swaps **with USD price, market cap and supply on every row**, plus trader identity; self-serve access is limited to a rolling ~30-day window, and Solana archive is a separate add-on ($210/mo OHLCV-only, $400/mo transfers+txns). Sources: [Bitquery Solana](https://docs.bitquery.io/docs/blockchain/Solana/), [Bitquery pricing](https://bitquery.io/pricing). **Confidence: high.**
- **Free with caveats:** Dexscreener exposes current pair txns counts but **not** a per-trade history endpoint (reference lists pairs/search/profiles/boosts/ads/metas only) — [reference](https://docs.dexscreener.com/api/reference). GeckoTerminal exposes `/trades` on pools but the endpoint's retention is undocumented ([API docs](https://apiguide.geckoterminal.com/)). Treat long-tail per-trade history as a paid capability.

### 3.3 Token creation / launch events (pump.fun, PumpSwap, Raydium, Meteora, Jupiter)
- **Detection technique is well-documented; the *data* is not sold by the launchpads:** you watch the launch programs. Verified program IDs:
  - pump.fun bonding curve: `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` (cited as the pump.fun program address in Bitquery's pump.fun docs) — [source](https://docs.bitquery.io/docs/blockchain/Solana/Pumpfun/Pump-Fun-Marketcap-Bonding-Curve-API/)
  - PumpSwap AMM: `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` — official pump repo ([PUMP_SWAP_README](https://github.com/pump-fun/pump-public-docs/blob/f0ef005c/docs/PUMP_SWAP_README.md))
  - Raydium **LaunchLab** `LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj`; AMM v4 `675kPX9…`; CPMM `CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C`; CLMM `CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK` — [Raydium program addresses](https://docs.raydium.io/reference/program-addresses)
  - Meteora Dynamic Bonding Curve: `dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN` (same on mainnet/devnet) — [Meteora DBC docs](https://docs.meteora.ag/developer-guides/dbc)
  - Jupiter Studio: launches on a bonding curve that **migrates to a Meteora pool** on graduation, with a Studio API (`/studio/v1/dbc-pool/create-tx`) — [Jupiter Studio](https://docs.jup.ag/user-docs/launch/studio), [Studio create-token API](https://developers.jup.ag/docs/studio/create-token)
- **Notable gap (evidence, not inference):** pump.fun publishes **programs, IDLs and MIT SDKs** but the official public repo (`pump-public-docs`) contains documentation and IDLs, **not a hosted data API** — [repo](https://github.com/pump-fun/pump-public-docs). Any third-party claim of an "official pump.fun API" refers to undocumented frontend endpoints; per project constraints, do not depend on those. **Confidence: medium-high** (inference from the official repo's contents + absence of any official API doc).
- **Ready-made launch feeds (cheap):** Solana Tracker **Memescope** (free real-time token launch feed) and Datastream "new tokens" room ([pricing/docs](https://docs.solanatracker.io/pricing)); Vybe WebSocket "New Tokens"/"New Markets" messages (~550 B / ~450 B each, 1 credit per 300 KB) — [Vybe WS pricing](https://docs.vybenetwork.com/docs/pricing); Bitquery pump.fun API incl. bonding-curve progress and migration tracking — [pump.fun API](https://docs.bitquery.io/docs/blockchain/Solana/Pumpfun/Pump-Fun-API/).
- **Inference:** for <10k launches/day, deriving creations yourself from Geyser (`logsSubscribe`/gRPC on the five program IDs above) is cheaper than any vendor; for >100k/day, buy a feed.

### 3.4 Token metadata + creator/authority info
- **Free/cheap:** Metaplex **DAS** via Helius (free plan allows 2 DAS req/s; paid 10–100 req/s — [Helius plans](https://www.helius.dev/docs/billing/plans)), QuickNode DAS add-on on any account ([QuickNode DAS](https://www.quicknode.com/docs/solana/solana-das-api)), Alchemy DAS v2 (`getAssetsByCreator_v2`, `getAssetsByAuthority_v2`, `getTokenAccounts_v2`; 160–480 CU per call) — [Alchemy DAS v2](https://www.alchemy.com/docs/reference/alchemy-das-apis-for-solana-v2).
- **Indexed/vendor-specific:** Solscan Pro Token Meta / Token Meta Multi (100 CU), Vybe `/v4/tokens/{mint}`, Solana Tracker token endpoints, Bitquery token supply/metadata.
- **Caveat (direct evidence):** Alchemy's `token_info.price_info` is cached up to 600 s and covers **only the top ~10,000 tokens by 24h volume** — fine for metadata, useless for fresh long-tail memecoin pricing.
- **Creator/authority nuance:** DAS gives the *current* update authority/mint authority; the **launching wallet** ("creator") is best obtained from the launch program's create instruction (pump.fun `CreateEvent`, PumpSwap `CreatePoolEvent`, Raydium/Meteora init instructions) — [pump repo docs list `CreateEvent`/`CreatePoolEvent` fields](https://github.com/pump-fun/pump-public-docs).

### 3.5 Current and historical token price
- **Current (free):** Jupiter Price API v3, ≤50 mints/request, free key at 1 RPS ([docs](https://developers.jup.ag/docs/price)) — **but** tokens untraded for ~7 days or flagged by Jupiter's heuristics are **omitted entirely**; expect silent missing data for dead memecoins. **Confidence: high (vendor-stated).**
- **Current + historical OHLCV (cheap):** GeckoTerminal OHLCV endpoints (free, keyless ~10 calls/min; higher limits via CoinGecko paid plans) — [GeckoTerminal API](https://apiguide.geckoterminal.com/), [keyless rate limits](https://docs.coingecko.com/docs/keyless-public-api). Solana Tracker (`/candles`-class endpoints in the 70+ API set, €50–€200), Vybe `/tokens/{mint}/candles` (50 credits) and `/oracle/pyth/pricefeeds/...` candles (30 credits) — [Vybe endpoints](https://docs.vybenetwork.com/docs/plans-rate-limits).
- **Historical depth risk:** GeckoTerminal does not publish a retention ceiling for OHLCV; treat "how far back can I get minute bars for a 6-month-old memecoin?" as **unverified** until tested. Bitquery's Solana archive OHLCV pack ($210/mo) is the documented depth guarantee.
- **Historical price from raw trades (self-derived):** with Helius `getTransactionsForAddress` full-mode responses you get `pre/postTokenBalances`, so USD price can be *derived* per swap; this is **researcher inference** on how to use documented fields, not a vendor feature.

### 3.6 Current and historical liquidity
- **Current (free):** Dexscreener pairs (`liquidity.usd`, `liquidity.base/quote`) — [reference](https://docs.dexscreener.com/api/reference); GeckoTerminal pools; both snapshot-only.
- **Historical (hard):** the only documented provider found that exposes per-change pool balances is **Bitquery `DEXPools`** (`Base{PostAmount}`, `Quote{PostAmount, PriceInUSD, PostAmountInUSD}`, with `ChangeAmount` semantics documented, archive dataset for >30 days) — [DEXPools](https://docs.bitquery.io/docs/blockchain/Solana/Solana-DexPools-API/). **Confidence: high for capability, medium for archive pricing details** ($210/$400 mo packs; Solana sells "two narrower packs").
- **Explicit caveat from Bitquery docs:** `PostAmount` is *everything the pool holds*, including out-of-range concentrated liquidity — **not** active in-range liquidity. Your "liquidity" metric definition must say which.
- **Missing:** no provider evaluated sells a clean "liquidity at time T (USD, active)" time series for Solana memecoins. You will either buy Bitquery and post-process, or reconstruct vault balances yourself from Geyser account updates (inference).

### 3.7 Market cap (current + peak/historical)
- **Current (free):** Dexscreener `marketCap`/`fdv` per pair; GeckoTerminal token/pool mcap; Jupiter omits many memecoins.
- **Historical/peak (paid):** Bitquery `Trading.Pairs` carries `Supply.MarketCap`, `FullyDilutedValuationUsd`, `TotalSupply` **on every interval row**, so peak mcap/ATH-time is a `max()` over rows; for the pump.fun bonding curve specifically, Bitquery documents a market-cap + bonding-curve-progress API with formulas — [marketcap & bonding curve](https://docs.bitquery.io/docs/blockchain/Solana/Pumpfun/Pump-Fun-Marketcap-Bonding-Curve-API/). Requires the archive add-on for >30-day lookbacks.
- **Alternative:** Dune SQL over Solana decoded tables (free/analyst tier) can compute peak mcap if you can join supply and price — depends on decoded-table availability for your target program (**unverified** in this pass; dune.com/pricing blocked).
- **Inference:** "peak market cap" is a *derived* metric everywhere; no vendor sells a labelled ATH field except inside their own UI. Budget engineering time for the aggregation, not dollars.

### 3.8 Token holders and holder distribution
- **Free/cheap:** Vybe `/v4/tokens/{mint}/top-holders` (80 credits, available on free) and `/holders-count-ts` (80 credits) with labelled entities (CEX/KOL/VC) — [Vybe holder data](https://docs.vybenetwork.com/docs/token-holder-data), [plans](https://docs.vybenetwork.com/docs/plans-rate-limits); Solscan Pro **Token Holders** / **Token Top** (100 CU each) — [endpoints](https://docs.solscan.io/solscan-api/solscan-pro-api-endpoints). Solana Tracker and Birdeye also advertise holder analytics.
- **Raw/self-serve:** Helius DAS `getTokenAccounts` / Alchemy `getTokenAccounts_v2` / `getProgramAccounts` on the token program give you every token account for a mint (then you aggregate yourself). QuickNode and Helius DAS both support this; Helius meters DAS at a separate RPS bucket.
- **Caveats (direct evidence / inference):** "holder count" is ill-defined for memecoins (dust accounts, pooled LP accounts, bonded PDAs). Vybe's `holders-count-ts` gives a series, which is the cleanest documented primitive. Anything richer (clustering, sybil/insider detection) is **not sold as a field** by the vendors evaluated — it is your own analysis on top of raw transfers (inference).

### 3.9 Wallet balances
- **Free:** standard RPC `getBalance` / `getTokenAccountsByOwner` (paid RPC recommended); Helius Wallet API `/balances` and `/balance-at` (historical point-in-time balance!) work on the **Free** plan — [Wallet API](https://www.helius.dev/docs/wallet-api). `balance-at` is unusual and valuable for paper-trading P&L snapshots. **Confidence: high.**
- **Paid only:** Vybe's wallet token balances are behind the **Portfolio package ($999+/mo)** — [plans](https://docs.vybenetwork.com/docs/plans-rate-limits); Moralis Wallet API on all plans ($149+).
- **Batch/historical:** Vybe `POST /v4/wallets/batch/token-balances-ts` (100 credits, paid tier), Bitquery balances (archive add-on for history).

### 3.10 Real-time wallet activity (websocket / streaming)
- **Cheapest credible:** paid RPC WebSocket (`logsSubscribe`/`accountSubscribe`). Solana Foundation docs position Geyser-class streaming (e.g. Yellowstone gRPC) at sub-100 ms vs ~200–400 ms for WebSocket subscriptions — [Solana indexing docs](https://github.com/solana-foundation/solana-com/blob/main/apps/docs/content/docs/en/payments/accept-payments/indexing.mdx), [Triton explainer](https://blog.triton.one/complete-guide-to-solana-streaming-and-yellowstone-grpc/).
- **Vendor options and their gates:**
  - Helius **LaserStream gRPC** — historical replay up to **48 hours**, auto-reconnect with replay, multi-node failover, ATA/mint filtering; mainnet requires **Business ($499)** or Professional — [LaserStream](https://www.helius.dev/docs/laserstream). Also Helius Webhooks for targeted addresses.
  - Solana Tracker Yellowstone gRPC — **€200/mo standalone**, 25 concurrent connections, EU+US, bundled free with €399+ RPC — [pricing](https://docs.solanatracker.io/pricing).
  - QuickNode Solana gRPC — $499/mo add-on (10 concurrent streams, 10 accounts/stream) on Build/Accelerate, included on Scale+ — [pricing](https://www.quicknode.com/pricing.md).
  - Alchemy Yellowstone gRPC — PAYG/Enterprise only — [docs](https://www.alchemy.com/docs/reference/yellowstone-grpc-overview).
  - Bitquery CoreCast gRPC / Kafka — Solana gRPC with context-aware filtering, priced in stream-minutes/GB on Pro+ — [CoreCast](https://docs.bitquery.io/docs/grpc/solana/introduction/), [pricing](https://bitquery.io/pricing).
  - Vybe WebSocket (Pro $299) — billed by data volume, 1 credit/300 KB — [pricing](https://docs.vybenetwork.com/docs/pricing).
  - Self-hosted Geyser plugin + Yellowstone: free software, but you must run a validator/plugin node ([yellowstone-grpc](https://github.com/rpcpool/yellowstone-grpc)).
- **Missing:** no vendor offers "stream every trade of *this specific wallet*" as a turnkey subscription without you filtering. You subscribe at the program/account level and filter client-side (inference from documented filter capabilities).

---

## 4. Gaps and risks (honest limits)

1. **Historical liquidity is the single biggest gap.** Per-change pool balances are documented only by Bitquery, at $210–$400/mo for Solana archive, and even there "liquidity" includes out-of-range CLMM liquidity. Dexscreener and GeckoTerminal give current snapshots only. If the project's central question depends on "how did liquidity/price evolve as the token died?", either budget Bitquery or run your own vault-balance reconstruction.
2. **Long-tail price coverage is structurally incomplete.** Jupiter explicitly drops tokens that haven't traded in ~7 days or fail heuristics — exactly the dead memecoins a wallet-intelligence backtest wants. Expect to need a second price source (GeckoTerminal/Bitquery/Dexscreener) and to define fallback precedence.
3. **Peak market cap / ATH is not a sold field.** It is derived from (supply × price) time series; only Bitquery gives supply+mcap per row (with archive add-on). Everything else is your aggregation.
4. **Holder distribution beyond "top N wallets" is not sold.** No vendor evaluated provides cluster/sybil/insider labels as a general product (Vybe labels *entities* such as CEX/KOL; that is a different thing from wallet clustering). Insider/coordinated-wallet analysis must be built by you from raw transfers.
5. **"Wallet performance" (win rate, realized PnL) is vendor-specific and unauditable.** Solana Tracker (PnL V2), Vybe (`/pnl`, `/pnl-ts`, `/top-pnl-traders`), Moralis, Birdeye all sell a PnL number with undisclosed methodology. Treat these as *features to compare against*, not as ground truth, and be prepared to recompute from decoded swaps (inference).
6. **Streaming latency claims are mostly vendor marketing.** Only the "gRPC vs WebSocket" gap is corroborated across sources; absolute latency numbers, uptime claims (e.g. Helius's 99.99% vs 99.84–99.85% comparison table, snapshot dated Feb 2024), must be treated as stale or self-serving.
7. **Vendor churn is real and fast.** Flipside's data business moved to SonarX in May 2026; Covalent's docs domain no longer resolves (GoldRush); Shyft's documented token/NFT APIs are deprecated. Design provider adapters so any single vendor can be swapped without touching the domain layer.
8. **Data licensing is uneven.** Bitquery's cheapest plan ($39) is explicitly **personal-use, no commercial license**; Moralis requires attribution on Starter/Pro; Dexscreener's terms permit commercial use *but* reserve the right to suspend; Dexscreener also states rate limits are specified at checkout for paid tiers. Legal review is required before shipping anything paid-for.
9. **Pre-December 2022 wallet history is degraded** for Helius ATA-aware queries (documented), and no vendor guarantees sub-second ordering of processed vs finalized data during reorgs — if paper-trading triggers on `processed`, add your own idempotency/rollback handling (inference).

---

## 5. Open questions a human must resolve

1. **Birdeye and Dune pricing tiers** — both pricing pages block automated fetching; open them in a browser and record the current CU/credit allowances and WebSocket eligibility. Birdeye's own docs currently contradict its pricing page.
2. **Syndica** — does a self-serve paid RPC/ChainStream tier still exist, at what price, and is gRPC sold? Only marketing pages are reachable; contact required.
3. **Triton One per-call rates** — confirm the $10/M calls + $0.08/GB figures on an invoice or inside the dashboard, since only the $125 prepay is published.
4. **Solana Tracker and Vybe historical depth** — neither states a retention ceiling for trades/OHLCV. Ask "how far back can I query trades for an arbitrary SPL mint?" in writing.
5. **GeckoTerminal retention** for minute OHLCV, and whether a CoinGecko paid plan (which tier, what price) is required for production polling.
6. **Accounts and keys to provision for Phase 0:** Helius free tier, Jupiter portal key (free, 1 RPS), Solana Tracker free key (2,500–10,000 req/mo), Dexscreener (no key), GeckoTerminal (no key). Confirm whether the paper-trading product will be **commercial** — if yes, Bitquery Personal is disqualified and Moralis attribution applies.
7. **Do we need per-wallet real-time alerts (<1 s) or is 2–5 s polling acceptable?** The answer decides whether Phase 2 needs a $200–$500/mo gRPC line item at all.

---

## 6. Sources

### Kept (decision-relevant, primary)
- Helius pricing — https://www.helius.dev/pricing ; plans & credits — https://www.helius.dev/docs/billing/plans ; `getTransactionsForAddress` — https://www.helius.dev/docs/rpc/gettransactionsforaddress ; Wallet API — https://www.helius.dev/docs/wallet-api ; LaserStream — https://www.helius.dev/docs/laserstream
- QuickNode pricing (markdown) — https://www.quicknode.com/pricing.md ; Solana DAS — https://www.quicknode.com/docs/solana/solana-das-api ; DAS product — https://www.quicknode.com/metaplex-das-api
- Triton One pricing — https://www.triton.one/pricing ; Dragon's Mouth gRPC — https://docs.triton.one/project-yellowstone/dragons-mouth-grpc-subscriptions
- Chainstack pricing — https://chainstack.com/pricing/ ; request units — https://docs.chainstack.com/docs/request-units ; Unlimited Node — https://docs.chainstack.com/docs/unlimited-node ; Business plan — https://chainstack.com/introducing-the-new-chainstack-business-plan/
- Alchemy pricing — https://www.alchemy.com/pricing ; Yellowstone gRPC — https://www.alchemy.com/docs/reference/yellowstone-grpc-overview ; DAS v2 — https://www.alchemy.com/docs/reference/alchemy-das-apis-for-solana-v2 ; Solana WebSocket — https://www.alchemy.com/docs/reference/solana-subscription-api-endpoints
- Syndica — https://docs.syndica.io/ ; https://syndica.io/product
- Shyft — https://shyft.to/ ; deprecated APIs — https://docs.shyft.to/solana-apis/fungible-tokens.md
- Solana public RPC — https://solana.com/docs/rpc ; https://solana.com/docs/references/clusters ; Geyser/Yellowstone context — https://github.com/solana-foundation/solana-com/blob/main/apps/docs/content/docs/en/payments/accept-payments/indexing.mdx ; https://github.com/rpcpool/yellowstone-grpc
- Dexscreener reference — https://docs.dexscreener.com/api/reference ; terms — https://docs.dexscreener.com/api/api-terms-and-conditions
- GeckoTerminal API guide — https://apiguide.geckoterminal.com/ ; CoinGecko keyless limits — https://docs.coingecko.com/docs/keyless-public-api
- Jupiter price API — https://developers.jup.ag/docs/price ; rate limits — https://developers.jup.ag/docs/portal/rate-limits ; plans — https://dev.jup.ag/docs/portal/plans
- Bitquery Solana — https://docs.bitquery.io/docs/blockchain/Solana/ ; DEX pools — https://docs.bitquery.io/docs/blockchain/Solana/Solana-DexPools-API/ ; pump.fun market cap — https://docs.bitquery.io/docs/blockchain/Solana/Pumpfun/Pump-Fun-Marketcap-Bonding-Curve-API/ ; gRPC — https://docs.bitquery.io/docs/grpc/solana/introduction/ ; pricing — https://bitquery.io/pricing
- Solana Tracker docs — https://docs.solanatracker.io/ ; pricing — https://docs.solanatracker.io/pricing ; data API — https://www.solanatracker.io/data-api
- Vybe plans — https://docs.vybenetwork.com/docs/plans-rate-limits ; WS pricing — https://docs.vybenetwork.com/docs/pricing ; holders — https://docs.vybenetwork.com/docs/token-holder-data
- Solscan Pro — https://docs.solscan.io/solscan-api/solscan-pro-api-endpoints ; https://pro-api.solscan.io/pro-api-docs/v2.0
- Moralis pricing — https://moralis.io/pricing/ ; Solana API — https://docs.moralis.com/web3-data-api/solana
- GoldRush Solana — https://goldrush.dev/docs/chains/solana ; pricing — https://goldrush.dev/pricing/
- Dune Solana catalog — https://docs.dune.com/data-catalog/solana/overview ; IDL tables — https://docs.dune.com/data-catalog/solana/idl-tables ; API executions — https://docs.dune.com/api-reference/executions/endpoint/execute-query
- Launch programs — https://docs.raydium.io/reference/program-addresses ; https://docs.raydium.io/products/launchlab ; https://docs.meteora.ag/developer-guides/dbc ; https://github.com/pump-fun/pump-public-docs ; https://docs.jup.ag/user-docs/launch/studio
- Flipside → SonarX — https://flipside-3887e776.mintlify.app/updates ; https://www.sonarx.com/blog/sonarx-acquires-flipside-crypto-blockchain-data-business ; https://www.einpresswire.com/article/913502316/flipside-sells-blockchain-data-business-to-sonarx-commits-fully-to-edisyl-enterprise-ai-platform
- Date anchor — https://www.coindesk.com/markets/2026/09/28/solana-etfs-draw-record-usd188-million-in-a-week-as-bitwise-takes-two-thirds-of-inflows

### Rejected / deprioritized
- Flipside as a candidate — blockchain data business divested to SonarX (May 2026); continuity unclear for new projects.
- Covalent legacy docs (`docs.covalenthq.com`) — DNS does not resolve; superseded by GoldRush.
- Shyft token/NFT data APIs — officially marked "deprecated, no longer supported".
- Third-party API-aggregator pages (dxttools.trade, apis.io, rpcplane.dev, screenerbot.io, dltHub) — used only as corroboration for rate limits/per-call prices, never as sole evidence.
- uwuu.ai "Pump Fun API" blog — low-quality SEO source; the "no official API" conclusion was drawn from the official pump.fun repo instead.
- Helius "compare QuickNode/Alchemy" table — vendor self-comparison with a Feb 2024 snapshot; not used for benchmarks.

---

## 7. Interface implications (what this means for the code, no code written)
- Define three ports: `WalletHistorySource`, `MarketDataSource` (price/liquidity/mcap/holders), `RealtimeSource`.
- Every port must accept an "as-of" time and return explicit `coverage: {from, to, complete: bool}` metadata, because capability gaps here are **per-token and per-time-window**, not per-vendor.
- Log which provider answered each query from day one; provider fallback will be routine (Jupiter omissions, GeckoTerminal gaps, Dexscreener snapshot-only).
