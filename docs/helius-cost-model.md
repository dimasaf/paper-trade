# Helius cost model — Phase 0/1 historical wallet discovery

Question: can Phase 0/1 historical wallet discovery run at $0/month, or is Helius Developer ($49/mo) required?
All vendor numbers below are quoted from official pages (links in Sources). Retrieved from docs at time of writing.

## Recommendation

**$0/month works for Phase 0 and for the Phase 1 targets as scoped here — provided decoded history is fetched with
`getTransactionsForAddress` (`transactionDetails: "full"`), not with a `getSignaturesForAddress` + `getTransaction` loop.**
Model A (1,000 wallets × 200 tx = 200k tx) costs ~20,000 credits = **2%** of the Free plan's 1M monthly credits.
Model B (500 tokens × 5,000 trades = 2.5M tx) costs ~250,000 credits = **25%** of monthly Free credits. Neither needs
$49. The Developer plan buys *throughput and features*, not headroom: it matters if (a) monthly decoded volume exceeds
~10M full transactions, (b) you must use the `getTransaction` loop (2.5M tx ≈ 2.5M credits ≈ 2.5× the Free monthly
allowance, so a single-month $0 run is impossible), (c) you need Developer-only features (`transactionSubscribe` /
enhanced `accountSubscribe` over WSS, Devnet gRPC), or (d) the 2 req/s DAS/Enhanced bucket is the bottleneck for your
discovery step. Note the counter-intuitive result: the "$0 fallback" loop is ~10× *more* credit-expensive per
transaction than the Helius-exclusive method, so the cheap path is also the $0 path.

## 1. Helius plan facts (official)

| | Free | Developer |
|---|---|---|
| Price | $0/mo | $49/mo |
| Monthly credits | 1M | 10M |
| RPC rate limit | 10 req/s | 50 req/s |
| DAS & Enhanced APIs (2nd, separate bucket) | 2 req/s | 10 req/s |
| Wallet API (follows DAS/Enhanced bucket) | 2 req/s | 10 req/s |
| Additional credits | not offered (`-` in table) | $5 per 1M |
| `sendTransaction` | 1/s | 5/s |
| `getProgramAccounts` | 5/s | 25/s |
| Webhooks | max 5 | max 50 |
| support | community | chat |

Free-tier eligible: standard RPC + all historical/archival methods (1 credit each), `getTransactionsForAddress`,
DAS API, Enhanced/Parsed APIs, Wallet API `history`/`transfers`/`balances`/`balance-at`, Parsed Streams (5 concurrent),
LaserStream WSS standard methods, `Sender`, webhooks.
Not on Free: Wallet API `identity`, `batch-identity`, `funded-by` (Free returns `403 Forbidden`); LaserStream gRPC
mainnet (Devnet only); LaserStream WSS Helius extensions (`transactionSubscribe`); preprocessed transactions;
preconfirmations; `sendBundle`; Staked Connections (pricing page marks it not included on Free); raw shreds
($1,000/mo/IP).
Helius's own FAQ: "The Free plan is ideal for prototyping and development with 1M monthly credits and 10 RPC req/s."
Autoscaling is enabled by default only on Business/Professional, so on Free a credit overrun is a hard stop, not a
bill.

## 2. Credit costs of the calls this plan needs

- `getTransactionsForAddress`: **10 credits per 100 returned full transactions, rounded up, 10-credit minimum**
  (so 1–100 → 10, 250 → 30, 1,000 → 100). Signatures-only response: **10 credits flat**. Failed responses: free.
  Returns up to **1,000 full transactions per call**; **no batch requests allowed**; mainnet retention "Unlimited".
- `getTransfersByAddress`: 10 credits (≤100 transfers/call).
- Standard/historical RPC (`getSignaturesForAddress`, `getTransaction`, `getBlock`, …): **1 credit** each.
  `getSignaturesForAddress` returns 1–1,000 signatures per call. `getTransaction` may be batched up to **100 per request**
  (credits still 1 per transaction).
