---
phase: 02-admin-configuration
plan: 22
subsystem: ui
tags: [react, openapi, oauth2, bitbucket, playwright, vitest, tdd]

requires:
  - phase: 02-admin-configuration
    provides: Plan 02-21 backend-only Bitbucket client-credentials authority, bounded status, expiry recovery, and direct connect/reconnect endpoints
provides:
  - Canonical secret-free OpenAPI and generated TypeScript client for direct Bitbucket connect, reconnect, status, and revoke
  - In-SPA administrator connect and expiry-recovery flow with public-status refetch
  - Accessible pending, success, and bounded failure states with DOM, history, storage, and console residue proofs
affects: [phase-02-verification, admin-bitbucket, generated-api-client, browser-security]

actuals:
  tokens: 51431
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Canonical FastAPI export followed by generated-client drift checking
    - Direct server-owned credential mutations followed by public-status refetch
    - Browser security assertions over DOM, route history, storage, and console surfaces

key-files:
  created: []
  modified:
    - backend/tests/api/test_openapi_contract.py
    - frontend/openapi.json
    - frontend/src/api/client/sdk.gen.ts
    - frontend/src/api/client/types.gen.ts
    - frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx
    - frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx
    - frontend/e2e/admin-configuration.spec.ts

key-decisions:
  - "Connect and reconnect are direct generated API mutations that never navigate the browser and always refetch bounded public status after success."
  - "Connection acquisition errors expose one fixed recovery instruction; provider diagnostics and credential-bearing fields remain outside browser-visible state."
  - "Only the active connect or reconnect control is disabled during acquisition; revoke retains its independent confirmation and pending authority."

patterns-established:
  - "Mutation-to-status projection: accept a successful direct mutation only after a generation-guarded public-status refetch."
  - "Secret-free browser proof: exercise recovery without provider credential fixtures and scan DOM, history, storage, and console for forbidden surfaces."

requirements-completed: [BITB-01, BITB-03, BITB-04, UI-03]

coverage:
  - id: D1
    description: "The canonical browser contract exposes direct Bitbucket connect, reconnect, status, and revoke with expiry metadata and no callback, authorization URL, workspace, or credential-bearing type."
    requirement: BITB-01
    verification:
      - kind: integration
        ref: "backend/tests/api/test_openapi_contract.py + frontend/src/api/admin-client-contract.test.ts"
        status: pass
      - kind: other
        ref: "frontend npm run api:check"
        status: pass
    human_judgment: false
  - id: D2
    description: "Administrators connect, observe expiry-driven reauthorization, recover through direct reconnect, and remain on the same SPA location."
    requirement: BITB-03
    verification:
      - kind: unit
        ref: "frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx#direct mutation and recovery cases"
        status: pass
      - kind: e2e
        ref: "frontend/e2e/admin-configuration.spec.ts#Bitbucket client credentials recover expiry without navigation or credential residue"
        status: pass
    human_judgment: false
  - id: D3
    description: "Connect and recovery publish accessible pending, recovered, and bounded-error states without credential-bearing DOM, history, storage, console, or browser route artifacts."
    requirement: UI-03
    verification:
      - kind: unit
        ref: "frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx#pending and bounded recovery cases"
        status: pass
      - kind: automated_ui
        ref: "playwright --grep Bitbucket client credentials"
        status: pass
    human_judgment: false

duration: 19min
completed: 2026-08-29
status: complete
---

# Phase 02 Plan 22: Secret-Free Bitbucket Browser Recovery Summary

**The administrator browser now uses the exact backend-only client-credentials contract for direct Bitbucket connection and expiry recovery, without navigation or provider credential surfaces.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-08-29T15:26:49Z
- **Completed:** 2026-08-29T15:45:33Z
- **Tasks:** 2
- **Files modified:** 9
- **Actual estimate scale:** 51,431 tokens (205,722 realized diff characters / 4)

## Accomplishments

- Regenerated and pinned a direct connect/reconnect/status/revoke browser contract with exact expiry and recovery status fields and no callback, authorization URL, workspace, provider credential, or ciphertext surface.
- Replaced callback navigation with generated direct mutations that stay inside the SPA, prevent duplicate submission, and refetch bounded public status before announcing success.
- Proved disconnected, connected, reauthorization-required, unavailable, pending, bounded-error, and recovered browser states with exact repository scope and expiry metadata.
- Removed provider credential material from the Playwright Bitbucket fixture and verified no forbidden surface enters DOM, route history, storage, or console output.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: secret-free generated contract specification** — `d22f259` (test)
2. **Task 1 GREEN: regenerated direct Bitbucket admin client** — `c5370ef` (feat)
3. **Task 2 RED: direct browser recovery specification** — `5d6063e` (test)
4. **Task 2 GREEN: in-SPA connect and recovery UI** — `2ed7d22` (feat)

Plan metadata is committed separately with this summary and synchronized planning state.

## TDD Gate Evidence

- **Task 1 RED:** backend OpenAPI drift failed against the stale checked-in schema, while the frontend contract failed four of seven assertions for the obsolete authorization response, missing direct path/export, and stale operation map.
- **Task 1 GREEN:** backend OpenAPI passed 11/11, the frontend contract passed 7/7, and a second canonical generation was byte-stable.
- **Task 2 RED:** focused Vitest failed four of eleven direct-mutation, accessible-pending, active-button, and bounded-recovery assertions; Playwright could not reach the removed callback/start-based page contract.
- **Task 2 GREEN:** the unchanged focused suite passed 11/11 and the named Playwright client-credentials journey passed 1/1.
- No refactor commit was needed; the GREEN implementations already retained the established request-generation and component boundaries.

