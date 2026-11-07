# Application checks

`Check application` runs on every pull request and push to `main`, and can be
started manually in GitHub Actions. Require **Application checks** in branch
protection: it fails if any component fails, is cancelled, or is skipped.
Also require **Website checks**, which runs on every pull request and main push.
The workflow does not deploy the application or contact real repositories.

The code-key and screenshot tests use synthetic Kotlin/Java, Angular and localization fixtures.
The backend job installs the bounded TypeScript/Angular parser and runs the real
[web capture smoke](angular-web-localization.md) through PostgreSQL, Redis, Celery,
an offline Angular build and Chromium for three scenarios, two languages and two
viewports. Web parser and renderer dependencies are locked in `tools/web-runtime`.
Synthetic discovery and isolated-parser regressions cover applications with up to
5,000 source files across modules, reject larger catalogs without partial results,
and retain the separate 500-file limit for localization catalogs.
The web import regression also exercises provider-owned credential transactions:
reading mapping settings must finish before the worker reads the scenario manifest
and application sources, so Bitbucket can acquire and recheck its credential lease.
Code traversal allows 20,000 total entries so package directories and unrelated
files do not consume the source-file allowance; localization traversal remains
limited to 5,000 entries.
The administrator's successful-import response accepts up to 5,500 source
references: 5,000 application files and 500 separate localization files.
Synthetic source-cache tests cover reuse across adapters, expiry, byte/entry
budgets, private filesystem access, credential changes and revoked provider access.
Initial-import PostgreSQL regressions verify that multi-row inserts batch the
database's read-projection triggers and reuse compiled SQL while preserving
language counts and provenance.
Unchanged refresh regressions also bound PostgreSQL read-projection updates while
advancing source provenance to the new execution and preserving value history.
The built smoke also configures a separate code/translation mapping through HTTP,
imports code-only keys, checks missing keys in the browser, saves a proposal and
requests its screenshot through the real Celery queue. PostgreSQL/API regressions
also cover dispatch after commit, rollback without dispatch, duplicate delivery and
durable scheduler recovery after a failed broker send. A synthetic renderer
replaces only the Android build boundary; it verifies the frozen commit IDs and
selected translation in its PNG. The browser checks editing base-language resources
in the translations repository, collapsible source context, visible waiting state, explicit
generation, dirty-edit blocking, authenticated image loading, retry after one failed
image request and reload.
The `code-capture-e2e.json` receipt and browser screenshots join the smoke artifacts.
The multilingual browser smoke also checks that **Needs translation** includes
absent target entries alongside empty imported values, with matching language
markers and an **Add translation** action. Run it with
`backend/.venv/bin/python tools/dashboard_smoke.py --multilingual`; it creates and
removes its own database and application containers with synthetic fixtures.
Actual Compose rendering is a separate Android check, described in
[the capture integration guide](code-keys-compose.md). It requires a reviewed,
prewarmed runner image; the ordinary application CI does not build private Android apps.

| Check | Coverage |
| --- | --- |
| Backend | Ruff, mypy, the complete pytest suite, migrations, disposable PostgreSQL 18, Redis 7 and a Celery worker; locked frontend tools and pinned fixtures for cross-language and historical regression checks |
| Frontend and API contracts | OpenAPI/client and MCP contract drift, ESLint, TypeScript, production build and the complete Vitest suite |
| MCP connector | Its own locked environment, Ruff, mypy and pytest |
| Built application smoke | Fresh Docker images, HTTP product setup, TLS provider fixture, imports, comments, review, change sets and pull requests, revoked-session saves, failure/recovery scenarios and browser checks at narrow widths and 200% zoom |

Actions and dependency locks are pinned. The workflow has read-only repository
permissions and needs no provider or production credentials. Test databases,
brokers, workers, images and Compose resources are isolated from the development
stack. Test reports and synthetic browser evidence are retained for seven days.

## Run locally

Use Docker, Node 24 and uv 0.11.12. The backend requires Python 3.14.7 or a later
3.14 patch. From the repository root:

