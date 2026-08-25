---
phase: 01-platform-foundation
plan: 14
subsystem: assurance-and-security
tags: [tdd, tier-3, mutation-testing, docker-compose, owasp-asvs, auth, source-digest, smoke]

requires:
  - phase: 01-platform-foundation/01-02..01-13
    provides: Complete separated FastAPI/React platform, internal authentication, PostgreSQL, Redis/Celery, generated client, and authenticated shell
provides:
  - Fail-closed immutable-source Tier 3 gauntlet with executable negative controls
  - Deployment-like Docker smoke and adversarial authentication proof with exact cleanup
  - Closed fresh-context OWASP ASVS-oriented review bound to an unchanged reviewed source digest
  - Complete backend and frontend mutation proof with zero non-equivalent survivors
affects: [01-15-final-evidence, phase-1-verification, release-security, authentication]

actuals:
  tokens: 97538
  tasks: 3
  commits: 83

tech-stack:
  added:
    - mutmut 3.7.0
    - Stryker 9.5.1 with Vitest runner
    - diff-cover, detect-secrets, pip-audit, and pip-licenses gate integration
  patterns:
    - Canonical sorted path/content digests distinguish review source from the self-referential closed artifact
    - Default gauntlet requires CLOSED/PASS while post-fix candidate mode accepts only OPEN/PENDING with zero open Critical/High
    - Every custom gate carries a restored negative control and propagates its first non-zero result
    - Security review fixes invalidate the candidate digest and repeat review plus the complete gauntlet

key-files:
  created:
    - tools/source_manifest.txt
    - tools/source_state.sh
    - tools/gauntlet.sh
    - tools/real_smoke.sh
    - tools/adversarial_auth.sh
    - tools/tests/test_source_state.sh
    - tools/tests/test_gauntlet.sh
    - tools/tests/test_real_smoke.sh
    - tools/tests/test_adversarial_auth.sh
    - docs/phase-01-smoke.md
    - docs/reviews/phase-01-code-security.md
    - frontend/stryker.config.mjs
  modified:
    - backend/pyproject.toml
    - frontend/package.json
    - frontend/package-lock.json
    - docker-compose.yml
    - backend/src/verboflex/auth/refresh_sessions.py
    - backend/src/verboflex/auth/rate_limits.py
    - backend/src/verboflex/api/v1/routes/auth.py
    - backend/src/verboflex/schemas/auth.py
    - frontend/src/features/auth/session.tsx

key-decisions:
  - "Use a non-self-referential review digest for the blind review and a separate canonical digest that includes the closed review artifact."
  - "Keep the default gauntlet fail-closed on CLOSED/PASS; expose a separate post-fix candidate mode that cannot claim final success."
  - "Treat every non-Killed backend mutation verdict and every frontend score below 100 as failure; equivalent mutants are removed through behavior-preserving refactors rather than ignored."
  - "Bind every accepted detect-secrets false positive to exact path, line, plugin, and hashed fingerprint; additions or drift fail closed."
  - "Retain VF-SEC-007 as visible Low dev-only debt requiring upgrade or time-bounded acceptance before ship."

patterns-established:
  - "Review lifecycle: fresh OPEN candidate -> unchanged-source full candidate gauntlet -> independent closure -> canonical digest -> official CLOSED gauntlet."
  - "Real smoke owns generated credentials, exact Compose project/image names, bounded readiness, and trap-based removal of containers, volumes, images, workers, and secret files."
  - "Refresh authority uses an exact __Host-verboflex_refresh cookie and logout revokes every member of its durable server-owned family."

requirements-completed: [PLAT-01, PLAT-02, PLAT-03, PLAT-04, PLAT-05, PLAT-06, AUTH-01, AUTH-04, UI-01]

coverage:
  - id: D1
    description: "One fail-closed command proves the complete Phase 1 Tier 3 stack against one unchanged canonical source state."
    requirement: PLAT-01
    verification:
      - kind: integration
        ref: "bash tools/gauntlet.sh#PHASE 1 GAUNTLET: PASS"
        status: pass
      - kind: unit
        ref: "tools/tests/test_source_state.sh and tools/tests/test_gauntlet.sh"
        status: pass
    human_judgment: false
  - id: D2
    description: "The deployment-like stack proves migrations, bootstrap, login/change/login/refresh/me/status/logout, Celery result 5, browser shell, and hostile authentication behavior."
    requirement: PLAT-06
    verification:
      - kind: e2e
        ref: "tools/real_smoke.sh and tools/adversarial_auth.sh#real staging smoke: PASS"
        status: pass
      - kind: automated_ui
        ref: "frontend/e2e/auth-shell.spec.ts#auth shell completes forced change, refresh, responsive navigation, and logout"
        status: pass
    human_judgment: false
  - id: D3
    description: "A genuinely fresh reviewer closed the OWASP ASVS-oriented authentication/security gate on the exact reviewed source with no open Critical, High, or Medium finding."
    requirement: AUTH-01
    verification:
      - kind: other
        ref: "docs/reviews/phase-01-code-security.md#Review-status CLOSED and Full-gauntlet-status PASS"
        status: pass
      - kind: integration
        ref: "tools/source_state.sh --verify-review-closed and --verify-review-source"
        status: pass
    human_judgment: false

