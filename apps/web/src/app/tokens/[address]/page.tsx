"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import SiteNav from "@/components/SiteNav";
import { apiUrl, coverageWarnings, type TokenRecord } from "@/lib/tokens";

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

export default function TokenDetailPage() {
  const params = useParams<{ address: string }>();
  const address = params?.address ?? "";
  const [token, setToken] = useState<TokenRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!address) return;
    const controller = new AbortController();

    async function loadToken() {
      try {
        const response = await fetch(
          `${apiUrl}/tokens/${encodeURIComponent(address)}`,
          { cache: "no-store", signal: controller.signal },
        );
        if (response.status === 404) {
          setError("This Token is not registered.");
          return;
        }
        if (!response.ok) throw new Error("Token request failed");
        setToken((await response.json()) as TokenRecord);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError("The Token detail could not be loaded.");
      }
    }

    void loadToken();
    return () => controller.abort();
  }, [address]);

  const warnings = token ? coverageWarnings(token.coverage) : [];

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-14 sm:px-10">
      <SiteNav />

      {error ? (
        <div
          role="alert"
          className="rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-rose-100"
        >
          {error}
        </div>
      ) : null}

      {token ? (
        <>
          <header className="mb-10">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
              {token.symbol} · {token.launch_platform}
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">
              {token.name}
            </h1>
            <p
              data-testid="token-address"
              className="mt-3 break-all font-mono text-xs text-slate-400"
            >
              {token.address}
            </p>
          </header>

          {warnings.length > 0 ? (
            <div
              data-testid="coverage-warnings"
              role="alert"
              className="mb-8 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-5 text-amber-100"
            >
              <p className="font-semibold">Coverage warnings</p>
              <ul className="mt-2 space-y-1 text-sm text-amber-100/80">
                {warnings.map((warning) => (
                  <li key={warning}>UNKNOWN or incomplete — {warning}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <section className="mb-8 rounded-3xl border border-slate-700 bg-slate-900/80 p-6 sm:p-8">
            <h2 className="text-xl font-semibold text-white">Provenance</h2>
            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">
                  Creator
                </dt>
                <dd className="mt-1 break-all font-mono text-sm text-slate-200">
                  {token.creator}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">
                  Launch platform
                </dt>
                <dd
                  data-testid="token-platform"
                  className="mt-1 text-sm text-slate-200"
                >
                  {token.launch_platform}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">
                  Creation time
                </dt>
                <dd className="mt-1 text-sm text-slate-200">
                  {formatTimestamp(token.created_at)}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">
                  Observed at
                </dt>
                <dd className="mt-1 text-sm text-slate-200">
                  {formatTimestamp(token.observed_at)}
                </dd>
              </div>
            </dl>
          </section>

          <section className="mb-8 rounded-3xl border border-slate-700 bg-slate-900/80 p-6 sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-xl font-semibold text-white">Lifecycle</h2>
              <span
                data-testid="token-lifecycle-state"
                className="rounded-full bg-cyan-400/15 px-4 py-2 text-sm font-semibold text-cyan-200"
              >
                {token.lifecycle_state}
              </span>
            </div>
            <ol data-testid="lifecycle-transitions" className="mt-4 space-y-2">
              {token.lifecycle_transitions.map((transition) => (
                <li
                  key={`${transition.source_event_id}-${transition.state}`}
                  className="flex flex-wrap justify-between gap-2 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm"
                >
                  <span className="font-medium text-slate-200">
                    {transition.state}
                  </span>
                  <span className="text-slate-500">
                    {formatTimestamp(transition.observed_at)}
                  </span>
                </li>
              ))}
            </ol>
          </section>

          <section className="mb-8 rounded-3xl border border-slate-700 bg-slate-900/80 p-6 sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-xl font-semibold text-white">
                Classification evidence
              </h2>
              <span className="text-xs text-slate-500">
                Configuration v{token.classification.configuration_version} ·{" "}
                {token.classification.configuration_id}
              </span>
            </div>
            <ul
              data-testid="classification-evidence"
              className="mt-4 space-y-2"
            >
              {token.classification.criteria.map((criterion) => (
                <li
                  key={criterion.criterion}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm"
                >
                  <span className="font-medium text-slate-200">
                    {criterion.criterion}
                  </span>
                  <span className="text-slate-500">
                    {criterion.observed} vs {criterion.threshold}
                  </span>
                  <span
                    className={
                      criterion.passed ? "text-emerald-300" : "text-rose-300"
                    }
                  >
                    {criterion.passed ? "PASS" : "FAIL"}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-3xl border border-slate-700 bg-slate-900/80 p-6 sm:p-8">
            <h2 className="text-xl font-semibold text-white">
              Provider coverage
            </h2>
            <ul data-testid="coverage-list" className="mt-4 space-y-3">
              {token.coverage.map((entry) => (
                <li
                  key={`${entry.provider}-${entry.as_of_start}`}
                  className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm"
                >
                  <div className="flex flex-wrap justify-between gap-2">
                    <span className="font-medium text-slate-200">
                      {entry.provider}
                    </span>
                    <span className="text-slate-500">{entry.commitment}</span>
                  </div>
                  <p className="mt-2 text-slate-400">
                    As of {formatTimestamp(entry.as_of_start)} —{" "}
                    {formatTimestamp(entry.as_of_end)} ·{" "}
                    {entry.complete ? "complete" : "incomplete"}
                  </p>
                  <p className="mt-2 text-slate-400">
                    Freshness: {entry.freshness_seconds}s · Slot: {entry.slot} ·
                    Normalization: {entry.normalization_version}
                  </p>
                  <p className="mt-2 break-all font-mono text-xs text-slate-500">
                    Signature: {entry.signature}
                  </p>
                  <p className="mt-2 text-slate-400">
                    Unknown fields:{" "}
                    {entry.unknown_fields.length > 0
                      ? entry.unknown_fields.join(", ")
                      : "none"}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        </>
      ) : null}
    </main>
  );
}
