import { expect, test, type Page } from "@playwright/test";

async function setup(page: Page, admin = true, timedOut = false) {
  let starts = 0;
  let completed = false;
  let sourceReads = 0;
  const now = new Date().toISOString();
  const revision = {
    id: "revision",
    version: 1,
    is_published: true,
    name: "Synthetic project",
    description: null,
  };
  const mapping = {
    id: "mapping",
    topology: "separate",
    primary_repository_id: "app",
    primary_source_branch: "main",
    translations_repository_id: "translations",
    translations_source_branch: "master",
    allowed_target_branches: ["release"],
    default_target_branch: "release",
    selected_layout_candidate_id: "layout",
    selected_layout_version: 1,
    candidate_version: 1,
  };
  function imported() {
    const active = starts > 0 && !completed;
    return {
      id: "import",
      mapping_id: "mapping",
      active_revision_id: "revision",
      topology: "separate",
      repository_sides: [
        { role: "keys", repository_id: "app", source_branch: "main" },
        {
          role: "translations",
          repository_id: "translations",
          source_branch: "master",
        },
      ],
      state: timedOut ? "may_be_stale" : active ? "running" : "current",
      action: timedOut
        ? "retry_import"
        : active
          ? "import_in_progress"
          : "refresh_import",
      capability: "ready",
      dataset_status: timedOut ? "retained" : "active",
      execution_number: starts + 1,
      latest_execution_at: now,
      retry_count: 0,
      error_category: timedOut ? "timeout" : null,
      error_message: null,
      parser_issues: [],
      parser_issue_remaining_count: 0,
      active_baseline: {
        imported_at: "2026-01-01T12:00:00Z",
        source_references: [
          {
            position: 0,
            repository_side: "keys",
            repository_id: "app",
            source_branch: "main",
            commit_hash: (completed ? "c" : "a").repeat(40),
            path: "Main.kt",
            sha256: "a".repeat(64),
            size_bytes: 20,
          },
          {
            position: 1,
            repository_side: "translations",
            repository_id: "translations",
            source_branch: "master",
            commit_hash: (completed ? "d" : "b").repeat(40),
            path: "base/strings.xml",
            sha256: "b".repeat(64),
            size_bytes: 30,
          },
        ],
      },
    };
  }
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let json: unknown;
    if (path.endsWith("/auth/refresh"))
      json = {
        access_token: "synthetic",
        token_type: "bearer",
        expires_in: 900,
        must_change_password: false,
      };
    else if (path.endsWith("/users/me"))
      json = {
        id: "user",
        email: "user@example.test",
        display_name: "Synthetic user",
        roles: [admin ? "admin" : "viewer"],
        must_change_password: false,
      };
    else if (path.endsWith("/products/workspace"))
      json = {
        items: [
          {
            id: "product",
            name: "Synthetic project",
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
    else if (path.endsWith("/admin/products/product")) {
      sourceReads++;
      json = {
        id: "product",
        name: "Synthetic project",
        is_active: true,
        active_revision: revision,
        candidate_revision: null,
        affected_mapping_count: 0,
      };
    } else if (path.endsWith("/revisions/revision/mappings"))
      json = { items: [mapping], next_cursor: null };
    else if (path.includes("/admin/repositories/")) {
      const id = path.split("/").at(-1);
      json = {
        id,
        workspace: "synthetic",
        repository_slug: id,
        descriptive_name: id === "app" ? "Application" : "Shared translations",
        provider: "bitbucket",
      };
    } else if (path.endsWith("/published/mapping-imports"))
      json = { items: [imported()], next_cursor: null };
    else if (path.endsWith("/published/mappings/mapping/imports")) {
      expect(route.request().method()).toBe("POST");
      starts++;
      return route.fulfill({ status: 202, json: imported() });
    } else if (path.endsWith("/imports/import")) json = imported();
    else if (path.endsWith("/translations/options"))
      json = {
        products: [{ id: "product", name: "Synthetic project" }],
        languages: [],
      };
    else if (path.endsWith("/translations/keys"))
      json = {
        items: [],
        next_cursor: null,
        available_languages: [],
        available_languages_truncated: false,
        default_selection_capped: false,
        visible_languages: [],
      };
    else if (path.endsWith("/notifications/unread-count"))
      json = { unread_count: 0 };
    else if (path.endsWith("/notifications/recent"))
      json = { items: [], next_cursor: null };
    else
      return route.fulfill({
        status: 503,
        json: { detail: "Unrelated synthetic service unavailable" },
      });
    return route.fulfill({ json });
  });
  return {
    starts: () => starts,
    sourceReads: () => sourceReads,
    complete: () => {
      completed = true;
    },
  };
}

for (const width of [320, 1440]) {
  test(`refreshes configured branches and resumes after reload at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const fixture = await setup(page);
    await page.goto("/products/product/strings");
    await page
      .getByRole("link", { name: "Update catalog", exact: true })
      .click();
    const scope = page.getByRole("article", {
      name: "Application · Shared translations",
    });
    await scope.getByText("Source details", { exact: true }).click();
    await expect(scope).toContainText("Application");
    await expect(scope).toContainText("Shared translations");
    await expect(scope).toContainText("main");
    await expect(scope).toContainText("master");
    expect(fixture.starts()).toBe(0);
    await scope
      .getByRole("button", { name: "Update catalog", exact: true })
      .click();
    await expect(
      scope.getByRole("button", { name: "Update in progress" }),
    ).toBeDisabled();
    await page.reload();
    await scope.getByText("Source details", { exact: true }).click();
    await expect(
      scope.getByRole("button", { name: "Update in progress" }),
    ).toBeDisabled();
    expect(fixture.starts()).toBe(1);
    fixture.complete();
    await expect(scope).toContainText("cccccccccccc");
    await expect(scope).toContainText("dddddddddddd");
    await expect(
      scope.getByRole("button", { name: "Update catalog", exact: true }),
    ).toBeEnabled();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `/tmp/verboflex-source-updates-${width}.png`,
      fullPage: true,
    });
    await page.getByRole("link", { name: "Strings", exact: true }).click();
    await expect(page).toHaveURL(/\/products\/product\/strings$/);
    expect(fixture.starts()).toBe(1);
  });
}

test("denies direct source update access to a viewer before reading source configuration", async ({
  page,
}) => {
  const fixture = await setup(page, false);
  await page.goto("/products/product/source-updates");
  await expect(page.getByText("Administrator access required")).toBeVisible();
  expect(fixture.starts()).toBe(0);
  expect(fixture.sourceReads()).toBe(0);
});

test.describe("Italian publication and catalog messages", () => {
  test.use({ locale: "it-IT" });

  test("opens the existing review and explains why later changes are waiting", async ({
    page,
  }, testInfo) => {
    await setup(page);
    const url = "https://bitbucket.org/example/catalog/pull-requests/8";
    await page.route("**/branch-workflow*", (route) => {
      expect(route.request().method()).toBe("GET");
      return route.fulfill({
        json: {
          enabled: true,
          workflow_id: "workflow",
          work_branch: "review",
          target_branch: "main",
          repository: "translations",
          can_publish: true,
          can_create_pr: false,
          open_pr_url: url,
          waiting_changes: 9,
          blocked_change: {
            id: "older",
            label: "welcome_title (it)",
            kind: "commit",
            state: "blocked",
            error_code: "import_changed",
            can_retry: true,
          },
          items: [],
          workflows: [],
          next_before: null,
        },
      });
    });
    await page.goto("/products/product/change-sets");
    const panel = page
      .locator("section")
      .filter({
        has: page.getByRole("link", { name: "Apri la revisione su Bitbucket" }),
      })
      .last();
    await expect(
      panel.getByRole("link", { name: "Apri la revisione su Bitbucket" }),
    ).toHaveAttribute("href", url);
    await expect(
      panel.getByText("Pubblicazione ferma su welcome_title (it)"),
    ).toBeVisible();
    await expect(
      panel.getByText("Modifiche ancora da inviare (9)"),
    ).toBeVisible();
    await expect(
      panel.getByRole("button", { name: "Crea una pull request" }),
    ).toHaveCount(0);
    await panel.screenshot({ path: testInfo.outputPath("pubblicazione.png") });
  });

  test("keeps a dated link to the catalog after a timeout", async ({
    page,
  }, testInfo) => {
    await setup(page, true, true);
    await page.goto("/products/product/source-updates");
    const card = page.getByRole("article");
    await expect(
      card.getByText("Il catalogo non è stato aggiornato", { exact: true }),
    ).toBeVisible();
    await expect(
      card.getByRole("link", { name: "Apri il catalogo traduzioni" }),
    ).toBeVisible();
    await expect(
      card.getByText(/Le stringhe disponibili sono quelle/),
    ).toBeVisible();
    await expect(
      card.getByRole("button", { name: "Riprova ad aggiornare" }),
    ).toBeEnabled();
    await card.screenshot({ path: testInfo.outputPath("catalogo.png") });
  });
});
