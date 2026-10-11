import { expect, test, type Page, type Route } from "@playwright/test";

const digest = "a".repeat(64);
const revisionDigest = "d".repeat(64);

async function reply(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function detail(role: string, pendingText: string | null = null) {
  return {
    id: "group-review",
    product_id: "product",
    product_name: "Mobile",
    raw_key: "menu.save",
    language: "it",
    language_label: "Italian",
    base_language: "en",
    base_maximum: null,
    explicit_maximum: null,
    constraint_version: null,
    states: ["approved"],
    state_summary: "approved",
    is_deleted: false,
    comment_count: 0,
    mutation_eligible: role !== "viewer",
    review_eligible: role === "admin" || role === "product_manager_reviewer",
    pending_change:
      pendingText === null
        ? null
        : {
            version: 1,
            state: "draft",
            reconciliation_required: false,
            updated_by: "translator",
            updated_at: "2026-09-10T10:00:00Z",
            values: [
              {
                translation_value_id: "value-1",
                selector_version: 1,
                selector_digest: digest,
                basis_revision_number: 1,
                basis_digest: revisionDigest,
                text: pendingText,
                grapheme_count: [...pendingText].length,
                maximum: null,
                is_over_limit: false,
                approval_eligible: true,
                submission_eligible: true,
              },
            ],
          },
    values: [
      {
        id: "value-1",
        selector_version: 1,
        selector_digest: digest,
        selector_kind: "scalar",
        selector_fields: [],
        source_text: "Save",
        translated_text: "Salva pubblicato",
        display_text: "Salva pubblicato",
        structure: [],
        grapheme_count: 17,
        constraint: {
          actual: 17,
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
          repository_name: "Mobile repo",
          repository_side: "direct",
          branch: "main",
          path: "locales/it.json",
          format: "json",
          commit_hash: "b".repeat(40),
          execution_id: "import-1",
          line: 2,
          column: 1,
        },
        history: [
          {
            revision_number: 1,
            revision_digest: revisionDigest,
            review_state: "approved",
            is_deleted: false,
            created_at: "2026-09-01T00:00:00Z",
            commit_hash: "b".repeat(40),
            execution_id: "import-1",
          },
        ],
        history_has_more: false,
      },
    ],
  };
}

function proposal(role: string, text: string, state = "draft") {
  const data = detail(role, text);
  return {
    translation_group_id: data.id,
    language: data.language,
    version: state === "draft" ? 1 : 2,
    state,
    reconciliation_required: false,
    published: [
      {
        translation_value_id: "value-1",
        selector_version: 1,
        selector_digest: digest,
        revision_number: 1,
        revision_digest: revisionDigest,
        text: "Salva pubblicato",
        review_state: "approved",
      },
    ],
    pending: data.pending_change.values,
    updated_by: role,
    updated_at: "2026-09-10T10:00:00Z",
    activity: {
      id: `activity-${state}`,
      translation_group_id: data.id,
      language: data.language,
      kind: state === "draft" ? "proposal_saved" : "state_changed",
      proposal_version: state === "draft" ? 1 : 2,
      actor_id: role,
      created_at: "2026-09-10T10:00:00Z",
      from_state: state === "draft" ? null : "draft",
      to_state: state === "draft" ? null : state,
      before_values: null,
      after_values: null,
      reason: null,
      comment_id: null,
    },
  };
}

async function mockReviewApi(page: Page, role: string, conflict = false) {
  let pendingText: string | null = null;
  let comments: unknown[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/auth/refresh")
      return reply(route, {
        access_token: `token-${role}`,
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      });
    if (path === "/api/v1/users/me")
      return reply(route, {
        id: role,
        email: `${role}@example.com`,
        display_name: role,
        roles: [role],
        must_change_password: false,
      });
    if (path === "/api/v1/system/status")
      return reply(route, {
        api: "online",
        database: "online",
        redis: "online",
        worker: "online",
        checked_at: "2026-09-10T10:00:00Z",
      });
    if (path === "/api/v1/notifications/unread-count")
      return reply(route, { unread_count: 0 });
    if (path === "/api/v1/notifications/recent")
      return reply(route, { items: [], next_cursor: null });
    if (path === "/api/v1/notifications/stream")
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: "",
      });
    if (
      path === "/api/v1/translations/group-review" &&
      request.method() === "GET"
    )
      return reply(route, detail(role, pendingText));
    if (
      path === "/api/v1/translations/group-review/proposal" &&
      request.method() === "PUT"
    ) {
      const body = request.postDataJSON();
      if (role === "viewer") return reply(route, { detail: "Forbidden" }, 403);
      if (conflict)
        return reply(
          route,
          {
            detail: "Translation proposal conflict",
            latest: proposal(role, "Server winner"),
          },
          409,
        );
      pendingText = body.values[0].proposed_text;
      return reply(route, proposal(role, pendingText));
    }
    if (path === "/api/v1/translations/group-review/proposal/state") {
      if (role !== "admin" && role !== "product_manager_reviewer")
        return reply(route, { detail: "Forbidden" }, 403);
      return reply(
        route,
        proposal(role, pendingText ?? "", request.postDataJSON().target_state),
      );
    }
    if (
      path === "/api/v1/translations/group-review/comments" &&
      request.method() === "GET"
    )
      return reply(route, { items: comments, older_cursor: null });
    if (
      path === "/api/v1/translations/group-review/comments" &&
      request.method() === "POST"
    ) {
      if (role === "viewer") return reply(route, { detail: "Forbidden" }, 403);
      const body = request.postDataJSON();
      const created = {
        id: "comment-1",
        translation_group_id: "group-review",
        language: "it",
        author: { id: role, display_name: role },
        body: body.body,
        mentions: body.mentions,
        status: "available",
        current_version: 1,
        edited: false,
        created_at: "2026-09-10T10:01:00Z",
        updated_at: "2026-09-10T10:01:00Z",
        deleted_at: null,
        deleted_by: null,
      };
      comments = [created];
      return reply(route, created, 201);
    }
    if (path === "/api/v1/users/mentions")
      return reply(route, [
        {
          id: "reviewer",
          display_name: "Reviewer User",
          email: "reviewer@example.com",
        },
      ]);
    if (path === "/api/v1/translations/group-review/activity")
      return reply(route, { items: [], next_cursor: null });
    return reply(route, { detail: "Unexpected request" }, 501);
  });
}

