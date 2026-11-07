import { expect, test, type Page } from "@playwright/test";

async function setup(page: Page, reviewer = true) {
  let attempts = 0;
  let created = false;
  const now = new Date().toISOString();
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown;
    if (path.endsWith("/auth/refresh"))
      body = {
        access_token: "synthetic",
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      };
    else if (path.endsWith("/users/me"))
      body = {
        id: "reviewer",
        email: "reviewer@example.test",
        display_name: "Reviewer",
        roles: [reviewer ? "product_manager_reviewer" : "viewer"],
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
            id: "product",
            name: "Synthetic Angular",
            active_revision_id: "revision",
          },
        ],
        languages: [],
      };
    else if (path.endsWith("/products/workspace"))
      body = {
        items: [
          {
            id: "product",
            name: "Synthetic Angular",
            coverage: null,
            imported_scope_count: 1,
            unimported_scope_count: 0,
            last_imported_at: null,
          },
        ],
        total: 1,
        page: 1,
        has_more: false,
      };
    else if (path.endsWith("/notifications/unread-count"))
      body = { unread_count: 0 };
    else if (path.endsWith("/notifications/recent"))
      body = { items: [], next_cursor: null };
    else if (path.endsWith("/notifications/stream"))
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: "",
      });
    else if (path.endsWith("/change-set-candidates"))
      body = {
        product_id: "product",
        active_revision_id: "revision",
        can_request_review: reviewer,
        max_selected_proposals: 100,
        items: [],
        next_after: null,
        destinations: [],
      };
    else if (path.endsWith("/branch-workflow"))
      body = {
        enabled: true,
        workflow_id: "workflow",
        repository: "synthetic/web",
        work_branch: "translations",
        target_branch: "main",
        can_publish: reviewer,
        can_add_language: reviewer,
        can_create_pr: reviewer && created,
        workflows: [],
        available_mappings: [],
        next_before: null,
        items: created
          ? [
              {
                id: "job",
                sequence: 1,
                kind: "language",
                state: "committed",
                label: "Language: fr-BE",
                created_at: now,
                commit_hash: "a".repeat(40),
                commit_url:
                  "https://bitbucket.org/synthetic/web/commits/" +
                  "a".repeat(40),
                pr_url: null,
                error_code: null,
                can_retry: false,
              },
            ]
          : [],
      };
    else if (
      path.endsWith("/languages") &&
      route.request().method() === "POST"
    ) {
      expect(reviewer).toBeTruthy();
      expect(route.request().postDataJSON()).toEqual({
        workflow_id: "workflow",
        language: "fr-BE",
      });
      attempts++;
      if (attempts === 1)
        return route.fulfill({
          status: 409,
          json: { detail: "Refresh the source" },
        });
      created = true;
      return route.fulfill({
        status: 202,
        json: { id: "job", state: "queued" },
      });
    } else
      return route.fulfill({
        status: 501,
        json: { detail: "Unexpected request" },
      });
    return route.fulfill({ json: body });
  });
  return () => attempts;
}

for (const width of [320, 1440])
  test(`reviewer adds a language, retries and reloads at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const attempts = await setup(page);
    await page.goto("/products/product/change-sets");
    const input = page.getByRole("textbox", {
      name: "New language",
      exact: true,
    });
    await input.fill("fr-BE");
    await page
      .getByRole("button", { name: "Add language", exact: true })
      .click();
    await expect(page.getByRole("alert")).toContainText(
      "Could not add this language",
    );
    await expect(input).toHaveValue("fr-BE");
    await page
      .getByRole("button", { name: "Add language", exact: true })
      .click();
    await expect(
      page.getByText("Saved to branch", { exact: true }),
    ).toBeVisible();
    expect(attempts()).toBe(2);
    await page.reload();
    await expect(
      page.getByText("Language: fr-BE", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Saved to branch", { exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
  });

test("viewer cannot initiate a new language", async ({ page }) => {
  const attempts = await setup(page, false);
  await page.goto("/products/product/change-sets");
  await expect(
    page.getByRole("heading", { name: "Approved changes", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Add language", exact: true }),
  ).toHaveCount(0);
  expect(attempts()).toBe(0);
});
