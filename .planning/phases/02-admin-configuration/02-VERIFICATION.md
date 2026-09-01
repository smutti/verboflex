---
phase: 02-admin-configuration
verified: 2026-09-01T09:02:08Z
verification_date: 2026-09-01
status: passed
score: "8/8 roadmap success criteria verified"
behavior_unverified: 0
overrides_applied: 0
head: 43e4bb7c1e89d09affa8f0a1868ff088acc98224
final_source_digest: a4b16eeb2879fd64b32a8942663bd2af117d99662b206bd24711744d9d302964
review_source_digest: ede23c16f49301366ec9e30edc885e52c726b5d57a7bc3a796be6e9f30979d90
inventories:
  phase_goal: "1/1 verified"
  roadmap_success_criteria: "8/8 verified"
  requirements: "15/15 satisfied"
  context_decisions: "23/23 honored"
  research_assumptions: "3/3 resolved and tested"
  spec_edge_rows: "54/54 disposition verified (47 tested, 2 assumption-resolved and tested, 5 dismissed)"
  prohibitions: "9/9 test-enforced"
  ui_categories: "8/8 verified"
  bitbucket_capabilities: "44/44 disposition verified (9 integrated, 35 opt-out)"
  review_rows: "20/20 adjudicated (13 critical closed, 2 warnings closed, 5 warnings open)"
  root_concerns: "6/6 closed"
review:
  status: pass_with_warnings
  critical: 0
  warning: 5
  open_warnings: [WR-03, WR-04, WR-05, WR-06, WR-07]
re_verification:
  previous_status: gaps_found
  previous_score: "53/64"
  gaps_closed:
    - "G1 cross-entry-point administrator safety"
    - "G2 complete candidate isolation and editing"
    - "G3 production OAuth composition"
    - "G4 usable end-to-end admin UI"
    - "G5 durable worker-loss handling"
    - "G6 clean fresh review"
  gaps_remaining: []
  regressions: []
---

# Phase 2: Admin Configuration Verification Report

**Phase Goal:** Deliver an administrator-only control plane for internal users, versioned products, reusable repositories, one-format mappings, a single organizational Bitbucket OAuth connection, and live read-only validation previews.  
**Verified:** 2026-09-01T09:02:08Z
**Status:** `passed`  
**Re-verification:** Yes — fresh goal-backward verification after gap closure. The earlier report, historical reviews, summaries, and prior PASS claims were treated as inventory only.

## Verdict

The Phase 2 goal is achieved at current HEAD `43e4bb7c1e89d09affa8f0a1868ff088acc98224`. All eight roadmap contracts, all 15 Phase 2 requirements, and every required inventory below are present, substantive, runtime-reachable, and covered by current executable evidence. The official unchanged-source gap-closure gauntlet passed all 18 layers and finished on the same final source digest. Post-summary stale-guard revalidation independently reconfirmed both digest authorities, inventory counts, and the semantic contract at this HEAD.

The current review has zero Critical findings and five explicitly open non-blocking warnings. WR-03 through WR-07 are retained as **OPEN — WARNING** below; this report does not call them fixed or omit their limitations. There are zero goal-blocking gaps, zero behavior-unverified truths, and no human-only item required for this verdict.

## Source and Evidence Freshness

| Authority | Fresh command or source | Result |
|---|---|---|
| Final source identity | `VERBOFLEX_SOURCE_MANIFEST=tools/phase2_source_manifest.txt tools/source_state.sh --digest` | `a4b16eeb2879fd64b32a8942663bd2af117d99662b206bd24711744d9d302964` |
| Review-mode identity | `VERBOFLEX_SOURCE_MANIFEST=tools/phase2_source_manifest.txt VERBOFLEX_REVIEW_PATH=docs/reviews/phase-02-code-security.md tools/source_state.sh --review-digest` | `ede23c16f49301366ec9e30edc885e52c726b5d57a7bc3a796be6e9f30979d90` |
| Canonical review binding | `tools/source_state.sh --verify-review-source` | exit 0 |
| Gap evidence binding | `VERBOFLEX_EVIDENCE_PATH=docs/evidence/phase-02-gap-closure.md tools/source_state.sh --verify-report-digest` | exit 0 |
| Official gate | `bash tools/phase2_gauntlet.sh --gap-closure` | exit 0; PASS 18/18; final digest unchanged |
| Decision ledger | `gsd-tools query check.decision-coverage-verify ...` | 23/23 honored; no `not_honored` entries |
| Current review inventory | authoritative section of `02-REVIEW.md` | 20 rows: CR-01..13 and WR-01..07; 13 Critical rows closed, WR-01/02 closed, WR-03..07 open |
| Literal edge registry | `phase2_spec_edge_matrix.json` consumed by `test_phase2_spec_edge_traceability.py` | 54 rows: 47 tested, 2 resolved by A-01/A-02 and tested, 5 dismissed |

