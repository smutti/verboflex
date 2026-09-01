---
phase: 02-admin-configuration
verified: 2026-09-01T09:41:51Z
verification_date: 2026-09-01
status: gaps_found
score: "5/8 roadmap success criteria verified"
behavior_unverified: 0
overrides_applied: 0
head: a1fd9afdd2896e74e5f2e6cb327670833d234924
inventories:
  phase_goal: "0/1 achieved"
  roadmap_success_criteria: "5/8 verified"
  requirements: "13/15 satisfied"
  context_decisions: "23/23 honored (non-blocking decision gate)"
  prohibitions: "9/9 remain test-enforced"
  review_rows: "23/23 adjudicated (15 closed, 2 blockers open, 6 warnings open)"
review:
  status: issues_found
  critical: 2
  warning: 6
  info: 0
  open_blockers: [CR-14, CR-15]
  open_warnings: [WR-03, WR-04, WR-05, WR-06, WR-07, WR-08]
re_verification:
  previous_status: passed
  previous_score: "8/8"
  gaps_closed: []
  gaps_remaining:
    - "CR-14: preview commit resolution truncates valid configured branches after the first 100"
    - "CR-15: ordinary React Router navigation can discard dirty product and mapping forms"
  regressions:
    - "The execute:post review found two current-code blockers that the prior verification inventory did not include."
gaps:
  - truth: "Every valid configured source branch can be resolved to an exact commit and used for candidate or active-revision preview validation."
    status: failed
    reason: "ProductPreviewPage.resolveCommits requests only cursor=null, limit=100 and searches that page locally, although the mapping workflow accepts branch 101+ through the exact branch endpoint."
    artifacts:
      - path: "frontend/src/features/admin/previews/ProductPreviewPage.tsx"
        issue: "resolveCommits never calls getAdminRepositoryBranch and throws when the configured branch is absent from page one."
      - path: "frontend/src/features/admin/previews/ProductPreviewPage.test.tsx"
        issue: "The commit-resolution test asserts the truncated first-page request and has no branch-101 preview regression."
    missing:
      - "Resolve each configured direct, keys, and translations branch through getAdminRepositoryBranch and require the returned exact name."
      - "Add candidate and active-revalidation regressions where branch 101 is absent from page one but the exact detail read succeeds."
  - truth: "Leaving any dirty product or mapping form is blocked before SPA navigation and requires the named Keep editing or Discard changes decision."
    status: failed
    reason: "The product wizard listens only for beforeunload and popstate, React Router Links can unmount it without either event, and ProductMappingsPage has no dirty-navigation guard."
    artifacts:
      - path: "frontend/src/features/admin/products/ProductWizardPage.tsx"
        issue: "The current listener runs after popstate and does not intercept Link/pushState navigation before unmount."
      - path: "frontend/src/components/layout/AppShell.tsx"
        issue: "RoutedDestination follows Link immediately and has no blocker handshake with the dirty form."
      - path: "frontend/src/features/admin/mappings/ProductMappingsPage.tsx"
        issue: "Mapping form state is mutable but no route or document-exit guard is registered."
    missing:
      - "Introduce a router-native navigation blocker shared by product and mapping forms while retaining beforeunload for document exits."
      - "Use the named Alert Dialog, preserve values and focus on Keep editing, and proceed only after Discard changes."
      - "Add real-router tests that click shell and product-detail links from both dirty forms and exercise both choices."
---

# Phase 2: Admin Configuration Verification Report

**Phase Goal:** Deliver an administrator-only control plane for internal users, versioned products, reusable repositories, one-format mappings, a single organizational Bitbucket OAuth connection, and live read-only validation previews.
**Verified:** 2026-09-01T09:41:51Z
**Status:** `gaps_found`
**Re-verification:** Fresh goal-backward reassessment after the execute:post review. The prior `passed` report had no `gaps:` section, so its claims were treated as historical inventory rather than evidence.

## Verdict

Phase 2 is **not complete at the current repository state**. Five of eight roadmap success criteria remain verified, but two independently confirmed product defects block the preview and admin-UX contracts, and the required critical-zero quality gate consequently fails.

