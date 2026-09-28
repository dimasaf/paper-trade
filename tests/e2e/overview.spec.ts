import { expect, test } from "@playwright/test";

import { healthComponentNames, readyHealth } from "./health-fixture";

test("Overview shows every ready workspace dependency", async ({ page }) => {
  await page.route("**/health", async (route) => {
    await route.fulfill({ json: readyHealth });
  });

  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Research workspace" }),
  ).toBeVisible();
  await expect(page.getByTestId("overall-status")).toHaveText("Ready");
  for (const component of healthComponentNames) {
    await expect(page.getByTestId(`${component}-status`)).toHaveText("Ready");
  }
});

test("Overview clearly identifies a degraded dependency", async ({ page }) => {
  await page.route("**/health", async (route) => {
    await route.fulfill({
      json: {
        ...readyHealth,
        status: "degraded",
        components: {
          ...readyHealth.components,
          database: { status: "unavailable", message: "Database probe failed" },
        },
      },
    });
  });

  await page.goto("/");

  await expect(page.getByTestId("overall-status")).toHaveText("Degraded");
  await expect(
    page.getByRole("alert").filter({ hasText: "PostgreSQL is unavailable" }),
  ).toBeVisible();
  await expect(page.getByTestId("database-status")).toHaveText("Unavailable");
  await expect(page.getByTestId("redis-status")).toHaveText("Ready");
});
