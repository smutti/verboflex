import { expect, test } from "@playwright/test";
import { keyPage } from "./fixtures/translation-scroll";

for (const width of [320, 1440]) {
  test(`all drafts confirmation and durable status at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.addInitScript(() =>
      localStorage.setItem("verboflex.ui-language", "it"),
    );
    let submitted = 0;
    let finished = false;
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
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
          id: "reviewer",
          email: "review@example.test",
          display_name: "Reviewer",
          roles: ["admin"],
          must_change_password: false,
        });
      if (path.endsWith("/translations/options"))
        return reply({
          products: [{ id: "alpha", name: "Synthetic project" }],
          languages: [
            { code: "en", label: "English" },
            { code: "fr", label: "French" },
            { code: "nl", label: "Dutch" },
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
      if (path.endsWith("/translations/keys"))
        return reply(keyPage({ items: [] }));
      const job = submitted
        ? {
            id: "job",
            state: finished ? "succeeded" : "queued",
            count: 506,
            error: null,
            branch_job_ids: finished ? ["commit-job"] : [],
            created_at: "2026-01-01T00:00:00Z",
          }
        : null;
      if (path.endsWith("/authoring/approval-preview"))
        return reply({
          count: finished ? 0 : 506,
          languages: finished ? {} : { fr: 251, nl: 255 },
          fingerprint: "a".repeat(64),
          source_changed: 0,
          over_limit: false,
          latest: job,
        });
      if (
        path.includes("/authoring/approvals/") &&
        request.method() === "PUT"
      ) {
        expect(request.postDataJSON()).toEqual({ fingerprint: "a".repeat(64) });
        submitted++;
        return route.fulfill({
          status: 202,
          json: {
            id: "job",
            state: "queued",
            count: 506,
            error: null,
            branch_job_ids: [],
            created_at: "2026-01-01T00:00:00Z",
          },
        });
      }
      return reply({ items: [], next_cursor: null, next_after: null });
    });
    await page.goto("/translations?product_id=alpha");
    await page
      .getByRole("button", { name: "Approva tutte le bozze", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("506 bozze selezionate");
    await expect(dialog).toContainText("fr: 251");
    await expect(dialog).toContainText("nl: 255");
    expect(submitted).toBe(0);
    await expect(dialog).toContainText("lingua base rimangono invariate");
    const bounds = await dialog.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    await page.screenshot({
      animations: "disabled",
      path: testInfo.outputPath("bulk-approval-confirmation.png"),
    });
    await page.getByRole("button", { name: "Conferma approvazione" }).click();
    await expect(
      page.getByText(
        "L’approvazione prosegue sul server. Puoi lasciare questa pagina.",
      ),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("button", { name: "Approvazione delle bozze…" }),
    ).toBeDisabled();
    expect(submitted).toBe(1);
    finished = true;
    await expect(page.getByText(/506 bozze approvate/)).toBeVisible({
      timeout: 10000,
    });
    await page.screenshot({
      animations: "disabled",
      path: testInfo.outputPath("bulk-approval-completed.png"),
    });
    expect(submitted).toBe(1);
  });
}