```sh
uv sync --project backend --locked
npm ci --prefix frontend
npm ci --prefix tools/web-runtime --ignore-scripts
npm --prefix frontend run api:check
backend/.venv/bin/python mcp-server/generate_contract.py --check
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend test -- --run
backend/.venv/bin/python tools/ci_backend.py --artifacts /tmp/verboflex-backend-evidence
backend/.venv/bin/python tools/web_capture_smoke.py --artifacts /tmp/verboflex-web-evidence
(cd backend && uv run --locked mypy src && uv run --locked ruff check src tests)
uv sync --project mcp-server --locked
uv run --project mcp-server pytest mcp-server/tests
npx --prefix frontend playwright install chromium
PHASE8_HTTP_SETUP=1 PHASE7_EVIDENCE_DIR=/tmp/verboflex-smoke-evidence bash tools/phase7_smoke.sh
```

Finish client generation before running frontend tests: generation replaces the
client directory. Vitest uses two workers to avoid CPU contention in large DOM
and accessibility tests; assertions and timeouts remain unchanged.

The focused session-renewal browser regression uses synthetic HTTP responses and
requires no backend or account credentials. After building, serve the frontend
in one terminal with `cd frontend && npm exec vite -- preview --host 127.0.0.1
--port 4179 --strictPort`. From the repository root in another terminal, run
`PLAYWRIGHT_BASE_URL=http://127.0.0.1:4179 npm --prefix frontend run e2e --
session-renewal.spec.ts`. It checks renewal after inactivity, preservation of
unsaved form input, revoked-session redirects, retry after a temporary service
failure and serialized refresh requests from two browser tabs. This focused
browser check supplements the ordinary Vitest session regression tests.

