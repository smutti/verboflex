---
status: resolved
trigger: "Procedi con le correzioni dei gap post-remediation WR-11, WR-12, WR-13 e WR-14"
created: 2026-09-03T21:09:36Z
updated: 2026-09-04T07:43:46Z
---

## Current Focus

hypothesis: Resolved and human-confirmed: incomplete canonical selector ownership plus missing lifecycle/session invalidation caused WR-11 through WR-14.
test: Commit the archived session and durable knowledge-base entry with exact file lists under `commit_docs: true`.
expecting: Two documentation commits contain only their named debug artifact; review and user-owned paths remain unstaged and untouched.
next_action: Run exact-file GSD commits for the resolved session and knowledge base, inspect commit contents/status, and return DEBUG COMPLETE.
bug_class: bohrbug
known_pattern_candidate: "phase3-nyquist-regressions — prior live-authority and responsive-focus fixes were one-off proven, but the durable gate and lifecycle edges remained outside their exact scope"
hypothesis_branches:
  - "code: same rendered import identity remains authoritative after access-token replacement/unmount because mutation ownership has no lifecycle abort/token invalidation"
  - "config: canonical Playwright and Stryker selectors enumerate an incomplete proof surface"
  - "environment: stale port or AbortController differences could confound observation, but JSDOM deferred promises and script parsing are environment-independent controls"
  - "data: access-token-only replacement is the minimal identity boundary; unchanged token/import/product is the live neighbor"
and_gate_candidate: "No per finding: each omitted selector or missing lifecycle invalidation is independently sufficient; all four OR branches must close for aggregate acceptance."
reasoning_checkpoint:
  hypothesis: "WR-11/12 occur because the canonical selectors enumerate only two browser IDs and legacy line coordinates; WR-13/14 occur because deferred mutation authority is keyed only to render identity/request tokens and neither mutation owns an AbortController invalidated on token replacement or unmount."
  confirming_evidence:
    - "The committed architecture RED observes exact grep IDs UI3-C23/UI3-C26 and no FRONTEND_MUTATION_MARKERS registry."
    - "The committed lifecycle RED directly observes undefined mutation signals and obsolete pending state after access-token-only replacement."
    - "Complete source tracing shows accessToken absent from rewrite importIdentity, confirmationRequestRef never invalidated by cleanup, and Published cleanup aborting only collection controllerRef."
    - "Generated operation Options extend Fetch RequestInit, directly proving both mutation calls accept AbortSignal without client changes."
  falsification_test: "The hypothesis is false if adding only selector ownership and lifecycle-bound AbortController/token invalidation does not green the unchanged RED tests, or if reverting those minimal production/gate hunks does not restore the same failures."
  fix_rationale: "Stable test IDs/semantic markers make the canonical gate own the intended proof surface; dedicated controllers plus live identity/token predicates make cleanup revoke the originating request's authority before any callback, toast, close, focus, refresh, or finalization."
  blind_spots: "Marker-selected mutant counts are unknown until direct Stryker runs; real-browser selection, full frontend adjacency, static/build checks, and the 14-layer canonical gauntlet remain unverified."
  candidate_causes:
    - "code: missing mutation-controller cleanup, accessToken authority membership, and combined live identity/request-token predicates"
    - "config: incomplete Playwright grep and Stryker ownership registry"
    - "environment: stale default Vite server could affect browser execution, mitigated by the gauntlet's isolated random port"
    - "data: access-token-only replacement is the minimal invalidating input, while unchanged authority is the live boundary neighbor"
  and_gate: "No within each finding: each selector omission or lifecycle-authority omission independently reproduces its warning. Yes for aggregate closeout: all four independent OR branches must pass the single canonical acceptance gate."
tdd_checkpoint:
  status: green
  test_commit: a0d2dc2
  fix_commits: [6ca073b, ecf2880]
  red_failures: "architecture 2 failed/5 passed; frontend 3 failed/27 passed"
  green_results: "architecture 7/7; focused/adjacent frontend 51/51; exact Stryker 42/42; Playwright 3/3; canonical gauntlet 14/14"

## Symptoms