WR-07 limits the digest claim: `phase2_spec_edge_matrix.json` is executable input but is not included in either source manifest digest. The matrix was therefore counted only after a fresh direct parse and fresh execution of its in-manifest architecture consumer; its omission remains an open provenance warning.

## Goal Achievement

### Roadmap Success Criteria

| # | Roadmap contract | Status | Current code and behavioral evidence |
|---|---|---|---|
| SC-01 | Complete reversible internal-user lifecycle with multiple roles, one-time credentials, and last-active-admin safety | ✓ VERIFIED | `admin_users.py` shares `ADMIN_AUTHORITY_LOCK_KEY`, `_lock_admin_authority`, `_require_admin_survivor`, and the common deactivation transition across HTTP and CLI. Concurrency/reset/CLI nodes passed in the 803-test run. |
| SC-02 | Candidate product changes remain isolated until atomic publication | ✓ VERIFIED | `save_product_candidate` and `_clone_active_revision_graph` clone all mappings/sides/targets with new IDs; `_promote_candidate_identity` and publication move identity/pointers only under the product lock. Clone/isolation/publication mutation inventories were all killed. |
| SC-03 | Global repositories are reusable while mappings and preview state remain product/revision-specific | ✓ VERIFIED | `Repository` owns normalized global provider identity; composite ownership FKs and revision-owned mapping/preview rows isolate product graphs. Repository race/reuse and graph-integrity tests passed. |
| SC-04 | One exact-scope organizational Bitbucket connection powers live repository listing and read-only preview | ✓ VERIFIED | Backend-only `client_credentials`, exact `repository` effective scope, encrypted access-only generations, reacquisition, local revoke, Compose parity, and GET-only provider adapter are production-wired. Mock-provider audit observed client credentials, five GETs, zero writes. |
| SC-05 | Each mapping has one exact format/layout, source branch, allowed/default targets, and fixed repository+target PR grouping | ✓ VERIFIED | Mapping schemas/services enforce direct/separate topology, exact live branches, allowed/default membership, one confirmed layout, and deterministic repository+target grouping. Mapping/grouping mutation inventories were fully killed. |
| SC-06 | Four-format bounded preview fails closed for invalid, ambiguous, stale, disconnected, timed-out, or worker-lost work | ✓ VERIFIED | Strict Android/Qt/JSON/iOS adapters feed a closed result envelope and durable UUID/attempt/generation CAS. Watchdog and dual-overlay worker-loss smokes produced `timed_out/time_limit_exceeded`, then an isolated successful retry. |
| SC-07 | Guided shadcn admin screens expose actionable states on supported layouts | ✓ VERIFIED | Guarded URL-backed routes use the generated client. Component/E2E tests exercise loading/error/empty/partial/overflow, 0/1/50/51 collections, 100/101 branches, 320px five-step traversal, stale recovery, and explicit publish/reactivate actions. |
| SC-08 | TDD, review, backend/frontend/worker, and deployment smoke gate closes cleanly | ✓ VERIFIED | Official gate passed 18/18: 803 backend, 271 frontend, static/build/OpenAPI/migration/property/mutation checks, provider/browser smoke, both deployment overlays, cleanup, and unchanged final digest. Current review is `pass_with_warnings`, `critical: 0`. |

**Roadmap score:** 8/8 verified; 0 present-but-behavior-unverified.

## Requirements Coverage

Every Phase 2 requirement is claimed and implemented; no Phase 2 requirement is orphaned. Checkboxes in `REQUIREMENTS.md` were not used as evidence.