## Acceptance Evidence

- Exact Task 1 command: **11 backend tests passed, 7 frontend tests passed, API generation drift check passed**.
- Exact Task 2 command: **11 focused Vitest tests passed, 1 named Playwright journey passed**.
- Canonical `npm run api:check`: **pass**, leaving `frontend/openapi.json` and `frontend/src/api/client` unchanged.
- Frontend TypeScript, ESLint, and production Vite build: **pass**.
- Source assertions confirm direct connect/reconnect/status exports and no start/callback operation.
- Browser assertions confirm one request per action, stable location/history, exact repository scope and expiry, and bounded recovery after controlled failure.

## Files Created/Modified

- `backend/tests/api/test_openapi_contract.py` — exact direct-operation, public-shape, and forbidden-surface schema assertions.
- `frontend/openapi.json` — canonical FastAPI export for the backend-only connection authority.
- `frontend/src/api/client/index.ts` — generator-owned direct operation and response barrel exports.
- `frontend/src/api/client/sdk.gen.ts` — generated direct connect and reconnect operations.
- `frontend/src/api/client/types.gen.ts` — generated bounded status/expiry and direct operation response types.
- `frontend/src/api/admin-client-contract.test.ts` — operation, schema, generated-export, and credential-surface contract tests.
- `frontend/src/features/admin/bitbucket/BitbucketConnectionPage.tsx` — direct mutations, accessible pending/result projection, safe recovery copy, and status refetch.
- `frontend/src/features/admin/bitbucket/BitbucketConnectionPage.test.tsx` — loading, status, direct mutation, expiry, recovery, revoke, and residue regression suite.
- `frontend/e2e/admin-configuration.spec.ts` — direct endpoint fixture and named responsive expiry/failure/recovery browser journey.

## Decisions Made

- Kept all credential acquisition backend-owned: the browser sends only the authenticated direct mutation and consumes the six-field public status response.
- Required a public-status refetch after mutation success rather than trusting mutation data as the lasting UI authority.
- Kept revoke independently actionable during connect/reconnect pending state, matching the requirement to disable only the active mutation control.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Scoped the generated credential-surface assertion to Bitbucket aliases**
- **Found during:** Task 1 GREEN
- **Issue:** A raw scan of the complete generated types file matched unrelated first-party authentication and repository schemas, producing false positives outside the public Bitbucket contract.
- **Fix:** Parsed TypeScript aliases and applied the forbidden-property assertion only to aliases prefixed `AdminBitbucket`, without weakening exact OpenAPI or generated export checks.
- **Files modified:** `frontend/src/api/admin-client-contract.test.ts`
- **Verification:** Frontend contract 7/7 and canonical API drift check passed.
- **Committed in:** `c5370ef`

**2. [Rule 3 - Blocking] Included the generator-owned client barrel**
- **Found during:** Task 1 GREEN
- **Issue:** The plan's file list omitted `frontend/src/api/client/index.ts`, but the canonical generator must update that barrel for the new direct exports.
- **Fix:** Accepted only the canonical `npm run api:generate` output and verified a second generation was byte-stable; no generated file was hand-edited.
- **Files modified:** `frontend/src/api/client/index.ts`
- **Verification:** `npm run api:check` passed with no generated diff.
- **Committed in:** `c5370ef`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking generated-artifact consistency issue)
**Impact on plan:** Both fixes preserve exact security scope and deterministic generation; no product scope was added.

## Issues Encountered

- The service already bound to localhost port 8080 served a stale frontend during the RED browser run. A task-scoped Vite runtime on port 4177 provided the current source for deterministic RED/GREEN Playwright evidence and was stopped after verification.
- The production build retains the existing Vite advisory for a JavaScript chunk above 500 kB; the build exits successfully and this plan did not introduce a new dependency or chunking boundary.

## Authentication Gates

None.

## Known Stubs

None.

## Threat Flags

None - all changed trust-boundary surfaces are covered by the plan's OpenAPI-to-client and administrator-browser threat register.

## User Setup Required

None - no external configuration, dependency, or provider credential is required for this browser/client update.

## Next Phase Readiness

- CR-03, CR-04, and G3 browser gaps are closed with drift-checked generated artifacts and automated SPA recovery evidence.
- `BITB-01`, `BITB-03`, `BITB-04`, and `UI-03` can advance when the requirements ledger confirms no later incomplete plan still declares them.
- Ready for Plan 02-24 and the remaining Phase 2 gap-closure sequence.

## Self-Check: PASSED

- All nine implementation/test artifacts and this summary exist.
- All four TDD commits exist in RED → GREEN → RED → GREEN order.
- Coverage metadata validates with three fully automated deliverables and no schema errors.
- Required OpenAPI, generated-client, focused Vitest, Playwright, lint, type, and production-build checks pass.
- No tracked deletion, dependency change, stub, skipped test, unrun verification, or unmodeled threat surface remains.

---
*Phase: 02-admin-configuration*
*Completed: 2026-08-29*
