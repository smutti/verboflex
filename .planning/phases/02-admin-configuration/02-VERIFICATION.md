---
phase: 02-admin-configuration
verified: 2026-08-29T10:27:29Z
status: gaps_found
score: 53/64 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "User lifecycle preserves the last-active-admin invariant through every privileged entry point."
    status: failed
    reason: "The HTTP service enforces the invariant, but the privileged deactivate-user CLI bypasses the global authority lock and survivor check."
    artifacts:
      - path: "backend/src/verboflex/services/admin_users.py"
        issue: "deactivate_user_by_email() directly deactivates the row without _lock_admin_authority() or _require_admin_survivor()."
      - path: "backend/src/verboflex/cli.py"
        issue: "The CLI delegates directly to the unsafe service path."
    missing:
      - "Route CLI deactivation through the same serialized invariant used by the HTTP lifecycle service."
      - "Add a failing-first regression for CLI deactivation of the sole active administrator, including concurrency coverage."
  - truth: "Editing a published product creates an isolated, complete candidate graph while the active configuration remains byte-for-byte unchanged."
    status: failed
    reason: "There is no production edit route for an existing product; candidate creation copies only the revision description, omits mappings/sides/targets, and updates the globally shared product name before publication."
    artifacts:
      - path: "backend/src/verboflex/services/products.py"
        issue: "save_product_candidate() creates a bare ProductRevision and mutates Product.display_name/name_key immediately."
      - path: "frontend/src/router.tsx"
        issue: "Only the /admin/products/new wizard route exists; no existing-product edit route supplies initialProduct."
    missing:
      - "Clone the full active revision graph into a new candidate and keep all effective active identity/configuration unchanged until publish."
      - "Add and test a routed existing-product edit workflow."
  - truth: "The shipped stack can establish and maintain the approved single organization-wide, repository-only Bitbucket connection."
    status: failed
    reason: "Base Compose supplies no OAuth settings; production supports authorization-code/refresh pairs while the approved and live-tested client uses client_credentials; callback completion redirects to the API origin; expiry does not change status or trigger a reachable refresh path."
    artifacts:
      - path: "docker-compose.yml"
        issue: "No VERBOFLEX_BITBUCKET_OAUTH_* or keyring configuration is passed to backend/worker."
      - path: "backend/src/verboflex/services/bitbucket_oauth.py"
        issue: "No client_credentials grant; refresh token is mandatory; provider_expires_at is ignored by status/readability."
      - path: "backend/src/verboflex/api/v1/routes/admin_bitbucket.py"
        issue: "Relative callback redirect resolves on localhost:8000 instead of the frontend on localhost:8080."
    missing:
      - "Choose and implement one approved production grant end-to-end, including Compose configuration and encrypted durable authority."
      - "Redirect callback completion to the configured frontend origin."
      - "Handle access-token expiry with reachable refresh/reauthorization behavior and tests."
  - truth: "Administrators can complete product setup, reactivation, repository/branch selection, and preview flows across the supported UI."
    status: failed
    reason: "Reactivation loads an endpoint that rejects the candidate-null state, mobile wizard navigation stops after step 2, several collection/branch consumers discard pagination, and Workspace overview is inert and permanently current."
    artifacts:
      - path: "frontend/src/features/admin/previews/ProductPreviewPage.tsx"
        issue: "Always requests candidate mappings before evaluating the reactivation state."
      - path: "frontend/src/features/admin/products/ProductWizardPage.tsx"
        issue: "Step buttons are desktop-only and mobile progress is display-only."
      - path: "frontend/src/features/admin/repositories/ProductRepositoriesPage.tsx"
        issue: "Fetches only the first 50 repositories and discards next_cursor."
      - path: "frontend/src/features/admin/mappings/ProductMappingsPage.tsx"
        issue: "Fetches only first repository/mapping/branch pages and discards cursors."
      - path: "frontend/src/components/layout/AppShell.tsx"
        issue: "Workspace overview is a button with no navigation and aria-current is unconditional."
    missing:
      - "Use a reactivation-compatible read model or endpoint and exercise the real backend contract in E2E."
      - "Add usable Previous/Next or selectable mobile step navigation."
      - "Consume pagination for repositories, mappings, and branches."
      - "Make Workspace overview navigable and derive current state from the route."
  - truth: "Every accepted preview job reaches a durable terminal state, including hard timeout and worker loss."
    status: failed
    reason: "The worker commits running before work and only writes a terminal state in the surviving task process; hard kill/crash has no watchdog, redelivery, or stale-running reconciliation."
    artifacts:
      - path: "backend/src/verboflex/services/preview_jobs.py"
        issue: "A running row can remain permanent when the process never reaches _finish_preview_job()."
      - path: "backend/src/verboflex/worker/celery_app.py"
        issue: "No late acknowledgement, reject-on-worker-lost, or reconciler is configured."
    missing:
      - "Implement durable worker-loss/hard-timeout recovery with attempt-safe terminalization or redelivery."
      - "Add a regression that kills/loses a running task and proves a bounded terminal result."
  - truth: "The final quality gate has no unresolved critical/high finding."
    status: failed
    reason: "The newest code review, committed after the earlier closed security review/evidence refresh, contains 10 confirmed critical findings."
    artifacts:
      - path: ".planning/phases/02-admin-configuration/02-REVIEW.md"
        issue: "CR-01 through CR-10 remain valid against current code."
    missing:
      - "Close every confirmed critical with focused TDD, repeat the full unchanged-source gate, and obtain a fresh review."
