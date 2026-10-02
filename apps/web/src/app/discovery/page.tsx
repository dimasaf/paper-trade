"use client";

import { type FormEvent, useEffect, useState } from "react";

import SiteNav from "@/components/SiteNav";
import {
  apiUrl,
  fetchLatestDiscoveryFunnel,
  funnelStageLabels,
  startDiscoveryFunnel,
  type DiscoveryFunnelRun,
  type FunnelMember,
  type FunnelStage,
} from "@/lib/discovery-funnel";
import type { HistoricalWinnerDiscovery } from "@/lib/historical-winners";

type FunnelView =
  | "loading"
  | "empty"
  | "running"
  | "failed"
  | "completed"
  | "unavailable";

const cohortFields = [
  {
    name: "cohort_id",
    label: "Cohort id",
    placeholder: "recorded-september-winners",
  },
  {
    name: "created_from",
    label: "Token created from",
    placeholder: "2026-09-28T09:00:00Z",
  },
  {
    name: "created_to",
    label: "Token created to",
    placeholder: "2026-09-28T09:00:00Z",
  },
  {
    name: "qualification_as_of",
    label: "Winner qualification as of",
    placeholder: "2026-09-28T10:00:00Z",
  },
  {
    name: "as_of",
    label: "Wallet gates as of",
    placeholder: "2026-09-28T10:00:00Z",
  },
] as const;

type CohortFieldName = (typeof cohortFields)[number]["name"];
type CohortForm = Record<CohortFieldName, string>;

const emptyCohort: CohortForm = {
  cohort_id: "",
  created_from: "",
  created_to: "",
  qualification_as_of: "",
  as_of: "",
};

const outcomeStyles: Record<FunnelMember["outcome"], string> = {
  INCLUDED: "text-emerald-300",
  EXCLUDED: "text-rose-300",
  UNKNOWN: "text-amber-200",
};

function value(amount: number | null): string {
  return amount === null ? "UNKNOWN" : `$${amount.toLocaleString()}`;
}

function timestamp(date: string): string {
  return new Date(date).toLocaleString();
}

function viewOf(run: DiscoveryFunnelRun | null): FunnelView {
  if (run === null) return "empty";
  if (run.status === "RUNNING") return "running";
  if (run.status === "FAILED") return "failed";
  return "completed";
}

