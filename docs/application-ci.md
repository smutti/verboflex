# Application checks

`Check application` runs on every pull request and push to `main`, and can be
started manually in GitHub Actions. Require **Application checks** in branch
protection: it fails if any component fails, is cancelled, or is skipped.
The workflow does not deploy the application or contact real repositories.

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

## Release boundary

A green check verifies the current automated baseline. It does not certify a
production host, off-site backups, alert delivery, native assistive technology,
multi-tenant isolation, or performance with tens of millions of strings. The
historical phase-specific Playwright suites are not all included here; their
remaining release-level reconciliation is separate work. See the
[authorization and audit model](authorization-and-audit.md) for the Phase 8 scope.

For a smoke-harness change, manually dispatch **Check application** with `scope: smoke`
to rerun only the disposable browser/container workflow. This deliberately skips
the aggregate **Application checks** gate; a successful smoke-only run is not a
complete verification. Skipped jobs use distinct names so they cannot satisfy the
required full-gate checks. Pushes and pull requests always run all jobs.
