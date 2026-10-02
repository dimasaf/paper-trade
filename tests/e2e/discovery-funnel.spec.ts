import { expect, test } from "@playwright/test";

const asOf = "2026-09-28T10:00:00Z";
const cohort = {
  cohort_id: "recorded-september-winners",
  created_from: "2026-09-28T09:00:00Z",
  created_to: "2026-09-28T09:00:00Z",
  qualification_as_of: asOf,
};
const token = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr";
const strongWallet = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1";
const failedWallet = "H78u6JJ82BpT8kae6UXkBbRWLYWUTfu7HXSGVxgY5dAY";
const unknownWallet = "Fz79XcXMRZ5ijyyQ8zZNwJBWXnr7hP3bVM1q4bRDGb7P";

type Outcome = "INCLUDED" | "EXCLUDED" | "UNKNOWN";

function reason(code: string, outcome: Outcome, message: string) {
  return {
    code,
    outcome,
    message,
    observed: null,
    threshold: null,
    configuration_version: 1,
    as_of: asOf,
  };
}

function member(
  subject: string,
  outcome: Outcome,
  reasons: ReturnType<typeof reason>[],
  extra: {
    evidence?: string[];
    coverage?: unknown[];
    warnings?: string[];
  } = {},
) {
  return {
    subject,
    outcome,
    reasons,
    evidence: extra.evidence ?? [],
    coverage: extra.coverage ?? [],
    warnings: extra.warnings ?? [],
  };
}

function stage(name: string, members: ReturnType<typeof member>[]) {
  return {
    name,
    subject: name === "TOKENS_ANALYZED" ? "TOKEN" : "WALLET",
    as_of: asOf,
    configuration_version: 1,
    evaluated: members.length,
    included: members.filter((entry) => entry.outcome === "INCLUDED").length,
    excluded: members.filter((entry) => entry.outcome === "EXCLUDED").length,
    unknown: members.filter((entry) => entry.outcome === "UNKNOWN").length,
    members,
  };
}

const incompleteCoverage = [
  {
    source: "HELIUS",
    complete: false,
    unknown_fields: ["price_usd", "liquidity_usd"],
  },
];

const completedRun = {
  run_id: "00000000-0000-0000-0000-000000000064",
  cohort,
  as_of: asOf,
  configuration_id: "00000000-0000-0000-0000-000000000001",
  configuration_version: 1,
  status: "COMPLETED",
  started_at: asOf,
  completed_at: asOf,
  error: null,
  stages: [
    stage("TOKENS_ANALYZED", [
      member(token, "INCLUDED", [
        reason(
          "INITIAL_MARKET_CAP_IN_RANGE",
          "INCLUDED",
          "initial_market_cap_usd 120000 against the configured winner rule >= 10000 and <= 500000.",
        ),
      ]),
    ]),
    stage("WALLETS_FOUND", [
      member(
        strongWallet,
        "INCLUDED",
        [
          reason(
            "RECORDED_WINNER_ACTIVITY",
            "INCLUDED",
            "Recorded activity on a qualified historical winner Token was found for this Wallet: BUY succeeded.",
          ),
        ],
        {
          coverage: incompleteCoverage,
          warnings: ["Recorded fixture has incomplete entry coverage"],
        },
      ),
    ]),
    stage("CANDIDATES", [
      member(strongWallet, "INCLUDED", [
        reason(
          "SUCCESSFUL_ENTRY",
          "INCLUDED",
          "A recorded BUY succeeded entry passes the configured candidate rule.",
        ),
      ]),
      member(failedWallet, "EXCLUDED", [
        reason(
          "ENTRY_TRANSACTION_FAILED",
          "EXCLUDED",
          "The recorded BUY failed, so it is not a candidate entry.",
        ),
      ]),
      member(unknownWallet, "UNKNOWN", [
        reason(
          "ENTRY_MOVEMENT_UNKNOWN",
          "UNKNOWN",
          "Every recorded movement for this Wallet is UNKNOWN, so a successful entry cannot be established.",
        ),
      ]),
    ]),
    stage("PROFITABLE", [
      member(strongWallet, "INCLUDED", [
        reason(
          "CLEAN_PROFITABILITY_AT_OR_ABOVE_MIDPOINT",
          "INCLUDED",
          "Clean ALL_TIME ROI 59% against the configured 50% target scores 100 out of 100.",
        ),
      ]),
    ]),
    stage("CONSISTENT", [
      member(strongWallet, "INCLUDED", [
        reason(
          "CONSISTENCY_AT_OR_ABOVE_MIDPOINT",
          "INCLUDED",
          "Win rate and profit concentration average to 60.",
        ),
      ]),
    ]),
    stage("COPYABLE", [
      member(strongWallet, "INCLUDED", [
        reason(
          "COPYABILITY_AT_OR_ABOVE_MIDPOINT",
          "INCLUDED",
          "The worst filled follower ROI scores 100.",
        ),
      ]),
    ]),
    stage("SMART_WALLET", [
      member(strongWallet, "INCLUDED", [
        reason(
          "REGISTRY_SMART_WALLET",
          "INCLUDED",
          "Total score 91 meets the Smart Wallet threshold 80 with known components and complete coverage.",
        ),
      ]),
    ]),
  ],
  warnings: [
    "Recorded fixture has incomplete entry coverage",
    "price_usd is UNKNOWN at the entry as-of time",
  ],
};

