---
phase: 04-localization-import-search-and-constraints
plan: 19
subsystem: testing
tags: [pytest, playwright, postgresql, celery, mutation-testing, source-bound-evidence]
requires:
  - phase: 04-18
    provides: Search/detail/constraint UI and generated API projection
  - phase: 04-22
    provides: Production import reconciliation and activation authority
provides:
  - Exact executable phase source, requirement, decision, edge, prohibition and UI inventory
  - Fail-closed source-bound closeout and complete isolated delivery gauntlet
  - Real four-format/four-role built-stack smoke and twelve deterministic mutation probes
  - Corrected parser, import, search, constraint and concurrent activation defects
affects: [04-20, 05-review-workflow, 06-bitbucket-write-back]
actuals:
  tokens: 208146
  tasks: 3
  commits: 105
tech-stack:
  added: []
  patterns:
    - Exact inventory equality plus named executable assertions and negative controls
    - Product-first shared read locks with post-lock authority revalidation
    - Source digest, exit status, sanitized command evidence and owned-resource cleanup
key-files:
  created:
    - tools/phase4_inventory.py
    - tools/phase4_source_manifest.txt
    - tools/phase4_gate.py
    - tools/phase4_gauntlet.sh
    - tools/phase4_smoke.sh
    - tools/phase4_smoke.py
    - tools/phase4_smoke_browser.mjs
    - tools/verify_translation_mutants.py
    - tools/verify_phase4_closeout.py
    - docs/evidence/phase-04.md
    - docs/evidence/phase-04-run.json
    - backend/tests/architecture/test_phase4_scope.py
    - backend/tests/architecture/test_phase4_closeout_gate.py
    - backend/tests/integration/test_import_status_activation_race.py
    - backend/tests/integration/test_constraint_activation_race.py
    - backend/tests/integration/test_retained_baseline_constraint_epoch.py
  modified:
    - backend/src/verboflex/services/import_jobs.py
    - backend/src/verboflex/services/preview_jobs.py
    - backend/src/verboflex/services/translation_imports.py
    - backend/src/verboflex/services/translation_constraints.py
    - backend/src/verboflex/services/translation_search.py
    - tools/phase4_parser_checkpoint.sh
key-decisions:
  - "Plan19 evidence requires one fresh full single-entrypoint run; targeted or historical passing runs cannot substitute."
  - "Blocking coverage is changed-line 100% for both applications plus parser branch 100%; whole-project coverage is diagnostic."
  - "Security closeout requires all 78 planned unique threat IDs with exact planned severity/disposition and real mitigation evidence."
  - "Constraint mutation and polling follow Product-first shared locking; retained baseline epoch updates require exact whole-row authority preservation."
  - "Two descriptor-less values prohibitions retain human judgment; Plan19 does not promote Plan20 phase verification."
patterns-established:
  - "Unique disposable PostgreSQL/Redis/Compose projects never modify user runtime data."
  - "Canonical full provider keys remain lossless while generated digest indexes and authenticated UUID seek anchors stay bounded."
requirements-completed: [FMT-01, FMT-02, FMT-03, FMT-04, FMT-06, FMT-07, FMT-08, SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07, SRCH-08, CONS-01, CONS-02, CONS-03, CONS-04, CONS-05]
coverage:
  - id: D1
    description: Exact executable source and exclusion inventory with fail-closed closeout
    verification:
      - kind: unit
        ref: "backend/tests/architecture/test_phase4_scope.py"
        status: pass
      - kind: unit
        ref: "backend/tests/architecture/test_phase4_closeout_gate.py"
        status: pass
    human_judgment: false
  - id: D2
    description: Full regression, migration, coverage, build, worker and built-browser delivery gate
    verification:
      - kind: integration
        ref: "bash tools/phase4_gauntlet.sh"
        status: pass
      - kind: e2e
        ref: "bash tools/phase4_smoke.sh"
        status: pass
    human_judgment: false
  - id: D3
    description: Critical parser, cursor, activation, role and server-count guarantees resist seeded regressions
    verification:
      - kind: other
        ref: "uv run --project backend python tools/verify_translation_mutants.py"
        status: pass
    human_judgment: false
  - id: D4
    description: Final transparency/values judgment and live-tenant/assistive-technology UAT
    verification: []
    human_judgment: true
    rationale: "These are explicitly retained Plan20 human judgments, not automated Plan19 passes."
