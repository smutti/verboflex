# SPEC addendum — larger imports and duplicate-key diagnostics

Status: approved by the user on 2026-09-06: "Approvo".
Tier: 3 — bounded resource use, canonical identity, import atomicity and admin-only source diagnostics.

User input, 2026-09-06: "fai fix per la importazione, per i duplicati possiamo aggiungere in UI una modalità per cui si mostra che ci sono delle chiavi duplicate".

This replaces only the whole-mapping capacity restriction and adds diagnostics to the approved MOKO addendum. SPEC.md v1 (including localization roots and product deletion) and the remaining MOKO requirements stay approved. Do not reopen their approval. The user's input requests this extension; it is not recorded as approval of the newly specified limits or interaction below.

## User-visible behavior proposed

- Fix discovery/import for the observed MOKO layout and datasets of Babel's size using the selected repository, source branch and optional localization root.
- Add **View duplicate keys** in Preview and import results when duplicate groups exist. Show affected keys, language/base marker, repository side, file, occurrence positions, and separate counts for duplicate groups and repeated occurrences beyond the first. Same key in different languages is not a duplicate.
- This is a **read-only diagnostic mode**, not silent deduplication or partial canonical activation. A mapping containing duplicate identities remains blocked from confirmation/publication or activation, with an explicit explanation. A previously active dataset is retained unchanged. The user corrects the source on Bitbucket, then revalidates/reimports.
- For Babel's current commit, success means a truthful complete diagnostic report, not claiming all 42,766 occurrences became valid canonical values. A duplicate-free synthetic dataset of equivalent scale proves successful import/search separately. Real full Babel import becomes possible after its source duplicates are resolved.

## C1 — Separate file and complete-mapping capacity

Given valid confirmed inputs satisfying all other budgets, exactly **50,000 canonical values per complete mapping** can be parsed, staged, activated and searched; 50,001 is rejected atomically with an actionable capacity message and no partial replacement. Count values across all languages and both sides of a separate mapping before joining, so ignored or unmatched records cannot bypass the bound. Preserve the existing 5,000-value bound for a single file and the format-specific depth/structure limits.

The original shared MAX_CANONICAL_VALUES contract served both file and complete-mapping validation. Separate those responsibilities explicitly; changing one constant globally and accidentally allowing oversized individual files is not acceptable. Update only existing assertions that enforce the superseded aggregate bound, documenting their mapping to C1 before RED.

Input discovery limits remain unchanged: 50 listing pages, 5,000 entries, 12 path levels, 500 files, 1 MiB per file and 20 MiB aggregate source bytes. Complete-mapping canonical encoded output has a separate hard ceiling of **128 MiB**; single-file expansion retains its existing source-plus-20-MiB allowance. Enforce both value and encoded-byte budgets incrementally, before accumulating an over-limit record. This is an explicit capacity extension, not unlimited parsing.

Use bounded persistence batches of at most 500 records and avoid multiple full materializations of the canonical payload. Preserve exact manifest hashing, retry idempotency, execution fencing and all-or-nothing activation. Where larger jobs require more execution time, the approved upper envelope is 180 seconds soft / 240 seconds hard for import tasks, coordinated with stale-execution reconciliation and leases; never disable timeout handling. Preview retains its existing timeout unless separately revised.

## C2 — Duplicate identity and complete diagnostic counts

Given two scalar strings with the same exact name in the same language, repository side and selected layout, identify both source occurrences as one duplicate group. Three occurrences mean one group and two repeated occurrences. Cross-file duplicates within the same layout must be found; separate languages, repository sides and supported typed selectors must not be conflated.

Scan all bounded files for duplicates, not only until the first parser issue or the existing five-item summary limit. Preserve source spelling and provenance; do not normalize away distinct keys, choose first/last, merge texts or rewrite remote files. Duplicate identical texts still count as duplicates.

Report malformed/unsupported source separately. An incomplete diagnostic scan must be visibly incomplete and cannot authorize publication/import. Diagnostics are not canonical values, and relaxing their representation must not bypass the canonical uniqueness invariant.

## C3 — Read-only UI mode

Given a finished duplicate report, the admin sees the total duplicate-group count and can open a keyboard-accessible view with **Only duplicate keys**, file/language filters and cursor pagination. Show repository, exact source branch, commit and report execution so stale results cannot be mistaken for a new scan.

Show group membership/occurrence positions without rendering source-controlled markup as HTML. Long keys are explicitly abbreviated in the list with their length and provenance; do not silently truncate canonical keys. Occurrence positions must be real parser-derived locations (line where available, otherwise an explicitly labeled resource position), never fabricated line numbers. Translation bodies and raw XML are not included in default diagnostics.

Cancel/close performs no mutation. Failed loads retain a retry action. Changes of product, mapping, token, input version or execution abort/fence old responses. Display missing and incomplete reports honestly. Diagnostic navigation must not enable editing, approval or PR actions for ambiguous data.

## C4 — Internal additive HTTP/JSON contract

Scope: existing internal FastAPI/React API; first-party generated TypeScript SDK is updated with it. Preview jobs and import executions already provide stable resource identities. Do not invent a second scheduler or perform provider discovery inside GET requests.

Add optional inexpensive report-summary fields to existing job/import projections. Add paginated GET children aligned with existing resources:

- `/api/v1/admin/preview-jobs/{job_id}/duplicates`
- `/api/v1/admin/products/{product_id}/imports/{import_id}/duplicates`, bound to the exact execution number in its query/cursor.