| Requirement | Contract | Status | Current evidence |
|---|---|---|---|
| AUTH-02 | Create, update, reset, deactivate, reactivate, and view internal users | ✓ SATISFIED | Admin API/UI plus common locked service/CLI transitions; one-time secret and authority-revocation tests pass. |
| AUTH-03 | Assign multiple fixed roles to one user | ✓ SATISFIED | Non-empty set semantics, stable ordering, self-admin protection, survivor invariant, and UI role controls are tested. |
| PROD-01 | Create/edit product name, description, and lifecycle | ✓ SATISFIED | A-01 normalization, routed `/new` and `/:id/edit`, isolated candidate identity, publication, deactivation, and reactivation are exercised. |
| PROD-02 | Configure one or more repositories per product | ✓ SATISFIED | Global credential-free registry plus revision-owned mapping sides; reuse and complete pagination are tested. |
| PROD-03 | Configure the exact source branch per mapping | ✓ SATISFIED | Provider branch resolution and paged/exact configured branch controls preserve opaque names, including item 101. |
| PROD-04 | Configure allowed/default PR target branches | ✓ SATISFIED | Non-empty normalized allowed set, exact live membership, default containment, and conflict projection are enforced. |
| PROD-05 | Configure product-specific PR grouping | ✓ SATISFIED | `pr_grouping.py` groups only exact repository UUID + target branch and is invariant to language/file order. |
| PROD-06 | Configure direct or linked-translation topology | ✓ SATISFIED | Closed topology schema/service/UI; topology changes require confirmation and clear irrelevant state. |
| PROD-07 | Link key and translation repositories | ✓ SATISFIED | Separate mappings require exact `keys` and `translations` repository/branch sides throughout API, DB, UI, and preview identity. |
| PROD-08 | Validate mapping through live bounded preview | ✓ SATISFIED | Commit-bound discovery, strict four-format detection, durable background jobs, polling, confirmation, stale checks, and recovery execute. |
| PROD-09 | Configure one localization format/layout per mapping | ✓ SATISFIED | Separate exact candidates, confidence 1, explicit radio selection, versioned confirmation, and ambiguity rejection are tested. |
| BITB-01 | Connect, reconnect, revoke, and inspect one organization-wide Bitbucket OAuth connection | ✓ SATISFIED | Direct admin operations, access-only encrypted generation, expiry reacquisition, bounded status, and local revoke are wired; WR-03 remains. |
| BITB-03 | List configured repository branches | ✓ SATISFIED | Provider pagination is fully traversed; app cursors and exact-branch lookups reach 100/101 boundary behavior. |
| BITB-04 | Read localization files from configured source branch | ✓ SATISFIED | Commit-bound GET-only source tree/raw reads enforce URL, generation, encoding, byte, depth, entry, page, and file ceilings. |
| UI-03 | Clear validation feedback for repository, branch, mapping, and credential setup | ✓ SATISFIED | Stable bounded copy, owning-region errors, preserved inputs, focus/ARIA, retry, conflict, and lifecycle blocker tests pass. |

**Requirements score:** 15/15 satisfied.

## Context Decisions D-01..D-23

The decision-coverage query returned 23/23 honored. Each row below also has a current runtime or test reachability anchor; the query result alone was not treated as proof.

| Decision | Locked outcome | Status | Current evidence |
|---|---|---|---|
| D-01 | Backend-generated temporary password, revealed once, forced change | ✓ VERIFIED | `_generate_temporary_credential`, hash-only persistence, `TemporaryPasswordDialog`; create/reset/reactivate and erasure tests. |
| D-02 | Corporate email immutable; replacement requires new account | ✓ VERIFIED | Update schema/service excludes email mutation; immutable-email API/UI tests. |
| D-03 | Only display name, roles, lifecycle, dedicated reset are administratively mutable | ✓ VERIFIED | Closed Pydantic schemas and lifecycle routes; secret/list/OpenAPI negative tests. |
| D-04 | Additive combinations of four roles; at least one retained | ✓ VERIFIED | Fixed enum/set validation plus empty/duplicate role tests. |
| D-05 | No self-admin removal; all paths preserve an active admin | ✓ VERIFIED | Shared advisory lock/survivor predicate and cross-entry/concurrency tests. |
| D-06 | Deactivation reversible; revoke authority; reactivation creates fresh secret | ✓ VERIFIED | Common lifecycle transaction advances token version/revokes sessions; freshness tests. |
| D-07 | Global repository unique by normalized workspace+slug and reusable | ✓ VERIFIED | `Repository` unique constraint and registration race/reuse tests. |
| D-08 | Product-specific configuration lives on revision mappings | ✓ VERIFIED | Revision-owned mappings/sides/targets and two-product isolation tests. |
| D-09 | Only Product has operational active/inactive state | ✓ VERIFIED | Product lifecycle service/schema; no mapping lifecycle column or route. |
| D-10 | Publish/reactivate requires every mapping valid; deactivation preserves graph | ✓ VERIFIED | Closed blocker matrix, full eligibility, graph-preserving lifecycle integration tests. |
| D-11 | One source, non-empty allowed targets, contained default per mapping | ✓ VERIFIED | Mapping validators and exact provider-branch tests. |
| D-12 | One mapping model with `direct` and `separate` topologies | ✓ VERIFIED | Closed enums/check constraints, side roles, service/UI transition tests. |
| D-13 | Layout is automatically discovered; no admin globs/templates | ✓ VERIFIED | Detector registry derives candidates; schemas/OpenAPI/browser expose no manual layout controls. |
| D-14 | Phase 2 preview adapters are read-only, not canonical writers | ✓ VERIFIED | Preview registry plus provider/canonical forbidden-boundary architecture tests. |
| D-15 | Preview shows files/formats/languages/samples and needs explicit confirmation | ✓ VERIFIED | `CandidateDetails`, partial label, radio selection, exact confirmation identity tests. |
| D-16 | Unsafe-to-bound scanning/parsing runs through background jobs | ✓ VERIFIED | HTTP persists/enqueues UUID only; Celery worker owns discovery/detection; background boundary tests. |
| D-17 | PR grouping is fixed by repository and target branch | ✓ VERIFIED | Five grouping/property tests and 13/13 grouping mutants killed. |
| D-18 | Alternative target must be drawn from allowed list | ✓ VERIFIED | Mapping membership validator and live checkbox/default controls. |
| D-19 | Guided new-product wizard; focused detail sections in shared admin shell | ✓ VERIFIED | URL-backed five-step wizard and overview/repositories/mappings/preview routes; 320px E2E. |
| D-20 | Active edits create isolated candidate; atomic publish promotes it | ✓ VERIFIED | Deep clone with fresh IDs, active immutability triggers, version conflicts, atomic pointer/identity promotion. |
| D-21 | Provider authentication is OAuth 2.0, not access/API/app-password tokens | ✓ VERIFIED | Client-credentials-only service/routes and forbidden credential/grant surface tests. |
| D-22 | Provider credentials backend-only, encrypted, separate from user auth | ✓ VERIFIED | `SecretStr`, MultiFernet, access-only encrypted row, redaction/OpenAPI/browser/log scans. |
| D-23 | Exact least-privilege scope matrix; no undocumented superset | ✓ VERIFIED | Exact `repository` comparison, x-oauth-scopes validation, 44-row capability matrix, provider audit. |

