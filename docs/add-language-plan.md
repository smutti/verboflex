# Add a project language

## Contract

Reviewers and administrators can initialize a new locale from the configured source
catalog on the translation working branch. The operation uses the existing durable
Celery branch queue; it never writes to the PR destination or opens a PR implicitly.
The action supports Android XML (including MOKO and separate code repositories),
Qt TS, per-locale and locale-rooted JSON, iOS strings, XLIFF and HTML collections.
Existing provider write capabilities still apply: GitHub is import/review only.

New catalogs copy source wording as a starting point, not machine translation.
Preserve keys, nesting, comments, encodings, metadata and placeholders. Initialize
language metadata and native plural forms for the destination language. Existing
catalogs must remain byte-identical, except for adding a new locale object to a
shared JSON document. Reject ambiguous layouts, duplicate destinations, stale
imports, unsupported shapes, limits and changed permissions before sending.

After a verified commit, refresh imports the new language. Explicit Angular file
allowlists gain only the exact catalogs authorized by verified language jobs;
immutable mapping configuration is not rewritten. Existing web scenarios and
Compose capture continue to use the selected locale and frozen import. Screenshot
support requires the project's existing reviewed runner/scenario integration;
this operation does not invent screens or provision new renderers.

## Verification

- Parser-backed preservation tests for every format, nested JSON, non-UTF-8 iOS,
  plural differences, rich text, placeholders, regional locales and hostile input.
- Real PostgreSQL/API/worker flow: import, request, commit, refresh, edit/review;
  no overwrite, idempotent execution, authority revocation and uncertain sends.
- Browser action, pending/failure/success/reload, reviewer/viewer roles and narrow
  layouts; six interface catalogs and generated API/MCP contracts stay aligned.
- Offline Angular/Chromium capture in a newly created third language across all
  three scenarios and both viewports, with saved replacement/interpolation.
- Repository lint, type checking, backend/frontend suites and built-stack smoke.

Work is isolated on `codex/add-project-language`, retaining the already verified
import-session fix from PR #20. No new runtime dependencies are planned. The final
GitHub PR is reviewed before any remote application deployment.
