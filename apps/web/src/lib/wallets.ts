export const apiUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type WalletMovementType =
  | "BUY"
  | "SELL"
  | "TRANSFER_IN"
  | "TRANSFER_OUT"
  | "AIRDROP"
  | "UNKNOWN";

export type WalletActivity = {
  signature: string;
  slot: number;
  chain_time: string;
  observed_at: string;
  succeeded: boolean;
  fee_usd: number;
  movements: Array<{
    token_address: string;
    movement_type: WalletMovementType;
    quantity: number;
    notional_usd: number | null;
    venue: string | null;
    evidence: string[];
  }>;
};

type WalletPnl = {
  realized_usd: number;
  unrealized_usd: number | null;
  total_usd: number | null;
};

export type Distribution = {
  count: number;
  average: number | null;
  median: number | null;
  minimum: number | null;
  maximum: number | null;
};

export type WalletBehavior = {
  address: string;
  as_of: string;
  metric_definitions: string[];
  windows: Array<{
    period: "24H" | "7D" | "30D" | "90D" | "ALL_TIME";
    starts_at: string | null;
    as_of: string;
    definition: string;
    realized_pnl_usd: number;
    unrealized_pnl_usd: number | null;
    total_pnl_usd: number | null;
    roi_percent: number | null;
    win_rate_percent: number | null;
    trade_count: number;
    winning_tokens: number;
    losing_tokens: number;
    average_win_usd: number | null;
    median_win_usd: number | null;
    average_loss_usd: number | null;
    median_loss_usd: number | null;
    profit_factor: number | null;
    max_drawdown_usd: number;
    largest_win_usd: number | null;
    largest_loss_usd: number | null;
    position_size_usd: Distribution;
    holding_time_seconds: Distribution;
    consistency: {
      profit_concentration: {
        top_one_percent: number | null;
        top_three_percent: number | null;
        top_five_percent: number | null;
      };
      profitable_days: number;
      profitable_weeks: number;
      profitable_months: number;
    };
    meme: {
      entry_count: number;
      early_entry_rate_percent: number | null;
      creation_to_entry_latency_seconds: Distribution;
      entry_market_cap_usd: Distribution;
      entry_liquidity_usd: Distribution;
      sub_100k_entry_rate_percent: number | null;
      sub_500k_entry_rate_percent: number | null;
      rug_exposure_rate_percent: number | null;
      dead_token_exposure_rate_percent: number | null;
      migration_success_rate_percent: number | null;
      token_activity_per_active_day: number | null;
    };
    unknowns: string[];
  }>;
  classifications: Array<{
    name: string;
    description: string;
    evidence: string[];
    score_effect: "NONE";
  }>;
  flags: Array<{
    name: string;
    wording: string;
    evidence: string[];
    confidence: "LOW" | "MEDIUM" | "HIGH";
    coverage: Array<{
      source: string;
      complete: boolean;
      unknown_fields: string[];
    }>;
  }>;
  coverage: Array<{
    source: string;
    complete: boolean;
    unknown_fields: string[];
  }>;
  warnings: string[];
};

type CopyabilityFill = {
  model: "CONSTANT_PRODUCT" | "FIXED_SLIPPAGE";
  confidence: "HIGH" | "LOW";
  liquidity_usd: number | null;
  pool_address: string | null;
  venue: string | null;
  snapshot_at: string | null;
  source_evidence: string[];
  fallback_assumptions: string[];
  venue_fee_sol: number;
};

export type WalletCopyability = {
  address: string;
  as_of: string;
  configuration_version: number | null;
  delays_ms: number[];
  follower_sizes_sol: number[];
  outcomes: Array<{
    token_address: string;
    leader_entry_signature: string;
    leader_exit_signature: string;
    follower_delay_ms: number;
    follower_size_sol: number;
    leader_roi_percent: number;
    follower_roi_percent: number | null;
    copy_decay_percent: number | null;
    status: "FILLED" | "REJECTED";
    entry_fill: CopyabilityFill | null;
    exit_fill: CopyabilityFill | null;
    pool_selections: Array<{
      side: "BUY" | "SELL";
      requested_at: string;
      pool_address: string | null;
      venue: string | null;
      pool_model:
        | "CONSTANT_PRODUCT"
        | "DLMM"
        | "CONCENTRATED"
        | "UNKNOWN"
        | null;
      snapshot_at: string | null;
      source_evidence: string[];
      status: "SELECTED" | "UNKNOWN" | "STALE";
      warning: string | null;
    }>;
    coverage: {
      token_address: string;
      entry_requested_at: string;
      exit_requested_at: string;
      complete: boolean;
      unknown_fields: string[];
      warnings: string[];
    };
    warnings: string[];
  }>;
  coverage: {
    provider: string;
    complete: boolean;
    freshness_seconds: number;
    unknown_fields: string[];
    warnings: string[];
  };
  warnings: string[];
};