duration: 171min
completed: 2026-09-06
status: complete
---

# Phase 04 Plan 19: Executable Scope and Adversarial Delivery Summary

Exact phase inventories, fail-closed closeout, 1,614 backend / 590 frontend regressions, twelve mutation probes and a real four-format/four-role built-stack smoke now pass on one frozen source state.

## Performance

- Started: 2026-09-06T09:28:12Z (first recorded Plan19 RED commit; earlier preparation is not estimated).
- Completed: 2026-09-06T12:18:18.047Z.
- Tasks: 3/3.
- Delivery files: 108; coordinated implementation window: 105 commits through `a5ec113`, including prerequisite/reviewer corrections by the coordinator and delegated executors.
- Actuals use 832584 diff characters / 4, rounded up to 208146 estimateTokens. Scope is realized backend/frontend/tools plus the two evidence files from `06cf106^` to `a5ec113`; excludes planning/review metadata and harness token usage. This is deliberately not rounded toward the original 50,000-token estimate.

## Accomplishments

1. Task 1 makes exact equality executable: 27 plans, 20 requirements, 23 decisions, 52 edges, zero flagged edge assumptions, two descriptor-less prohibitions, eight UI categories, 50 instances and three axes. Named test definitions and assertions are checked against independent plan/context/UI sources; forbidden HTTP/worker/parser/provider scope remains guarded.
2. Task 2 supplies one isolated gauntlet and actual Docker deployment smoke. All prior backend/frontend suites, migration roundtrips, safe parsers, active imports, role matrices, generated clients, builds, audits, approved licenses and worker/browser paths execute without touching user runtime data.
3. Task 3 supplies twelve deterministic source mutants, passing baselines, exact kill exit codes, bounded execution, exclusive mutation ownership and byte-exact restoration. Negative controls also prove the checker itself fails closed.

## Final Verification

Source delivery commit: `231e5b1`; digest: `sha256:2df3766ead7f1aea3597a8ad8b99205f14508a4189109996149265a163017b3a`.

Single-entrypoint command: `bash tools/phase4_gauntlet.sh`, exit 0, 2026-09-06 12:10:38–12:15:19 UTC plus bounded startup/cleanup. All 27 command records are zero. Source digest is unchanged after mutation and cleanup.

| Layer | Final result |
|---|---|
| Full backend, randomized seed 419, real worker and migrations | 1,614 passed, 153.17 seconds |
| Backend changed lines versus pre-04 baseline | 3,285/3,285, zero missing, 100% |
| Parser line/branch gate | 1,817 statements / 704 branches, zero missing/partial, 100% |
| Backend mypy / Ruff / format | 103 modules; no errors; 220 formatted files |
| Full frontend | 32 files, 590 passed |
| Frontend changed lines | 842/842, zero missing, 100% |
| Generated API, FE types/lint/format/build, supply-chain policies | Passed |
| Required source mutants | 12/12 killed, all restored, 19.192 seconds |
| Responsive browser journeys | 21/21 passed |
| Actual fresh built stack | Four formats, four roles, UUID-only queues, real API/worker/built browser, redaction and cleanup passed; 62 seconds |

Whole-backend coverage rounds to 97% and is diagnostic; no false global-100 claim. Existing moderate npm advisories and local-package audit limitations are disclosed in evidence, not waived into a clean vulnerability claim.

Canonical evidence: [phase-04.md](../../../docs/evidence/phase-04.md) and [phase-04-run.json](../../../docs/evidence/phase-04-run.json). Original owner-only records: `/var/folders/0t/8j9ddhjn68393k7yzdpwnjl80000gp/T/verboflex-phase04-gate-92tdd_0i`.

Explicit task verification entrypoints also passed: closeout `--self-test` (58 tests), mutation `--self-test` (six tests), mutation `--list`, both shell syntax checks, gauntlet `--list`, and smoke `--dry-run`. The official API-coverage detector returns exact `passed:true, block:false, detected:false, coverage_present:false`; no coverage file is invented.

