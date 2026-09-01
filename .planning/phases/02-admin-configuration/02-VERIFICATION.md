---
phase: 02-admin-configuration
verified: 2026-09-01T18:09:09Z
verification_date: 2026-09-01
status: passed
score: "8/8 roadmap success criteria verified"
behavior_unverified: 0
overrides_applied: 0
head: 5b1d425352003d0543ecab634ad14a104a46206d
review_source_digest: 2e93097910a805663c7ccad721f4f629b478bdd01efca95541c8509c5f0354a9
final_source_digest: e7f71e46fdaf7aea75230852d4232fb6b8e9fcfb43bd6f14f7440a89743a88e7
inventories:
  phase_goal: {count: 1, total: 1}
  roadmap_success_criteria: {count: 8, total: 8}
  requirements: {count: 15, total: 15}
  context_decisions: {count: 23, total: 23}
  research_assumptions: {count: 3, total: 3}
  spec_edge_rows: {count: 54, total: 54}
  prohibitions: {count: 9, total: 9}
  ui_considerations: {count: 8, total: 8}
  bitbucket_capabilities: {count: 44, total: 44}
  review_rows: {count: 23, total: 23}
review:
  status: issues_found
  critical: 0
  warning: 6
  info: 0
  open_blockers: []
  open_warnings: [WR-03, WR-04, WR-05, WR-06, WR-07, WR-08]
re_verification:
  previous_status: gaps_found
  previous_score: "5/8"
  gaps_closed:
    - "CR-14: exact-detail resolution now covers configured branch 101+ for candidate and immutable active-revision previews."
    - "CR-15: one router-native dirty-form transaction owner now blocks product and mapping transitions before route commit."
  gaps_remaining: []
  regressions: []
gaps: []
---

# Phase 2: Admin Configuration Verification Report

**Phase Goal:** Deliver an administrator-only control plane for internal users, versioned products, reusable repositories, one-format mappings, a single organizational Bitbucket OAuth connection, and live read-only validation previews.
**Verified:** 2026-09-01T18:09:09Z
**Status:** `passed`
**Re-verification:** Yes — fresh independent goal-backward verification after CR-14 and CR-15 gap closure. This verifier inspected current source and executable evidence; SUMMARY claims were not accepted as proof.

## Verdict

Phase 2 achieves its goal at committed HEAD `5b1d425352003d0543ecab634ad14a104a46206d`. All eight ROADMAP success criteria and all 15 Phase 2 requirements are verified. The result is bound to review-source digest `2e93097910a805663c7ccad721f4f629b478bdd01efca95541c8509c5f0354a9` and final-source digest `e7f71e46fdaf7aea75230852d4232fb6b8e9fcfb43bd6f14f7440a89743a88e7`.

The canonical security review is `CLOSED` with `Open-critical-high: 0`. The structured reviewer truthfully remains `issues_found` because WR-03 through WR-08 remain six OPEN Warnings. Those warnings are nonblocking under the project's High threshold; WR-08 remains deferred and is not represented as fixed.

## Source and Evidence Binding

| Authority | Current evidence | Verdict |
|---|---|---|
| Review source | `2e93097910a805663c7ccad721f4f629b478bdd01efca95541c8509c5f0354a9` | ✓ Exact review-mode digest |
| Final canonical source | `e7f71e46fdaf7aea75230852d4232fb6b8e9fcfb43bd6f14f7440a89743a88e7` | ✓ Exact final-mode digest |
| Canonical review | `Review-status: CLOSED`; `Open-critical-high: 0` | ✓ Critical/High gate closed |
| Structured review | `issues_found`; Critical 0, Warning 6, Info 0 | ✓ Reconciled with all 23 current CR/WR rows |
| Official post-canonical gauntlet | 18/18 ordered layers; final digest unchanged | ✓ PASS |
| Provider boundary | Five audited GET requests, zero provider writes, no residual owned resources | ✓ Read-only contract preserved |
| Fresh independent corroboration | CR-14 exact-detail trace, CR-15 router/focus/mobile trace, focused executable tests, semantic closeout audit | ✓ Current behavior independently checked |

## Goal Achievement

### Roadmap Success Criteria

| # | Roadmap contract | Status | Current code and behavioral evidence |
|---|---|---|---|
| SC-01 | Admin manages the complete reversible internal-user lifecycle with multiple roles, one-time credentials, and last-active-admin invariants. | ✓ VERIFIED | HTTP and CLI lifecycle paths share `ADMIN_AUTHORITY_LOCK_KEY` and the database survivor predicate; concurrency and one-time-secret tests exercise the transitions. |
| SC-02 | Candidate product configuration remains isolated until explicit atomic publication. | ✓ VERIFIED | Fresh-ID candidate graph cloning, published-child immutability, optimistic versioning, and locked identity promotion are substantive, wired, and covered by publication tests. |
| SC-03 | Repositories are globally reusable while branches, mappings, and preview state remain product/revision-specific. | ✓ VERIFIED | Normalized global repository identity is separate from revision-owned mapping and preview records; two-product isolation and ownership constraints are tested. |
| SC-04 | One organization-wide Bitbucket OAuth connection uses exact read-only `repository` scope for live branches and source content. | ✓ VERIFIED | Client-credentials acquisition, exact effective-scope validation, encrypted access-only generations, GET-only provider adapter, and bounded branch/source reads are wired. |
| SC-05 | Every direct/separate mapping has one exact layout, source branch, targets/default, and repository+target grouping. | ✓ VERIFIED | Closed schemas and mapping services enforce direct/separate sides, exact opaque branches, contained defaults, one layout identity, and exact grouping properties. |
| SC-06 | Bounded Android XML, Qt `.ts`, JSON, and iOS `.strings` preview fails closed for invalid, ambiguous, stale, disconnected, or bounded terminal states. | ✓ VERIFIED | Four strict detectors feed durable revision/commit-bound jobs; exact-detail branch resolution now covers branch 101+ for candidate and active-revision validation, and confirmation/currentness gates are tested. |
| SC-07 | Guided shadcn admin screens expose actionable and data-safe lifecycle, OAuth, mapping, preview, and job states. | ✓ VERIFIED | User/product/repository/mapping/preview screens are generated-client backed; shared router blocking protects dirty product and mapping forms, including Link, Back, reload, 320px Sheet, focus, and value preservation. |
| SC-08 | RED→GREEN TDD, code review, backend/frontend/worker, and deploy smoke gates pass. | ✓ VERIFIED | Post-canonical gauntlet passed 18/18: semantic 34/34, backend 807/807, frontend 304/304, property and mutation gates, provider/browser 57/57 and 8/8, both deployment overlays, cleanup, and unchanged digest. |