- **CR-14:** a mapping may validly select branch 101 through the exact provider lookup, but preview commit resolution searches only the first 100-item page and fails before candidate validation or active-revision revalidation starts.
- **CR-15:** ordinary React Router navigation can unmount dirty product forms without confirmation; mapping forms have no dirty-exit guard at all.
- **SC-08:** the fresh review reports `critical: 2`, so the phase quality gate cannot pass until both blockers are fixed and reviewed again.

The six open warnings remain visible but do not independently determine the `gaps_found` status. No override applies, and neither blocker is explicitly deferred by a later roadmap phase.

## Source and Evidence Freshness

| Authority | Result |
|---|---|
| Current HEAD | `a1fd9afdd2896e74e5f2e6cb327670833d234924` |
| Fresh execute:post review | `02-REVIEW.md`, reviewed 2026-09-01, `critical: 2`, `warning: 6`, `status: issues_found` |
| Reviewed source head | `99d2d0af5dfb27cc3ef47590f480ae7a33cf4d94`; no backend/frontend/tools/docker production diff exists from that head to current HEAD |
| Prior verification head | `43e4bb7c1e89d09affa8f0a1868ff088acc98224`; no Phase 2 production diff exists from that head to current HEAD |
| Phase 1 regression gate | Effective backend 284/284 and frontend 96/96; the first backend run's two failures were reproduced as missing Redis/worker infrastructure and the full worker file passed 4/4 with disposable Redis plus a distinct Celery worker |
| Independent focused checks | Preview commit-resolution test 1/1 PASS; mapping branch-101 test 1/1 PASS. Their combined call traces expose CR-14 rather than disproving it. |

## Goal Achievement

### Roadmap Success Criteria

| # | Roadmap contract | Status | Current code and behavioral evidence |
|---|---|---|---|
| SC-01 | Complete reversible internal-user lifecycle with multiple roles, one-time credentials, and last-active-admin safety | ✓ VERIFIED | Shared `ADMIN_AUTHORITY_LOCK_KEY`, survivor predicate, common HTTP/CLI transitions, and unchanged passing concurrency/lifecycle evidence remain present. |
| SC-02 | Candidate product changes remain isolated until atomic publication | ✓ VERIFIED | Complete fresh-ID graph clone, published-child immutability, and locked atomic identity promotion remain substantive and wired. |
| SC-03 | Global repositories are reusable while branches, mappings, and preview state remain product/revision-specific | ✓ VERIFIED | Global normalized repository identity and revision-owned mapping/preview rows remain isolated by model/service/database ownership. |
| SC-04 | One exact-scope organizational Bitbucket connection powers live branch listing and read-only source access | ✓ VERIFIED | Client-credentials-only exact `repository` scope, encrypted access-only generation, GET-only adapter, branch listing, and source reads remain wired. |
| SC-05 | Each mapping has one format/layout, source branch, allowed/default targets, and fixed repository+target grouping | ✓ VERIFIED | Direct/separate schemas and services enforce one exact mapping identity; exact branch 101 restoration proves valid mappings can extend beyond page one. |
| SC-06 | Four-format bounded preview works and fails closed only for invalid, ambiguous, stale, disconnected, or bounded terminal states | ✗ FAILED | `resolveCommits` at `ProductPreviewPage.tsx:228-237` rejects a valid configured branch merely because it is outside the first 100-item page. |
| SC-07 | Guided shadcn admin screens expose actionable, data-safe form and lifecycle states | ✗ FAILED | The UI-SPEC requires `Leave without saving?` before leaving dirty forms; Router Links bypass the product listener and mappings have no guard. |
| SC-08 | TDD, review, backend/frontend/worker, and deployment quality gate closes cleanly | ✗ FAILED | Fresh review has two open Critical findings. Passing suites do not cover the branch-101 preview or real Router-Link dirty-form transitions. |

**Roadmap score:** 5/8 verified; 0 present-but-behavior-unverified.

## Requirements Coverage

All 15 Phase 2 IDs appear in plan frontmatter; there are no orphaned Phase 2 requirements. Checkboxes in `REQUIREMENTS.md` were not used as evidence.