test("translator saves empty and Unicode proposals while published authority remains visible", async ({
  page,
}) => {
  await mockReviewApi(page, "translator");
  await page.goto("/translations/group-review");
  await page.getByRole("button", { name: "Edit translation" }).click();
  const editor = page.getByRole("textbox", { name: "Proposed translation" });
  await editor.fill("");
  await page.getByRole("button", { name: "Save translation" }).click();
  await expect(
    page.getByRole("region", { name: "Pending proposal" }),
  ).toContainText("Empty pending translation");
  await page.getByRole("button", { name: "Edit translation" }).click();
  await page
    .getByRole("textbox", { name: "Proposed translation" })
    .fill("家族 👨‍👩‍👧‍👦 مرحبا");
  await page.getByRole("button", { name: "Save translation" }).click();
  await expect(
    page.getByRole("region", { name: "Pending proposal" }),
  ).toContainText("家族 👨‍👩‍👧‍👦 مرحبا");
  await expect(
    page.getByRole("region", { name: "Published translation" }),
  ).toContainText("Salva pubblicato");
});

test("first-save-wins conflict preserves the local Unicode draft and viewer stays read-only", async ({
  browser,
}) => {
  const translator = await browser.newPage();
  await mockReviewApi(translator, "translator", true);
  await translator.goto("/translations/group-review");
  await translator.getByRole("button", { name: "Edit translation" }).click();
  const draft = translator.getByRole("textbox", {
    name: "Proposed translation",
  });
  await draft.fill("私の未保存案");
  await translator.getByRole("button", { name: "Save translation" }).click();
  await expect(
    translator.getByRole("heading", {
      name: "Translation changed in another session",
    }),
  ).toBeVisible();
  await expect(translator.getByRole("dialog")).toContainText("私の未保存案");

  const viewer = await browser.newPage();
  await mockReviewApi(viewer, "viewer");
  await viewer.goto("/translations/group-review");
  await expect(
    viewer.getByRole("region", { name: "Published translation" }),
  ).toBeVisible();
  await expect(
    viewer.getByRole("button", { name: "Edit translation" }),
  ).toHaveCount(0);
  await expect(
    viewer.getByRole("textbox", { name: "Add a comment" }),
  ).toHaveCount(0);
});

test("reviewer approves a pending proposal and author posts a mention comment", async ({
  page,
}) => {
  await mockReviewApi(page, "product_manager_reviewer");
  await page.goto("/translations/group-review");
  await page.getByRole("button", { name: "Edit translation" }).click();
  await page
    .getByRole("textbox", { name: "Proposed translation" })
    .fill("Da revisionare");
  await page.getByRole("button", { name: "Save translation" }).click();
  await page.getByRole("button", { name: "Approve translation" }).click();
  await expect(
    page.getByRole("region", { name: "Pending proposal" }),
  ).toContainText("Approved");
  const composer = page.getByRole("textbox", { name: "Add a comment" });
  await composer.fill("Controlla @Re");
  await composer.pressSequentially("v");
  await expect(
    page.getByRole("listbox", { name: "Mention a person" }),
  ).toBeVisible();
  await page.getByRole("option", { name: "Reviewer User" }).click();
  await page.getByRole("button", { name: "Post comment" }).click();
  await expect(page.getByText("Controlla @Reviewer User")).toBeVisible();
});
