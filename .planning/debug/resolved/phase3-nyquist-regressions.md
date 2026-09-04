---
status: resolved
trigger: "Procedi con le correzioni"
created: 2026-09-03T19:30:26Z
updated: 2026-09-03T20:48:43Z
---

## Current Focus

hypothesis: Human verification and the concrete regression artifacts satisfy the full resolution contract.
test: Commit this resolved ledger under the enabled documentation policy, then append and commit the durable knowledge-base entry.
expecting: Two documentation commits capture the resolved ledger and KB prevention pattern while excluded runtime artifacts remain untouched.
next_action: Commit .planning/debug/resolved/phase3-nyquist-regressions.md through gsd-tools.
bug_class: bohrbug
reasoning_checkpoint:
  hypothesis: "Six direct divergences cause the six specified failures: unsafe provider expiry arithmetic escapes the closed OAuth boundary; old import-start and rewrite-confirmation closures lack a live authority comparison; committed confirmation wrongly depends on refresh success; the executable JSON registry is absent from the manifest; and row-error focus lacks both mobile registration and post-commit scheduling."
  confirming_evidence:
    - "WR-01 stack traces point to both timedelta construction and datetime addition at `_persist_access_only`; the exact maximum safe neighbor passes."
    - "WR-02 and WR-03 resolve old promises after identity replacement and directly observe forbidden toast/callback/load/focus side effects."
    - "WR-09 returns a successful confirmation response plus refresh false and directly observes mutation-failure UI and resubmission."
    - "WR-04's fixture proves source_state digests declared JSON inputs, while real-manifest equality identifies the single absent row."
    - "WR-10 against isolated current Vite source renders the visible mobile alert but reports it inactive; source initially registered only desktop, and adding mobile registration without moving the pre-commit microtask still failed focus."
  falsification_test: "Any unchanged driving regression remaining RED after its isolated minimal change, or not returning RED when that change is reverted, disproves that boundary's causal claim."
  fix_rationale: "Compute expiry before persistence under a closed arithmetic exception; compare async completions with live authority refs/tokens; mark server confirmation committed independently of collection refresh; declare the registry in the manifest; and consume a focus request after responsive alerts commit, selecting the rendered target."
  blind_spots: "Full adjacent suites, desktop responsive focus, renewal with oversized lifetime, scoped mutation checks, and the canonical 14-layer gauntlet have not yet been rerun."
  candidate_causes:
    - "code: missing arithmetic translation, async identity/token ownership, mutation-vs-refresh state separation, and visible-target focus selection"
    - "config: canonical Phase 3 manifest omits one executable JSON registry"
    - "environment: stale Docker port 8080 confounded the first WR-10 run but isolated current Vite still reproduces the focus defect"
    - "data: provider maximum-plus-one lifetime triggers WR-01, but valid boundary data is a trigger rather than corrupt state"
  and_gate: "No within any individual regression: each has one sufficient boundary defect. The session aggregate is six independent OR branches, all of which must be fixed to close the requested set."
tdd_checkpoint:
  test_commit: 7cae046
  status: red
  failures: 6 deterministic Nyquist regressions

## Symptoms

expected: Oversized OAuth lifetimes fail closed; obsolete mutations have no side effects; confirmed baselines remain successful across refresh failure; every executable registry is digest-bound; mobile errors receive visible focus.
actual: OverflowError escapes; stale product/import completions mutate current UI; refresh failure is reported as confirmation failure; the JSON registry is absent from the manifest; mobile focus targets a hidden desktop alert.
errors: OAuth 1 passed/2 failed; manifest 1 passed/1 failed; focused Vitest 23 passed/3 failed; mobile Playwright 1 failed.
reproduction: Run the focused commands recorded in .planning/phases/03-bitbucket-import-integration/03-VALIDATION.md.
started: Discovered by the 2026-09-03 Phase 3 Nyquist audit; review warnings existed before the audit.

## Eliminated

- hypothesis: The current WR-10 failure is caused by the stale Docker frontend served on Playwright's default port 8080.
  evidence: The stale server caused a different top-level error, but the isolated current-source Vite run rendered the intended mobile alert and still failed `toBeFocused`.
  timestamp: 2026-09-03T19:38:09Z