Use `items` and `next_cursor`, default 50 / maximum 100 groups per page, with bounded occurrence pages rather than unbounded nested lists. Cursors bind execution, filters and source authority. Reads use stored worker-generated diagnostics, not additional Bitbucket calls.

Require the existing admin bearer-role dependency. Verify 401 unauthenticated, 403 for each non-admin role, 404 for missing/mismatched resources, and the established invalid/stale cursor error convention. Reject access to deleted products under the approved lifecycle contract. Keep existing job state/error enums and their meanings; a duplicate report does not turn a failed import into `current`.

Bound report storage to 50,000 occurrence references and 16 MiB encoded diagnostic data; reject overflow explicitly, retain prior active data and show that diagnostics are incomplete. Response pages must remain bounded by both item count and encoded size. A report-generation failure must never become a successful empty report.

Authentication, revocation, rate limits, execution correlation and authorization gates require actual tests before claiming a pass. Report endpoints are idempotent reads. Logs contain bounded fixed error codes and correlation IDs, not source-controlled text, credentials or raw exceptions. Dedicated security review required before completion.

## C5 — Atomicity, refresh and recovery

On duplicate detection in a first import, no active canonical dataset is created. On refresh, do not mark existing keys deleted, replace constraints/review states, activate clean subsets, or revive stale work. Preserve historical and existing active rows, and associate diagnostics with the failed attempt.

After the user resolves duplicates on Bitbucket, a fresh validation/import at the new commit clears the current warning only on authoritative successful completion. Historical reports retain their original source identity. Repeated delivery must not duplicate diagnostic rows or activate an obsolete execution.

## C6 — Executable verification and real Babel evidence

- RED/GREEN: exact 50,000 / 50,001 aggregate boundary, unchanged 5,000 / 5,001 file boundary, encoded-output boundary, both separate sides, duplicate groups and occurrence counts, cross-file duplicates, malformed/hostile XML, and duplicate-free fixtures for all existing formats.
- Real PostgreSQL integration: bounded batch staging/activation, search count and representative values, interrupted worker/retry, old-execution fencing, retained baseline on diagnostics, report pagination/ownership and migration up/down.
- Scale fixture: 19 synthetic MOKO files totaling at least Babel's observed 42,766 source occurrences, plus duplicate-free 50,000-value import. Record runtime and peak resident memory; a duplicate-free 50,000-value local worker/import test must finish within the configured hard timeout with peak process RSS at most 512 MiB. Measure in a fresh process and record toolchain/database configuration. Do not claim these target measurements already passed.
- Live Babel: use the durable read-only probe, record exact commit and actual diagnostic counts without committing proprietary content. Do not deduplicate the live source in memory and call that a real successful import. No writes to Bitbucket or automatic changes to the user's product.
- Full suites, types, lint/format, 100% changed-line gate, mutation/property tests, randomized order with seeds, API/SDK generation checks, browser/accessibility tests, dedicated security pass, backed-up Docker upgrade and smoke per the parent SPEC. All evidence is source-state-specific; no automatic Phase 4 UAT pass.

## Setup plan / files

Continue quick task 260906-kjj sequentially on codex/merge-phases-4-5. Preserve unrelated untracked files. No new dependencies or installs, no push/PR/merge. Commit this addendum on approval, then RED/GREEN checkpoints under the existing cadence. Alembic owns additive diagnostic persistence and root/lifecycle migrations; rehearse on an isolated database first.

Reuse the already-approved fixture directory `backend/tests/fixtures/localization/moko_xml/`, source-root tests, `tools/check_repository_importability.py`, `tools/uat_product_lifecycle_gate.sh` and mutation/checker infrastructure. Additional new tests and focused UI/tooling files:

- `backend/tests/unit/localization/importing/test_mapping_capacity.py`
- `backend/tests/unit/localization/preview/test_moko_xml.py`
- `backend/tests/unit/localization/test_duplicate_diagnostics.py`
- `backend/tests/api/test_import_duplicate_diagnostics.py`
- `backend/tests/integration/test_import_capacity.py`
- `backend/tests/integration/test_import_duplicate_diagnostics.py`
- `frontend/src/features/admin/imports/DuplicateKeysDialog.tsx`
- `frontend/src/features/admin/imports/DuplicateKeysDialog.test.tsx`
- `tools/benchmark_import_capacity.py`
- `tools/tests/test_import_capacity_benchmark.py`

Extend existing parser, worker, preview/import API/schema/service, source-root UI and browser tests rather than introducing a parallel import implementation. Extend EVIDENCE.md and the current PLAN; do not mark the parent task complete while deletion/root work remains.

## Must NOT / residual decision

No automatic source edits, first/last-wins deduplication, inferred base language, partial active datasets, unbounded reports, disabled safety tests, credential leakage or fabricated canonical import success.

**Decision presented for approval:** duplicates are visible in a read-only diagnostic mode and remain blocking for the entire affected mapping. If the desired behavior is importing/activating the clean subset while quarantining duplicate keys, that is a different identity/refresh contract and must replace C3/C5 explicitly before implementation.

## Revisions

- 2026-09-06 proposal: incorporates the new request for larger imports and visible duplicate keys; explicit aggregate/output capacity and diagnostic-mode semantics await approval. Earlier S1/S2 implementation and earlier approvals remain unchanged.
- 2026-09-06 approval: user approved this exact addendum, including the 50,000-value capacity and read-only diagnostics with duplicate keys remaining blocking. Proceed with implementation; no further policy approval is required for these scenarios.
