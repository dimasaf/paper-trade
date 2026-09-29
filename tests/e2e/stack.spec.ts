import { expect, test } from "@playwright/test";

import { healthComponentNames } from "./health-fixture";

test("running workspace reports every dependency ready", async ({ page }) => {
  test.skip(
    !process.env.STACK_E2E,
    "Runs against the Docker Compose workspace",
  );

  await page.goto("/");

  await expect(page.getByTestId("overall-status")).toHaveText("Ready");
  for (const component of healthComponentNames) {
    await expect(page.getByTestId(`${component}-status`)).toHaveText("Ready");
  }
});

test("running workspace rejects invalid research settings through FastAPI", async ({
  page,
}) => {
  test.skip(
    !process.env.STACK_E2E,
    "Runs against the Docker Compose workspace",
  );

  await page.goto("/settings");
  await expect(page.getByText("Active version 1")).toBeVisible();
  const editor = page.getByLabel("Research configuration JSON");
  const configuration = JSON.parse(await editor.inputValue()) as {
    execution: { latency_ms: number };
  };
  configuration.execution.latency_ms = -1;
  await editor.fill(JSON.stringify(configuration, null, 2));
  await page.getByRole("button", { name: "Save new version" }).click();

  await expect(
    page.getByRole("alert").filter({
      hasText: "configuration.execution.latency_ms",
    }),
  ).toBeVisible();
  await expect(page.getByText("Active version 1")).toBeVisible();
});

const recordedStackJourneyEvent = {
  event_id: "stack-journey-pumpswap-0001",
  address: "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
  name: "Stack Journey Token",
  symbol: "SJOUR",
  creator: "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
  created_at: "2026-09-28T09:00:00Z",
  observed_at: "2026-09-28T09:00:05Z",
  launch_platform: "PUMP_SWAP",
  lifecycle_state: "NEW",
  has_pool: true,
  liquidity_usd: 52000,
  market_cap_usd: 120000,
  volume_24h_usd: 30000,
  coverage: {
    provider: "recorded-stack-journey",
    as_of_start: "2026-09-28T09:00:00Z",
    as_of_end: "2026-09-28T09:05:00Z",
    complete: true,
    commitment: "confirmed",
    freshness_seconds: 5,
    signature: "recorded-signature-stack-journey-0001",
    slot: 314159268,
    normalization_version: "launch-event/v1",
    unknown_fields: [],
    warnings: [],
  },
};

test("running workspace registers a recorded launch event into a Token detail page", async ({
  page,
}) => {
  test.skip(
    !process.env.STACK_E2E,
    "Runs against the Docker Compose workspace",
  );

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  const response = await page.request.post(`${apiUrl}/tokens`, {
    data: { event: recordedStackJourneyEvent },
  });
  expect([200, 201]).toContain(response.status());
  const registered = (await response.json()) as { address: string };
  expect(registered.address).toBe(recordedStackJourneyEvent.address);

  const migration = {
    ...recordedStackJourneyEvent,
    event_id: "stack-journey-pumpswap-migration-0002",
    observed_at: "2026-09-28T09:10:05Z",
    lifecycle_state: "MIGRATED",
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
  };
  const migrated = await page.request.post(`${apiUrl}/tokens`, {
    data: { event: migration },
  });
  expect(migrated.status()).toBe(200);

  await page.goto(`/tokens/${recordedStackJourneyEvent.address}`);

  await expect(
    page.getByRole("heading", { name: "Stack Journey Token" }),
  ).toBeVisible();
  await expect(page.getByTestId("token-platform")).toHaveText("PUMP_SWAP");
  await expect(page.getByTestId("token-lifecycle-state")).toHaveText(
    "MIGRATED",
  );
  await expect(page.getByTestId("lifecycle-transitions")).toContainText(
    "CreatePoolEvent",
  );
  await expect(page.getByTestId("classification-evidence")).toContainText(
    "launch_source",
  );
  await expect(page.getByTestId("coverage-list")).toContainText(
    "recorded-stack-journey",
  );
});

