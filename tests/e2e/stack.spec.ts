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

  await page.goto(`/tokens/${recordedStackJourneyEvent.address}`);

  await expect(
    page.getByRole("heading", { name: "Stack Journey Token" }),
  ).toBeVisible();
  await expect(page.getByTestId("token-platform")).toHaveText("PUMP_SWAP");
  await expect(page.getByTestId("token-lifecycle-state")).toHaveText("NEW");
  await expect(page.getByTestId("classification-evidence")).toContainText(
    "launch_source",
  );
  await expect(page.getByTestId("coverage-list")).toContainText(
    "recorded-stack-journey",
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