function FunnelMemberCard({ member }: { member: FunnelMember }) {
  return (
    <article className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
      <div className="flex flex-wrap justify-between gap-2">
        <p className="break-all font-mono text-xs text-cyan-300">
          {member.subject}
        </p>
        <p className={`text-xs font-semibold ${outcomeStyles[member.outcome]}`}>
          {member.outcome}
        </p>
      </div>
      <ul className="mt-2 space-y-2 text-xs text-slate-300">
        {member.reasons.map((reason, index) => (
          <li key={`${reason.code}-${index}`}>
            <span className="font-mono text-[11px] text-slate-400">
              {reason.code}
            </span>
            {" · "}
            {reason.message}
            {reason.observed ? ` · observed ${reason.observed}` : ""}
            {reason.threshold ? ` · rule ${reason.threshold}` : ""}
            <span className="text-slate-500">
              {` · config v${reason.configuration_version} · as of ${timestamp(reason.as_of)}`}
            </span>
          </li>
        ))}
      </ul>
      {member.coverage.length > 0 ? (
        <ul className="mt-2 space-y-1 text-xs">
          {member.coverage.map((entry) => (
            <li
              key={entry.source}
              className={entry.complete ? "text-slate-400" : "text-amber-200"}
            >
              {entry.source} coverage{" "}
              {entry.complete ? "complete" : "incomplete"}
              {entry.unknown_fields.length > 0
                ? ` · UNKNOWN: ${entry.unknown_fields.join(", ")}`
                : ""}
            </li>
          ))}
        </ul>
      ) : null}
      {member.warnings.length > 0 ? (
        <ul role="alert" className="mt-2 list-disc pl-4 text-xs text-amber-200">
          {member.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function FunnelStageCard({ stage }: { stage: FunnelStage }) {
  return (
    <details
      data-testid={`funnel-stage-${stage.name.toLowerCase()}`}
      className="rounded-2xl border border-slate-700 bg-slate-950/60"
    >
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-white">
        {funnelStageLabels[stage.name]} · {stage.evaluated} evaluated ·{" "}
        <span className="font-normal text-emerald-300">
          {stage.included} included
        </span>{" "}
        ·{" "}
        <span className="font-normal text-rose-300">
          {stage.excluded} excluded
        </span>{" "}
        ·{" "}
        <span className="font-normal text-amber-200">
          {stage.unknown} unknown
        </span>
      </summary>
      <div className="space-y-3 px-4 pb-4">
        <p className="text-xs text-slate-500">
          {`Gate decisions as of ${timestamp(stage.as_of)} under configuration version ${stage.configuration_version}.`}
        </p>
        {stage.members.map((member) => (
          <FunnelMemberCard key={member.subject} member={member} />
        ))}
      </div>
    </details>
  );
}

function CompletedFunnel({ run }: { run: DiscoveryFunnelRun }) {
  return (
    <div className="mt-5 space-y-4">
      <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4 text-sm text-slate-300">
        <p>
          {`Completed ${timestamp(run.completed_at ?? run.started_at)} · configuration version ${run.configuration_version}`}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          {`run ${run.run_id} · cohort ${run.cohort.cohort_id} · Tokens created ${timestamp(
            run.cohort.created_from,
          )} to ${timestamp(run.cohort.created_to)} · winners qualified as of ${timestamp(
            run.cohort.qualification_as_of,
          )} · Wallet gates as of ${timestamp(run.as_of)}`}
        </p>
      </div>

      <ul data-testid="funnel-counts" className="flex flex-wrap gap-3">
        {run.stages.map((stage) => (
          <li
            key={stage.name}
            className="rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-xs text-slate-300"
          >
            <span className="block uppercase tracking-wide text-slate-500">
              {funnelStageLabels[stage.name]}
            </span>
            {`${stage.evaluated} evaluated · ${stage.included} included · ${stage.excluded} excluded · ${stage.unknown} unknown`}
          </li>
        ))}
      </ul>

      {run.warnings.length > 0 ? (
        <ul
          data-testid="funnel-warnings"
          role="alert"
          className="list-disc pl-5 text-sm text-amber-200"
        >
          {run.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}

      <div data-testid="funnel-stages" className="space-y-3">
        {run.stages.map((stage) => (
          <FunnelStageCard key={stage.name} stage={stage} />
        ))}
      </div>
    </div>
  );
}

export default function DiscoveryPage() {
  const [discovery, setDiscovery] = useState<HistoricalWinnerDiscovery | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [funnel, setFunnel] = useState<DiscoveryFunnelRun | null>(null);
  const [funnelView, setFunnelView] = useState<FunnelView>("loading");
  const [funnelError, setFunnelError] = useState<string | null>(null);
  const [cohort, setCohort] = useState<CohortForm>(emptyCohort);
  const [formError, setFormError] = useState<string | null>(null);
  const [runPending, setRunPending] = useState(false);

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
    async function loadFunnel() {
      try {
        const run = await fetchLatestDiscoveryFunnel(controller.signal);
        setFunnel(run);
        setFunnelView(viewOf(run));
        setFunnelError(run?.error ?? null);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setFunnelView("unavailable");
        setFunnelError("The Discovery funnel is unavailable.");
      }
    }
    void loadDiscovery();
    void loadFunnel();
    return () => controller.abort();
  }, []);

  async function runFunnel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (Object.values(cohort).some((entry) => entry.trim() === "")) {
      setFormError("Every cohort field is required to run discovery.");
      return;
    }
    setFormError(null);
    setRunPending(true);
    try {
      const started = await startDiscoveryFunnel({
        cohort: {
          cohort_id: cohort.cohort_id.trim(),
          created_from: cohort.created_from.trim(),
          created_to: cohort.created_to.trim(),
          qualification_as_of: cohort.qualification_as_of.trim(),
        },
        as_of: cohort.as_of.trim(),
      });
      setFunnel(started);
      setFunnelView(viewOf(started));
      setFunnelError(started.error);
    } catch (reason) {
      const message =
        reason instanceof Error
          ? reason.message
          : "The Discovery funnel run failed.";
      const latest = await fetchLatestDiscoveryFunnel().catch(() => undefined);
      setFunnel(latest ?? null);
      setFunnelError(latest?.error ?? message);
      setFunnelView(latest === undefined ? "unavailable" : "failed");
    } finally {
      setRunPending(false);
    }
  }

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

      <section
        data-testid="discovery-funnel"
        className="mb-10 rounded-3xl border border-slate-700 bg-slate-900/80 p-6"
      >
        <h2 className="text-2xl font-semibold text-white">Discovery funnel</h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-300">
          One fixed cohort evaluated from analyzed Tokens through candidates,
          profitability, consistency, Copyability, and Registry acceptance.
          Every exclusion carries a machine-readable code, a human-readable
          reason, its configuration version, and its as-of time. Results that
          recorded evidence cannot establish stay visible as UNKNOWN instead of
          counting as failures, and partial provider coverage stays on the
          Wallet.
        </p>

        <form
          data-testid="funnel-cohort-form"
          onSubmit={runFunnel}
          className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
        >
          {cohortFields.map((field) => (
            <label
              key={field.name}
              className="flex flex-col gap-1 text-xs text-slate-300"
            >
              {field.label}
              <input
                data-testid={`funnel-${field.name}`}
                className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-white"
                placeholder={field.placeholder}
                value={cohort[field.name]}
                onChange={(event) =>
                  setCohort((current) => ({
                    ...current,
                    [field.name]: event.target.value,
                  }))
                }
              />
            </label>
          ))}
          <button
            type="submit"
            disabled={runPending}
            className="self-end rounded-lg border border-cyan-400/60 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50"
          >
            {runPending ? "Running discovery…" : "Run discovery funnel"}
          </button>
        </form>

        {formError ? (
          <p
            role="alert"
            data-testid="funnel-form-error"
            className="mt-3 text-sm text-rose-200"
          >
            {formError}
          </p>
        ) : null}

        <div className="mt-5">
          {funnelView === "loading" ? (
            <p data-testid="funnel-loading" className="text-sm text-slate-400">
              Loading the latest discovery funnel…
            </p>
          ) : null}
          {funnelView === "empty" ? (
            <p data-testid="funnel-empty" className="text-sm text-slate-400">
              No discovery funnel run has been recorded yet. Choose a fixed
              cohort and run discovery.
            </p>
          ) : null}
          {funnelView === "running" ? (
            <p data-testid="funnel-running" className="text-sm text-amber-200">
              {funnel
                ? `Discovery funnel run ${funnel.run_id} started ${timestamp(
                    funnel.started_at,
                  )} is still running.`
                : "A discovery funnel run is still running."}
            </p>
          ) : null}
          {funnelView === "failed" ? (
            <div
              role="alert"
              data-testid="funnel-failed"
              className="rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-100"
            >
              {`The discovery funnel run failed. ${funnelError ?? "No error detail was recorded."}`}
            </div>
          ) : null}
          {funnelView === "unavailable" ? (
            <div
              role="alert"
              data-testid="funnel-unavailable"
              className="rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-100"
            >
              {funnelError ?? "The Discovery funnel is unavailable."}
            </div>
          ) : null}
          {funnelView === "completed" && funnel ? (
            <CompletedFunnel run={funnel} />
          ) : null}
        </div>
      </section>

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
