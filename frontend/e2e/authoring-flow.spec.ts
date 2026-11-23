import { expect, test } from "@playwright/test";
import { group, keyPage } from "./fixtures/translation-scroll";

for (const width of [1440, 390]) {
  test(`two saved additions survive a blocked catalog and reopen independently (${width}px)`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let sourceBlocked = true;
    let imported = false;
    const writes: unknown[] = [];
    const entries: {
      key: string;
      text: string;
      version: number;
      state: "approved" | "draft";
    }[] = [
      { key: "welcome", text: "Benvenuto", version: 4, state: "approved" },
      { key: "duration", text: "Durata", version: 2, state: "approved" },
    ];
    const entry = ({
      key,
      text,
      version,
      state,
    }: (typeof entries)[number]) => ({
      id: `saved-${key}`,
      version,
      state,
      source_changed: false,
      path: "app/it/strings.xml",
      input: {
        scope_id: "scope",
        execution_id: "execution",
        file_position: 2,
        parent_key_id: key,
        key,
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
          items: entries.map(({ key, text }) =>
            group(key, { translated_text: text }),
          ),
        });
        const visible = new URL(req.url()).searchParams.getAll(
          "visible_languages",
        );
        if (visible.length) result.visible_languages = visible;
        for (const [index, row] of result.items.entries()) {
          const saved = entry(entries[index]);
          const slot = row.slots[0];
          slot.states = imported ? [saved.state] : [];
          if (!imported)
            Object.assign(slot, {
              group_id: null,
              kind: "absent",
              editable: false,
              authoring_request: {
                id: saved.id,
                version: saved.version,
                state: saved.state,
                source_changed: false,
                value_count: 1,
              },
            });
        }
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
      if (path.endsWith("/authoring/destinations") && sourceBlocked)
        return reply({
          items: [],
          truncated: false,
          blocked_scopes: [
            {
              scope_id: "scope",
              code: "source_refresh_required",
              message: "Source requires refresh",
            },
          ],
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
      const saved = entries.find(({ key }) =>
        path.endsWith(`/authoring/saved-${key}`),
      );
      if (saved) {
        if (req.method() === "PUT") {
          expect(sourceBlocked).toBe(false);
          const body = req.postDataJSON();
          writes.push({ id: saved.key, ...body });
          saved.text = body.forms[0].text;
          saved.version++;
          saved.state = "draft";
        }
        return reply(entry(saved));
      }
      if (path.endsWith("/authoring")) {
        expect(req.method()).toBe("GET");
        return reply({
          items: imported ? [] : entries.map(entry),
          next_after: null,
        });
      }
      return reply({ items: [], next_cursor: null });
    });
    await page.goto("/translations?product_id=alpha&language=it");
    const row = (key: string) =>
      page.locator(`[data-translation-group-id="${key}"]`);
    const dialog = page.getByRole("dialog");
    await expect(
      page.getByRole("button", { name: "Add translation", exact: true }),
    ).toHaveCount(0);
    for (const { key, text } of entries) {
      await expect(
        row(key).getByText("Approved · awaiting catalog update"),
      ).toBeVisible();
      await row(key).getByRole("button", { name: "Edit saved entry" }).click();
      await expect(
        dialog.getByLabel("Translation", { exact: true }),
      ).toHaveValue(text);
      await expect(
        dialog.getByRole("link", { name: "Update catalog" }),
      ).toHaveAttribute("href", "/products/alpha/source-updates");
      await expect(
        dialog.getByRole("button", { name: "Save", exact: true }),
      ).toBeDisabled();
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
    }
    expect(writes).toHaveLength(0);
    sourceBlocked = false;
    await page.reload();
    for (const { key, text, version } of entries) {
      const updated = text + " aggiornato";
      await row(key).getByRole("button", { name: "Edit saved entry" }).click();
      await expect(
        dialog.getByLabel("Translation", { exact: true }),
      ).toHaveValue(text);
      await dialog.getByLabel("Translation", { exact: true }).fill(updated);
      await dialog.getByRole("button", { name: "Save", exact: true }).click();
      await expect(dialog).toHaveCount(0);
      expect(writes.at(-1)).toMatchObject({
        id: key,
        expected_version: version,
        language: "it",
        forms: [{ form: "other", text: updated }],
      });
      await expect(
        row(key).getByText(updated, { exact: true }).first(),
      ).toBeVisible();
    }
    expect(writes).toHaveLength(2);
    await page.screenshot({
      path: testInfo.outputPath("saved-inline.png"),
      fullPage: true,
    });
    imported = true;
    await page.reload();
    await expect(
      page.getByRole("button", { name: "Edit saved entry" }),
    ).toHaveCount(0);
    for (const { key, text } of entries) {
      await expect(
        row(key).locator(`[data-translation-editor-trigger="${key}"]`),
      ).toBeVisible();
      await expect(
        row(key).getByText(text, { exact: true }).first(),
      ).toBeVisible();
    }
    await page.screenshot({
      path: testInfo.outputPath("imported.png"),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  });
}
