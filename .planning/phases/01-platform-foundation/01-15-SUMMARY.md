---
phase: 01-platform-foundation
plan: 15
subsystem: assurance-and-evidence
tags: [tdd, tier-3, immutable-source, mutation-testing, security-review, evidence]

requires:
  - phase: 01-platform-foundation/01-01..01-14
    provides: Complete Phase 1 platform slice plus source-bound gauntlet and closed security review
provides:
  - Digest-bound final Phase 1 evidence for one unchanged CLOSED source state
  - Three-round append-only Tier 3 verification history with explicit human grading
  - Fail-closed assurance fixes for auth authority, mutation, coverage, lifecycle, and adversarial controls
affects: [phase-2, phase-1-verification, release-security, authentication]

actuals:
  tokens: 52334
  tasks: 2
  commits: 64

tech-stack:
  added: []
  patterns:
    - Evidence is generated outside the canonical source set and published only after a source-specific verifier PASS
    - Every material blind finding is human-graded before an observable RED to minimal GREEN remediation
    - Equivalent mutants require an exact source map, semantic rationale, identical generated SQL, and divergent negative control
    - Final claims bind commit, canonical digest, review digest, layer sequence, external log, and append-only verifier record

key-files:
  created:
    - docs/evidence/phase-01.md
    - .planning/phases/01-platform-foundation/01-VERIFICATION.md
    - tools/equivalent_mutants.txt
    - tools/frontend_coverage_exclusions.txt
    - tools/verify_equivalent_mutants.py
    - tools/verify_rate_limit_boundary_mutant.py
  modified:
    - .planning/phases/01-platform-foundation/01-SPEC.md
    - docs/reviews/phase-01-code-security.md
    - tools/gauntlet.sh
    - backend/src/verboflex/api/v1/routes/auth.py
    - backend/src/verboflex/auth/refresh_sessions.py
    - backend/src/verboflex/core/config.py
    - frontend/src/components/layout/AppShell.tsx

key-decisions:
  - "Keep __Host-verboflex_refresh Secure in every environment, including local development; Microsoft Entra/OIDC remains deferred."
  - "Treat every blind material finding as human-owned classification; behavioural findings require TDD, a new digest, full gauntlet, and fresh verification."
  - "Accept exactly two human-approved join mutants as equivalent only through identical PostgreSQL SQL proof; kill all 891 non-equivalent backend mutants."
  - "Use the single explicitly human-authorized Round 3 exception after Round 2 remediation; no further round is implied or authorized."
  - "Retain VF-SEC-007 as visible Low development-only debt requiring ship-time upgrade or time-bounded acceptance."

patterns-established:
  - "Blind verification: four inputs -> ordered attacks -> append-only freeze -> draft comparison -> source-specific verdict."
  - "Assurance remediation: classify -> RED -> minimal GREEN -> fresh source review/rebind -> candidate gauntlet -> immutable official gauntlet."

requirements-completed: [PLAT-01, PLAT-02, PLAT-03, PLAT-04, PLAT-05, PLAT-06, AUTH-01, AUTH-04, UI-01]

coverage:
  - id: D1
    description: "One immutable CLOSED source state passes all 13 gauntlet layers and immediate digest checks."
    requirement: PLAT-01
    verification:
      - kind: integration
        ref: "tools/gauntlet.sh#PHASE 1 GAUNTLET: PASS"
        status: pass
      - kind: other
        ref: "tools/source_state.sh --verify-final-before-report and --verify-report-digest"
        status: pass
    human_judgment: false
  - id: D2
    description: "A genuinely fresh Tier 3 verifier independently attacks the exact source state before seeing the evidence draft."
    requirement: AUTH-01
    verification:
      - kind: other
        ref: "Round 3 append-only blind record and source-specific verdict passed"
        status: pass
    human_judgment: false
  - id: D3
    description: "The authenticated shell satisfies the approved visual and responsive contract."
    requirement: UI-01
    verification:
      - kind: automated_ui
        ref: "frontend/e2e/auth-shell.spec.ts#desktop/tablet/mobile shell, focus, teardown, and logout"
        status: pass
      - kind: manual_procedural
        ref: "Human visual gate at 1440x900, 768x900, and 375x812"
        status: pass
    human_judgment: true
    rationale: "The user approved the visual hierarchy and personally completed the disposable-password transition."

duration: 18h56min
completed: 2026-08-26
status: complete
---

# Phase 1 Plan 15: Immutable Evidence and Tier 3 Verification Summary

**The internal-auth platform is bound to one unchanged digest with a 13-layer gauntlet, closed security review, and blind fresh-context Tier 3 PASS.**

## Performance

