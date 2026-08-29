import { expect, test, type Page, type Route } from "@playwright/test";

const temporaryPassword = "VF-once-only-secret-29";
const now = "2026-08-28T19:30:00Z";

type ConnectionStatus =
  "Connected" | "Disconnected" | "Reauthorization required" | "Unavailable";

interface ProductRevision {
  description: string | null;
  id: string;
  is_published: boolean;
  version: number;
}

interface Product {
  active_revision: ProductRevision | null;
  candidate_revision: ProductRevision | null;
  id: string;
  is_active: boolean;
  name: string;
}

interface AdminMockState {
  connectionDelayMs: number;
  connectionFailures: number;
  connectionMutations: string[];
  connectionStatus: ConnectionStatus;
  deactivateFailures: number;
  mappings: Array<Record<string, unknown>>;
  paginateProducts: boolean;
  previewAttempts: number;
  previewMode: "success" | "timeout-then-success";
  product: Product;
  productFailures: number;
  products: Product[];
  productsDelayMs: number;
  publicationConflicts: number;
  reactivationConflicts: number;
  repositories: Array<Record<string, unknown>>;
  users: Array<Record<string, unknown>>;
}

const publishedRevision: ProductRevision = {
  description: "Published localization configuration",
  id: "revision-published",
  is_published: true,
  version: 4,
};

const candidateRevision: ProductRevision = {
  description: "Candidate localization configuration",
  id: "revision-candidate",
  is_published: false,
  version: 5,
};

function product(overrides: Partial<Product> = {}): Product {
  return {
    active_revision: publishedRevision,
    candidate_revision: candidateRevision,
    id: "product-1",
    is_active: true,
    name: "Zulu Mobile",
    ...overrides,
  };
}

const directMapping = {
  allowed_target_branches: ["main", "release/very-long-supported-target-name"],
  candidate_version: 5,
  default_target_branch: "main",
  id: "mapping-direct",
  primary_repository_id: "repository-app",
  primary_source_branch: "main",
  selected_layout_candidate_id: null,
  selected_layout_version: null,
  topology: "direct",
  translations_repository_id: null,
  translations_source_branch: null,
};

const separateMapping = {
  allowed_target_branches: ["main"],
  candidate_version: 5,
  default_target_branch: "main",
  id: "mapping-separate",
  primary_repository_id: "repository-app",
  primary_source_branch: "keys/main",
  selected_layout_candidate_id: null,
  selected_layout_version: null,
  topology: "separate",
  translations_repository_id: "repository-translations",
  translations_source_branch: "translations/main",
};

function defaultState(): AdminMockState {
  const current = product();
  return {
    connectionDelayMs: 0,
    connectionFailures: 0,
    connectionMutations: [],
    connectionStatus: "Connected",
    deactivateFailures: 0,
    mappings: [directMapping, separateMapping],
    paginateProducts: false,
    previewAttempts: 0,
    previewMode: "success",
    product: current,
    productFailures: 0,
    products: [
      current,
      product({
        active_revision: null,
        candidate_revision: {
          ...candidateRevision,
          id: "candidate-alpha",
          version: 1,
        },
        id: "product-2",
        is_active: false,
        name: "Alpha Embedded",
      }),
      product({
        active_revision: {
          ...publishedRevision,
          id: "published-web",
          version: 2,
        },
        candidate_revision: null,
        id: "product-3",
        name: "Browser Portal With An Intentionally Long Product Name For Local Overflow",
      }),
    ],
    productsDelayMs: 0,
    publicationConflicts: 0,
    reactivationConflicts: 0,
    repositories: [
      {
        descriptive_name: "Application repository",
        id: "repository-app",
        repository_slug:
          "application-with-an-intentionally-long-repository-slug",
        workspace: "verboflex-workspace",
      },
      {
        descriptive_name: "Translations repository",
        id: "repository-translations",
        repository_slug: "translations",
        workspace: "verboflex-workspace",
      },
    ],
    users: [
      {
        display_name: "Admin User",
        email: "admin@verboflex.test",
        id: "admin-user",
        is_active: true,
        must_change_password: false,
        roles: ["admin"],
      },
      {
        display_name: "Inactive Translator",
        email: "inactive@verboflex.test",
        id: "inactive-user",
        is_active: false,
        must_change_password: true,
        roles: ["translator"],
      },
    ],
  };
}

