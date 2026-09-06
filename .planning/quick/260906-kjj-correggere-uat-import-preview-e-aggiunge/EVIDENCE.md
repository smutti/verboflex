# Quick 260906-kjj — implementation evidence

## 2026-09-06 final approved implementation — GREEN and deployed locally

The approved quick-task implementation is complete at source digest `sha256:ac5ac91cec32207560b2ae3002c6b4940aa9d82f6182c58a6fb189746a5e259c`.

- Final isolated backend gate: **1,680 passed** with randomized seed 419, PostgreSQL 18, Redis 7 and a real Celery worker; 169.27s and 97% whole-project coverage. Changed-line coverage against `25b7a95`: **183/183 executable lines, 100%**. Mypy passed for 111 source files and Ruff lint passed. Owner-only evidence: `/var/folders/0t/8j9ddhjn68393k7yzdpwnjl80000gp/T/verboflex-phase04-gate-ohhw1os6`; command-output SHA-256 `9d3bee3900717932979b50f2fe8e4931fa7cf696d6f61d02dbd85f81475d0561`.
- Final frontend gate: **603 passed** across 33 files; TypeScript, ESLint, Prettier and the production build passed. Coverage was 87.14% statements / 80.58% branches / 88.10% lines; changed-line coverage was **49/49, 100%**. Vite retains the known advisory for a minified chunk above 500 kB.
- The generated OpenAPI document and TypeScript client reproduce cleanly. Python dependency audit reports no known third-party vulnerabilities. npm reports no high-severity finding; two pre-existing moderate `qs` findings remain through `typed-rest-client` and were not auto-upgraded in this no-new-dependency change.
- A private pre-migration PostgreSQL backup was retained at `/var/folders/0t/8j9ddhjn68393k7yzdpwnjl80000gp/T/verboflex-pre-kjj-backup.XXXXXX.Fb6r0HXgwe/verboflex.dump` (157,340 bytes, mode 0600, SHA-256 `1a62cd08fd65c35f9c3176de99c311b758c41d9c333d9f6bbedf9e237f9b9ca8`). Local Docker was rebuilt and migrated from 0021 through `0025_preview_diagnostics (head)`; backend, frontend, PostgreSQL, Redis and worker are healthy, Celery ping returns one node, `/api/v1/health` returns `ok`, and `/login` returns HTTP 200.
- A local bearer-authorized smoke created one uniquely named disposable product, deleted it through the new endpoint, and verified its detail becomes 404. No existing product was deleted. Logical deletion retains history and releases only the live normalized name; queued/running preview or import work blocks deletion with 409.
- Duplicate source inspection now enumerates Android/MOKO, JSON, iOS `.strings` and Qt `.ts` occurrences while canonical parsers remain strict. Preview and import responses expose only bounded report summaries, and the UI opens the existing read-only paginated duplicate report only when a report is actionable. Repository scan exhaustion has a stable diagnostic and asks for a narrower localization root.
- The live read-only Babel evidence remains commit `6102ff5a2ba6a50bbf1d24f75f6e2a7fb3e7c625`: 19 files, 3,570,592 bytes and 145 duplicate groups. This is a successful complete diagnostic, **not** a canonical import. Babel remains blocked until the duplicates are fixed in Bitbucket; no first/last-wins behavior, partial activation or provider write was introduced.

Human authenticated browser UAT was not auto-passed. The public login page was visually reachable after deployment, but the previously supplied password did not authenticate the sole current admin during the smoke attempt, so the authenticated UI verification remains for the user (or a separately authorized credential reset). This does not affect the bearer/API, role-matrix, UI component, migration or worker checks above. No push, PR or merge was performed.

## 2026-09-06 approved lossless MOKO semantics — GREEN checkpoint

Approved executable contract: `SPEC-MOKO-SEMANTICS.md`, approval message "Approvo", specification commit `555ffd2`.