- hypothesis: Per-test spectrum-based fault localization can rank the six failures.
  evidence: The project has aggregate coverage but no per-test coverage matrix required for Ochiai ranking; direct strict tests and stack/DOM assertions already localize each boundary.
  timestamp: 2026-09-03T19:38:09Z
- hypothesis: Registering the mobile RowError ref while retaining the catch-path microtask is sufficient for WR-10.
  evidence: Component tests stayed green, but isolated current-source Playwright still found the visible mobile alert inactive for five seconds after the mobile ref was added.
  timestamp: 2026-09-03T19:42:43Z
- hypothesis: Only the Published cursor-terminal and Rewritten missing-data mutation targets moved.
  evidence: Focused Stryker generated no mutant at Published line 76 and source differential shows the complete five-entry ACTION_LABELS block moved from 76-80 to 77-81; the current selector omits `run_import` at 81.
  timestamp: 2026-09-03T20:00:58Z

## Evidence

- timestamp: 2026-09-03T19:30:26Z
  checked: Fresh merged-source Phase 3 gauntlet before adding regressions.
  found: 14/14 layers passed on digest e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c.
  implication: Existing suites missed the six boundary cases; failures are not broad environmental breakage.
- timestamp: 2026-09-03T19:30:26Z
  checked: Nyquist auditor focused test runs and static gates.
  found: Six intended assertions fail while Ruff, formatting, typecheck, ESLint, Prettier, and diff checks pass.
  implication: The RED tests are valid executable specifications for implementation/configuration remediation.
- timestamp: 2026-09-03T19:33:30Z
  checked: Complete BitbucketOAuthService expiry path and WR-01 boundary tests.
  found: `_persist_access_only` performs both `timedelta(seconds=expires_in)` and datetime addition after `_exchange_and_validate` has returned, so arithmetic overflow is outside the closed OAuth exception boundary.
  implication: A valid integer provider field can escape as raw `OverflowError` before transaction commit.
- timestamp: 2026-09-03T19:33:30Z
  checked: Complete PublishedMappingImports mutation and responsive rendering paths.
  found: `startImport` has no generation or product/import identity check after awaiting the mutation, and only the hidden desktop RowError registers a focus ref.
  implication: Old completions can mutate the replacement product; mobile failures necessarily focus the hidden desktop duplicate.
- timestamp: 2026-09-03T19:33:30Z
  checked: Complete RewrittenBaselineDialog comparison and confirmation paths.
  found: An old `confirmBaseline` closure compares its captured identity to the same captured render value, and treats `onConfirmed(false)` after a successful commit as confirmation failure.
  implication: Obsolete confirmations retain side effects, while a committed mutation becomes retryable when only refresh fails.
- timestamp: 2026-09-03T19:33:30Z
  checked: Phase 3 source manifest and source_state manifest resolution.
  found: The exact executable JSON edge registry is tracked and consumed by tests but has no include rule in the canonical manifest.
  implication: Its content can change without affecting the Phase 3 source digest.
- timestamp: 2026-09-03T19:33:57Z
  checked: Focused WR-01 pytest reproduction (`maximum_datetime_safe or unsafe_token_lifetime`).
  found: The maximum safe lifetime passed; maximum-plus-one and beyond-timedelta inputs both failed with raw `OverflowError` at `_persist_access_only` line 479 (1 passed, 2 failed).
  implication: The boundary predicate itself is correct; only unsafe arithmetic needs translation to the closed OAuth error without persisting state.
- timestamp: 2026-09-03T19:34:15Z
  checked: Focused WR-04 architecture reproduction (`manifest_covers_sources or executable_json_registry`).
  found: The fixture digest negative control passed, while the real manifest coverage assertion failed solely because `phase2_spec_edge_matrix.json` is absent (1 passed, 1 failed).
  implication: `source_state.sh` already handles the registry correctly when declared; WR-04 needs one explicit manifest include rather than script changes.
- timestamp: 2026-09-03T19:34:34Z
  checked: Focused WR-02/03/09 Vitest reproduction for PublishedMappingImports and RewrittenBaselineDialog.
  found: Exactly the three Nyquist cases failed (23 passed, 3 failed): the old start completion stole focus/kept old data, the old confirmation called `onConfirmed`, and refresh false rendered `Baseline update unavailable`.
  implication: Each async boundary defect is deterministic and isolated; adjacent existing component behavior remains green before fixes.