The focused interface-language regression uses the same preview server and
synthetic HTTP fixtures: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:4179 npm --prefix
frontend run e2e -- ui-language.spec.ts`. It checks browser-language detection,
English fallback, all six supported interface languages, persisted manual choices,
cross-tab changes, open dialogs, unsaved input, keyboard access and a narrow screen.
It also checks the issue-reporting link, original product and branch names, French
translation content, and filter selection, clearing and reload. It verifies the
browser's inherited `translate` property
for content and dialogs rendered outside the React root. The initial HTML opts
out of automatic translation with `translate="no"`, `notranslate` and the Google
translation meta tag. Headless Chromium does not exercise an external translation
service; extensions that ignore these page directives require a manual check.

The focused account-removal browser check uses the same preview server:
`PLAYWRIGHT_BASE_URL=http://127.0.0.1:4179 npm --prefix frontend run e2e --
user-deletion.spec.ts`. Synthetic responses exercise deactivation, cancellation,
explicit deletion confirmation, the 204 response, focus restoration and reload on
desktop and 320-pixel screens. Real PostgreSQL API tests additionally verify
permissions, historical references, credential revocation, email reuse,
reactivation races and migration rollback protection.

The focused translation-detail browser check uses the same preview server:
`PLAYWRIGHT_BASE_URL=http://127.0.0.1:4179 npm --prefix frontend run e2e --
translation-detail-review.spec.ts`. Synthetic records and an authenticated image
fixture verify the review column, screenshots on the right, mobile stacking at 320
pixels, the empty/unconfigured states, collapsed technical metadata, on-demand
activity, viewer permissions, dirty-edit warnings and restoration without rendering.
HTML fixtures additionally verify the visible email preview, saved and live text,
fragment highlighting, embedded repository images, blocked external image requests,
sandbox restrictions and fit at desktop and mobile widths. Backend image tests
cover pinned commits, path normalization, budgets, access revocation and refresh
without changing translation revisions or saved proposals.
The Vitest suite also checks saved-proposal length and stale capture versions.
The focused `email-template-editor.spec.ts` uses the same preview server and
synthetic HTTP fixtures. It checks click/keyboard selection in the email canvas,
protected variables, escaped live text, embedded images, saved proposals across
fragments and reload, base-language editing, dirty-language guards, viewer access
and fit at 320, 768 and 1440 pixels. Vitest additionally covers per-user/project
view preferences, conflicts, failed saves and stale language responses. Real API
tests cover current-scope catalog pagination, pending text across a document,
permission revocation and inactive products without repository I/O.
It also verifies named screenshot scenarios, automatic selection for a key, and
text-position toggles without another render. Browser checks verify normalized
outline alignment at 320, 768 and 1440 pixels. Synthetic backend tests enforce
scenario selection at the API boundary and cover OCR ambiguity, multiline text,
timeouts, absent engines, access revocation and receipt expiration. Real OCR uses
the optional bundled Tesseract models; the Android renderer/cache contract is unchanged.

The frozen Phase 4 API-scope check uses a recorded GSD verdict bound to the exact
plan contents in `tools/phase4_api_scope_receipt.json`. Any changed or added plan
or coverage declaration requires rerunning and reviewing that workflow check.
Application tests do not depend on a developer's private GSD installation path.
The performance baseline is a SHA-256-checked source fixture, so a fresh public
Git history does not need the original development commits.

The smoke also verifies [approval commits](approval-branches.md): consecutive
approvals become separate commits on one working branch, and a PR is created only
after the explicit browser action. The scenario also configures approval branches
through the admin interface and rejects a repeated approval without another commit.
Its import source is the working branch: after reimporting an approval, the next
approval creates a new commit and the earlier approval remains awaiting the PR
destination. Reimporting alone must not report target integration.
It checks 320-pixel and 200% zoom layouts and uses a synthetic Bitbucket provider.
It also verifies the translation badges through pending, approved/awaiting-target
and integrated states, using a real Celery check against synthetic target contents.
Target verification must not create another commit or pull request.
It also imports a shared MOKO catalog with unrelated duplicate keys, saves two
approved edits as sequential commits, preserves every unrelated byte and verifies
that no PR is opened for that product.

## Release boundary

A green check verifies the current automated baseline. It does not certify a
production host, off-site backups, alert delivery, native assistive technology,
separate-organization isolation, or performance with tens of millions of strings. The
historical phase-specific Playwright suites are not all included here; their
remaining release-level reconciliation is separate work. See the
[authorization and audit model](authorization-and-audit.md) for the Phase 8 scope.

For a smoke-harness change, manually dispatch **Check application** with `scope: smoke`
to rerun only the disposable browser/container workflow. This deliberately skips
the aggregate **Application checks** gate; a successful smoke-only run is not a
complete verification. Skipped jobs use distinct names so they cannot satisfy the
required full-gate checks. Pushes and pull requests always run all jobs.

## Product website and public repository

**Website checks** builds the allowlisted static artifact, validates local links,
metadata and screenshot budgets, then runs the interactive demo and responsive
Chromium checks. The same workflow is reused as a prerequisite for Pages deployment.
It needs no secrets and publishes no application data.

**Publish product website** runs for site/workflow changes pushed to `main`, or by
manual dispatch. It validates first, then uploads only `site/dist/` and deploys with
GitHub Pages OIDC. It never deploys the backend, database or workers. The Pages
environment accepts only `main`. See [site maintenance](../site/README.md).

Protect `main` with the **Application checks** and **Website checks** status checks,
require an up-to-date branch and resolved conversations, and disable force pushes
and branch deletion. Keep the standard administrator recovery bypass. No independent
reviewer is mandated for the single-maintainer repository. Workflows have read-only
permissions by default; only the Pages deploy job receives Pages/OIDC write access.

The local Mac relay has synthetic tests for authentication, revision/patch binding,
request/output bounds and actual Seatbelt file/network restrictions (the latter runs
only on macOS). Run `backend/.venv/bin/python -m pytest
backend/tests/unit/localization/test_compose_macos.py`. A real private Android render
remains a local integration check; no private Android source or translations belong
in application CI fixtures.

## Angular web capture

The backend job also builds the pinned synthetic Angular image and runs the renderer
negative tests inside a container with networking disabled. A real Celery worker then
captures three scenarios in two existing languages and a newly created third
language at two viewport sizes, using saved text
from the API. Unique render receipts and authenticated PNG digests are checked.
Dependency preparation is separate from the offline application builds. This gate
requires no private repository or provider credentials. See the
[web onboarding guide](angular-web-localization.md) for profiles and runner setup.

## Project language creation

The built-stack approval-branch smoke also uses **Add language** in the real
browser, waits for the Celery commit against the TLS provider fixture, reloads the
history, imports the new catalog and rejects a duplicate language. Only the
explicit PR action publishes a pull request. Backend tests cover all supported
catalog formats, preserved bytes/keys/placeholders, plural profiles, authorization,
uncertain-send recovery and additive Angular catalog registrations. The focused
browser check is `PLAYWRIGHT_BASE_URL=http://127.0.0.1:4179 npm --prefix frontend
run e2e -- add-language.spec.ts` against the built preview server.
See [adding languages](adding-languages.md) for format and runner boundaries.