## Task Commits

- Task 1 RED `06cf106`; inventory/validator `c88f4dd`; exact UI/edge/security corrections `35412b8`, `480b8c3`, `857d497`; security negative controls and metadata binding `f1fceef` → `d17834d`, `75c4b85` → `af0b9da`.
- Task 2 gauntlet `06d738f`, coverage gate `c69868b`; smoke RED `8ee6d09` → real deployment `ae274d7`; final evidence `a5ec113`.
- Task 3 RED `c4b1fdf` → mutation runner `7d6a7db`; verifier CLI corrections `9c79a7a`, `49d2057`.
- Every coordinated corrective commit in the execution window is listed below; documentation commits do not change the source digest.

## Deviations from Plan

All corrections were found while exercising Task 2's required gates or the Task 1/3 negative controls, stayed inside locked Phase04 behavior, and were authorized by the coordinator as bounded correctness prerequisites. No new dependency upgrade or deferred review/write-back feature was introduced. Detailed paths, exact selectors and historical results are preserved in the evidence report.

| Rule / correction | Issue and correction | RED / GREEN or evidence commits |
|---|---|---|
| Rule 3 — prerequisite collection/types/format | Duplicate pytest basenames, 12 parser mypy errors, stale Phase2 translation-model guards and migration formatting blocked the actual full suite; fixed without dropping coverage. | `9e07359`, `db92213` → `ff395b9` |
| Rule 1 — real preview authority | Legacy repository scope string rejected the actual Connect profile; both guards now use the approved pullrequest:write capability. | `791eb1c` → `b755ba9` |
| Rule 1 — CR01 parser tails | Non-whitespace Android item tails were discarded; reject plural/array tails atomically. | `e15f3f6` → `9f2312c` |
| Rule 1 — CR02 reconciliation | Externally changed Rejected targets did not become Draft; preserve identities/history while resetting state. | `fde78b0` → `6acf763` |
| Rule 1/2 — CR03 optimistic ABA | Rule deletion/recreation reused version1; durable per-key BIGINT generation and legacy epoch fencing in migration0018. | `5fb80d8` → `05dfbe9` |
| Rule 1 — CR04 inherited detail | Separate-repository detail used the wrong base-key join; use scope/raw-key inheritance. | `2022ea9` |
| Rule 1/2 — CR05 bounded identity | Long keys overflowed cursors/B-tree indexes; lossless full keys plus authenticated UUID seek and generated SHA256 unique identity0020, collisions fail closed. | `9cdb137`, `2b25b57` → `39725a9` |
| Rule 1 — CR06 Unicode | Python casefold and SQL normalization differed; use real PostgreSQL18 Unicode folding and bounded indexes0019. | `676f71c`, `69b6de9` |
| Rule 1/2 — CR07 output bounds | API structure bounds disagreed with valid parsers and repeated metadata amplified output; shared bounded contract and incremental20MiB aggregate budget. | `497b431`, `62f53d4` → `bda72ac` |
| Rule 1 — CR08 refresh discovery | Worker froze old preview file membership; re-detect current members within exact confirmed layout authority. | `c22ea2c` → `268d9c5` |
| Rule 1 — CR09 confirmation UI | Bound response digest was wrongly compared with unbound request digest; validate response authority and generation fences. | `bcedbe3` → `a691ab3` |
| Rule 1 — CR10 mixed groups | One tombstone hid live siblings; preserve stable group UUID and history, filter current members, allow constraints only with live authority. | `eadc8fd` → `1ecc596`, `64a5e38` |
| Rule 2 — CR11 security ledger | Fabricated/missing/downgraded threat rows could pass; require exact78 planned IDs and metadata, consistent sharedSC, actual mitigation proof. | `f1fceef` → `d17834d`, `75c4b85` → `af0b9da` |
| Rule 2 — checkpoint redaction | Failure helper printed raw output; only safe identity/exit/digest is public and own failed raw log is removed. | `13e4bdf` → `5758d65` |
| Rule 1 — CR12 query restoration | Deferred options overwrote a newer search query; retain snapshot/query generation equality. | `059e127` → `645219c` |
| Rule 1 — CR13 API422 | Declared string error excluded framework validation arrays; generated union now matches both existing wire shapes. | `e4413dd` → `47a33ad` |
| Rule 1 — CR14 polling race | Worker commit between authority reads caused500 or current/not_created; Product-first shared lock makes detail/list snapshots coherent. | `8f53f17` → `ec6fd68` |
| Rule 1 — CR15 lock inversion | Constraint scope→mapping conflicted with activation Product→mapping→scope; shared Product first and fresh post-lock authority prevent the cycle. | `9208fa6` → `4ee6ee0` |
| Rule 1 — CR16 retained epoch | Constraint projection increment re-ran strict current-execution activation checks during refresh;0021 permits exact epoch-only authentic retained baseline updates, preserving all other guards. | `9d8a8a9` → `231e5b1` |
| Rule 1 — remaining runtime/UI regressions | Explicit HTTP page_size50 string normalization; genuine UI audit issues, POST/options readiness races, cursor invalidation and deleted orphan preservation corrected under targeted tests. | `652cd7a` → `d257545`, `5854228`, `7d3f9d3`, `df45ed0` → `aaf6dfc`, `c3ac604` → `7245cad` |