---

# Phase 2: Admin Configuration Verification Report

**Phase Goal:** Deliver an administrator-only control plane for internal users, versioned products, reusable repositories, one-format mappings, a single organizational Bitbucket OAuth connection, and live read-only validation previews.
**Verified:** 2026-08-29T10:27:29Z
**Status:** `gaps_found`
**Re-verification:** No — initial goal-backward verification.

## Goal Achievement

### Roadmap Success Criteria

| # | Roadmap contract | Status | Current-code evidence |
|---|---|---|---|
| 1 | Complete reversible internal-user lifecycle with multiple roles, one-time credentials, and last-active-admin safety | ✗ FAILED | HTTP paths are substantive, but `deactivate_user_by_email()` bypasses the survivor invariant and is exposed by the privileged CLI. |
| 2 | Candidate product changes remain isolated until atomic publication | ✗ FAILED | Existing-product edit is unrouted; the candidate omits the active mapping graph and the product name changes before publication. |
| 3 | Global repositories are reusable while mappings and preview state remain product/revision-specific | ✓ VERIFIED | Global repository identity is separated from revision-owned `ProductRepositoryMapping`; service and DB tests cover reuse and revision isolation. |
| 4 | One exact-scope organizational Bitbucket connection powers live repository listing and read-only preview | ✗ FAILED | Production Compose/config/grant/callback/expiry paths do not match the approved, live-tested connection. |
| 5 | Each mapping has one exact format/layout, source branch, allowed/default targets, and fixed repository+target PR grouping | ✓ VERIFIED | Mapping validators, layout identity/version selection, branch constraints, and deterministic `pr_grouping.py` are wired and targeted tests pass. |
| 6 | Four-format bounded preview fails closed for invalid, ambiguous, stale, disconnected, or timed-out work | ✗ FAILED | Detector/confirmation logic is strong, but worker loss/hard timeout can leave `running` forever rather than failing closed. |
| 7 | Guided shadcn admin screens expose actionable states on supported layouts | ✗ FAILED | Published edit/reactivation/mobile navigation/pagination and Workspace overview have observable wiring gaps. |
| 8 | TDD, review, backend/frontend/worker, and deployment smoke gate closes cleanly | ✗ FAILED | The supplied gauntlet/test/smoke facts are valid but the newest review has 10 unresolved critical findings. |