**Score:** 8/8 roadmap success criteria verified; 0 present-but-behavior-unverified.

## Requirements Coverage

All 15 Phase 2 requirement IDs are claimed by plans and have current implementation evidence. There are no orphaned Phase 2 requirements. REQUIREMENTS checkboxes were not treated as proof.

| Requirement | Status | Current evidence |
|---|---|---|
| AUTH-02 | ✓ SATISFIED | Guarded user create/list/update/reset/deactivate/reactivate service, API, CLI, generated client, and admin UI. |
| AUTH-03 | ✓ SATISFIED | Fixed additive multi-role sets, stable projection, self-admin protection, and concurrent last-admin invariant. |
| PROD-01 | ✓ SATISFIED | Normalized product identity, active/inactive lifecycle, immutable revisions, candidate editing, and atomic publication. |
| PROD-02 | ✓ SATISFIED | Credential-free global repository registry is reusable across products without sharing mapping state. |
| PROD-03 | ✓ SATISFIED | Mapping API/UI stores exact opaque source branches and restores configured branch 101+ through detail lookup. |
| PROD-04 | ✓ SATISFIED | Allowed target branches are normalized as a set and the default must be a member. |
| PROD-05 | ✓ SATISFIED | Group identity is exactly repository UUID plus target branch and is permutation-stable. |
| PROD-06 | ✓ SATISFIED | Closed topology enum supports exactly direct and separate mappings. |
| PROD-07 | ✓ SATISFIED | Separate mappings require explicit revision-owned Keys and Translations sides. |
| PROD-08 | ✓ SATISFIED | Candidate and immutable active-revision previews resolve every configured side by exact branch detail, including branch 101+, then bind the returned commit. |
| PROD-09 | ✓ SATISFIED | Preview returns separate exact format/layout candidates for Android XML, Qt `.ts`, JSON, and iOS `.strings`; ambiguity fails closed. |
| BITB-01 | ✓ SATISFIED | Single connection supports connect, reconnect, local revoke, and bounded status via exact client-credentials authority. |
| BITB-03 | ✓ SATISFIED | Cursor-bounded branch listing and exact branch detail lookup are both generated-client backed. |
| BITB-04 | ✓ SATISFIED | Commit-bound tree and raw-source GETs enforce host/path, pagination, depth, count, byte, and timeout budgets. |
| UI-03 | ✓ SATISFIED | Approved loading/empty/error/populated/partial states plus router-native dirty-form decisions preserve values and connected focus. |

**Requirements score:** 15/15 satisfied.

## Required Artifacts

| Artifact | Expected | Status | Substance, wiring, and data-flow evidence |
|---|---|---|---|
| `backend/src/verboflex/services/admin_users.py` | Shared user lifecycle authority | ✓ VERIFIED | HTTP and CLI transitions use the same advisory lock, survivor predicate, session revocation, and one-time-secret boundary. |
| Product/revision/repository/mapping models, migrations, and services | Isolated candidate and reusable repository graph | ✓ VERIFIED | Composite ownership, immutable published children, deep clone, optimistic concurrency, atomic publication, and sidecar revalidation reach PostgreSQL. |
| `backend/src/verboflex/services/bitbucket_oauth.py` and provider adapter | Exact-scope backend-only read authority | ✓ VERIFIED | Client credentials become encrypted generations; only bounded GET methods are public and provider results flow to services/jobs. |
| Preview worker and four detector adapters | Durable bounded read-only validation | ✓ VERIFIED | Exact commits and provider bytes flow through strict detectors to durable results and confirmation/currentness gates. |
| `frontend/src/features/admin/previews/ProductPreviewPage.tsx` | Exact configured-side commit resolution | ✓ VERIFIED | `configuredPreviewSourceSides` calls `resolveConfiguredBranchCommit`, which uses generated `getAdminRepositoryBranch`, requires exact returned-name equality, and supplies role-bound commits to candidate/active calls. |
| Dirty-form navigation provider and product/mapping guards | Pre-transition SPA and document-exit protection | ✓ VERIFIED | One application-scoped `useBlocker` owner handles router transactions; `useBeforeUnload` remains separate; forms register fingerprints and connected focus restoration. |
| `frontend/src/components/layout/AppShell.tsx` | Desktop/mobile router destinations | ✓ VERIFIED | Link, browser Back, and 320px Sheet destinations pass through the shared blocker before route commit. |
| Phase 2 gauntlet, source manifest, evidence, and reviews | Digest-bound quality authority | ✓ VERIFIED | Ordered gates, exact source-state checks, canonical critical-zero review, and structured semantic inventories reconcile. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Configured direct/keys/translations branch | Exact Bitbucket branch detail | `resolveConfiguredBranchCommit` → generated `getAdminRepositoryBranch` | ✓ WIRED | Returned name must equal the configured opaque name byte-for-byte before its commit is accepted. |
| Candidate and immutable active revision | Preview job creation | `configuredPreviewSourceSides` → candidate/active generated calls | ✓ WIRED | Every side carries repository identity, side role, exact branch, and exact-detail commit. |
| Preview worker | Provider commit authority | `_process_preview` re-resolution and commit comparison | ✓ WIRED | Worker rejects name/commit drift before reading or parsing; provider audit stays GET-only. |
| Dirty product/mapping state | Router transition | form fingerprint → `useDirtyFormNavigationGuard` → provider `useBlocker` | ✓ WIRED | Link/PUSH/POP is captured before route commit and only one destination is retained. |
| Keep editing | Preserved form and trigger | blocker reset → dialog close → deferred connected focus | ✓ WIRED | Product and mapping values remain unchanged and focus returns when the trigger is still connected. |
| Discard changes | Captured destination | blocker proceed exactly once | ✓ WIRED | One stored router transaction is consumed; stale intent is cleared on clean/unmount. |
| Document exit | Native browser prompt | `useBeforeUnload` | ✓ WIRED | Reload/tab close is independent of SPA dialog ownership. |
| Mobile Sheet destination | Shared router owner | `MobileNavigationCommitObserver` and AppShell links | ✓ WIRED | 320px cancel restores focus; discard completes only the captured navigation. |

