# SPEC — UAT import/preview corrections and product deletion

Status: v1 approved by the user: "Approvo. Puoi verificare anche che babel possa essere importato correttamente?"
Tier: 3 (deletion, authorization and worker concurrency).

## Scope and decisions proposed for approval

Internal existing HTTP/JSON API, consumed by the React SPA and generated SDK in this repository. Product is already a stable UUID resource; deletion must not destroy immutable published revisions or provider history. Existing Phase 2 prohibited a delete action; the user's new request explicitly expands that earlier scope.

1. Correct the false published-import error on draft-only products.
2. Make bounded repository discovery usable on a repository with unrelated directories: allow an optional localization root directory per repository side of a mapping. Existing mappings default to repository root and keep their current behavior. This is an explicit additive configuration feature, not silently raising or removing the 50-page budget.
3. Add administrator-only logical deletion of a product. Remove it from normal product lists, selectors, translation search and operational routes while preserving historical rows. Bitbucket repositories, branches, files, PRs, shared repository registrations and the global connection remain untouched. No restore UI or irreversible purge in this change.
4. Allow a new product to reuse a deleted product's name, with a new UUID and no inherited history or configuration.

## Setup plan

- Tools/new dependencies: none; use installed locked Python/Node test, type, lint, coverage and browser toolchain.
- Isolation: current feature branch codex/merge-phases-4-5, sequential execution; preserve unrelated/untracked work. No push/PR/merge.
- Commit SPEC at approval, then RED/GREEN checkpoints and final evidence under normal GSD conventions.
- Alembic owns additive schema migrations. Rehearse up/down on an isolated PostgreSQL database. Do not downgrade the user's database or delete its product for testing.
- Rebuild/update the local Docker app only after green checks, with fresh private database backup and original runtime environment preserved.
- Reuse tools/phase4_gauntlet.sh, tools/phase4_smoke.sh and existing coverage/mutation infrastructure where applicable. Add tools/uat_product_lifecycle_gate.sh as the persisted focused entry point, tools/uat_product_lifecycle_mutants.py for targeted manual mutants if existing mutation infrastructure cannot express them, and tools/tests/test_uat_product_lifecycle_gate.py for fail-closed negative controls.
- New focused test files: backend/tests/api/test_admin_product_deletion.py; backend/tests/integration/test_product_deletion.py; backend/tests/integration/test_preview_source_root.py; frontend/src/features/admin/products/ProductDeleteDialog.test.tsx. Extend existing mapping/import/preview component tests and browser tests rather than inventing a second harness.
- Final evidence: .planning/quick/260906-kjj-correggere-uat-import-preview-e-aggiunge/EVIDENCE.md. Existing Phase 4 source-bound reports become stale when source changes; preserve their history and do not relabel them passed for an unseen digest.

## Executable scenarios

### S1 — Draft-only published imports
Given a product with candidate revision and no published revision, opening Mappings shows an explanatory unpublished state and performs no published-import request. Candidate editing and Preview remain available. An actual error for a published product still displays a recoverable error; do not treat every 404 as empty.

### S2 — Inactive published product
Given a suspended product with a published revision, show that imports are unavailable until reactivation; no false network-failure framing and no enabled import mutation. Active published products retain polling, pagination and stale-authority guards.

### S3 — Root-scoped discovery
Given a repository fixture with more than 50 unrelated directories and localization files under `translations`, choosing root `translations` discovers only that subtree. At most the existing 50 listing pages, 5,000 entries, 12 path levels, 500 candidate files, 1 MiB per file and 20 MiB total apply. The detector receives repository-relative file paths and the exact source-branch commit, not target-branch content. Existing timeout and byte budgets remain.

### S4 — Root identity and hostile paths
Omitted root preserves current whole-repository behavior. Reject absolute paths, traversal, URL-like roots and escaping provider entries; accept only normalized repository-relative directories. A root change increments candidate authority, invalidates old preview confirmation and participates in input identity/digest. Published root is immutable and respected by import/refresh/revalidation, including separate keys/translations sides. No file outside the configured subtree is read as candidate content.

### S5 — Actionable preview failure
Deterministically reproduce the current 50-page failure. Keep existing job states/error_code values compatible; add optional safe diagnostic information for a known discovery limit. The UI explains that the scan limit was reached and suggests narrowing the localization root. Unknown exceptions retain a generic failure. Do not expose stack traces, credentials, provider bodies or raw exceptions. A successful Celery delivery is never presented as a successful preview when the persisted job failed.

