# Dependency security

Dependency updates are verified against the committed lockfiles, including
development tools. Do not use audit exceptions or dismiss Dependabot alerts as a
substitute for updating/removing affected packages.

## Public-release audit — 11 October 2026

The frontend lock now uses `source-map-js` 1.2.2 and the backend lock uses Mako
1.4.3. These address [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)
and [GHSA-5639-2j2p-m4mx](https://github.com/advisories/GHSA-5639-2j2p-m4mx).
Only the affected transitive packages were updated; no advisory was dismissed.

## Current compatibility choices

- Backend: PyJWT **2.15.1** replaces 2.13.0; urllib3 **2.8.0** replaces 2.7.0 in
  the development graph. The standalone MCP lock already used PyJWT 2.15.1.
  VerboFlex still restricts access tokens to HS256; no authentication policy changed.
- Frontend: patched brace-expansion, fast-uri, js-yaml, qs and undici in the lock.
  `js-yaml: 4.3.2` retains the existing major-version override used by the API
  generator/linter. The scoped `typed-rest-client > qs: 6.16.0` override replaces
  that package's vulnerable exact pin, while retaining Stryker's supported client.
  Reconsider these overrides when upstream dependencies adopt secure compatible pins.
- The shadcn CLI was used only to import `shadcn/tailwind.css`. Its transitive
  `braces` dependency has no published fix. The CSS from **shadcn 4.19.0** is now
  owned at `frontend/src/styles/shadcn.css`, with the original MIT notice and a
  distributable license in `frontend/public/licenses/shadcn.txt`. The original
  CSS SHA256 is `bc7d83425702955b4cb67cb14ede9d603f9d912376d57a2d81d661094d2a782a`.
  Compiled CSS was identical before/after this move. Existing React/Radix components
  and `components.json` remain project-owned. Review the CLI's dependency audit
  before reintroducing it to add/generate components; do not reinstall it just for CSS.

Upstream references: [PyJWT critical advisory](https://github.com/advisories/GHSA-ffc3-869f-jxw9),
[PyJWT releases](https://pyjwt.readthedocs.io/en/stable/changelog.html),
[braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm),
[qs changes](https://github.com/ljharb/qs/blob/main/CHANGELOG.md).

## Repeat audits

Run from the repository root after installing the backend development tools. These
commands audit locked packages rather than opportunistically resolving new versions.

```sh
npm --prefix frontend audit

uv export --project backend --locked --all-groups --format requirements-txt \
  --no-emit-project --no-emit-package verboflex-mcp \
  --output-file /tmp/verboflex-backend-audit.txt
backend/.venv/bin/pip-audit --no-deps --disable-pip \
  -r /tmp/verboflex-backend-audit.txt

uv export --project mcp-server --locked --all-groups --format requirements-txt \
  --no-emit-project --output-file /tmp/verboflex-mcp-audit.txt
backend/.venv/bin/pip-audit --no-deps --disable-pip \
  -r /tmp/verboflex-mcp-audit.txt
```

Local workspace packages are excluded from the PyPI audit; their source is covered
by code review/tests. Audit databases evolve, so a clean result is dated evidence,
not a permanent security guarantee. After updates, run auth/OAuth and input-robustness
tests, MCP tests, frontend tests/typecheck/build and the Docker/browser smoke.
