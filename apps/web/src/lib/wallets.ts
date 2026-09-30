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