expected: The canonical gauntlet selects all three Phase 3 browser regressions and retains mutation ownership for authority/request/commit predicates; obsolete confirmation/import completions have no effects after token replacement or unmount.
actual: The browser grep selects only two tests, canonical mutation ownership omits remediation predicates, confirmation survives token-only replacement/unmount, and start-import survives unmount.
errors: WR-11, WR-12, WR-13, and WR-14 are active warnings in the independent post-remediation review.
reproduction: Use the exact source locations and reproduction requirements recorded in .planning/phases/03-bitbucket-import-integration/03-REVIEW.md.
started: Discovered by the 2026-09-03 independent Nyquist remediation review.

## Eliminated

None.

## Evidence

- timestamp: 2026-09-03T21:09:36Z
  checked: Independent review findings and current worktree status.
  found: WR-11 through WR-14 are documented in a concurrently modified review report; only that report and explicitly excluded user runtime paths are dirty.
  implication: The new session must treat the report as read-only evidence and scope commits to tests, implementation, canonical gate, and this session ledger.
- timestamp: 2026-09-03T21:09:36Z
  checked: Prior resolved Nyquist session.
  found: WR-01 through WR-10 are resolved and archived separately; its 14/14 digest predates the four new review findings.
  implication: This investigation requires a new persistent session and a fresh final digest without reopening the resolved ledger.
- timestamp: 2026-09-03T21:11:27Z
  checked: Phase-0 semantic recall capability and durable debug knowledge base.
  found: MemPalace is not installed/configured, so fallback keyword/identifier matching surfaced `phase3-nyquist-regressions`; it records live-authority, request-token, committed-state, and responsive-focus fixes, but explicitly scopes lifecycle/unmount and retained canonical ownership outside that resolved session.
  implication: Treat the prior resolution as a high-probability candidate only; the new WR-11 through WR-14 tests must directly prove the uncovered gate and lifecycle boundaries.
- timestamp: 2026-09-03T21:16:02Z
  checked: Complete owned gauntlet, architecture contract, Playwright specification, both import components, and both unit suites.
  found: The browser test has no stable UI ID while the gate greps only UI3-C23/UI3-C26; the Stryker selector and exact report registry own only polling, labels, cursor termination, and missing data; confirmation identity excludes accessToken and has no confirmation cleanup/controller; start-import cleanup aborts only collection work and leaves pending mutation tokens live.
  implication: All four findings have direct source-level support and fit deterministic specified-oracle regressions; generated-client signal capability and exact mutation predicate boundaries remain to be confirmed.
- timestamp: 2026-09-03T21:16:30Z
  checked: Generated Hey API operation options and current mutation tooling.
  found: Both start-import and rewrite-confirmation accept `Options` extending Fetch `RequestInit`, so dedicated AbortSignals are supported; existing Stryker uses exact line selectors and the prior one-off fix-site scope was not retained.
  implication: Lifecycle cleanup can abort real requests without generated-code changes, while stable semantic marker resolution can replace brittle raw coordinates for the newly owned predicates.
- timestamp: 2026-09-03T21:16:30Z
  checked: SBFL Phase 1.25 preconditions.
  found: Runnable failing/passing suites exist after regressions are added, but the project emits aggregate rather than per-test execution coverage, so no Ochiai spectrum can be computed.
  implication: SBFL is explicitly skipped; deterministic architecture and deferred-promise tests directly localize the four Bohrbug boundaries.
- timestamp: 2026-09-03T21:17:40Z
  checked: Unchanged focused control suites before RED authoring.
  found: Phase 3 gauntlet architecture passes 5/5 and the two import component suites pass 27/27.
  implication: Any subsequent focused failures are attributable to the newly specified WR-11 through WR-14 boundaries rather than an already-broken baseline.
- timestamp: 2026-09-03T21:19:10Z
  checked: First strict RED run after adding only agent-authored tests and the stable browser-test ID.
  found: Architecture is exactly 2 failed/5 passed: canonical grep selects UI3-C23/UI3-C26 but omits UI3-C27, and no semantic mutation marker registry exists. Frontend is exactly 3 failed/27 passed: start-import and confirmation calls expose no AbortSignal, and access-token-only rerender leaves the replacement confirmation disabled by obsolete pending state.
  implication: WR-11 through WR-14 reproduce deterministically at their specified selection/authority boundaries; production and canonical gate implementation may proceed after committing this RED evidence.
