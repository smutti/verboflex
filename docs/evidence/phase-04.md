---
phase: 04
status: passed
source_digest: sha256:2df3766ead7f1aea3597a8ad8b99205f14508a4189109996149265a163017b3a
gauntlet_exit: 0
smoke_exit: 0
---

# Phase 04 executable delivery evidence

The complete fresh `bash tools/phase4_gauntlet.sh` passed on frozen delivery commit `231e5b1`, from 2026-09-06 12:10:38 UTC through 12:15:19 UTC (plus bounded startup/cleanup). All 27 command records returned zero. The final result was written only after source-digest equality and cleanup succeeded. This run includes CR15 (constraint/activation lock order) and CR16 (retained-baseline constraint epoch) corrections; the earlier `ec6fd68` pass remains historical. Plan20 independently owns phase review/security/verification verdicts and remaining human judgment.

- Durable exact argv, working directories, UTC timestamps, durations, exit codes, output hashes, twelve mutation records, and artifact hashes: [phase-04-run.json](phase-04-run.json).
- Owner-only original evidence: `/var/folders/0t/8j9ddhjn68393k7yzdpwnjl80000gp/T/verboflex-phase04-gate-92tdd_0i` (`result.json`, `commands.json`, `backend.xml`, `backend-coverage.xml`, `frontend-coverage/cobertura-coverage.xml`, named section logs).
- Reproducible source identity: `uv run --project backend python tools/verify_phase4_closeout.py --digest`. Relevant dirty/untracked sources prevent a full run; ambient ignored build output and review/planning documents are excluded.
- Toolchain authority: `backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json`, `frontend/package-lock.json`; PostgreSQL 18 and Redis 7 isolated images. Approved regex 2026.9.3 and React Virtual 3.14.10 retained; no new dependency/version upgrade.
- Spec approval: no separate fresh SPEC approval obtained for the autonomous corrective work; it follows the pre-existing Phase04 plans/context and coordinator-authorized regression scenarios. Treat this as layered evidence, not independent proof that the specification is complete.

## Final fresh gauntlet

| Layer | Executed check | Result |
|---|---|---|
| Exact scope / fail-closed closeout | Named architecture tests, then smoke helper controls | pass; exact inventory below; 15 smoke helper tests and shell controls pass |
| Backend regression, migrations, worker | Entire `uv run pytest -q --randomly-seed=419` with JUnit and branch coverage | 1,614 passed, zero failed; 153.17 seconds; includes prior phases and real isolated worker |
| Backend changed lines | `diff-cover` versus `d987d5f48273d49234b07aacb3fa185337a1b4f2 --fail-under=100` | 3,285 / 3,285, zero missing |
| Parser branches | `coverage report --include=*/localization/importing/* --fail-under=100` | 1,817 statements and 704 branches, zero missing/partial, 100% |
| Types / lint / format | Full backend mypy, Ruff, source/test/migration formatting | 103 modules; no type/lint errors; 220 formatted files |
| Generated contract | `npm --prefix frontend run api:check` | no drift |
| Frontend regression / accessibility | Full Vitest coverage suite | 32 files, 590 passed, zero failed |
| Frontend changed lines | Cobertura `diff-cover` against the same baseline | 842 / 842, zero missing |
| Frontend types / lint / format / build | Four standard npm scripts | all exit zero |
| Supply chain | pip-audit, Python license policy, npm high audit/tree/lock/license checks and negative controls | pass under the explicit policies; disclosures below |
| Mutation | `tools/verify_translation_mutants.py` | 12 / 12 killed; baseline zero / mutant one; all sources restored byte-for-byte; 19.192 seconds |
| Built responsive browser | `translations.spec.ts` | 21 / 21 desktop/mobile journeys passed; 12.650 seconds |
| Real deployment | `bash tools/phase4_smoke.sh` from fresh application images | four formats, four roles, UUID-only broker jobs, real API/worker and built browser; redaction and own-resource cleanup pass; 62 seconds |

