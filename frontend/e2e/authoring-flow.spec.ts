import { expect, test } from "@playwright/test";
import { group, keyPage } from "./fixtures/translation-scroll";

for (const width of [1440, 390]) {
  test(`saved additions reopen their identity and become imported (${width}px)`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let text = "Testo italiano già salvato",
      version = 4,
      imported = false;
    let state = "approved";
    const writes: unknown[] = [];
    const entry = () => ({
      id: "saved-entry",
      version,
      state,
      source_changed: false,
      path: "app/it/strings.xml",
      input: {
        scope_id: "scope",
        execution_id: "execution",
        file_position: 2,
        parent_key_id: "welcome",
        key: "welcome",
        language: "it",
        kind: "text",
        forms: [{ form: "other", text }],
      },
    });
    await page.route("**/api/v1/**", async (route) => {
      const req = route.request(),
        path = new URL(req.url()).pathname;
      const reply = (json: unknown) => route.fulfill({ json });
      if (path.endsWith("/auth/refresh"))
        return reply({
          access_token: "synthetic",
          token_type: "bearer",
          expires_in: 900,
          must_change_password: false,
        });
      if (path.endsWith("/users/me"))
        return reply({
          id: "editor",
          email: "editor@example.test",
          display_name: "Synthetic editor",
          roles: ["admin"],
          must_change_password: false,
        });
      if (path.endsWith("/translations/options"))
        return reply({
          products: [{ id: "alpha", name: "Alpha" }],
          languages: [
            { code: "en", label: "English" },
            { code: "it", label: "Italian" },
          ],
        });
      if (path.endsWith("/notifications/unread-count"))
        return reply({ unread_count: 0 });
      if (path.endsWith("/notifications/stream"))
        return route.fulfill({ contentType: "text/event-stream", body: "" });
      if (path.endsWith("/system/status"))
        return reply({
          api: "online",
          database: "online",
          redis: "online",
          worker: "online",
          checked_at: new Date().toISOString(),
        });
      if (path.endsWith("/translations/keys")) {
        const result = keyPage({
          items: [group("welcome", { translated_text: text })],
        });
        const visible = new URL(req.url()).searchParams.getAll(
          "visible_languages",
        );
        if (visible.length) result.visible_languages = visible;
        const slot = result.items[0].slots[0];
        slot.states = imported ? ["approved"] : [];
        if (!imported)
          Object.assign(slot, {
            group_id: null,
            kind: "absent",
            editable: false,
            authoring_request: {
              id: "saved-entry",
              version,
              state,
              source_changed: false,
              value_count: 1,
            },
          });
        return reply(result);
      }
      if (path.endsWith("/authoring/approval-preview"))
        return reply({
          count: 0,
          latest: null,
          languages: {},
          source_changed: 0,
          over_limit: false,
          fingerprint: "a".repeat(64),
        });
      if (path.endsWith("/authoring/destinations"))
        return reply({
          items: [
            {
              scope_id: "scope",
              execution_id: "execution",
              file_position: 2,
              path: "app/it/strings.xml",
              format: "android_xml",
              repository: "team/app",
              provider: "bitbucket",
              repository_side: "translations",
              base_language: "en",
              languages: ["it"],
              topology: "separate",
            },
          ],
          truncated: false,
          blocked_scopes: [],
        });
      if (path.endsWith("/authoring/saved-entry")) {
        if (req.method() === "PUT") {
          const body = req.postDataJSON();
          writes.push(body);
          text = body.forms[0].text;
          version++;
          state = "draft";
          return reply({ ...entry(), state: "draft" });
        }
        return reply(entry());
      }
      if (path.endsWith("/authoring"))
        return reply({ items: imported ? [] : [entry()], next_after: null });
      return reply({ items: [], next_cursor: null });
    });
    await page.goto("/translations?product_id=alpha&language=it");
    await expect(
      page.getByText("Approved · awaiting catalog update"),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Add translation", exact: true }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "Edit saved entry" }).click();
    await expect(page.getByLabel("Translation", { exact: true })).toHaveValue(
      text,
    );
    await page
      .getByLabel("Translation", { exact: true })
      .fill("Testo italiano aggiornato");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect.poll(() => writes.length).toBe(1);
    expect(writes[0]).toMatchObject({
      expected_version: 4,
      language: "it",
      forms: [{ form: "other", text: "Testo italiano aggiornato" }],
    });
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(
      page.getByText("Testo italiano aggiornato", { exact: true }).first(),
    ).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath("saved-inline.png"),
      fullPage: true,
    });
    imported = true;
    await page.reload();
    await expect(
      page.getByRole("button", { name: "Edit saved entry" }),
    ).toHaveCount(0);
    await expect(
      page.locator('[data-translation-editor-trigger="welcome"]'),
    ).toBeVisible();
    await expect(
      page.getByText("Testo italiano aggiornato", { exact: true }).first(),
    ).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath("imported.png"),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  });
}