- timestamp: 2026-09-03T21:20:05Z
  checked: RED diff static/format pre-commit checks.
  found: Ruff lint and git whitespace checks pass; Ruff formatter requests two mechanical Python compactions and Prettier requests formatting in the two TSX unit tests.
  implication: No semantic revision is needed; run repository formatters before the RED commit and reconfirm identical failures.
- timestamp: 2026-09-03T21:23:20Z
  checked: RED evidence commit and first isolated GREEN boundary.
  found: Commit `a0d2dc2` contains only the four regression files. PublishedMappingImports now gives each start mutation an AbortController, invalidates/clears owned tokens on authority cleanup, checks live authority plus exact request-token ownership, and passes 18/18 focused tests.
  implication: WR-14 is green in isolation; the unchanged Rewritten tests remain the next independent code boundary before canonical selector work.
- timestamp: 2026-09-03T21:24:30Z
  checked: RewrittenBaselineDialog lifecycle implementation and focused suite.
  found: accessToken now participates in confirmation identity; a dedicated controller is aborted and its request token invalidated on identity replacement, close, or unmount; generated confirmation receives its signal; the live authority/token and uncommitted-finalization predicates have stable markers; all 12 dialog tests pass.
  implication: WR-13 is green in isolation, including token-only replacement and unmount; only WR-11/12 canonical gate ownership remains RED.
- timestamp: 2026-09-03T21:27:10Z
  checked: Canonical selector implementation, shell syntax, whitespace, and architecture contract.
  found: The gauntlet now owns exactly four semantic markers, resolves each to its following predicate line, merges those lines into exact report ownership, updates shifted legacy targets, and greps UI3-C23/UI3-C26/UI3-C27; shell syntax and diff whitespace pass and architecture is 7/7.
  implication: WR-11/12 structural contracts are green; direct Stryker and isolated Playwright execution must prove the selected semantics rather than only their declarations.
- timestamp: 2026-09-03T21:28:20Z
  checked: First combined focused behavior and static verification.
  found: Component tests pass 30/30, TypeScript passes, architecture/Ruff/shell checks pass, but ESLint rejects one exhaustive-deps warning because the effect cleanup reads `pendingRef.current` directly.
  implication: Runtime behavior is green, but guardrail acceptance requires an effect-local stable map reference before mutation and browser checks.
- timestamp: 2026-09-03T21:29:20Z
  checked: Effect-local cleanup revision and complete focused frontend rerun.
  found: The stable pending-request map capture clears ESLint; 30/30 component tests, TypeScript, ESLint, and Prettier all pass.
  implication: Target and adjacent focused signals are green; exact mutation ownership is the next acceptance signal.
- timestamp: 2026-09-03T21:31:00Z
  checked: First canonical marker-resolved Stryker invocation.
  found: The resolver selected legacy targets plus Published lines 1042/1050 and Rewritten lines 644/653, instrumenting 42 mutants. Stryker stopped at its initial full-Vitest dry run because `ProductMappingsPage.test.tsx` still expects the older exact start-import call without the newly supported AbortSignal.
  implication: Mutation results are not yet valid; this is an adjacent contract adaptation outside current file ownership, not a surviving mutant. Parent ownership expansion was requested before changing that test.
- timestamp: 2026-09-03T21:32:00Z
  checked: Parent coordination for the adjacent dry-run failure.
  found: Ownership was explicitly expanded to the single `ProductMappingsPage.test.tsx` assertion; it now expects the generated call's AbortSignal and no other adjacent behavior changed.
  implication: Focused adjacency and canonical mutation verification may resume without exceeding file ownership.
- timestamp: 2026-09-03T21:32:10Z
  checked: Persistent marker-resolved Stryker rerun after the adjacent generated-call adaptation.
  found: The full dry run passes 363 tests and exactly 42 mutants execute, but mutation score is 78.57%, meaning nine semantic mutants remain non-killed.
  implication: Canonical mutation ownership is active and measurable, but its newly retained predicates need explicit boundary-neighbor oracles before WR-12 can be accepted.
- timestamp: 2026-09-03T21:32:20Z
  checked: Every non-killed mutant in the persistent Stryker JSON.
  found: Two survivors replace the Published authority/token equalities with true; four survivors weaken or constant-replace the rewrite authority-and-token conjunction; three survivors constant-replace or invert the uncommitted finalization identity predicate.
  implication: The implementation boundary is localized and the missing guard is explicit truth-table coverage of each pure predicate's false neighbors, not a production control-flow change.