- **Duration:** 18h56min elapsed across review and human-grade checkpoints
- **Started:** 2026-08-25T15:05:57+02:00
- **Completed:** 2026-08-26T10:02:06+02:00
- **Tasks:** 2
- **Files created/modified:** 35 source, test, checker, configuration, review, SPEC, and evidence files
- **Commits:** 64 including evidence and plan metadata

## Accomplishments

- Proved the final CLOSED source state at commit `3a0ea238cf1953fd9e086b2e2eda42a57509f10d`, canonical digest `ed816871a1e6ff21fecb9a7204d3f83db33ebd1772165013ba5abda170a470f9`, through 13/13 official gauntlet layers without source or HEAD drift.
- Completed blind-first Tier 3 verification with exactly four initial inputs, ordered adversarial attacks, append-only records, explicit human grading, and one explicitly authorized third-round exception.
- Strengthened the platform to 268 backend and 75 frontend tests, 100% changed-line branch coverage, 891/891 non-equivalent backend mutants killed plus exactly two proved equivalent, 199/199 backend property mutants, and 153/153 plus 37/37 frontend mutation results.
- Preserved the hardened `__Host-verboflex_refresh` cookie boundary, provider-independent internal accounts/roles, and deliberate deferral of Microsoft Entra/OIDC.

## Task Commits

### Task 1: Run the final unchanged-source gauntlet

- Source contract and Round 1 remediation: `aa43eeb`, `06df146`, `b5f9a14`, `123ec57`, `10d53be`, `5d640ba`, `39598de`, `9df369b`, `60074eb`, `b8ee3b1`, `259cad2`, `6fdf4ca`, `e0da721`, `5e3da41`, `13d0e50`.
- Checker isolation, stale logout authority, and coverage semantics: `7002e0f`, `76697fe`, `01cae15`, `16bb1cc`, `eae77d7`, `2e397c0`, `9fa26a3`, `9224a63`, `8a94244`, `d3d9371`, `2043a94`, `e962a8c`, `927acef`, `48e5ca6`, `c2fa7a6`.
- Scanner/type/browser remediation and source-review rebinds: `a619f57`, `e53fb6e`, `7a430a6`, `b279806`, `e6c88d9`, `25b5c4d`, `7f93715`, `ea99834`, `554ed03`, `3ac757c`, `9f28dd2`, `c642969`, `3087eb4`, `fd107b9`, `ea9e7ef`, `389bb58`.
- Lifecycle and tamper-harness remediation: `596b32c`, `cf98c3a`, `e97e8c8`, `aefc706`, `112af30`, `c1fb597`, `1f1650d`, `5657f91`.
- Round 2 rate/config/SPEC remediation and final review closure: `2c285c1`, `64ef070`, `acdb3ba`, `be96733`, `f4a56e0`, `4d4b171`, `d430965`, `3a0ea23`.

### Task 2: Run blind verifier protocol and finalize digest-bound evidence

- Final evidence: `7b33e59`.
- Plan metadata: committed after this summary and the GSD state updates.

## Final Automated Evidence

- Official `tools/gauntlet.sh`: **PASS**, 13/13 layers, terminal `PHASE 1 GAUNTLET: PASS`.
- Exact source identity: HEAD `3a0ea238...`, canonical digest `ed816871...70f9`, review digest `3b398c710...8084f`; all before/after/immediate-report checks matched.
- Regression/build: backend **268/268**, frontend **75/75**, Playwright **1/1**, 1,948 modules, TypeScript/mypy/Ruff/ESLint/Prettier/build all passed.
- Coverage/mutation: backend **1007/1007** and frontend **157/157** changed lines at 100%; backend **891/891** non-equivalent plus two exact equivalent; property **199/199**; frontend **153/153** and property **37/37**.
- Deployment/adversarial: reversible PostgreSQL migration **3/3**, OpenAPI drift control, dependency/license/secret controls, adversarial auth, real staging smoke, and zero scoped resource residue passed.
- Source/security review: `CLOSED/PASS`, Critical/High/Medium/Low `0/0/0/1`; VF-SEC-007 is the sole open Low dev-only dependency debt.
- Fresh Tier 3 Round 3: **`passed`** for the exact state; frozen-prefix SHA
  `ae149268...01897d`, final append-only record SHA `546ae839...e96de`, zero
  material finding/survivor, canary `not-run/not-applicable`, finalization
  `granted`.

## Decisions Made

- The final evidence is not an input to its own verifier: it remained outside the repo until the blind record was frozen and was compared only afterward.
- Behavioural and description/mapping findings remained distinct. Behavioural changes always invalidated the prior digest; description-only revisions did not invent a behavioural PASS.
- The default two-round cap was exceeded only after explicit human authorization for Round 3, following complete Round 2 disclosure and remediation.
- Refresh-cookie security is an invariant in every environment, not a deployment-only toggle.