| Requirement | Status | Evidence / blocker |
|---|---|---|
| AUTH-02 | ✓ SATISFIED | Guarded list/create/update/reset/deactivate/reactivate authority remains wired. |
| AUTH-03 | ✓ SATISFIED | Fixed additive role sets and last-active-admin invariants remain enforced. |
| PROD-01 | ✓ SATISFIED | Versioned create/edit/lifecycle API and candidate isolation remain operational. |
| PROD-02 | ✓ SATISFIED | Reusable credential-free repository registry remains product-independent. |
| PROD-03 | ✓ SATISFIED | Mapping UI/API stores exact source branches, including an exact configured branch outside page one. |
| PROD-04 | ✓ SATISFIED | Allowed targets and contained default target remain validated. |
| PROD-05 | ✓ SATISFIED | PR grouping remains exact repository UUID plus target branch. |
| PROD-06 | ✓ SATISFIED | Direct/separate topology remains closed and validated. |
| PROD-07 | ✓ SATISFIED | Separate Keys/Translations sides remain explicit and revision-owned. |
| PROD-08 | ✗ BLOCKED | A valid branch 101 mapping cannot start preview validation because the frontend cannot resolve its commit. |
| PROD-09 | ✓ SATISFIED | Successful preview still selects exactly one detected format/layout and ambiguity fails closed. |
| BITB-01 | ✓ SATISFIED | Connect/reconnect/revoke/bounded status use the single client-credentials connection. |
| BITB-03 | ✓ SATISFIED | Backend pagination and exact branch detail lookup work; the consumer mismatch is recorded under PROD-08. |
| BITB-04 | ✓ SATISFIED | Exact commit-bound source read capability remains GET-only and bounded when invoked. |
| UI-03 | ✗ BLOCKED | Approved dirty-form feedback/preservation is absent for mapping forms and bypassable through normal SPA navigation. |

**Requirements score:** 13/15 satisfied.

## Required Artifacts

| Artifact group | Existence / substance | Wiring / data flow | Status |
|---|---|---|---|
| User admin API/service/CLI/UI | Present and substantive | HTTP/CLI → shared authority lock → PostgreSQL → generated client/UI | ✓ VERIFIED |
| Product/revision/repository/mapping graph | Present and substantive | Candidate graph → validation → atomic publication/reactivation | ✓ VERIFIED |
| OAuth and Bitbucket provider adapter | Present and substantive | Compose → client credentials → encrypted generation → validated GET-only reads | ✓ VERIFIED |
| Four-format preview backend | Present and substantive | Worker → strict detectors → durable bounded job/result/confirmation | ✓ VERIFIED |
| `ProductPreviewPage.resolveCommits` | Present but incomplete | Valid configured branch → first list page only → local find → throw before preview | ✗ PARTIAL / BLOCKER |
| Product and mapping dirty-form guards | Product listener present; mapping guard absent | Router Link/pushState → immediate route unmount; no pre-navigation blocker | ✗ NOT WIRED / BLOCKER |
| Quality/evidence gate | Present | Current review inventory reaches verifier with two Critical findings | ✗ FAILED |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Mapping configured branch | Exact provider branch detail | `getAdminRepositoryBranch` in `ProductMappingsPage` | ✓ WIRED | Focused branch-101 test passes and returns the exact commit. |
| Configured branch | Preview commit request | `ProductPreviewPage.resolveCommits` | ✗ NOT WIRED | Uses `listAdminRepositoryBranches({cursor:null, limit:100})` and never calls the exact detail operation. |
| Dirty product details | Internal wizard step change | local pending-navigation Alert Dialog | ✓ WIRED | `requestStep` blocks step changes and preserves focus/values. |
| Dirty product details | Shell/product route navigation | React Router blocker | ✗ NOT WIRED | `AppShell.RoutedDestination` follows `<Link>` immediately. |
| Dirty mapping form | Any document or SPA exit | shared dirty-state blocker | ✗ NOT WIRED | No beforeunload or router blocker exists in `ProductMappingsPage`. |
| Preview result | Publication/reactivation | exact current confirmation/eligibility | ✓ WIRED | Candidate and active-revalidation authorities remain server-bound and fail closed. |

## Data-Flow Trace (Level 4)