## Data-Flow Trace (Level 4)

| Artifact/value | Real source and flow | Produces real data | Status |
|---|---|---|---|
| Users/products/repositories/mappings | PostgreSQL → service/schema → OpenAPI/generated client → React | Yes | ✓ FLOWING |
| Branch list and exact branch 101+ | Bitbucket GET → bounded adapter → backend API → generated client → mapping/preview UI | Yes | ✓ FLOWING |
| Candidate preview | Configured side → exact branch detail → exact commit → durable job → worker/provider bytes → detector → result UI | Yes | ✓ FLOWING |
| Active-revision revalidation | Immutable published graph → exact detail/commit → sidecar job/confirmation → lifecycle authority | Yes | ✓ FLOWING |
| Dirty navigation decision | Form fingerprint + router transaction → Alert Dialog → reset/proceed → values/focus or one destination | Yes | ✓ FLOWING |
| Preview publication eligibility | Durable current confirmation + revision/commit/connection identities → locked publication/reactivation | Yes | ✓ FLOWING |

## Independent Closure Traces

### CR-14 — Exact configured branch authority

The trace starts at each configured direct, keys, or translations branch. `configuredPreviewSourceSides` preserves repository identity and side role, `resolveConfiguredBranchCommit` calls generated `getAdminRepositoryBranch`, exact returned-name equality is required, and the returned commit is bound into candidate or immutable active-revision job creation. The worker independently resolves stored branch authority and rejects a commit mismatch before parsing. Branch 101+ succeeds without depending on the first branch-list page. Current provider evidence records five GETs and zero writes.

### CR-15 — Router-native dirty-form ownership

Dirty product and mapping fingerprints register with one application-scoped `DirtyFormNavigationProvider`. Router `useBlocker` captures Link/PUSH/POP before transition; `useBeforeUnload` separately owns document exits. `Keep editing` resets the transition, preserves values, and restores connected trigger focus after the Alert Dialog closes. `Discard changes` consumes one stored destination once. Clean transitions and unmount clear stale intent. Real-router evidence covers product and mapping Links, browser Back, reload, mobile 320px Sheet navigation, retained values, and focus restoration.

## Context Decision Coverage — D-01..D-23

| Decision | Current implementation evidence | Status |
|---|---|---|
| D-01 | Backend-generated temporary passwords are returned once and force password change. | ✓ HONORED |
| D-02 | Corporate email is immutable and remains the normalized stable login identifier. | ✓ HONORED |
| D-03 | Admin mutations are limited to display name, roles, lifecycle, and dedicated reset; plaintext is not retained. | ✓ HONORED |
| D-04 | Roles use the four fixed additive enums and every user retains at least one. | ✓ HONORED |
| D-05 | Self-admin removal and zero-active-admin outcomes are transactionally rejected. | ✓ HONORED |
| D-06 | Deactivation revokes authority; reactivation creates a fresh one-time credential. | ✓ HONORED |
| D-07 | Repository UUID rows are globally unique by normalized workspace+slug and reusable. | ✓ HONORED |
| D-08 | Product/revision mapping state remains independent despite shared repository rows. | ✓ HONORED |
| D-09 | Only the product owns active/inactive state; mappings have no independent lifecycle state. | ✓ HONORED |
| D-10 | Publication/reactivation requires every mapping's current valid confirmed preview. | ✓ HONORED |
| D-11 | Each mapping has one exact source branch, allowed targets, and contained default target. | ✓ HONORED |
| D-12 | One closed mapping model supports direct or explicit separate Keys/Translations sides. | ✓ HONORED |
| D-13 | Layout is discovered automatically; no user glob/file/template authority exists. | ✓ HONORED |
| D-14 | Phase 2 adapters are bounded read-only detectors, not canonical imports or writers. | ✓ HONORED |
| D-15 | Files/formats/languages/samples are visible; invalid or ambiguous detection blocks confirmation. | ✓ HONORED |
| D-16 | Preview runs through durable Celery jobs with bounded timeout/retry/watchdog behavior. | ✓ HONORED |
| D-17 | PR grouping identity is fixed to repository plus target and never crosses either boundary. | ✓ HONORED |
| D-18 | Allowed targets and one default are stored; any alternative must remain in the set. | ✓ HONORED |
| D-19 | New-product wizard and focused product/repository/mapping/preview routes share the admin shell. | ✓ HONORED |
| D-20 | Active edits clone a candidate; locked atomic publication alone changes the active identity. | ✓ HONORED |
| D-21 | Bitbucket uses OAuth 2.0 client credentials, not repository tokens, API tokens, or app passwords. | ✓ HONORED |
| D-22 | Provider credentials are backend-only, encrypted, redacted, and separate from internal auth. | ✓ HONORED |
| D-23 | Exact read-only scope/capability matrix is executable; undocumented supersets are rejected. | ✓ HONORED |