**Decision score:** 23/23 verified.

## Research Assumptions A-01..A-03

| Assumption | Resolution | Status | Executable evidence |
|---|---|---|---|
| A-01 | NFKC, Unicode whitespace collapse/trim, printable ≤120 code points, casefolded global `name_key` | ✓ RESOLVED/TESTED | `normalize_product_name`; `test_a01_normalizes_display_and_global_identity_key`; product-name property suite. |
| A-02 | Strict per-format encoding/shape matrix; duplicate/invalid/unsupported content blocks | ✓ RESOLVED/TESTED | Android/Qt/JSON/iOS unit/property suites; detector mutation inventories including invalid UTF, duplicate identity, DTD/entity, escape, and registry mutations. |
| A-03 | Exact pagination/file/depth/byte/language/sample/time/job/polling/list bounds | ✓ RESOLVED/TESTED | `SOURCE_DISCOVERY_BUDGET`, HTTPX timeouts, preview job limits, polling scheduler, boundary tests, watchdog/worker-loss smoke. |

**Assumption score:** 3/3 resolved and tested.

## Literal SPEC Edge Rows

Fresh matrix parsing found exactly 54 rows: 47 `tested`, 1 `resolved-A-01`, 1 `resolved-A-02`, and 5 `dismissed`. `test_phase2_spec_edge_traceability.py` freshly proved a one-to-one match with the literal SPEC table and reachable collected test nodes.