const jupiterStudioCreation = {
  event_id: "stack-jupiter-studio-create-0001",
  address: "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4",
  name: "Stack Jupiter Studio Token",
  symbol: "SSTUDIO",
  creator: "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
  created_at: "2026-09-28T10:10:00Z",
  observed_at: "2026-09-28T10:10:03Z",
  launch_platform: "JUPITER_STUDIO",
  lifecycle_state: "NEW",
  has_pool: false,
  evidence: [
    {
      event_type: "CREATE",
      event_name: "Meteora DBC create",
      program_id: "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN",
      bonding_curve: null,
      bonding_curve_progress_percent: null,
      pool: null,
    },
  ],
  coverage: {
    provider: "recorded-jupiter-studio",
    as_of_start: "2026-09-28T10:10:00Z",
    as_of_end: "2026-09-28T10:12:00Z",
    complete: false,
    commitment: "confirmed",
    freshness_seconds: 3,
    signature: "stack-jupiter-studio-create-0001",
    slot: 314159500,
    normalization_version: "meteora-dbc/v1",
    unknown_fields: ["liquidity_usd", "market_cap_usd", "volume_24h_usd"],
    warnings: ["Bonding-curve market facts are not available at creation"],
  },
};

const jupiterStudioGraduation = {
  ...jupiterStudioCreation,
  event_id: "stack-jupiter-studio-graduation-0002",
  observed_at: "2026-09-28T10:20:05Z",
  lifecycle_state: "MIGRATED",
  has_pool: true,
  graduation_pool_address: "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
  liquidity_usd: 75000,
  market_cap_usd: 180000,
  volume_24h_usd: 45000,
  evidence: [
    {
      event_type: "GRADUATE",
      event_name: "Meteora DBC graduate",
      program_id: "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN",
      bonding_curve: null,
      bonding_curve_progress_percent: null,
      pool: "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
    },
  ],
  coverage: {
    provider: "recorded-meteora-dbc",
    as_of_start: "2026-09-28T10:20:00Z",
    as_of_end: "2026-09-28T10:22:00Z",
    complete: true,
    commitment: "confirmed",
    freshness_seconds: 5,
    signature: "stack-jupiter-studio-graduation-0002",
    slot: 314159501,
    normalization_version: "meteora-dbc/v1",
    unknown_fields: [],
    warnings: [],
  },
};

test("running workspace shows a Jupiter Studio Token graduating through Meteora DBC", async ({
  page,
}) => {
  test.skip(
    !process.env.STACK_E2E,
    "Runs against the Docker Compose workspace",
  );

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  expect(
    (
      await page.request.post(`${apiUrl}/tokens`, {
        data: { event: jupiterStudioCreation },
      })
    ).status(),
  ).toBe(201);
  expect(
    (
      await page.request.post(`${apiUrl}/tokens`, {
        data: { event: jupiterStudioGraduation },
      })
    ).status(),
  ).toBe(200);

  await page.goto(`/tokens/${jupiterStudioCreation.address}`);

  await expect(
    page.getByRole("heading", { name: "Stack Jupiter Studio Token" }),
  ).toBeVisible();
  await expect(page.getByTestId("token-platform")).toHaveText("JUPITER_STUDIO");
  await expect(page.getByTestId("token-lifecycle-state")).toHaveText(
    "MIGRATED",
  );
  await expect(page.getByTestId("lifecycle-transitions")).toContainText(
    "Meteora DBC graduate",
  );
  await expect(page.getByTestId("lifecycle-transitions")).toContainText(
    "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
  );
  await expect(page.getByTestId("coverage-warnings")).toContainText(
    "Bonding-curve market facts are not available at creation",
  );
});

test("running workspace persists immutable research configuration versions", async ({
  page,
}) => {
  test.skip(
    !process.env.STACK_E2E,
    "Runs against the Docker Compose workspace",
  );

  await page.goto("/settings");
  await expect(page.getByText("Active version 1")).toBeVisible();
  const editor = page.getByLabel("Research configuration JSON");
  const configuration = JSON.parse(await editor.inputValue()) as {
    cluster: { minimum_contributing_independent_wallets: number };
  };
  configuration.cluster.minimum_contributing_independent_wallets = 4;
  await editor.fill(JSON.stringify(configuration, null, 2));
  await page.getByRole("button", { name: "Save new version" }).click();

  await expect(page.getByText("Active version 2")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Active version 2")).toBeVisible();
  await expect(page.getByTestId("configuration-history")).toContainText(
    "Version 1",
  );
});