function connection(state: AdminMockState) {
  return {
    connected_at: state.connectionStatus === "Disconnected" ? null : now,
    expires_at:
      state.connectionStatus === "Connected" ? "2026-09-28T19:30:00Z" : null,
    revoked_at: state.connectionStatus === "Disconnected" ? now : null,
    scope_label: "Read-only repository access",
    scope_profile: "repository",
    status: state.connectionStatus,
  };
}

function layoutCandidates() {
  return [
    ["android_xml", "Android XML", "res/values/strings.xml"],
    ["qt_ts", "Qt TS", "translations/application_it.ts"],
    ["json", "JSON", "locales/en.json"],
    ["ios_strings", "iOS strings", "Resources/en.lproj/Localizable.strings"],
  ].map(([format, identity, file], index) => ({
    confidence: 1,
    files: [file],
    format,
    id: `layout-${index + 1}`,
    keys: ["screen.title"],
    languages: ["en", "it"],
    layout_identity: identity,
    repository_side: "direct",
    samples: [
      {
        key: "screen.title",
        language: "en",
        translation: "A bounded preview sample",
      },
    ],
    samples_are_partial: true,
    version: 1,
  }));
}

function previewJob(
  state: "queued" | "succeeded" | "timed_out",
  attempt: number,
) {
  return {
    attempt,
    candidate_revision_id: "revision-candidate",
    candidate_revision_version: 5,
    connection_generation: 3,
    created_at: new Date().toISOString(),
    detector_version: "detector-v1",
    error_code: state === "timed_out" ? "time_limit_exceeded" : null,
    finished_at: state === "queued" ? null : new Date().toISOString(),
    id: `preview-job-${attempt}`,
    input_digest: `preview-input-${attempt}`,
    is_current: true,
    mapping_id: "mapping-direct",
    product_id: "product-1",
    repository_sides: [
      {
        commit_hash: "abcdef0123456789",
        repository_id: "repository-app",
        role: "direct",
        source_branch: "main",
      },
    ],
    result:
      state === "succeeded"
        ? {
            detector_version: "detector-v1",
            digest: `preview-digest-${attempt}`,
            layout_candidates: layoutCandidates(),
          }
        : null,
    started_at: state === "queued" ? null : new Date().toISOString(),
    state,
  };
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    body: JSON.stringify(body),
    contentType: "application/json",
    status,
  });
}

function requestBody(route: Route): Record<string, unknown> {
  return route.request().postDataJSON() as Record<string, unknown>;
}

