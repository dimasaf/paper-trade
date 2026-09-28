import { expect, test } from "@playwright/test";

test("running workspace reports every dependency ready", async ({ page }) => {
  test.skip(
    !process.env.STACK_E2E,
    "Runs against the Docker Compose workspace",
  );

  await page.goto("/");

  await expect(page.getByTestId("overall-status")).toHaveText("Ready");
  for (const component of ["application", "database", "redis", "worker"]) {
    await expect(page.getByTestId(`${component}-status`)).toHaveText("Ready");
  }
});
