"use client";

import { useParams } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import SiteNav from "@/components/SiteNav";
import { apiUrl, type WalletAccounting } from "@/lib/wallets";

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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!address) return;
    const controller = new AbortController();
    async function loadAccounting() {
      try {
        const response = await fetch(
          `${apiUrl}/wallets/${encodeURIComponent(address)}/accounting`,
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
  }, [address]);

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