- M1/M2: `backend/tests/unit/localization/importing/test_moko_semantics.py` proves literal unknown MOKO escapes, known-escape decoding, malformed Unicode/trailing-backslash rejection and unchanged generic Android rejection.
- M3/M4: the same file proves opaque direct `<resources>` text creates no identity, real resource positions remain stable, minimal scalar replacement preserves all bytes outside the selected body, self-closing values work, forged locators fail, and forbidden XML structures remain rejected.
- M5: the duplicate test combines opaque text, literal escapes and duplicates and now produces a complete exact report. The durable read-only live probe against repository UUID `ee938eee-26bb-4f69-920f-bce502bba261`, branch `master`, root `babel/src/commonMain/moko-resources`, commit `6102ff5a2ba6a50bbf1d24f75f6e2a7fb3e7c625` reports 19 files / 3,570,592 bytes / 145 groups / 145 repeated occurrences / `diagnostic_complete=true` / no issue codes / canonical import `blocked_by_duplicates`. No source text, keys, credentials or provider writes were emitted.
- M6: Hypothesis ran 80 bounded parse/edit combinations per suite run. A manual mutant that dropped the backslash from an unknown escape was executed; the property failed with `\\z` becoming `z`, then passed after exact restoration.

Fresh source-bound checks after the final code edit:

- `tools/phase4_gate.py --section backend-tests-migrations-parsers-worker`: **1664 passed**, randomized seed 419, 172.67s, whole-project branch coverage 97%. Gate command exit 0, source digest `sha256:6528f86d7d8faac19397612f04aac609e2b5fdb92950e8732c30ddf7ce6d1bb3`, private evidence `/var/folders/0t/8j9ddhjn68393k7yzdpwnjl80000gp/T/verboflex-phase04-gate-_293_409`, output SHA-256 `49eb930c5fcd74fb2120d0e657fff6e3a729e4856710ccc7ff7255d1cdf1f3ff`.
- `diff-cover ... --compare-branch=555ffd2 --fail-under=100`: **82/82 changed executable lines, 100%**.
- Targeted parser/architecture regression: **119 passed**. Ruff and mypy: pass, 111 source files. `git diff --check`: pass.
- The first full isolated attempt correctly failed 4 tests: one compatibility default was missing and the new module bypassed the parser registry. Production code was corrected (no architecture-test exemption); the 35 focused regressions passed before the fresh full run. Failed evidence is retained at `/var/folders/0t/8j9ddhjn68393k7yzdpwnjl80000gp/T/verboflex-phase04-gate-ab6lr9fg`.

This closes only the approved MOKO semantic addendum. Babel remains blocked by source duplicates and has not been canonically imported. The broader quick task remains incomplete: no Docker upgrade, product deletion, push, PR, merge or UAT state change.

## 2026-09-06 source-bound regression checkpoint (not release-ready)

- Isolated `tools/phase4_gate.py --section backend-tests-migrations-parsers-worker`: **1647 passed**, randomized seed 419, real isolated PostgreSQL/Redis/worker, 177.27s. Gate reports **partial**, not full gauntlet. Source digest before this evidence edit: `sha256:2f4af99f2a109b35f9263a8f0d23c44c5fd8e0a9d7216fa21140b11ff50f94c8`. Private evidence directory: `/var/folders/0t/8j9ddhjn68393k7yzdpwnjl80000gp/T/verboflex-phase04-gate-1y2qh9g8`; command log SHA-256 `8c3c0eaadbe1eb7322e9544eb363558cfded9097188060340909ed8a07da9796`.
- Frontend: **596 passed**, TypeScript, ESLint and production build passed. Existing large-chunk warning remains visible.
- Backend Ruff and mypy: passed (110 source files). `git diff --check`: passed.
- Fresh 50,000-value synthetic parser/staging/initial-activation probe, with actual content sizes/hashes: **95.35s / 477.22 MiB**, within the approved 240s/512MiB target; concurrent isolated regression suite was running. This harness does NOT execute under Celery's timeout. Default import timeouts still need the approved coordinated extension from 60/75 to 180/240 before claiming production capacity. No search/refresh/Babel success claim.
- Additional stored-report API integration tests pass: unauthenticated 401, every non-admin role 403, missing/wrong product/execution 404, unfinished 409, filter/cursor mismatch 422, group and occurrence pagination, exact commit identity, idempotent report storage. Worker-root alias tests first reproduced acceptance of encoded roots (`%74ranslations`, `translations/%2e`), then pass after using the same canonical root validator as the API.
- The staged-source changed-line gate against approval commit `7f5a934` is **NOT PASSING: 443/478 executable lines (92%, 35 missing)**. This includes new files; an earlier unstaged run omitted them and is not used as final evidence. Whole-project coverage 97% does not replace this gate. Mutation/property/browser/security/deploy gates remain pending.

Checkpoint only: current tests are green, but the approved task is incomplete. No Docker upgrade, remote write, product mutation, PR, push or UAT advance. Additional unsupported MOKO escapes and inter-element text remain an explicit semantic contract gap; diagnostics fail closed. Deletion and the other pending work below remain approved, not cancelled.