**Decision coverage:** 23/23 honored; `not_honored: []`. This advisory gate found no drift.

## Research Assumptions — A-01..A-03

| Assumption | Resolved contract and current evidence | Status |
|---|---|---|
| A-01 | Product names use NFKC, Unicode whitespace collapse, `casefold()` identity, printable/length checks, and global database uniqueness; exact normalization/conflict tests pass. | ✓ RESOLVED AND TESTED |
| A-02 | Strict format-specific encodings, duplicate-aware JSON, exact locale shapes, hardened XML, bounded `.strings`, and unsupported-fixture rejection are implemented across four detectors. | ✓ RESOLVED AND TESTED |
| A-03 | Durable async preview enforces exact provider/tree/depth/file/byte/language/sample/time/poll/list bounds and fail-closed terminal behavior. | ✓ RESOLVED AND TESTED |

## SPEC Edge Inventory — 54/54

Every literal edge row is one-to-one with `phase2_spec_edge_matrix.json`, one plan must-have, and at least one collectable executable test node. The two formerly unresolved rows are resolved by A-01/A-02; five explicitly dismissed axes remain tested as non-semantic or deferred-scope invariants.

| Edge | Phase disposition | Current executable evidence | Status |
|---|---|---|---|
| R1-adjacency | tested | `backend/tests/api/test_admin_users.py::test_duplicate_normalized_email_conflicts_without_enumeration_or_secret` | ✓ VERIFIED |
| R1-empty | tested | `backend/tests/integration/test_admin_user_concurrency.py::test_concurrent_cross_deactivation_cannot_remove_the_last_active_admin` | ✓ VERIFIED |
| R1-ordering | tested | `backend/tests/api/test_admin_users.py::test_user_list_has_stable_opaque_default_and_maximum_pagination` | ✓ VERIFIED |
| R1-idempotency | tested | `backend/tests/api/test_admin_users.py::test_admin_updates_roles_then_resets_deactivates_and_reactivates_one_identity` | ✓ VERIFIED |
| R1-concurrency | tested | `backend/tests/integration/test_admin_user_concurrency.py::test_concurrent_cross_role_removal_cannot_remove_the_last_active_admin` | ✓ VERIFIED |
| R2-adjacency | tested | `backend/tests/api/test_admin_users.py::test_role_input_must_be_a_non_empty_subset_of_the_fixed_vocabulary` | ✓ VERIFIED |
| R2-empty | tested | `backend/tests/api/test_admin_users.py::test_role_input_must_be_a_non_empty_subset_of_the_fixed_vocabulary` | ✓ VERIFIED |
| R2-encoding | tested | `backend/tests/api/test_admin_users.py::test_duplicate_normalized_email_conflicts_without_enumeration_or_secret` | ✓ VERIFIED |
| R2-ordering | tested | `backend/tests/api/test_admin_users.py::test_admin_updates_roles_then_resets_deactivates_and_reactivates_one_identity` | ✓ VERIFIED |
| R2-idempotency | tested | `backend/tests/api/test_admin_users.py::test_admin_updates_roles_then_resets_deactivates_and_reactivates_one_identity` | ✓ VERIFIED |
| R2-concurrency | tested | `backend/tests/integration/test_admin_user_concurrency.py::test_concurrent_cross_role_removal_cannot_remove_the_last_active_admin` | ✓ VERIFIED |
| R3-idempotency | tested | `backend/tests/integration/test_admin_user_concurrency.py::test_concurrent_resets_serialize_and_only_the_last_committed_secret_is_valid` | ✓ VERIFIED |
| R3-concurrency | tested | `backend/tests/integration/test_admin_user_concurrency.py::test_concurrent_resets_serialize_and_only_the_last_committed_secret_is_valid` | ✓ VERIFIED |
| R4-empty | tested | `backend/tests/unit/test_product_names.py::test_a01_normalizes_display_and_global_identity_key` | ✓ VERIFIED |
| R4-encoding | resolved-A-01 | `backend/tests/unit/test_product_names.py::test_a01_normalizes_display_and_global_identity_key` | ✓ VERIFIED |
| R4-idempotency | tested | `backend/tests/api/test_admin_products.py::test_expected_version_conflicts_duplicate_name_and_identical_save_are_atomic` | ✓ VERIFIED |
| R4-concurrency | tested | `backend/tests/integration/test_product_publication.py::test_product_lock_linearizes_publish_equal_retry_and_stale_writer` | ✓ VERIFIED |
| R5-idempotency | tested | `backend/tests/integration/test_bitbucket_oauth.py::test_client_credentials_repetition_never_resurrects_generation` | ✓ VERIFIED |
| R5-concurrency | tested | `backend/tests/integration/test_bitbucket_oauth.py::test_client_credentials_rotation_and_revoke_serialize` | ✓ VERIFIED |
| R6-adjacency | tested | `backend/tests/integration/test_repository_registry.py::test_repository_identity_normalizes_lowercase_and_rejects_path_like_input` | ✓ VERIFIED |
| R6-empty | tested | `backend/tests/integration/test_repository_registry.py::test_repository_identity_normalizes_lowercase_and_rejects_path_like_input` | ✓ VERIFIED |
| R6-encoding | tested | `backend/tests/integration/test_repository_registry.py::test_repository_identity_normalizes_lowercase_and_rejects_path_like_input` | ✓ VERIFIED |
| R6-ordering | tested | `backend/tests/api/test_admin_repositories.py::test_repository_collection_is_empty_bounded_opaque_and_exactly_server_ordered` | ✓ VERIFIED |
| R6-idempotency | tested | `backend/tests/integration/test_repository_registry.py::test_sequential_duplicate_conflicts_and_uuid_reuse_is_a_separate_lookup` | ✓ VERIFIED |
| R6-concurrency | tested | `backend/tests/integration/test_repository_registry.py::test_two_session_registration_race_has_one_201_one_409_and_one_row` | ✓ VERIFIED |
| R7-adjacency | tested | `backend/tests/unit/services/test_mappings.py::test_target_set_rejects_empty_malformed_or_nonmember_default_without_mutation` | ✓ VERIFIED |
| R7-empty | tested | `backend/tests/unit/services/test_mappings.py::test_separate_mapping_requires_exact_keys_and_translations_sides` | ✓ VERIFIED |
| R7-encoding | tested | `backend/tests/unit/services/test_mappings.py::test_branches_must_match_current_live_discovery_exactly` | ✓ VERIFIED |
| R7-ordering | dismissed | `backend/tests/unit/services/test_mappings.py::test_target_set_rejects_empty_malformed_or_nonmember_default_without_mutation` | ✓ VERIFIED |
| R7-idempotency | tested | `backend/tests/unit/services/test_mappings.py::test_duplicate_identity_conflicts_while_identical_update_is_a_true_noop` | ✓ VERIFIED |
| R7-concurrency | tested | `backend/tests/unit/services/test_mappings.py::test_duplicate_identity_conflicts_while_identical_update_is_a_true_noop` | ✓ VERIFIED |
| R8-adjacency | tested | `backend/tests/unit/services/test_pr_grouping.py::test_only_exact_repository_and_target_branch_determine_group_identity` | ✓ VERIFIED |
| R8-empty | tested | `backend/tests/unit/services/test_pr_grouping.py::test_empty_input_is_empty_and_grouping_has_no_provider_or_persistence_capability` | ✓ VERIFIED |
| R8-ordering | dismissed | `backend/tests/unit/services/test_pr_grouping.py::test_mapping_file_and_language_permutations_leave_groups_invariant` | ✓ VERIFIED |
| R8-idempotency | tested | `backend/tests/unit/services/test_pr_grouping.py::test_mapping_file_and_language_permutations_leave_groups_invariant` | ✓ VERIFIED |
| R8-concurrency | dismissed | `backend/tests/unit/services/test_pr_grouping.py::test_empty_input_is_empty_and_grouping_has_no_provider_or_persistence_capability` | ✓ VERIFIED |
| R9-adjacency | tested | `backend/tests/integration/test_preview_jobs.py::test_all_four_formats_return_separate_exact_layout_candidates` | ✓ VERIFIED |
| R9-empty | tested | `backend/tests/unit/localization/preview/test_android_xml.py::test_android_empty_names_and_unrelated_files_never_confirm_or_interfere` | ✓ VERIFIED |
| R9-encoding | resolved-A-02 | `backend/tests/unit/localization/preview/test_json.py::test_json_unsupported_shapes_never_confirm` | ✓ VERIFIED |
| R9-ordering | tested | `backend/tests/unit/localization/preview/test_json.py::test_json_file_order_does_not_change_candidate_identity_or_output` | ✓ VERIFIED |
| R9-idempotency | tested | `backend/tests/integration/test_preview_jobs.py::test_succeeded_result_remains_inspectable_but_is_not_current_after_revision_change` | ✓ VERIFIED |
| R9-concurrency | tested | `backend/tests/integration/test_preview_jobs.py::test_new_commit_makes_an_inflight_completion_stale_and_nonconfirmable` | ✓ VERIFIED |
| R10-adjacency | tested | `backend/tests/integration/test_product_publication.py::test_every_mapping_requires_one_current_exact_confirmation` | ✓ VERIFIED |
| R10-empty | tested | `backend/tests/integration/test_product_publication.py::test_closed_blockers_leave_active_and_candidate_graphs_unchanged` | ✓ VERIFIED |
| R10-ordering | dismissed | `backend/tests/integration/test_product_publication.py::test_every_mapping_requires_one_current_exact_confirmation` | ✓ VERIFIED |
| R10-idempotency | tested | `backend/tests/integration/test_product_publication.py::test_product_lock_linearizes_publish_equal_retry_and_stale_writer` | ✓ VERIFIED |
| R10-concurrency | tested | `backend/tests/integration/test_product_publication.py::test_product_lock_linearizes_publish_equal_retry_and_stale_writer` | ✓ VERIFIED |
| R11-adjacency | dismissed | `frontend/src/router.test.tsx::keeps product navigation URL-backed, ordered, singular, and locally contained` | ✓ VERIFIED |
| R11-empty | tested | `frontend/src/features/admin/products/ProductConfiguration.test.tsx::renders stable loading, bounded retry, and exact empty collection states` | ✓ VERIFIED |
| R11-ordering | tested | `frontend/src/features/admin/users/UsersPage.test.tsx::preserves API order and cursor pagination without client re-sorting or de-duplicating` | ✓ VERIFIED |
| R11-idempotency | tested | `frontend/src/features/admin/users/UsersPage.test.tsx::prevents duplicate pending user submissions and sanitizes failure` | ✓ VERIFIED |
| R11-concurrency | tested | `frontend/src/features/admin/products/ProductConfiguration.test.tsx::uses expected candidate version and preserves edits on conflict or failure` | ✓ VERIFIED |
| R12-idempotency | tested | `backend/tests/architecture/test_phase2_scope.py::test_provider_integration_contains_no_dynamic_or_mutating_http_verbs` | ✓ VERIFIED |
| R12-concurrency | tested | `backend/tests/architecture/test_phase2_scope.py::test_provider_integration_contains_no_dynamic_or_mutating_http_verbs` | ✓ VERIFIED |

