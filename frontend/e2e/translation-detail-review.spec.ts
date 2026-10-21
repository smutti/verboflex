import { expect, test, type Page } from "@playwright/test";
import type { TranslationGroupDetailResponse } from "../src/api/client";

// All records, text, credentials and screenshots are synthetic.
const text = "Salva le modifiche";
const detail: TranslationGroupDetailResponse = {
  id: "review-group",
  product_id: "review-product",
  product_name: "Demo Mobile",
  raw_key: "settings.save_changes",
  language: "it",
  language_label: "Italian",
  base_language: "en",
  base_maximum: 30,
  explicit_maximum: null,
  constraint_version: null,
  states: ["draft"],
  state_summary: "draft",
  is_deleted: false,
  comment_count: 0,
  mutation_eligible: true,
  review_eligible: true,
  pending_change: {
    version: 2,
    state: "draft",
    reconciliation_required: false,
    updated_by: "synthetic-reviewer",
    updated_at: "2026-10-20T10:00:00Z",
    values: [
      {
        translation_value_id: "review-value",
        selector_version: 1,
        selector_digest: "a".repeat(64),
        basis_revision_number: 1,
        basis_digest: "d".repeat(64),
        text,
        grapheme_count: 18,
        maximum: 30,
        is_over_limit: false,
        approval_eligible: true,
        submission_eligible: true,
      },
    ],
  },
  values: [
    {
      id: "review-value",
      selector_version: 1,
      selector_digest: "a".repeat(64),
      selector_kind: "scalar",
      selector_fields: [],
      source_text: "Save changes",
      translated_text: "Salva",
      display_text: "Salva",
      structure: [],
      grapheme_count: 5,
      constraint: {
        actual: 5,
        maximum: 30,
        source: "base_default",
        status: "within_limit",
        overage: 0,
      },
      review_state: "draft",
      is_deleted: false,
      deleted_at: null,
      provenance: {
        repository_id: "synthetic-repo",
        repository_name: "Demo translations",
        repository_side: "direct",
        branch: "main",
        path: "res/values-it/strings.xml",
        format: "android",
        commit_hash: "a".repeat(40),
        execution_id: "synthetic-import",
        line: 10,
        column: 2,
      },
      history: [
        {
          revision_number: 1,
          revision_digest: "d".repeat(64),
          review_state: "draft",
          is_deleted: false,
          created_at: "2026-10-20T09:00:00Z",
          commit_hash: "a".repeat(40),
          execution_id: "synthetic-import",
        },
      ],
      history_has_more: false,
    },
  ],
};
const capture = {
  id: "synthetic-capture",
  state: "succeeded",
  request: { preview_function: "demo.SettingsPreview", proposal_version: 2 },
  created_at: "2026-10-20T10:00:00Z",
  expires_at: "2026-10-27T10:00:00Z",
  error_code: null,
  location: {
    status: "found",
    regions: [{ x: 0.315, y: 0.553, width: 0.37, height: 0.035 }],
  },
};
const screenshot = `<svg xmlns="http://www.w3.org/2000/svg" width="360" height="520" viewBox="0 0 360 520">
<rect width="360" height="520" fill="#f8fafc"/><rect width="360" height="64" fill="#fff"/>
<text x="24" y="40" font-family="sans-serif" font-size="20" fill="#111827">Impostazioni</text>
<rect x="20" y="92" width="320" height="260" rx="8" fill="#fff" stroke="#e5e7eb"/>
<text x="40" y="130" font-family="sans-serif" font-size="16" fill="#111827">Preferenze del profilo</text>
<text x="40" y="170" font-family="sans-serif" font-size="14" fill="#6b7280">Nome visualizzato</text>
<rect x="40" y="184" width="280" height="44" rx="8" fill="#f8fafc" stroke="#e5e7eb"/>
<text x="54" y="212" font-family="sans-serif" font-size="14" fill="#111827">Utente demo</text>
<rect x="40" y="272" width="280" height="48" rx="8" fill="#0f766e"/>
<text x="180" y="302" text-anchor="middle" font-family="sans-serif" font-size="16" fill="white">Salva le modifiche</text>
</svg>`;

async function setup(
  page: Page,
  state: "ready" | "empty" | "unconfigured",
  role = "admin",
) {
  const requests = { captures: 0, activity: 0, authenticatedImages: 0 };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const base = "/api/v1/translations/review-group";
    if (path.endsWith("/image")) {
      if (request.headers().authorization === "Bearer synthetic-review-token")
        requests.authenticatedImages++;
      await route.fulfill({ contentType: "image/svg+xml", body: screenshot });
      return;
    }
    if (request.method() === "PUT" && path.includes("/screenshots/"))
      requests.captures++;
    if (path === `${base}/activity`) requests.activity++;
    const responses: Record<string, unknown> = {
      "/api/v1/auth/refresh": {
        access_token: "synthetic-review-token",
        token_type: "bearer",
        expires_in: 900,
        must_change_password: false,
      },
      "/api/v1/users/me": {
        id: "synthetic-reviewer",
        email: "reviewer@example.test",
        display_name: "Demo Reviewer",
        roles: [role],
        must_change_password: false,
      },
      "/api/v1/translations/options": {
        products: [{ id: "review-product", name: "Demo Mobile" }],
        languages: [{ code: "it", label: "Italian" }],
      },
      [base]: detail,
      [`${base}/comments`]: { items: [], older_cursor: null },
      [`${base}/activity`]: { items: [], next_cursor: null },
      [`${base}/code-context`]: {
        configured: state !== "unconfigured",
        occurrences: [],
        previews:
          state === "unconfigured"
            ? []
            : [
                {
                  function: "demo.SettingsPreview",
                  path: "Settings.kt",
                  line: 10,
                  keys: ["settings.save_changes"],
                  annotation: "@Preview",
                  evidence: "static_reference",
                },
              ],
        capture_functions:
          state === "unconfigured" ? [] : ["demo.SettingsPreview"],
        scenarios:
          state === "unconfigured"
            ? []
            : [
                {
                  preview_function: "demo.SettingsPreview",
                  label: "Profile settings",
                  explicit: true,
                },
              ],
      },
      [`${base}/screenshots`]: {
        items: state === "ready" ? [capture] : [],
        next_cursor: null,
      },
    };
    if (path in responses) await route.fulfill({ json: responses[path] });
    else
      await route.fulfill({
        status: 503,
        json: { detail: "Unrelated service unavailable in synthetic fixture" },
      });
  });
  return requests;
}