- DAS API: **10 credits per request for all DAS endpoints** (`getAssetsByCreator`, `getTokenAccounts`, …), and DAS
  runs in its **own rate bucket** (2 req/s Free, 10 req/s Developer) separate from the RPC bucket.
- Legacy Enhanced Transactions: 100 credits. Parsed Events: 10 credits/request (docs state metering starts
  September 24, 2026; unmetered before that). Parsed Streams events: 1 credit/event.
- Wallet API: **100 credits per request**, all endpoints; `/v1/wallet/{wallet}/history` returns up to 100 transactions
  per request, so history backfill is 100 credits per 100 transactions.

## 3. Cost models (arithmetic + assumptions)

Assumptions: full decoded history via `getTransactionsForAddress` unless stated; page size 1,000 full tx (documented
max); credits are plan-independent; 429 backoff causes wall-clock stretch but no extra credits; no retries counted.

**Model A — backfill 1,000 wallets × avg 200 tx = 200,000 tx.**
- Requests: 1 per wallet (200 < 1,000 page cap) = 1,000 requests, each returning 200 full tx.
- Credits: 200 returned = `10 × ceil(200/100)` = 20 credits/request → 1,000 × 20 = **20,000 credits = 2% of the 1M
  Free allowance.** (Cross-check: 200,000 × 0.1 credit/tx = 20,000.) Floor if any wallet returns nothing: 10 credits each.
- Wall clock: 1,000 requests ÷ 10 req/s ≈ 100 s minimum (RPC bucket); realistically minutes given large payloads.
- Verdict: **$0.** Optional DAS discovery on top (1,000 × `getTokenAccounts` = 10,000 credits via the 2 req/s DAS
  bucket ≈ 500 s) → 30,000 credits total = 3% of monthly. Still $0.
- Same job via Wallet API `history`: 200,000 ÷ 100 per request = 2,000 requests × 100 credits = **200,000 credits
  (20% of monthly)** at 2 req/s ≈ 1,000 s. $0, but 10× the credits and 10× slower than Model A.

**Model B — full trade history of 500 tokens × 5,000 trades = 2,500,000 tx.**
- Credits: 2,500,000 × 0.1 = **250,000 credits = 25% of the 1M Free allowance.**
- Requests: ≈ 2,500 if perfectly packed at 1,000 tx/page; more in practice because each address is a separate request
  (no batching) and a token's trades are spread across pool/pair accounts, each of which must be enumerated first.
- Wall clock: 2,500 ÷ 10 req/s = 250 s ≈ 4 min idealised; multi-address fan-out and 429 backoff dominate in reality.
- Verdict: **$0 on credits.** Binding constraints are RPC latency/429s and the cost of enumerating pool accounts — not
  credits. Free-tier credit ceiling ≈ 10M returned full tx/month (1M ÷ 0.1), i.e. Model B could run ~4× per month.

**Model C — same 2.5M tx via the $0 fallback loop (`getSignaturesForAddress` + `getTransaction`).**
- Signatures: 2,500,000 ÷ 1,000 per call = 2,500 requests × 1 credit = 2,500 credits.
- Transactions: 2,500,000 × 1 credit = 2,500,000 credits (unchanged whether batched 100/request or not).
- Total ≈ **2,502,500 credits = 250% of the 1M monthly Free allowance → not achievable in one month on Free.**
- Options: spread over 3 monthly Free cycles (~3 calendar months, assuming near-zero other usage), or $49 for one
  Developer month (2.5M = 25% of its 10M).
- Wall clock: unbatched = ~2.5M requests ÷ 10 req/s ≈ 250,000 s ≈ 69 h; batched 100/request = ~27,500 requests ÷ 10
  req/s ≈ 46 min. Batching changes bytes-of-time by ~90× at identical credit cost.
