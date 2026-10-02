"use client";

import { type FormEvent, useEffect, useState } from "react";

import SiteNav from "@/components/SiteNav";
import {
  detectClusters,
  fetchClusterDetail,
  fetchLiveClusters,
  type ClusterActivity,
  type StoredWalletCluster,
  type WalletCluster,
  type WalletClusterDetail,
} from "@/lib/clusters";

const REFRESH_INTERVAL_MS = 10000;

function timestamp(value: string | null): string {
  return value === null ? "UNKNOWN" : new Date(value).toLocaleString();
}

function sol(value: number): string {
  return `${value.toLocaleString()} SOL`;
}

function score(value: number | null): string {
  return value === null ? "UNKNOWN" : value.toFixed(2);
}

function seconds(value: number | null): string {
  return value === null ? "UNKNOWN" : `${value.toFixed(1)}s`;
}

function velocity(value: number | null): string {
  return value === null ? "UNKNOWN" : `${value.toFixed(2)} buys/min`;
}

function statusClass(status: WalletCluster["status"]): string {
  if (status === "ACTIVE") return "text-xs font-semibold text-emerald-300";
  if (status === "SUPERSEDED") return "text-xs font-semibold text-cyan-300";
  return "text-xs font-semibold text-amber-200";
}

function ClusterCard({
  stored,
  onSelect,
  selected,
}: {
  stored: StoredWalletCluster;
  onSelect: (token: string) => void;
  selected: boolean;
}) {
  const cluster = stored.cluster;
  return (
    <article
      data-testid={`cluster-${cluster.token_address}`}
      className={
        selected
          ? "rounded-2xl border border-cyan-400/60 bg-cyan-500/10 p-5"
          : "rounded-2xl border border-slate-700 bg-slate-900/80 p-5"
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="break-all font-mono text-xs text-cyan-300">
            {cluster.token_address}
          </h3>
          <p className="mt-1 text-xs text-slate-400">
            version {stored.version} · configuration v
            {cluster.configuration_version}
          </p>
        </div>
        <span className={statusClass(cluster.status)}>{cluster.status}</span>
      </div>

      <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-xs text-slate-500">
            Wallets (raw / independent)
          </dt>
          <dd>
            {cluster.raw_wallet_count} /{" "}
            {cluster.contributing_independent_wallet_count}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Average / weighted quality</dt>
          <dd>
            {score(cluster.average_wallet_score)} /{" "}
            {score(cluster.weighted_wallet_score)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Total bought</dt>
          <dd>{sol(cluster.total_sol)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Buy velocity</dt>
          <dd>{velocity(cluster.buy_velocity_per_minute)}</dd>
        </div>
      </dl>

      <p className="mt-3 text-xs text-slate-400">
        First buy {timestamp(cluster.first_buy_at)} · last buy{" "}
        {timestamp(cluster.last_buy_at)} · window{" "}
        {seconds(cluster.window_span_seconds)} of {cluster.window_seconds}s
      </p>

      <button
        type="button"
        onClick={() => onSelect(cluster.token_address)}
        className="mt-3 rounded-lg border border-cyan-400/60 bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-100"
      >
        {selected ? "Hide detail" : "Show detail"}
      </button>
    </article>
  );
}

function EvidenceList({ cluster }: { cluster: WalletCluster }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 text-sm text-slate-300">
      <h3 className="font-semibold text-white">Evidence</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {cluster.evidence.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function RelationshipList({ cluster }: { cluster: WalletCluster }) {
  const count = cluster.contributing_independent;
  return (
    <div
      data-testid="cluster-relationships"
      className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 text-sm text-slate-300"
    >
      <h3 className="font-semibold text-white">
        Contributing-independent relationships
      </h3>
      <p className="mt-2">
        Raw Wallet count {count.raw_wallet_count} · contributing-independent{" "}
        {count.contributing_independent_wallet_count} at or above{" "}
        {count.confidence_threshold} confidence.
      </p>
      <ul className="mt-3 space-y-2">
        {count.groups.map((group) => (
          <li key={group.representative}>
            <span className="break-all font-mono text-xs text-slate-400">
              {group.wallets.join(", ")}
            </span>
            <p className="mt-1 text-xs text-slate-400">{group.reason}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ActivityTimeline({ activity }: { activity: ClusterActivity[] }) {
  return (
    <div
      data-testid="cluster-timeline"
      className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 text-sm text-slate-300"
    >
      <h3 className="font-semibold text-white">Qualifying timing</h3>
      <ol className="mt-3 space-y-3">
        {activity.map((event) => (
          <li
            key={`${event.signature}-${event.wallet_address}`}
            className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"
          >
            <p className="font-mono text-xs text-slate-400">
              {event.signature}
            </p>
            <p className="mt-1">
              {event.movement_type} · {sol(event.sol_amount)} · Wallet{" "}
              <span className="break-all font-mono text-xs">
                {event.wallet_address}
              </span>
            </p>
            <p className="mt-1 text-xs text-slate-400">
              chain {timestamp(event.chain_time)} · observed{" "}
              {timestamp(event.observed_at)} · {event.commitment}
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}

function CoverageList({ cluster }: { cluster: WalletCluster }) {
  return (
    <div
      data-testid="cluster-coverage"
      className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 text-sm text-slate-300"
    >
      <h3 className="font-semibold text-white">Coverage</h3>
      <ul className="mt-2 space-y-1">
        {cluster.coverage.map((item) => (
          <li key={item.source}>
            {item.source} · {item.complete ? "complete" : "incomplete"}
            {item.unknown_fields.length > 0
              ? ` · UNKNOWN: ${item.unknown_fields.join(", ")}`
              : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ClusterDetailView({ detail }: { detail: WalletClusterDetail }) {
  const cluster = detail.current.cluster;
  return (
    <section className="mt-8 space-y-6" data-testid="cluster-detail">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
          Cluster detail
        </p>
        <h2 className="mt-2 break-all font-mono text-lg text-white">
          {cluster.token_address}
        </h2>
        <p className="mt-1 text-sm text-slate-400">
          <span className={statusClass(cluster.status)}>{cluster.status}</span>{" "}
          · version {detail.current.version} · {cluster.status_reason}
        </p>
      </header>

      {cluster.warnings.length > 0 ? (
        <div
          role="alert"
          className="rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-100"
        >
          <strong>Cluster coverage warnings</strong>
          <ul className="mt-2 list-disc pl-5">
            {cluster.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <EvidenceList cluster={cluster} />
        <RelationshipList cluster={cluster} />
        <CoverageList cluster={cluster} />
        <div
          data-testid="cluster-contributions"
          className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 text-sm text-slate-300"
        >
          <h3 className="font-semibold text-white">Wallet contributions</h3>
          <ul className="mt-3 space-y-3">
            {cluster.wallets.map((wallet) => (
              <li key={wallet.wallet_address}>
                <span className="break-all font-mono text-xs text-slate-400">
                  {wallet.wallet_address}
                </span>
                <p className="mt-1">
                  score {score(wallet.wallet_score)} · {sol(wallet.total_sol)} ·{" "}
                  {wallet.buy_count} buy(s) ·{" "}
                  {wallet.independent ? "independent" : "collapsed"}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <ActivityTimeline activity={cluster.activity} />

      {cluster.unknowns.length > 0 ? (
        <div
          data-testid="cluster-unknowns"
          className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5 text-sm text-amber-100"
        >
          <h3 className="font-semibold">Unknown Cluster evidence</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {cluster.unknowns.map((unknown) => (
              <li key={unknown}>{unknown}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div
        data-testid="cluster-history"
        className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 text-sm text-slate-300"
      >
        <h3 className="font-semibold text-white">Version history</h3>
        <ol className="mt-3 space-y-3">
          {detail.history.map((stored) => (
            <li
              key={stored.version}
              className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"
            >
              <p className={statusClass(stored.cluster.status)}>
                v{stored.version} · {stored.cluster.status}
                {stored.cluster.superseded_by_version !== null
                  ? ` → v${stored.cluster.superseded_by_version}`
                  : ""}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                {stored.cluster.status_reason}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                recorded {timestamp(stored.created_at)} · as of{" "}
                {timestamp(stored.cluster.as_of)}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export default function ClustersPage() {
  const [clusters, setClusters] = useState<StoredWalletCluster[]>([]);
  const [detail, setDetail] = useState<WalletClusterDetail | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const [asOf] = useState(() => new Date().toISOString());

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        setClusters(await fetchLiveClusters(asOf, controller.signal));
        if (selected) {
          setDetail(
            await fetchClusterDetail(selected, asOf, controller.signal),
          );
        }
        setError(null);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError("The live Smart Wallet Clusters are unavailable.");
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
  }, [asOf, selected, reloadToken]);

  async function detect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    try {
      const detection = await detectClusters(asOf);
      setMessage(
        `Detected ${detection.created_clusters} new, ${detection.updated_clusters} updated, ` +
          `${detection.invalidated_clusters} invalidated, ${detection.duplicates} duplicate ` +
          "movements.",
      );
      setReloadToken((token) => token + 1);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The Cluster detection run failed.",
      );
    } finally {
      setPending(false);
    }
  }

  function select(token: string) {
    setDetail(null);
    setSelected((current) => (current === token ? null : token));
  }

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-14 sm:px-10">
      <SiteNav />
      <header className="mb-10">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
          Cluster Detector
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">
          Live Smart Wallet Clusters
        </h1>
        <p className="mt-3 max-w-3xl text-slate-300">
          A Cluster is at least N Contributing-independent Wallets buying the
          same Token inside a configured window. Related Wallets collapse into
          one confirmation, duplicate realtime events never inflate counts or
          volume, and a materially changed Cluster supersedes its previous
          version while an expired or threshold-lost Cluster is invalidated in
          place.
        </p>
        <form
          data-testid="cluster-detect-form"
          onSubmit={detect}
          className="mt-5"
        >
          <button
            type="submit"
            disabled={pending}
            className="rounded-lg border border-cyan-400/60 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50"
          >
            {pending ? "Detecting…" : "Detect Clusters"}
          </button>
        </form>
      </header>

      {error ? (
        <div
          role="alert"
          data-testid="clusters-unavailable"
          className="mb-6 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-amber-100"
        >
          {error}
        </div>
      ) : null}

      {message ? (
        <div
          data-testid="cluster-detection-summary"
          className="mb-6 rounded-2xl border border-cyan-500/30 bg-cyan-500/5 p-4 text-sm text-cyan-100"
        >
          {message}
        </div>
      ) : null}

      <section>
        <h2 className="text-2xl font-semibold text-white">Live clusters</h2>
        {clusters.length === 0 ? (
          <p
            data-testid="clusters-empty"
            className="mt-4 text-sm text-slate-400"
          >
            No Cluster currently meets the configured thresholds. Run detection
            over the confirmed Smart Wallet activity to populate the feed.
          </p>
        ) : (
          <div data-testid="clusters-list" className="mt-4 space-y-4">
            {clusters.map((stored) => (
              <ClusterCard
                key={stored.cluster.token_address}
                stored={stored}
                selected={selected === stored.cluster.token_address}
                onSelect={select}
              />
            ))}
          </div>
        )}
      </section>

      {detail ? <ClusterDetailView detail={detail} /> : null}
    </main>
  );
}
