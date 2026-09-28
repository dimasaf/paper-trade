import { expect, test } from "@playwright/test";

const defaultConfiguration = {
  token: {
    launch_sources: ["PUMP_FUN", "PUMP_SWAP"],
    require_pool: true,
    minimum_liquidity_usd: 10000,
    minimum_market_cap_usd: 25000,
    minimum_24h_volume_usd: 10000,
    winner_initial_market_cap_min_usd: 10000,
    winner_initial_market_cap_max_usd: 500000,
    winner_peak_market_cap_min_usd: 1000000,
    entry_market_cap_buckets_usd: [50000, 100000],
  },
  wallet: {
    minimum_score: 80,
    minimum_trades: 20,
    copyability_delays_ms: [500, 1000],
    copyability_sizes_sol: [0.1, 0.25],
    score_weights: {
      profitability: 20,
      consistency: 20,
      copyability: 25,
      risk_quality: 15,
      entry_quality: 10,
      history_quality: 10,
    },
  },
  cluster: {
    minimum_contributing_independent_wallets: 3,
    window_seconds: 300,
    minimum_average_wallet_score: 80,
  },
  signal: {
    watch_score: 60,
    paper_buy_score: 80,
    cooldown_seconds: 900,
    score_weights: {
      wallet_quality: 25,
      contributing_independent_wallets: 20,
      token_risk: 20,
      liquidity: 10,
      entry_quality: 10,
      buy_velocity: 10,
      market_confirmation: 5,
    },
  },
  paper_trading: {
    starting_balance_usd: 10000,
    sizing_mode: "PERCENT",
    position_size_percent: 1,
    position_size_sol: 0.5,
    maximum_position_percent: 3,
    maximum_open_positions: 10,
  },
  risk: {
    stop_loss_percent: 15,
    take_profit_percent: 30,
    partial_take_profits: [{ gain_percent: 25, sell_percent: 25 }],
    trailing_stop_percent: 15,
    smart_wallet_sell_pressure_percent: 60,
    liquidity_collapse_percent: 50,
    holder_concentration_increase_percent: 10,
    volume_collapse_percent: 70,
    maximum_holding_seconds: 86400,
  },
  execution: {
    latency_ms: 3000,
    fallback_slippage_percent: 2,
    venue_fee_percent: 0.25,
    network_fee_sol: 0.000005,
    priority_fee_sol: 0.0001,
    failed_transaction_probability_percent: 1,
    maximum_pool_participation_percent: 1,
  },
};

const versionOne = {
  id: "00000000-0000-0000-0000-000000000001",
  version: 1,
  created_at: "2026-09-28T09:00:00Z",
  configuration: defaultConfiguration,
};

test("Settings displays, edits, and versions research assumptions", async ({
  page,
}) => {
  let versions = [versionOne];
  await page.route("**/research-configurations/active", async (route) => {
    await route.fulfill({ json: versions[0] });
  });
  await page.route("**/research-configurations", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as {
        configuration: typeof defaultConfiguration;
      };
      versions = [
        {
          ...versionOne,
          id: "00000000-0000-0000-0000-000000000002",
          version: 2,
          created_at: "2026-09-28T09:30:00Z",
          configuration: body.configuration,
        },
        ...versions,
      ];
      await route.fulfill({ status: 201, json: versions[0] });
      return;
    }
    await route.fulfill({ json: versions });
  });

  await page.goto("/settings");

  await expect(
    page.getByRole("heading", { name: "Research settings" }),
  ).toBeVisible();
  await expect(page.getByText("Active version 1")).toBeVisible();
  for (const section of [
    "Token",
    "Wallet",
    "Cluster",
    "Signal",
    "Paper Trading",
    "Risk",
    "Execution",
  ]) {
    await expect(page.getByRole("heading", { name: section })).toBeVisible();
  }

  const changed = structuredClone(defaultConfiguration);
  changed.cluster.minimum_contributing_independent_wallets = 4;
  await page
    .getByLabel("Research configuration JSON")
    .fill(JSON.stringify(changed, null, 2));
  await page.getByRole("button", { name: "Save new version" }).click();

  await expect(page.getByText("Active version 2")).toBeVisible();
  await expect(page.getByText("Saved immutable version 2.")).toBeVisible();
  await expect(page.getByTestId("configuration-history")).toContainText(
    "Version 1",
  );
});

test("Settings shows actionable validation errors without creating a version", async ({
  page,
}) => {
  await page.route("**/research-configurations/active", async (route) => {
    await route.fulfill({ json: versionOne });
  });
  await page.route("**/research-configurations", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 422,
        json: {
          detail: [
            {
              loc: ["body", "configuration", "signal"],
              msg: "Value error, watch_score must be lower than paper_buy_score",
            },
          ],
        },
      });
      return;
    }
    await route.fulfill({ json: [versionOne] });
  });

  await page.goto("/settings");
  const invalid = structuredClone(defaultConfiguration);
  invalid.signal.watch_score = 90;
  await page
    .getByLabel("Research configuration JSON")
    .fill(JSON.stringify(invalid, null, 2));
  await page.getByRole("button", { name: "Save new version" }).click();

  await expect(
    page.getByRole("alert").filter({
      hasText:
        "configuration.signal: Value error, watch_score must be lower than paper_buy_score",
    }),
  ).toBeVisible();
  await expect(page.getByText("Active version 1")).toBeVisible();
});