**Roadmap contract score:** 2/8 verified.

### PLAN Must-Have Disposition

The 64 detailed PLAN truths were read and checked against code. The merged score retains roadmap wording where a PLAN truth only restates it.

| Plans | Verified / total | Failed or narrowed truth |
|---|---:|---|
| 02-01 | 2/3 | “any transition” preserving an active admin fails through CLI deactivation. |
| 02-02 | 2/3 | Published-product candidate isolation is incomplete: no graph clone and effective product identity changes early. |
| 02-03–02-04 | 5/5 | Repository identity and the core singleton/encryption/generation service are substantive. Operational production wiring is separately failed by the roadmap contract. |
| 02-05 | 1/3 | Refresh is not reachable and expiry never yields a correct public/read state; revoke itself is verified. |
| 02-06–02-10 | 15/15 | Bounded read adapter, discovery, mapping/topology/grouping, and normal publication service paths are substantive and tested. |
| 02-11 | 2/3 | Attempt identity is guarded, but hard-kill/worker-loss terminalization is absent. |
| 02-12–02-15 | 13/13 | Four detectors, registry/ambiguity, confirmation, publication predicate, and generated-client drift are substantive and wired. |
| 02-16 | 3/4 | Shared-shell URL/current-state contract is broken by the inert, always-current Workspace overview. |
| 02-17 | 3/3 | User-page lifecycle, one-time credential modal, and conflict handling are present for the HTTP UI path. |
| 02-18 | 2/4 | Existing-product save/edit is unreachable and the mobile five-step wizard cannot advance beyond the embedded step. |
| 02-19 | 2/4 | Callback does not complete on the SPA origin; real-backend reactivation and mobile E2E behavior fail. |
| 02-20 | 3/4 | Deployment-like/mock/live evidence exists, but the mandatory fresh-review truth fails. |

**Detailed PLAN score:** 53/64 truths verified; 0 present-but-behavior-unverified truths.

## Required Artifacts and Wiring

All 44 paths declared under PLAN `must_haves.artifacts` exist and contain substantive code. The GSD artifact helper returned zero entries because these plans use inline YAML maps, so existence/substance/wiring was checked manually. Existence does not rescue the following broken links.

| Artifact group | Exists/substantive | Wiring/data status | Result |
|---|---|---|---|
| User admin API/service/UI | Yes | HTTP path flows API → service → PostgreSQL; CLI uses a different unsafe transition | ⚠ PARTIAL |
| Product/revision/mapping models, migrations, services | Yes | Normal create/publish flows reach PostgreSQL; active graph → candidate clone/edit route is missing | ✗ HOLLOW FOR EDIT |
| OAuth service/routes/UI | Yes | Core service reaches encrypted DB state and Bitbucket adapter; Compose/grant/callback/expiry authority is incomplete | ✗ PARTIAL |
| Discovery/read adapter | Yes | Credential lease → validated `api.bitbucket.org` reads → opaque cursors | ✓ VERIFIED |
| Preview detectors/registry/confirmation | Yes | Commit-bound bytes → exact detector → digest/confirmation → publication predicate | ✓ VERIFIED |
| Preview worker | Yes | Queued → running → terminal on surviving process; no durable recovery after process loss | ✗ PARTIAL |
| Generated client/admin SPA | Yes | Most API operations consume generated types; existing edit/reactivation/mobile/pagination paths are disconnected | ✗ PARTIAL |
| Compose/smoke/gauntlet tooling | Yes | Mock flow and checks exist; base OAuth configuration and clean-review gate fail | ✗ PARTIAL |

### Key Links

