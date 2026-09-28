"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const sectionLabels = {
  token: "Token",
  wallet: "Wallet",
  cluster: "Cluster",
  signal: "Signal",
  paper_trading: "Paper Trading",
  risk: "Risk",
  execution: "Execution",
} as const;

type SectionName = keyof typeof sectionLabels;
type ResearchConfiguration = Record<SectionName, unknown>;

type ConfigurationVersion = {
  id: string;
  version: number;
  created_at: string;
  configuration: ResearchConfiguration;
};

type ValidationDetail = {
  msg?: string;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function SettingsPage() {
  const [active, setActive] = useState<ConfigurationVersion | null>(null);
  const [history, setHistory] = useState<ConfigurationVersion[]>([]);
  const [editor, setEditor] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    async function loadSettings() {
      try {
        const [activeResponse, historyResponse] = await Promise.all([
          fetch(`${apiUrl}/research-configurations/active`, {
            cache: "no-store",
            signal: controller.signal,
          }),
          fetch(`${apiUrl}/research-configurations`, {
            cache: "no-store",
            signal: controller.signal,
          }),
        ]);
        if (!activeResponse.ok || !historyResponse.ok) {
          throw new Error("Research configuration request failed");
        }
        const activeDocument =
          (await activeResponse.json()) as ConfigurationVersion;
        setActive(activeDocument);
        setEditor(JSON.stringify(activeDocument.configuration, null, 2));
        setHistory((await historyResponse.json()) as ConfigurationVersion[]);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError") {
          return;
        }
        setError("Research settings are unavailable.");
      }
    }

    void loadSettings();
    return () => controller.abort();
  }, []);

  async function saveNewVersion() {
    setError(null);
    setNotice(null);
    let configuration: ResearchConfiguration;
    try {
      configuration = JSON.parse(editor) as ResearchConfiguration;
    } catch {
      setError("Configuration must be valid JSON.");
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${apiUrl}/research-configurations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ configuration }),
      });
      if (!response.ok) {
        const document = (await response.json()) as {
          detail?: ValidationDetail[] | string;
        };
        const detail = Array.isArray(document.detail)
          ? document.detail
              .map((item) => item.msg)
              .filter(Boolean)
              .join("; ")
          : document.detail;
        throw new Error(detail || "Configuration could not be saved.");
      }
      const created = (await response.json()) as ConfigurationVersion;
      setActive(created);
      setHistory((current) => [created, ...current]);
      setEditor(JSON.stringify(created.configuration, null, 2));
      setNotice(`Saved immutable version ${created.version}.`);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Configuration could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-14 sm:px-10">
      <nav className="mb-8 flex gap-5 text-sm text-cyan-300">
        <Link href="/">Overview</Link>
        <span aria-current="page" className="text-white">
          Settings
        </span>
      </nav>

      <header className="mb-8">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-300">
          Versioned assumptions
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">
          Research settings
        </h1>
        <p className="mt-3 max-w-3xl text-slate-300">
          Every save creates an immutable version used by later research
          decisions. Previous assumptions remain available for reproduction.
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
      {notice ? (
        <div
          role="status"
          className="mb-6 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-4 text-emerald-100"
        >
          {notice}
        </div>
      ) : null}

      {active ? (
        <>
          <section className="mb-8 rounded-3xl border border-slate-700 bg-slate-900/80 p-6 sm:p-8">
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold text-white">
                  Active version {active.version}
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  {new Date(active.created_at).toLocaleString()} · {active.id}
                </p>
              </div>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              {(Object.keys(sectionLabels) as SectionName[]).map((name) => (
                <article
                  key={name}
                  className="rounded-2xl border border-slate-700 bg-slate-950/70 p-5"
                >
                  <h3 className="font-semibold text-white">
                    {sectionLabels[name]}
                  </h3>
                  <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs leading-5 text-slate-400">
                    {JSON.stringify(active.configuration[name], null, 2)}
                  </pre>
                </article>
              ))}
            </div>
          </section>

          <section className="mb-8 rounded-3xl border border-slate-700 bg-slate-900/80 p-6 sm:p-8">
            <h2 className="text-xl font-semibold text-white">
              Create a new version
            </h2>
            <p className="mt-2 text-sm text-slate-400">
              Edit the complete document. Invalid values and incompatible ranges
              are rejected before a version is created.
            </p>
            <label
              htmlFor="configuration-editor"
              className="mt-5 block text-sm font-medium text-slate-200"
            >
              Research configuration JSON
            </label>
            <textarea
              id="configuration-editor"
              value={editor}
              onChange={(event) => setEditor(event.target.value)}
              rows={24}
              spellCheck={false}
              className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-950 p-4 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-cyan-500"
            />
            <button
              type="button"
              onClick={() => void saveNewVersion()}
              disabled={saving}
              className="mt-4 rounded-xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save new version"}
            </button>
          </section>
        </>
      ) : null}

      <section className="rounded-3xl border border-slate-700 bg-slate-900/80 p-6 sm:p-8">
        <h2 className="text-xl font-semibold text-white">Version history</h2>
        <ol data-testid="configuration-history" className="mt-4 space-y-3">
          {history.map((item) => (
            <li
              key={item.id}
              className="flex flex-wrap justify-between gap-2 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm"
            >
              <span className="font-medium text-slate-200">
                Version {item.version}
              </span>
              <span className="text-slate-500">
                {new Date(item.created_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