| Rendered / submitted value | Authoritative source and flow | Produces real data | Status |
|---|---|---|---|
| Users/products/repositories/mappings | PostgreSQL → service/schema → generated client → React | Yes | ✓ FLOWING |
| Configured branch 101 in mapping form | Exact branch endpoint → generated client → merged live options | Yes | ✓ FLOWING |
| Configured branch 101 in preview | Mapping response → truncated first page → local miss → exception | No commit reaches job creation | ✗ DISCONNECTED |
| Dirty product/mapping values during Link navigation | React local state → route unmount | Values are discarded without the required decision | ✗ DISCONNECTED |
| Preview samples | Provider bytes → worker/detectors → PostgreSQL → polling UI | Yes when commit resolution succeeds | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command / method | Result | Status |
|---|---|---|---|
| Current preview commit resolution | `npm test -- --run ProductPreviewPage.test.tsx -t "resolves exact commits..."` | 1/1 PASS; test asserts only `cursor:null, limit:100` | ✗ GAP CONFIRMED |
| Exact configured branch 101 | `npm test -- --run ProductMappingsPage.test.tsx -t "restores configured branch 101..."` | 1/1 PASS; exact detail endpoint returns branch 101 | ✓ PASS; proves preview inconsistency |
| SPA dirty-form interception | Source call-chain from `AppShell.Link` through product/mapping forms plus test inventory | No Router blocker; tests cover manual `popstate`/reload only | ✗ GAP CONFIRMED |
| Default Compose flow API drift | Literal route comparison with canonical `frontend/openapi.json` | `/oauth/start` and `/oauth/callback` absent; `/connect` present | ⚠ WARNING CONFIRMED |
| Prior-phase regression | Execute-phase regression gate | Effective backend 284/284; frontend 96/96 | ✓ PASS |

## Probe Execution

No `scripts/**/tests/probe-*.sh` or phase-declared probe exists. The phase's runnable checks are tests, gauntlets, and smoke scripts rather than verifier probes.

## Test Quality Audit

| Test evidence | Linked requirement | Active | Disabled | Circular | Strongest assertion | Verdict |
|---|---|---:|---:|---:|---|---|
| `ProductPreviewPage.test.tsx` commit resolution | PROD-08, BITB-03 | yes | 0 | no | Behavioral request/body assertions | ✗ INSUFFICIENT: codifies first-page truncation and omits branch 101 |
| `ProductMappingsPage.test.tsx` branch 101 | PROD-03, BITB-03 | yes | 0 | no | Behavioral pagination + exact detail lookup | ✓ VALID |
| Product dirty-form tests | UI-03 | yes | 0 | no | Synthetic beforeunload/popstate | ✗ INSUFFICIENT: no real Router Link transition |
| Mapping form tests | UI-03 | yes | 0 | no | Form mutation/save behavior | ✗ INSUFFICIENT: no dirty-exit behavior |
| Phase 2 backend/frontend suites | All IDs | yes | 0 source-level skips found | no circular expected-value generator found | Value and behavioral | ✓ Broad regression evidence; does not cover the two blockers |

**Disabled tests on requirements:** 0.
**Circular patterns detected:** 0.
**Insufficient behavioral seams:** 2 root seams, matching CR-14 and CR-15.

## Decision Coverage

`gsd-tools query check.decision-coverage-verify` reports **23/23 honored**, with no `not_honored` entries. This gate is advisory and does not override observable failures in the shipped UI.

## Current Review Inventory — All 23 Rows

