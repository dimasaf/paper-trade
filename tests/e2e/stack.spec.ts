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
    cluster: { minimum_independent_wallets: number };
  };
  configuration.cluster.minimum_independent_wallets = 4;
  await editor.fill(JSON.stringify(configuration, null, 2));
  await page.getByRole("button", { name: "Save new version" }).click();

  await expect(page.getByText("Active version 2")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Active version 2")).toBeVisible();
  await expect(page.getByTestId("configuration-history")).toContainText(
    "Version 1",
  );
});