duration: 4h45min
completed: 2026-08-25
status: complete
---

# Phase 1 Plan 14: Tier 3 Gauntlet and Security Review Summary

**A source-bound Tier 3 gauntlet now proves the complete internal-auth platform, hostile paths, deployment smoke, 932 killed mutants, and a closed fresh-context ASVS review.**

## Performance

- **Duration:** 4h45min
- **Started:** 2026-08-25T09:04:38+02:00
- **Completed:** 2026-08-25T13:49:00+02:00
- **Tasks:** 3
- **Files created/modified:** 64 implementation, test, harness, configuration, and review files
- **Implementation/review commits:** 82

## Accomplishments

- Built a deterministic source manifest and source-state checker that proves required categories, distinguishes review/canonical digests, rejects dirty or missing inputs, and prevents an OPEN candidate from masquerading as a final closed review.
- Built the ordered fail-closed gauntlet for randomized tests, types, format/lint/complexity, 100% changed-line coverage, backend/frontend mutation, property suites, reversible migrations, OpenAPI drift, secret/dependency/license audits, real Docker smoke, adversarial auth, browser E2E, and final source identity.
- Proved the real staging lifecycle twice in the final workflow, including migrations, non-echoed bootstrap, temporary login, mandatory password change, ordinary login, refresh, me/status, Celery result 5, full-family logout, hostile tokens/origin/replay/concurrency/limits/outage, browser storage/viewports/logout, and exact resource cleanup.
- Closed a genuinely fresh-context OWASP ASVS-oriented review with C/H/M/L `0/0/0/1`, no open Critical/High/Medium, and every historical Medium finding resolved through observable RED then GREEN.
- Achieved backend mutation `779 killed / 0 survived / 0 timeout / 0 error / 0 untested` and frontend mutation `153 killed / 0 survived / 0 timeout / 0 no-coverage / 0 error`, score 100%.

## Task Commits

### Task 1: Fail-closed source, coverage, mutation, drift, and secret gates

- Initial checker RED/GREEN: `5dedba7`, `fc3f9e2`.
- Source/closure/OpenAPI/adversarial negative controls and fixes: `73ccbaa`, `ec62826`, `671168d`, `3dff501`, `578a65f`, `3af062e`, `a70b671`, `846bef5`, `e202e39`, `49377ae`.
- Mutation scope, freshness, package/migration workspace, verdict, and survivor-killing cycles: `aa169c0`, `71b5ef6`, `695bafa`, `865f79d`, `a649a2d`, `249ca9e`, `21d7672`, `73dc25a`, `c21e189`, `9d4406e`, `69a6658`, `c0eece4`, `c04a3ce`, `a737fcf`, `48d7bef`, `a8793c9`, `c065c28`, `8cb6987`, `4b6a322`, `f635d7f`, `040adf4`, `4da71a8`, `862268d`, `9d739ba`, `fb54b66`, `0f9c0ba`, `59eedb5`, `9cdadc8`, `0fec1f8`, `f6bfc7e`.
- Static fail-fast, formatting, and exact secret audit RED/GREEN: `fe115f8`, `fbeac3c`, `a19872d`, `8f5730e`, `ccbb883`.

### Task 2: Staging stack and hostile authentication proof

- Initial smoke/adversarial RED/GREEN: `ac6efe3`, `1d8a397`.
- TLS boundary, post-fix mode, test-infrastructure lifecycle, and deterministic frontend format: `1bb45ff`, `7370924`, `186318e`, `2b24091`, `af031eb`, `76b00c7`, `042eaf5`, `aeb967d`.
- Cookie, logout-family, and real-smoke proof cycles: `3360355`, `950743a`, `987a4cc`, `ebeb608`, `321b3db`, `569f832`, `fc63c2b`, `9c0a681`, `4238dea`, `9f38f9b`.

### Task 3: Fresh-context code/security review and revision gate

- Review artifacts and independent candidate checkpoints: `d376b6f`, `1945cb4`, `aea1141`, `f8b7850`, `01b11e7`, `d287313`, `d83e8e9`, `14e32f5`.
- Review-driven coverage/rate/input TDD cycles: `56b3d78`, `37083c0`, `5a7b1eb`, `3a44df5`, `f4b9777`, `b8b8053`.
- Independent closure after the unchanged-source full candidate gauntlet: `b3d1698`.

