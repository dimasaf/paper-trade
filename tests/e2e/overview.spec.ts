import { expect, test } from "@playwright/test";

const readyHealth = {
  status: "ready",
  checked_at: "2026-09-28T08:00:00Z",
  correlation_id: "browser-test",
  components: {
    application: { status: "ready", message: "API is serving requests" },
    database: { status: "ready", message: "PostgreSQL accepted a query" },
    redis: { status: "ready", message: "Redis responded to ping" },
    worker: { status: "ready", message: "ARQ heartbeat is current" },
  },
};

test("Overview shows every ready workspace dependency", async ({ page }) => {
  await page.route("**/health", async (route) => {
    await route.fulfill({ json: readyHealth });
  });

  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Research workspace" }),
  ).toBeVisible();
  await expect(page.getByTestId("overall-status")).toHaveText("Ready");
  for (const component of ["application", "database", "redis", "worker"]) {
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