- timestamp: 2026-09-03T19:35:03Z
  checked: Focused WR-10 Playwright reproduction at 320x720.
  found: The test failed, but the final DOM showed `Published imports unavailable` rather than either row-level `Import did not start` alert; the intended visible alert was absent.
  implication: The known desktop-only focus ref remains a production defect, but this run also requires tracing why the collection load failed before finalizing the WR-10 mechanism.
- timestamp: 2026-09-03T19:36:24Z
  checked: WR-10 trace DOM/network, Playwright config, and listener on the default base URL.
  found: The trace served an older PublishedMappingImports DOM (legacy table headings and no mobile projection) from Docker's long-lived port 8080 listener; Playwright has no webServer and defaults directly to that port.
  implication: The top-level error observation is an environment-confounded repro and does not describe the current branch; WR-10 must be rerun against an isolated current-source Vite server.
- timestamp: 2026-09-03T19:38:09Z
  checked: WR-10 against current source on isolated Vite port 4174.
  found: The visible mobile `Import did not start` alert rendered, but Playwright consistently reported it inactive for five seconds.
  implication: The current-source failure exactly confirms the responsive focus-registration defect independently of the stale port-8080 environment.
- timestamp: 2026-09-03T19:38:52Z
  checked: WR-01 after computing expiry before persistence and translating `OverflowError`.
  found: Maximum safe, maximum-plus-one, and beyond-timedelta boundary cases all pass (3 passed); unsafe cases remain closed and persist no connection.
  implication: The minimal arithmetic-boundary fix satisfies WR-01 without rejecting the exact valid maximum neighbor.
- timestamp: 2026-09-03T19:39:27Z
  checked: WR-04 after declaring the executable JSON registry in the canonical manifest.
  found: Both real manifest coverage and registry digest negative control pass (2 passed).
  implication: The existing source-state resolver now binds this semantic test input into the canonical digest with no script change.
- timestamp: 2026-09-03T19:40:54Z
  checked: WR-02 after adding live authority comparison and request-token-owned pending cleanup.
  found: All PublishedMappingImports component tests pass, including the old-product deferred completion contract (17 passed).
  implication: Obsolete mutation completion now exits before toast/reload/error/focus effects while same-authority successful mutation behavior remains intact.
- timestamp: 2026-09-03T19:41:46Z
  checked: WR-03 and WR-09 after live identity/token ownership and explicit committed-state separation.
  found: All RewrittenBaselineDialog tests pass (9 passed), including obsolete completion suppression, refresh-failure success, stale 409, and pending dismissal behavior.
  implication: Only the live request can cause callbacks, and a successful server mutation can no longer be relabeled or resubmitted due to downstream refresh failure.
- timestamp: 2026-09-03T19:42:43Z
  checked: First WR-10 fix attempt (desktop/mobile refs plus rendered-element selection).
  found: PublishedMappingImports unit neighbors passed 17/17, but Playwright still failed only `toBeFocused`; the visible mobile alert existed and was inactive.
  implication: Responsive target selection is necessary but not sufficient; focus scheduling precedes conditional alert ref commit and must move to a post-commit effect.
- timestamp: 2026-09-03T19:44:07Z
  checked: WR-10 after moving the focus request into a failure-state effect.
  found: PublishedMappingImports passed 17/17 and isolated current-source Playwright passed 1/1 at 320x720.
  implication: Post-commit scheduling plus rendered responsive target selection fully satisfies the original mobile focus contract.
- timestamp: 2026-09-03T19:45:05Z
  checked: Combined focused suites and first static verification.
  found: Backend 21/21 and frontend 26/26 passed; Ruff and Python formatting passed; TypeScript passed; ESLint rejected two render-time ref assignments and one obsolete dependency warning.
  implication: Runtime contracts are green, but the frontend implementation must preserve React render purity before guardrail acceptance.
- timestamp: 2026-09-03T19:46:01Z
  checked: Frontend identity synchronization revision and complete static rerun.
  found: Identity refs now synchronize in layout effects; TypeScript, ESLint, Prettier, Ruff, Python formatting, and git diff checks all pass, while focused frontend tests remain 26/26.
  implication: The fixes meet React purity and repository formatting/type/lint constraints without changing the validated behavior.
