# Application checks

`Check application` runs on every pull request and push to `main`, and can be
started manually in GitHub Actions. Require **Application checks** in branch
protection: it fails if any component fails, is cancelled, or is skipped.
Also require **Website checks**, which runs on every pull request and main push.
The workflow does not deploy the application or contact real repositories.

The code-key and screenshot tests use synthetic Kotlin/Java and localization fixtures.
The built smoke also configures a separate code/translation mapping through HTTP,
imports code-only keys, checks missing keys in the browser, saves a proposal and
requests its screenshot through the real scheduler/Celery queue. A synthetic renderer
replaces only the Android build boundary; it verifies the frozen commit IDs and
selected translation in its PNG. The browser checks editing base-language resources
in the translations repository, compact source context, visible waiting state, lazy
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
npm --prefix frontend run api:check
backend/.venv/bin/python mcp-server/generate_contract.py --check
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend test -- --run
backend/.venv/bin/python tools/ci_backend.py --artifacts /tmp/verboflex-backend-evidence
(cd backend && uv run --locked mypy src && uv run --locked ruff check src tests)
uv sync --project mcp-server --locked
uv run --project mcp-server pytest mcp-server/tests
npx --prefix frontend playwright install chromium
PHASE8_HTTP_SETUP=1 PHASE7_EVIDENCE_DIR=/tmp/verboflex-smoke-evidence bash tools/phase7_smoke.sh
```

Finish client generation before running frontend tests: generation replaces the
client directory. Vitest uses two workers to avoid CPU contention in large DOM
and accessibility tests; assertions and timeouts remain unchanged.

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
