import { apiUrl } from "@/lib/tokens";

export { apiUrl };

export type RealtimeMovementType =
  | "BUY"
  | "SELL"
  | "TRANSFER_IN"
  | "TRANSFER_OUT"
  | "AIRDROP"
  | "UNKNOWN";

export type RealtimeCoverage = {
  provider: string;
  as_of_start: string;
  as_of_end: string;
  complete: boolean;
  commitment: RealtimeCommitment;
  freshness_seconds: number;
  normalization_version: string;
  unknown_fields: string[];
  warnings: string[];
};

export type RealtimeCommitment = "confirmed" | "processed";

export type RealtimeWalletEvent = {
  idempotency_key: string;
  event_id: string;
  wallet_address: string;
  token_address: string;
  movement_type: RealtimeMovementType;
  quantity: number;
  notional_usd: number | null;
  price_usd: number | null;
  venue: string | null;
  signature: string;
  slot: number;
  chain_time: string;
  observed_at: string;
  received_at: string;
  commitment: RealtimeCommitment;
  wallet_score: number | null;
  score_as_of: string;
  eligible_for_decisions: boolean;
  evidence: string[];
  coverage: RealtimeCoverage;
  warnings: string[];
};

export type RealtimeTrackingRun = {
  run_id: string;
  as_of: string;
  started_at: string;
  completed_at: string;
  subscribed_wallets: string[];
  received: number;
  recorded: number;
  duplicates: number;
  processed_only: number;
  skipped_unsubscribed: number;
  reconnects: number;
  max_lag_seconds: number | null;
  processing_latency_seconds: number;
  warnings: string[];
};

export type RealtimeTrackingStatus = {
  as_of: string;
  subscribed_wallets: string[];
  stored_events: number;
  decision_events: number;
  received: number;
  recorded: number;
  duplicates: number;
  processed_only: number;
  skipped_unsubscribed: number;
  reconnects: number;
  max_lag_seconds: number | null;
  processing_latency_seconds: number | null;
  last_run_at: string | null;
  warnings: string[];
};

export async function fetchRealtimeFeed(
  limit: number,
  signal?: AbortSignal,
): Promise<RealtimeWalletEvent[]> {
  const response = await fetch(`${apiUrl}/realtime/feed?limit=${limit}`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) throw new Error("Realtime feed request failed");
  return (await response.json()) as RealtimeWalletEvent[];
}

export async function fetchRealtimeStatus(
  signal?: AbortSignal,
): Promise<RealtimeTrackingStatus> {
  const response = await fetch(`${apiUrl}/realtime/status`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) throw new Error("Realtime status request failed");
  return (await response.json()) as RealtimeTrackingStatus;
}

export async function pollRealtimeTracking(
  signal?: AbortSignal,
): Promise<RealtimeTrackingRun> {
  const response = await fetch(`${apiUrl}/realtime/polls`, {
    method: "POST",
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new Error(`Realtime tracking poll failed (${response.status})`);
  }
  return (await response.json()) as RealtimeTrackingRun;
}