**Plan metadata:** final documentation commit follows this summary.

## Final Automated Evidence

- Official default `bash tools/gauntlet.sh`: **`PHASE 1 GAUNTLET: PASS`** on canonical CLOSED digest `3552de3da32987f16dbb2c0b1a4681a103e3a9d533c273ec2c96c36dac4c8584`.
- Non-self-referential reviewed-source digest: `60658f82cd814c9180a9a2bb9db1da90a82cb23620c8ee5d2705e33bc969c5bc`, reproduced twice before review and again after closure.
- Backend regression: **251/251**; backend changed-line coverage **973/973, 100%**; mypy, Ruff check/format, and Radon all passed.
- Frontend regression: **72/72**; TypeScript, ESLint, Prettier, Vite build, diff coverage, and Playwright **1/1** all passed.
- Mutation/property: mutmut **779/779 killed**, Stryker **153/153 killed at 100%**, backend property selection **71 passed**, frontend property suite **3 passed**.
- Migration rehearsal **3/3**; OpenAPI controlled RED and byte-identical generation GREEN; detect-secrets true-key and exact-policy negative controls plus exact 23-row repository scan passed.
- Backend dependency audit found no published-package vulnerability; frontend runtime dependency audit was clean. The complete development tree retains only the documented `VF-SEC-007` advisory.
- Fresh reviewer artifact: `CLOSED`, full gauntlet `PASS`, C/H/M/L `0/0/0/1`, open Critical/High `0`, closure verdict `PASS_WITH_LOW_DEV_ONLY_DEBT`.

## Security and API Outcomes