## Deviations from Plan

### Human-graded assurance remediations

1. **[Rule 1/2 - Source/checker integrity] Bound Python runtime, made diff coverage and mutation fresh/non-vacuous, proved property attribution, ran packaged controls, and isolated caller-owned layer records.**
2. **[Rule 1/2 - Authentication authority] Revoked all authority on deactivation, keyed logout limits by valid authenticated user, and kept stale credentials peer-bounded.**
3. **[Rule 1/2 - Coverage/mutation adequacy] Added branch-aware Cobertura and exact exclusion controls, killed all non-equivalent auth mutants, and constrained two equivalent joins through identical-SQL proof.**
4. **[Rule 1/2 - UI determinism] Fixed deferred-result typing plus responsive Sheet Escape, focus, teardown, and Tooltip-layer ownership without retries or weakened assertions.**
5. **[Rule 1/2 - Harness cleanup/security] Repaired Celery failure cleanup, byte-level JWT tampering, exact secret-policy line drift, Cobertura parser identity, and real diff-cover output parsing.**
6. **[Rule 1/2 - Round 2 verifier findings] Added a fail-closed continuous-denial rate-limit mutant proof, made Secure cookies mandatory locally, and completed bidirectional SPEC remediation mapping.**

**Total deviations:** 6 grouped human-graded correctness, security, QA, and description/mapping categories.  
**Impact:** Every behavioural change followed RED -> GREEN, source review/rebind, candidate gauntlet, new canonical digest, and full official gauntlet. No threshold, assertion, waiver, or security boundary was weakened.

## Threat Flags

| Flag | File | Description |
| --- | --- | --- |
| threat_flag: authentication-authority | `backend/src/verboflex/api/v1/routes/auth.py` | Account deactivation and logout authority transitions changed; exhaustive state and mutation tests cover revocation and peer isolation. |
| threat_flag: rate-limit-identity | `backend/src/verboflex/auth/refresh_sessions.py` | Logout budget identity now distinguishes valid live user authority from stale/anonymous credentials. |
| threat_flag: cookie-configuration | `backend/src/verboflex/core/config.py` | Refresh cookie security is locked to Secure=true in every environment. |

## Issues Encountered

- Round 1 and Round 2 produced genuine material findings and therefore could not verify the final state. Both frozen append-only records and human grades remain disclosed as history.
- The user explicitly authorized one Round 3 exception after Round 2 remediation. No further verifier round is authorized or claimed.
- One reported cleanup issue could not reproduce under the production command and was human-graded a reviewer false positive; no speculative fix was applied without RED.
- VF-SEC-007 remains visible Low development-only dependency debt and requires ship-time disposition.

## Cleanup

- Official and verifier-owned Compose projects, containers, volumes, images, generated credentials, mutation workspaces, coverage reports, and Celery workers were scoped and removed.
- Raw official and verifier records remain only in private external temporary directories and contain no credential or secret value.
- The pre-existing `.planning/milestone.lock` remains untracked, unmodified, and unstaged.

## Known Stubs

None. No product TODO/FIXME, skipped test, unrun verification, or incomplete UI
data source was introduced. The scan found the historical module description
`Authentication contract stubs` at `backend/src/verboflex/api/v1/routes/auth.py:1`;
the blind verifier classified it as a nonblocking description note because all
routes are implemented and covered, not as an executable stub or deferred defect.

## User Setup Required

None. Phase 1 verification used generated one-run credentials and isolated local infrastructure.

## Next Phase Readiness

- Phase 2 can build on a source-bound FastAPI/React/PostgreSQL/Redis/Celery foundation with internal username/password authentication and provider-independent role authority.
- Microsoft Entra/OIDC remains explicitly deferred; later integration must preserve the internal user/role boundary.
- VF-SEC-007 requires explicit upgrade or time-bounded acceptance before release/ship.

## Self-Check: PASSED

- The evidence exists at `docs/evidence/phase-01.md`, contains the exact
  machine-readable source digest, and `--verify-report-digest` plus
  `--verify-final-before-report` both return zero after its commit.
- All 63 plan implementation/review/evidence commits from `aa43eeb` through
  `7b33e59` exist on `codex/phase-1-platform-foundation`; the final metadata
  commit follows this summary.
- The Round 3 frozen verifier prefix remains byte-identical and its final
  source-specific verdict is `passed`; no source change follows verification.
- No unexpected deletion, generated repository artifact, container, or worker
  residue remains. Only `.planning/milestone.lock` is untracked.

---

*Phase: 01-platform-foundation*  
*Completed: 2026-08-26*
