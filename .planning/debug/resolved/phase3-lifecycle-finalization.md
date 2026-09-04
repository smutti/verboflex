---
status: resolved
trigger: "Correggere i residui di finalizzazione lifecycle WR-13 e WR-14"
created: 2026-09-04T08:01:49Z
updated: 2026-09-04T10:36:03Z
---

## Current Focus

hypothesis: Confirmed by machine and human verification — both async finally setters require exact live lifecycle ownership, so cleanup/unmount revocation suppresses state synchronization while live failure and success finalization remain intact.
test: Record the explicit human confirmation, archive this resolved ledger, and append the prevention record to the durable debug knowledge base.
expecting: The resolved ledger and knowledge-base entry commit independently, while the pre-existing modified review and user-owned untracked paths remain untouched.
next_action: Move this ledger to `.planning/debug/resolved/` and commit exactly the resolved session and knowledge-base entry as separate documentation commits.
bug_class: bohrbug
known_pattern_candidate: "phase3-post-remediation-review-gaps — prior lifecycle cleanup closes visible effects but its KB recurrence guard does not observe the residual async-finally setter boundary"
hypothesis_branches:
  - "code: finally evaluates identity/commit predicates that omit exact live request and controller ownership"
  - "config: canonical mutation markers own the incomplete predicates but do not yet own a lifecycle/controller predicate"
  - "environment: React may ignore post-unmount setters, hiding the call, but a pure decision observer is runtime-independent"
  - "data: unchanged identity after unmount is the minimal failing input; a changed identity already suppresses finalization"
and_gate_candidate: "No per residual warning: each incomplete finally predicate independently permits its setter; both OR branches must close for aggregate WR-13/WR-14 completion."
reasoning_checkpoint:
  hypothesis: "RewrittenBaselineDialog and PublishedMappingImports call React state setters after unmount because their finally predicates omit the exact live controller/request ownership that cleanup already revokes."
  confirming_evidence:
    - "The test-only component observers directly record `true` from both finally decisions after unmount, after their AbortSignals are already aborted and all visible effects are suppressed."
    - "The direct truth tables show Published live identity ignores revoked request ownership and rewrite identity/commit cannot represent a live uncommitted request; the controller predicate does not exist."
    - "Complete source tracing shows cleanup clears controllers/tokens while leaving identity refs unchanged, exactly explaining the two observed `true` decisions."
  falsification_test: "The hypothesis is false if adding only exact live controller/token ownership to the existing finally gates does not turn the unchanged five frontend RED assertions and one architecture RED assertion green, or if causal revert does not restore them."
  fix_rationale: "Reuse the ownership already required for callbacks, add a marker-owned exact non-aborted controller predicate, evaluate finalization before owned cleanup, and pass that decision into the existing state-finalization predicates; this removes only unowned setter calls while preserving live failure cleanup."
  blind_spots: "Exact Stryker mutant count is unknown until the updated marker selection runs; full frontend adjacency, architecture corpus, causal revert, and the fresh 14-layer gauntlet remain unverified."
  candidate_causes:
    - "code: finally uses identity/commit-only predicates after cleanup has revoked exact controller and token ownership"
    - "config: the canonical semantic marker registry owns the incomplete predicates but has no exact controller-ownership target"
    - "environment: React silently ignoring post-unmount setters hides the call, ruled out as a cause by direct predicate observers"
    - "data: unchanged identity after unmount is the minimal failing neighbor; identity replacement already returns false"
  and_gate: "No for each warning: either weak finally predicate independently permits its own setter after cleanup. Both independent OR branches must be fixed for aggregate WR-13/WR-14 closure."
tdd_checkpoint:
  status: green
  failures: 2 residual review findings
  red_failures: "frontend 5 failed/30 passed across exact lifecycle/predicate assertions; architecture 1 failed/6 passed for missing controller marker ownership"
  test_commit: 239294f
  fix_commit: 6e8e858
  green_results: "frontend focused 35/35; architecture 7/7; exact Stryker 52/52"

## Symptoms

expected: An async completion may clear live uncommitted state, but must perform no pending/progress state synchronization after ownership invalidation or unmount.
actual: RewrittenBaselineDialog can call setConfirmationProgress in finally after unmount; PublishedMappingImports can call setPendingMappings in finally after unmount.
errors: WR-13 and WR-14 remain partially remediated in the latest independent review.
reproduction: Resolve deferred mutations after component cleanup and observe the finalization decision independently of React ignoring the setter.
started: Proven by the 2026-09-04 independent post-remediation review.