| Edge | Current disposition | Reachable current test node |
|---|---|---|
| R1-adjacency | ✓ TESTED | `test_duplicate_normalized_email_conflicts_without_enumeration_or_secret` |
| R1-empty | ✓ TESTED | `test_concurrent_cross_deactivation_cannot_remove_the_last_active_admin` |
| R1-ordering | ✓ TESTED | `test_user_list_has_stable_opaque_default_and_maximum_pagination` |
| R1-idempotency | ✓ TESTED | `test_admin_updates_roles_then_resets_deactivates_and_reactivates_one_identity` |
| R1-concurrency | ✓ TESTED | `test_concurrent_cross_role_removal_cannot_remove_the_last_active_admin` |
| R2-adjacency | ✓ TESTED | role non-empty/fixed-vocabulary node |
| R2-empty | ✓ TESTED | role non-empty/fixed-vocabulary node |
| R2-encoding | ✓ TESTED | normalized email conflict node |
| R2-ordering | ✓ TESTED | stable role update/lifecycle node |
| R2-idempotency | ✓ TESTED | identical role/display update node |
| R2-concurrency | ✓ TESTED | cross-role-removal concurrency node |
| R3-idempotency | ✓ TESTED | concurrent reset/final-secret node |
| R3-concurrency | ✓ TESTED | concurrent reset/final-secret node |
| R4-empty | ✓ TESTED | A-01 normalization node |
| R4-encoding | ✓ RESOLVED A-01 + TESTED | A-01 normalization node |
| R4-idempotency | ✓ TESTED | version/conflict/identical-save node |
| R4-concurrency | ✓ TESTED | product-lock publish/stale-writer node |
| R5-idempotency | ✓ TESTED | credential repetition/generation node |
| R5-concurrency | ✓ TESTED | credential rotation/revoke serialization node |
| R6-adjacency | ✓ TESTED | repository identity normalization node |
| R6-empty | ✓ TESTED | repository identity normalization node |
| R6-encoding | ✓ TESTED | repository identity normalization node |
| R6-ordering | ✓ TESTED | server-ordered repository collection node |
| R6-idempotency | ✓ TESTED | duplicate/UUID reuse node |
| R6-concurrency | ✓ TESTED | two-session registration race node |
| R7-adjacency | ✓ TESTED | target-set/default-membership node |
| R7-empty | ✓ TESTED | exact separate-side node |
| R7-encoding | ✓ TESTED | live exact branch node |
| R7-ordering | ✓ DISMISSED (set order has no meaning) | target-set normalization guard node |
| R7-idempotency | ✓ TESTED | duplicate identity/true no-op node |
| R7-concurrency | ✓ TESTED | duplicate identity/conflict node |
| R8-adjacency | ✓ TESTED | exact repository+target identity node |
| R8-empty | ✓ TESTED | empty/no-capability grouping node |
| R8-ordering | ✓ DISMISSED (order cannot affect identity) | grouping permutation node |
| R8-idempotency | ✓ TESTED | grouping permutation/invariance node |
| R8-concurrency | ✓ DISMISSED (Phase 2 executes no PR jobs) | no-provider/persistence capability node |
| R9-adjacency | ✓ TESTED | four separate exact format candidates node |
| R9-empty | ✓ TESTED | empty/unrelated content node |
| R9-encoding | ✓ RESOLVED A-02 + TESTED | unsupported-shape and invalid-encoding nodes |
| R9-ordering | ✓ TESTED | file-order invariant node |
| R9-idempotency | ✓ TESTED | succeeded-result currentness node |
| R9-concurrency | ✓ TESTED | in-flight stale commit node |
| R10-adjacency | ✓ TESTED | every-mapping confirmation node |
| R10-empty | ✓ TESTED | closed blocker/unchanged graphs node |
| R10-ordering | ✓ DISMISSED (validity is order-independent) | every-mapping confirmation node |
| R10-idempotency | ✓ TESTED | product-lock linearization node |
| R10-concurrency | ✓ TESTED | product-lock linearization node |
| R11-adjacency | ✓ DISMISSED (routes have no merge semantics) | router local-containment node |
| R11-empty | ✓ TESTED | loading/retry/empty collection node |
| R11-ordering | ✓ TESTED | API-order/cursor node |
| R11-idempotency | ✓ TESTED | duplicate-pending submission node |
| R11-concurrency | ✓ TESTED | expected-version/preserved-edit node |
| R12-idempotency | ✓ TESTED | no dynamic/mutating provider verb node |
| R12-concurrency | ✓ TESTED | same read-only provider-boundary node |

**Edge score:** 54/54 disposition verified.

## Prohibitions

All nine are `verification: test`. Each has non-empty enforcement evidence and passed; none was silently accepted on judgment.

| # | Prohibition | Status | Wired enforcement evidence |
|---|---|---|---|
| P-01 | Never expose temporary passwords outside the one successful lifecycle response | ✓ VERIFIED | Hash-only model/service; response-only schema; list/detail/OpenAPI/log tests; UI erases acknowledgement state. |
| P-02 | Never mutate/deactivate/replace active revision during candidate save, preview, or failure | ✓ VERIFIED | Ownership triggers, deep clone, read-only preview path, graph-byte identity and failure tests. |
| P-03 | Never expose Bitbucket credentials/client secrets to SPA, OpenAPI, payloads, or logs | ✓ VERIFIED | SecretBox/SecretStr, closed schemas, redaction scans, storage guard, provider diagnostics tests. |
| P-04 | Never propagate product-specific state between products sharing a repository | ✓ VERIFIED | Revision ownership constraints and two-product repository/mapping isolation tests. |
| P-05 | Never guess ambiguity or combine formats/layouts into one mapping | ✓ VERIFIED | Strict detector registry, exact candidate separation, ambiguity/unsupported fixtures, confidence guards. |
| P-06 | Never group across repository or target-branch boundaries | ✓ VERIFIED | Grouping property suite and killed equality/order mutants. |
| P-07 | Never present bounded samples as exhaustive | ✓ VERIFIED | `samples_are_partial` response and visible exact partial-sample copy tested in UI/E2E. |
| P-08 | Never publish with absent/stale/ambiguous/invalid/disconnected/unconfirmed preview | ✓ VERIFIED | Closed blockers, current identity/confirmation checks, negative publication matrix and E2E. |
| P-09 | Never write provider source/canonical translation/commit/branch/PR state from preview | ✓ VERIFIED | GET-only adapter/allowlist, provider-spy/architecture tests, five GETs/zero writes audit. |

**Prohibition score:** 9/9 test-enforced.

## UI State Categories

