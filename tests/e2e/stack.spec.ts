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
