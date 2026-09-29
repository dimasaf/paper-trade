import { expect, test } from "@playwright/test";

const raydiumAddress = "JEKNVnkbo3jma5nREBBJCDoXFVeKkD56V3xKrvRmWxFG";

const migratedRaydiumToken = {
  address: raydiumAddress,
  name: "Recorded Raydium Token",
  symbol: "RRAY",
  creator: "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
  created_at: "2026-09-28T10:00:00Z",
  observed_at: "2026-09-28T10:15:03Z",
  launch_platform: "RAYDIUM_LAUNCHLAB",
  lifecycle_state: "MIGRATED",
  lifecycle_transitions: [
    {
      state: "NEW",
      observed_at: "2026-09-28T10:00:04Z",
      source_event_id:
        "raydium-launchlab:recorded-raydium-launchlab-create-0001",
      reason: "launch event registered",
    },
    {
      state: "MIGRATED",
      observed_at: "2026-09-28T10:15:03Z",
      source_event_id:
        "raydium-launchlab:recorded-raydium-launchlab-migrate-0002",
      reason: "launch event registered",
    },
  ],
  classification: {
    configuration_id: "00000000-0000-0000-0000-000000000001",
    configuration_version: 1,
    passed: false,
    criteria: [],
  },
  coverage: [
    {
      provider: "raydium-launchlab-program",
      as_of_start: "2026-09-28T10:00:00Z",
      as_of_end: "2026-09-28T10:00:04Z",
      complete: true,
      commitment: "confirmed",
      freshness_seconds: 4,
      signature: "recorded-raydium-launchlab-create-0001",
      slot: 314159300,
      normalization_version: "raydium-launchlab/v1",
      unknown_fields: [],
      warnings: [],
    },
    {
      provider: "raydium-launchlab-program",
      as_of_start: "2026-09-28T10:15:00Z",
      as_of_end: "2026-09-28T10:15:03Z",
      complete: false,
      commitment: "confirmed",
      freshness_seconds: 3,
      signature: "recorded-raydium-launchlab-migrate-0002",
      slot: 314159301,
      normalization_version: "raydium-launchlab/v1",
      unknown_fields: ["name", "symbol"],
      warnings: [
        "Raydium LaunchLab migration created pool 27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4",
        "LaunchLab program data does not include Token metadata",
      ],
    },
  ],
};

test("Raydium LaunchLab detail exposes migration provenance and missing metadata", async ({
  page,
}) => {
  await page.route(`**/tokens/${raydiumAddress}`, async (route) => {
    if (route.request().resourceType() === "document") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      json: migratedRaydiumToken,
      headers: { "access-control-allow-origin": "*" },
    });
  });

  await page.goto(`/tokens/${raydiumAddress}`);

  await expect(
    page.getByRole("heading", { name: "Recorded Raydium Token" }),
  ).toBeVisible();
  await expect(page.getByTestId("token-platform")).toHaveText(
    "RAYDIUM_LAUNCHLAB",
  );
  await expect(page.getByTestId("token-lifecycle-state")).toHaveText(
    "MIGRATED",
  );
  await expect(page.getByTestId("lifecycle-transitions")).toContainText(
    "MIGRATED",
  );
  await expect(page.getByTestId("coverage-list")).toContainText(
    "raydium-launchlab-program",
  );
  await expect(page.getByTestId("coverage-list")).toContainText(
    "raydium-launchlab/v1",
  );
  await expect(page.getByTestId("coverage-warnings")).toContainText(
    "name is UNKNOWN",
  );
  await expect(page.getByTestId("coverage-warnings")).toContainText(
    "LaunchLab program data does not include Token metadata",
  );
});