| Link | Status | Evidence |
|---|---|---|
| Admin user routes → lifecycle service → DB | ✓ WIRED | Role/temporary-password/session-revocation paths use serialized service transactions. |
| Privileged CLI → lifecycle invariant | ✗ NOT WIRED | CLI calls `deactivate_user_by_email()` without the HTTP survivor guard. |
| Product save → complete candidate graph | ✗ NOT WIRED | Only a bare revision row is created; mappings/sides/targets are not cloned. |
| Product list/detail → existing-product edit wizard | ✗ NOT WIRED | Router exposes `/new`, overview, repositories, mappings, and preview, but no edit route with `initialProduct`. |
| OAuth settings → backend/worker Compose | ✗ NOT WIRED | Base environment omits required client/secret/callback/keyring values. |
| OAuth callback → frontend page | ✗ NOT WIRED | Relative 303 Location remains on the API origin. |
| OAuth expiry → refresh/reauthorization | ✗ NOT WIRED | `refresh()` has no route/task/caller and status/read lease ignore expiry. |
| OAuth lease → Bitbucket read adapter | ✓ WIRED | Exact-generation credential lease is consumed by discovery/read services. |
| Mapping API → candidate revision graph | ✓ WIRED | Optimistic version checks and revision-owned mapping mutations reach PostgreSQL. |
| Source read → four detector registry → candidate response | ✓ WIRED | Bounded commit-resolved bytes flow through exact Android/Qt/JSON/iOS detectors. |
| Preview confirmation → publication predicate | ✓ WIRED | Bound digest/layout/authority identity is checked before normal publication. |
| Celery hard loss → durable terminal job | ✗ NOT WIRED | Only the running worker process can finish the row. |
| React admin pages → generated client | ✓ WIRED | Generated OpenAPI client is used; drift check passes. |
| Cursor-bearing APIs → repository/mapping/branch UI | ✗ PARTIAL | First page is rendered, but `next_cursor` is discarded by these consumers. |

### Data-Flow Trace

| Rendered/returned data | Real source | Flow | Status |
|---|---|---|---|
| Users/products/repositories | PostgreSQL queries | API schemas → generated client → React states | ✓ FLOWING, except edit navigation gap |
| Branches/source files | Bitbucket Cloud | encrypted lease → HTTPS adapter → bounded service → API/UI | ✓ FLOWING for reachable first pages |
| Preview samples/layout choices | Commit-bound provider bytes | worker → detector registry → PostgreSQL job → polling UI | ✓ FLOWING during normal worker completion |
| Reactivation mappings | Candidate-mapping endpoint | Endpoint rejects the candidate-null state required for reactivation | ✗ DISCONNECTED |
| OAuth connection in base Compose | Environment → service factory | Required environment values are absent, factory returns unavailable | ✗ DISCONNECTED |

## Requirements Coverage

Every Phase 2 requirement ID is claimed by at least one plan; there are no orphaned Phase 2 requirements. `[x]` markers in `REQUIREMENTS.md` were treated as planning metadata, not evidence.

| Requirement | Description (REQUIREMENTS.md) | Status | Evidence / blocker |
|---|---|---|---|
| AUTH-02 | Create, update, reset, deactivate, and view internal users | ✗ BLOCKED | HTTP lifecycle works, but the privileged CLI can deactivate the sole active admin. |
| AUTH-03 | Assign multiple roles to one user | ✓ SATISFIED | Durable many-role assignment is enforced in model/service/API/UI tests. |
| PROD-01 | Create and edit product identity/description/status | ✗ BLOCKED | No routed existing-product edit; name mutates before candidate publication. |
| PROD-02 | Configure one or more repositories per product | ✓ SATISFIED | Reusable repositories and revision-owned mapping associations are implemented. |
| PROD-03 | Configure source branch per mapping | ✗ BLOCKED | Backend supports exact branches, but UI cannot reach branch results after the first 100. |
| PROD-04 | Configure allowed target branches | ✗ BLOCKED | Validation exists, but pagination makes valid later branches unselectable in the control plane. |
| PROD-05 | Configure PR grouping | ✓ SATISFIED | Fixed repository UUID + exact target branch grouping is deterministic and tests pass. |
| PROD-06 | Configure direct vs linked-translation topology | ✓ SATISFIED | Direct/separate topology constraints and transitions are implemented. |
| PROD-07 | Link key and translation repositories | ✓ SATISFIED | Separate Keys/Translations sides retain explicit repository/branch identity. |
| PROD-08 | Validate mapping through live bounded preview | ✗ BLOCKED | Normal preview works, but worker loss can remain running forever and reactivation preview is unreachable. |
| PROD-09 | Configure localization format per mapping | ✓ SATISFIED | Exactly one versioned layout candidate can be selected/confirmed. |
| BITB-01 | Connect/reconnect/revoke/view one organizational OAuth connection | ✗ BLOCKED | Shipped configuration, approved grant, callback origin, and expiry lifecycle do not compose. |
| BITB-03 | List configured repository branches | ✗ BLOCKED | API pagination exists; admin UI silently discards continuation pages. |
| BITB-04 | Read localization files from configured source branch | ✗ BLOCKED | Read adapter is substantive, but the approved production credential path is not implemented. |
| UI-03 | Clear repository/branch/mapping/credential validation feedback | ✗ BLOCKED | Critical edit/reactivation/mobile/pagination/navigation flows are not actionable. |