async function installAdminApi(page: Page, state: AdminMockState) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname, searchParams } = url;
    const method = request.method();

    if (pathname === "/api/v1/auth/refresh" && method === "POST") {
      return json(route, {
        access_token: "memory-only-e2e-access-token",
        expires_in: 900,
        must_change_password: false,
        token_type: "bearer",
      });
    }
    if (pathname === "/api/v1/users/me" && method === "GET") {
      return json(route, state.users[0]);
    }
    if (pathname === "/api/v1/system/status" && method === "GET") {
      return json(route, {
        api: "online",
        checked_at: now,
        database: "online",
        redis: "online",
        worker: "online",
      });
    }
    if (pathname === "/api/v1/admin/products" && method === "GET") {
      if (state.productsDelayMs > 0) {
        await new Promise((resolve) =>
          setTimeout(resolve, state.productsDelayMs),
        );
      }
      if (state.productFailures > 0) {
        state.productFailures -= 1;
        return json(route, { detail: "bounded product list failure" }, 503);
      }
      const status = searchParams.get("status");
      const filtered = state.products.filter((item) =>
        status === "active"
          ? item.is_active
          : status === "inactive"
            ? !item.is_active
            : true,
      );
      const cursor = searchParams.get("cursor");
      if (state.paginateProducts && cursor === null) {
        return json(route, {
          items: filtered.slice(0, 2),
          next_cursor: "page-2",
        });
      }
      return json(route, {
        items:
          state.paginateProducts && cursor === "page-2"
            ? filtered.slice(2)
            : filtered,
        next_cursor: null,
      });
    }
    if (pathname === "/api/v1/admin/products" && method === "POST") {
      const body = requestBody(route);
      const created = product({
        active_revision: null,
        candidate_revision: {
          description:
            typeof body.description === "string" ? body.description : null,
          id: "new-candidate",
          is_published: false,
          version: 1,
        },
        id: "product-new",
        is_active: false,
        name: String(body.name),
      });
      state.product = created;
      state.products.push(created);
      return json(route, created, 201);
    }
    if (
      /^\/api\/v1\/admin\/products\/[^/]+$/.test(pathname) &&
      method === "GET"
    ) {
      return json(route, state.product);
    }
    if (
      /^\/api\/v1\/admin\/products\/[^/]+$/.test(pathname) &&
      method === "PUT"
    ) {
      const body = requestBody(route);
      state.product = {
        ...state.product,
        candidate_revision:
          state.product.candidate_revision === null
            ? null
            : {
                ...state.product.candidate_revision,
                description:
                  typeof body.description === "string"
                    ? body.description
                    : null,
                version: state.product.candidate_revision.version + 1,
              },
        name: String(body.name),
      };
      return json(route, state.product);
    }
    if (pathname.endsWith("/deactivate") && method === "POST") {
      if (state.deactivateFailures > 0) {
        state.deactivateFailures -= 1;
        return json(route, { detail: "bounded lifecycle failure" }, 503);
      }
      state.product = { ...state.product, is_active: false };
      return json(route, state.product);
    }
    if (pathname.endsWith("/publish") && method === "POST") {
      if (state.publicationConflicts > 0) {
        state.publicationConflicts -= 1;
        return json(
          route,
          {
            blockers: [
              "mapping_configuration_invalid",
              "preview_confirmation_required",
            ],
            detail: "Product publication blocked",
          },
          409,
        );
      }
      state.product = {
        ...state.product,
        active_revision:
          state.product.candidate_revision === null
            ? state.product.active_revision
            : { ...state.product.candidate_revision, is_published: true },
        candidate_revision: null,
        is_active: true,
      };
      return json(route, state.product);
    }
    if (pathname.endsWith("/reactivate") && method === "POST") {
      if (state.reactivationConflicts > 0) {
        state.reactivationConflicts -= 1;
        return json(
          route,
          {
            blockers: ["layout_required", "target_configuration_invalid"],
            detail: "Product lifecycle conflict",
          },
          409,
        );
      }
      state.product = { ...state.product, is_active: true };
      return json(route, state.product);
    }
    if (/\/candidate\/mappings$/.test(pathname) && method === "GET") {
      return json(route, { items: state.mappings, next_cursor: null });
    }
    if (/\/candidate\/mappings$/.test(pathname) && method === "POST") {
      const body = requestBody(route);
      const created = {
        ...directMapping,
        ...body,
        candidate_version: Number(body.expected_candidate_version) + 1,
        id: `mapping-${state.mappings.length + 1}`,
        primary_repository_id:
          typeof body.repository_id === "string"
            ? body.repository_id
            : "repository-app",
        primary_source_branch:
          typeof body.source_branch === "string" ? body.source_branch : "main",
        selected_layout_candidate_id: null,
        selected_layout_version: null,
        translations_repository_id: null,
        translations_source_branch: null,
      };
      state.mappings.push(created);
      return json(route, created, 201);
    }
    if (
      /\/candidate\/mappings\/[^/]+\/preview-jobs$/.test(pathname) &&
      method === "POST"
    ) {
      state.previewAttempts += 1;
      const firstAttemptTimesOut =
        state.previewMode === "timeout-then-success" &&
        state.previewAttempts === 1;
      return json(
        route,
        previewJob(
          firstAttemptTimesOut ? "queued" : "succeeded",
          state.previewAttempts,
        ),
        201,
      );
    }
    if (
      /^\/api\/v1\/admin\/preview-jobs\/[^/]+$/.test(pathname) &&
      method === "GET"
    ) {
      const attempt = pathname.endsWith("-1") ? 1 : state.previewAttempts;
      return json(
        route,
        previewJob(attempt === 1 ? "timed_out" : "succeeded", attempt),
      );
    }
    if (pathname.endsWith("/confirmation") && method === "POST") {
      const body = requestBody(route);
      return json(route, {
        confirmed_at: now,
        confirmed_by: "admin-user",
        job_id: `preview-job-${state.previewAttempts}`,
        layout_candidate_id: body.layout_candidate_id,
        layout_candidate_version: 1,
        mapping_id: "mapping-direct",
        preview_digest: body.preview_digest,
      });
    }
    if (pathname === "/api/v1/admin/repositories" && method === "GET") {
      return json(route, { items: state.repositories, next_cursor: null });
    }
    if (pathname === "/api/v1/admin/repositories" && method === "POST") {
      const body = requestBody(route);
      const created = {
        descriptive_name:
          typeof body.descriptive_name === "string"
            ? body.descriptive_name
            : null,
        id: `repository-${state.repositories.length + 1}`,
        repository_slug: String(body.repository_slug),
        workspace: String(body.workspace),
      };
      state.repositories.push(created);
      return json(route, created, 201);
    }
    if (/\/repositories\/[^/]+\/branches$/.test(pathname) && method === "GET") {
      return json(route, {
        items: [
          { commit_hash: "abcdef0123456789", name: "main" },
          {
            commit_hash: "fedcba9876543210",
            name: "release/very-long-supported-target-name",
          },
          { commit_hash: "1234567890abcdef", name: "keys/main" },
          { commit_hash: "7890abcdef123456", name: "translations/main" },
        ],
        next_cursor: null,
      });
    }
    if (pathname === "/api/v1/admin/users" && method === "GET") {
      return json(route, { items: state.users, next_cursor: null });
    }
    if (pathname === "/api/v1/admin/users" && method === "POST") {
      const body = requestBody(route);
      const created = {
        display_name: String(body.display_name),
        email: String(body.email),
        id: "created-user",
        is_active: true,
        must_change_password: true,
        roles: body.roles,
      };
      state.users.push(created);
      return json(
        route,
        { ...created, temporary_password: temporaryPassword },
        201,
      );
    }
    if (pathname === "/api/v1/admin/bitbucket" && method === "GET") {
      return json(route, connection(state));
    }
    if (pathname.endsWith("/bitbucket/revoke") && method === "POST") {
      state.connectionStatus = "Disconnected";
      return json(route, connection(state));
    }
    const connectionMutation = pathname.match(
      /^\/api\/v1\/admin\/bitbucket\/(connect|reconnect)$/,
    );
    if (connectionMutation !== null && method === "POST") {
      const action = connectionMutation[1];
      state.connectionMutations.push(action);
      if (state.connectionDelayMs > 0) {
        await new Promise((resolve) =>
          setTimeout(resolve, state.connectionDelayMs),
        );
      }
      if (state.connectionFailures > 0) {
        state.connectionFailures -= 1;
        return json(route, { detail: "Bitbucket connection unavailable" }, 503);
      }
      state.connectionStatus = "Connected";
      return json(route, connection(state));
    }

    return json(
      route,
      { detail: `Unhandled mock route: ${method} ${pathname}` },
      501,
    );
  });
}