Whole-backend combined coverage rounds to 97% and is diagnostic, not claimed as 100%. The blocking contracts are both changed-line gates and parser branch coverage. The complete suite also runs four arbitrary-byte parser properties (configured maximum 100 examples each), one cross-format property (maximum 60), and the grapheme composition property; these do not substitute for the hostile golden fixtures or real execution.

## Source contract → executable checks

The full named mapping is [phase4_source_manifest.txt](../../tools/phase4_source_manifest.txt), validated against independent plan/context/UI inventories and executable test definitions, not merely self-referential manifest markers. Exact counts: GOAL 1, PLAN 27, REQ 20, DECISION 23, EDGE 52, EDGE_ASSUMPTION 0, PROHIBITION 2, UI_CATEGORY 8, UI_INSTANCE 50, UI_AXIS 3. The two descriptor-less values prohibitions intentionally remain flagged/unverified in the inventory; automation cannot replace their final human judgment.

| Contract / attack | Runnable selector or layer | Status |
|---|---|---|
| Stable typed identities; hostile and unsupported input closes atomically | `tests/unit/localization/importing/` plus unsafe-xml/input-bound/selector-collision mutants | pass |
| Complete single-execution activation; stale/superseded work cannot replace current data | `test_translation_import_activation.py::test_activation_advances_dataset_and_baseline_to_the_same_execution`, `::test_superseded_activation_cannot_replace_current_dataset` | pass |
| No discarded structured history or historical-only active filter matches | `test_structured_group_deletion.py` actual Android refresh | pass |
| Bounded signed cursor, literal search and authorized scope | `test_translation_search.py::test_keyset_cursor_is_bounded_tamper_proof_scope_bound_and_stale_safe`, `test_phase4_search_regressions.py` | pass |
| No deleted constraint generation reuse; role enforcement and server grapheme authority | `test_translation_constraints.py`, `test_constraint_generation_migration.py`, role-bypass/client-length-authority/code-point-count mutants | pass |
| No mixed polling/activation status or cross-product blocking | `test_import_status_activation_race.py::test_polling_and_activation_share_one_coherent_snapshot` (four interleavings) | pass |
| No constraint/activation lock inversion; post-read authority is revalidated | `test_constraint_activation_race.py` (seven cases, four real worker interleavings) | pass |
| Retained baseline permits exact constraint epochs, never forged activation or ownership | `test_retained_baseline_constraint_epoch.py` (26 cases including downgrade/reupgrade) | pass |
| No in-request parser/provider work, deferred mutations, manual frontend networking or content persistence | `test_phase4_scope.py`, `test_background_boundaries.py` | pass |
| No fabricated/downgraded security ledger or raw failure evidence | `test_phase4_closeout_gate.py`, `test_phase4_checkpoint_redaction.py` | pass |

Official API detector rerun: `node /Users/smutti/.codex/gsd-core/bin/gsd-tools.cjs check api-coverage.verify-pre 04 --raw` returned exact booleans `passed:true`, `block:false`, `detected:false`, `coverage_present:false`. No `COVERAGE.md` is created; this is the prescribed planning detector result, not a claim that provider communication does not exist.

## Independent verification and limits

Fresh-context code-review and security agents inspected the delivery separately from implementation, found behavioral defects, and rechecked the corrections. They do not establish independent model-family diversity. The coordinating GSD workflow classified the findings and required fixes rather than waivers. Their final digest-bound reports are `docs/reviews/phase-04-code-review.md` and `docs/reviews/phase-04-security-review.md`; Plan20 owns their final promotion after independently reading this final run. Delivery now passes after CR15/CR16 corrections; final report promotion is independently owned, and no stale review is relabeled as final.

No specified automated delivery layer was omitted or substituted. Live Bitbucket tenant availability is not exercised: the isolated smoke uses the audited TLS provider fixture. Assistive-technology/usability and the two transparency/values prohibitions retain human judgment; these are not silently marked automated passes. Global 100% coverage is not a newly invented requirement. No confirmed behavioral finding was dismissed; exploratory oracle mistakes and interrupted/failed runs are disclosed below.

## Independent review corrections