## 2026-09-06 approved capacity/diagnostics extension — work in progress

The later `Approvo` approved SPEC-IMPORT-CAPACITY-DUPLICATES.md; approval commit 7f5a934. The historical S1/S2 evidence below is not a claim about the current expanded diff.

Implemented checkpoints now include root persistence/API/UI and worker propagation, MOKO layout classification, independent mapping capacity, worker-stored duplicate reports and read-only paginated UI, streaming exact manifests and batched initial activation. None is deployed or claimed phase-complete yet. Product deletion remains pending under the existing approval.

Contract-test changes authorized by C1/C4/S4 (not relaxed assertions): aggregate limit test monkeypatches now address MAX_CANONICAL_MAPPING_VALUES; former shared-20-MiB tests explicitly reduce the new aggregate-byte budget to exercise the same rejection path. Root response snapshots gain only the two nullable root fields. Exact OpenAPI/client operation inventories must add only the two approved GET duplicate-report children; model inventories add only duplicate_report.py. Existing uniqueness, bearer protection, parser boundary and provider-write prohibitions remain intact. RED full suite exposed those closed inventories before their additive updates. The parser-boundary failure will be fixed by routing inspection through the registry, not by exempting the diagnostic module.

Real Babel read-only probe at master / 6102ff5a2ba6a50bbf1d24f75f6e2a7fb3e7c625 found 19 files, 3,570,592 bytes, 145 duplicate groups and 145 extra occurrences: base 25, bg 31, de 8, es 8, fr 28, it 30, nl 8, pt 7. The semantic diagnostic is explicitly INCOMPLETE: the compatible Android XML parser also rejects unknown escape sequences and non-whitespace text between string elements. Those cases remain blocked, not discarded or normalized. The safe fallback extracts source identities only; it does not create canonical values. No remote content or credentials were committed. The approved MOKO addendum requires surfacing additional semantic gaps before changing their interpretation.

Scale measurements, fresh processes / local PostgreSQL 18 test harness / Python 3.14.7: initial 50,000-value implementation 271.48s / 1051.56 MiB peak RSS (FAIL); intermediate ORM batching 161.98s / 1144.94 MiB (FAIL); bounded empty-scope insert batches and streaming manifest 48.75s / 442.02 MiB (PASS for synthetic parser+staging+activation only). This is not a live Babel import, a 50,000-value refresh benchmark, or a search proof. Benchmark source references are being corrected to hash the actual synthetic bytes before the final rerun.

Targeted passes so far: 514 backend localization/mapping/preview tests; 28 activation tests after batching; 184 frontend mapping/preview/import tests; dialog behavior RED (missing button from null stub) then GREEN. Full frontend first run: 595 pass / one additive operation-inventory mismatch; that inventory was then updated and its 18 tests pass. Full backend first run: 1623 pass / 14 failures, comprising closed inventories, parser boundary, missing root attributes in test doubles, one migration test leaving its module database at revision 0020, and unavailable isolated Redis/worker. The 0020 round-trip must restore head after its assertions. These are not a green final gate.

Still required: final complete suites with the proper isolated worker; extended report ownership/cursor/retry/late-execution tests; all-format duplicate occurrence enumeration (non-Android adapters currently fail closed at their first intra-file duplicate); per-file/output trust-boundary checks; 19-file MOKO scale/search and refresh measurement; cheap report summaries; complete root/diagnostic UI authority tests; S5 bounded-discovery messaging; product deletion; migration round-trip, changed-line/mutation/property/browser/security gates; private backup and Docker upgrade. No UAT status advance, push, PR or merge.

Date: 2026-09-06. Not a completed task, deployment, canonical Babel import or UAT pass.
Approved contracts: SPEC.md v1 and SPEC-MOKO-ADDENDUM.md (approval recorded in 2c301d9).

## Implemented slice: S1/S2

ProductMappingsPage now fetches product publication/activation authority even when a candidate-version prop is supplied. Draft-only and inactive published products display explanatory states without requesting published imports. Active published products retain real import failures and their retry behavior. Published import access does not depend on having a candidate revision. Product/token identity and existing abort/generation guards fence obsolete authority.

TDD:
- New draft-only test failed because the published-import endpoint was called once.
- New inactive-published test failed because the reactivation explanation was absent.
- Both passed after implementation; the existing 17 mapping tests also passed.
- Added a regression for published products without candidates; it failed because import access had become coupled to candidate availability. Separated those authorities. The new test initially used an ambiguous global button selector (desktop and mobile controls both exist); corrected it to the named published-import table, retaining the same enabled-button assertion.
- Existing fixtures now return publication authority by default; prior behavioral assertions are unchanged.