const emptyDiscovery = {
  cohort,
  configuration_id: "00000000-0000-0000-0000-000000000001",
  configuration_version: 1,
  winners: [],
  early_buyers: [],
  candidate_wallets: [],
};

test("Discovery funnel shows every stage count and opens a stage for its pass and fail reasons", async ({
  page,
}) => {
  await page.route("**/discovery/historical-winners/latest", async (route) => {
    await route.fulfill({ json: emptyDiscovery });
  });
  await page.route("**/discovery/funnel/latest", async (route) => {
    await route.fulfill({ json: completedRun });
  });

  await page.goto("/discovery");

  await expect(
    page.getByRole("heading", { name: "Discovery funnel" }),
  ).toBeVisible();
  const counts = page.getByTestId("funnel-counts");
  await expect(counts).toContainText("Tokens analyzed");
  await expect(counts).toContainText("Wallets found");
  await expect(counts).toContainText("Candidates");
  await expect(counts).toContainText("Profitable");
  await expect(counts).toContainText("Consistent");
  await expect(counts).toContainText("Copyable");
  await expect(counts).toContainText("Smart Wallets");
  await expect(counts).toContainText("1 evaluated · 1 included");
  await expect(page.getByTestId("funnel-warnings")).toContainText(
    "incomplete entry coverage",
  );

  const candidates = page.getByTestId("funnel-stage-candidates");
  await expect(candidates).toContainText(
    "3 evaluated · 1 included · 1 excluded · 1 unknown",
  );
  await candidates.getByText("Candidates · 3 evaluated").click();
  await expect(candidates).toContainText("SUCCESSFUL_ENTRY");
  await expect(candidates).toContainText("ENTRY_TRANSACTION_FAILED");
  await expect(candidates).toContainText("ENTRY_MOVEMENT_UNKNOWN");
  await expect(candidates).toContainText("UNKNOWN");
  await expect(candidates).toContainText("config v1");

  const found = page.getByTestId("funnel-stage-wallets_found");
  await found.getByText("Wallets found · 1 evaluated").click();
  await expect(found).toContainText("HELIUS coverage incomplete");
  await expect(found).toContainText("UNKNOWN: price_usd, liquidity_usd");

  const smartWallets = page.getByTestId("funnel-stage-smart_wallet");
  await smartWallets.getByText("Smart Wallets · 1 evaluated").click();
  await expect(smartWallets).toContainText("REGISTRY_SMART_WALLET");

  const tokens = page.getByTestId("funnel-stage-tokens_analyzed");
  await tokens.getByText("Tokens analyzed · 1 evaluated").click();
  await expect(tokens).toContainText("INITIAL_MARKET_CAP_IN_RANGE");
  await expect(tokens).toContainText("rule >= 10000 and <= 500000");
});