- timestamp: 2026-09-03T21:32:30Z
  checked: Direct specified-oracle truth tables for all four marker-owned predicates.
  found: Live/mismatched identity, owned/obsolete/undefined token, and committed/uncommitted neighbors pass alongside every deferred component regression: 34/34 focused tests green and Prettier clean.
  implication: The predicate surface is now independently executable; rerunning the unchanged exact mutation selector will determine whether every weakened branch is detected.
- timestamp: 2026-09-03T21:32:40Z
  checked: Second unchanged exact marker-resolved Stryker execution.
  found: The full dry run passes 367 tests and the same 42 mutants execute; all 42 are killed for a 100.00 mutation score with the breaking threshold still 100.
  implication: Truth-table neighbors close every observed semantic survivor; the gate's independent exact-location assertion and browser selection remain to verify.
- timestamp: 2026-09-03T21:32:50Z
  checked: Canonical exact mutation-report assertion and isolated Playwright selection/execution.
  found: `assert_stryker_report` accepts exactly 42/42 killed at the expected legacy and marker-resolved locations. The grep lists exactly UI3-C27, UI3-C23, UI3-C26 and all 3/3 pass against a fresh random-port Vite process.
  implication: WR-11 browser ownership and WR-12 mutation ownership are behaviorally proven; pre-commit adjacency and the causal revert guardrail remain before the full gauntlet.
- timestamp: 2026-09-03T21:33:00Z
  checked: Complete pre-commit focused and static suite.
  found: Architecture is 7/7, frontend behavior is 51/51, typecheck/shell/whitespace are green, but ESLint reports four `react-refresh/only-export-components` warnings because the mutation-testable pure predicates were exported from component modules.
  implication: Guardrail acceptance is blocked; move those helpers and truth tables into the explicitly allowed narrow helper module rather than suppressing lint or weakening mutation ownership.
- timestamp: 2026-09-03T21:33:10Z
  checked: Dedicated mutation-authority helper extraction and full focused/static rerun.
  found: The components again export only components, all four predicate truth tables live in a focused helper test, architecture is 7/7, frontend is 51/51, and typecheck, ESLint, Prettier, Ruff, and shell syntax pass.
  implication: The lint blocker is resolved without suppression; exact Stryker ownership must be reconfirmed at the helper's marker-resolved lines.
- timestamp: 2026-09-03T21:33:20Z
  checked: First exact Stryker run and canonical report assertion after helper extraction.
  found: Semantic markers re-resolve and all 35 selected mutants are killed, but the exact report assertion correctly fails: adding helper imports shifted the legacy Published cursor line from 526 to 530 and rewrite missing-data line from 431 to 435, leaving the old raw selectors with only incidental or zero mutants.
  implication: The semantic marker mechanism is refactor-stable, while the two pre-existing raw legacy selectors must be updated to their verified statements before the canonical ownership proof is valid.
- timestamp: 2026-09-03T21:33:30Z
  checked: Exact Stryker rerun after correcting cursor and missing-data coordinates.
  found: All 38 executed mutants are killed, and the exact-location assertion now restores cursor/missing-data ownership but still rejects action ownership: the helper import shifted action values from lines 77-81 to 81-85, while the old range selects only line 81.
  implication: One final raw-coordinate correction is required; this also demonstrates why the newly remediated predicates use semantic markers rather than raw lines.
- timestamp: 2026-09-03T21:33:40Z
  checked: Final exact Stryker run after all verified legacy coordinates and semantic marker locations were aligned.
  found: Stryker executes exactly 42 mutants across action, cursor, missing-data, polling, and four marker-owned authority predicates; all 42 are killed, and the independent exact-location report assertion passes.
  implication: WR-12 now has both 100% mutation behavior and exact retained source ownership; commit and causal revert remain before the full canonical gauntlet.
- timestamp: 2026-09-03T21:33:50Z
  checked: Atomic GREEN implementation commit.
  found: Commit `6ca073b` contains exactly nine authorized implementation, canonical-gate, helper, focused-test, architecture-contract, and adjacent generated-call adaptation files; the RED test commit remains independently at `a0d2dc2`.
  implication: The fix-acceptance causal signal can now revert only the GREEN commit without touching the pre-existing review or user-owned untracked paths.