| Finding | Required behavior | Owner / current evidence |
|---|---|---|
| CR01 | Android plural/array item tails containing non-whitespace must fail atomically, never discard content. | RED e15f3f6 → GREEN 9f2312c; four regression cases; parser package 176 tests / 100% branches at that revision. |
| CR02 | An uncorrelated externally changed target resets Rejected as well as Approved to Draft while retaining identity and history. | RED fde78b0 → GREEN 6acf763; 22 activation tests passed. |
| CR03 | Deleting and recreating a constraint cannot resurrect an old optimistic version. | RED 5fb80d8 → GREEN 05dfbe9; durable BIGINT counter, old INTEGER epoch fenced, live versions retained, migration roundtrip passed. |
| CR04 | Separate-repository detail must report the same inherited base rule as constraint recalculation. | Search correction 2022ea9, independent recheck pending final freeze. |
| CR05 | A valid long raw key cannot break a cursor or a natural-identity database index. | Bounded v2 seek cursor 9cdb137; storage RED 2b25b57, generated SHA256 identity migration 0020. Valid 3840-character key activates losslessly; forced staging/canonical collisions roll back; exact UTF8 digests and migration roundtrip pass. |
| CR06 | Search query and stored-key Unicode case folding must agree beyond sharp-s. | PostgreSQL 18 casefold and migration 0019; dedicated real-DB regressions. |
| CR07 | Parser output and bounded API structure contracts agree without metadata amplification. | Structure contract 497b431; output budget GREEN bda72ac, 192 parser tests with 100% line/branch coverage, 13 amplification regression tests all killed the allowance mutant. |
| CR08 | A refresh discovers current members inside the confirmed layout rather than freezing preview filenames. | RED c22ea2c → GREEN 268d9c5; 65 authority/activation/worker tests passed. |
| CR09 | Bound confirmation digest need not equal the unbound preview request digest. | RED bcedbe3 → GREEN a691ab3; 67 component tests and actual browser differing-digest acceptance passed. |
| CR10 | Mixed live/tombstoned variants remain an active group with a stable deep link; current filters exclude historical-only matches. | RED eadc8fd → GREEN 1ecc596; real Android refresh, live-member constraint authority and deleted-only rejection pass. Additional historical-only violation control 64a5e38 passes. |
| CR11 / T-04-62, T-04-64 | Security closeout requires all 78 unique planned threats with unchanged severity/disposition and actual high-severity mitigation proof. | Exact-ID RED f1fceef → GREEN d17834d; metadata RED 75c4b85 → GREEN af0b9da. Five metadata attacks fail before correction; legitimate consistent SC duplicate remains valid; 59 closeout/redaction tests pass. |
| T-04-20 | Failed parser checkpoint commands cannot disclose raw source or secrets in public evidence. | Canary RED 13e4bdf → GREEN 5758d65; failures emit only safe command identity/exit/digest and remove their own raw failure log. |
| CR12 | Restoring a search snapshot cannot overwrite a newer query entered during deferred options authorization. | RED 059e127 → GREEN 645219c; new-query and cleared-query browser-component cases plus full frontend 590 tests pass. |
| CR13 | Declared search/constraint 422 schema must match both request-validation and service-error wire shapes. | RED e4413dd → GREEN 47a33ad; six real HTTP shape cases and 26 contract tests pass; generated error unions preserve wire behavior. |
| Polling/activation snapshot | Concurrent worker activation cannot produce HTTP 500 or a mixed current/not-created status projection. | RED 8f53f17 → GREEN ec6fd68; actual detail/list interleavings observe PostgreSQL lock waits and preserve cross-product progress. Four cases plus 99 adjacent tests pass, followed by smoke-only and full fresh deployment passes. |
| CR15 | Constraint mutations acquire Product first, serialize with activation without a mapping/scope cycle, and revalidate active published authority. | RED 9208fa6 → GREEN 4ee6ee0. Real PUT/DELETE interleavings fail on inverted DB lock ordering before correction; same/cross-product cases and inactive/unpublished authority pass. Seven dedicated cases, 102 combined regressions; revision-fence bypass killed with exact DID NOT RAISE oracle and source restored. |
| CR16 | A legitimate retained baseline permits only an exact epoch increment during queued/running/failed/reconciliation refresh, without weakening actual activation. | RED 9d8a8a9 → GREEN 231e5b1, migration 0021. Eight real trigger failures become green; 26 dedicated cases and 117 adjacent cases pass, including two downgrade/reupgrade cycles. Four supplementary DB-function mutants are killed; executable command records and restoration evidence are in phase-04-run.json, separately from the final twelve source probes. |
| Cursor projection epoch | Constraint edits invalidate membership-bound search cursors atomically; retries/rollback do not. | RED df45ed0 → GREEN aaf6dfc; full constraints suite and independent cursor mutation probe passed. |