| Category | Status | Current source and executable evidence |
|---|---|---|
| empty | ✓ VERIFIED | Named list/preview states and component tests |
| loading | ✓ VERIFIED | Route/list/branch/preview Skeletons, `aria-busy`, pending/dedup tests |
| error | ✓ VERIFIED | Bounded owning-region Alerts, preserved inputs, retry, sanitization |
| populated | ✓ VERIFIED | Deterministic API order, desktop tables/mobile stacks, routed actions |
| partial | ✓ VERIFIED | Active/candidate distinction, blockers, terminal-cursor gating, sample copy |
| overflow | ✓ VERIFIED | Focusable local overflow, wrapping actions, 320px/200% zoom E2E |
| zero-one-many | ✓ VERIFIED | 0/1/50/51 rows, 100/101 branches, grammar and explicit confirmation |
| long-text | ✓ VERIFIED | safe wraps, full-copy access, long identifier/text tests |

**UI score:** 8/8 verified.

## Bitbucket Capability Matrix

Fresh parsing of `COVERAGE.md` found exactly 44 decisions: 9 integrated and 35 explicit opt-outs. The forbidden-boundary suite proves opt-outs are absent from provider adapter, service, OpenAPI, and generated client surfaces.

| Capability | Decision | Status | Current reachability/enforcement |
|---|---|---|---|
| oauth-client-credentials-acquisition | INTEGRATE | ✓ VERIFIED | exact token exchange/provider audit |
| oauth-client-credentials-reacquisition | INTEGRATE | ✓ VERIFIED | serialized renewal/reconnect tests |
| oauth-authorization-code-callback-and-refresh-token-flows | OPT-OUT | ✓ ENFORCED | service/route/client absence test |
| oauth-effective-scope-inspection | INTEGRATE | ✓ VERIFIED | exact token and response scope checks |
| repository-metadata-by-workspace-and-slug | INTEGRATE | ✓ VERIFIED | metadata GET and provider audit |
| branch-listing-with-provider-pagination | INTEGRATE | ✓ VERIFIED | provider traversal and app cursor tests |
| branch-to-commit-resolution | INTEGRATE | ✓ VERIFIED | exact branch name/hash validation |
| source-tree-directory-pagination | INTEGRATE | ✓ VERIFIED | commit-bound budgeted traversal |
| raw-source-file-read-at-commit | INTEGRATE | ✓ VERIFIED | streamed bounded raw GET |
| provider-next-url-validation | INTEGRATE | ✓ VERIFIED | host/path/resource validation mutants killed |
| oauth-provider-side-token-revocation | OPT-OUT | ✓ ENFORCED | local generation revoke only |
| repository-listing-and-search | OPT-OUT | ✓ ENFORCED | explicit registration only |
| account-profile-and-email | OPT-OUT | ✓ ENFORCED | endpoint/scope absent |
| workspace-membership-and-permissions | OPT-OUT | ✓ ENFORCED | capability absent |
| project-listing-and-metadata | OPT-OUT | ✓ ENFORCED | endpoint family absent |
| workspace-and-project-administration | OPT-OUT | ✓ ENFORCED | admin APIs excluded by allowlist |
| tag-listing-and-other-ref-discovery | OPT-OUT | ✓ ENFORCED | branch-only refs |
| commit-history-listing-and-search | OPT-OUT | ✓ ENFORCED | no commit collection/search |
| commit-diff-diffstat-and-patch-read | OPT-OUT | ✓ ENFORCED | no diff family |
| commit-status-read-and-write | OPT-OUT | ✓ ENFORCED | no status capability |
| source-file-create-update-delete | OPT-OUT | ✓ ENFORCED | GET-only adapter |
| branch-create-update-delete | OPT-OUT | ✓ ENFORCED | branch GET only |
| tag-create-update-delete | OPT-OUT | ✓ ENFORCED | tags/writes absent |
| commit-create | OPT-OUT | ✓ ENFORCED | source write absent |
| pull-request-list-and-read | OPT-OUT | ✓ ENFORCED | PR family absent |
| pull-request-create-and-update | OPT-OUT | ✓ ENFORCED | write scope/operation absent |
| pull-request-merge-decline-and-approve | OPT-OUT | ✓ ENFORCED | workflow capability absent |
| pull-request-comments-tasks-and-activity | OPT-OUT | ✓ ENFORCED | collaboration capability absent |
| pull-request-diff-and-diffstat | OPT-OUT | ✓ ENFORCED | PR/diff absent |
| repository-webhook-list-and-read | OPT-OUT | ✓ ENFORCED | webhook family absent |
| repository-webhook-create-update-delete | OPT-OUT | ✓ ENFORCED | webhook admin absent |
| repository-settings-and-permissions-admin | OPT-OUT | ✓ ENFORCED | exact reader scope/allowlist |
| branch-restrictions-and-merge-checks-admin | OPT-OUT | ✓ ENFORCED | policy API absent |
| deploy-keys-access-keys-and-ssh-keys-admin | OPT-OUT | ✓ ENFORCED | OAuth-only credential surface |
| pipelines-list-and-read | OPT-OUT | ✓ ENFORCED | pipelines family absent |
| pipelines-run-stop-and-manage | OPT-OUT | ✓ ENFORCED | pipeline mutation absent |
| deployments-and-environments | OPT-OUT | ✓ ENFORCED | deployment family absent |
| issues-list-and-read | OPT-OUT | ✓ ENFORCED | issues family absent |
| issues-create-update-delete-and-comments | OPT-OUT | ✓ ENFORCED | issue mutation absent |
| downloads-list-and-read | OPT-OUT | ✓ ENFORCED | source API only |
| downloads-upload-and-delete | OPT-OUT | ✓ ENFORCED | downloads mutation absent |
| wiki-read-and-write | OPT-OUT | ✓ ENFORCED | wiki endpoint/scope absent |
| snippets-read-and-write | OPT-OUT | ✓ ENFORCED | snippet endpoint/scope absent |
| code-search | OPT-OUT | ✓ ENFORCED | bounded source traversal only |