## Eliminated

None.

## Evidence

- timestamp: 2026-09-04T08:01:49Z
  checked: Latest independent review and current repository status.
  found: WR-13/WR-14 retain only post-unmount finally state writes; callback, toast, close, focus, refresh, AbortSignal, and request-token suppression are already covered. The independent review report is concurrently modified.
  implication: Fix only finalization ownership, preserve every existing suppression contract, and keep the review report read-only.
- timestamp: 2026-09-04T08:01:49Z
  checked: Previous resolved post-remediation debug session.
  found: WR-11/WR-12 and the broader portions of WR-13/WR-14 are archived on digest 0227a4fb; this residual needs a separate TDD session and fresh digest.
  implication: Do not reopen or modify the resolved session; use it only as historical evidence.
- timestamp: 2026-09-04T08:03:46Z
  checked: Phase-0 semantic recall capability and durable debug knowledge base.
  found: MemPalace is not configured, so fallback matching surfaced `phase3-post-remediation-review-gaps`; that entry proves abort/token cleanup and visible-effect suppression, but its recurrence guard observes neither post-cleanup finalization decision.
  implication: Treat the prior resolution as a candidate only and add a specified, directly observable finalization oracle before changing production code.
- timestamp: 2026-09-04T08:06:51Z
  checked: Complete RewrittenBaselineDialog, PublishedMappingImports, their component tests, mutationAuthority helper/tests, and canonical marker architecture/gauntlet contract.
  found: Rewritten cleanup aborts and nulls controller/token, but finally calls an identity-plus-commit predicate after cleanup state is already revoked; Published cleanup aborts and clears pending requests, but finally gates its setter only on authority identity. All visible-effect paths already use stronger abort/token/live checks. The marker registry owns exactly the four incomplete/current authority predicates.
  implication: Add exact controller ownership as a retained semantic predicate, feed it with token/live authority into both finalization decisions, and preserve every existing callback/toast/close/focus/refresh suppression path.
- timestamp: 2026-09-04T08:06:51Z
  checked: SBFL Phase 1.25 preconditions and common-pattern scan.
  found: The tests emit aggregate rather than per-test spectra, so Ochiai ranking is unavailable. The deterministic symptom matches Async/Timing cleanup plus State Management invalid-transition patterns and is classified as a Bohrbug because deferred promises reproduce the same branch every run.
  implication: Skip SBFL explicitly and use working-backwards deterministic predicate observation with strict RED/GREEN and causal revert.
- timestamp: 2026-09-04T08:08:01Z
  checked: Unchanged focused frontend control suites.
  found: RewrittenBaselineDialog, PublishedMappingImports, and mutationAuthority pass 34/34 before new assertions.
  implication: Any focused failure after test-only edits is attributable to the new WR-13/WR-14 finalization contract rather than a pre-existing broken baseline.
- timestamp: 2026-09-04T08:09:09Z
  checked: First test-only strict RED run.
  found: Frontend is deterministically 5 failed/30 passed: both unmount observers directly receive `true` instead of `false`, live-authority ignores revoked ownership, the controller oracle is absent, and the rewrite live-uncommitted signature cannot distinguish ownership from committed state. Architecture is 1 failed/6 passed because the canonical registry lacks the required controller-ownership marker.
  implication: The residual WR-13/WR-14 mechanisms are reproduced without production edits; formatting and identical RED reconfirmation may precede the atomic test commit.
- timestamp: 2026-09-04T08:09:56Z
  checked: Formatted RED reconfirmation and atomic test commit.
  found: The identical frontend 5 failed/30 passed and architecture 1 failed/6 passed results recur after formatting; commit `239294f` contains exactly the four authorized test/architecture files and no production change.
  implication: Strict TDD RED is durable. The structured reasoning checkpoint is complete, so the minimal GREEN implementation may begin.
- timestamp: 2026-09-04T08:11:19Z
  checked: First minimal GREEN implementation and focused behavior/architecture suites.
  found: A shared exact non-aborted controller predicate now feeds Published live identity plus token ownership and Rewritten exact identity/token ownership before either finally setter. The three focused frontend suites pass 35/35 and the marker architecture contract passes 7/7; live finalization observers remain true and both unmount observers are false.
  implication: Target behavior is green with preserved live failure/success cleanup. Static checks and exact marker-resolved mutation ownership must now validate the implementation surface.
