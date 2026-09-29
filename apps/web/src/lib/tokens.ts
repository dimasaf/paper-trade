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

export const apiUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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
