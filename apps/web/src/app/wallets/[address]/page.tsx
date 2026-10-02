"use client";

import { useParams } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import SiteNav from "@/components/SiteNav";
import {
  apiUrl,
  type WalletAccounting,
  type WalletBehavior,
  type WalletCopyability,
} from "@/lib/wallets";

function amount(value: number | null): string {
  return value === null ? "UNKNOWN" : `$${value.toFixed(2)}`;
}

function timestamp(value: string): string {
  return new Date(value).toLocaleString();
}

export default function WalletDetailPage() {
  const params = useParams<{ address: string }>();
  const address = params?.address ?? "";
  const [accounting, setAccounting] = useState<WalletAccounting | null>(null);
  const [behavior, setBehavior] = useState<WalletBehavior | null>(null);
  const [copyability, setCopyability] = useState<WalletCopyability | null>(
    null,
  );
  const [asOf] = useState(() => new Date().toISOString());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!address) return;
    const controller = new AbortController();
    async function loadAccounting() {
      try {
        const response = await fetch(
          `${apiUrl}/wallets/${encodeURIComponent(address)}/accounting?as_of=${encodeURIComponent(asOf)}`,
          { cache: "no-store", signal: controller.signal },
        );
        if (response.status === 404) {
          setError("This Wallet has no recorded history.");
          return;
        }
        if (!response.ok) throw new Error("Wallet accounting request failed");
        setAccounting((await response.json()) as WalletAccounting);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError("The Wallet detail could not be loaded.");
      }
    }
    void loadAccounting();
    return () => controller.abort();
  }, [address, asOf]);

  useEffect(() => {
    if (!address) return;
    const controller = new AbortController();
    async function loadBehavior() {
      try {
        const response = await fetch(
          `${apiUrl}/wallets/${encodeURIComponent(address)}/behavior?as_of=${encodeURIComponent(asOf)}`,
          { cache: "no-store", signal: controller.signal },
        );
        if (response.ok) setBehavior((await response.json()) as WalletBehavior);
      } catch (reason) {
        if (!(reason instanceof DOMException && reason.name === "AbortError"))
          setBehavior(null);
      }
    }
    void loadBehavior();
    return () => controller.abort();
  }, [address, asOf]);

  useEffect(() => {
    if (!address) return;
    const controller = new AbortController();
    async function loadCopyability() {
      try {
        const response = await fetch(
          `${apiUrl}/wallets/${encodeURIComponent(address)}/copyability?as_of=${encodeURIComponent(asOf)}`,
          { cache: "no-store", signal: controller.signal },
        );
        if (response.ok)
          setCopyability((await response.json()) as WalletCopyability);
      } catch (reason) {
        if (!(reason instanceof DOMException && reason.name === "AbortError"))
          setCopyability(null);
      }
    }
    void loadCopyability();
    return () => controller.abort();
  }, [address, asOf]);

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
      {accounting ? (
        <>
          <header className="mb-10">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
              Point-in-time history
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">
              Wallet accounting
            </h1>
            <p
              data-testid="wallet-address"
              className="mt-3 break-all font-mono text-xs text-slate-400"
            >
              {accounting.address}
            </p>
            <p className="mt-2 text-sm text-slate-400">
              As of {timestamp(accounting.as_of)}
            </p>
          </header>

          {accounting.warnings.length > 0 ? (
            <section
              role="alert"
              className="mb-8 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-5 text-amber-100"
            >
              <h2 className="font-semibold">
                Coverage and accounting warnings
              </h2>
              <ul className="mt-2 list-disc pl-5 text-sm">
                {accounting.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </section>
          ) : null}

          {behavior ? <BehaviorSummary behavior={behavior} /> : null}
          {copyability ? (
            <CopyabilitySummary copyability={copyability} />
          ) : null}

          <section className="grid gap-4 md:grid-cols-2">
            <PnlCard
              label="Inclusive PnL"
              pnl={accounting.pnl.inclusive}
              testId="inclusive-pnl"
            />
            <PnlCard
              label="Clean PnL"
              pnl={accounting.pnl.clean}
              testId="clean-pnl"
            />
          </section>

          <Section title="Holdings" testId="wallet-holdings">
            {accounting.holdings.length === 0 ? (
              <p>No remaining holdings.</p>
            ) : (
              accounting.holdings.map((holding) => (
                <div
                  key={holding.token_address}
                  className="rounded-xl border border-slate-800 bg-slate-950/60 p-4"
                >
                  <p className="break-all font-mono text-xs text-slate-400">
                    {holding.token_address}
                  </p>
                  <p className="mt-2">
                    {holding.quantity} units · {holding.clean_quantity} clean ·{" "}
                    {holding.contaminated_quantity} contaminated
                  </p>
                  <p className="mt-1 text-sm text-slate-400">
                    Cost basis {amount(holding.cost_basis_usd)} · mark{" "}
                    {amount(holding.mark_price_usd)}
                  </p>
                </div>
              ))
            )}
          </Section>

          <Section title="FIFO lots" testId="wallet-lots">
            {accounting.lots.map((lot) => (
              <div
                key={lot.lot_id}
                className="rounded-xl border border-slate-800 bg-slate-950/60 p-4"
              >
                <p className="font-mono text-xs text-slate-300">
                  {lot.source_signature}
                </p>
                <p className="mt-1 text-sm">
                  {lot.remaining_quantity} / {lot.initial_quantity} remaining at{" "}
                  {amount(lot.unit_cost_usd)} per unit
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  {lot.contaminated
                    ? `Contaminated: ${lot.contamination_reason}`
                    : "Clean acquisition"}
                </p>
              </div>
            ))}
          </Section>

          <Section
            title="Contamination evidence"
            testId="contamination-evidence"
          >
            {accounting.contamination.length === 0 ? (
              <p>None.</p>
            ) : (
              accounting.contamination.map((item) => (
                <div
                  key={`${item.source_signature}-${item.token_address}`}
                  className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4"
                >
                  <p>
                    {item.movement_type} · {item.quantity} units
                  </p>
                  <p className="mt-1 font-mono text-xs text-slate-400">
                    {item.source_signature}
                  </p>
                </div>
              ))
            )}
          </Section>

          <Section title="Failed transactions" testId="failed-transactions">
            {accounting.failed_transactions.length === 0 ? (
              <p>None.</p>
            ) : (
              accounting.failed_transactions.map((activity) => (
                <p
                  key={activity.signature}
                  className="font-mono text-xs text-rose-200"
                >
                  {activity.signature}
                </p>
              ))
            )}
          </Section>
          <Section title="Unknown movements" testId="unknown-movements">
            {accounting.unknown_movements.length === 0 ? (
              <p>None.</p>
            ) : (
              accounting.unknown_movements.map((movement) => (
                <p
                  key={movement.signature}
                  className="font-mono text-xs text-amber-200"
                >
                  {movement.movement_type} · {movement.signature}
                </p>
              ))
            )}
          </Section>
          <Section title="Provider coverage" testId="wallet-coverage">
            {accounting.coverage.map((coverage) => (
              <p key={coverage.provider} className="text-sm">
                {coverage.provider} · {coverage.commitment} ·{" "}
                {coverage.complete ? "complete" : "incomplete"} ·{" "}
                {coverage.unknown_fields.join(", ") ||
                  "no declared unknown fields"}
              </p>
            ))}
          </Section>
          <Section title="Source transactions" testId="source-transactions">
            {accounting.source_transactions.map((activity) => (
              <div
                key={activity.signature}
                className="rounded-xl border border-slate-800 bg-slate-950/60 p-4"
              >
                <p className="font-mono text-xs">{activity.signature}</p>
                <p className="mt-1 text-sm">
                  {activity.succeeded ? "Succeeded" : "Failed"} · slot{" "}
                  {activity.slot} · fee {amount(activity.fee_usd)}
                </p>
              </div>
            ))}
          </Section>
        </>
      ) : null}
    </main>
  );
}

