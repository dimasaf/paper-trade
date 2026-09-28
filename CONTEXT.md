# Paper Trade

A research platform for Solana meme coins that asks one question: does activity from historically profitable, realistically copyable wallets yield an executable trading edge after latency, slippage, liquidity, fees, and rugs? It discovers wallets, scores them, generates explainable signals, and validates them through paper trading — never real money.

## Language

**Edge**:
Positive expected value per trade after realistic execution costs. The platform's output is a verdict on whether an Edge exists, not a return figure.
_Avoid_: alpha, profit, ROI

**Copyability**:
The degree to which a Wallet's Edge survives a follower's latency, position size, and available liquidity. A modeled distribution of outcomes, not a single number.
_Avoid_: followability, replicability

**Copy Decay**:
The fall in follower ROI as follower latency increases against a leader's entry. The signature of a latency-sensitive Wallet.
_Avoid_: decay, slippage

**Smart Wallet**:
A Wallet in the `SMART_WALLET` registry state — one that passed the profitability, consistency, copyability, and risk gates. An operational label, not a claim of skill.
_Avoid_: alpha wallet, good wallet, whale

**Contributing-independent Wallets**:
Wallets with no detected shared controller (common funding, synchronized trades, inter-wallet transfers). Replaces raw wallet count when judging a Cluster.
_Avoid_: unique wallets, independent wallets

**Cluster**:
A set of at least N Contributing-independent Wallets buying the same Token inside a configured window.
_Avoid_: herd, group buy, swarm

**Signal**:
An explainable IGNORE / WATCH / PAPER_BUY recommendation carrying a score, reasons, and warnings. Not a trade and not an order.
_Avoid_: alert, call, pick

**Paper Trade**:
A simulated fill of a Signal against virtual funds under a configured execution scenario. Requires no private key.
_Avoid_: mock trade, simulated order

**Wallet Trade**:
A normalized, side-classified movement of a Token by a Wallet, distinguishing BUY and SELL from TRANSFER_IN, TRANSFER_OUT, AIRDROP, and UNKNOWN.
_Avoid_: transaction, transfer

**Token**:
A Solana SPL mint tracked by the platform together with its market state. Not every SPL token is a Token; classification is configurable.
_Avoid_: coin, asset, memecoin

**Registry state**:
One of CANDIDATE, WATCHLIST, SMART_WALLET, SUSPENDED, REJECTED. Reassigned on periodic rescores; never permanent.
_Avoid_: tier, rank
