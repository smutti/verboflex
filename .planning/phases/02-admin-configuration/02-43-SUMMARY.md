---
phase: 02-admin-configuration
plan: 43
subsystem: frontend-runtime-security
tags: [nginx, csp, clickjacking, docker, smoke, tdd]

requires:
  - phase: 02-42
    provides: Green shared Phase 2 built-image smoke lifecycle and inactive-product recovery flow
provides:
  - Exact runtime CSP and anti-framing headers on the built frontend image
  - Root and deep-link SPA fallback verification in the common Phase 2 smoke path
  - Fail-closed negative controls for missing, duplicate, bypassed, or weakened headers
affects: [02-38, phase-02-gauntlet, frontend-deployment, security-review]

actuals:
  tokens: 2833
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - Nginx security headers are exact, unique, and applied with always
    - Built artifacts are probed at both root and a try_files deep SPA route
    - Smoke diagnostics identify only target, header, and expected value

key-files:
  created: []
  modified:
    - docker/frontend.nginx.conf
    - tools/phase2_smoke.sh
    - backend/tests/architecture/test_phase2_live_provider_smoke.py

key-decisions:
  - "The frontend image serves one canonical CSP plus XFO, nosniff, referrer, and permissions headers with Nginx always semantics."
  - "The common smoke path verifies exact case-insensitive singleton headers on both / and /admin/products/security-header-probe after frontend readiness."
  - "The versioned gauntlet's supported --gap-closure mode is the phase-wide authority; the unsupported literal --mode review command did not justify changing the CLI."

patterns-established:
  - "Runtime security contract: parse normalized response headers, require one canonical value, and keep failures bounded."
  - "Packaging regression guard: exercise the same built frontend image and lifecycle used by every Phase 2 smoke mode."

requirements-completed: [UI-03]

coverage:
  - id: D1
    description: The built frontend denies framing and exposes the complete defensive header contract at root and deep SPA fallback.
    requirement: UI-03
    verification:
      - kind: integration
        ref: bash tools/phase2_smoke.sh --base-client-credentials
        status: pass
      - kind: other
        ref: bash tools/phase2_gauntlet.sh --gap-closure (18/18 layers)
        status: pass
    human_judgment: false
  - id: D2
    description: Missing common invocation, missing deep-link, duplicate headers, weakened CSP/XFO, and unbounded diagnostics are rejected.
    requirement: UI-03
    verification:
      - kind: unit
        ref: backend/tests/architecture/test_phase2_live_provider_smoke.py (16/16 passed)
        status: pass
      - kind: mutation
        ref: Phase 2 gauntlet backend 129/129 and Stryker 30/30 killed
        status: pass
    human_judgment: false

duration: 10h 28m
completed: 2026-09-01
status: complete
---

# Phase 02 Plan 43: Runtime Frontend Anti-Framing Summary

**The production Nginx image now serves a complete, exact anti-clickjacking policy whose root and deep SPA responses are enforced by the shared Phase 2 runtime gauntlet.**

## Performance

- **Duration:** 10h 28m
- **Started:** 2026-08-31T20:44:57Z
- **Completed:** 2026-09-01T07:12:57Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added a canonical CSP with `frame-ancestors 'none'` and `frame-src 'none'`, `X-Frame-Options: DENY`, nosniff, strict referrer policy, and a restrictive permissions policy, all emitted with `always`.
- Extended the common built-image smoke to probe `/` and `/admin/products/security-header-probe`, normalize CRLF, and require exactly one case-insensitive header with the complete expected value.
- Added in-memory negative controls proving the contract fails when its common invocation, deep fallback, uniqueness guard, CSP, XFO, or bounded diagnostic policy is removed or weakened.
- Closed the official phase-wide assurance gate from a fresh source digest with all 18 layers passing and zero plan resources left behind.

## Task Commits

1. **Task 1 RED: require built-image anti-framing headers** - `8105fed` (test)
2. **Task 1 GREEN: serve canonical headers from Nginx** - `de9a1aa` (fix)
3. **Task 2 RED: require anti-framing negative controls** - `5bc9be6` (test)
4. **Task 2 GREEN: harden the common smoke contract** - `f724d19` (test)
5. **REFACTOR: preserve reviewed secret fixture offsets** - `c0675af` (refactor)

## Files Created/Modified

- `docker/frontend.nginx.conf` - Emits the exact CSP, frame denial, MIME, referrer, and capability headers with `always`.
- `tools/phase2_smoke.sh` - Probes root and deep-link responses from the built frontend, rejects redirects/missing/duplicate/weakened headers, and emits bounded diagnostics.
- `backend/tests/architecture/test_phase2_live_provider_smoke.py` - Freezes the common invocation, two-target runtime contract, canonical values, uniqueness, diagnostics, and negative controls.

## Decisions Made