Fresh checks after the final source formatting:

```sh
cd frontend
npm run test:coverage -- --coverage.reportsDirectory=/tmp/verboflex-kjj-ui-final-coverage --coverage.reporter=cobertura
npm run typecheck
npm run lint
npm run format:check
npm run build
cd ../backend
uv run diff-cover /tmp/verboflex-kjj-ui-final-coverage/cobertura-coverage.xml --compare-branch=2c301d9 --fail-under=100
uv run pytest tests/unit/localization/importing/test_android_xml.py tests/unit/localization/importing/test_conformance.py -q
```

- Frontend: 32 files, 593 tests passed (including 20 mapping tests).
- TypeScript, ESLint and Prettier: passed. Initial formatting check identified the two changed files; formatted them and reran checks.
- Build: passed; existing-style bundle warning for a chunk over 500 kB remains, not suppressed.
- Changed-line coverage: 7/7 reported executable lines, 100%, enforced by diff-cover exit status. This is instrumented-line coverage, not a claim that every new JSX branch or race has been independently verified.
- `git diff --check`: passed.
- Existing Android canonical parser and cross-format conformance tests: 94 passed. These preserve the current limit/duplicate contracts; they are not a MOKO or real Babel import test.

## Additional real Babel findings: contract checkpoint

Repeated the read-only structural probe described in BABEL-IMPORTABILITY.md against the same source commit 6102ff5a2ba6a50bbf1d24f75f6e2a7fb3e7c625 on master. Again: 20 pages, 19 files, 3,570,592 bytes, zero production preview candidates. Only structure/counts were emitted; no source text, credentials, remote writes or user-product changes.

The expanded probe counts every resources/string child and unique name per file:

| Directory | String elements | Unique names | Repeated occurrences beyond first |
| --- | ---: | ---: | ---: |
| base | 4321 | 4296 | 25 |
| bg | 3956 | 3925 | 31 |
| de | 2651 | 2643 | 8 |
| es | 2650 | 2642 | 8 |
| fr | 2953 | 2925 | 28 |
| it | 3195 | 3165 | 30 |
| nl | 2411 | 2403 | 8 |
| pt | 2380 | 2373 | 7 |

The other eleven files have no repeated names. All nineteen contain 42,766 string elements; 145 occurrences repeat names within their own file. This is NOT 145 distinct duplicated keys, nor a count of successfully parsed/imported canonical values. Nested tags observed are b and u, compatible with the existing canonical Android tag vocabulary; metadata and duplicate handling still require exact import verification.

Two independent blockers remain beyond path recognition:

1. The approved addendum explicitly requires duplicate keys to fail closed. Source duplicates cannot be silently resolved by choosing first/last values, skipped, or edited on Bitbucket without separate authority.
2. `localization/importing/core.py` sets MAX_CANONICAL_VALUES=5000; `localization/importing/registry.py` enforces that bound on the complete mapping. Even the sum of per-file unique names is 42,621, far above that ceiling. The addendum explicitly preserves existing budgets. Supporting this repository's complete volume therefore requires an explicit capacity-contract change, not merely the approved MOKO path adaptation or localization-root configuration.

Do not reinterpret preview discovery success, XML structural parsing, or per-file parsing as a successful complete canonical import. Do not automatically infer base=English. No capacity increase or source deduplication was implemented.

## Pending and assurance limits

- S3–S5: root schema/API/UI, propagation, bounded diagnostics — not implemented.
- S6–S10: logical deletion/API/UI/migration/concurrency — not implemented; existing approval remains valid.
- MOKO production support and isolated Babel import/search — not implemented; blocked by the additional capacity/source-data findings above.
- Full backend suite, randomized suite, mutation/property additions, dedicated security review, browser smoke, fresh Docker backup/rebuild/migration and full gauntlet — pending, not claimed passed.
- Independent old-coder blind verification: not performed.
- Local Docker remains on the previous build. No database migration, product deletion, publication, push, PR or merge was performed.
- Temporary probe is diagnostic evidence, not yet the durable parameterized tool required by the approved addendum. Full task completion still requires that tool and the focused reproducible gate.

Next: obtain direction on Babel capacity beyond the approved 5000-value bound and retain duplicate-key rejection; resume the remaining already-approved slices without asking to approve them again.
