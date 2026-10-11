import { expect, test, type Page } from "@playwright/test";
import { openNativeZoomBrowser } from "../../tools/phase7_zoom_extension/native_zoom.mjs";
import { waitForSubmissionDetail } from "../../tools/phase7_browser_readiness.mjs";

async function setup(page: Page, role = "product_manager_reviewer", loseAdmission = false, empty = false, longTarget?: string) {
  let posts = 0;
  let admissionPosts = 0;
  let recoveredAdmissions = 0;
  let accepted: object | undefined;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      new URL(request.url()).pathname.endsWith("/submission-batches")
    )
      admissionPosts++;
  });
  const now = new Date().toISOString();
  const review = {
    id: "review-1",
    product_id: "product-1",
    active_revision_id: "revision-1",
    state: "ready",
    attempt: 1,
    created_at: now,
    started_at: now,
    expires_at: new Date(Date.now() + 900000).toISOString(),
    error_code: null,
    file_count: 1,
    manifest_digest: "a".repeat(64),
    proposal_count: 1,
    value_count: 1,
    groups: [
      {
        id: "group-1",
        repository_id: "repo-1",
        workspace: "team",
        repository_slug: "mobile",
        target_branch: "main",
        target_head: "a".repeat(40),
        source_branch: "verboflex/server-reservation",
        proposal_ids: ["proposal-1"],
        value_count: 1,
        file_count: 1,
        sources: [],
      },
    ],
    destinations: longTarget ? [{
      mapping_id: "mapping-1", repository_id: "repo-1", workspace: "team",
      repository_slug: "mobile", allowed_targets: ["main", longTarget],
      default_target: "main", chosen_target: longTarget,
    }] : [],
    next_values_after: null,
    values: [
      {
        proposal_id: "proposal-1",
        value_id: "value-1",
        language: "it",
        selector_kind: "scalar",
        published_text: "Published <script>",
        proposed_text: "Proposed è",
      },
    ],
  };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown;
    let status = 200;
    if (path.endsWith("/auth/refresh"))
      body = {
        access_token: "review-token",
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      };
    else if (path.endsWith("/users/me"))
      body = {
        id: "actor",
        email: "actor@example.test",
        display_name: "Reviewer",
        roles: [role],
        must_change_password: false,
      };
    else if (path.endsWith("/system/status"))
      body = {
        api: "online",
        database: "online",
        redis: "online",
        worker: "online",
        checked_at: now,
      };
    else if (path.endsWith("/translations/options"))
      body = {
        products: [
          {
            id: "product-1",
            name: "Review product",
            active_revision_id: "revision-1",
          },
        ],
        languages: [],
      };
    else if (path.endsWith("/notifications/unread-count"))
      body = { unread_count: 0 };
    else if (path.endsWith("/notifications/stream"))
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: "",
      });
    else if (path.endsWith("/notifications/recent"))
      body = { items: [], next_cursor: null };
    else if (path.endsWith("/change-set-candidates"))
      body = {
        product_id: "product-1",
        active_revision_id: "revision-1",
        can_request_review: role !== "viewer",
        max_selected_proposals: 1,
        next_after: null,
        items: empty ? [] : [
          {
            proposal_id: "proposal-1",
            mapping_id: "mapping-1",
            version: 2,
            key: "menu.save",
            language: "it",
            state: "approved",
            value_count: 1,
            can_review: role !== "viewer",
            blocker: null,
          },
        ],
      };
    else if (path.endsWith("/change-sets") && empty)
      body = { items: [], next_cursor: null, page_size: 25 };
    else if (
      path.endsWith("/submission-reviews") &&
      route.request().method() === "POST"
    ) {
      posts++;
      expect(route.request().postDataJSON()).toEqual({
        proposals: [{ proposal_id: "proposal-1", expected_version: 2 }],
        targets: [],
      });
      status = 202;
      body = { ...review, state: "queued", values: [] };
    } else if (path.endsWith("/submission-batches") && loseAdmission) {
      const intent = route.request().postDataJSON();
      expect(intent.review_id).toBe(review.id);
      accepted = {
        id: "batch-1", product_id: "product-1", review_id: review.id,
        request_key: intent.request_key, created_at: now,
        groups: [{ id: "group-1", workspace: "team", repository_slug: "mobile", target_branch: "main" }],
      };
      return route.abort("failed");
    } else if (path.includes("/submission-batches/by-key/") && loseAdmission) {
      expect(accepted).toBeDefined();
      recoveredAdmissions++;
      body = accepted;
    } else if (path.endsWith("/submission-reviews/review-1")) body = review;
    else if (path.endsWith("/submission-reviews/review-1/files"))
      body = { items: [], next_after: null };
    else return route.fulfill({ status: 501, body: "Unexpected request" });
    return route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
  return () => ({ reviews: posts, admissions: admissionPosts, ...(loseAdmission ? { recoveries: recoveredAdmissions } : {}) });
}

