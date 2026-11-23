import { expect, test } from "@playwright/test";
import type { TranslationProposalResponse } from "../src/api/client";
import { editable, group, keyPage } from "./fixtures/translation-scroll";

for (const filtered of [false, true]) {
  test(`saving beyond the first page keeps the current row and scroll (filtered ${filtered})`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const saved = new Map<string, TranslationProposalResponse>();
    const cursors: string[] = [];
    let generation = 0;
    await page.route("**/api/v1/**", async (route) => {
      const req = route.request(),
        url = new URL(req.url()),
        path = url.pathname;
      const reply = (json: unknown) => route.fulfill({ json });
      if (path === "/api/v1/auth/refresh")
        return reply({
          access_token: "synthetic",
          token_type: "bearer",
          expires_in: 900,
          must_change_password: false,
        });
      if (path === "/api/v1/users/me")
        return reply({
          id: "editor",
          email: "editor@example.test",
          display_name: "Synthetic editor",
          roles: ["admin"],
          must_change_password: false,
        });
      if (path === "/api/v1/translations/options")
        return reply({
          products: [{ id: "alpha", name: "Alpha" }],
          languages: [
            { code: "en", label: "English" },
            { code: "it", label: "Italian" },
          ],
        });
      if (path === "/api/v1/notifications/unread-count")
        return reply({ unread_count: 0 });
      if (path === "/api/v1/notifications/stream")
        return route.fulfill({ contentType: "text/event-stream", body: "" });
      if (path === "/api/v1/system/status")
        return reply({
          api: "online",
          database: "online",
          redis: "online",
          worker: "online",
          checked_at: new Date().toISOString(),
        });
      if (path === "/api/v1/translations/keys") {
        const cursor = url.searchParams.get("cursor");
        if (cursor) {
          cursors.push(cursor);
          if (!cursor.startsWith(`g${generation}-`))
            return route.fulfill({
              status: 422,
              json: { detail: "Stale cursor" },
            });
        }
        const offset = cursor ? Number(cursor.split("-")[1]) : 0;
        const all = Array.from(
          { length: 150 },
          (_, i) => `group-${String(i).padStart(3, "0")}`,
        ).filter((id) => !filtered || !saved.has(id));
        const data = keyPage({
          items: all.slice(offset, offset + 50).map((id) =>
            group(id, {
              translated_text: saved.get(id)?.pending[0].text ?? "Old",
            }),
          ),
          next_cursor:
            offset + 50 < all.length ? `g${generation}-${offset + 50}` : null,
        });
        data.visible_languages = url.searchParams.getAll("visible_languages")
          .length
          ? url.searchParams.getAll("visible_languages")
          : ["it"];
        if (generation)
          await new Promise((resolve) => setTimeout(resolve, 200));
        return reply(data);
      }
      const match = path.match(
        /^\/api\/v1\/translations\/(group-\d+)(\/proposal)?$/,
      );
      if (match) {
        const id = match[1];
        if (match[2] && req.method() === "PUT") {
          const text = req.postDataJSON().values[0].proposed_text;
          const leaf = {
            translation_value_id: id,
            selector_version: 1,
            selector_digest: "a".repeat(64),
            basis_revision_number: 1,
            basis_digest: "b".repeat(64),
            text,
            grapheme_count: text.length,
            maximum: null,
            is_over_limit: false,
          };
          const result: TranslationProposalResponse = {
            translation_group_id: id,
            product_id: "alpha",
            language: "it",
            version: 1,
            state: "draft",
            reconciliation_required: false,
            target_branch: null,
            target_integrated: false,
            updated_at: new Date().toISOString(),
            updated_by: { id: "editor", display_name: "Synthetic editor" },
            pending: [leaf],
            published: [{ ...leaf, text: "Old" }],
          };
          saved.set(id, result);
          generation++;
          return reply(result);
        }
        const detail = editable(id),
          proposal = saved.get(id);
        if (proposal)
          detail.pending_change = { ...proposal, values: proposal.pending };
        return reply(detail);
      }
      return reply({ items: [], next_cursor: null });
    });
    await page.goto(
      `/translations?language=it${filtered ? "&work_status=needs_translation" : ""}`,
    );
    await expect(
      page.locator('[data-translation-editor-trigger="group-000"]'),
    ).toBeVisible();
    // Virtual rows can change height after measurement. Scroll until a row
    // from the second page is actually visible, then edit that same row.
    let id: string | null = null;
    await expect
      .poll(
        async () => {
          id = await page
            .locator("[data-translation-editor-trigger]")
            .evaluateAll((elements) => {
              for (const element of elements) {
                const key = (element as HTMLElement).dataset
                  .translationEditorTrigger!;
                const rect = element.getBoundingClientRect();
                if (
                  Number(key.slice(6)) >= 50 &&
                  rect.top > 200 &&
                  rect.bottom < 700
                )
                  return key;
              }
              return null;
            });
          if (!id)
            await page.evaluate(() => window.scrollBy(0, innerHeight / 2));
          return id;
        },
        { timeout: 15000, intervals: [60, 100, 200] },
      )
      .not.toBeNull();
    expect(cursors).toContain("g0-50");
    await page.locator(`[data-translation-editor-trigger="${id}"]`).click();
    await page
      .getByRole("textbox", { name: "Proposed translation", exact: true })
      .fill("Updated synthetic text");
    const before = await page.evaluate(() => window.scrollY);
    await page.screenshot({ path: testInfo.outputPath("before-save.png") });
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect.poll(() => saved.size).toBe(1);
    await expect.poll(() => cursors.includes("g1-50")).toBe(true);
    await expect(
      page.getByRole("textbox", { name: "Proposed translation", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.locator(`[data-translation-editor-trigger="${id}"]`),
    ).toBeInViewport();
    expect(
      Math.abs((await page.evaluate(() => window.scrollY)) - before),
    ).toBeLessThan(200);
    await page.screenshot({ path: testInfo.outputPath("after-save.png") });
    expect(await page.getByRole("alert").allTextContents()).toEqual([]);
  });
}