- Correctness caveat: `getSignaturesForAddress` "does not include transactions involving associated token accounts",
  so this loop misses swaps where only the wallet's ATA is referenced unless you first enumerate token accounts and
  query each one — which raises call count further.
- Verdict: **not $0 in one month at this scale**, and 10× the credits of Model B for the same data.

Marginal cost check (Developer): 1M full transactions × 0.1 = 100,000 credits ≈ **$0.50 per 1M decoded full
transactions** at the $5/1M overage rate.

## 4. Free alternatives for decoded historical swaps

- **Solana Tracker Data API Free** — €0, **10,000 requests/month, 3 req/s**, no Datastream (WebSocket needs
  Premium+). Contradiction: the docs pricing page says 10,000 req/mo, while the data-api marketing page says
  "2.5K requests / month — 3 requests per second"; the resources page mentions a "free, 2,500 requests/month" key.
  Treat 10,000 as the docs-stated figure and verify on signup. Trade endpoint is cursor-paginated; the per-request page
  size is **not stated in the pages reviewed** (SDK README documents max 5,000/request for *holders*), so at an assumed
  ~100 trades/request: Model A needs ~2,000 requests (fits 10k), Model B needs ~25,000 requests (exceeds 10k even at the
  higher, disputed quota). Commercial-use permission for the free plan is **not stated** in the ToS excerpt reviewed.
- **GoldRush** — 14-day free trial: 25,000 credits at 4 RPS, no card; **Vibe Coding $10/mo**: 10,000 credits
  (prorated), 4 RPS; Professional $250/mo: 300,000 credits, 50 RPS. Credit value ≈ $0.00077/credit (their pricing
  calculator), i.e. the $10 plan ≈ $7.70 of usage. Endpoint pricing is fixed-price per call or tiered by result count
  (1–50/51–200/201–500/501+); **the credit cost of the Solana transaction-history endpoint is not published on the pages
  reviewed** — must be read off their pricing calculator. Consequence: Model A/B coverage cannot be computed from
  published numbers (see Missing evidence). Also, the only $0 steady state is the time-boxed 14-day trial; after it the
  floor is $10/mo.