- timestamp: 2026-09-04T08:12:27Z
  checked: Frontend TypeScript/ESLint/Prettier, architecture Ruff/format, shell syntax, whitespace, and displaced legacy mutation coordinates.
  found: All static checks pass. The owned import/predicate additions shift legacy Published action ownership to lines 82-86, cursor ownership to 531, and Rewritten missing-data ownership to 439; both canonical selector and independent report expectations now match those verified statements. Architecture remains 7/7.
  implication: The canonical gate is syntactically and structurally aligned; exact mutation behavior and count are the next acceptance signal.
- timestamp: 2026-09-04T08:14:04Z
  checked: First bounded exact Stryker attempt.
  found: Instrumentation selected 4 source files and 52 mutants; the initial full 368-test dry run passed in 27 seconds, but the conservative 60-second wrapper terminated before mutation completion with exit 142 and no accepted verdict.
  implication: Record the timeout as non-evidence, scale the explicit bound to 240 seconds for the measured suite size, and require a complete exact-location JSON report.
- timestamp: 2026-09-04T08:16:02Z
  checked: Scaled bounded exact-owned Stryker run and independent JSON validation.
  found: The 368-test dry run passed; exactly 52 mutants executed across only Published lines 82-86/531, Rewritten line 439, polling lines 34/35/37/38, and mutationAuthority marker targets 7/15/23/33/43. All 52/52 were killed with 100.00%, zero timeout/survivor/no-coverage/error, and the independent exact-location assertion passed.
  implication: The driving predicates kill every weakened identity/token/controller/committed-state neighbor and the canonical count is honestly updated from 42 to 52. Atomic GREEN commit and causal revert remain.
- timestamp: 2026-09-04T08:17:04Z
  checked: Atomic GREEN commit and fix-acceptance causal revert/reapply.
  found: Commit `6e8e858` contains exactly the two components, mutationAuthority helper, and canonical gauntlet. Reverting only that commit restores exactly frontend 5 failed/30 passed plus architecture 1 failed/6 passed; restoring the exact four paths to HEAD returns frontend 35/35 and architecture 7/7.
  implication: The GREEN change directly causes the regression close and is fully reapplied with no owned uncommitted code. Held-out adjacency and the fresh canonical gauntlet remain.
- timestamp: 2026-09-04T08:17:46Z
  checked: Held-out component adjacency and complete owned static checks after causal restoration.
  found: Rewritten, Published, mutationAuthority, and ProductMappingsPage pass 52/52; TypeScript, ESLint, Prettier, Ruff, Python formatting, architecture 7/7, shell syntax, and whitespace all pass. Status contains only the pre-existing modified review, user-owned untracked runtime paths, and this active ledger.
  implication: Guardrail adjacent/static signals are green and source is ready for the single fresh canonical 14-layer gauntlet.
- timestamp: 2026-09-04T08:31:25Z
  checked: Fresh canonical Phase 3 gauntlet and persistent result records.
  found: `bash tools/phase3_gauntlet.sh` passes all 14/14 ordered layers in 781 seconds on digest `64bdc9a3e5c4085036c78732b4285609dd3a00c6c307b7c33f40149b5fb0684b`, unchanged at final-source-state. Included results are backend 958/958 at 95% coverage, frontend 368/368, backend mutations 6/6, exact frontend mutations 52/52, Playwright 3/3, architecture/provider 119/119, production dependency audit clear, and deployment smoke provider mutations 0.
  implication: Every applicable machine guardrail signal is accepted on one unchanged source digest; only mandatory human workflow confirmation remains.
- timestamp: 2026-09-04T08:31:25Z
  checked: Final commit provenance and repository status.
  found: RED commit `239294f` contains exactly four test/architecture files; GREEN commit `6e8e858` contains exactly four implementation/gauntlet files. Status contains only the pre-existing modified `03-REVIEW.md`, user-owned `.gsd/`, `.planning/agent-history.json`, `graphify-out/`, and this active ledger.
  implication: No owned implementation or test change remains uncommitted and no unrelated user-owned state was altered; hand off the human-verify checkpoint without archiving.
- timestamp: 2026-09-04T10:36:03Z
  checked: Human verification checkpoint response.
  found: The user explicitly confirmed that the corrected workflows are fixed in the real environment.
  implication: Machine and human verification are both complete, so the session may be resolved and archived with its prevention record.