- timestamp: 2026-09-03T21:34:00Z
  checked: Fix-acceptance causal revert of commit `6ca073b`.
  found: With only the GREEN commit reversed, architecture returns to exactly 2 failed/5 passed (missing UI3-C27 grep and marker registry) and frontend returns to exactly 3 failed/27 passed (undefined AbortSignals and token-only replacement still pending).
  implication: The original defects causally return when the fix is removed, satisfying the revert-and-reconfirm signal; restore the exact committed paths and reconfirm GREEN.
- timestamp: 2026-09-03T21:34:10Z
  checked: Exact restoration after causal revert and full focused/static acceptance rerun.
  found: Worktree code is restored exactly to HEAD; architecture passes 7/7, all four focused/adjacent frontend files pass 51/51, and TypeScript, ESLint, Prettier, Ruff, shell syntax, and whitespace checks all pass.
  implication: Fix-acceptance signals 1-5 are satisfied locally; the single canonical 14-layer Phase 3 gauntlet is the remaining machine-verifiable acceptance gate.
- timestamp: 2026-09-03T21:34:20Z
  checked: First fresh canonical Phase 3 gauntlet at digest `0275cacd5d10c1b3326984b12ae6812740070f8120bed07ad7055dfdcd66c905`.
  found: Source-state passes, but checker-negative-controls rejects `UI3-C27` as an extra item because `UI3-C##` is a locked planning consideration namespace with exactly 26 owners; the mobile focus regression needs a stable browser tag, not a new planning consideration.
  implication: Use a distinct stable Playwright namespace (`PW3-C27`) in the three owned selector/title contracts; do not modify or weaken the locked Phase 3 scope architecture test.
- timestamp: 2026-09-03T21:34:30Z
  checked: Browser-only `PW3-C27` tag correction across the owned title, grep, and exact selector contract.
  found: The full architecture corpus passes 58/58; exact discovery lists three tests; isolated random-port Playwright passes 3/3 including PW3-C27; shell syntax and whitespace remain clean.
  implication: WR-11 has a stable canonical browser tag without corrupting the locked planning consideration namespace; commit and rerun the full canonical gate.
- timestamp: 2026-09-03T21:34:40Z
  checked: Full canonical Phase 3 acceptance gauntlet after commit `ecf2880`.
  found: All 14/14 ordered layers pass in 478 seconds at unchanged source digest `0227a4fbd295caf78a676cb798e5cabf378710884d1418a5262df7bf33512534`; this includes backend 958/958 at 95% coverage, frontend 367/367, backend mutations 6/6, exact frontend mutations 42/42, Playwright 3/3, supply-chain/schema, architecture/provider audit, deployment smoke, and final source-state equality.
  implication: Every required machine-verifiable acceptance signal is green; inspect persistent records and final repository state before handing off the human verification checkpoint.
- timestamp: 2026-09-03T21:34:50Z
  checked: Persistent gauntlet records, recent commits, and final worktree state.
  found: Digest/result agree on `0227a4fbd295caf78a676cb798e5cabf378710884d1418a5262df7bf33512534`, the layer record contains exactly 14 ordered entries, and commits `a0d2dc2`, `6ca073b`, and `ecf2880` are present. Status contains only the pre-existing modified `03-REVIEW.md`, user-owned `.gsd/`, `.planning/agent-history.json`, `graphify-out/`, and this active debug ledger.
  implication: No implementation or gate edits remain uncommitted and no unrelated user-owned state was altered; machine verification is complete and the session may await human confirmation.
- timestamp: 2026-09-04T07:41:24Z
  checked: Human verification checkpoint response.
  found: The user confirmed the corrected workflow is fixed in the real environment.
  implication: The session satisfies both machine and human verification and may be archived with its prevention record.
- timestamp: 2026-09-04T07:43:46Z
  checked: Archive path, prevention block, durable KB entry, and planning commit configuration.
  found: The resolved ledger is under `.planning/debug/resolved/`, the KB entry records why the gap escaped and the verified recurrence guards, `commit_docs` is true, and MemPalace is disabled so the markdown knowledge base is the durable fallback.
  implication: Commit exactly the resolved session and knowledge base as separate debug-artifact commits; no semantic index action is applicable.

## Resolution