- Kept the CSP intentionally complete for current SPA assets and API connections while denying base, object, frame source, and frame ancestry authority.
- Put the assertion after frontend readiness in the single common smoke path so base, browser, and worker-loss modes inherit the same built-image proof without another build lifecycle.
- Treated the supported `--gap-closure` interface as the official full-review command after the plan's literal `--mode review --repeat 1 --clean-runs 1` was rejected by the versioned CLI.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Preserved reviewed secret-fixture line identities after adding architecture constants**
- **Found during:** Task 2 final gap-closure gauntlet.
- **Issue:** New module constants shifted the exact line numbers of intentionally seeded secret fixtures, causing the fail-closed secret policy to report unreviewed findings.
- **Fix:** Moved the constants below the reviewed fixtures, preserving the exact existing line identities without weakening the allowlist, detector, or scan scope.
- **Files modified:** `backend/tests/architecture/test_phase2_live_provider_smoke.py`
- **Verification:** Secret policy passed in the fresh 18/18 gauntlet and the complete architecture/provider-spy layer passed 53/53.
- **Committed in:** `c0675af`

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking assurance repair)
**Impact on plan:** The adjustment preserved a pre-existing exact secret-review contract. It changed no production behavior, dependency, package, lockfile, threshold, or security scope.

## Verification

- Focused architecture contract: **16/16 passed**, including in-memory negative controls for common-path removal, deep-link removal, duplicate headers, and weakened CSP/XFO values.
- Backend full suite: **803/803 passed**, total coverage **97%**; frontend full suite: **271/271 passed**.
- Changed-scope coverage: backend **641/641** and frontend **634/634**, both **100%**.
- Type/build quality: mypy, Ruff lint/format, TypeScript, ESLint, Prettier, and the Vite production build passed.
- Mutation: backend detector inventories **129/129 killed** and Stryker polling **30/30 killed**.
- Migrations/OpenAPI: **10/10 passed** and generated client drift check passed.
- Supply chain and secrets: Python audit found no known vulnerabilities, production npm audit found zero vulnerabilities, and secret/license/storage guards passed. The existing dev-only `qs` advisory remains a non-blocking Phase 2 warning.
- Real runtime: base built-image smoke passed; provider audit proved `client_credentials`, exact `repository` scope, five GETs, and zero writes; Playwright passed **8/8**; worker-loss staging and production overlays both passed.
- Gap closure: `bash tools/phase2_gauntlet.sh --gap-closure` passed **18/18 layers** with final source digest `3d07af5efc811a412f85419dd6db10cf6c5804101ff545ae60669795dd020c30` unchanged.
- Cleanup: zero plan containers, networks, volumes, images, or secret files remained. The pre-existing `verboflex-frontend:phase02-27-e2e` and `verboflex-backend:phase02-27-e2e` caches were preserved.
- Dependency integrity: `frontend/package.json` and `frontend/package-lock.json` remained unchanged.

## TDD Gate Compliance

- Task 1 RED `8105fed` failed against the current built image because the CSP header was absent; GREEN `de9a1aa` made the same runtime root/deep probes pass.
- Task 2 RED `5bc9be6` failed first on the missing negative-control validator; GREEN `f724d19` passed the complete focused contract and base smoke.
- REFACTOR `c0675af` preserved the exact reviewed secret-fixture offsets and all gates stayed green.

## Issues Encountered

- The plan's literal final command used unsupported CLI flags (`--mode`, `--repeat`, and `--clean-runs`). The versioned CLI was not broadened; the already prescribed official `--gap-closure` mode ran from zero and passed all 18 layers.
- The development dependency tree retains the existing two moderate `qs` findings through `typed-rest-client`; the production dependency audit is clean and this plan intentionally made no package or lockfile changes.
- Vite retains its existing non-blocking warning for a JavaScript chunk larger than 500 kB.
- The optional external live-provider layer was skipped because it requires explicit opt-in and local credentials; the mandatory isolated mock-provider API/browser proof passed fully.

## User Setup Required

None - no new credentials, provider permissions, package, dependency, or service configuration is required.

## Next Phase Readiness

- CR-13 is closed with runtime evidence from the shipped frontend image and fail-closed regression controls.
- Plan 02-38 can perform the final fresh ASVS review and independent Phase 2 verification.
- WR-03 through WR-07 remain OPEN non-blocking warnings exactly as required.

## Known Stubs

None.

## Authentication Gates

None.

## Threat Surface Review

No unplanned trust boundary was introduced. The only network-facing change is the planned Nginx response-header surface, covered by T-02-43-01 through T-02-43-05 and the built-image runtime smoke.

## Self-Check: PASSED

- All three modified implementation, smoke, and architecture artifacts exist on disk.
- All five RED, GREEN, and refactor commits exist in git history.
- The focused contracts, base smoke, and official 18/18 gap-closure gauntlet completed successfully.
- The tracked implementation tree was clean before summary/tracking updates; only the four explicitly preserved untracked workspace artifacts remain.
- Independent inspection confirmed zero Phase 02-37 plan resources and both preserved Phase 02-27 cache images.

---
*Phase: 02-admin-configuration*
*Completed: 2026-09-01*