**Capability score:** 44/44 disposition verified (9 integrated, 35 opt-out).

## Current Fresh Review CR-01..CR-13 and WR-01..WR-07

This is the authoritative 20-row inventory. The separate legacy appendix in `02-REVIEW.md` is non-authoritative and was not used for current disposition.

| Row | Current status | Current production/evidence anchor | Verdict |
|---|---|---|---|
| CR-01 | CLOSED | shared backend/worker/scheduler provider environment | ✓ VERIFIED |
| CR-02 | CLOSED | exact bounded client-credentials exchange | ✓ VERIFIED |
| CR-03 | CLOSED | no callback/authorization-code/refresh authority | ✓ VERIFIED |
| CR-04 | CLOSED for normal authority; WR-03 remains | access-only encrypted generation/renewal | ✓ VERIFIED WITH WR-03 |
| CR-05 | CLOSED | complete isolated candidate graph | ✓ VERIFIED |
| CR-06 | CLOSED | immutable revalidation/reactivation | ✓ VERIFIED |
| CR-07 | CLOSED | persistent five-step mobile controls | ✓ VERIFIED |
| CR-08 | CLOSED | complete cursor/51st mapping gating | ✓ VERIFIED |
| CR-09 | CLOSED | watchdog CAS and worker-kill smoke | ✓ VERIFIED |
| CR-10 | CLOSED | common HTTP/CLI admin invariant | ✓ VERIFIED |
| CR-11 | CLOSED | scheduler parity and dual-overlay loss smoke | ✓ VERIFIED |
| CR-12 | CLOSED | immutable revalidation sidecar/UI recovery | ✓ VERIFIED |
| CR-13 | CLOSED | runtime CSP/anti-framing headers | ✓ VERIFIED |
| WR-01 | CLOSED | location-authoritative Workspace shell | ✓ VERIFIED |
| WR-02 | CLOSED | graph ownership/published immutability | ✓ VERIFIED |
| WR-03 | **OPEN — WARNING** | unbounded positive `expires_in` can overflow | ⚠ OPEN; not fixed |
| WR-04 | **OPEN — WARNING** | dev-only Stryker → typed-rest-client → `qs` advisory | ⚠ OPEN; not fixed |
| WR-05 | **OPEN — WARNING** | mutable container tags | ⚠ OPEN; not fixed |
| WR-06 | **OPEN — WARNING** | `.env.example` lacks seven Phase 2 keys | ⚠ OPEN; not fixed |
| WR-07 | **OPEN — WARNING** | edge JSON outside digests | ⚠ OPEN; not fixed |

The review gate remains `critical: 0`, `warning: 5`, `status: pass_with_warnings`. None of WR-03..07 is represented as fixed.

## G1..G6 Root-Concern Closure

| Root | Current closure | Status |
|---|---|---|
| G1 cross-entry admin safety | shared advisory lock/survivor transition covers HTTP and CLI | ✓ CLOSED |
| G2 candidate isolation/editing | routed edit deep-clones full active graph; atomic delayed promotion | ✓ CLOSED |
| G3 OAuth composition | client credentials, exact scope, encrypted generation, renewal, Compose, GET-only adapter | ✓ CLOSED; WR-03 retained |
| G4 end-to-end admin UI | URL routes, mobile wizard, complete cursors, recovery, UI state matrix | ✓ CLOSED |
| G5 worker-loss handling | Beat scheduler and attempt/generation CAS in staging+production | ✓ CLOSED |
| G6 clean fresh review | CR-01..13 closed, critical 0, five open warnings | ✓ CLOSED WITH WARNINGS |

**Root-concern score:** 6/6 closed.

## Artifacts, Wiring, and Data Flow