Invariant-backed removal of unreachable internal frontend continuation and bounded cursor-output guards preserved all untrusted transport/decoder fences and gained maximum-valid-input regressions; no pragma/noqa/line-touch coverage waiver was used. Supplementary semantic probes killed the removed authority defenses. Package policy admits only the pre-approved exact regex identity/version/SPDX tuple; wrong versions/identities/expressions/UNKNOWN fail.

## Issues Encountered

The first full attempts exposed real UI/runtime bugs, changed-line gaps, a formatting failure and a real import polling500. Interrupted runs cleaned their own resources and never wrote a passing result. A smoke-only retry happened to pass but was explicitly not treated as a resolution; deterministic HTTP interleavings led to CR14. The complete `ec6fd68` gate then passed honestly before independent review discovered CR15/CR16; closeout was reopened, both were corrected, and the final complete run above replaced it. Historical evidence and unsuccessful oracle designs remain disclosed.

The Docker desktop credential helper stalled isolated image builds; an anonymous temporary Docker client configuration resolved that without changing user Docker credentials. Synthetic TLS Bitbucket and unique disposable databases/volumes supply real API/Celery/browser execution, not a live-tenant claim.

## TDD Gate Compliance

Behavioral defects have observed RED tests before GREEN commits. Immediately passing boundary extensions were checked with semantic negative controls rather than claimed as new REDs. CR15's two lock-order failures and inactive-authority failure precede its GREEN; cross-product positives were already passing. CR16 has eight actual database RED failures,26 final cases,117 adjacent passes and four killed DB-guard mutants with exact restore. The final persisted twelve-probe runner is independently fail-closed tested.

## Known Stubs and Threat Surface

No new functional stub or skipped planned automated verification remains. Diff scan found only normal HTML placeholder styling/hints and a synthetic preview fixture's empty result before its explicit authority setup; these do not supply fake product data. No new network endpoint, provider write permission or unregistered trust surface was added. Migrations0018–0021 strengthen the existing identity/concurrency trust boundary and were independently reviewed; all planned threat IDs remain accounted for.

## User Setup and Next Plan Readiness

No setup is required for the repeatable isolated automated gate. Approved dependency pins and user runtime data are unchanged.

Plan04-20 can consume the final source-bound evidence and independently promote code/security/Nyquist/UI/goal verification. Live Bitbucket and assistive usability, plus the two transparency/values prohibitions, remain human judgment; this summary does not claim that Phase04 is already finally verified. The old-coder workflow influenced this delivery through executable RED/GREEN contracts, meaningful coverage, mutation probes and honest source-bound evidence; no new separate human SPEC approval was obtained for autonomous corrections.

## Coordinated Commit Ledger

