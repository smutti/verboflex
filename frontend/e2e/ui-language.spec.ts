import { expect, test, type Locator, type Page } from "@playwright/test";
import type { TranslationKeyPageResponse } from "../src/api/client";

test.use({ locale: "it-IT" });

const productName = "MUG Demo";
const translationText = "Enregistrer les modifications";
const languages = [{ code: "fr", label: "French" }];
const translations: TranslationKeyPageResponse = {
  available_languages: languages,
  available_languages_truncated: false,
  default_selection_capped: false,
  visible_languages: ["fr"],
  next_cursor: null,
  items: [
    {
      translation_key_id: "synthetic-key",
      scope_id: "synthetic-scope",
      product_id: "synthetic-product",
      product_name: productName,
      raw_key: "settings.save",
      base_language: "en",
      rank: 0,
      key_truncated: false,
      source_text: "Save changes",
      source_truncated: false,
      slots: [
        {
          language: "fr",
          language_label: "French",
          group_id: "synthetic-group",
          kind: "imported",
          editable: false,
          edit_field: null,
          effective_text: translationText,
          is_deleted: false,
          matches_filters: true,
          no_max_count: 1,
          over_limit_count: 0,
          within_limit_count: 0,
          pending_change: {
            state: "approved",
            version: 1,
            value_count: 1,
            reconciliation_required: false,
            target_branch: "master",
            target_integrated: false,
          },
          preview_kind: "scalar",
          provenance: null,
          read_only_reason: "unavailable_provenance",
          selector_kinds: ["scalar"],
          source_changed: false,
          states: ["approved"],
          text_truncated: false,
          value_count: 1,
          comment_count: 0,
        },
      ],
    },
  ],
};

test.beforeEach(async ({ context }) => {
  await context.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const responses: Record<string, unknown> = {
      "/api/v1/auth/refresh": {
        access_token: "synthetic-language-test-token",
        token_type: "bearer",
        expires_in: 900,
        must_change_password: false,
      },
      "/api/v1/users/me": {
        id: "synthetic-viewer",
        email: "viewer@example.test",
        display_name: "Language Test",
        roles: ["viewer"],
        must_change_password: false,
      },
      "/api/v1/translations/options": {
        products: [{ id: "synthetic-product", name: productName }],
        languages,
      },
      "/api/v1/translations/keys": translations,
    };
    if (path in responses) {
      await route.fulfill({ json: responses[path] });
    } else {
      await route.fulfill({
        status: 503,
        json: { detail: "Unrelated service unavailable in synthetic fixture" },
      });
    }
  });
});

// Assert the browser's effective, inherited translation mode, including portals
// outside #root. Headless Chromium does not run a vendor translation service.
async function expectOriginalContent(locator: Locator) {
  await expect(locator).toBeVisible();
  await expect(locator).toHaveJSProperty("translate", false);
}

const locales = [
  {
    code: "it",
    name: "Italiano",
    profile: "Profilo",
    strings: "Stringhe",
    current: "Password attuale",
  },
  {
    code: "en",
    name: "English",
    profile: "Profile",
    strings: "Strings",
    current: "Current password",
  },
  {
    code: "de",
    name: "Deutsch",
    profile: "Profil",
    strings: "Zeichenfolgen",
    current: "Aktuelles Passwort",
  },
  {
    code: "es",
    name: "Español",
    profile: "Perfil",
    strings: "Cadenas",
    current: "Contraseña actual",
  },
  {
    code: "fr",
    name: "Français",
    profile: "Profil",
    strings: "Chaînes",
    current: "Mot de passe actuel",
  },
  {
    code: "nl",
    name: "Nederlands",
    profile: "Profiel",
    strings: "Tekenreeksen",
    current: "Huidig wachtwoord",
  },
];

async function chooseLanguage(page: Page, name: string) {
  await page
    .getByRole("button", {
      name: /^(Lingua dell|Interface language:|Oberflächensprache:|Idioma de la interfaz:|Langue de l|Interfacetaal:)/,
    })
    .first()
    .click();
  await page.getByRole("menuitemradio", { name, exact: true }).click();
}

for (const locale of locales) {
  test.describe(`browser locale ${locale.code}`, () => {
    test.use({
      locale: `${locale.code}-${{ it: "IT", en: "GB", de: "DE", es: "ES", fr: "FR", nl: "NL" }[locale.code]}`,
    });
    test("uses the browser language on the first visit", async ({ page }) => {
      await page.goto("/profile");
      await expect(page.locator("html")).toHaveAttribute("lang", locale.code);
      await expect(
        page.getByRole("heading", { name: locale.profile, exact: true }),
      ).toBeVisible();
      expect(
        await page.evaluate(() =>
          localStorage.getItem("verboflex.ui-language"),
        ),
      ).toBeNull();
    });
  });
}

test.describe("unsupported browser language", () => {
  test.use({ locale: "ja-JP" });
  test("falls back to English and honors a saved choice", async ({ page }) => {
    await page.goto("/profile");
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await chooseLanguage(page, "Français");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "fr");
    await expect(
      page.getByRole("heading", { name: "Profil", exact: true }),
    ).toBeVisible();
  });
});

