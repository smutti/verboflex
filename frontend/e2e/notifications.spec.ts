import { expect, test, type Page, type Route } from "@playwright/test";

async function reply(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function notice(id = "notice-1", read = false) {
  return {
    id,
    actor: { user_id: "author", display_name: "Ada Reviewer" },
    comment_status: "available",
    created_at: "2026-09-10T12:00:00Z",
    is_read: read,
    key_excerpt: "checkout.title",
    language: "it",
    originating_comment_id: "comment-1",
    product: { id: "product", name: "Mobile" },
    read_at: read ? "2026-09-10T12:01:00Z" : null,
    translation_group_id: "group-review",
  };
}

async function mockNotifications(
  page: Page,
  principal: "alice" | "bob" = "alice",
) {
  let read = false;
  const own = principal === "alice";
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/v1/auth/refresh")
      return reply(route, {
        access_token: `token-${principal}`,
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      });
    if (path === "/api/v1/users/me")
      return reply(route, {
        id: principal,
        email: `${principal}@example.com`,
        display_name: principal,
        roles: ["viewer"],
        must_change_password: false,
      });
    if (path === "/api/v1/system/status")
      return reply(route, {
        api: "online",
        database: "online",
        redis: "online",
        worker: "online",
        checked_at: "2026-09-10T12:00:00Z",
      });
    if (path === "/api/v1/notifications/unread-count")
      return reply(route, { unread_count: own && !read ? 100 : 0 });
    if (path === "/api/v1/notifications/recent")
      return reply(route, {
        items: own ? [notice("notice-1", read)] : [],
        next_cursor: null,
      });
    if (path === "/api/v1/notifications/stream")
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: "",
      });
    if (path === "/api/v1/notifications")
      return reply(route, {
        items:
          own && (url.searchParams.get("view") !== "unread" || !read)
            ? [notice("notice-1", read)]
            : [],
        next_cursor: null,
      });
    if (path === "/api/v1/notifications/notice-1/read") {
      read = true;
      return reply(route, { item: notice("notice-1", true), unread_count: 0 });
    }
    if (path === "/api/v1/translations/options")
      return reply(route, {
        products: [{ id: "product", name: "Mobile" }],
        languages: [{ code: "it", label: "Italian" }],
      });
    if (path === "/api/v1/translations/group-review/comments/anchor") {
      if (!own) return reply(route, { detail: "Comment unavailable" }, 404);
      return reply(route, {
        target_id: "comment-1",
        items: [
          {
            id: "comment-1",
            translation_group_id: "group-review",
            language: "it",
            author: { id: "author", display_name: "Ada Reviewer" },
            body: "Please verify this exact comment",
            mentions: [],
            status: "available",
            current_version: 1,
            edited: false,
            created_at: "2026-09-10T12:00:00Z",
            updated_at: "2026-09-10T12:00:00Z",
            deleted_at: null,
            deleted_by: null,
          },
        ],
      });
    }
    if (path === "/api/v1/notifications/by-comment/comment-1/read") {
      read = true;
      return reply(route, { item: notice("notice-1", true), unread_count: 0 });
    }
    if (path === "/api/v1/translations/group-review")
      return reply(route, {
        id: "group-review",
        product_id: "product",
        product_name: "Mobile",
        raw_key: "checkout.title",
        language: "it",
        language_label: "Italian",
        base_language: "en",
        base_maximum: null,
        explicit_maximum: null,
        constraint_version: null,
        states: ["approved"],
        state_summary: "approved",
        is_deleted: false,
        pending_change: null,
        comment_count: 1,
        mutation_eligible: false,
        review_eligible: false,
        values: [
          {
            id: "value-1",
            selector_version: 1,
            selector_digest: "a".repeat(64),
            selector_kind: "scalar",
            selector_fields: [],
            source_text: "Checkout",
            translated_text: "Cassa",
            display_text: "Cassa",
            structure: [],
            grapheme_count: 5,
            constraint: {
              actual: 5,
              maximum: null,
              source: "none",
              status: "no_max",
              overage: null,
            },
            review_state: "approved",
            is_deleted: false,
            deleted_at: null,
            provenance: {
              repository_id: "repo",
              repository_name: "Repo",
              repository_side: "direct",
              branch: "main",
              path: "it.json",
              format: "json",
              commit_hash: "b".repeat(40),
              execution_id: "import",
              line: 1,
              column: 1,
            },
            history: [
              {
                revision_number: 1,
                revision_digest: "d".repeat(64),
                review_state: "approved",
                is_deleted: false,
                created_at: "2026-09-01T00:00:00Z",
                commit_hash: "b".repeat(40),
                execution_id: "import",
              },
            ],
            history_has_more: false,
          },
        ],
      });
    if (path === "/api/v1/translations/group-review/comments")
      return reply(route, { items: [], older_cursor: null });
    return reply(route, { detail: "Unavailable" }, 404);
  });
}

