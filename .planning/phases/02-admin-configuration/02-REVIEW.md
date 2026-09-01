---
phase: 02-admin-configuration
reviewed: 2026-09-01T18:17:51Z
review_date: 2026-09-01
depth: deep
review_mode: digest-delta
asvs_level: OWASP ASVS 5.0 Level 1
scope: test-only delta 5389c15..542903d after the prior full typed review
diff_base: 5389c15c7c1d5f4f6f63e6a2568937ab423b3857
reviewed_head: 542903d39b11617c1985574eb4a5f7d32f9038cf
previous_reviewed_source_digest: f12c23d7aa7655027b189b7793227403575e5393e92ed08ae9009db9dda1e1ca
reviewed_source_digest: 2e93097910a805663c7ccad721f4f629b478bdd01efca95541c8509c5f0354a9
files_reviewed: 1
files_reviewed_list:
  - backend/tests/architecture/test_phase2_gap_closure.py
findings:
  critical: 0
  warning: 6
  info: 0
  total: 6
status: issues_found
review_inventory:
  CR-01: {disposition: closed, severity: critical}
  CR-02: {disposition: closed, severity: critical}
  CR-03: {disposition: closed, severity: critical}
  CR-04: {disposition: closed, severity: critical}
  CR-05: {disposition: closed, severity: critical}
  CR-06: {disposition: closed, severity: critical}
  CR-07: {disposition: closed, severity: critical}
  CR-08: {disposition: closed, severity: critical}
  CR-09: {disposition: closed, severity: critical}
  CR-10: {disposition: closed, severity: critical}
  CR-11: {disposition: closed, severity: critical}
  CR-12: {disposition: closed, severity: critical}
  CR-13: {disposition: closed, severity: critical}
  CR-14: {disposition: closed, severity: critical}
  CR-15: {disposition: closed, severity: critical}
  WR-01: {disposition: closed, severity: warning}
  WR-02: {disposition: closed, severity: warning}
  WR-03: {disposition: open, severity: warning}
  WR-04: {disposition: open, severity: warning}
  WR-05: {disposition: open, severity: warning}
  WR-06: {disposition: open, severity: warning}
  WR-07: {disposition: open, severity: warning}
  WR-08: {disposition: open, severity: warning}
---

# Phase 2: Code Review Report

**Reviewed:** 2026-09-01T18:17:51Z
**Depth:** deep digest-delta
**Files Reviewed:** 1 changed source file
**Status:** issues_found
**Reviewed HEAD:** `542903d39b11617c1985574eb4a5f7d32f9038cf`
**Reviewed-source digest:** `2e93097910a805663c7ccad721f4f629b478bdd01efca95541c8509c5f0354a9`

## Narrative Findings (AI reviewer)

### Summary

This fresh typed review is bounded to the only source delta after the prior full review: commit `542903d`, which changes `backend/tests/architecture/test_phase2_gap_closure.py:1236-1254`. The exact `5389c15..542903d` diff replaces a stale live-report assertion that required `gaps_found` with explicit branches for the two valid semantic transitions already enforced by `_verifier_groups`: truthful `gaps_found` and truthful `passed`.

No new Critical, project High-equivalent, Warning, or Info defect is introduced by the delta. The passed branch requires no open blockers, no gaps, and complete inventory counts. The existing helper still rejects duplicate YAML keys, missing or extra inventory identifiers, malformed records, count/total drift, hidden warnings, unsupported statuses, false passed reports with gaps or blockers, and `gaps_found` reports without concrete gaps. The existing mutation tests still exercise those fail-closed paths.

The delta changes no production/runtime/schema/API/generated/dependency/configuration/manifest behavior. It neither closes nor hides any existing warning. The current typed outcome therefore remains exactly Critical 0, Warning 6, Info 0, total 6, with `status: issues_found`. CR-01..CR-15 and WR-01..WR-02 remain CLOSED; WR-03..WR-08 remain OPEN Warnings; WR-08 remains deferred.