## Prohibitions — 9/9 Test-Enforced

| ID | Must-NOT contract | Current enforcement evidence | Status |
|---|---|---|---|
| P-01 | MUST NOT expose a temporary password outside its single successful lifecycle response. | Negative API/OpenAPI/log/persistence tests and one-time response projection. | ✓ VERIFIED |
| P-02 | MUST NOT mutate or deactivate the active revision through candidate save/preview/failure. | Published-child constraints and transactional negative integration tests. | ✓ VERIFIED |
| P-03 | MUST NOT expose Bitbucket OAuth credentials or callback secrets outside backend authority. | Secret response/log/browser/persistence scans and backend-only encrypted generations. | ✓ VERIFIED |
| P-04 | MUST NOT couple product-specific mapping state merely because products share a repository. | Composite ownership plus two-product isolation tests. | ✓ VERIFIED |
| P-05 | MUST NOT silently guess ambiguity or combine formats/layouts into one mapping. | Ambiguous/mixed fixtures remain separate blocking candidates. | ✓ VERIFIED |
| P-06 | MUST NOT group changes across repository or target-branch boundaries. | Exact grouping property tests. | ✓ VERIFIED |
| P-07 | MUST NOT present bounded preview samples as exhaustive repository content. | Response metadata and visible partial-sample UI contract. | ✓ VERIFIED |
| P-08 | MUST NOT publish with absent, stale, invalid, disconnected, or unconfirmed preview. | Negative publication matrix and immutable confirmation/currentness gates. | ✓ VERIFIED |
| P-09 | MUST NOT write provider source or canonical import/translation/PR state from Phase 2 preview. | Architecture scans, OpenAPI boundary, provider spy, and five-GET/zero-write runtime audit. | ✓ VERIFIED |