root_cause: "WR-11: the canonical Playwright grep omitted the mobile-focus test's stable browser tag; WR-12: canonical Stryker ownership was bound only to legacy raw coordinates and omitted the live-authority/request-token/committed-state predicates; WR-13: confirmation identity excluded accessToken and had no mutation controller/token cleanup on authority replacement or unmount; WR-14: start-import owned no AbortSignal and its cleanup left pending tokens authoritative after unmount."
fix: "Added the PW3-C27 browser tag and exact three-test grep; introduced a semantic marker registry and extracted mutation-authority predicates with full truth tables; bound confirmation authority to accessToken and lifecycle-owned AbortController/request tokens; bound start-import mutations to lifecycle-owned AbortControllers and cleanup invalidation; adapted the one adjacent generated-call assertion."
verification:
  target_test: {result: pass}
  mutation_check: {result: pass, mutant_killed: "42/42 exact frontend plus 6/6 backend"}
  no_op_deletion: {result: pass, deletion_justified_by_rca: false}
  adjacent_tests:
    result: pass
    suites_run: ["focused frontend 51/51", "architecture 58/58", "full frontend 367/367", "full backend 958/958"]
  revert_and_reconfirm: {result: pass, bug_returned_on_revert: true, fixed_on_reapply: true}
  canonical_gauntlet: {result: pass, layers: "14/14", duration_seconds: 478, source_digest: "0227a4fbd295caf78a676cb798e5cabf378710884d1418a5262df7bf33512534"}
  human_verification: {result: pass, confirmed_at: "2026-09-04T07:41:24Z"}
  guardrail_verdict: accepted
oracle_type: specified
files_changed:
  - backend/tests/architecture/test_phase3_gauntlet.py
  - frontend/e2e/admin-configuration.spec.ts
  - frontend/src/features/admin/imports/PublishedMappingImports.tsx
  - frontend/src/features/admin/imports/PublishedMappingImports.test.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx
  - frontend/src/features/admin/imports/mutationAuthority.ts
  - frontend/src/features/admin/imports/mutationAuthority.test.ts
  - frontend/src/features/admin/mappings/ProductMappingsPage.test.tsx
  - tools/phase3_gauntlet.sh

## Prevention

why_not_caught: "The existing canonical gate ran unit, mutation, and browser checks, but its selectors did not include the mobile-focus regression or the live-authority/request-token/committed-state predicates, and no deferred access-token-replacement or unmount tests existed. Type, lint, build, and happy-path tests cannot prove async lifecycle revocation."
recurrence_guard: "`PublishedMappingImports.test.tsx` and `RewrittenBaselineDialog.test.tsx` now assert zero obsolete callback/toast/close/focus/refresh/finalization effects and aborted request signals; `mutationAuthority.test.ts` covers every predicate truth-table neighbor; `test_phase3_gauntlet.py` requires the exact semantic marker registry and browser tags; `tools/phase3_gauntlet.sh` enforces exact 42/42 mutation ownership and the three-test Playwright grep in the canonical 14-layer gate."

### Blameless branched 5-Whys

- **Code/lifecycle branch:** Deferred mutations could complete after access-token replacement or unmount because only collection requests owned lifecycle cleanup; mutation requests lacked dedicated controllers, and rewrite identity omitted session authority. That was possible because request validity was expressed in local captured state rather than a shared, explicitly tested live-authority contract. The actionable condition was to make each mutation own an AbortController/request token, include access-token authority in identity, and centralize the predicates in `mutationAuthority.ts`.
- **Configuration/gate branch:** The browser and mutation regressions existed outside the canonical proof surface because Playwright grepped only two stable tags and Stryker retained legacy raw coordinates without the remediation predicates. That persisted because the architecture contract verified the gate generally, not the exact selector set. The actionable condition was to require exact browser tags and an exact marker-to-line registry, then reject report ownership drift independently of mutation score.
- **Environment/data branch:** A stale dev server or ordinary same-token data could have hidden the failures. The investigation controlled those alternatives with deferred promises, the access-token-only boundary neighbor, unmount cleanup, and isolated random-port Vite execution. They were not contributing root causes.
- **AND-gate:** No individual warning required multiple simultaneous causes; each code or selector omission independently reproduced its warning. Aggregate Phase 3 acceptance required all four branches to close in the same unchanged source digest.