- `06cf106` test(04-19): specify exact coverage and fail-closed closeout
- `9e07359` fix(04-19): restore strict phase-wide collection and type gates
- `c4b1fdf` test(04-19): require killed mutants and byte-exact restoration
- `c88f4dd` feat(04-19): enforce source equality and structured closeout verdicts
- `8ee6d09` test(04-19): specify isolated smoke dry-run contract
- `7d6a7db` feat(04-19): kill twelve semantic regressions with reversible probes
- `9c79a7a` test(04-19): bind closeout CLI to downstream plan contract
- `49d2057` fix(04-19): accept prescribed closeout paths and bind untracked sources
- `d4f8dc4` test(04-18): reproduce audited UI contract and recovery defects
- `791eb1c` test(04-19): expose preview rejection of current Connect authority
- `b755ba9` fix(04-19): align preview authority with current Bitbucket capability
- `db92213` fix(04-19): preserve legacy architecture checks under full collection
- `35412b8` test(04-19): reject unproven flagged edge assumptions
- `5854228` fix(04-18): align audited UI contracts and accessible recovery
- `480b8c3` test(04-19): reject severe security waivers without mitigation proof
- `857d497` feat(04-19): bind named edge and UI proof to strict closeout authority
- `06d738f` feat(04-19): run isolated full-stack gauntlet with fail-closed evidence
- `ff395b9` fix(04-19): qualify dynamic legacy guard imports for full collection
- `c69868b` fix(04-19): enforce configured backend coverage and smoke tooling gates
- `d537db1` test(04-18): require approved base-language warning weight
- `7d3f9d3` fix(04-18): align base-language warning with approved weight
- `0a1ebfe` docs(04): record independent UI audit and verified corrections
- `7a8da40` test(04-19): reproduce obsolete post-acceptance import expectation
- `afa86f7` test(04-19): distinguish pending import dispatch from server acceptance
- `250ce26` style(04-19): format filter interaction regression
- `652cd7a` test(04-19): reproduce explicit translation page size rejection
- `d257545` fix(04-19): normalize the supported translation page size query
- `ae274d7` feat(04-19): verify isolated four-format deployment smoke
- `e596796` test(04-19): bind approved regex license to one exact release
- `3f95b64` fix(04-19): recognize the previously approved exact regex license
- `6a37434` test(04-19): cover canonical input authority and service failure boundaries
- `e15f3f6` test(04-19): expose discarded Android structured item tails
- `1f60cd6` test(04-19): verify API rollback and production worker boundaries
- `9f2312c` fix(04-19): reject unsupported Android structured item tails
- `fde78b0` test(04-19): expose rejected-state refresh and preserve reconciliation context
- `acce79f` test(04-19): reproduce separate limits and long key cursor failures
- `5fb80d8` test(04-19): expose stale constraint versions after delete and recreate
- `2022ea9` fix(04-19): resolve detail base limits across repository sides
- `6acf763` fix(04-19): reset externally changed rejected translations to draft
- `9cdb137` fix(04-19): resolve bounded seek cursors from authorized groups
- `f52846b` test(04-19): reproduce Unicode search mismatch and align cursor v2 probes
- `676f71c` fix(04-19): align Unicode search and indexes with caseless matching
- `bcedbe3` test(04-09): reproduce language-bound confirmation digest rejection
- `5b5636a` docs(04): preserve independent review findings pending remediation
- `a691ab3` fix(04-09): accept server-bound preview confirmation digests
- `05dfbe9` fix(04-19): preserve constraint generations across removal
- `57a3920` test(04-19): reproduce parser and detail structure bound mismatch
- `df45ed0` test(04-19): require constraint edits to invalidate dataset cursors
- `aaf6dfc` fix(04-19): invalidate cursors on constraint projection changes
- `c3c3cff` test(04-19): preserve the approved iOS comment structure boundary
- `2b25b57` test(04-19): reproduce valid long-key import storage failure
- `497b431` fix(04-19): share bounded complete structures across parsing and detail
- `c22ea2c` test(04-19): reproduce confirmed-layout refresh membership loss
- `268d9c5` fix(04-19): discover refresh files within confirmed layouts
- `8f6ba39` test(04-19): require typed independent review scope metadata
- `768de71` fix(04-19): retain validated independent review scope metadata
- `b8ec2e8` test(04-19): reject cursors after effective constraint changes
- `39725a9` fix(04-19): bound key identity indexes without truncating source text
- `62f53d4` test(04-19): expose canonical output amplification across adapters
- `664fd75` test(04-19): enforce changed-line gates for both applications
- `4f82e43` docs(04-19): record review corrections and remaining assurance gaps
- `1c9a017` test(04-19): cover search restoration and frontend authority failures
- `ea8a414` refactor(04-19): remove unreachable internal continuation guard
- `d0a7646` test(04-19): reproduce route preference readiness race
- `b39a0fd` test(04-19): await authorized route options before preference assertions
- `c3ac604` test(04-19): keep deleted empty keys tombstoned during refresh
- `93cbe52` test(04-19): type deferred option success with generated contract
- `bda72ac` fix(04-19): bound canonical expansion while building every adapter
- `7245cad` fix(04-19): do not revive keys without live canonical values
- `69b6de9` test(04-19): verify signed cursor grammar and seek anchor authority
- `31c6e63` test(04-19): require committed inputs for final delivery evidence
- `5640ab6` test(04-19): exercise authority loss and safe public failure boundaries
- `83bfddf` test(04-19): prove maximum valid cursor envelope remains bounded
- `2b3b0d6` refactor(04-19): remove unreachable bounded cursor output branch
- `eadc8fd` test(04-19): retain active structured siblings after partial deletion
- `8bb6dfe` docs(04-20): record confirmed final review blockers and remaining scope
- `1ecc596` fix(04-19): preserve live groups and stable authority across variant deletion
- `f1fceef` test(04-19): reject incomplete or fabricated security threat ledgers
- `d17834d` fix(04-19): require complete unique planned security threat evidence
- `059e127` test(04): reproduce query loss while restoring search navigation
- `645219c` fix(04): preserve queries edited during search restoration
- `13e4bdf` test(04-19): prevent raw checkpoint failure output disclosure
- `5758d65` fix(04-19): redact and discard raw checkpoint command failures
- `a5c4029` style(04-19): format complete security ledger fixture
- `5d3e49e` docs(04): record independent security findings and planned risk log
- `75c4b85` test(04-19): reject downgraded and conflicting planned threat metadata
- `64a5e38` test(04-19): separate live constraint filters from tombstone history
- `af0b9da` fix(04-19): bind security verdicts to authoritative threat metadata
- `9571990` docs(04-19): record independently discovered closeout corrections
- `e4413dd` test(04): expose undocumented translation validation error shapes
- `47a33ad` fix(04): document actual translation validation error unions
- `df90536` style(04-19): format the preserved historical phase boundary assertion
- `8f53f17` test(04-19): reproduce mixed import polling snapshots during activation
- `ec6fd68` fix(04-19): serialize import status snapshots with activation authority
- `4c6afe3` docs(04): preserve independent reviews and runtime closeout blocker
- `3100abd` docs(04): bind independent security pass to final gauntlet
- `84cfc19` docs(04-19): record fresh source-bound full gauntlet and smoke evidence
- `26bb0c9` docs(04): reopen release audit for confirmed refresh constraint gaps
- `55d3960` docs(04): record proven constraint refresh concurrency blockers
- `9208fa6` test(04-19): reproduce constraint activation lock inversion
- `9d8a8a9` test(04-20): reproduce retained baseline constraint epoch rejection
- `91b8486` docs(04-19): hold delivery closeout for confirmed concurrency defects
- `4ee6ee0` fix(04-19): serialize constraint mutations before activation locks
- `231e5b1` fix(04-20): permit authenticated retained baseline epoch increments
- `a5ec113` docs(04-19): bind final gauntlet evidence after concurrency corrections

## Self-Check: PASSED

All key artifacts above exist. Every commit in the coordinated ledger resolves in this repository. The final result/command metadata contains27 zero exits,12 killed/restored mutations and successful smoke cleanup, and the current delivery digest equals the recorded digest. Source files were not changed by evidence or planning updates.