## UI Considerations — 8/8

| Category | Current implementation evidence | Status |
|---|---|---|
| empty | Named empty states exist for resource collections and not-run preview; impossible zero-user authority is an error. | ✓ VERIFIED |
| loading | Geometry-matched Skeletons, `aria-busy` submissions, and durable preview text states are wired. | ✓ VERIFIED |
| error | Owning regions retain recoverable values, sanitize provider detail, focus actionable feedback, and offer approved next steps. | ✓ VERIFIED |
| populated | Deterministic API order, text-first status, one primary CTA, desktop tables, and mobile stacked lists are present. | ✓ VERIFIED |
| partial | Candidate/active distinction, mapping blockers, and explicit partial-sample labeling are visible. | ✓ VERIFIED |
| overflow | Wrapping actions, local file/sample scrolling, stacked mobile lists, and 320px no-page-overflow behavior are exercised. | ✓ VERIFIED |
| zero-one-many | Named zero copy, singular grammar, cursor pagination, and explicit one-mapping confirmation are covered. | ✓ VERIFIED |
| long-text | Wrapping prose, `overflow-wrap:anywhere` opaque values, copy access, full action labels, and tooltip-backed nav truncation are covered. | ✓ VERIFIED |

Dirty product and mapping transitions additionally have behavior-level router tests for Link, Back, reload, values, focus, and 320px Sheet interaction; therefore no UI transition remains merely presence-verified.

## Bitbucket Capability Dispositions — 44/44

The capability contract contains nine exact integrations and 35 reasoned opt-outs. The executable coverage rewrite proves the three client-credentials replacements without semantic loss, and every opt-out retains a nonempty least-privilege reason.