- timestamp: 2026-09-03T19:46:52Z
  checked: First bounded WR-02 Stryker invocation with exact `testFiles`.
  found: Stryker instrumented four fix-site mutants but its Vitest runner executed zero tests despite matching the requested file, so the run exited before mutation.
  implication: The runner's exact-file filter is incompatible in this configuration; mutation must retry via coverage-related selection or be logged as unavailable rather than silently passed.
- timestamp: 2026-09-03T19:49:28Z
  checked: Bounded full-Vitest Stryker probes at WR-02 and WR-03/09 fix sites.
  found: WR-02 killed 4/4 mutants. WR-03/09 killed 10/12; a removed post-refresh live-identity guard and empty success-toast literal survived, while the pre-callback identity and committed-state mutants were killed by the original regressions.
  implication: The core tests bite, but guardrail acceptance requires held-out same-boundary coverage for the two surviving behaviors rather than excluding them from mutation scope.
- timestamp: 2026-09-03T19:51:02Z
  checked: Mutation-driven oracle hardening and repeated scoped Stryker.
  found: The dialog suite passes 10/10 and the same WR-03/09 production range kills 12/12 mutants; WR-02 remains 4/4, for 16/16 scoped frontend mutants killed.
  implication: The exact async identity, committed-state, and success-notification behaviors now resist fix-site mutation overfitting.
- timestamp: 2026-09-03T19:52:32Z
  checked: Stash-based revert-and-reconfirm for the exact five-file fix set.
  found: Without the fix, the original counts returned exactly (WR-01 2 failed/1 passed, WR-04 1 failed/1 passed, WR-02/03/09 3 failed/23 passed, WR-10 1 failed). After reapply, backend 3+2, frontend 27, and mobile 1 all passed.
  implication: The tracked fix set is causally necessary and sufficient for all six original regressions; excluded untracked artifacts were untouched.
- timestamp: 2026-09-03T19:52:58Z
  checked: Atomic fix commit preparation.
  found: WR-01=`2755ce0`, WR-04=`a423217`, WR-02/10=`3c3ee94`, WR-03/09=`914ae07`; only the explicitly excluded untracked runtime/debug artifacts remain dirty.
  implication: Canonical source-state can now bind the exact tested production, manifest, and regression-test source to a clean digest.
- timestamp: 2026-09-03T19:57:34Z
  checked: First canonical Phase 3 gauntlet on digest `a282c0c2302c9dc05eed3d57ddf8beeca545926f3c3321ecbf5e4cb47242afd3`.
  found: Source-state, negative controls, 956 backend tests at 95%, backend static checks, migrations/OpenAPI, 360 frontend tests at 83.52%, frontend static/build, and 6/6 backend mutants passed. Stryker killed 18/18 generated mutants but the layer rejected because configured expected targets at Published line 480 and Rewritten line 367 no longer generated after line insertions.
  implication: Behavior and mutation killing are green; canonical acceptance is correctly blocked until its explicit line-number ownership registry follows the same semantic target locations.
- timestamp: 2026-09-03T19:59:01Z
  checked: Pre-fix and current numbered source around both missing mutation targets, plus the complete gauntlet selector and ownership assertion.
  found: Published's selected `nextCursor === null` condition moved exactly 480 -> 493; Rewritten's selected `result.data === undefined` condition moved exactly 367 -> 409. The gauntlet hard-codes each old number in both `--mutate` and `expected_locations`.
  implication: Rebinding those four numeric literals restores the same semantic proof scope without broadening or weakening mutation ownership.
- timestamp: 2026-09-03T19:59:25Z
  checked: Minimal verifier line-binding patch and whitespace validation.
  found: The diff changes only the Published 480 -> 493 and Rewritten 367 -> 409 numbers in the selector and matching ownership assertion; `git diff --check` passes.
  implication: The verifier now points at the original semantic conditions and retains exact fail-closed ownership checks.
- timestamp: 2026-09-03T19:59:52Z
  checked: Focused fail-closed gauntlet architecture suite after the line rebindings.
  found: All 5 tests pass in 1.79 seconds.
  implication: Script structure, source manifest contract, mutation-domain proof, and evidence constraints remain valid; direct Stryker generation is the remaining pre-commit check.