function BehaviorSummary({ behavior }: { behavior: WalletBehavior }) {
  return (
    <section className="mb-8 space-y-6" data-testid="wallet-behavior">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
          Behavior and consistency
        </p>
        <h2 className="mt-2 text-2xl font-semibold">
          Recorded behavior metrics
        </h2>
      </header>
      <div
        data-testid="behavior-definitions"
        className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5"
      >
        <h3 className="font-semibold">Metric definitions</h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
          {behavior.metric_definitions.map((definition) => (
            <li key={definition}>{definition}</li>
          ))}
        </ul>
      </div>
      <div className="grid gap-4 lg:grid-cols-2" data-testid="behavior-windows">
        {behavior.windows.map((window) => (
          <article
            key={window.period}
            className="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-5"
          >
            <h3 className="font-semibold">{window.period} window</h3>
            <p className="mt-1 text-xs text-slate-400">{window.definition}</p>
            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <Metric label="PnL" value={amount(window.total_pnl_usd)} />
              <Metric
                label="Realized PnL"
                value={amount(window.realized_pnl_usd)}
              />
              <Metric
                label="Unrealized PnL"
                value={amount(window.unrealized_pnl_usd)}
              />
              <Metric label="ROI" value={percent(window.roi_percent)} />
              <Metric
                label="Win rate"
                value={percent(window.win_rate_percent)}
              />
              <Metric
                label="Closed trades"
                value={String(window.trade_count)}
              />
              <Metric
                label="Winning / losing Tokens"
                value={`${window.winning_tokens} / ${window.losing_tokens}`}
              />
              <Metric
                label="Profit factor"
                value={number(window.profit_factor)}
              />
              <Metric
                label="Max drawdown"
                value={amount(window.max_drawdown_usd)}
              />
              <Metric
                label="Average / median win"
                value={`${amount(window.average_win_usd)} / ${amount(window.median_win_usd)}`}
              />
              <Metric
                label="Average / median loss"
                value={`${amount(window.average_loss_usd)} / ${amount(window.median_loss_usd)}`}
              />
              <Metric
                label="Largest win / loss"
                value={`${amount(window.largest_win_usd)} / ${amount(window.largest_loss_usd)}`}
              />
              <Metric
                label="Median position size"
                value={amount(window.position_size_usd.median)}
              />
              <Metric
                label="Median holding time"
                value={seconds(window.holding_time_seconds.median)}
              />
            </dl>
            <p className="mt-4 text-sm text-slate-300">
              Profit concentration: top one{" "}
              {percent(window.consistency.profit_concentration.top_one_percent)}
              , top three{" "}
              {percent(
                window.consistency.profit_concentration.top_three_percent,
              )}
              , top five{" "}
              {percent(
                window.consistency.profit_concentration.top_five_percent,
              )}
              .
            </p>
            <p className="mt-1 text-sm text-slate-300">
              Profitable days/weeks/months: {window.consistency.profitable_days}{" "}
              / {window.consistency.profitable_weeks} /{" "}
              {window.consistency.profitable_months}.
            </p>
            <p className="mt-4 text-sm text-slate-300">
              Meme-specific: {percent(window.meme.early_entry_rate_percent)}{" "}
              early entries ·{" "}
              {seconds(window.meme.creation_to_entry_latency_seconds.median)}{" "}
              creation-to-entry latency ·{" "}
              {amount(window.meme.entry_market_cap_usd.average)} entry market
              cap · {amount(window.meme.entry_liquidity_usd.average)} entry
              liquidity · {percent(window.meme.sub_100k_entry_rate_percent)}{" "}
              entries below $100k ·{" "}
              {percent(window.meme.sub_500k_entry_rate_percent)} entries below
              $500k · {percent(window.meme.rug_exposure_rate_percent)} rug
              exposure · {percent(window.meme.dead_token_exposure_rate_percent)}{" "}
              dead Token exposure ·{" "}
              {percent(window.meme.migration_success_rate_percent)} migration
              success · {number(window.meme.token_activity_per_active_day)}{" "}
              Tokens per active day.
            </p>
            {window.unknowns.length > 0 ? (
              <ul className="mt-3 list-disc pl-5 text-xs text-amber-200">
                {window.unknowns.map((unknown) => (
                  <li key={unknown}>{unknown}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <section
          data-testid="behavior-classifications"
          className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5"
        >
          <h3 className="font-semibold">Descriptive classifications</h3>
          {behavior.classifications.length === 0 ? (
            <p className="mt-2 text-sm text-slate-400">
              No classification has sufficient recorded evidence.
            </p>
          ) : (
            <ul className="mt-2 space-y-3 text-sm">
              {behavior.classifications.map((classification) => (
                <li key={classification.name}>
                  <strong>{classification.name}</strong> ·{" "}
                  {classification.description}
                  <p className="mt-1 text-slate-400">
                    Evidence: {classification.evidence.join(" ")}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section
          data-testid="behavior-risk-flags"
          className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5"
        >
          <h3 className="font-semibold">Evidence-backed review flags</h3>
          {behavior.flags.length === 0 ? (
            <p className="mt-2 text-sm text-slate-400">
              No review flags from recorded evidence.
            </p>
          ) : (
            <ul className="mt-2 space-y-3 text-sm">
              {behavior.flags.map((flag) => (
                <li key={flag.name}>
                  <strong>{flag.name}</strong> · {flag.wording}
                  <p className="mt-1 text-slate-300">
                    Confidence: {flag.confidence}. Evidence:{" "}
                    {flag.evidence.join(" ")}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    Coverage:{" "}
                    {flag.coverage
                      .map(
                        (item) =>
                          `${item.source} (${item.complete ? "complete" : "incomplete"})`,
                      )
                      .join(", ")}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </section>
  );
}

function CopyabilitySummary({
  copyability,
}: {
  copyability: WalletCopyability;
}) {
  const scenarios = copyability.delays_ms.flatMap((delay) =>
    copyability.follower_sizes_sol.map((size) => {
      const outcomes = copyability.outcomes.filter(
        (outcome) =>
          outcome.follower_delay_ms === delay &&
          outcome.follower_size_sol === size,
      );
      const filled = outcomes.filter(
        (outcome) =>
          outcome.follower_roi_percent !== null &&
          outcome.copy_decay_percent !== null,
      );
      const average = (values: number[]) =>
        values.length === 0
          ? null
          : values.reduce((total, value) => total + value, 0) / values.length;
      return {
        delay,
        size,
        outcomes,
        leader: average(filled.map((outcome) => outcome.leader_roi_percent)),
        follower: average(
          filled.map((outcome) => outcome.follower_roi_percent as number),
        ),
        decay: average(
          filled.map((outcome) => outcome.copy_decay_percent as number),
        ),
        rejected: outcomes.length - filled.length,
        coverageUnknowns: [
          ...new Set(
            outcomes.flatMap((outcome) => outcome.coverage.unknown_fields),
          ),
        ],
        models: [...new Set(filled.map((outcome) => outcome.entry_fill?.model))]
          .filter(Boolean)
          .join(", "),
        confidence: [
          ...new Set(filled.map((outcome) => outcome.entry_fill?.confidence)),
        ]
          .filter(Boolean)
          .join(", "),
      };
    }),
  );
  return (
    <section className="mb-8" data-testid="wallet-copyability">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
          Copyability and Copy Decay
        </p>
        <h2 className="mt-2 text-2xl font-semibold">Follower outcomes</h2>
        <p className="mt-1 text-sm text-slate-400">
          Each follower entry and exit uses the recorded pool state after its
          configured delay.
        </p>
      </header>
      {copyability.warnings.length > 0 ? (
        <div
          role="alert"
          className="mt-4 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-100"
        >
          <strong>Copyability coverage warnings</strong>
          <ul className="mt-2 list-disc pl-5">
            {copyability.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <div
        data-testid="copyability-coverage"
        className="mt-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-300"
      >
        <strong>
          Pool coverage · {copyability.coverage.provider} ·{" "}
          {copyability.coverage.complete ? "complete" : "incomplete"}
        </strong>
        {copyability.coverage.unknown_fields.length > 0 ? (
          <p className="mt-1 text-xs text-slate-400">
            UNKNOWN: {copyability.coverage.unknown_fields.join(", ")}
          </p>
        ) : null}
      </div>
      <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-950/60 text-slate-400">
            <tr>
              <th className="p-3">Delay</th>
              <th className="p-3">Follower size</th>
              <th className="p-3">Leader ROI</th>
              <th className="p-3">Follower ROI</th>
              <th className="p-3">Copy Decay</th>
              <th className="p-3">Coverage</th>
              <th className="p-3">Fill evidence</th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map((scenario) => (
              <tr
                key={`${scenario.delay}-${scenario.size}`}
                className="border-t border-slate-800"
              >
                <td className="p-3">{scenario.delay} ms</td>
                <td className="p-3">{scenario.size} SOL</td>
                <td className="p-3">{percent(scenario.leader)}</td>
                <td className="p-3">{percent(scenario.follower)}</td>
                <td className="p-3">{percent(scenario.decay)}</td>
                <td className="p-3 text-xs text-slate-400">
                  {scenario.coverageUnknowns.length
                    ? scenario.coverageUnknowns.join(", ")
                    : "complete"}
                </td>
                <td className="p-3 text-xs text-slate-400">
                  {scenario.models || "No fill"} ·{" "}
                  {scenario.confidence || "UNKNOWN"}
                  {scenario.rejected ? ` · ${scenario.rejected} rejected` : ""}
                  <details className="mt-2 text-slate-300">
                    <summary>Pool evidence</summary>
                    {scenario.outcomes.map((outcome) => (
                      <div
                        key={`${outcome.leader_entry_signature}-${outcome.leader_exit_signature}`}
                        className="mt-2"
                      >
                        {outcome.pool_selections.map((selection) => (
                          <p key={selection.side}>
                            {selection.side} · {selection.venue ?? "UNKNOWN"} ·{" "}
                            {selection.pool_address ?? "no pool"} ·{" "}
                            {selection.snapshot_at
                              ? timestamp(selection.snapshot_at)
                              : selection.status}
                            {selection.source_evidence.length
                              ? ` · ${selection.source_evidence.join(" ")}`
                              : ""}
                            {selection.warning ? ` · ${selection.warning}` : ""}
                          </p>
                        ))}
                        {[outcome.entry_fill, outcome.exit_fill]
                          .filter(
                            (fill): fill is NonNullable<typeof fill> =>
                              fill !== null,
                          )
                          .flatMap((fill) => fill.fallback_assumptions)
                          .map((assumption) => (
                            <p key={assumption}>Assumption: {assumption}</p>
                          ))}
                      </div>
                    ))}
                  </details>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-slate-400">{label}</dt>
      <dd>{value}</dd>
    </>
  );
}

function number(value: number | null): string {
  return value === null ? "UNKNOWN" : value.toFixed(2);
}

function percent(value: number | null): string {
  return value === null ? "UNKNOWN" : `${value.toFixed(2)}%`;
}

function seconds(value: number | null): string {
  return value === null ? "UNKNOWN" : `${value.toFixed(0)} seconds`;
}

function PnlCard({
  label,
  pnl,
  testId,
}: {
  label: string;
  pnl: WalletAccounting["pnl"]["clean"];
  testId: string;
}) {
  return (
    <section
      data-testid={testId}
      className="rounded-2xl border border-cyan-500/30 bg-cyan-500/5 p-5"
    >
      <h2 className="font-semibold text-cyan-100">{label}</h2>
      <p className="mt-3 text-2xl font-semibold">{amount(pnl.total_usd)}</p>
      <p className="mt-2 text-sm text-slate-300">
        Realized {amount(pnl.realized_usd)} · Unrealized{" "}
        {amount(pnl.unrealized_usd)}
      </p>
    </section>
  );
}

function Section({
  title,
  testId,
  children,
}: {
  title: string;
  testId: string;
  children: ReactNode;
}) {
  return (
    <section className="mt-8">
      <h2 className="text-xl font-semibold text-white">{title}</h2>
      <div data-testid={testId} className="mt-3 space-y-3 text-slate-200">
        {children}
      </div>
    </section>
  );
}