- The refresh cookie is exactly `__Host-verboflex_refresh`, always `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, and has no `Domain`; set and delete scopes match and no legacy cookie is emitted.
- Logout revokes the complete durable refresh family; real smoke proves both the pre-rotation token A1 and successor A2 return exact 401 after logout.
- Refresh rate limits use stable server-owned family plus validated peer IP, collapse invalid authority to a bounded sentinel, run before rotation, and preserve exact 429/503 behavior.
- OAuth2 form and password-change fields have bounded runtime/OpenAPI maxima and oversized requests return 422 before Redis, Argon2, bearer decoding, or durable mutation.
- The seven-operation HTTP surface remains compatibility-checked through canonical OpenAPI generation; no undocumented route or response contract was introduced.
- All 23 detect-secrets findings were independently classified as exact false positives. The source-bound policy records `path|line|plugin|hashed-fingerprint`; there is no blanket exclusion or accepted real secret.

### Fresh-review finding matrix

| Finding | Final state | Verified disposition |
| --- | --- | --- |
| VF-SEC-001 | RESOLVED Medium | Canonical manifest covers every required source category and fails on empty/missing/dirty/error states. |
| VF-SEC-002 | RESOLVED Medium | Candidate and final review metadata are single-valued, source-bound, and enforced as distinct OPEN/PENDING versus CLOSED/PASS states. |
| VF-SEC-003 | RESOLVED Medium | Executable OpenAPI negative control restores its mutation before the byte-identical generated-client check. |
| VF-SEC-004 | RESOLVED Medium | Smoke credentials/resources are private, generated, bounded, non-echoed, and removed by exact project cleanup. |
| VF-SEC-005 | RESOLVED Medium | Complete handwritten backend/frontend auth-session mutation scope killed 779+153 mutants with zero other verdict. |
| VF-SEC-006 | RESOLVED Medium | App ports are loopback-only and the source-bound runbook defines the managed TLS/HSTS deployment edge. |
| VF-SEC-007 | OPEN Low | Dev-only `typed-rest-client -> qs` advisory is absent from runtime and requires ship-time upgrade or time-bounded acceptance. |
| VF-SEC-008 | RESOLVED Medium | Exact `__Host-verboflex_refresh` set/delete contract: Secure, HttpOnly, SameSite=Lax, Path=/, no Domain, no legacy emission. |
| VF-SEC-009 | RESOLVED Medium | Logout revokes the complete durable refresh family; A1 and A2 both return 401 afterward. |
| VF-SEC-010 | RESOLVED Medium | Refresh limiter uses stable family+peer or bounded invalid sentinel before rotation and fails closed on Redis errors. |
| VF-SEC-011 | RESOLVED Medium | OAuth/password inputs carry exact runtime/OpenAPI maxima and oversize requests fail before Redis/Argon2/durable work. |

## Decisions Made

- The review artifact cannot hash itself: reviewers bind to the review digest, while the official final command binds the complete CLOSED artifact through a separate canonical digest.
- `--post-fix-candidate` is explicitly non-final and requires OPEN/PENDING candidate metadata; the default command remains fail-closed on CLOSED/PASS.
- Mutation quality is binary for the handwritten auth/session scope: every non-equivalent mutant must be killed, with no score waiver, ignored mutation, or stale-result reuse.
- TLS termination remains an explicit managed-edge boundary for local repository infrastructure; the runbook requires trusted TLS 1.2/1.3, redirect/unreachability, HSTS, hostname/certificate validation, and loopback-only forwarding.

## Deviations from Plan

### Auto-fixed Issues

1. **[Rule 1 - Checker bugs] Closed source-state and ordered-gate fail-open paths.** Empty exclusion results, silently empty manifest rules, incomplete frontend source inclusion, candidate/final review confusion, OpenAPI controls, duplicate staging execution, Ruff format propagation, and stale mutation results each received an observable failing checker test before the fix.
2. **[Rule 2 - Missing security proof] Expanded mutation to the complete handwritten auth/session state.** Backend scope now covers nine auth modules and frontend scope covers `session.tsx`; equivalent mutants were removed through behavior-preserving refactors and all logical/output survivors received targeted tests.
3. **[Rule 2 - Authentication hardening] Resolved strict cookie and logout-family findings.** The generic refresh cookie became an exact host-only `__Host-` cookie and logout now revokes the entire durable family, with set/delete and A1/A2 smoke proofs.
4. **[Rule 1 - Authority/rate bugs] Removed rotating-token limiter bypass and bounded credential work.** Refresh identity now derives from stable family plus peer; invalid tokens share a bounded sentinel; request maxima reject oversized OAuth/password data before Redis/Argon2/durable work.
5. **[Rule 2 - Audit correctness] Replaced count-only secret acceptance with exact source-bound dispositions.** The fresh reviewer independently classified 23/23 detections as false positives; a real key fixture and any unreviewed tuple still fail.

**Total deviations:** 5 grouped auto-fixed correctness/security categories (Rules 1-2).  
**Impact:** All changes directly close plan-owned security/reliability gaps and strengthen, never weaken, the approved thresholds.

## Issues Encountered

- Early complete gauntlet rounds intentionally stopped at the first real failure: missing checker contracts, incomplete mutation scope, survivors/equivalent mutants, cookie/logout/rate/input findings, backend coverage gaps, Ruff drift, and an outdated count-only secret map. Each round was classified before a separate RED→GREEN correction and a new source digest/review cycle.
- The final complete npm development audit reports GHSA-q8mj-m7cp-5q26 only through `typed-rest-client -> qs`. It is absent from the runtime dependency tree and remains the explicit Open Low `VF-SEC-007`; it must be upgraded or time-bound accepted before ship.
- Source-state commands print a harmless warning for the not-yet-created excluded `docs/evidence/` directory; category resolution, digest equality, candidate/closure contracts, and both final source checks still pass. Plan 01-15 owns evidence creation.

## Cleanup

- Candidate projects `verboflex_phase01_smoke_8378_1787657687` and `verboflex_phase01_smoke_9118_1787657860` were removed with containers, volumes, images, and workers all at zero.
- Official projects `verboflex_phase01_smoke_23585_1787658169` and `verboflex_phase01_smoke_24332_1787658342` were removed with containers, volumes, images, and workers all at zero.
- Generated passwords, environment files, mutation workspaces, Playwright output, coverage reports, and scanner reports lived only in private temporary paths and were removed or overwritten outside the repository.

## Known Stubs

None. The realized diff contains no product stub, TODO/FIXME, skipped test, or unrun verification. Empty collections and strings introduced by the plan are bounded test probes, cleanup sentinels, or the optional OAuth2 `scope` default; none flows to an unfinished UI.

## User Setup Required

None. All proof used local isolated resources and disposable generated credentials.

## Next Phase Readiness

- Plan 01-15 can consume the CLOSED review, reviewed-source digest, canonical digest, and official all-layer PASS to create the final immutable evidence and independent-verifier handoff.
- `VF-SEC-007` remains visible and nonblocking for this phase but is a mandatory ship-time disposition; any runtime reachability, severity increase, or additional advisory makes it blocking.
- The unrelated untracked `.planning/milestone.lock` remains preserved and untouched.

## Self-Check: PASSED

- All 64 realized implementation/test/harness/review paths exist in the final committed source or are intentional modifications of tracked files.
- All 82 implementation and reviewer commits from `5dedba7` through `b3d1698` exist on `codex/phase-1-platform-foundation`.
- The review is `CLOSED/PASS`, both source-state review verifiers return zero, the official default gauntlet passed, and cleanup counts are zero.
- No unexpected tracked deletion, generated untracked artifact, or source drift remains; only `.planning/milestone.lock` is untracked.

---

*Phase: 01-platform-foundation*  
*Completed: 2026-08-25*
