import { apiUrl } from "@/lib/tokens";

export { apiUrl };

export type FunnelStageName =
  | "TOKENS_ANALYZED"
  | "WALLETS_FOUND"
  | "CANDIDATES"
  | "PROFITABLE"
  | "CONSISTENT"
  | "COPYABLE"
  | "SMART_WALLET";

export type FunnelOutcome = "INCLUDED" | "EXCLUDED" | "UNKNOWN";

export type FunnelReason = {
  code: string;
  outcome: FunnelOutcome;
  message: string;
  observed: string | null;
  threshold: string | null;
  configuration_version: number;
  as_of: string;
};

export type FunnelMember = {
  subject: string;
  outcome: FunnelOutcome;
  reasons: FunnelReason[];
  evidence: string[];
  coverage: Array<{
    source: string;
    complete: boolean;
    unknown_fields: string[];
  }>;
  warnings: string[];
};

export type FunnelStage = {
  name: FunnelStageName;
  subject: "TOKEN" | "WALLET";
  as_of: string;
  configuration_version: number;
  evaluated: number;
  included: number;
  excluded: number;
  unknown: number;
  members: FunnelMember[];
};

export type DiscoveryFunnelCohort = {
  cohort_id: string;
  created_from: string;
  created_to: string;
  qualification_as_of: string;
};

export type DiscoveryFunnelRequest = {
  cohort: DiscoveryFunnelCohort;
  as_of: string;
};

export type DiscoveryFunnelRun = {
  run_id: string;
  cohort: DiscoveryFunnelCohort;
  as_of: string;
  configuration_id: string;
  configuration_version: number;
  status: "RUNNING" | "COMPLETED" | "FAILED";
  started_at: string;
  completed_at: string | null;
  error: string | null;
  stages: FunnelStage[];
  warnings: string[];
};

export const funnelStageLabels: Record<FunnelStageName, string> = {
  TOKENS_ANALYZED: "Tokens analyzed",
  WALLETS_FOUND: "Wallets found",
  CANDIDATES: "Candidates",
  PROFITABLE: "Profitable",
  CONSISTENT: "Consistent",
  COPYABLE: "Copyable",
  SMART_WALLET: "Smart Wallets",
};

export async function fetchLatestDiscoveryFunnel(
  signal?: AbortSignal,
): Promise<DiscoveryFunnelRun | null> {
  const response = await fetch(`${apiUrl}/discovery/funnel/latest`, {
    cache: "no-store",
    signal,
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("Discovery funnel request failed");
  return (await response.json()) as DiscoveryFunnelRun;
}

export async function startDiscoveryFunnel(
  request: DiscoveryFunnelRequest,
  signal?: AbortSignal,
): Promise<DiscoveryFunnelRun> {
  const response = await fetch(`${apiUrl}/discovery/funnel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    signal,
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`Discovery funnel run failed (${response.status})`);
  }
  return (await response.json()) as DiscoveryFunnelRun;
}