## Historical intermediate results and failures (not substituted for final evidence)

- The complete `ec6fd68` run passed 1,581 backend/590 frontend tests and actual smoke (61 seconds), then independent review found CR15/CR16. Evidence commit `84cfc19` remains historical; delivery was explicitly held in `91b8486` until both fixes and the fresh run above passed. No retry was used as a bug resolution. CR15 initial combined tests were obscured by CR16's trigger exception; a DB lock-order oracle isolated two genuine lock inversions while two cross-product controls passed. One new test's nested-with lint warning was fixed before the full rerun.

- Whole backend: 1,357 tests passed in the diagnostic run; global branch coverage 94.86%, not 100%. The parser package alone is 100% including branches. Changed-line gaps are being addressed; no global coverage waiver is used to claim changed-line coverage.
- Built deployment-like smoke: commit ae274d7, four formats and four roles, real queued jobs/API/worker/built browser, redaction and cleanup passed in 60 seconds. Must rerun after the review corrections.
- Exact scope inventory: 27 plans, 20 requirements, 23 decisions, 52 unique edges, zero flagged assumptions, two prohibitions, 50 UI instances across eight categories and three axes. Named executable selectors are in tools/phase4_source_manifest.txt; this mapping is not a substitute for running those tests.
- Twelve selected semantic mutants were killed and restored byte-for-byte in an earlier diagnostic run; final gauntlet reruns them against final sources.
- Frontend changed-line gaps were closed with meaningful async authority and snapshot tests. Current CR12 source: full 590 tests pass, changed-line coverage 842/842 (100%) against the pre-Phase04 baseline. Global frontend coverage is not claimed to be 100%.
- The first attempted final run was deliberately interrupted when independent CR10 evidence arrived. Isolated resources were cleaned; it produced no passing result and is not final evidence. Full fresh backend coverage, all gates and deployment smoke remain required after CR13 freezes.
- The later complete run passed 1,577 backend tests, both changed-line 100% gates, parser 100% branches, 590 frontend tests, twelve mutations and 21 browser journeys, but failed the real deployment smoke on import-status HTTP 500. A retry passed and was explicitly not treated as a fix. Deterministic real-database interleavings then reproduced the detail 500 and list incoherence, leading to the Product-first shared-lock correction above. No failed or interrupted run is promoted to final passing evidence.
- Exact regex approval was already recorded in 04-07-SUMMARY and its license in 04-14-SUMMARY. The post-install license policy now recognizes only regex 2026.9.3 with Apache-2.0 AND CNRI-Python, tested against wrong version/name/expression/UNKNOWN. Installed Python license inventory: 107 accepted packages.
- pip-audit reports no known external-package vulnerabilities; local VerboFlex is not a PyPI distribution and is reported as unauditable by that tool. npm high-severity gate passes with two pre-existing moderate qs/typed-rest-client findings still disclosed.

## Assurance boundary

Plan19 implements the pre-existing Phase04 plan in the shared branch as directed; no new dependency or version upgrade is authorized here. Isolated disposable service instances and owner-only temporary evidence avoid user runtime data. The first polling-race oracle paused after eager scope loading and did not reproduce the error; it was rejected. The committed regression pauses in the actual job/mapping-scope read window, reproduces HTTP 500 and collection incoherence, then verifies PostgreSQL lock blocking and cross-product progress. Intermediate logs and cumulative diagnostic coverage are not substituted for the successful final fresh gauntlet above.
