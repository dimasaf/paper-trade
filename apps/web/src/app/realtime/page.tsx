"use client";

import { type FormEvent, useEffect, useState } from "react";

import SiteNav from "@/components/SiteNav";
import {
  fetchRealtimeFeed,
  fetchRealtimeStatus,
  pollRealtimeTracking,
  type RealtimeTrackingStatus,
  type RealtimeWalletEvent,
} from "@/lib/realtime";

const FEED_LIMIT = 50;
const REFRESH_INTERVAL_MS = 5000;

function timestamp(date: string): string {
  return new Date(date).toLocaleString();
}

function usd(amount: number | null): string {
  return amount === null ? "UNKNOWN" : `$${amount.toLocaleString()}`;
}

function amount(quantity: number): string {
  return quantity.toLocaleString();
}

function score(value: number | null): string {
  return value === null ? "UNKNOWN" : value.toFixed(1);
}

function seconds(value: number | null): string {
  return value === null ? "UNKNOWN" : `${value.toFixed(1)}s`;
}

function RealtimeEventCard({ event }: { event: RealtimeWalletEvent }) {
  return (
    <article
      data-testid={`realtime-event-${event.signature}`}
      className="rounded-2xl border border-slate-700 bg-slate-900/80 p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-cyan-300">{event.movement_type}</h3>
          <p className="mt-1 break-all font-mono text-xs text-slate-400">
            Wallet {event.wallet_address}
          </p>
          <p className="break-all font-mono text-xs text-slate-400">
            Token {event.token_address}
          </p>
        </div>
        <span
          className={
            event.eligible_for_decisions
              ? "text-xs font-semibold text-emerald-300"
              : "text-xs font-semibold text-amber-200"
          }
        >
          {event.eligible_for_decisions
            ? "CONFIRMED · eligible"
            : "PROCESSED · observation only"}
        </span>
      </div>

      <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-xs text-slate-500">Amount</dt>
          <dd>{amount(event.quantity)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Price</dt>
          <dd>{usd(event.price_usd)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Valuation</dt>
          <dd>{usd(event.notional_usd)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Smart Wallet score</dt>
          <dd>{score(event.wallet_score)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Event time</dt>
          <dd>{timestamp(event.chain_time)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Observed time</dt>
          <dd>{timestamp(event.observed_at)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Venue</dt>
          <dd>{event.venue ?? "UNKNOWN"}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Slot</dt>
          <dd>{event.slot}</dd>
        </div>
      </dl>

      <p
        data-testid="realtime-coverage"
        className={
          event.coverage.complete
            ? "mt-4 text-xs text-slate-400"
            : "mt-4 text-xs text-amber-200"
        }
      >
        {event.coverage.provider} coverage ·{" "}
        {event.coverage.complete ? "complete" : "incomplete"} ·{" "}
        {event.coverage.commitment}
        {event.coverage.unknown_fields.length > 0
          ? ` · UNKNOWN: ${event.coverage.unknown_fields.join(", ")}`
          : ""}
      </p>

      {event.warnings.length > 0 ? (
        <ul role="alert" className="mt-3 list-disc pl-5 text-xs text-amber-200">
          {event.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function StatusOverview({ status }: { status: RealtimeTrackingStatus }) {
  const counters = [
    {
      label: "Subscribed Smart Wallets",
      value: status.subscribed_wallets.length,
    },
    { label: "Received events", value: status.received },
    { label: "Recorded events", value: status.recorded },
    { label: "Duplicate events", value: status.duplicates },
    { label: "Processed-only events", value: status.processed_only },
    { label: "Skipped unsubscribed", value: status.skipped_unsubscribed },
    { label: "Reconnects", value: status.reconnects },
    { label: "Decision events", value: status.decision_events },
  ] as const;

  return (
    <section
      data-testid="realtime-status"
      className="rounded-3xl border border-slate-700 bg-slate-900/80 p-6"
    >
      <h2 className="text-2xl font-semibold text-white">
        Live tracking observability
      </h2>
      <p className="mt-2 max-w-3xl text-sm text-slate-300">
        Reconnects, lag, duplicates, received events, and processing latency
        stay visible.{" "}
        {status.last_run_at
          ? `Last poll completed ${timestamp(status.last_run_at)}.`
          : "No tracking poll has been recorded yet."}
      </p>
      <ul data-testid="realtime-counters" className="mt-4 flex flex-wrap gap-3">
        {counters.map((counter) => (
          <li
            key={counter.label}
            className="rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-xs text-slate-300"
          >
            <span className="block uppercase tracking-wide text-slate-500">
              {counter.label}
            </span>
            {counter.value}
          </li>
        ))}
        <li className="rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-xs text-slate-300">
          <span className="block uppercase tracking-wide text-slate-500">
            Max chain-to-observed lag
          </span>
          {seconds(status.max_lag_seconds)}
        </li>
        <li className="rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-xs text-slate-300">
          <span className="block uppercase tracking-wide text-slate-500">
            Processing latency
          </span>
          {seconds(status.processing_latency_seconds)}
        </li>
      </ul>
      {status.subscribed_wallets.length > 0 ? (
        <ul className="mt-4 flex flex-wrap gap-2 text-xs text-slate-400">
          {status.subscribed_wallets.map((wallet) => (
            <li key={wallet} className="break-all font-mono">
              {wallet}
            </li>
          ))}
        </ul>
      ) : null}
      {status.warnings.length > 0 ? (
        <ul role="alert" className="mt-4 list-disc pl-5 text-sm text-amber-200">
          {status.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export default function RealtimePage() {
  const [feed, setFeed] = useState<RealtimeWalletEvent[]>([]);
  const [status, setStatus] = useState<RealtimeTrackingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const [nextStatus, nextFeed] = await Promise.all([
          fetchRealtimeStatus(controller.signal),
          fetchRealtimeFeed(FEED_LIMIT, controller.signal),
        ]);
        setStatus(nextStatus);
        setFeed(nextFeed);
        setError(null);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError("The live Wallet feed is unavailable.");
      }
    }
    void load();
    const timer = setInterval(() => {
      void load();
    }, REFRESH_INTERVAL_MS);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [reloadToken]);

  async function poll(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    try {
      await pollRealtimeTracking();
      setReloadToken((token) => token + 1);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The realtime tracking poll failed.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-14 sm:px-10">
      <SiteNav />
      <header className="mb-10">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
          Confirmed real time
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">
          Smart Wallet live feed
        </h1>
        <p className="mt-3 max-w-3xl text-slate-300">
          Only Wallets currently in the SMART_WALLET Registry state are tracked.
          Confirmed buys, sells, transfers in, and transfers out normalize into
          the same movement forms as historical activity. Processed commitment
          is shown for observation but can never trigger a downstream decision,
          and signature/slot idempotency suppresses reconnect and replay
          duplicates.
        </p>
        <form data-testid="realtime-poll-form" onSubmit={poll} className="mt-5">
          <button
            type="submit"
            disabled={pending}
            className="rounded-lg border border-cyan-400/60 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50"
          >
            {pending ? "Polling…" : "Poll the live stream"}
          </button>
        </form>
      </header>

      {error ? (
        <div
          role="alert"
          data-testid="realtime-unavailable"
          className="mb-6 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-amber-100"
        >
          {error}
        </div>
      ) : null}

      {status ? (
        <div className="mb-8">
          <StatusOverview status={status} />
        </div>
      ) : null}

      <section>
        <h2 className="text-2xl font-semibold text-white">Live feed</h2>
        {feed.length === 0 ? (
          <p
            data-testid="realtime-empty"
            className="mt-4 text-sm text-slate-400"
          >
            No Wallet activity has been recorded yet. Poll the confirmed stream
            to populate the feed.
          </p>
        ) : (
          <div data-testid="realtime-feed" className="mt-4 space-y-4">
            {feed.map((event) => (
              <RealtimeEventCard key={event.idempotency_key} event={event} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
