import { expect, test } from "@playwright/test";

const tokenAddress = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr";

const tokenDetail = {
  address: tokenAddress,
  name: "Recorded Swap Token",
  symbol: "RSWAP",
  creator: "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
  created_at: "2026-09-28T09:00:00Z",
  observed_at: "2026-09-28T09:00:05Z",
  launch_platform: "PUMP_SWAP",
  lifecycle_state: "NEW",
  lifecycle_transitions: [
    {
      state: "NEW",
      observed_at: "2026-09-28T09:00:05Z",
      source_event_id: "recorded-pumpswap-pool-0001",
      reason: "launch event registered",
      evidence: [
        {
          event_type: "POOL_CREATE",
          event_name: "CreatePoolEvent",
          program_id: "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
          bonding_curve: null,
          bonding_curve_progress_percent: null,
          pool: "4wBqpZM9W7D6h2ZQ5E6o1CymCPG9hrpE7cXkYkKpE8Qm",
        },
      ],
    },
  ],
  classification: {
    configuration_id: "00000000-0000-0000-0000-000000000001",
    configuration_version: 1,
    passed: false,
    criteria: [
      {
        criterion: "launch_source",
        threshold: "PUMP_FUN, PUMP_SWAP",
        observed: "PUMP_SWAP",
        passed: true,
      },
      {
        criterion: "liquidity_usd",
        threshold: ">= 10000",
        observed: "UNKNOWN",
        passed: false,
      },
    ],
  },
  coverage: [
    {
      provider: "recorded-pumpswap",
      as_of_start: "2026-09-28T09:00:00Z",
      as_of_end: "2026-09-28T09:05:00Z",
      complete: false,
      commitment: "confirmed",
      freshness_seconds: 5,
      signature: "recorded-signature-pumpswap-0001",
      slot: 314159265,
      normalization_version: "launch-event/v1",
      unknown_fields: ["liquidity_usd"],
      warnings: ["Market facts are not available yet"],
    },
  ],
};

test("Token detail shows provenance, lifecycle, classification evidence, and coverage warnings", async ({
  page,
}) => {
  await page.route("**/tokens/**", async (route) => {
    if (route.request().resourceType() === "document") {
      await route.fallback();
      return;
    }
    await route.fulfill({ json: tokenDetail });
  });

  await page.goto(`/tokens/${tokenAddress}`);

  await expect(
    page.getByRole("heading", { name: "Recorded Swap Token" }),
  ).toBeVisible();
  await expect(page.getByTestId("token-address")).toContainText(tokenAddress);
  await expect(page.getByTestId("token-platform")).toHaveText("PUMP_SWAP");
  await expect(page.getByTestId("token-lifecycle-state")).toHaveText("NEW");
  await expect(page.getByTestId("lifecycle-transitions")).toContainText("NEW");
  await expect(page.getByTestId("launch-program-evidence")).toContainText(
    "CreatePoolEvent",
  );
  await expect(page.getByTestId("classification-evidence")).toContainText(
    "liquidity_usd",
  );
  await expect(page.getByTestId("classification-evidence")).toContainText(
    "FAIL",
  );
  await expect(page.getByTestId("coverage-list")).toContainText(
    "recorded-pumpswap",
  );
  await expect(page.getByTestId("coverage-list")).toContainText("incomplete");
  const warnings = page.getByTestId("coverage-warnings");
  await expect(warnings).toContainText(
    "recorded-pumpswap coverage is incomplete",
  );
  await expect(warnings).toContainText("liquidity_usd is UNKNOWN");
  await expect(warnings).toContainText("Market facts are not available yet");
});

test("Token detail reports an unregistered address instead of inventing data", async ({
  page,
}) => {
  await page.route("**/tokens/**", async (route) => {
    if (route.request().resourceType() === "document") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 404,
      json: { detail: "Token is not registered" },
    });
  });

  await page.goto("/tokens/unknownaddress");

  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "This Token is not registered." }),
  ).toBeVisible();
});

test("Token universe lists registered Tokens and links to each detail page", async ({
  page,
}) => {
  await page.route("**/tokens", async (route) => {
    if (route.request().resourceType() === "document") {
      await route.fallback();
      return;
    }
    await route.fulfill({ json: [tokenDetail] });
  });

  await page.goto("/tokens");

  await expect(
    page.getByRole("heading", { name: "Registered Tokens" }),
  ).toBeVisible();
  await expect(page.getByTestId("token-list")).toContainText("RSWAP");
  await expect(page.getByTestId("token-list")).toContainText("PUMP_SWAP");
  await expect(page.getByRole("link", { name: /RSWAP/ })).toHaveAttribute(
    "href",
    `/tokens/${tokenAddress}`,
  );
});
