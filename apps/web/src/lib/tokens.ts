export type ClassificationCriterion = {
  criterion: string;
  threshold: string;
  observed: string;
  passed: boolean;
};

export type Classification = {
  configuration_id: string;
  configuration_version: number;
  passed: boolean;
  criteria: ClassificationCriterion[];
};

export type LaunchProgramEvidence = {
  event_type: string;
  program_id: string;
  event_name: string;
  bonding_curve: string | null;
  bonding_curve_progress_percent: number | null;
  pool: string | null;
};

export type LifecycleTransition = {
  state: string;
  observed_at: string;
  source_event_id: string;
  reason: string;
  graduation_pool_address: string | null;
  evidence?: LaunchProgramEvidence[];
};

export type ProviderCoverage = {
  provider: string;
  as_of_start: string;
  as_of_end: string;
  complete: boolean;
  commitment: string;
  freshness_seconds: number;
  signature: string;
  slot: number;
  normalization_version: string;
  unknown_fields: string[];
  warnings: string[];
};

export type TokenRecord = {
  address: string;
  name: string;
  symbol: string;
  creator: string;
  created_at: string;
  observed_at: string;
  launch_platform: string;
  lifecycle_state: string;
  lifecycle_transitions: LifecycleTransition[];
  classification: Classification;
  coverage: ProviderCoverage[];
};

export type MarketProviderCoverage = {
  provider: "DEXSCREENER" | "GECKOTERMINAL" | "JUPITER";
  requested_as_of: string;
  as_of_start: string;
  as_of_end: string;
  complete: boolean;
  freshness_seconds: number;
  unknown_fields: string[];
  warnings: string[];
};

export type MarketPool = {
  address: string;
  venue: string;
};

export type MarketObservation = {
  observation_id: string;
  address: string;
  observed_at: string;
  price_usd: number | null;
  supply: number | null;
  market_cap_usd: number | null;
  liquidity_usd: number | null;
  volume_24h_usd: number | null;
  pools: MarketPool[];
  coverage: MarketProviderCoverage;
};

export type MarketPeak = {
  value_usd: number;
  observed_at: string;
  observation_id: string;
  provider: string;
};

export type TokenMarketState = {
  address: string;
  as_of: string;
  current: MarketObservation | null;
  observations: MarketObservation[];
  peaks: {
    market_cap_usd: MarketPeak | null;
    liquidity_usd: MarketPeak | null;
  };
  coverage: MarketProviderCoverage[];
  warnings: string[];
};

export const apiUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function coverageWarnings(coverage: ProviderCoverage[]): string[] {
  const warnings: string[] = [];
  for (const entry of coverage) {
    if (!entry.complete) {
      warnings.push(`${entry.provider} coverage is incomplete`);
    }
    for (const field of entry.unknown_fields) {
      warnings.push(`${field} is UNKNOWN`);
    }
    warnings.push(...entry.warnings);
  }
  return warnings;
}
