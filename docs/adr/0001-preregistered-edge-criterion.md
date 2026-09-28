# Pre-registered edge criterion

## Context

The platform exists to determine whether an executable edge exists. The starter document explicitly warns against optimizing for impressive historical returns. Without a criterion fixed before the first backtest, the natural failure mode is to keep tuning strategy parameters until the backtest looks profitable — a result that proves nothing about the future.

## Decision

The pass/fail bar is fixed in advance. An Edge is considered supported only if a fixed strategy configuration, over a fixed historical window, satisfies all of:

1. net-positive expectancy after latency, slippage, and fees;
2. still positive under the pessimistic execution scenario (3–5 s latency, 3–5% slippage);
3. holds on a held-out time split;
4. profit factor > 1.2 over at least 100 trades;
5. remains positive with the single best trade removed.

Failing the bar is a reportable result ("no edge at this latency"), not a prompt to re-tune.

## Consequences

- Strategy parameters may not be tuned against the evaluation window after seeing the result.
- The pessimistic execution scenario and an out-of-sample time split are requirements, not nice-to-haves.
- The primary deliverable becomes the measurement apparatus and its verdict, not returns.
- Reports must always show ideal vs delayed vs delayed+slippage vs delayed+slippage+fees side by side.