- timestamp: 2026-09-03T20:00:58Z
  checked: Focused Stryker with the first two rebindings and direct JSON ownership inspection.
  found: Stryker killed 24/24, including the new Published 493 and Rewritten 409 targets, but actual Published locations were {77,78,79,80,493}; comparison with pre-regression source shows ACTION_LABELS moved as a block from 76-80 to 77-81.
  implication: The behavioral mutation proof is strong, but exact semantic ownership additionally requires moving the label range so `run_import` at current line 81 remains included.
- timestamp: 2026-09-03T20:01:42Z
  checked: Complete three-branch verifier rebind and whitespace validation.
  found: The selector now follows the full five-entry ACTION_LABELS block at 77-81 plus Published 493 and Rewritten 409; expected ownership mirrors those exact lines and `git diff --check` passes.
  implication: A focused rerun can now confirm the verifier neither omits nor invents a semantic target.
- timestamp: 2026-09-03T20:02:57Z
  checked: Final focused Stryker run, direct exact-ownership assertion, and repeated gauntlet architecture suite.
  found: All 25 generated mutants were killed; ownership exactly equals Published {77,78,79,80,81,493}, Rewritten {409}, polling {34,35,37,38}; architecture suite passes 5/5.
  implication: The verifier repair restores and slightly recovers the originally intended label coverage (including current `run_import`) without any surviving mutant or ownership ambiguity.
- timestamp: 2026-09-03T20:03:18Z
  checked: Atomic verifier repair commit and post-commit worktree status.
  found: `ab045d8` commits only tools/phase3_gauntlet.sh; included source is clean and only explicitly excluded untracked .gsd/, agent history, debug ledger, and graphify-out/ remain.
  implication: The canonical gauntlet can bind the exact production, tests, and verifier code to one new digest.
- timestamp: 2026-09-03T20:11:10Z
  checked: Canonical `bash tools/phase3_gauntlet.sh` from committed digest 2b1b22590d42d8333b41547dddb90d8a484b5fe08dbaed5032c86877b8831b9c.
  found: All 14/14 layers passed in 437 seconds. Highlights: 956 backend tests at 95% coverage, 360 frontend tests at 83.52% coverage, all static/build/migration/OpenAPI gates, backend 6/6 mutation proof, frontend 25/25 exact-owned mutants killed, responsive Playwright 2/2, supply-chain/schema checks, provider audit 117/117, deployment smoke, API preseal, and identical final source digest.
  implication: The fix is stable across focused, adjacent, randomized full-suite, mutation, browser, container, and final source-integrity boundaries.
- timestamp: 2026-09-03T20:20:50Z
  checked: Owned process cleanup and final acceptance state.
  found: The isolated current-source Vite server was stopped; the worktree contains no tracked changes and only the explicitly excluded untracked runtime/debug artifacts remain.
  implication: Automated verification is complete and the session can safely wait for human end-to-end confirmation without hidden test infrastructure remaining active.
- timestamp: 2026-09-03T20:43:53Z
  checked: Human verification checkpoint response.
  found: The user explicitly confirmed the fixes and accepted the automated UAT evidence as verification that all six requested regressions are correct.
  implication: The session satisfies the final resolution gate and may be archived with its prevention and recurrence-guard record.
- timestamp: 2026-09-03T20:45:23Z
  checked: Planning policy, MemPalace availability, and exact regression artifact names from the test-first commit.
  found: `commit_docs` is true; MemPalace is explicitly disabled; all seven named regression tests exist and passed within focused/canonical verification.
  implication: Archive commits are required, the Markdown knowledge base is the durable recall path, and every recurrence guard can cite a verified artifact.
- timestamp: 2026-09-03T20:48:43Z
  checked: Exact archive move and excluded artifact status.
  found: The resolved ledger now exists only at .planning/debug/resolved/phase3-nyquist-regressions.md; .gsd/, agent history, and graphify-out/ remain untracked and untouched.
  implication: The resolved-session documentation commit can be scoped to exactly one file.

## Resolution

