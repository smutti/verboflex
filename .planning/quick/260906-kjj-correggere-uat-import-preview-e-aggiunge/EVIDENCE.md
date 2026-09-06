# Quick 260906-kjj — partial implementation checkpoint

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