for (const width of [320, 768, 1440]) {
  test(`review content precedes optional screenshots and technical details at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const requests = await setup(page, "ready");
    await page.goto("/translations/review-group");
    const content = page.getByRole("region", {
      name: "Translation content",
      exact: true,
    });
    const screenshots = page.getByRole("complementary", {
      name: "Screenshots",
      exact: true,
    });
    const image = screenshots.getByAltText(
      "Compose screen preview with the selected translations",
    );
    await expect(image).toBeVisible();
    await expect
      .poll(() =>
        image.evaluate((e: HTMLImageElement) => e.complete && e.naturalWidth),
      )
      .toBe(360);
    await expect(
      content.getByRole("region", { name: "Pending proposal" }),
    ).toContainText(text);
    await expect(
      content.getByRole("region", { name: "Published translation" }),
    ).toContainText("Salva");
    await expect(
      content.getByRole("button", { name: "Approve translation", exact: true }),
    ).toBeEnabled();
    await expect(
      page.getByText("settings.save_changes", { exact: true }),
    ).toBeHidden();
    expect(requests).toEqual({
      captures: 0,
      activity: 0,
      authenticatedImages: 1,
    });
    const left = (await content.boundingBox())!;
    const right = (await screenshots.boundingBox())!;
    if (width >= 768) {
      expect(right.x).toBeGreaterThanOrEqual(left.x + left.width);
      expect(Math.abs(right.y - left.y)).toBeLessThan(2);
    } else {
      expect(right.y).toBeGreaterThan(left.y + left.height);
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const marker = screenshots.getByRole("img", {
      name: "Text position in screenshot",
    });
    await expect(marker).toBeVisible();
    const imageBox = (await image.boundingBox())!;
    const markerBox = (await marker.locator("rect").first().boundingBox())!;
    // SVG boundingBox includes the outer six-pixel halo around the text rectangle.
    expect(
      Math.abs(markerBox.x + 3 - (imageBox.x + imageBox.width * 0.315)),
    ).toBeLessThan(1);
    expect(
      Math.abs(markerBox.y + 3 - (imageBox.y + imageBox.height * 0.553)),
    ).toBeLessThan(1);
    expect(Math.abs(markerBox.width - 6 - imageBox.width * 0.37)).toBeLessThan(
      1,
    );
    await screenshots.getByRole("button", { name: "Hide position" }).click();
    await expect(marker).toHaveCount(0);
    await screenshots.getByRole("button", { name: "Show position" }).click();
    expect(requests.captures).toBe(0);
    await page.screenshot({
      path: testInfo.outputPath(`review-${width}.png`),
      fullPage: true,
    });
    await page
      .getByText("Technical details and history", { exact: true })
      .click();
    await expect(
      page.getByRole("region", { name: "Source context" }),
    ).toBeVisible();
    expect(requests.activity).toBe(0);
    await page.getByRole("button", { name: "Show activity history" }).click();
    await expect(
      page.getByText("No activity yet", { exact: true }),
    ).toBeVisible();
    expect(requests.activity).toBe(1);
    await page.reload();
    await expect(image).toBeVisible();
    expect(requests.captures).toBe(0);
  });
}

for (const state of ["empty", "unconfigured"] as const) {
  test(`review remains usable with ${state} screenshots`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 900 });
    const requests = await setup(page, state, "viewer");
    await page.goto("/translations/review-group");
    await expect(
      page.getByText(
        state === "empty"
          ? "No screenshot available"
          : "Screenshots are not available for this translation.",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Pending proposal" }),
    ).toContainText(text);
    await expect(
      page.getByRole("button", { name: "Approve translation", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Edit translation", exact: true }),
    ).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(requests.captures).toBe(0);
  });
}

test("unsaved edits disable generation and flag the saved image as stale", async ({
  page,
}) => {
  const requests = await setup(page, "ready");
  await page.goto("/translations/review-group");
  await expect(
    page.getByAltText("Compose screen preview with the selected translations"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Edit translation", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Proposed translation", exact: true })
    .fill("Conferma le modifiche");
  await expect(
    page.getByText(/This screenshot does not show your latest changes/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate screenshot", exact: true }),
  ).toBeDisabled();
  expect(requests.captures).toBe(0);
});
