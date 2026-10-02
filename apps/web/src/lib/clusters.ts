import { apiUrl } from "@/lib/tokens";
import type { ContributingIndependentCount } from "@/lib/wallets";

export { apiUrl };

export type ClusterStatus = "ACTIVE" | "SUPERSEDED" | "INVALIDATED";
export type ClusterMovementType = "BUY" | "SELL";
export type ClusterScoreWeighting = "EQUAL" | "WALLET_SCORE" | "TOTAL_SOL";

export type ClusterCoverage = {
  source: string;
  complete: boolean;
  unknown_fields: string[];
};

export type ClusterActivity = {
  event_id: string;
  wallet_address: string;
  token_address: string;
  movement_type: ClusterMovementType;
  quantity: number;
  sol_amount: number;
  notional_usd: number | null;
  wallet_score: number | null;
  score_as_of: string | null;
  signature: string;
  slot: number;
  chain_time: string;
  observed_at: string;
  commitment: "confirmed" | "processed";
  eligible_for_decisions: boolean;
  evidence: string[];
  coverage: {
    provider: string;
    as_of_start: string;
    as_of_end: string;
    complete: boolean;
    commitment: string;
    freshness_seconds: number;
    normalization_version: string;
    unknown_fields: string[];
    warnings: string[];
  };
};

export type ClusterWalletContribution = {
  wallet_address: string;
  wallet_score: number | null;
  score_as_of: string | null;
  total_sol: number;
  buy_count: number;
  first_buy_at: string;
  last_buy_at: string;
  independent: boolean;
  evidence: string[];
};

export type WalletCluster = {
  token_address: string;
  status: ClusterStatus;
  status_reason: string;
  superseded_by_version: number | null;
  as_of: string;
  configuration_id: string;
  configuration_version: number;
  window_seconds: number;
  score_weighting: ClusterScoreWeighting;
  raw_wallet_count: number;
  contributing_independent_wallet_count: number;
  average_wallet_score: number | null;
  weighted_wallet_score: number | null;
  total_sol: number;
  total_notional_usd: number | null;
  buy_count: number;
  first_buy_at: string | null;
  last_buy_at: string | null;
  window_span_seconds: number | null;
  buy_velocity_per_minute: number | null;
  wallets: ClusterWalletContribution[];
  contributing_independent: ContributingIndependentCount;
  activity: ClusterActivity[];
  evidence: string[];
  unknowns: string[];
  warnings: string[];
  coverage: ClusterCoverage[];
};

export type StoredWalletCluster = {
  token_address: string;
  version: number;
  created_at: string;
  cluster: WalletCluster;
};

export type WalletClusterDetail = {
  token_address: string;
  current: StoredWalletCluster;
  history: StoredWalletCluster[];
};

export type ClusterDetection = {
  as_of: string;
  configuration_id: string;
  configuration_version: number;
  received: number;
  recorded: number;
  duplicates: number;
  created_clusters: number;
  updated_clusters: number;
  invalidated_clusters: number;
  unchanged_clusters: number;
  clusters: StoredWalletCluster[];
  warnings: string[];
};

export async function fetchLiveClusters(
  asOf: string,
  signal?: AbortSignal,
): Promise<StoredWalletCluster[]> {
  const response = await fetch(
    `${apiUrl}/clusters?as_of=${encodeURIComponent(asOf)}`,
    { cache: "no-store", signal },
  );
  if (!response.ok) throw new Error("Live clusters request failed");
  return (await response.json()) as StoredWalletCluster[];
}

export async function fetchClusterDetail(
  tokenAddress: string,
  asOf: string,
  signal?: AbortSignal,
): Promise<WalletClusterDetail | null> {
  const response = await fetch(
    `${apiUrl}/clusters/${encodeURIComponent(tokenAddress)}?as_of=${encodeURIComponent(asOf)}`,
    { cache: "no-store", signal },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("Cluster detail request failed");
  return (await response.json()) as WalletClusterDetail;
}

export async function detectClusters(
  asOf: string,
  signal?: AbortSignal,
): Promise<ClusterDetection> {
  const response = await fetch(
    `${apiUrl}/clusters/detections?as_of=${encodeURIComponent(asOf)}`,
    { method: "POST", cache: "no-store", signal },
  );
  if (!response.ok) {
    throw new Error(`Cluster detection failed (${response.status})`);
  }
  return (await response.json()) as ClusterDetection;
}