The canonical review and verifier were inspected only as untrusted transition context. Both remain bound to their recorded earlier HEAD/digest and are not promoted here as current-digest authority. This report alone is freshly bound to review digest `2e93097910a805663c7ccad721f4f629b478bdd01efca95541c8509c5f0354a9`.

### Delta Assessment

**File:** `backend/tests/architecture/test_phase2_gap_closure.py:1236-1254`

**Result:** No finding. The change broadens only the live fixture assertion from one historical state to the two states accepted by the phase verifier contract. It does not weaken `_verifier_groups`, which remains the validation authority before the branch assertions run.

**Negative controls retained:**

- Duplicate frontmatter keys are rejected by `_UniqueKeySafeLoader` at lines 378-409.
- Review inventory exact-set, table, severity, disposition, count, and typed-status reconciliation remains enforced at lines 512-605.
- Verifier inventory exact identifiers/totals, unique blocker/warning lists, preserved `WR-03..WR-08`, and state-specific gap/completeness rules remain enforced at lines 608-685.
- Missing/duplicate/hidden/count-inconsistent review mutants remain at lines 1201-1233.
- Incomplete inventory, hidden warning, false-gap, blocker, unsupported-status, and gap-without-detail verifier mutants remain at lines 1257-1293.

## Warnings

### WR-03: Provider `expires_in` is not upper-bounded

**Classification:** WARNING
**File:** `backend/src/verboflex/services/bitbucket_oauth.py:345-363`, `backend/src/verboflex/services/bitbucket_oauth.py:516-533`
**Issue:** An arbitrarily large positive provider expiry passes validation and can raise `OverflowError` during persistence date arithmetic. The test-only delta does not touch this path.
**Fix:** Enforce a documented maximum token lifetime, map arithmetic failure to `OAuthConnectionUnavailable`, and cover boundary and enormous values.

### WR-04: The locked developer dependency graph contains a known moderate advisory

**Classification:** WARNING
**File:** `frontend/package.json:35-40`, `frontend/package-lock.json:12991-13018`
**Issue:** The development-only Stryker chain resolves affected `qs@6.15.1` through `typed-rest-client@2.3.1`. The test-only delta does not change dependencies.
**Fix:** Upgrade or compatibly override the affected chain, regenerate the lockfile, and enforce a full-graph advisory threshold in CI.

### WR-05: Container provenance is mutable

**Classification:** WARNING
**File:** `docker/backend.Dockerfile:3-5`, `docker/backend.Dockerfile:22`, `docker/frontend.Dockerfile:3`, `docker/frontend.Dockerfile:17`, `docker-compose.yml:36`, `docker-compose.yml:51`
**Issue:** Upstream and deployable images remain tag-only, so reviewed source digests do not identify later container bytes. The test-only delta does not change image selectors.
**Fix:** Pin approved images with `tag@sha256:...` and update digests through a reviewed automation path.

### WR-06: The canonical environment example cannot configure Phase 2

**Classification:** WARNING
**File:** `.env.example:1-13`, `docker-compose.yml:21-27`
**Issue:** `.env.example` still omits the three required Bitbucket inputs and four preview/watchdog controls consumed by Compose. The test-only delta does not change configuration.
**Fix:** Add safe placeholders, formats, generation guidance, defaults, and validated ranges for all seven settings.

### WR-07: The source manifest omits executable Phase 2 test data

**Classification:** WARNING
**File:** `tools/phase2_source_manifest.txt:1-36`, `backend/tests/architecture/phase2_spec_edge_matrix.json:1`
**Issue:** The semantic traceability test reads the JSON matrix, but the manifest still excludes it from source digests. The test-only delta does not repair manifest coverage.
**Fix:** Include executable non-code fixtures in the manifest and add a manifest-coverage assertion, then regenerate digests.

### WR-08: The advertised default Compose flow calls removed OAuth endpoints