- timestamp: 2026-09-04T10:36:03Z
  checked: Archive configuration, semantic-memory capability, and durable knowledge-base fallback.
  found: `commit_docs` is true and MemPalace is disabled in project configuration; `.planning/debug/knowledge-base.md` remains the durable source of truth.
  implication: Commit the resolved ledger and KB entry as separate exact-file documentation commits and skip semantic indexing with an explicit record.

## Resolution

root_cause: "WR-13: rewrite finalization checks only unchanged identity and uncommitted state after cleanup has cleared its controller/token; WR-14: published-import finalization checks only unchanged authority identity after cleanup has aborted and cleared its pending controller/token."
fix: "Added a marker-owned exact live-controller predicate; extended Published authority with exact current request ownership; evaluated both finally decisions before owned cleanup; and required exact controller/token/live identity plus uncommitted state before either React state synchronization."
verification:
  target_test: {result: pass, suites: "focused frontend 35/35 and architecture 7/7"}
  mutation_check: {result: pass, mutant_killed: "52/52 exact-owned frontend"}
  no_op_deletion: {result: pass, deletion_justified_by_rca: false}
  adjacent_tests: {result: pass, suites_run: ["focused/adjacent frontend 52/52", "architecture 7/7", "TypeScript", "ESLint", "Prettier", "Ruff", "shell syntax"]}
  revert_and_reconfirm: {result: pass, bug_returned_on_revert: true, fixed_on_reapply: true}
  canonical_gauntlet: {result: pass, layers: "14/14", duration_seconds: 781, source_digest: "64bdc9a3e5c4085036c78732b4285609dd3a00c6c307b7c33f40149b5fb0684b", backend: "958/958", frontend: "368/368", backend_mutation: "6/6", frontend_mutation: "52/52", playwright: "3/3", architecture_provider: "119/119"}
  human_verification: {result: pass, confirmed_at: "2026-09-04T10:36:03Z"}
  guardrail_verdict: accepted
oracle_type: specified
files_changed:
  - backend/tests/architecture/test_phase3_gauntlet.py
  - frontend/src/features/admin/imports/PublishedMappingImports.tsx
  - frontend/src/features/admin/imports/PublishedMappingImports.test.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx
  - frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx
  - frontend/src/features/admin/imports/mutationAuthority.ts
  - frontend/src/features/admin/imports/mutationAuthority.test.ts
  - tools/phase3_gauntlet.sh

## Prevention

why_not_caught: "The existing unmount tests proved aborted signals and suppressed callbacks, toasts, close, focus, and refresh effects, but did not observe the async-finally state-synchronization decisions themselves. React can ignore a post-unmount setter, so UI assertions masked the call; the canonical mutation registry also owned identity, token, and committed-state predicates without an exact controller-lifecycle predicate."
recurrence_guard: "`PublishedMappingImports.test.tsx` and `RewrittenBaselineDialog.test.tsx` directly assert that finalization decisions are false after unmount and true for live boundary neighbors; `mutationAuthority.test.ts` covers exact live, aborted, mismatched, null-controller, revoked-token, and committed/uncommitted truth-table neighbors; `test_phase3_gauntlet.py` and `tools/phase3_gauntlet.sh` retain exactly five semantic markers and require all 52/52 owned frontend mutants to be killed inside the canonical 14-layer gate."

### Blameless branched 5-Whys

- **Code/lifecycle branch:** Post-unmount finalization remained possible because each `finally` block used an identity/commit predicate weaker than the callback authority already enforced elsewhere. That weaker boundary persisted because cleanup, callbacks, and state synchronization evolved as separate decisions, and cleanup cleared the controller/token without invalidating unchanged identity. The actionable condition was to evaluate one exact live controller/token/identity predicate before owned cleanup and require that decision for either setter.
- **Configuration/gate branch:** The canonical mutation gate retained the prior authority predicates but not controller lifecycle ownership. That happened because its marker registry mirrored the predicates already extracted for visible effects, while the post-unmount state-setter boundary had no directly observable oracle. The actionable condition was to add a fifth semantic marker, exact architecture ownership, and an honest 52-mutant target/count contract.
- **Environment/data branch:** React ignoring post-unmount setters and the unchanged-identity input made the defect invisible to rendered-UI assertions, while changed identity already returned false. Direct predicate observers with deferred promises removed that runtime masking and proved the minimal unchanged-identity boundary; environment and data were concealment conditions, not additional root causes.
- **AND-gate:** No per residual warning required multiple simultaneous causes; each weak finalization predicate independently permitted its own setter after lifecycle revocation. Aggregate WR-13/WR-14 closure required both independent branches to pass on the same unchanged source digest.