| Row | Current disposition | Independent current anchor | Verdict |
|---|---|---|---|
| CR-01 | CLOSED | Shared backend/worker/scheduler provider environment remains in base Compose | ✓ VERIFIED |
| CR-02 | CLOSED | Exact bounded Basic-auth client-credentials exchange remains implemented | ✓ VERIFIED |
| CR-03 | CLOSED | Callback/authorization-code/refresh authority remains absent from API/service | ✓ VERIFIED |
| CR-04 | CLOSED for normal authority | Access-only encrypted generation and serialized renewal remain; WR-03 retained | ✓ VERIFIED WITH WARNING |
| CR-05 | CLOSED | Complete isolated candidate graph clone and atomic identity promotion remain wired | ✓ VERIFIED |
| CR-06 | CLOSED | Immutable active-revision revalidation/reactivation sidecar remains wired | ✓ VERIFIED |
| CR-07 | CLOSED | Persistent five-step mobile wizard controls remain present and tested | ✓ VERIFIED |
| CR-08 | CLOSED | Cursor collection and mapping-51 lifecycle gating remain complete | ✓ VERIFIED |
| CR-09 | CLOSED | Watchdog CAS and retry isolation remain deployed | ✓ VERIFIED |
| CR-10 | CLOSED | HTTP/CLI authority-reducing paths share the admin lock/survivor predicate | ✓ VERIFIED |
| CR-11 | CLOSED | Separate scheduler exists in base, staging, and production overlays | ✓ VERIFIED |
| CR-12 | CLOSED | Exact immutable active-revalidation model/API/UI recovery remains present | ✓ VERIFIED |
| CR-13 | CLOSED | Runtime CSP, `frame-ancestors 'none'`, XFO DENY, and defensive headers remain exact | ✓ VERIFIED |
| CR-14 | **OPEN — BLOCKER** | `resolveCommits` reads only page one while exact branch lookup exists and mapping branch 101 passes | ✗ FAILED |
| CR-15 | **OPEN — BLOCKER** | Router Links bypass product listeners; mapping form has no guard | ✗ FAILED |
| WR-01 | CLOSED | Workspace overview and location-authoritative shell remain wired | ✓ VERIFIED |
| WR-02 | CLOSED | Composite ownership FKs and published-child immutability triggers remain present | ✓ VERIFIED |
| WR-03 | **OPEN — WARNING** | `expires_in` accepts any positive integer; persistence uses unbounded `timedelta` | ⚠ OPEN |
| WR-04 | **OPEN — WARNING** | Locked dev chain remains `@stryker-mutator/core → typed-rest-client@2.3.1 → qs@6.15.1` | ⚠ OPEN |
| WR-05 | **OPEN — WARNING** | Docker/Compose images remain tag-only without `@sha256:` pins | ⚠ OPEN |
| WR-06 | **OPEN — WARNING** | `.env.example` still contains none of the required Phase 2 provider/watchdog keys | ⚠ OPEN |
| WR-07 | **OPEN — WARNING** | Executable `phase2_spec_edge_matrix.json` remains outside `phase2_source_manifest.txt` | ⚠ OPEN |
| WR-08 | **OPEN — WARNING** | Default `phase2_compose_flow.py` still calls removed OAuth start/callback routes | ⚠ OPEN |

## Prohibitions and Anti-Patterns

The nine test-tier Phase 2 prohibitions remain enforced: no active-revision mutation from candidate work, no provider/canonical writes, no cross-product mapping leakage, no cross-repository/target grouping, no secret exposure, no ambiguity guessing, no exhaustive-sample claim, and no invalid publication.

No unreferenced `TBD`, `FIXME`, or `XXX` marker was found in Phase 2 production source. The blockers are functional omissions rather than placeholder files. No disabled requirement test or circular expected-value generator was found.

## Human Verification Required

None for this verdict. Both blocking failures are programmatically observable in current source and test call chains. Human visual/UAT cannot convert them into a pass; implementation and automated real-router regressions are required first.

## Deferred-Item Filter

Neither blocker is deferred. Phase 3 builds import-grade resilience on top of the Phase 2 read-only boundary; it does not own Phase 2 preview commit resolution or Phase 2 dirty-form navigation safety.

## Gaps Summary

Two root gaps block the phase goal:

1. **Exact configured branch → preview commit is not wired.** Valid branch 101+ configurations cannot run candidate validation or active-revision revalidation.
2. **Dirty form → Router navigation blocker is not wired.** Ordinary SPA navigation can discard product and mapping edits without the required confirmation.

The failed quality-gate criterion is a consequence of these two root gaps: a fresh review cannot be Critical-zero until both are fixed and re-reviewed.

## Recommended Gap Plans

### 02-44: Exact Preview Branch Resolution

Use RED→GREEN TDD to replace page-one local commit lookup with exact configured-branch reads for every direct/separate/active-revalidation side. Add branch-101 candidate and active-revalidation tests, then rerun affected frontend/E2E/API drift checks.

### 02-45: Router-Native Dirty Form Protection

Use RED→GREEN TDD to add one shared router blocker to product and mapping forms, retain beforeunload for document exits, and prove `Keep editing`/`Discard changes` through real shell and product-detail links with value/focus preservation.

After both plans, rerun the Phase 2 quality gate, fresh code review, and independent verifier. The canonical next workflow is `$gsd-plan-phase 2 --gaps`.

---

_Verified: 2026-09-01T09:41:51Z_
_Verifier: the agent (gsd-verifier)_
