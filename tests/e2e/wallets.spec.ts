import { expect, test } from "@playwright/test";

const walletAddress = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1";
const tokenAddress = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr";

const accounting = {
  address: walletAddress,
  as_of: "2026-09-28T10:00:00Z",
  source_transactions: [
    {
      signature: "recorded-wallet-buy-0001",
      slot: 314159266,
      chain_time: "2026-09-28T09:05:00Z",
      observed_at: "2026-09-28T09:05:10Z",
      succeeded: true,
      fee_usd: 1,
      movements: [
        {
          token_address: tokenAddress,
          movement_type: "BUY",
          quantity: 10,
          notional_usd: 20,
          venue: "Raydium",
          evidence: ["recorded Helius SWAP"],
        },
      ],
    },
    {
      signature: "recorded-wallet-failed-buy-0001",
      slot: 314159271,
      chain_time: "2026-09-28T09:30:00Z",
      observed_at: "2026-09-28T09:30:10Z",
      succeeded: false,
      fee_usd: 0.5,
      movements: [
        {
          token_address: tokenAddress,
          movement_type: "BUY",
          quantity: 99,
          notional_usd: 99,
          venue: null,
          evidence: ["recorded failed Helius SWAP"],
        },
      ],
    },
  ],
  trades: [],
  lots: [
    {
      lot_id: "recorded-wallet-buy-0001:0",
      token_address: tokenAddress,
      source_signature: "recorded-wallet-buy-0001",
      acquired_at: "2026-09-28T09:05:00Z",
      initial_quantity: 10,
      remaining_quantity: 3,
      unit_cost_usd: 2.1,
      contaminated: false,
      contamination_reason: null,
    },
  ],
  holdings: [
    {
      token_address: tokenAddress,
      quantity: 8,
      contaminated_quantity: 5,
      clean_quantity: 3,
      cost_basis_usd: 9.3,
      mark_price_usd: 5,
    },
  ],
  pnl: {
    inclusive: { realized_usd: 21.5, unrealized_usd: 30.7, total_usd: 52.2 },
    clean: { realized_usd: 21.5, unrealized_usd: 5.7, total_usd: 27.2 },
  },
  contamination: [
    {
      token_address: tokenAddress,
      source_signature: "recorded-wallet-airdrop-0001",
      quantity: 5,
      movement_type: "AIRDROP",
      evidence: ["recorded Helius token transfer from mint authority"],
    },
  ],
  failed_transactions: [
    {
      signature: "recorded-wallet-failed-buy-0001",
      slot: 314159271,
      chain_time: "2026-09-28T09:30:00Z",
      observed_at: "2026-09-28T09:30:10Z",
      succeeded: false,
      fee_usd: 0.5,
      movements: [],
    },
  ],
  unknown_movements: [
    {
      trade_id: "recorded-wallet-unknown-0001:0",
      signature: "recorded-wallet-unknown-0001",
      slot: 314159272,
      chain_time: "2026-09-28T09:35:00Z",
      observed_at: "2026-09-28T09:35:10Z",
      token_address: tokenAddress,
      movement_type: "UNKNOWN",
      quantity: 1,
      notional_usd: null,
      fee_usd: 0,
      venue: null,
      succeeded: true,
      evidence: ["recorded Helius instruction could not be classified"],
    },
  ],
  coverage: [
    {
      provider: "HELIUS",
      requested_as_of: "2026-09-28T10:00:00Z",
      as_of_start: "2026-09-28T09:00:00Z",
      as_of_end: "2026-09-28T09:50:00Z",
      complete: false,
      freshness_seconds: 30,
      commitment: "confirmed",
      unknown_fields: ["pre_2026-09-28T09:00:00Z_history"],
      warnings: ["Recorded fixture has no earlier history"],
    },
  ],
  mark_price_provenance: [
    {
      token_address: tokenAddress,
      price_usd: 5,
      observed_at: "2026-09-28T09:50:00Z",
      provider: "DEXSCREENER",
    },
  ],
  warnings: ["Recorded fixture has no earlier history"],
};

test("Wallet detail shows FIFO accounting, contamination, failed and unknown history, and coverage", async ({
  page,
}) => {
  await page.route("**/wallets/**/accounting*", async (route) => {
    await route.fulfill({ json: accounting });
  });

  await page.goto(`/wallets/${walletAddress}`);

  await expect(
    page.getByRole("heading", { name: "Wallet accounting" }),
  ).toBeVisible();
  await expect(page.getByTestId("wallet-address")).toContainText(walletAddress);
  await expect(page.getByTestId("inclusive-pnl")).toContainText("52.20");
  await expect(page.getByTestId("clean-pnl")).toContainText("27.20");
  await expect(page.getByTestId("wallet-holdings")).toContainText(
    "5 contaminated",
  );
  await expect(page.getByTestId("wallet-lots")).toContainText(
    "recorded-wallet-buy-0001",
  );
  await expect(page.getByTestId("contamination-evidence")).toContainText(
    "AIRDROP",
  );
  await expect(page.getByTestId("failed-transactions")).toContainText(
    "recorded-wallet-failed-buy-0001",
  );
  await expect(page.getByTestId("unknown-movements")).toContainText("UNKNOWN");
  await expect(page.getByTestId("wallet-coverage")).toContainText("HELIUS");
  await expect(page.getByTestId("source-transactions")).toContainText(
    "recorded-wallet-buy-0001",
  );
});