async function expectNoPageOverflow(page: Page) {
  const widths = await page.evaluate(() => ({
    body: document.body.scrollWidth,
    document: document.documentElement.scrollWidth,
    viewport: innerWidth,
  }));
  expect(widths.body).toBeLessThanOrEqual(widths.viewport);
  expect(widths.document).toBeLessThanOrEqual(widths.viewport);
}

async function expectNoCredentialResidue(page: Page) {
  const residue = await page.evaluate(() => ({
    historyState: history.state,
    localStorage: Object.entries(localStorage),
    sessionStorage: Object.entries(sessionStorage),
    text: document.body.innerText,
    url: location.href,
  }));
  expect(residue.localStorage).toEqual([]);
  expect(residue.sessionStorage).toEqual([]);
  expect(residue.url).not.toContain(temporaryPassword);
  expect(residue.text).not.toContain(temporaryPassword);
  const serialized = JSON.stringify(residue).toLowerCase();
  for (const forbidden of [
    "authorization_url",
    "callback",
    "client_secret",
    "ciphertext",
    "refresh_token",
  ]) {
    expect(serialized).not.toContain(forbidden);
  }
}

async function chooseSelect(page: Page, label: string, option: string) {
  await page.getByLabel(label, { exact: true }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

test("product collection preserves API order across all states and responsive projections", async ({
  page,
}) => {
  const state = defaultState();
  state.productsDelayMs = 300;
  state.productFailures = 1;
  state.paginateProducts = true;
  await installAdminApi(page, state);
  await page.emulateMedia({ reducedMotion: "reduce" });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/admin/products");
  await expect(page.getByRole("status")).toContainText("Loading products");
  await expect(page.getByRole("heading", { name: "Products" })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("Products unavailable");
  await page.getByRole("button", { name: "Retry loading page" }).click();
  await expect(page.getByRole("table", { name: "Products" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Zulu Mobile" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Alpha Embedded" }),
  ).toBeVisible();

  const firstPageNames = await page
    .getByRole("table", { name: "Products" })
    .getByRole("link")
    .allTextContents();
  expect(firstPageNames).toEqual(["Zulu Mobile", "Alpha Embedded"]);
  await page.getByRole("button", { name: "Load more products" }).click();
  await expect(
    page.getByRole("table", { name: "Products" }).getByRole("link"),
  ).toHaveCount(3);

  await chooseSelect(page, "Product status", "Inactive");
  await expect(
    page.getByRole("link", { name: "Alpha Embedded" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Zulu Mobile" })).toHaveCount(0);
  await chooseSelect(page, "Products per page", "100");

  state.products = [];
  state.paginateProducts = false;
  state.productsDelayMs = 0;
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "No products configured" }),
  ).toBeVisible();

  state.products = defaultState().products;
  for (const width of [320, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.reload();
    await expect(page.getByRole("heading", { name: "Products" })).toBeVisible();
    const navigationTrigger = page.getByRole("button", {
      name: "Open navigation",
    });
    if (width < 1024) {
      await expect(navigationTrigger).toBeVisible();
      await navigationTrigger.click();
      const sheet = page.getByRole("dialog", { name: "Navigation" });
      await expect(sheet.getByRole("link", { name: "Products" })).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(navigationTrigger).toBeFocused();
    } else {
      await expect(navigationTrigger).toBeHidden();
      await expect(
        page
          .locator("aside")
          .getByRole("navigation", { name: "Primary navigation" }),
      ).toBeVisible();
    }
    if (width < 768) {
      await expect(page.getByLabel("Products mobile list")).toBeVisible();
      await expect(page.getByRole("table", { name: "Products" })).toBeHidden();
    } else {
      await expect(page.getByRole("table", { name: "Products" })).toBeVisible();
    }
    await expectNoPageOverflow(page);
    expect(
      await page.evaluate(
        () => matchMedia("(prefers-reduced-motion: reduce)").matches,
      ),
    ).toBe(true);
  }
});

test("five-step configuration reuses repositories, exposes both topologies, and clears one-time user secrets", async ({
  page,
}) => {
  const state = defaultState();
  state.mappings = [];
  await installAdminApi(page, state);
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.goto("/admin/products/new");

  await page
    .getByLabel("Name", { exact: true })
    .fill("New Localization Product");
  await page
    .getByLabel("Description")
    .fill("A candidate assembled through the real five-step wizard");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(
    page.getByRole("heading", { name: "Repositories" }),
  ).toBeVisible();
  await expect(page.getByRole("table", { name: "Repositories" })).toContainText(
    "Application repository",
  );
  await page
    .getByRole("button", { name: "Use Application repository" })
    .click();
  await expect(
    page.getByRole("button", { name: "Application repository selected" }),
  ).toBeDisabled();

  await page.getByRole("button", { name: "Mappings" }).click();
  await expect(
    page.getByRole("heading", { name: "Add mapping" }),
  ).toBeVisible();
  await expect(page.getByLabel("Direct")).toBeChecked();
  await page.getByLabel("Separate").click();
  await expect(
    page.getByRole("alertdialog", { name: "Change mapping topology?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Change topology" }).click();
  await expect(page.getByLabel("Separate")).toBeChecked();
  await page.getByLabel("Direct").click();
  await page.getByRole("button", { name: "Change topology" }).click();
  await chooseSelect(
    page,
    "Repository",
    "Application repository — verboflex-workspace/application-with-an-intentionally-long-repository-slug",
  );
  await expect(page.getByLabel("Source branch")).toBeEnabled();
  await chooseSelect(page, "Source branch", "main");
  await page.getByLabel("Allow target main").check();
  await chooseSelect(page, "Default target", "main");
  await page.getByRole("button", { name: "Save mapping" }).click();
  await expect(page.getByRole("table", { name: "Mappings" })).toContainText(
    "direct",
  );

  await page.getByRole("button", { name: "Preview" }).click();
  await expect(
    page.getByRole("heading", { name: "Validation has not run" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Review and publish" }).click();
  await expect(
    page.getByRole("heading", { name: "Review and publish" }),
  ).toBeVisible();

  state.mappings = [directMapping, separateMapping];
  await page.goto("/admin/products/product-1/mappings");
  const mappingsTable = page.getByRole("table", { name: "Mappings" });
  await expect(mappingsTable).toContainText("direct");
  await expect(mappingsTable).toContainText("separate");
  await expect(mappingsTable).toContainText(
    "release/very-long-supported-target-name",
  );
  await expectNoPageOverflow(page);

  await page.goto("/admin/users");
  await page.getByRole("button", { name: "Add user" }).click();
  await page.getByLabel("Corporate email").fill("translator@verboflex.test");
  await page.getByLabel("Display name").fill("New Translator");
  await page.getByRole("checkbox", { name: "Translator" }).check();
  await page.getByRole("button", { name: "Create user" }).click();
  const credentialDialog = page.getByRole("dialog", {
    name: "Temporary password created",
  });
  await expect(credentialDialog.getByLabel("Temporary password")).toHaveText(
    temporaryPassword,
  );
  await credentialDialog
    .getByRole("button", { name: "I saved the password" })
    .click();
  await expect(credentialDialog).toHaveCount(0);
  await expect(
    page
      .getByRole("table", { name: "Internal users" })
      .getByText("New Translator", {
        exact: true,
      }),
  ).toBeVisible();
  await expectNoCredentialResidue(page);
});

test("product lifecycle remains backend-authoritative for deactivate and reactivation blockers", async ({
  page,
}) => {
  const state = defaultState();
  state.deactivateFailures = 1;
  await installAdminApi(page, state);
  await page.goto("/admin/products/product-1/overview");

  await page.getByRole("button", { name: "Deactivate product" }).click();
  const dialog = page.getByRole("alertdialog", {
    name: "Deactivate Zulu Mobile?",
  });
  await dialog.getByRole("button", { name: "Deactivate product" }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "active state is unchanged",
  );
  await expect(page.getByText("Active", { exact: true })).toBeVisible();
  await dialog.getByRole("button", { name: "Deactivate product" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText("Inactive", { exact: true })).toBeVisible();

  state.product = product({ candidate_revision: null, is_active: false });
  state.mappings = [directMapping];
  state.previewMode = "success";
  state.reactivationConflicts = 1;
  await page.goto("/admin/products/product-1/preview");
  await page.getByRole("button", { name: "Run validation" }).click();
  await page.getByRole("radio", { name: "Android XML — Android XML" }).check();
  await page.getByRole("button", { name: "Confirm preview" }).click();
  await expect(page.getByText("Confirmed", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Reactivate product" }).click();
  const reactivateDialog = page.getByRole("alertdialog", {
    name: "Reactivate Zulu Mobile?",
  });
  await reactivateDialog
    .getByRole("button", { name: "Reactivate product" })
    .click();
  const blockers = page.getByRole("alert", { name: "Publication blocked" });
  await expect(blockers).toContainText("Layout selection required");
  await expect(blockers).toContainText("Target configuration invalid");
  await expect(
    blockers.getByRole("link", { name: "Review mapping 1" }),
  ).toHaveAttribute("href", "#preview-mapping-direct");

  await page.getByRole("button", { name: "Reactivate product" }).click();
  await page
    .getByRole("alertdialog", { name: "Reactivate Zulu Mobile?" })
    .getByRole("button", { name: "Reactivate product" })
    .click();
  await expect(page.getByText("Active", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Reactivate product" }),
  ).toHaveCount(0);
});

test("Bitbucket client credentials recover expiry without navigation or credential residue", async ({
  page,
}) => {
  const state = defaultState();
  state.connectionStatus = "Disconnected";
  state.connectionDelayMs = 150;
  const consoleMessages: string[] = [];
  page.on("console", (message) => consoleMessages.push(message.text()));
  await installAdminApi(page, state);
  await page.setViewportSize({ width: 320, height: 900 });
  await page.goto("/admin/bitbucket");
  const initialNavigation = await page.evaluate(() => ({
    href: location.href,
    length: history.length,
  }));

  const connect = page.getByRole("button", { name: "Connect Bitbucket" });
  await connect.click();
  await expect(connect).toBeDisabled();
  await expect(connect).toHaveAttribute("aria-busy", "true");
  await expect(
    page.getByRole("status", { name: "Bitbucket connection mutation" }),
  ).toContainText("Connecting Bitbucket");
  await expect(page.getByLabel("Bitbucket connection status")).toContainText(
    "Connected",
  );
  await expect(
    page.getByText("Read-only repository access", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("28 Sept 2026, 19:30 UTC")).toBeVisible();
  await expect(
    page.getByLabel("Bitbucket connection status"),
  ).not.toContainText("workspace");
  expect(state.connectionMutations).toEqual(["connect"]);
  expect(await page.evaluate(() => location.href)).toBe(initialNavigation.href);
  expect(await page.evaluate(() => history.length)).toBe(
    initialNavigation.length,
  );

  state.connectionStatus = "Reauthorization required";
  await page.reload();
  await expect(page.getByLabel("Bitbucket connection status")).toContainText(
    "Reauthorization required",
  );
  state.connectionFailures = 1;
  state.connectionDelayMs = 0;
  const reconnect = page.getByRole("button", {
    name: "Reconnect Bitbucket",
  });
  await reconnect.click();
  await expect(page.getByRole("alert")).toContainText(
    "Verify the server configuration, then try again. The current connection status is unchanged.",
  );
  await expect(page.getByLabel("Bitbucket connection status")).toContainText(
    "Reauthorization required",
  );
  await expect(reconnect).toBeEnabled();
  expect(state.connectionMutations).toEqual(["connect", "reconnect"]);

  await reconnect.click();
  await expect(page.getByLabel("Bitbucket connection status")).toContainText(
    "Connected",
  );
  await expect(
    page.getByRole("status", { name: "Bitbucket connection mutation" }),
  ).toContainText("Bitbucket reconnected");
  expect(state.connectionMutations).toEqual([
    "connect",
    "reconnect",
    "reconnect",
  ]);
  expect(await page.evaluate(() => location.href)).toBe(initialNavigation.href);
  expect(await page.evaluate(() => history.length)).toBe(
    initialNavigation.length,
  );
  await expectNoCredentialResidue(page);
  const serializedConsole = consoleMessages.join("\n").toLowerCase();
  for (const forbidden of [
    "authorization_url",
    "callback",
    "client_secret",
    "ciphertext",
    "refresh_token",
  ]) {
    expect(serializedConsole).not.toContain(forbidden);
  }
  await expectNoPageOverflow(page);

  state.product = product();
  state.mappings = [directMapping];
  state.previewMode = "timeout-then-success";
  state.previewAttempts = 0;
  state.publicationConflicts = 1;
  await page.goto("/admin/products/product-1/preview");
  await page.getByRole("button", { name: "Run validation" }).click();
  await expect(page.getByText("Queued", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("alert").filter({ hasText: "Validation timed out" }),
  ).toBeVisible({
    timeout: 5_000,
  });
  await page.getByRole("button", { name: "Retry validation" }).click();
  await expect(page.getByText("Succeeded", { exact: true })).toBeVisible();
  for (const label of [
    "Android XML — Android XML",
    "Qt TS — Qt TS",
    "JSON — JSON",
    "iOS strings — iOS strings",
  ]) {
    await expect(page.getByRole("radio", { name: label })).toBeVisible();
  }
  await page.getByRole("radio", { name: "JSON — JSON" }).check();
  await expect(
    page.getByText(
      "Preview samples are partial: up to 10 per language and 100 total.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Confirm preview" }).focus();
  await expect(
    page.getByRole("button", { name: "Confirm preview" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByText("Confirmed", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Publish changes" }).click();
  await page
    .getByRole("alertdialog", { name: "Publish Zulu Mobile?" })
    .getByRole("button", { name: "Publish changes" })
    .click();
  await expect(
    page.getByRole("alert", { name: "Publication blocked" }),
  ).toContainText("Preview confirmation required");
  await page.getByRole("button", { name: "Publish changes" }).click();
  await page
    .getByRole("alertdialog", { name: "Publish Zulu Mobile?" })
    .getByRole("button", { name: "Publish changes" })
    .click();
  await expect(
    page.getByRole("button", { name: "Publish changes" }),
  ).toHaveCount(0);
  await expect(page.getByText("Active", { exact: true })).toBeVisible();
  await expectNoCredentialResidue(page);
  await expectNoPageOverflow(page);
});