| Capability | Decision | Current evidence / least-privilege reason | Status |
|---|---|---|---|
| `oauth-client-credentials-acquisition` | INTEGRATE | Exact bounded Basic-auth client-credentials exchange. | ✓ VERIFIED |
| `oauth-client-credentials-reacquisition` | INTEGRATE | New client-credentials exchange rotates to a fresh encrypted generation. | ✓ VERIFIED |
| `oauth-authorization-code-callback-and-refresh-token-flows` | OPT-OUT | Server-to-server credentials have no browser callback or refresh-token authority. | ✓ VERIFIED |
| `oauth-effective-scope-inspection` | INTEGRATE | Live effective scope must equal exactly `repository`. | ✓ VERIFIED |
| `repository-metadata-by-workspace-and-slug` | INTEGRATE | Explicit configured repository identity is resolved and verified. | ✓ VERIFIED |
| `branch-listing-with-provider-pagination` | INTEGRATE | Bounded provider cursors are collected through validated next URLs. | ✓ VERIFIED |
| `branch-to-commit-resolution` | INTEGRATE | Exact branch detail, returned-name equality, and exact commit binding close CR-14. | ✓ VERIFIED |
| `source-tree-directory-pagination` | INTEGRATE | Commit-bound traversal enforces page/entry/depth budgets. | ✓ VERIFIED |
| `raw-source-file-read-at-commit` | INTEGRATE | Streamed commit-bound GET enforces byte and timeout budgets. | ✓ VERIFIED |
| `provider-next-url-validation` | INTEGRATE | Scheme, host, path family, cursor, and redirect constraints are enforced. | ✓ VERIFIED |
| `oauth-provider-side-token-revocation` | OPT-OUT | No verified provider revoke endpoint; local generation invalidation is immediate. | ✓ VERIFIED |
| `repository-listing-and-search` | OPT-OUT | Explicit workspace/slug registration avoids broad discovery authority. | ✓ VERIFIED |
| `account-profile-and-email` | OPT-OUT | Preview needs no account/email scope. | ✓ VERIFIED |
| `workspace-membership-and-permissions` | OPT-OUT | Organization membership administration is outside Phase 2. | ✓ VERIFIED |
| `project-listing-and-metadata` | OPT-OUT | Products bind configured repositories directly. | ✓ VERIFIED |
| `workspace-and-project-administration` | OPT-OUT | The connection is a read-only repository consumer. | ✓ VERIFIED |
| `tag-listing-and-other-ref-discovery` | OPT-OUT | Only configured branches are valid mapping inputs. | ✓ VERIFIED |
| `commit-history-listing-and-search` | OPT-OUT | Preview resolves one selected branch commit. | ✓ VERIFIED |
| `commit-diff-diffstat-and-patch-read` | OPT-OUT | Preview reads one commit and performs no comparison. | ✓ VERIFIED |
| `commit-status-read-and-write` | OPT-OUT | Build/status authority is unrelated to configuration preview. | ✓ VERIFIED |
| `source-file-create-update-delete` | OPT-OUT | Provider writes are deferred and require explicit reauthorization. | ✓ VERIFIED |
| `branch-create-update-delete` | OPT-OUT | Phase 2 lists branches but cannot mutate them. | ✓ VERIFIED |
| `tag-create-update-delete` | OPT-OUT | Tag mutation is outside the workflow. | ✓ VERIFIED |
| `commit-create` | OPT-OUT | Read-only validation cannot create commits. | ✓ VERIFIED |
| `pull-request-list-and-read` | OPT-OUT | No provider PR resource is needed for configuration preview. | ✓ VERIFIED |
| `pull-request-create-and-update` | OPT-OUT | Later submission owns PR write authority and reauthorization. | ✓ VERIFIED |
| `pull-request-merge-decline-and-approve` | OPT-OUT | Provider PR workflow actions are out of Phase 2 scope. | ✓ VERIFIED |
| `pull-request-comments-tasks-and-activity` | OPT-OUT | Review context remains application-owned. | ✓ VERIFIED |
| `pull-request-diff-and-diffstat` | OPT-OUT | Phase 2 has no provider PR or write-back diff. | ✓ VERIFIED |
| `repository-webhook-list-and-read` | OPT-OUT | Preview is explicit and polling-based. | ✓ VERIFIED |
| `repository-webhook-create-update-delete` | OPT-OUT | Webhook administration requires unrelated authority. | ✓ VERIFIED |
| `repository-settings-and-permissions-admin` | OPT-OUT | The least-privilege reader never modifies repository settings. | ✓ VERIFIED |
| `branch-restrictions-and-merge-checks-admin` | OPT-OUT | App target configuration does not administer provider policy. | ✓ VERIFIED |
| `deploy-keys-access-keys-and-ssh-keys-admin` | OPT-OUT | OAuth is the locked credential model. | ✓ VERIFIED |
| `pipelines-list-and-read` | OPT-OUT | CI state is not needed for configuration preview. | ✓ VERIFIED |
| `pipelines-run-stop-and-manage` | OPT-OUT | Phase 2 cannot trigger provider pipelines. | ✓ VERIFIED |
| `deployments-and-environments` | OPT-OUT | Deployment metadata is unrelated to localization configuration. | ✓ VERIFIED |
| `issues-list-and-read` | OPT-OUT | Bitbucket issues are not localization sources. | ✓ VERIFIED |
| `issues-create-update-delete-and-comments` | OPT-OUT | No issue mutation authority is requested. | ✓ VERIFIED |
| `downloads-list-and-read` | OPT-OUT | Sources come from the repository source API. | ✓ VERIFIED |
| `downloads-upload-and-delete` | OPT-OUT | Phase 2 performs no provider artifact mutation. | ✓ VERIFIED |
| `wiki-read-and-write` | OPT-OUT | Wiki content is not localization discovery input. | ✓ VERIFIED |
| `snippets-read-and-write` | OPT-OUT | Snippets are not configurable localization repositories. | ✓ VERIFIED |
| `code-search` | OPT-OUT | Discovery uses bounded selected-repository traversal, not provider-wide search. | ✓ VERIFIED |

## Current Review Inventory — 23/23

The table below is authoritative for this verifier. It preserves the structured review's exact status/count relationship: zero open Critical rows and six open Warning rows.

| Row | Disposition | Severity | Current production/evidence anchor | Verifier result |
|---|---|---|---|---|
| CR-01 | CLOSED | CRITICAL | Shared backend/worker/scheduler provider environment in base Compose. | ✓ VERIFIED |
| CR-02 | CLOSED | CRITICAL | Exact bounded Basic-auth client-credentials exchange. | ✓ VERIFIED |
| CR-03 | CLOSED | CRITICAL | Callback, authorization-code, and refresh-token authority absent. | ✓ VERIFIED |
| CR-04 | CLOSED | CRITICAL | Access-only encrypted generations, serialized renewal, and post-I/O generation checks. | ✓ VERIFIED; WR-03 retained |
| CR-05 | CLOSED | CRITICAL | Complete fresh-ID candidate graph clone and atomic identity promotion. | ✓ VERIFIED |
| CR-06 | CLOSED | CRITICAL | Immutable active-revision sidecar revalidation/reactivation. | ✓ VERIFIED |
| CR-07 | CLOSED | CRITICAL | Persistent five-step mobile wizard controls at 320px. | ✓ VERIFIED |
| CR-08 | CLOSED | CRITICAL | Cursor collection rejects stale pages and waits for terminal completeness. | ✓ VERIFIED |
| CR-09 | CLOSED | CRITICAL | Watchdog CAS, bounded stale batch, and retry-attempt isolation. | ✓ VERIFIED |
| CR-10 | CLOSED | CRITICAL | HTTP/CLI destructive paths share admin lock and survivor predicate. | ✓ VERIFIED |
| CR-11 | CLOSED | CRITICAL | Separate Beat scheduler exists in base, staging, and production overlays. | ✓ VERIFIED |
| CR-12 | CLOSED | CRITICAL | Immutable active-revalidation currentness and recovery authority. | ✓ VERIFIED |
| CR-13 | CLOSED | CRITICAL | Complete runtime CSP, `frame-ancestors 'none'`, XFO DENY, and defensive headers. | ✓ VERIFIED |
| CR-14 | CLOSED | CRITICAL | Exact-detail candidate/active direct/separate branch 101+, exact name, role-bound commit, worker recheck, zero writes. | ✓ VERIFIED |
| CR-15 | CLOSED | CRITICAL | Shared pre-transition router blocker, separate beforeunload, values/focus, one destination, Link/Back/mobile coverage. | ✓ VERIFIED |
| WR-01 | CLOSED | WARNING | Workspace overview and location-authoritative shell. | ✓ VERIFIED |
| WR-02 | CLOSED | WARNING | Composite ownership FKs and published-child immutability triggers. | ✓ VERIFIED |
| WR-03 | OPEN | WARNING | Unbounded positive `expires_in` can overflow persistence arithmetic. | ⚠ RETAINED OPEN WARNING |
| WR-04 | OPEN | WARNING | Development Stryker chain retains two moderate advisory records. | ⚠ RETAINED OPEN WARNING |
| WR-05 | OPEN | WARNING | Docker/Compose image selectors remain tag-only, without digest pins. | ⚠ RETAINED OPEN WARNING |
| WR-06 | OPEN | WARNING | `.env.example` omits seven Phase 2 provider/watchdog settings. | ⚠ RETAINED OPEN WARNING |
| WR-07 | OPEN | WARNING | Executable edge-matrix JSON remains outside the source manifest digest. | ⚠ RETAINED OPEN WARNING |
| WR-08 | OPEN | WARNING | Deferred no-flag Compose path calls removed OAuth routes; supported `--gap-closure` does not invoke it. | ⚠ RETAINED OPEN WARNING — DEFERRED, NOT FIXED |

