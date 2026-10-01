import { expect, test } from "@playwright/test";

const walletAddress = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1";
const stackWalletAddress = "4wBqpZM9W7D6h2ZQ5E6o1CymCPG9hrpE7cXkYkKpE8Qm";
const tokenAddress = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr";

const behavior = {
  address: walletAddress,
  as_of: "2026-09-28T10:00:00Z",
  metric_definitions: [
    "Clean FIFO metrics use only evidence available at the requested as-of time.",
  ],
  windows: ["24H", "7D", "30D", "90D", "ALL_TIME"].map((period) => ({
    period,
    starts_at: period === "ALL_TIME" ? null : "2026-09-27T10:00:00Z",
    as_of: "2026-09-28T10:00:00Z",
    definition:
      "Clean FIFO metrics; only facts available at the requested as-of time are included.",
    realized_pnl_usd: 21.5,
    unrealized_pnl_usd: 5.7,
    total_pnl_usd: 27.2,
    roi_percent: 59.39,
    win_rate_percent: 100,
    trade_count: 2,
    winning_tokens: 1,
    losing_tokens: 0,
    average_win_usd: 10.75,
    median_win_usd: 10.75,
    average_loss_usd: null,
    median_loss_usd: null,
    profit_factor: null,
    max_drawdown_usd: 0,
    largest_win_usd: 17.67,
    largest_loss_usd: null,
    position_size_usd: {
      count: 2,
      average: 26,
      median: 26,
      minimum: 21,
      maximum: 31,
    },
    holding_time_seconds: {
      count: 2,
      average: 750,
      median: 750,
      minimum: 600,
      maximum: 900,
    },
    consistency: {
      profit_concentration: {
        top_one_percent: 100,
        top_three_percent: 100,
        top_five_percent: 100,
      },
      profitable_days: 1,
      profitable_weeks: 1,
      profitable_months: 1,
    },
    meme: {
      entry_count: 1,
      early_entry_rate_percent: 100,
      creation_to_entry_latency_seconds: {
        count: 1,
        average: 30,
        median: 30,
        minimum: 30,
        maximum: 30,
      },
      entry_market_cap_usd: {
        count: 1,
        average: 12000,
        median: 12000,
        minimum: 12000,
        maximum: 12000,
      },
      entry_liquidity_usd: {
        count: 1,
        average: 8000,
        median: 8000,
        minimum: 8000,
        maximum: 8000,
      },
      sub_100k_entry_rate_percent: 100,
      sub_500k_entry_rate_percent: 100,
      rug_exposure_rate_percent: 0,
      dead_token_exposure_rate_percent: 0,
      migration_success_rate_percent: 100,
      token_activity_per_active_day: 1,
    },
    unknowns: ["Historical liquidity remains UNKNOWN."],
  })),
  classifications: [
    {
      name: "EARLY_BUYER",
      description: "Descriptive only.",
      evidence: ["Recorded early entry."],
      score_effect: "NONE",
    },
  ],
  flags: [
    {
      name: "RAPID_TOKEN_ENTRY",
      wording: "Timing can warrant review and does not identify intent.",
      evidence: ["30 seconds after recorded creation."],
      confidence: "MEDIUM",
      coverage: [
        {
          source: "RECORDED_MARKET_EVIDENCE",
          complete: false,
          unknown_fields: ["historical_liquidity"],
        },
      ],
    },
  ],
  coverage: [
    {
      source: "RECORDED_MARKET_EVIDENCE",
      complete: false,
      unknown_fields: ["historical_liquidity"],
    },
  ],
  warnings: ["Historical liquidity remains UNKNOWN."],
};

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

test("running Docker stack persists recorded Wallet accounting for the detail journey", async ({
  page,
}) => {
  test.skip(!process.env.STACK_E2E, "Runs against the Docker Compose workspace");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  const recording = {
    history: {
      address: stackWalletAddress,
      activities: [
        {
          signature: "stack-wallet-accounting-buy-0001",
          slot: 314159800,
          chain_time: "2020-01-01T00:00:00Z",
          observed_at: "2020-01-01T00:00:01Z",
          succeeded: true,
          fee_usd: 0,
          movements: [
            {
              token_address: tokenAddress,
              movement_type: "BUY",
              quantity: 10,
              notional_usd: 20,
              venue: "Raydium",
              evidence: ["recorded stack Wallet swap"],
            },
          ],
        },
        {
          signature: "stack-wallet-accounting-observed-after-as-of-0002",
          slot: 314159801,
          chain_time: "2020-01-01T00:00:02Z",
          observed_at: "2100-01-01T00:00:00Z",
          succeeded: true,
          fee_usd: 0,
          movements: [
            {
              token_address: tokenAddress,
              movement_type: "SELL",
              quantity: 10,
              notional_usd: 100,
              venue: "Raydium",
              evidence: ["recorded after requested as-of time"],
            },
          ],
        },
      ],
      coverage: {
        provider: "HELIUS",
        requested_as_of: "2020-01-01T00:00:01Z",
        as_of_start: "2020-01-01T00:00:00Z",
        as_of_end: "2020-01-01T00:00:01Z",
        complete: true,
        freshness_seconds: 1,
        commitment: "confirmed",
        unknown_fields: [],
        warnings: [],
      },
    },
    mark_prices: [
      {
        token_address: tokenAddress,
        price_usd: 5,
        observed_at: "2020-01-01T00:00:02Z",
        provider: "DEXSCREENER",
      },
    ],
  };
  const recordingUrl = `${apiUrl}/wallets/${stackWalletAddress}/accounting/recordings`;
  expect([200, 201]).toContain((await page.request.post(recordingUrl, { data: recording })).status());
  expect((await page.request.post(recordingUrl, { data: recording })).status()).toBe(200);

  const accountingResponse = await page.request.get(
    `${apiUrl}/wallets/${stackWalletAddress}/accounting?as_of=2020-01-01T00:00:03Z`,
  );
  expect(accountingResponse.status()).toBe(200);
  const accounting = await accountingResponse.json();
  expect(accounting.pnl.clean.total_usd).toBe(30);
  expect(accounting.source_transactions).not.toContainEqual(
    expect.objectContaining({
      signature: "stack-wallet-accounting-observed-after-as-of-0002",
    }),
  );

  await page.goto(`/wallets/${stackWalletAddress}`);

  await expect(page.getByRole("heading", { name: "Wallet accounting" })).toBeVisible();
  await expect(page.getByTestId("clean-pnl")).toContainText("30.00");
  await expect(page.getByTestId("wallet-lots")).toContainText(
    "stack-wallet-accounting-buy-0001",
  );
  await expect(page.getByTestId("wallet-coverage")).toContainText("HELIUS");
});

test("Wallet detail shows FIFO accounting, contamination, failed and unknown history, and coverage", async ({
  page,
}) => {
  await page.route("**/wallets/**/accounting*", async (route) => {
    await route.fulfill({ json: accounting });
  });
  await page.route("**/wallets/**/behavior*", async (route) => {
    await route.fulfill({ json: behavior });
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
  await expect(page.getByTestId("behavior-definitions")).toContainText(
    "Clean FIFO",
  );
  await expect(page.getByTestId("behavior-windows")).toContainText(
    "90D window",
  );
  await expect(page.getByTestId("behavior-classifications")).toContainText(
    "EARLY_BUYER",
  );
  await expect(page.getByTestId("behavior-risk-flags")).toContainText(
    "does not identify intent",
  );
});