root_cause: "WR-01: `_persist_access_only` does unchecked timedelta/datetime arithmetic outside the OAuth error boundary; WR-02: `startImport` applies completion side effects without comparing against live product/access authority; WR-03: `confirmBaseline` self-compares two values captured by the obsolete closure instead of live identity/request ownership; WR-04: the Phase 3 manifest omits `phase2_spec_edge_matrix.json`; WR-09: successful server confirmation is treated as failed/retryable when only collection refresh returns false; WR-10: only the desktop RowError is registered and focus is scheduled before newly conditional alert refs commit."
fix: "WR-01 computes provider expiry before mutating the connection and translates arithmetic overflow to the closed OAuth error. WR-04 explicitly includes the executable edge registry in the Phase 3 source manifest. WR-02 fences mutation completions with live authority identity and request-owned pending cleanup. WR-03/09 bind confirmation to the live identity/request token and represent server commit independently from refresh. WR-10 registers both responsive alerts and consumes focus after commit on the rendered target. The gauntlet's exact Stryker bindings follow the same relocated semantic targets."
verification:
  target_test: {result: pass}
  mutation_check: {result: pass, reason_if_skipped: "Frontend Stryker applies to the async UI fix sites and killed 16/16 scoped fix-site mutants plus 25/25 canonical exact-owned mutants. Direct mutation was unavailable for the Python OAuth arithmetic, manifest/config, and browser-focus boundaries; their specified tests and causal revert covered those boundaries.", mutant_killed: true}
  no_op_deletion: {result: pass, deletion_justified_by_rca: false}
  adjacent_tests: {result: pass, suites_run: ["focused backend 21/21", "focused frontend 27/27", "mobile Playwright 1/1", "canonical Phase 3 gauntlet 14/14 with backend 956 tests at 95% and frontend 360 tests at 83.52%"]}
  revert_and_reconfirm: {result: pass, bug_returned_on_revert: true, fixed_on_reapply: true}
  guardrail_verdict: accepted
oracle_type: specified
files_changed: [backend/src/verboflex/services/bitbucket_oauth.py, frontend/src/features/admin/imports/PublishedMappingImports.tsx, frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx, frontend/src/features/admin/imports/RewrittenBaselineDialog.test.tsx, tools/phase3_source_manifest.txt, tools/phase3_gauntlet.sh]

## Prevention

five_whys:
  code_branch:
    - "Boundary behavior was implemented from happy-path state: provider expiry arithmetic remained outside the closed error boundary; asynchronous UI completions trusted captured identity; confirmation coupled a committed mutation to refresh; responsive focus ran before conditional alerts committed."
    - "Those states remained possible because the prior suite did not drive maximum-plus-one data, identity replacement during pending work, successful mutation plus failed refresh, or the mobile-only focus target."
    - "The actionable condition was absence of executable boundary-neighbor and authority-supersession specifications, now supplied by the Nyquist regressions."
  config_branch:
    - "An executable JSON registry was not digest-bound because the manifest enumerated source classes but omitted this non-code semantic input."
    - "The mutation proof also encoded semantic ownership as line numbers, so legitimate insertions shifted its target coordinates."
    - "The actionable condition was missing manifest negative-control coverage and a fail-closed ownership rebind whenever selected semantics move."
  environment_data_branch:
    - "A stale default-port frontend initially obscured the mobile symptom, while maximum-plus-one provider lifetime data exposed the OAuth failure."
    - "The actionable conditions are isolated random-port browser execution and explicit representability neighbors at the datetime boundary."
  and_gate: "No individual regression required multiple simultaneous root causes; six independent OR branches formed the aggregate session. The stale port was a confounder, not a production cause."
why_not_caught: "Existing unit, type, lint, build, and closeout gates exercised normal provider values and live-request UI flows but had no executable tests for expiry representability neighbors, authority replacement during deferred completion, commit-versus-refresh separation, executable JSON manifest membership, or visible responsive focus. Review warnings identified the risks but were non-blocking prose rather than regression gates."
recurrence_guard: "Test-first commit 7cae046 adds `test_client_credentials_accepts_maximum_datetime_safe_token_lifetime`, `test_client_credentials_rejects_unsafe_token_lifetime_with_closed_error`, `test_source_state_digest_changes_when_executable_json_registry_changes`, PublishedMappingImports `ignores a deferred start response after product authority changes`, RewrittenBaselineDialog `ignores an old confirmation completion after product and import identity change` and `does not report a committed confirmation as failed or allow proposal resubmission when refresh fails`, plus Playwright `mobile import failure focuses the visible mobile alert`; tools/phase3_gauntlet.sh binds these sources and exact mutation ownership into the canonical 14-layer gate."
