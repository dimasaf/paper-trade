import { expect, test } from "@playwright/test";

const discovery = {
  cohort: {
    cohort_id: "recorded-september-winners",
    created_from: "2026-09-28T09:00:00Z",
    created_to: "2026-09-28T09:00:00Z",
    qualification_as_of: "2026-09-28T10:00:00Z",
  },
  configuration_id: "00000000-0000-0000-0000-000000000001",
  configuration_version: 1,
  winners: [
    {
      token_address: "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
      token_symbol: "RSWAP",
      created_at: "2026-09-28T09:00:00Z",
      initial_market_cap_usd: 120000,
      initial_market_cap_observed_at: "2026-09-28T09:00:00Z",
      peak_market_cap_usd: 1200000,
      peak_market_cap_observed_at: "2026-09-28T09:50:00Z",
      qualified: true,
      qualifying_facts: [
        {
          criterion: "initial_market_cap_usd",
          observed: "120000",
          threshold: ">= 10000 and <= 500000",
          passed: true,
        },
        {
          criterion: "peak_market_cap_usd",
          observed: "1.2e+06",
          threshold: ">= 1e+06",
          passed: true,
        },
      ],
    },
  ],
  early_buyers: [
    {
      wallet_address: "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
      token_address: "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
      chain_time: "2026-09-28T09:05:00Z",
      amount_tokens: 10,
      amount_usd: null,
      price_usd: null,
      market_cap_usd: 125000,
      liquidity_usd: null,
      token_age_seconds: 300,
      entry_market_cap_bucket: "<= 250000",
      venue: "Raydium",
      signature: "recorded-early-buy-0001",
      coverage: {
        provider: "HELIUS",
        complete: false,
        unknown_fields: ["price_usd", "liquidity_usd"],
        warnings: ["Recorded fixture has incomplete entry coverage"],
      },
      entry_evaluation: {
        as_of: "2026-09-28T09:05:00Z",
        unavailable_facts: [
          "future_peak_market_cap_usd",
          "future_rug_status",
          "future_wallet_quality",
        ],
      },
      warnings: [
        "price_usd is UNKNOWN at the entry as-of time",
        "liquidity_usd is UNKNOWN at the entry as-of time",
      ],
    },
  ],
  candidate_wallets: [
    {
      wallet_address: "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
      passed: true,
      evidence: [
        {
          criterion: "successful_buy",
          observed: "BUY succeeded",
          threshold: "successful BUY",
          passed: true,
        },
      ],
    },
  ],
};

test("Discovery journey shows a fixed winner, its early buyer, unknown coverage, and entry boundary", async ({
  page,
}) => {
  await page.route("**/discovery/historical-winners/latest", async (route) => {
    await route.fulfill({ json: discovery });
  });

  await page.goto("/discovery");

  await expect(
    page.getByRole("heading", { name: "Historical winners and early buyers" }),
  ).toBeVisible();
  await expect(page.getByTestId("historical-winner-cohort")).toContainText(
    "Configuration version 1",
  );
  await expect(page.getByTestId("historical-winners")).toContainText("RSWAP");
  await expect(page.getByTestId("historical-winners")).toContainText(
    "1,200,000",
  );
  await expect(page.getByTestId("early-buyers")).toContainText(
    "recorded-early-buy-0001",
  );
  await expect(page.getByTestId("early-buyers")).toContainText("UNKNOWN");
  await expect(page.getByTestId("entry-boundary")).toContainText(
    "future_peak_market_cap_usd",
  );
  await expect(page.getByTestId("candidate-wallets")).toContainText("PASS");
});
