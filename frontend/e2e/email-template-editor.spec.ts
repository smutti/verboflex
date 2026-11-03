import { expect, test, type Page } from "@playwright/test";
import {
  emailDetail,
  emailDocument,
  emailProjection,
  emailTemplates,
} from "../src/features/translations/emailEditorTestFixture";

// Synthetic records only; no provider credentials, repository or production writes.
const raster =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6R1sAAAAASUVORK5CYII=";

async function setup(page: Page, role = "translator") {
  const saved = new Map<string, ReturnType<typeof emailProjection>>();
  const requests = { saves: 0, external: 0 };
  page.on("request", (request) => {
    if (request.url().includes("external.example.test")) requests.external++;
  });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const id = path.split("/")[4];
    if (path.endsWith("/proposal") && route.request().method() === "PUT") {
      requests.saves++;
      const body = route.request().postDataJSON();
      const projection = emailProjection(
        id,
        body.values[0].proposed_text,
        (saved.get(id)?.version ?? 0) + 1,
      );
      saved.set(id, projection);
      await route.fulfill({ json: projection });
      return;
    }
    if (path.endsWith("/html-editor")) {
      const document = emailDocument(id.split("-")[0]);
      document.document = `<html><body style="margin:0;background:#f1f5f9;font-family:Arial,sans-serif"><table width="600" style="margin:auto;background:white"><tr><td style="padding:36px"><img alt="Repository logo" src="${raster}" width="120" height="32" style="background:#0f766e"><h1>WELCOME HOME</h1><p style="line-height:1.8"><!--BODY--></p><p style="color:#64748b">Your home, always close. Manage your account and discover the services available to you.</p><p style="padding:24px 0"><a style="background:#0f766e;color:white;padding:16px 24px"><!--CTA--></a></p></td></tr></table></body></html>`;
      document.fragments.forEach((fragment) => {
        fragment.text =
          saved.get(fragment.group_id)?.pending[0].text ?? fragment.text;
      });
      await route.fulfill({ json: document });
      return;
    }
    if (/\/translations\/(en|it|fr)-(body|cta)$/.test(path)) {
      const detail = emailDetail(id),
        projection = saved.get(id);
      if (projection)
        detail.pending_change = {
          version: projection.version,
          state: projection.state,
          reconciliation_required: false,
          updated_at: projection.updated_at,
          updated_by: projection.updated_by,
          values: projection.pending,
        };
      await route.fulfill({ json: detail });
      return;
    }
    const responses: Record<string, unknown> = {
      "/api/v1/auth/refresh": {
        access_token: "synthetic-review-token",
        token_type: "bearer",
        expires_in: 900,
        must_change_password: false,
      },
      "/api/v1/users/me": {
        id: "editor",
        email: "editor@example.test",
        display_name: "Demo Editor",
        roles: [role],
        must_change_password: false,
      },
      "/api/v1/products/workspace": {
        items: [
          {
            id: "product",
            name: "Synthetic emails",
            coverage: null,
            imported_scope_count: 1,
            unimported_scope_count: 0,
            last_imported_at: null,
          },
        ],
        total: 1,
        page: 1,
        has_more: false,
      },
      "/api/v1/products/product/html-templates": {
        items: emailTemplates,
        next_cursor: null,
      },
      "/api/v1/translations/options": {
        products: [{ id: "product", name: "Synthetic emails" }],
        languages: [
          { code: "en", label: "English" },
          { code: "it", label: "Italian" },
          { code: "fr", label: "French" },
        ],
      },
    };
    if (path in responses) await route.fulfill({ json: responses[path] });
    else
      await route.fulfill({
        status: 503,
        json: { detail: "Synthetic unrelated service" },
      });
  });
  await page.goto("/products/product/strings");
  return requests;
}

test("selects email text, previews safe edits and saves through the existing proposal API", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const requests = await setup(page);
  const field = page.getByRole("textbox", { name: "Translation · Italian" });
  await expect(field).toHaveValue("Ciao ");
  const iframe = page.locator('iframe[title="Interactive email preview"]');
  await expect(iframe).toHaveAttribute("sandbox", "allow-same-origin");
  const frame = page.frameLocator('iframe[title="Interactive email preview"]');
  await expect(frame.getByAltText("Repository logo")).toBeVisible();
  expect(
    await frame
      .getByAltText("Repository logo")
      .evaluate((img: HTMLImageElement) => img.naturalWidth),
  ).toBe(1);
  await frame
    .getByRole("button", { name: "Select email text: Apri account" })
    .click();
  await expect(field).toHaveValue("Apri account");
  await field.fill("Gestisci <account>");
  await expect(frame.locator('[data-vf-fragment="it-cta"]')).toHaveText(
    "Gestisci <account>",
  );
  await expect(frame.locator("account")).toHaveCount(0);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Translation saved as Draft" }),
  ).toBeVisible();
  await frame.locator('[data-vf-fragment="it-body"]').focus();
  await page.keyboard.press("Enter");
  await expect(field).toHaveValue("Ciao ");
  await expect(page.getByLabel("Protected variable")).toHaveText("{{name}}");
  await field.fill("Benvenuto ");
  await expect(frame.locator('[data-vf-fragment="it-body"]')).toHaveText(
    "Benvenuto {{name}}",
  );
  await expect(frame.locator('[data-vf-fragment="it-cta"]')).toHaveText(
    "Gestisci <account>",
  );
  await page.getByLabel("Translate into").selectOption("fr");
  await page.getByRole("button", { name: "Keep editing" }).click();
  await expect(field).toHaveValue("Benvenuto ");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Translation saved as Draft" }),
  ).toBeVisible();
  await page.reload();
  await expect(field).toHaveValue("Benvenuto ");
  await expect(frame.locator('[data-vf-fragment="it-cta"]')).toHaveText(
    "Gestisci <account>",
  );
  await page.getByLabel("Translate into").selectOption("en");
  await expect(
    page.getByRole("textbox", { name: "Translation · English" }),
  ).toHaveValue("Hello ");
  expect(requests.saves).toBe(2);
  expect(requests.external).toBe(0);
  await page.screenshot({
    path: "/tmp/verboflex-email-desktop.png",
    fullPage: true,
  });
});

for (const width of [320, 768]) {
  test(`fits the email and editor at ${width}px and preserves read-only access`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const requests = await setup(page, "viewer");
    await expect(page.getByText("Read-only translation")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save draft" })).toHaveCount(
      0,
    );
    const frame = page.frameLocator(
      'iframe[title="Interactive email preview"]',
    );
    await frame.locator('[data-vf-fragment="it-cta"]').click();
    await expect(
      page
        .getByRole("region", { name: "Selected text editor" })
        .getByText("Apri account"),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBe(true);
    const bounds = await page
      .locator('iframe[title="Interactive email preview"]')
      .boundingBox();
    expect(bounds!.width).toBeLessThanOrEqual(width);
    expect(bounds!.height).toBeLessThan(900);
    await page.screenshot({
      path: `/tmp/verboflex-email-${width}.png`,
      fullPage: true,
    });
    expect(requests.saves).toBe(0);
  });
}