export type WalletAccounting = {
  address: string;
  as_of: string;
  source_transactions: WalletActivity[];
  lots: Array<{
    lot_id: string;
    token_address: string;
    source_signature: string;
    acquired_at: string;
    initial_quantity: number;
    remaining_quantity: number;
    unit_cost_usd: number;
    contaminated: boolean;
    contamination_reason: "TRANSFER_IN" | "AIRDROP" | null;
  }>;
  holdings: Array<{
    token_address: string;
    quantity: number;
    contaminated_quantity: number;
    clean_quantity: number;
    cost_basis_usd: number;
    mark_price_usd: number | null;
  }>;
  pnl: { inclusive: WalletPnl; clean: WalletPnl };
  contamination: Array<{
    token_address: string;
    source_signature: string;
    quantity: number;
    movement_type: "TRANSFER_IN" | "AIRDROP";
    evidence: string[];
  }>;
  failed_transactions: WalletActivity[];
  unknown_movements: Array<{
    signature: string;
    token_address: string;
    movement_type: "UNKNOWN";
    quantity: number;
    evidence: string[];
  }>;
  coverage: Array<{
    provider: string;
    requested_as_of: string;
    as_of_start: string;
    as_of_end: string;
    complete: boolean;
    freshness_seconds: number;
    commitment: string;
    unknown_fields: string[];
    warnings: string[];
  }>;
  mark_price_provenance: Array<{
    token_address: string;
    price_usd: number;
    observed_at: string;
    provider: string;
  }>;
  warnings: string[];
};

export type RegistryState =
  | "CANDIDATE"
  | "WATCHLIST"
  | "SMART_WALLET"
  | "SUSPENDED"
  | "REJECTED";

export type ScoreComponentName =
  | "profitability"
  | "consistency"
  | "copyability"
  | "risk_quality"
  | "entry_quality"
  | "history_quality";

export type LeaderboardSort =
  | "TOTAL_SCORE"
  | "RECENT_ROI"
  | "LONG_TERM_ROI"
  | "RECENT_PNL"
  | "LONG_TERM_PNL";

export type WalletScoreComponent = {
  name: ScoreComponentName;
  score: number | null;
  weight: number;
  weighted_points: number;
  reasons: string[];
  evidence: string[];
  warnings: string[];
  unknowns: string[];
};

export type WalletQualityPeriod = {
  period: "30D" | "ALL_TIME";
  starts_at: string | null;
  total_pnl_usd: number | null;
  realized_pnl_usd: number;
  roi_percent: number | null;
  win_rate_percent: number | null;
  trade_count: number;
  max_drawdown_usd: number;
};

export type WalletScore = {
  address: string;
  as_of: string;
  configuration_id: string;
  configuration_version: number;
  total_score: number;
  recommended_state: RegistryState;
  components: WalletScoreComponent[];
  quality: WalletQualityPeriod[];
  reasons: string[];
  warnings: string[];
  evidence: string[];
  unknowns: string[];
  coverage: Array<{
    source: string;
    complete: boolean;
    unknown_fields: string[];
  }>;
};

export type WalletRegistryTransition = {
  address: string;
  version: number;
  from_state: RegistryState;
  to_state: RegistryState;
  reason: string;
  evidence: string[];
  as_of: string;
  configuration_version: number;
  created_at: string;
};

export type WalletRegistry = {
  address: string;
  state: RegistryState;
  transitions: WalletRegistryTransition[];
};

export type WalletLeaderboardEntry = {
  address: string;
  total_score: number;
  recommended_state: RegistryState;
  as_of: string;
  configuration_version: number;
  quality: WalletQualityPeriod[];
  warnings: string[];
};

export async function fetchWalletScore(
  address: string,
  asOf: string,
  signal?: AbortSignal,
): Promise<WalletScore | null> {
  const response = await fetch(
    `${apiUrl}/wallets/${encodeURIComponent(address)}/score?as_of=${encodeURIComponent(asOf)}`,
    { cache: "no-store", signal },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("Wallet score request failed");
  return (await response.json()) as WalletScore;
}

export async function fetchWalletRegistry(
  address: string,
  signal?: AbortSignal,
): Promise<WalletRegistry | null> {
  const response = await fetch(
    `${apiUrl}/wallets/${encodeURIComponent(address)}/registry`,
    { cache: "no-store", signal },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("Wallet registry request failed");
  return (await response.json()) as WalletRegistry;
}

export async function fetchWalletLeaderboard(
  options: {
    asOf: string;
    sort: LeaderboardSort;
    registryState: RegistryState | "ALL";
    limit: number;
  },
  signal?: AbortSignal,
): Promise<WalletLeaderboardEntry[]> {
  const params = new URLSearchParams({
    as_of: options.asOf,
    sort: options.sort,
    limit: String(options.limit),
  });
  if (options.registryState !== "ALL") {
    params.set("registry_state", options.registryState);
  }
  const response = await fetch(
    `${apiUrl}/wallets/scores?${params.toString()}`,
    {
      cache: "no-store",
      signal,
    },
  );
  if (!response.ok) throw new Error("Wallet leaderboard request failed");
  return (await response.json()) as WalletLeaderboardEntry[];
}
