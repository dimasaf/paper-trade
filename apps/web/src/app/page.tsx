"use client";

import { useEffect, useState } from "react";

import SiteNav from "@/components/SiteNav";

const healthComponentNames = [
  "application",
  "database",
  "redis",
  "worker",
] as const;

type HealthComponentName = (typeof healthComponentNames)[number];
type ComponentState = "ready" | "unavailable";

type ComponentHealth = {
  status: ComponentState;
  message: string;
};

type HealthDocument = {
  status: "ready" | "degraded";
  checked_at: string;
  correlation_id: string;
  components: Record<HealthComponentName, ComponentHealth>;
};

const componentLabels: Record<HealthComponentName, string> = {
  application: "Application",
  database: "PostgreSQL",
  redis: "Redis",
  worker: "ARQ worker",
};

const componentEntries = healthComponentNames.map(
  (name) => [name, componentLabels[name]] as const,
);

function displayStatus(status: "ready" | "degraded" | ComponentState): string {
  if (status === "ready") return "Ready";
  if (status === "degraded") return "Degraded";
  return "Unavailable";
}

export default function OverviewPage() {
  const [health, setHealth] = useState<HealthDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const unavailableComponents = health
    ? componentEntries.filter(
        ([name]) => health.components[name]?.status !== "ready",
      )
    : [];

  useEffect(() => {
    const controller = new AbortController();
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

    async function loadHealth() {
      try {
        const response = await fetch(`${apiUrl}/health`, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Health request failed");
        setHealth((await response.json()) as HealthDocument);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError("The API health document is unavailable.");
      }
    }

    void loadHealth();
    return () => controller.abort();
  }, []);

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-14 sm:px-10">
      <SiteNav />
      <header className="mb-10 flex flex-col gap-3">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
          Paper Trade
        </p>
        <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
          Research workspace
        </h1>
        <p className="max-w-2xl text-base leading-7 text-slate-300">
          Local infrastructure readiness for Solana Smart Wallet research and
          Paper Trading.
        </p>
      </header>

      <section className="rounded-3xl border border-slate-700 bg-slate-900/80 p-6 shadow-2xl shadow-cyan-950/20 sm:p-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-white">
              Workspace health
            </h2>
            <p className="mt-1 text-sm text-slate-400">
              Each dependency is checked independently through the backend
              health interface.
            </p>
          </div>
          <span
            data-testid="overall-status"
            className={`rounded-full px-4 py-2 text-sm font-semibold ${
              health?.status === "ready"
                ? "bg-emerald-400/15 text-emerald-300"
                : "bg-amber-400/15 text-amber-200"
            }`}
          >
            {health
              ? displayStatus(health.status)
              : error
                ? "Degraded"
                : "Checking"}
          </span>
        </div>

        {error ? (
          <div
            role="alert"
            className="mb-4 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-5 text-amber-100"
          >
            <p className="font-semibold">API unavailable</p>
            <p className="mt-1 text-sm text-amber-100/80">{error}</p>
          </div>
        ) : null}

        {health?.status === "degraded" ? (
          <div
            role="alert"
            className="mb-4 rounded-2xl border border-rose-500/40 bg-rose-500/10 p-5 text-rose-100"
          >
            <p className="font-semibold">Workspace degraded</p>
            <ul className="mt-2 space-y-1 text-sm text-rose-100/80">
              {unavailableComponents.map(([name, label]) => (
                <li key={name}>
                  {label} is unavailable —{" "}
                  {health.components[name]?.message ?? "No result returned"}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          {health
            ? componentEntries.map(([name, label]) => {
                const component = health.components[name] ?? {
                  status: "unavailable" as const,
                  message: "No health result was returned",
                };
                return (
                  <article
                    key={name}
                    className="rounded-2xl border border-slate-700 bg-slate-950/70 p-5"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <h3 className="font-semibold text-white">{label}</h3>
                      <span
                        data-testid={`${name}-status`}
                        className={
                          component.status === "ready"
                            ? "text-emerald-300"
                            : "text-rose-300"
                        }
                      >
                        {displayStatus(component.status)}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-400">
                      {component.message}
                    </p>
                  </article>
                );
              })
            : null}
        </div>

        {health ? (
          <footer className="mt-6 flex flex-wrap justify-between gap-2 border-t border-slate-800 pt-5 text-xs text-slate-500">
            <span>Checked {new Date(health.checked_at).toLocaleString()}</span>
            <span>Correlation {health.correlation_id}</span>
          </footer>
        ) : null}
      </section>
    </main>
  );
}
