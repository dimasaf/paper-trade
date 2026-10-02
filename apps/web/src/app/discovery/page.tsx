"use client";

import { useEffect, useState } from "react";

import SiteNav from "@/components/SiteNav";
import {
  apiUrl,
  type HistoricalWinnerDiscovery,
} from "@/lib/historical-winners";

function value(amount: number | null): string {
  return amount === null ? "UNKNOWN" : `$${amount.toLocaleString()}`;
}

function timestamp(date: string): string {
  return new Date(date).toLocaleString();
}

export default function DiscoveryPage() {
  const [discovery, setDiscovery] = useState<HistoricalWinnerDiscovery | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function loadDiscovery() {
      try {
        const response = await fetch(
          `${apiUrl}/discovery/historical-winners/latest`,
          {
            cache: "no-store",
            signal: controller.signal,
          },
        );
        if (response.status === 404) {
          setError("No recorded historical-winner cohort is available yet.");
          return;
        }
        if (!response.ok)
          throw new Error("Historical winner discovery request failed");
        setDiscovery((await response.json()) as HistoricalWinnerDiscovery);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError("Historical winner discovery could not be loaded.");
      }
    }
    void loadDiscovery();
    return () => controller.abort();
  }, []);

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-14 sm:px-10">
      <SiteNav />
      <header className="mb-10">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
          Historical discovery
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">
          Historical winners and early buyers
        </h1>
        <p className="mt-3 max-w-3xl text-slate-300">
          Winners are qualified from a fixed cohort before recorded buyer
          entries are evaluated. Entry facts retain their own as-of boundary.
        </p>
      </header>

      {error ? (
        <div
          role="alert"
          className="mb-6 rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-rose-100"
        >
          {error}
        </div>
      ) : null}

      {discovery ? (
        <div className="space-y-8">
          <section
            data-testid="historical-winner-cohort"
            className="rounded-2xl border border-slate-700 bg-slate-900/80 p-5 text-sm text-slate-300"
          >
            <h2 className="font-semibold text-white">Fixed cohort</h2>
            <p className="mt-2">
              {timestamp(discovery.cohort.created_from)} to{" "}
              {timestamp(discovery.cohort.created_to)}
              {" · "}qualified as of{" "}
              {timestamp(discovery.cohort.qualification_as_of)}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Configuration version {discovery.configuration_version} ·{" "}
              {discovery.cohort.cohort_id}
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white">
              Historical winners
            </h2>
            <div data-testid="historical-winners" className="mt-4 space-y-4">
              {discovery.winners.map((winner) => (
                <article
                  key={winner.token_address}
                  className="rounded-2xl border border-slate-700 bg-slate-900/80 p-5"
                >
                  <div className="flex flex-wrap justify-between gap-3">
                    <h3 className="font-semibold text-cyan-300">
                      {winner.token_symbol}
                    </h3>
                    <span
                      className={
                        winner.qualified ? "text-emerald-300" : "text-rose-300"
                      }
                    >
                      {winner.qualified ? "QUALIFIED" : "NOT QUALIFIED"}
                    </span>
                  </div>
                  <p className="mt-2 break-all font-mono text-xs text-slate-400">
                    {winner.token_address}
                  </p>
                  <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div>
                      <dt className="text-xs text-slate-500">
                        Initial market cap
                      </dt>
                      <dd>{value(winner.initial_market_cap_usd)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-slate-500">
                        Peak market cap
                      </dt>
                      <dd>{value(winner.peak_market_cap_usd)}</dd>
                    </div>
                  </dl>
                  <ul className="mt-4 space-y-1 text-sm text-slate-300">
                    {winner.qualifying_facts.map((fact) => (
                      <li key={fact.criterion}>
                        {fact.criterion}: {fact.observed} / {fact.threshold} ·{" "}
                        {fact.passed ? "PASS" : "FAIL"}
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-white">Early buyers</h2>
            <div data-testid="early-buyers" className="mt-4 space-y-4">
              {discovery.early_buyers.map((buyer) => (
                <article
                  key={`${buyer.wallet_address}:${buyer.signature}`}
                  className="rounded-2xl border border-slate-700 bg-slate-900/80 p-5"
                >
                  <h3 className="break-all font-mono text-sm text-cyan-300">
                    {buyer.wallet_address}
                  </h3>
                  <p className="mt-1 text-xs text-slate-400">
                    {timestamp(buyer.chain_time)} · {buyer.token_age_seconds}s
                    since Token creation · {buyer.venue ?? "UNKNOWN venue"}
                  </p>
                  <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
                    <div>
                      <dt className="text-xs text-slate-500">Amount</dt>
                      <dd>
                        {buyer.amount_tokens} Tokens / {value(buyer.amount_usd)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-slate-500">Price</dt>
                      <dd>{value(buyer.price_usd)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-slate-500">Market cap</dt>
                      <dd>
                        {value(buyer.market_cap_usd)} ·{" "}
                        {buyer.entry_market_cap_bucket}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-slate-500">Liquidity</dt>
                      <dd>{value(buyer.liquidity_usd)}</dd>
                    </div>
                  </dl>
                  <p className="mt-3 break-all font-mono text-xs text-slate-400">
                    Signature: {buyer.signature}
                  </p>
                  <p
                    data-testid="entry-boundary"
                    className="mt-3 text-xs text-amber-200"
                  >
                    Entry as of {timestamp(buyer.entry_evaluation.as_of)}.
                    Unavailable:{" "}
                    {buyer.entry_evaluation.unavailable_facts.join(", ")}.
                  </p>
                  {buyer.warnings.length > 0 ? (
                    <ul
                      role="alert"
                      className="mt-3 list-disc pl-5 text-sm text-amber-200"
                    >
                      {buyer.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  ) : null}
                </article>
              ))}
            </div>
          </section>

          <section data-testid="candidate-wallets">
            <h2 className="text-2xl font-semibold text-white">
              Candidate Wallet pool
            </h2>
            <ul className="mt-4 space-y-3">
              {discovery.candidate_wallets.map((candidate) => (
                <li
                  key={candidate.wallet_address}
                  className="rounded-xl border border-slate-700 bg-slate-900/80 p-4"
                >
                  <p className="break-all font-mono text-sm text-cyan-300">
                    {candidate.wallet_address}
                  </p>
                  <p
                    className={
                      candidate.passed
                        ? "mt-1 text-emerald-300"
                        : "mt-1 text-rose-300"
                    }
                  >
                    {candidate.passed ? "PASS" : "FAIL"}
                  </p>
                  {candidate.evidence.map((fact) => (
                    <p
                      key={`${candidate.wallet_address}:${fact.criterion}`}
                      className="text-xs text-slate-400"
                    >
                      {fact.criterion}: {fact.observed} ·{" "}
                      {fact.passed ? "PASS" : "FAIL"}
                    </p>
                  ))}
                </li>
              ))}
            </ul>
          </section>
        </div>
      ) : null}
    </main>
  );
}
