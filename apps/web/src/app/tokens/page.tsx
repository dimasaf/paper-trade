"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import SiteNav from "@/components/SiteNav";
import { apiUrl, coverageWarnings, type TokenRecord } from "@/lib/tokens";

export default function TokensPage() {
  const [tokens, setTokens] = useState<TokenRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadTokens() {
      try {
        const response = await fetch(`${apiUrl}/tokens`, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Token request failed");
        setTokens((await response.json()) as TokenRecord[]);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError("The Token universe is unavailable.");
      }
    }

    void loadTokens();
    return () => controller.abort();
  }, []);

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-14 sm:px-10">
      <SiteNav />
      <header className="mb-10">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
          Token universe
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">
          Registered Tokens
        </h1>
        <p className="mt-3 max-w-3xl text-slate-300">
          Every Token is registered from a confirmed, recorded launch event with
          its provenance, lifecycle, classification evidence, and provider
          coverage.
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

      <section className="rounded-3xl border border-slate-700 bg-slate-900/80 p-6 sm:p-8">
        <ol data-testid="token-list" className="space-y-3">
          {tokens.map((token) => {
            const warnings = coverageWarnings(token.coverage);
            return (
              <li
                key={token.address}
                className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Link
                    href={`/tokens/${encodeURIComponent(token.address)}`}
                    className="font-semibold text-cyan-300"
                  >
                    {token.symbol} · {token.name}
                  </Link>
                  <span className="text-xs text-slate-500">
                    {token.launch_platform} · {token.lifecycle_state}
                  </span>
                </div>
                <p className="mt-2 break-all font-mono text-xs text-slate-400">
                  {token.address}
                </p>
                {warnings.length > 0 ? (
                  <p className="mt-2 text-xs text-amber-200">
                    {warnings.length} coverage warning
                    {warnings.length === 1 ? "" : "s"}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ol>
        {tokens.length === 0 && !error ? (
          <p className="text-sm text-slate-400">
            No Tokens are registered yet.
          </p>
        ) : null}
      </section>
    </main>
  );
}