**Classification:** WARNING
**File:** `tools/phase2_compose_flow.py:478-482`, `tools/phase2_compose_flow.py:530-546`
**Issue:** The positional/no-flag flow still calls removed authorization-code endpoints and fails before its remaining lifecycle checks. The supported gap-closure path does not invoke it, and the test-only delta does not repair it. **Disposition remains deferred, not fixed.**
**Fix:** Migrate the flow to the current client-credentials contract or remove it; if retained, execute it explicitly in the gauntlet.

### Current CR/WR Inventory Re-audit

Every row below is the current typed inventory. Disposition and severity remain on the same row so the semantic audit can reconcile the table one-to-one with frontmatter.

| Row | Disposition | Severity | Current authority / delta result |
|---|---|---|---|
| CR-01 | CLOSED | CRITICAL | Base Compose provider environment remains unchanged. |
| CR-02 | CLOSED | CRITICAL | Exact bounded client-credentials exchange remains unchanged. |
| CR-03 | CLOSED | CRITICAL | Client-credentials-only lifecycle authority remains unchanged. |
| CR-04 | CLOSED | CRITICAL | Access-only encrypted generation and renewal authority remain unchanged; WR-03 stays separate and open. |
| CR-05 | CLOSED | CRITICAL | Candidate graph clone and atomic identity promotion remain unchanged. |
| CR-06 | CLOSED | CRITICAL | Immutable active-revision sidecar revalidation remains unchanged. |
| CR-07 | CLOSED | CRITICAL | Persistent five-step mobile wizard controls remain unchanged. |
| CR-08 | CLOSED | CRITICAL | Cursor completeness and stale-page rejection remain unchanged. |
| CR-09 | CLOSED | CRITICAL | Watchdog CAS and retry-attempt isolation remain unchanged. |
| CR-10 | CLOSED | CRITICAL | HTTP/CLI admin survivor authority remains unchanged. |
| CR-11 | CLOSED | CRITICAL | Beat scheduler deployment parity remains unchanged. |
| CR-12 | CLOSED | CRITICAL | Active-revalidation currentness and recovery remain unchanged. |
| CR-13 | CLOSED | CRITICAL | Runtime CSP and defensive response headers remain unchanged. |
| CR-14 | CLOSED | CRITICAL | Exact-detail candidate/active branch authority remains unchanged. |
| CR-15 | CLOSED | CRITICAL | Router-native dirty-form transition authority remains unchanged. |
| WR-01 | CLOSED | WARNING | Workspace overview and location-authoritative shell remain unchanged. |
| WR-02 | CLOSED | WARNING | Composite ownership and published-child immutability remain unchanged. |
| WR-03 | OPEN | WARNING | Provider expiry remains unbounded above. |
| WR-04 | OPEN | WARNING | Development dependency advisory remains present. |
| WR-05 | OPEN | WARNING | Container image selectors remain mutable tags. |
| WR-06 | OPEN | WARNING | Phase 2 environment settings remain undocumented in `.env.example`. |
| WR-07 | OPEN | WARNING | Executable edge-matrix JSON remains outside the source manifest. |
| WR-08 | OPEN | WARNING | Default no-flag Compose flow remains broken and deferred. |

## Verification Performed

- Exact source delta inspected: `5389c15..542903d`.
- Current semantic helpers and mutation controls inspected in context.
- Current structured review inventory, canonical review, and verifier report inspected as untrusted context only.
- Focused semantic test: `cd backend && uv run pytest -q tests/architecture/test_phase2_gap_closure.py -x`.
- Artifact whitespace check: `git diff --check -- .planning/phases/02-admin-configuration/02-REVIEW.md`.

## Closure Decision

**No Critical or project High-equivalent blocker exists in the reviewed delta.** The delta creates no new finding and closes no retained finding. Six Warning findings remain open, so the canonical typed status is exactly `issues_found`.

---

_Reviewed: 2026-09-01T18:17:51Z_
_Reviewer: the agent (gsd-code-reviewer, digest-delta)_
_Depth: deep_