test("bell exposes the exact accessible count, visual 99+, recent items and read reconciliation", async ({
  page,
}) => {
  await mockNotifications(page);
  await page.goto("/");
  const bell = page.getByRole("button", {
    name: "Notifications, 100 unread notifications",
  });
  await expect(bell).toBeVisible();
  await expect(bell).toContainText("99+");
  await bell.click();
  await expect(page.getByRole("menu", { name: "Notifications" })).toContainText(
    "checkout.title",
  );
  await page.getByRole("menuitem", { name: /View all notifications/ }).click();
  await expect(
    page.getByRole("heading", { name: "Notifications" }),
  ).toBeVisible();
  await expect(
    page.getByRole("article", { name: "Notification from Ada Reviewer" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Mark as read" }).click();
  await expect(
    page.getByRole("article", { name: "Notification from Ada Reviewer" }),
  ).toContainText("Read");
  await page.getByRole("tab", { name: "Unread" }).click();
  await expect(page.getByText("You're all caught up")).toBeVisible();
});

test("keyboard notification retains comment focus through the menu exit animation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockNotifications(page);
  await page.goto("/translations/group-review");
  await expect(
    page.getByRole("heading", { name: "Translation details" }),
  ).toBeFocused();
  // Keep native Presence/animation handling observable while the route loads.
  await page.addStyleTag({
    content:
      '[data-slot="dropdown-menu-content"][data-state="closed"] { animation-duration: 500ms; }',
  });
  const bell = page.getByRole("button", {
    name: "Notifications, 100 unread notifications",
  });
  await bell.focus();
  await page.keyboard.press("Enter");
  const notification = page.getByRole("menuitem", { name: /Ada Reviewer/ });
  await notification.hover();
  await notification.focus();
  await page.keyboard.press("Enter");
  const target = page.getByTestId("exact-comment-comment-1");
  await expect(target).toBeVisible();
  await expect(page.locator('[data-slot="dropdown-menu-content"]')).toHaveCount(
    0,
  );
  await expect(target).toBeFocused();
  const refreshedBell = page.getByRole("button", {
    name: "Notifications, no unread notifications",
  });
  await refreshedBell.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menu", { name: "Notifications" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator('[data-slot="dropdown-menu-content"]')).toHaveCount(
    0,
  );
  await expect(refreshedBell).toBeFocused();
});

test("notification deep link focuses the exact comment before marking only its origin read", async ({
  page,
}) => {
  await mockNotifications(page);
  await page.goto("/translations/group-review?comment=comment-1");
  const target = page.getByText("Please verify this exact comment");
  await expect(target).toBeVisible();
  await expect(page.getByTestId("exact-comment-comment-1")).toBeFocused();
  await expect(
    page.getByRole("button", {
      name: "Notifications, no unread notifications",
    }),
  ).toBeVisible();
});

test("a foreign principal receives empty notification state and generic unavailable deep links", async ({
  page,
}) => {
  await mockNotifications(page, "bob");
  await page.goto("/notifications");
  await expect(page.getByText("No notifications yet")).toBeVisible();
  await expect(page.getByText("checkout.title")).toHaveCount(0);
  await page.goto("/translations/group-review?comment=comment-1");
  await expect(page.getByText("Comment not available")).toBeVisible();
  await expect(page.getByText("Please verify this exact comment")).toHaveCount(
    0,
  );
});