**Coverage:** 6/15 satisfied, 9/15 blocked.

## Decision and Prohibition Coverage

The decision ledger query reports all 23 `02-CONTEXT.md` decisions as referenced (`23/23`, no `not_honored` entries). That traceability result is non-blocking and does not prove runtime correctness; D-09/D-16/D-21 are among the decisions whose implementation has the gaps above.

Eight of nine SPEC prohibitions have direct enforcement/tests (secret exposure, repository-state coupling, ambiguity, PR grouping, sample labeling, stale/unconfirmed publish, and provider/canonical writes). The candidate-save prohibition is violated in effective behavior because product identity changes before publish and no isolated candidate graph is constructed.

## `02-REVIEW.md` Adjudication

The review commit is newer than `docs/reviews/phase-02-code-security.md` and the last evidence refresh. Each finding was independently checked against current code; none is rejected.

| Finding | Verdict | Code evidence | Goal impact |
|---|---|---|---|
| CR-01 Compose cannot receive Bitbucket config | **CONFIRMED** | `docker-compose.yml:9-20` omits all OAuth/keyring settings; the service factory degrades to unavailable. | Blocks BITB-01/04 and SC4. |
| CR-02 Approved client-credentials grant absent | **CONFIRMED** | `bitbucket_oauth.py:122-151` implements only authorization-code/refresh; `:742-759` requires a refresh token. | Live proof exercised a separate memory-only authority, not production. |
| CR-03 Callback redirects to API origin | **CONFIRMED** | `admin_bitbucket.py:227-230` returns a relative path from port 8000 while SPA is port 8080. | Same-tab completion is broken. |
| CR-04 Token expiry leaves false Connected state | **CONFIRMED** | `public_status()` and `_require_readable_connection()` ignore `provider_expires_at`; `refresh()` is orphaned. | Reads fail after expiry without an actionable status. |
| CR-05 Published edit unreachable/incomplete | **CONFIRMED** | Router has no existing edit route; `products.py:209+` creates only a revision and `:159-161,189` mutates global identity. | Breaks candidate isolation and PROD-01. |
| CR-06 Reactivation unreachable | **CONFIRMED** | Preview page requests candidate mappings at `:687-696` before detecting candidate-null reactivation at `:785-795`; backend rejects that state. | Breaks product lifecycle UI. |
| CR-07 Mobile wizard cannot advance | **CONFIRMED** | Step buttons are `hidden ... md:block`; mobile `Step n of 5` is display-only; embedded later steps provide no step navigation. | Breaks supported mobile flow. |
| CR-08 Pagination discarded | **CONFIRMED** | Repository/mapping/preview pages request fixed first pages and never consume their `next_cursor`; only Users/Products do. | Makes valid repositories/branches/mappings inaccessible. |
| CR-09 Worker loss leaves permanent running | **CONFIRMED** | `preview_jobs.py:837` commits running; terminalization occurs only later in the same process; Celery config has no recovery mechanism. | Breaks durable fail-closed preview. |
| CR-10 CLI can deactivate last admin | **CONFIRMED** | `admin_users.py:413-431` omits the authority lock/survivor check; `cli.py:99-106` calls it. | Breaks AUTH-02/SC1 safety invariant. |
| WR-01 Workspace overview inert/current | **CONFIRMED WARNING** | `AppShell.tsx:139-159` renders a no-op button with unconditional `aria-current="page"`. | Navigation/accessibility defect; included in UI gap. |
| WR-02 DB lacks cross-graph ownership constraints | **CONFIRMED WARNING** | Independent FKs permit cross-product revision/mapping/job IDs; published immutability trigger covers only revision rows. | Service checks reduce current exposure, but DB integrity is not fail-closed. |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Fixed repository+target grouping | `uv run pytest -q tests/unit/services/test_pr_grouping.py` | 5 passed in 0.14s | ✓ PASS |
| Preview polling ordering/stop behavior | `npm test -- --run src/features/admin/previews/usePreviewPolling.test.ts` | 13 passed | ✓ PASS |
| Generated OpenAPI drift | `npm run api:check` | Generation completed; committed schema/client unchanged | ✓ PASS |
| Phase 2 scripts parse | `bash -n tools/phase2_gauntlet.sh tools/phase2_smoke.sh` | syntax ok | ✓ PASS |

