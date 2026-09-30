import { apiUrl } from "@/lib/tokens";

export { apiUrl };

export type DiscoveryCriterion = {
  criterion: string;
  observed: string;
  threshold: string;
  passed: boolean;
};

export type HistoricalWinnerDiscovery = {
  cohort: {
    cohort_id: string;
    created_from: string;
    created_to: string;
    qualification_as_of: string;
  };
  configuration_id: string;
  configuration_version: number;
  winners: Array<{
    token_address: string;
    token_symbol: string;
    created_at: string;
    initial_market_cap_usd: number | null;
    initial_market_cap_observed_at: string | null;
    peak_market_cap_usd: number | null;
    peak_market_cap_observed_at: string | null;
    qualified: boolean;
    qualifying_facts: DiscoveryCriterion[];
  }>;
  early_buyers: Array<{
    wallet_address: string;
    token_address: string;
    chain_time: string;
    amount_tokens: number;
    amount_usd: number | null;
    price_usd: number | null;
    market_cap_usd: number | null;
    liquidity_usd: number | null;
    token_age_seconds: number;
    entry_market_cap_bucket: string;
    venue: string | null;
    signature: string;
    coverage: {
      provider: string;
      complete: boolean;
      unknown_fields: string[];
      warnings: string[];
    };
    entry_evaluation: {
      as_of: string;
      unavailable_facts: string[];
    };
    warnings: string[];
  }>;
  candidate_wallets: Array<{
    wallet_address: string;
    passed: boolean;
    evidence: DiscoveryCriterion[];
  }>;
};
