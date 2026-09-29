import { expect, test } from "@playwright/test";

const raydiumAddress = "JEKNVnkbo3jma5nREBBJCDoXFVeKkD56V3xKrvRmWxFG";
const creator = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1";
const pool = "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4";

const creation = {
  event_id: "raydium-launchlab:stack-create-0001",
  address: raydiumAddress,
  name: "Stack Raydium Token",
  symbol: "SRAY",
  creator,
  created_at: "2026-09-28T10:00:00Z",
  observed_at: "2026-09-28T10:00:04Z",
  launch_platform: "RAYDIUM_LAUNCHLAB",
  lifecycle_state: "NEW",
  has_pool: false,
  coverage: {
    provider: "raydium-launchlab-program",
    as_of_start: "2026-09-28T10:00:00Z",
    as_of_end: "2026-09-28T10:00:04Z",
    complete: true,
    commitment: "confirmed",
    freshness_seconds: 4,
    signature: "stack-raydium-launchlab-create-0001",
    slot: 314159400,
    normalization_version: "raydium-launchlab/v1",
    unknown_fields: [],
    warnings: [],
  },
};

const migration = {
  event_id: "raydium-launchlab:stack-migrate-0002",
  address: raydiumAddress,
  name: "UNKNOWN",
  symbol: "UNKNOWN",
  creator,
  created_at: "2026-09-28T10:15:00Z",
  observed_at: "2026-09-28T10:15:03Z",
  launch_platform: "RAYDIUM_LAUNCHLAB",
  lifecycle_state: "MIGRATED",
  has_pool: true,
  coverage: {
    provider: "raydium-launchlab-program",
    as_of_start: "2026-09-28T10:15:00Z",
    as_of_end: "2026-09-28T10:15:03Z",
    complete: false,
    commitment: "confirmed",
    freshness_seconds: 3,
    signature: "stack-raydium-launchlab-migrate-0002",
    slot: 314159401,
    normalization_version: "raydium-launchlab/v1",
    unknown_fields: ["name", "symbol"],
    warnings: [
      `Raydium LaunchLab migration created pool ${pool}`,
      "LaunchLab program data does not include Token metadata",
    ],
  },
};

test("running workspace keeps one Raydium Token through LaunchLab migration", async ({
  page,
}) => {
  test.skip(
    !process.env.STACK_E2E,
    "Runs against the Docker Compose workspace",
  );

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  expect(
    (
      await page.request.post(`${apiUrl}/tokens`, { data: { event: creation } })
    ).status(),
  ).toBe(201);
  expect(
    (
      await page.request.post(`${apiUrl}/tokens`, {
        data: { event: migration },
      })
    ).status(),
  ).toBe(200);
  expect(
    (
      await page.request.post(`${apiUrl}/tokens`, {
        data: { event: migration },
      })
    ).status(),
  ).toBe(200);

  await page.goto(`/tokens/${raydiumAddress}`);

  await expect(
    page.getByRole("heading", { name: "Stack Raydium Token" }),
  ).toBeVisible();
  await expect(page.getByTestId("token-platform")).toHaveText(
    "RAYDIUM_LAUNCHLAB",
  );
  await expect(page.getByTestId("token-lifecycle-state")).toHaveText(
    "MIGRATED",
  );
  await expect(page.getByTestId("lifecycle-transitions")).toHaveText("NEW");
  await expect(page.getByTestId("lifecycle-transitions")).toHaveText(
    "MIGRATED",
  );
  await expect(page.getByTestId("coverage-list")).toContainText(
    "raydium-launchlab-program",
  );
});
