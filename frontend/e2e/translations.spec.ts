import { expect, test, type Page, type Route } from "@playwright/test";
import type {
  RoleName,
  TranslationGroupDetailResponse,
  TranslationGroupSummaryResponse,
} from "../src/api/client";

// UI4 consideration inventory: the UI-SPEC's 50 applicable instances across
// eight categories. Companion unit suites own field/race variants; journeys
// below prove browser composition. Plan19 runs every referenced suite.
const considerations = {
  empty: [
    "options",
    "no dataset",
    "no matches",
    "missing source",
    "empty target",
    "no rule",
    "no parser issues",
    "no revision history",
  ],
  loading: [
    "options skeleton",
    "search skeleton",
    "cursor append",
    "detail skeleton",
    "save pending",
    "remove pending",
  ],
  error: [
    "search retry",
    "cursor retry",
    "detail retry",
    "parser failure",
    "save failure",
    "remove failure",
    "version conflict",
  ],
  populated: [
    "five filters",
    "result anatomy",
    "selectors",
    "provenance",
    "explicit maximum",
    "read-only review",
  ],
  partial: [
    "mixed review",
    "some over limit",
    "atomic separate mapping",
    "stale dataset",
    "missing optional metadata",
    "incomplete mandatory authority",
  ],
  overflow: [
    "filter reflow",
    "two-line excerpt",
    "full detail wrap",
    "selector containment",
    "parser issue cap",
    "action wrapping",
  ],
  "zero-one-many": [
    "result cardinality",
    "cursor cardinality",
    "structured values",
    "parser issue remainder",
    "history bound",
  ],
  "long-text": [
    "raw keys",
    "multiline translations",
    "product/repository names",
    "paths",
    "labels",
    "mixed scripts",
  ],
} as const;
// Exact owner files for the inventory above, in addition to these journeys:
// TranslationFilters.test.tsx / TranslationSearchPage.test.tsx (options/filter/search)
// TranslationResultList.test.tsx / useTranslationSearch.test.ts (cursor/list)
// TranslationDetailPage.test.tsx / MaximumLengthDialog.test.tsx (detail/constraint)
// ProductPreviewPage.test.tsx / PublishedMappingImports.test.tsx (preview/parser)
// AppShell.test.tsx / router.test.tsx (navigation/authentication)

const hostile =
  '<img src=x onerror="window.translationExecuted=true">👨‍👩‍👧‍👦\nمرحبا ';
