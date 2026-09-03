---
phase: 02-admin-configuration
reviewed: 2026-09-01T19:27:33Z
review_date: 2026-09-01
depth: deep
review_mode: digest-delta
asvs_level: OWASP ASVS 5.0 Level 1
scope: bounded regression-fix delta dd80fbc..2faff96 after the prior typed review
diff_base: dd80fbc41d514ea99907f9475dd08e87f79ceddf
reviewed_head: 2faff96e8c35b9964f7c458095fe9f1039a42e16
previous_reviewed_source_digest: 2e93097910a805663c7ccad721f4f629b478bdd01efca95541c8509c5f0354a9
reviewed_source_digest: bf9597261aee80e83d7ced33ec2a88162b7e47072507d174d30f97100214bf29
files_reviewed: 4
files_reviewed_list:
  - tools/gauntlet.sh
  - tools/real_smoke.sh
  - tools/tests/test_gauntlet.sh
  - tools/tests/test_real_smoke.sh
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

**Reviewed:** 2026-09-01T19:27:33Z
**Depth:** deep digest-delta
**Files Reviewed:** 4 changed source files
**Status:** issues_found
**Reviewed HEAD:** `2faff96e8c35b9964f7c458095fe9f1039a42e16`
**Reviewed-source digest:** `bf9597261aee80e83d7ced33ec2a88162b7e47072507d174d30f97100214bf29`

## Narrative Findings (AI reviewer)

### Summary

This fresh typed review is bounded to the exact regression-fix delta `dd80fbc..2faff96`: two RED checker changes in `a9c1e2f` followed by the two harness fixes in `2faff96`. All four files were read in full and their call chains into Docker Compose, OpenAPI drift generation/restoration, secret scanning, and smoke cleanup were traced.

No new Critical, project High-equivalent, Warning, or Info defect is introduced by this delta. The OpenAPI negative control preserves the exact `diff --git` semantic check without the early-closing pipeline that produced status 141 under `set -o pipefail`. The secret audit remains an exact, sorted four-field equality policy over path, line, detector type, and fingerprint; the new rows do not introduce a path-only, type-only, wildcard, or ignore-baseline bypass. The smoke harness uses disposable random provider values, a valid Fernet key, an owner-only runtime directory, and a mode-0600 environment file. Values are captured rather than echoed, Compose rendering is suppressed in preflight, and cleanup remains confined to the generated project, images, and runtime directory.

The RED/GREEN ordering is genuine. At `a9c1e2f`, the tests required the three Bitbucket inputs while the historical preflight still omitted them, and base Compose's `${VAR:?}` contract returned nonzero. The historical `printf | grep -Fq` control also reproduces status 141 with a large early match under pipefail. At `2faff96`, both packaged regression checkers pass.

The delta changes no application runtime, API, schema, generated client, package, lockfile, dependency, or production authorization behavior. It neither closes nor hides any retained warning. The current typed outcome therefore remains exactly Critical 0, Warning 6, Info 0, total 6, with `status: issues_found`. CR-01..CR-15 and WR-01..WR-02 remain CLOSED; WR-03..WR-08 remain OPEN Warnings; WR-08 remains deferred.

### Delta Assessment

**Files:** `tools/gauntlet.sh:717-746`, `tools/tests/test_gauntlet.sh:26-32`

**Result:** No finding. The shell `case` test recognizes the same fixed substring as the former `grep -Fq`, but does not create a producer/consumer pipeline and therefore cannot convert a successful early match into SIGPIPE status 141. The surrounding negative control still requires a real source mutation, a nonzero API drift result, exact restoration of the backend subject and generated frontend artifacts, and failure for the expected reason.

**Files:** `tools/gauntlet.sh:754-909`, `tools/gauntlet.sh:1339-1351`

**Result:** No finding. Current detector output is compared byte-for-byte with the audited policy after normalization to sorted `path|line|type|hashed_secret` rows. The focused self-test passes the current exact map and proves that one appended unreviewed fingerprint is rejected. The additions are exact current false positives and do not weaken scan scope or matching precision.

**Files:** `tools/real_smoke.sh:112-160`, `tools/real_smoke.sh:168-228`, `tools/tests/test_real_smoke.sh:16-33`

**Result:** No finding. The client secret is generated with OpenSSL, the encryption key with `Fernet.generate_key()`, and neither is printed. Both preflight and full smoke place the values only in a generated owner-only runtime tree with a mode-0600 env file. The normal smoke installs bounded cleanup before Compose resources are created; successful preflight deletes its exact runtime directory. The regression checker supplies non-secret fixtures only to Compose's configuration rendering and separately exercises the real generated-value preflight.

## Warnings

### WR-03: Provider `expires_in` is not upper-bounded

**Classification:** WARNING
**File:** `backend/src/verboflex/services/bitbucket_oauth.py:345-363`, `backend/src/verboflex/services/bitbucket_oauth.py:516-533`
**Issue:** An arbitrarily large positive provider expiry passes validation and can raise `OverflowError` during persistence date arithmetic. The regression-harness delta does not touch this path.
**Fix:** Enforce a documented maximum token lifetime, map arithmetic failure to `OAuthConnectionUnavailable`, and cover boundary and enormous values.