### S6 — Delete authorization and confirmation
Add DELETE /api/v1/admin/products/{product_id}. No authentication returns 401; each non-admin role returns 403 without mutation. Admin UI requires an explicit dialog with product name and effects; Cancel sends no DELETE. A forged/stale product selection must not delete a different product.

### S7 — Delete effect and retry
Deleting a draft, inactive or published product with no active work returns 204. Persist deleted_at/deleted_by and is_active=false atomically. Product/configuration/value/history rows remain. Normal lists, selectors, direct product/nested reads, search/detail and operational routes no longer expose or act on that product. Existing authenticator semantics remain unchanged. Repeat DELETE of an already-deleted known UUID returns 204 without further changes; missing UUID returns generic 404. These are new endpoint semantics, not a rewrite of existing deactivation.

### S8 — Active work and concurrency
Deletion while a preview/import/revalidation is queued or running returns 409 with a bounded actionable message and changes nothing. Use Product-first lock ordering consistent with worker activation and publication. Race tests cover deletion versus enqueue, activation and publication; no worker can activate or revive a deleted product. No background provider mutation is triggered by deletion.

### S9 — Name reuse and historical integrity
After deleting product A, creating product B with A's name succeeds with a new UUID; A's revisions, translation identities and history remain tied only to A. Concurrent creation of two non-deleted products with the same normalized name still permits exactly one. Downgrade must fail explicitly if reuse makes restoration of the old unique constraint unsafe; do not delete or merge rows to make downgrade pass.

### S10 — UI and real execution
Successful deletion returns to Products and invalidates cached product/translation selectors. Confirm/cancel/error/conflict states remain keyboard accessible and fit narrow viewports. Verify fresh local build, migration head, API health, worker ping and HTTP/browser flows using a disposable test product; never delete the user's existing product automatically. Actual Bitbucket preview verification is read-only and must use a user-selected localization root/branch, without fabricating UAT acceptance.

## Failure model and evidence

- Data loss/wrong-product deletion: persisted before/after assertions, cancellation tests, strict UUID scope, migration rehearsal and mutation controls.
- Authorization leaks: all-role API matrix and direct/nested/search endpoint tests, not only hidden UI buttons.
- Deletion/job races: real PostgreSQL lock/interleaving tests, denied enqueue and activation after deletion.
- Silent truncation/unbounded scans: >50-directory synthetic fixture, exact-budget boundary tests, generated nested-path/escape properties and safe error assertions.
- Breaking clients: generated OpenAPI/SDK comparison; optional fields/defaults preserve existing shapes and enums.
- Regressions: fresh backend/frontend suites, types, lint/format, 100% changed-line gates, 3–5 meaningful mutation probes, randomized-suite execution with recorded seeds, browser/build/deployment smoke and diff secret scan. Unavailable/substituted layers must be explicitly recorded, never claimed passed.

## API gate disposition at proposal time

Design constraints, not verified passes: conventional UUID DELETE/204; additive optional root/diagnostic fields; existing OAuth bearer/admin role boundary; ID-scoped idempotency; no unbounded child deletion or provider fan-out in DELETE; indexed logical deletion and existing cursor pagination; no expensive history payload in default responses; no raw internal failure leakage. Rate-limit and revocation behavior must be inspected and tested before claiming the blast-radius gate passed. Security-sensitive changes require a dedicated security review. Independent old-coder blind verification is not performed and must not be claimed unless its protocol is separately executed.

## Must NOT

- Purge history or modify any Bitbucket/shared connection/repository resource.
- Implement a repository-wide unlimited traversal or arbitrarily relax safety budgets.
- Turn the current user's products into test fixtures or delete one without a separate explicit UI/action request.
- Change source branch to default PR target, infer a rename, truncate canonical keys/text, bypass roles, revive deleted products or mark unanswered UAT tests passed.
- Disable existing tests or weaken assertions merely to reach green. Existing accepted-contract tests that need updating must be identified in RED and mapped to this newly approved specification.

## Residual assumptions

Logical rather than physical deletion, no restore UI, deletion blocked during active jobs, name reuse, and optional root configuration are proposals requiring approval. If a different deletion or discovery policy is desired, revise visibly before implementation.

## Revisions

- 2026-09-06 v1: Proposed from live UAT failures and the new product-deletion request; approval not yet obtained.
- 2026-09-06 approval: User explicitly approved v1 and requested live importability verification of babel. This adds a verification target, not automatic authorization for a new localization format or provider writes. Any format/layout contract gap will be surfaced separately.