- **Bitquery Personal** — $39/mo billed annually ($468/yr) or $49/mo monthly; 100,000 API points/mo ≈ "20k calls/mo"
  (vendor's own conversion); 30 req/min, 3 concurrent; flat-rate add-on points $40/1M. Licence is explicitly
  "**Personal use only — no commercial use**" → **disqualified if the product is commercial.** Free tier is not a
  durable $0 option: 10K free points for the *first month* on the Developer plan (one-time) plus a 7-day trial
  (1,000 API points, 2 concurrent streams). At 30 req/min, 20k calls ≈ 11 h minimum wall clock. Points-per-call data
  volume is not published, so it cannot be mapped onto Models A/B.
- Summary: at Phase 0 scale (Model A), Solana Tracker Free plausibly covers it at $0 and Helius Free definitively does;
  at Model B scale only Helius Free is demonstrably $0 from published numbers. GoldRush = $10/mo, not $0. Bitquery
  Personal = $39/mo and licence-disqualified for a commercial product.

## 5. Caveats

1. Buckets are separate: RPC (10/s Free) and DAS/Enhanced incl. Wallet API (2/s Free). A mixed discovery+backfill job
   can run both concurrently without sharing a rate budget — but the 2/s bucket, not credits, will cap DAS/Wallet work.
2. `getTransactionsForAddress` allows **no batch requests** — one address per call. Credits scale with *returned
   transactions* (0.1/tx), requests scale with the number of addresses queried. Model B's 2,500-request estimate assumes
   favourable packing and pool-account enumeration; validate on a 5-token sample.
3. The `tokenAccounts` filter "does not support transactions prior to December 2022" (slot 111,491,819). Irrelevant for
   recent memecoin discovery; blocking for pre-2023 tokens without the documented workaround.
4. `getSignaturesForAddress` omits ATA-only activity (explicit in docs) — the Model C loop under-collects unless ATA
   enumeration is added.
5. Responses are heavy: up to 1,000 full transactions **with full `meta`** per call. Storage/parse cost is on your side;
   "$0" covers vendor cost only, not engineering or infra time.
6. Free plan has no overage purchase (`-`) so exceeding 1M credits forces an upgrade; it is not a pay-as-you-go stop.
7. Rate-limit etiquette is documented: on 429/503, wait ~1 s, double up to 30 s, ±25% jitter, give up after 5 attempts.
8. The Free plan is positioned by Helius for "prototyping and development"; **no explicit commercial-use licence term for
   the Free tier was found** in the pages reviewed — verify in the Helius ToS before shipping a commercial product.
9. Free is capped at 5 webhooks — relevant if Phase 1 leans on webhooks for live monitoring. Parsed Events/Parsed
   Streams metering is documented as starting September 24, 2026, so those paths are currently unpriced in practice.
10. Vendor credit costs and plan limits change; re-verify before committing budget or writing a spend claim.

## 6. Missing evidence / not published

- GoldRush: credits per Solana transaction-history call (only a calculator, no table found) → Model A/B coverage on
  GoldRush cannot be computed.
- Solana Tracker: trades-per-request page size; whether free-tier data may be used commercially; whether the free
  quota is 10,000 or 2,500 requests/month (docs contradict marketing).
- Helius: the pricing comparison table's "Archival data" row value for Free did not render in the retrieved page text.
  The historical-data guide states archival methods cost 1 credit (with `getTransactionsForAddress` the exception) and
  no plan gate is documented, and the Wallet API page enumerates exactly which endpoints 403 on Free — implying
  historical queries are Free-eligible — but no explicit "available on Free" sentence was found.
- Whether Free-tier `getTransactionsForAddress` throughput on 1,000-tx full pages sustains 10 req/s in practice
  (payload-size dependent) — an empirical question for a spike, not a docs question.
- Validation limitation: a `source_check` was run on the plan/price claim and returned status "unclear" (automated
  passage assessment unavailable); the numbers were instead verified by hand against the fetched official pages.

## 7. Sources

- Helius pricing (plan grid, RPS, credit packs): https://www.helius.dev/pricing
- Helius plans & pricing docs (Free vs Developer, features): https://www.helius.dev/docs/billing/plans
- Helius credits (per-call credit costs incl. DAS 10, Wallet API 100, historical 1): https://www.helius.dev/docs/billing/credits
- Helius rate limits (two buckets, Wallet API follows DAS/Enhanced, batch limits): https://www.helius.dev/docs/billing/rate-limits
- `getTransactionsForAddress` (metering 10/100, 1,000 per call, no batching, pre-Dec-2022 caveat): https://www.helius.dev/docs/rpc/gettransactionsforaddress
- `getSignaturesForAddress` (1–1,000 per call, ATA exclusion): https://www.helius.dev/docs/api-reference/rpc/http/getsignaturesforaddress
- Wallet API (100 credits, 100 tx/page, Free 403 endpoints): https://www.helius.dev/docs/api-reference/wallet-api
- Solana Tracker pricing & limits (Free 10,000 req, 3 req/s): https://docs.solanatracker.io/pricing
- Solana Tracker data-api page (conflicting 2.5K free): https://www.solanatracker.io/data-api
- GoldRush pricing (trial 25,000 credits, $10 = 10,000 credits): https://goldrush.dev/pricing/
- GoldRush pricing calculator ($0.00077/credit, tiered pricing): https://goldrush.dev/docs/pricing-calculator
- Bitquery pricing (Personal $39–49, no commercial use): https://bitquery.io/pricing
- Bitquery billing docs (points, first-month free 10K): https://docs.bitquery.io/docs/plans/how-billing-works/
- Bitquery rate limits (30/min Personal): https://docs.bitquery.io/docs/plans/rate-limits/