No conventional `scripts/**/tests/probe-*.sh` or PLAN-declared probe was found, so Probe Execution is not applicable. The orchestrator-supplied facts—14/14 final gauntlet, live 5 GET/0 writes, 14-plan/0-violation TDD checkpoint, and regression gate with temporary Redis/Celery—are recorded as valid historical evidence. They do not exercise the failed paths above.

## Test Quality and Anti-Patterns

- No `.skip`, `.only`, `pytest.mark.skip`, `xfail`, or test TODO marker was found in the scanned Phase 2 test areas.
- The review explains three misleading proof boundaries: the product-copy test asserts only revision fields, the callback test checks a Location header without following it across origins, and the reactivation E2E mock returns candidate mappings in a backend-impossible candidate-null state.
- The live Bitbucket probe correctly proves exact repository scope and zero writes, but it uses client credentials plus memory-only authority and therefore is not a production-path integration test.
- One TODO exists in generated `frontend/src/api/client/client/client.gen.ts:214`; it is generator-owned cleanup text, not a Phase 2 implementation stub. No unreferenced `TBD`, `FIXME`, or source `XXX` debt marker was found.

## Human Verification Required

None is required to establish this verdict: each blocking failure is observable in current wiring or invariants. After gap closure, repeat desktop/mobile UAT and a real same-tab Bitbucket connection, expiry, and reactivation flow before declaring the phase passed.

## Gaps Summary and Closure Guidance

The implementation contains substantial, well-tested foundations, but the Phase 2 outcome is not achieved. Six root concerns block progress: cross-entry-point admin safety, complete candidate isolation/editing, production OAuth composition, usable end-to-end admin UI, durable worker-loss handling, and a clean fresh review.

Recommended closure order:

1. Run `$gsd-plan-phase 2 --gaps` and create focused TDD plans from the structured frontmatter gaps.
2. Fix authority/data-integrity paths first: last-admin CLI, candidate graph clone/identity isolation, and preview recovery.
3. Align the approved Bitbucket grant and shipped configuration; close callback and expiry behavior with production-path tests.
4. Repair existing edit/reactivation/mobile/pagination/navigation flows and replace impossible mocks with contract-faithful E2E fixtures.
5. Repeat the complete unchanged-source Phase 2 gauntlet and obtain a fresh code/security review; then rerun verification.

---

_Verified: 2026-08-29T10:27:29Z_
_Verifier: the agent (gsd-verifier)_