test("Discovery funnel shows an empty state before any cohort has run", async ({
  page,
}) => {
  await page.route("**/discovery/historical-winners/latest", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "none" } });
  });
  await page.route("**/discovery/funnel/latest", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "none" } });
  });

  await page.goto("/discovery");

  await expect(page.getByTestId("funnel-empty")).toContainText(
    "No discovery funnel run has been recorded yet",
  );
  await expect(page.getByTestId("funnel-stages")).toHaveCount(0);
});

test("Discovery funnel keeps a running cohort visible", async ({ page }) => {
  await page.route("**/discovery/historical-winners/latest", async (route) => {
    await route.fulfill({ json: emptyDiscovery });
  });
  await page.route("**/discovery/funnel/latest", async (route) => {
    await route.fulfill({
      json: {
        ...completedRun,
        status: "RUNNING",
        stages: [],
        completed_at: null,
        warnings: [],
      },
    });
  });

  await page.goto("/discovery");

  await expect(page.getByTestId("funnel-running")).toContainText(
    "is still running",
  );
  await expect(page.getByTestId("funnel-stages")).toHaveCount(0);
});

test("Discovery funnel shows a failed cohort with its recorded error", async ({
  page,
}) => {
  await page.route("**/discovery/historical-winners/latest", async (route) => {
    await route.fulfill({ json: emptyDiscovery });
  });
  await page.route("**/discovery/funnel/latest", async (route) => {
    await route.fulfill({
      json: {
        ...completedRun,
        status: "FAILED",
        stages: [],
        error: "ValueError: recorded early-buyer provider is unavailable",
      },
    });
  });

  await page.goto("/discovery");

  await expect(page.getByTestId("funnel-failed")).toContainText(
    "recorded early-buyer provider is unavailable",
  );
  await expect(page.getByTestId("funnel-stages")).toHaveCount(0);
});

test("Researcher runs a fixed cohort and reads the completed funnel", async ({
  page,
}) => {
  let posted: Record<string, unknown> | null = null;
  await page.route("**/discovery/historical-winners/latest", async (route) => {
    await route.fulfill({ json: emptyDiscovery });
  });
  await page.route("**/discovery/funnel/latest", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "none" } });
  });
  await page.route("**/discovery/funnel", async (route) => {
    posted = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ status: 201, json: completedRun });
  });

  await page.goto("/discovery");
  await expect(page.getByTestId("funnel-empty")).toBeVisible();

  await page.getByTestId("funnel-cohort_id").fill("recorded-september-winners");
  await page.getByTestId("funnel-created_from").fill("2026-09-28T09:00:00Z");
  await page.getByTestId("funnel-created_to").fill("2026-09-28T09:00:00Z");
  await page
    .getByTestId("funnel-qualification_as_of")
    .fill("2026-09-28T10:00:00Z");
  await page.getByTestId("funnel-as_of").fill("2026-09-28T10:00:00Z");
  await page.getByRole("button", { name: "Run discovery funnel" }).click();

  expect(posted).toEqual({
    cohort: {
      cohort_id: "recorded-september-winners",
      created_from: "2026-09-28T09:00:00Z",
      created_to: "2026-09-28T09:00:00Z",
      qualification_as_of: "2026-09-28T10:00:00Z",
    },
    as_of: "2026-09-28T10:00:00Z",
  });
  await expect(page.getByTestId("funnel-stages")).toContainText(
    "Smart Wallets · 1 evaluated",
  );
  await expect(page.getByTestId("funnel-counts")).toContainText(
    "Smart Wallets",
  );
  await expect(page.getByTestId("funnel-empty")).toHaveCount(0);
});

test("Discovery funnel asks for every cohort field before it runs", async ({
  page,
}) => {
  await page.route("**/discovery/historical-winners/latest", async (route) => {
    await route.fulfill({ json: emptyDiscovery });
  });
  await page.route("**/discovery/funnel/latest", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "none" } });
  });

  await page.goto("/discovery");
  await page.getByRole("button", { name: "Run discovery funnel" }).click();

  await expect(page.getByTestId("funnel-form-error")).toContainText(
    "Every cohort field is required",
  );
});