| Artifact group | Exists/substantive | Real flow | Status |
|---|---|---|---|
| User admin API/service/CLI/UI | yes | route/CLI → shared lock/service → PostgreSQL → generated client/UI | ✓ VERIFIED |
| Product/revision/repository/mapping graph | yes | API → locks → owned revision graph → publication/reactivation | ✓ VERIFIED |
| OAuth/provider adapter | yes | Compose → token endpoint → encrypted generation → lease → validated GET | ✓ VERIFIED |
| Discovery/four-format preview | yes | branch → commit → bounded bytes → detector → durable result/confirmation | ✓ VERIFIED |
| Worker recovery | yes | UUID → running CAS → worker/scheduler terminal CAS → retry | ✓ VERIFIED |
| Generated client/admin SPA | yes | OpenAPI → generated calls → routed state/forms/lifecycle | ✓ VERIFIED |
| Deployment/security | yes | three Compose layers; built Nginx root/fallback headers | ✓ VERIFIED |
| Quality/evidence | yes | digests → 18 layers → cleanup/final identity | ✓ VERIFIED; WR-07 retained |

### Critical Key Links

| From | To | Via | Status |
|---|---|---|---|
| Admin HTTP/CLI | active-admin invariant | common lock/survivor predicate | ✓ WIRED |
| Active product | isolated candidate | complete fresh-ID graph clone | ✓ WIRED |
| Candidate | effective active config | locked atomic publication | ✓ WIRED |
| OAuth settings | backend/worker/scheduler | shared Compose environment | ✓ WIRED |
| OAuth connection | provider reads | generation checked before/after GET | ✓ WIRED |
| Provider source | detectors | exact commit + bounded traversal | ✓ WIRED |
| Preview | publication/reactivation | closed identity/confirmation/eligibility | ✓ WIRED |
| Worker loss | terminal/retry | Beat watchdog + CAS | ✓ WIRED |
| OpenAPI | admin SPA | generated client + drift/behavior tests | ✓ WIRED |
| Partial collections | lifecycle authority | terminal cursor gating | ✓ WIRED |

### Level-4 Data Flow

| Value | Authoritative source and flow | Status |
|---|---|---|
| users/products/repositories/mappings | PostgreSQL → service/schema → generated client → React | ✓ FLOWING |
| Bitbucket status | encrypted singleton generation → bounded response → page | ✓ FLOWING |
| branches/source | provider HTTP → validated adapter/discovery → API | ✓ FLOWING |
| preview details | commit bytes → worker/detector → PostgreSQL → polling UI | ✓ FLOWING |
| lifecycle blockers | current graph/confirmations → eligibility → UI | ✓ FLOWING |
| recovery | stale running rows → Beat lock/CAS → terminal/retry | ✓ FLOWING |

No goal-path dynamic value terminates in a production placeholder, mock-only branch, or hardcoded empty prop.

## Behavioral and Quality Gate

| Layer | Fresh result | Status |
|---|---|---|
| Semantic closure | 30 passed, including edge and gap fingerprints | ✓ PASS |
| Backend | 803 passed; 97% overall coverage | ✓ PASS |
| Frontend | 271 passed | ✓ PASS |
| Static/build | mypy 81 files, Ruff, typecheck/lint/format/build | ✓ PASS |
| Properties | 200 backend + 3 frontend | ✓ PASS |
| Changed scope | 641/641 backend + 634/634 frontend | ✓ PASS |
| Mutations | all backend inventories killed; polling 30/30 | ✓ PASS |
| Migrations/OpenAPI | 10 passed; generated diff clean | ✓ PASS |
| Supply chain | policy passed; production audits clean | ✓ PASS WITH WR-04/05 |
| Architecture/provider spy | 53 passed | ✓ PASS |
| Base Compose | client-credentials readiness | ✓ PASS |
| Provider/browser | provider audit; Playwright 8/8 | ✓ PASS |
| Worker loss | staging+production recovery | ✓ PASS |
| Live external provider | explicitly optional SKIP | informational |
| Cleanup/final identity | zero resources; digest unchanged | ✓ PASS |

No unreferenced `TBD`, `FIXME`, or `XXX` blocker exists in Phase 2 production source. Inspected empty seeds and conditional `return null` paths are state guards replaced by real generated-client data. The generator-owned client TODO is not an implementation stub.

## Human Verification Required

None. State transitions, cancellation/supersession, pagination, worker loss, governed layout breakpoints, and provider HTTP behavior all have passing behavioral or deployment/browser evidence. The external-account smoke is explicitly optional, not an unverified must-have.

## Gaps Summary

No goal-blocking gaps remain. WR-03..WR-07 remain visible follow-up work and are not represented as fixed.

## Frozen Legacy Compatibility Appendix — Non-Authoritative

The following sentence is retained only because `test_phase2_gap_closure.py` freezes it as a compatibility fingerprint. It describes the superseded 2026-08-29 failed verification, **not** current disposition.

> Six root concerns block progress: cross-entry-point admin safety, complete candidate isolation/editing, production OAuth composition, usable end-to-end admin UI, durable worker-loss handling, and a clean fresh review.

---

_Verified: 2026-09-01T09:02:08Z_
_Verifier: the agent (gsd-verifier)_