test("switches all six languages, retains unsaved password fields and exposes issue reporting", async ({
  page,
}) => {
  await page.goto("/profile");
  const input = page.locator('input[autocomplete="current-password"]');
  await input.fill("synthetic-unsaved-password");
  await input.evaluate((element) =>
    element.setAttribute("data-retained", "true"),
  );
  for (const locale of locales) {
    await chooseLanguage(page, locale.name);
    await expect(page.locator("html")).toHaveAttribute("lang", locale.code);
    await expect(
      page.getByRole("heading", { name: locale.profile, exact: true }),
    ).toBeVisible();
    await expect(page.getByLabel(locale.current, { exact: true })).toHaveValue(
      "synthetic-unsaved-password",
    );
    await expect(input).toHaveAttribute("data-retained", "true");
  }
  await chooseLanguage(page, "English");
  await page
    .getByRole("button", { name: "Open user menu for Language Test" })
    .click();
  const report = page.getByRole("menuitem", {
    name: "Report a problem on GitHub",
  });
  await expectOriginalContent(report);
  await expect(report).toHaveAttribute(
    "href",
    "https://github.com/smutti/verboflex/issues/new/choose",
  );
  await expect(report).toHaveAttribute("rel", "noopener noreferrer");
  await page.keyboard.press("Escape");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});

test("updates open filter portals across tabs without changing drafts, API values or repository content", async ({
  page,
  context,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/translations");
  await expect(page.locator('meta[name="google"]')).toHaveAttribute(
    "content",
    "notranslate",
  );
  const results = page.getByRole("list", {
    name: "Risultati delle traduzioni",
  });
  await expectOriginalContent(
    results.getByText(`Prodotto: ${productName}`, { exact: true }),
  );
  await expectOriginalContent(
    results.getByText(translationText, { exact: true }),
  );
  await expectOriginalContent(
    results.getByText("In attesa di master", { exact: true }),
  );
  await page.getByRole("button", { name: /^Filtra/ }).click();
  let dialog = page.getByRole("dialog", {
    name: "Filtra traduzioni",
    exact: true,
  });
  await expectOriginalContent(dialog);
  expect(
    await dialog.evaluate((element) =>
      document.getElementById("root")!.contains(element),
    ),
  ).toBe(false);
  await dialog.getByRole("combobox", { name: "Coda di lavoro" }).click();
  await page.getByRole("option", { name: "Da tradurre", exact: true }).click();
  const other = await context.newPage();
  await other.goto("/profile");
  await chooseLanguage(other, "Deutsch");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  dialog = page.getByRole("dialog", {
    name: "Übersetzungen filtern",
    exact: true,
  });
  await expectOriginalContent(dialog);
  await expect(
    dialog.getByRole("combobox", { name: "Arbeitsliste" }),
  ).toHaveValue("Übersetzung erforderlich");
  const filtered = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return (
      url.pathname === "/api/v1/translations/keys" &&
      url.searchParams.get("work_status") === "needs_translation"
    );
  });
  await dialog.getByRole("button", { name: "Filter anwenden" }).click();
  await filtered;
  await expect(
    page.getByText("Warten auf master", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(translationText, { exact: true })).toBeVisible();
  const cleared = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return (
      url.pathname === "/api/v1/translations/keys" &&
      !url.searchParams.has("work_status")
    );
  });
  await page
    .getByRole("button", { name: "Filter zurücksetzen", exact: true })
    .click();
  await cleared;
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(page.getByText(translationText, { exact: true })).toBeVisible();
  await other.close();
  expect(errors).toEqual([]);
});

test("offers the same choices from the sign-in page with keyboard access on a narrow screen", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({
      status: 401,
      json: { detail: "synthetic signed-out session" },
    }),
  );
  await page.setViewportSize({ width: 320, height: 760 });
  await page.goto("/login");
  await expect(
    page.getByRole("button", { name: "Accedi a VerboFlex" }),
  ).toBeVisible();
  const picker = page.getByRole("button", {
    name: "Lingua dell’interfaccia: Italiano",
  });
  await picker.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menuitemradio")).toHaveCount(6);
  await expect(
    page.getByRole("menuitemradio", { name: "Italiano", exact: true }),
  ).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("Home");
  await expect(
    page.getByRole("menuitemradio", { name: "Italiano", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(
    page.getByRole("menuitemradio", { name: "English", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(
    page.getByRole("button", { name: "Interface language: English" }),
  ).toBeFocused();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("keeps the header flag and profile controls reachable at 320 pixels", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 760 });
  await page.goto("/profile");
  for (const locale of locales) {
    await chooseLanguage(page, locale.name);
    await expect(
      page.getByRole("heading", { name: locale.profile, exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
  await page.screenshot({
    path: "/tmp/verboflex-ui-language-mobile.png",
    fullPage: true,
  });
});