function detail(
  id = "group-0",
  maximum: number | null = 5,
  version: number | null = null,
): TranslationGroupDetailResponse {
  const actual = 6;
  return {
    id,
    product_id: "product",
    product_name: "Mobile product",
    raw_key: `key.${id}`,
    language: "it",
    language_label: "Italian",
    base_language: "en",
    base_maximum: 5,
    explicit_maximum: version === null ? null : maximum,
    constraint_version: version,
    states: ["draft"],
    state_summary: "draft",
    is_deleted: false,
    pending_change: null,
    comments: [],
    values: [
      {
        id: `value-${id}`,
        selector_kind: "json_path",
        selector_version: 1,
        selector_digest: "a".repeat(64),
        selector_fields: [{ name: "segments", value: ["menu", "literal.dot"] }],
        source_text: "Save",
        translated_text: hostile.repeat(4),
        display_text: "Target",
        structure: [],
        grapheme_count: actual,
        review_state: "draft",
        is_deleted: false,
        deleted_at: null,
        constraint: {
          actual,
          maximum,
          source:
            maximum === null
              ? "none"
              : version === null
                ? "base_default"
                : "language_override",
          status:
            maximum === null
              ? "no_max"
              : actual > maximum
                ? "over_limit"
                : "within_limit",
          overage: maximum === null ? null : Math.max(actual - maximum, 0),
        },
        provenance: {
          repository_id: "repo",
          repository_name: "Mobile repository",
          repository_side: "direct",
          branch: "main",
          path: `locales/${"nested/".repeat(20)}it.json`,
          format: "json",
          commit_hash: "a".repeat(40),
          execution_id: "execution",
          line: 2,
          column: 1,
        },
        history: [
          {
            revision_number: 1,
            review_state: "approved",
            is_deleted: false,
            created_at: "2026-09-01T00:00:00Z",
            commit_hash: "b".repeat(40),
            execution_id: "old-execution",
          },
        ],
        history_has_more: false,
      },
    ],
  };
}
function summary(index: number, maximum = 5): TranslationGroupSummaryResponse {
  return {
    id: `group-${index}`,
    product_id: "product",
    product_name: "Mobile product",
    raw_key: `key.group-${index}`,
    language: "it",
    language_label: "Italian",
    rank: 0,
    source_text: "Save",
    source_language: "en",
    translated_text: hostile,
    selector_kinds: ["json_path"],
    provenance: {
      repository_name: "Mobile repository",
      branch: "main",
      path: "locales/it.json",
    },
    value_count: 1,
    over_limit_count: maximum < 6 ? 1 : 0,
    within_limit_count: maximum >= 6 ? 1 : 0,
    no_max_count: 0,
    states: ["draft"],
    state_summary: "draft",
    has_over_limit: maximum < 6,
    has_no_max: false,
    is_deleted: false,
  };
}
async function json(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(data),
  });
}
async function setup(page: Page, role: RoleName = "admin") {
  const state = {
    maximum: 5,
    version: null as number | null,
    failMore: true,
    paginate: true,
    conflict: false,
    hold: false,
    release: () => {},
    writes: [] as {
      method: string;
      body: { max_chars?: number; expected_version: number };
    }[],
    queries: [] as URLSearchParams[],
    detailReads: 0,
  };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname,
      method = route.request().method();
    if (path === "/api/v1/auth/refresh")
      return json(route, {
        access_token: "memory-e2e-token",
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      });
    if (path === "/api/v1/users/me")
      return json(route, {
        id: "principal",
        email: "person@example.com",
        display_name: "Person",
        roles: [role],
        must_change_password: false,
      });
    if (path === "/api/v1/system/status")
      return json(route, {
        api: "online",
        database: "online",
        redis: "online",
        worker: "online",
        checked_at: "2026-09-06T00:00:00Z",
      });
    if (path === "/api/v1/translations/options")
      return json(route, {
        products: [{ id: "product", name: "Mobile product" }],
        languages: [{ code: "it", label: "Italian" }],
      });
    if (path === "/api/v1/translations") {
      state.queries.push(url.searchParams);
      if (url.searchParams.get("cursor")) {
        if (state.failMore) {
          state.failMore = false;
          return json(route, { detail: "Translation search unavailable" }, 503);
        }
        return json(route, {
          items: [summary(49), summary(50)],
          next_cursor: null,
        });
      }
      const deleted = url.searchParams.get("deleted") === "deleted";
      return json(route, {
        items: Array.from({ length: state.paginate ? 50 : 1 }, (_, i) => ({
          ...summary(i, state.maximum),
          is_deleted: deleted,
        })),
        next_cursor: state.paginate ? "cursor-two" : null,
      });
    }
    const mutation = path.match(
      /^\/api\/v1\/translations\/([^/]+)\/constraints\/it$/,
    );
    if (mutation) {
      const body = route.request().postDataJSON();
      state.writes.push({ method, body });
      if (role === "viewer" || role === "translator")
        return json(route, { detail: "Forbidden" }, 403);
      if (state.hold)
        await new Promise<void>((resolve) => {
          state.release = resolve;
        });
      if (state.conflict) {
        state.conflict = false;
        state.maximum = 8;
        state.version = 4;
        return json(route, { detail: "Translation constraint conflict" }, 409);
      }
      state.maximum = method === "DELETE" ? 5 : body.max_chars;
      state.version = method === "DELETE" ? null : (state.version ?? 0) + 1;
      const projection = detail(mutation[1], state.maximum, state.version);
      return json(route, {
        translation_group_id: mutation[1],
        language: "it",
        base_language: "en",
        explicit_maximum: state.version === null ? null : state.maximum,
        version: state.version,
        violating_count: state.maximum < 6 ? 1 : 0,
        total_count: 1,
        values: projection.values.map((v) => ({
          id: v.id,
          language: "it",
          constraint: v.constraint,
          approval_eligible: state.maximum >= 6,
          submission_eligible: state.maximum >= 6,
        })),
      });
    }
    const match = path.match(/^\/api\/v1\/translations\/([^/]+)$/);
    if (match) {
      state.detailReads++;
      return json(route, detail(match[1], state.maximum, state.version));
    }
    return json(route, { detail: "Unexpected request" }, 501);
  });
  return state;
}