## Behavioral Spot-Checks

| Behavior | Command/evidence | Result | Status |
|---|---|---|---|
| Structured closure contract | `cd backend && uv run pytest -q tests/architecture/test_phase2_gap_closure.py -x` | 8/8 passed | ✓ PASS |
| CR-14 exact-detail branch authority | Focused preview tests plus direct source trace through generated detail and worker recheck | Candidate/active direct/separate branch 101+ succeeds; mismatch fails closed | ✓ PASS |
| CR-15 router transaction authority | Focused unit/real-router/browser paths | Link, Back, reload, values, focus, one destination, and 320px Sheet covered | ✓ PASS |
| Official post-canonical quality gate | `bash tools/phase2_gauntlet.sh --gap-closure` recorded against final digest | 18/18; digest unchanged; zero residual owned resources | ✓ PASS |
| Review-source binding | `tools/source_state.sh --verify-review-source` | Exact review digest accepted | ✓ PASS |
| Final report-source binding | `tools/source_state.sh --verify-report-digest` | Exact final digest accepted | ✓ PASS |

## Probe Execution

Step 7c: SKIPPED — no phase-declared or conventional `scripts/**/tests/probe-*.sh` probe exists. Phase 2 uses named tests, the ordered gauntlet, deployment smoke, provider/browser smoke, and source-state checks.

## Test Quality Audit

| Test authority | Linked scope | Active/skipped | Circularity | Assertion level | Verdict |
|---|---|---|---|---|---|
| Phase 2 semantic inventory and negative mutants | Goal, requirements, decisions, assumptions, edges, prohibitions, UI, capabilities, review/verifier schemas | Active; 0 disabled | No circular expected-value generation | Value + mutation rejection | ✓ VALID |
| Product/user/repository/mapping/publication integration nodes | AUTH-02/03, PROD-01..07 | Active; 0 requirement-only skips | Independent database and concurrency outcomes | Behavioral | ✓ VALID |
| Preview/detector/worker/property nodes | PROD-08/09, BITB-03/04, A-02/A-03, R9/R10/R12 | Active | Independent fixtures/properties and provider spy | Behavioral + value | ✓ VALID |
| CR-14 exact-detail coverage | PROD-08, BITB-03 | Active | Provider fixture is external to production resolver | Behavioral call/result/fail-closed assertions | ✓ VALID |
| CR-15 real-router/browser coverage | UI-03 | Active | Real data router and DOM interactions | Behavioral transition/value/focus assertions | ✓ VALID |
| Changed-scope and mutation gates | Current implementation diff | Active | Mutants are generated changes, not expected-value oracles | Coverage + kill outcome | ✓ VALID |

**Disabled requirement tests:** 0.

**Circular expected-value generators:** 0.

**Insufficient behavior assertions:** 0 for roadmap success criteria.

## Anti-Patterns and Prohibition Scan

No missing, stub, orphaned, hollow, or disconnected must-have artifact remains. No unreferenced `TBD`, `FIXME`, or `XXX` marker blocks completion. No provider write, canonical translation/import/PR write, hidden Critical, disabled sole-authority test, or false passed inventory was found. The six explicit warnings above remain visible and do not become silent passes.

## Human Verification Required

None. The user-facing state transitions that previously required caution now have executable real-router/browser evidence, including the behavior-dependent cancellation, ordering, cleanup, values, and focus invariants. Visual/UAT is not being used to substitute for a missing automated contract.

## Deferred Items

WR-08 is explicitly deferred and remains **OPEN — WARNING**. This verifier does not claim it was repaired. WR-03 through WR-07 also remain open warnings for later hardening. These warnings do not mask an unmet Phase 2 roadmap truth and do not alter the passed status under the current High blocking threshold.

## Gaps Summary

No blocking gaps remain. CR-14 and CR-15 are closed by reachable current production paths and behavioral evidence; all inventory totals are complete; `gaps: []`; no human-verification item remains.

---

_Verified: 2026-09-01T18:09:09Z_

_Verifier: the agent (fresh independent gsd-verifier, compact continuation)_
