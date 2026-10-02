"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import SiteNav from "@/components/SiteNav";
import {
  fetchWalletLeaderboard,
  type LeaderboardSort,
  type RegistryState,
  type WalletLeaderboardEntry,
} from "@/lib/wallets";

const registryStates = [
  "ALL",
  "CANDIDATE",
  "WATCHLIST",
  "SMART_WALLET",
  "SUSPENDED",
  "REJECTED",
] as const;

const sortOptions: Array<{ value: LeaderboardSort; label: string }> = [
  { value: "TOTAL_SCORE", label: "Total score" },
  { value: "RECENT_ROI", label: "Recent ROI (30D)" },
  { value: "LONG_TERM_ROI", label: "Long-term ROI (all time)" },
  { value: "RECENT_PNL", label: "Recent PnL (30D)" },
  { value: "LONG_TERM_PNL", label: "Long-term PnL (all time)" },
];

const limits = [10, 25, 50, 100] as const;

function quality(entry: WalletLeaderboardEntry, period: "30D" | "ALL_TIME") {
  return entry.quality.find((item) => item.period === period) ?? null;
}

function percent(value: number | null): string {
  return value === null ? "UNKNOWN" : `${value.toFixed(2)}%`;
}

function amount(value: number | null): string {
  return value === null ? "UNKNOWN" : `$${value.toFixed(2)}`;
}

function timestamp(value: string): string {
  return new Date(value).toLocaleString();
}

export default function WalletLeaderboardPage() {
  const [entries, setEntries] = useState<WalletLeaderboardEntry[]>([]);
  const [sort, setSort] = useState<LeaderboardSort>("TOTAL_SCORE");
  const [registryState, setRegistryState] = useState<RegistryState | "ALL">(
    "ALL",
  );
  const [limit, setLimit] = useState<number>(25);
  const [asOf] = useState(() => new Date().toISOString());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function loadEntries() {
      try {
        const rows = await fetchWalletLeaderboard(
          { asOf, sort, registryState, limit },
          controller.signal,
        );
        setEntries(rows);
        setError(null);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError("The Smart Wallet leaderboard is unavailable.");
      }
    }
    void loadEntries();
    return () => controller.abort();
  }, [asOf, limit, registryState, sort]);

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-14 sm:px-10">
      <SiteNav />
      <header className="mb-10">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
          Smart Wallet Registry
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">
          Wallet leaderboard
        </h1>
        <p className="mt-3 max-w-3xl text-slate-300">
          Every scored Wallet appears with its weighted Smart Wallet Score, its
          Registry state, and both recent and long-term quality, so a weak
          recent period cannot hide behind an all-time number.
        </p>
      </header>

      <section className="mb-6 flex flex-wrap items-end gap-4 rounded-3xl border border-slate-700 bg-slate-900/80 p-6">
        <label className="flex flex-col gap-1 text-sm text-slate-300">
          Sort by
          <select
            data-testid="leaderboard-sort"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
            value={sort}
            onChange={(event) => setSort(event.target.value as LeaderboardSort)}
          >
            {sortOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-300">
          Registry state
          <select
            data-testid="leaderboard-registry-state"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
            value={registryState}
            onChange={(event) =>
              setRegistryState(event.target.value as RegistryState | "ALL")
            }
          >
            {registryStates.map((state) => (
              <option key={state} value={state}>
                {state}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-300">
          Limit
          <select
            data-testid="leaderboard-limit"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          >
            {limits.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </section>

      {error ? (
        <div
          role="alert"
          className="mb-6 rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-rose-100"
        >
          {error}
        </div>
      ) : null}

      <section className="overflow-x-auto rounded-3xl border border-slate-700 bg-slate-900/80">
        <table
          data-testid="wallet-leaderboard"
          className="w-full text-left text-sm"
        >
          <thead className="bg-slate-950/60 text-slate-400">
            <tr>
              <th className="p-3">Wallet</th>
              <th className="p-3">State</th>
              <th className="p-3">Score</th>
              <th className="p-3">Recent 30D</th>
              <th className="p-3">Long term</th>
              <th className="p-3">As of</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const recent = quality(entry, "30D");
              const longTerm = quality(entry, "ALL_TIME");
              return (
                <tr
                  key={entry.address}
                  className="border-t border-slate-800 align-top"
                >
                  <td className="p-3">
                    <Link
                      href={`/wallets/${encodeURIComponent(entry.address)}`}
                      className="break-all font-mono text-xs text-cyan-300"
                    >
                      {entry.address}
                    </Link>
                    {entry.warnings.length > 0 ? (
                      <p className="mt-1 text-xs text-amber-200">
                        {entry.warnings.length} warning
                        {entry.warnings.length === 1 ? "" : "s"}
                      </p>
                    ) : null}
                  </td>
                  <td className="p-3">{entry.recommended_state}</td>
                  <td className="p-3 font-semibold">
                    {entry.total_score.toFixed(2)}
                  </td>
                  <td className="p-3 text-xs text-slate-300">
                    ROI {percent(recent?.roi_percent ?? null)} · PnL{" "}
                    {amount(recent?.total_pnl_usd ?? null)} ·{" "}
                    {recent?.trade_count ?? 0} closed
                  </td>
                  <td className="p-3 text-xs text-slate-300">
                    ROI {percent(longTerm?.roi_percent ?? null)} · PnL{" "}
                    {amount(longTerm?.total_pnl_usd ?? null)} ·{" "}
                    {longTerm?.trade_count ?? 0} closed
                  </td>
                  <td className="p-3 text-xs text-slate-400">
                    {timestamp(entry.as_of)} · config v
                    {entry.configuration_version}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {entries.length === 0 && !error ? (
          <p className="p-6 text-sm text-slate-400">
            No Wallet has a recorded score yet. Score a Wallet or run a
            reassessment first.
          </p>
        ) : null}
      </section>
    </main>
  );
}