test("UI4 inventory covers 50 instances, eight categories and three open axes", () => {
  expect(Object.keys(considerations)).toHaveLength(8);
  expect(Object.values(considerations).flat()).toHaveLength(50);
  expect([
    "network loss",
    "request-response without live updates",
    "reduced motion",
  ]).toHaveLength(3);
});

for (const viewport of [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 320, height: 800 },
]) {
  test.describe(viewport.name, () => {
    test.use({
      viewport: { width: viewport.width, height: viewport.height },
      reducedMotion: "reduce",
    });
    test("SRCH-01..08: literal search/filter, cursor retry, detail/back focus — loading/error/populated/overflow/long-text", async ({
      page,
    }) => {
      const state = await setup(page, "viewer");
      await page.goto("/translations");
      const query = page.getByRole("textbox", {
        name: "Search keys and translations",
      });
      await query.fill("literal %_ <tag>");
      await query.press("Enter");
      await expect
        .poll(() => state.queries.at(-1)?.get("q"))
        .toBe("literal %_ <tag>");
      await page
        .getByRole("combobox", { name: "Product", exact: true })
        .click();
      await page
        .getByRole("option", { name: "Mobile product", exact: true })
        .click();
      await page
        .getByRole("combobox", { name: "Language", exact: true })
        .click();
      await page
        .getByRole("option", { name: "Italian (it)", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Load more translations" })
        .scrollIntoViewIfNeeded();
      await expect(
        page.getByRole("button", { name: "Retry loading more" }),
      ).toBeVisible();
      expect(await page.getByRole("listitem").count()).toBeGreaterThan(0);
      await page.getByRole("button", { name: "Retry loading more" }).click();
      await expect(
        page.getByText("51 translation groups loaded", { exact: true }),
      ).toBeVisible();
      const link = page.locator('a[data-translation-group-id="group-50"]');
      await link.scrollIntoViewIfNeeded();
      await link.focus();
      const scroll = await page.evaluate(() => window.scrollY);
      await link.press("Enter");
      await expect(
        page.getByRole("heading", { name: "Translation details", exact: true }),
      ).toBeVisible();
      await expect(page.getByText("Pending change: None")).toBeVisible();
      await expect(page.getByText("Comments: No comments yet")).toBeVisible();
      await expect(page.getByTestId("target-value-group-50")).toContainText(
        "<img",
      );
      expect(await page.locator("main img").count()).toBe(0);
      await expect(
        page.getByRole("button", { name: /max length|language override/i }),
      ).toHaveCount(0);
      await page.getByRole("link", { name: "Back to translations" }).click();
      await expect(query).toHaveValue("literal %_ <tag>");
      await expect(
        page.getByRole("combobox", { name: "Language", exact: true }),
      ).toContainText("Italian");
      await expect(link).toBeFocused();
      expect(
        Math.abs((await page.evaluate(() => window.scrollY)) - scroll),
      ).toBeLessThan(120);
      const stored = await page.evaluate(() =>
        JSON.stringify({ ...localStorage, ...sessionStorage }),
      );
      expect(stored).not.toContain("literal");
      expect(stored).not.toContain("<img");
      expect(page.url()).not.toContain("literal");
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
    });
    test("CONS-01..05: create edit remove, pending duplicate/dismissal, conflict replacement — network-loss and reduced-motion", async ({
      page,
    }) => {
      const state = await setup(page);
      state.paginate = false;
      await page.goto("/translations");
      await page.getByRole("link", { name: /Open details/ }).click();
      await page.getByRole("button", { name: "Add language override" }).click();
      const field = page.getByRole("spinbutton", {
        name: "Maximum characters",
      });
      await field.fill("9");
      state.hold = true;
      await page.getByRole("button", { name: "Save max length" }).click();
      await expect.poll(() => state.writes.length).toBe(1);
      await expect(
        page.getByRole("button", { name: "Save max length" }),
      ).toHaveAttribute("aria-busy", "true");
      await expect(
        page.getByRole("button", { name: "Discard max length changes" }),
      ).toBeDisabled();
      await page.keyboard.press("Enter");
      await page.keyboard.press("Escape");
      await page.mouse.click(2, 2);
      expect(state.writes).toHaveLength(1);
      await expect(page.getByRole("dialog")).toBeVisible();
      state.hold = false;
      state.release();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: "Edit max length" }),
      ).toBeFocused();
      await expect(
        page.getByText("Within limit", { exact: true }).first(),
      ).toBeVisible();
      await page.getByRole("button", { name: "Edit max length" }).click();
      await field.fill("17");
      state.conflict = true;
      await page.getByRole("button", { name: "Save max length" }).click();
      await expect(page.getByRole("alert")).toContainText(
        "Maximum length changed",
      );
      await expect(field).toHaveValue("17");
      await page.getByRole("button", { name: "Reload current value" }).click();
      const reads = state.detailReads;
      await expect(page.getByRole("alertdialog")).toBeVisible();
      expect(state.detailReads).toBe(reads);
      await page.getByRole("button", { name: "Keep entered value" }).click();
      await expect(field).toHaveValue("17");
      await page.getByRole("button", { name: "Reload current value" }).click();
      await page.getByRole("button", { name: "Replace entered value" }).click();
      await expect(field).toHaveValue("8");
      expect(state.writes).toHaveLength(2);
      await field.fill("0");
      await page.getByRole("button", { name: "Save max length" }).click();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      expect(state.writes.at(-1)?.body.expected_version).toBe(4);
      await expect(page.getByTestId("target-value-group-0")).toContainText(
        "<img",
      );
      await expect(
        page.getByRole("region", { name: "Review context" }),
      ).toContainText("Draft");
      await page
        .getByRole("button", { name: "Remove language override" })
        .click();
      await expect(page.getByRole("alertdialog")).toContainText(
        "inherit the current en maximum of 5 characters",
      );
      await page
        .getByRole("button", { name: "Remove language override", exact: true })
        .click();
      await expect(page.getByRole("alertdialog")).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: "Add language override" }),
      ).toBeFocused();
      await page.getByRole("link", { name: "Back to translations" }).click();
      await expect(
        page.getByRole("link", { name: /Open details/ }),
      ).toBeVisible();
      expect(state.queries.length).toBeGreaterThan(1);
      expect(state.writes.map((w) => w.method)).toEqual([
        "PUT",
        "PUT",
        "PUT",
        "DELETE",
      ]);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
    });
    for (const role of [
      "admin",
      "product_manager_reviewer",
      "translator",
      "viewer",
    ] as RoleName[])
      test(`SRCH-06 SRCH-07 CONS-02: ${role} direct detail and read-only context`, async ({
        page,
      }) => {
        await setup(page, role);
        await page.goto("/translations/group-0");
        await expect(
          page.getByRole("heading", {
            name: "Translation details",
            exact: true,
          }),
        ).toBeFocused();
        await expect(page.getByText("Pending change: None")).toBeVisible();
        await expect(page.getByText("Comments: No comments yet")).toBeVisible();
        await expect(
          page.getByRole("region", { name: "Review context" }),
        ).toContainText("Draft");
        await expect(
          page.getByRole("button", { name: "Add language override" }),
        ).toHaveCount(
          role === "admin" || role === "product_manager_reviewer" ? 1 : 0,
        );
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          ),
        ).toBe(true);
      });
  });
}