test("reviewer opens full review at 320px and reload requires a fresh in-memory selection", async ({
  page,
}) => {
  const posts = await setup(page);
  await page.goto("/products/product-1/change-sets");
  await expect(
    page.getByRole("link", { name: "Change sets", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await page.getByRole("checkbox", { name: "Select menu.save (it)" }).check();
  await page
    .getByRole("button", { name: "Review selected changes (1)" })
    .click();
  await expect(page.getByText("Review ready", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Published <script>", { exact: true }),
  ).toBeVisible();
  expect(posts()).toEqual({ reviews: 1, admissions: 0 });
  await expect(page).toHaveURL(/\/change-sets\/review$/);
  await expect(page.getByText("Proposed è", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 320, height: 720 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(
    page.getByRole("button", { name: "Create pull request", exact: true }),
  ).toBeEnabled();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "No changes selected" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Back to selection" }),
  ).toBeVisible();
  expect(posts()).toEqual({ reviews: 1, admissions: 0 });
});

test("viewer sees current proposals without review action", async ({
  page,
}) => {
  const posts = await setup(page, "viewer");
  await page.goto("/products/product-1/change-sets");
  await expect(page.getByText("Submission access is read-only")).toBeVisible();
  await expect(page.getByRole("checkbox")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: /Review selected changes/ }),
  ).toHaveCount(0);
  expect(posts()).toEqual({ reviews: 0, admissions: 0 });
});

test("empty workspace reaches empty history by keyboard without an admission", async ({ page }) => {
  const posts = await setup(page, "viewer", false, true);
  await page.goto("/products/product-1/change-sets");
  await expect(page.getByRole("heading", { name: "No approved changes ready" })).toBeVisible();
  await expect(page.getByText("Submission access is read-only")).toBeVisible();
  await page.getByRole("button", { name: "Submission history", exact: true }).press("Enter");
  await expect(page.getByRole("heading", { name: "No submissions yet" })).toBeVisible();
  expect(posts()).toEqual({ reviews: 0, admissions: 0 });
});

test("long target remains inside its review control at native 200 percent and 320px", async ({}, testInfo) => {
  const browser = await openNativeZoomBrowser();
  try {
    const page = await browser.context.newPage();
    const branch = "release/" + "long-target-".repeat(12);
    await setup(page, "product_manager_reviewer", false, false, branch);
    await page.goto(`${process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:8080"}/products/product-1/change-sets`);
    await page.getByRole("checkbox", { name: "Select menu.save (it)" }).check();
    await page.getByRole("button", { name: "Review selected changes (1)" }).click();
    await expect(page.getByText("Review ready", { exact: true })).toBeVisible();
    const trigger = page.getByRole("combobox", { name: "Target branch for team/mobile (mapping-1)" });
    await expect(trigger).toContainText(branch);
    for (const [width, factor] of [[1440, 2], [320, 1]]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await browser.zoom(page, factor)).toBe(factor);
      const bounds = await trigger.evaluate((element) => {
        const control = element.getBoundingClientRect();
        const value = element.querySelector('[data-slot="select-value"]')!.getBoundingClientRect();
        const card = element.parentElement!;
        const before = card.querySelectorAll("p")[1].getBoundingClientRect();
        const after = card.querySelectorAll("p")[2].getBoundingClientRect();
        return { controlTop: control.top, controlBottom: control.bottom, valueTop: value.top, valueBottom: value.bottom, beforeBottom: before.bottom, afterTop: after.top };
      });
      expect(bounds.valueTop).toBeGreaterThanOrEqual(bounds.controlTop);
      expect(bounds.valueBottom).toBeLessThanOrEqual(bounds.controlBottom);
      expect(bounds.beforeBottom).toBeLessThanOrEqual(bounds.controlTop);
      expect(bounds.afterTop).toBeGreaterThanOrEqual(bounds.controlBottom);
      await browser.screenshot(page, testInfo.outputPath(`long-target-${width}.png`));
    }
  } finally {
    await browser.close();
  }
});

test("detail evidence waits for delayed sections before measuring the complete screenshot", async ({}, testInfo) => {
  const browser = await openNativeZoomBrowser();
  try {
    const page = await browser.context.newPage();
    await page.setContent(["Included proposals", "File changes", "Submitted values", "Activity"].map((name, index) => `<section aria-label="${name}"><h3>${name}</h3><p role="status">Loading</p><div id="section-${index}"></div></section>`).join("") + `<script>setTimeout(() => {for(const node of document.querySelectorAll('[role="status"]'))node.remove();for(const node of document.querySelectorAll('[id^="section-"]')){node.style.height='900px';node.textContent='Loaded complete section';}}, 600);</script>`);
    await waitForSubmissionDetail(page);
    expect(await page.getByRole("status").count()).toBe(0);
    const capture = await browser.screenshot(page, testInfo.outputPath("complete-delayed-detail.png"));
    expect(capture.pixel_height).toBeGreaterThan(3600);
    expect(capture.pixel_height).toBe(await page.evaluate(() => Math.ceil(document.documentElement.scrollHeight)));
  } finally {
    await browser.close();
  }
});

test("real Chromium tab zoom reflows selection and review at 200 percent", async ({}, testInfo) => {
  const browser = await openNativeZoomBrowser();
  try {
    const page = await browser.context.newPage();
    const posts = await setup(page);
    await page.goto(
      `${process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:8080"}/products/product-1/change-sets`,
    );
    await expect(
      page.getByRole("checkbox", { name: "Select menu.save (it)" }),
    ).toBeVisible();
    const baseDpr = await page.evaluate(() => devicePixelRatio);
    expect(await browser.zoom(page, 2)).toBe(2);
    expect(await page.evaluate(() => devicePixelRatio)).toBe(baseDpr * 2);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page
      .getByRole("checkbox", { name: "Select menu.save (it)" })
      .press("Space");
    await page
      .getByRole("button", { name: "Review selected changes (1)" })
      .press("Enter");
    await expect(page.getByText("Review ready", { exact: true })).toBeVisible();
    expect(await browser.zoom(page, 2)).toBe(2);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(posts()).toEqual({ reviews: 1, admissions: 0 });
    const capture = await browser.screenshot(page, testInfo.outputPath("native-zoom-review.png"));
    expect(capture.pixel_width).toBe(1440);
    expect(capture.pixel_width).toBe((await page.evaluate(() => innerWidth)) * 2);
  } finally {
    await browser.close();
  }
});

test("lost accepted response automatically recovers the same key without a second submission", async ({ page }) => {
  const requests = await setup(page, "product_manager_reviewer", true);
  await page.goto("/products/product-1/change-sets");
  await page.getByRole("checkbox", { name: "Select menu.save (it)" }).check();
  await page.getByRole("button", { name: "Review selected changes (1)" }).click();
  await expect(page.getByText("Review ready", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Create pull request", exact: true }).press("Enter");
  await expect(page.getByRole("heading", { name: "Submission queued", exact: true })).toBeFocused();
  await expect(page.getByRole("link", { name: "View change set: team/mobile → main" })).toHaveAttribute("href", "/products/product-1/change-sets/group-1");
  expect(requests()).toEqual({ reviews: 1, admissions: 1, recoveries: 1 });
});

test("durable history reload, partial outcomes and long RTL detail stay readable at 320px", async ({
  page,
}) => {
  const posts = await setup(page);
  const now = new Date().toISOString();
  const group = {
    id: "group-1",
    batch_id: "batch-1",
    status: "failed",
    stage: "pull_request",
    attempt: 1,
    repository_id: "repo-1",
    workspace: "team",
    repository_slug: "mobile",
    target_branch: "release/" + "long-target-".repeat(12),
    target_head: "a".repeat(40),
    source_branch: "verboflex/" + "long-source-".repeat(12),
    proposal_count: 1,
    value_count: 1,
    file_count: 1,
    error_code: "provider_unavailable",
    can_retry: true,
    can_reconcile: false,
    can_finalize: false,
    pr_id: null,
    pr_url: null,
    pr_state: null,
    created_at: now,
    attempt_started_at: now,
    finished_at: null,
    branch_commit: "a".repeat(40),
    commit_hash: "b".repeat(40),
    sources: [],
    provenance_available: true,
  };
  const success = {
    ...group,
    id: "group-success",
    status: "succeeded",
    can_retry: false,
    pr_id: 41,
    pr_url: "https://bitbucket.org/team/mobile/pull-requests/41",
    pr_state: "OPEN",
  };
  let retry = 0;
  await page.route("**/api/v1/products/product-1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown;
    if (path.endsWith("/change-sets"))
      data = { items: [group, success], next_cursor: null, page_size: 25 };
    else if (path.endsWith("/change-sets/group-1")) data = group;
    else if (path.endsWith("/submission-batches/batch-1"))
      data = { groups: [group, success] };
    else if (path.endsWith("/group-1/items"))
      data = {
        items: [
          {
            proposal_id: "proposal-1",
            proposal_version: 2,
            key_id: "key",
            key: "long.key.".repeat(20),
            key_truncated: false,
            language: "ar",
            value_count: 1,
            current_version: 3,
            newer_version_available: true,
          },
        ],
        next_cursor: null,
      };
    else if (path.endsWith("/group-1/values"))
      data = {
        items: [
          {
            proposal_id: "proposal-1",
            proposal_version: 2,
            value_id: "value",
            key: "key",
            language: "ar",
            selector_kind: "scalar",
            selector: "default",
            published_text: "Published",
            proposed_text: "<script>مرحبا</script>\n" + "قيمة ".repeat(40),
            file_path: "nested/".repeat(25) + "ar.xml",
            basis_revision_number: 1,
            basis_digest: "f".repeat(64),
            source: null,
          },
        ],
        next_cursor: null,
      };
    else if (path.endsWith("/group-1/files"))
      data = {
        items: [
          {
            id: "file",
            path: "nested/".repeat(25) + "ar.xml",
            format: "android_xml",
            changed_values: 1,
            before_sha256: "c".repeat(64),
            after_sha256: "d".repeat(64),
            before_bytes: 100,
            after_bytes: 120,
          },
        ],
        next_cursor: null,
      };
    else if (path.endsWith("/group-1/activity"))
      data = { items: [], next_cursor: null };
    else if (path.endsWith("/group-1/retry")) {
      retry++;
      data = { ...group, status: "queued", attempt: 2, can_retry: false };
    } else return route.fallback();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  });
  await page.goto("/products/product-1/change-sets/history");
  await page
    .getByRole("link", { name: /View change set/ })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "1 of 2 pull requests opened" }),
  ).toBeVisible();
  await expect(page.getByText(/Newer proposal available/)).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Open pull request #41/ }),
  ).toHaveAttribute("rel", "noopener noreferrer");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Submission failed", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 320, height: 720 });
  await expect(page.getByText(/<script>مرحبا/)).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "Back to submission history" }).click();
  await expect(page.locator("#history-group-1")).toBeFocused();
  expect(retry).toBe(0);
  expect(posts()).toEqual({ reviews: 0, admissions: 0 });
});