### WR-04: The locked developer dependency graph contains a known moderate advisory

**Classification:** WARNING
**File:** `frontend/package.json:35-40`, `frontend/package-lock.json:12991-13018`
**Issue:** The development-only Stryker chain resolves affected `qs@6.15.1` through `typed-rest-client@2.3.1`. The regression-harness delta does not change dependencies.
**Fix:** Upgrade or compatibly override the affected chain, regenerate the lockfile, and enforce a full-graph advisory threshold in CI.

### WR-05: Container provenance is mutable

**Classification:** WARNING
**File:** `docker/backend.Dockerfile:3-5`, `docker/backend.Dockerfile:22`, `docker/frontend.Dockerfile:3`, `docker/frontend.Dockerfile:17`, `docker-compose.yml:36`, `docker-compose.yml:51`
**Issue:** Upstream and deployable images remain tag-only, so reviewed source digests do not identify later container bytes. The regression-harness delta does not change image selectors.
**Fix:** Pin approved images with `tag@sha256:...` and update digests through a reviewed automation path.

### WR-06: The canonical environment example cannot configure Phase 2

**Classification:** WARNING
**File:** `.env.example:1-13`, `docker-compose.yml:21-27`
**Issue:** `.env.example` still omits the three required Bitbucket inputs and four preview/watchdog controls consumed by Compose. The regression harness now generates its own disposable values, but the canonical user-facing example remains incomplete.
**Fix:** Add safe placeholders, formats, generation guidance, defaults, and validated ranges for all seven settings.

### WR-07: The source manifest omits executable Phase 2 test data

**Classification:** WARNING
**File:** `tools/phase2_source_manifest.txt:1-36`, `backend/tests/architecture/phase2_spec_edge_matrix.json:1`
**Issue:** The semantic traceability test reads the JSON matrix, but the manifest still excludes it from source digests. The regression-harness delta does not repair manifest coverage.
**Fix:** Include executable non-code fixtures in the manifest and add a manifest-coverage assertion, then regenerate digests.

### WR-08: The advertised default Compose flow calls removed OAuth endpoints

**Classification:** WARNING
**File:** `tools/phase2_compose_flow.py:478-482`, `tools/phase2_compose_flow.py:530-546`
**Issue:** The positional/no-flag flow still calls removed authorization-code endpoints and fails before its remaining lifecycle checks. The supported gap-closure path does not invoke it, and the regression-harness delta does not repair it. **Disposition remains deferred, not fixed.**
**Fix:** Migrate the flow to the current client-credentials contract or remove it; if retained, execute it explicitly in the gauntlet.

### Current CR/WR Inventory Re-audit

Every row below is the current typed inventory. Disposition and severity remain on the same row so the semantic audit can reconcile the table one-to-one with frontmatter.

| Row | Disposition | Severity | Current authority / delta result |
|---|---|---|---|
| CR-01 | CLOSED | CRITICAL | Base Compose provider environment remains unchanged; the legacy smoke now supplies its required values. |
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

- Exact source delta inspected: `dd80fbc..2faff96` and separate RED/GREEN commits `a9c1e2f` / `2faff96`.
- Full contents and relevant callers read for all four scoped files.
- Shell syntax: `bash -n tools/gauntlet.sh tools/real_smoke.sh tools/tests/test_gauntlet.sh tools/tests/test_real_smoke.sh` — PASS.
- Packaged gauntlet checker: `bash tools/tests/test_gauntlet.sh` — PASS.
- Packaged real-smoke checker: `bash tools/tests/test_real_smoke.sh` — PASS.
- OpenAPI SIGPIPE reproduction of the removed pipeline: status 141 under `set -o pipefail` with an early fixed-string match.
- Missing-provider-variable RED reproduction: base/staging Compose configuration exits 1 at the exact `${VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET:?}` contract.
- Secret policy self-test, including appended-fingerprint negative control, passed through the packaged gauntlet checker.
- No owned `verboflex-phase01-smoke*` temporary runtime directory remained after focused checks.
- Artifact whitespace and worktree checks passed; only the pre-existing untracked `.gsd/`, planning runtime files, and `graphify-out/` remain outside review scope.
- Phase 2 final-mode source digest independently reproduced as `b0f7e5f09c804d81ad86ccc0a68032b3a4a031f4c7a69d3dbeca65ab5be587f6` before this report write.
- The full Phase 2 gauntlet was intentionally not rerun for this bounded review.

## Closure Decision

**No Critical or project High-equivalent blocker exists in the reviewed delta.** The delta creates no new finding and closes no retained finding. Six Warning findings remain open, so the canonical typed status is exactly `issues_found`.

---

_Reviewed: 2026-09-01T19:27:33Z_
_Reviewer: the agent (gsd-code-reviewer, digest-delta)_
_Depth: deep_
