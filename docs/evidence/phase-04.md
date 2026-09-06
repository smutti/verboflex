---
phase: 04
status: in_progress
---

# Phase 04 evidence — closeout in progress

This is a working ledger, not passing closeout evidence. The final source digest and fresh complete gate results are not frozen yet.

## Independent review corrections

| Finding | Required behavior | Owner / current evidence |
|---|---|---|
| CR01 | Android plural/array item tails containing non-whitespace must fail atomically, never discard content. | RED e15f3f6 → GREEN 9f2312c; four regression cases; parser package 176 tests / 100% branches at that revision. |
| CR02 | An uncorrelated externally changed target resets Rejected as well as Approved to Draft while retaining identity and history. | RED fde78b0 → GREEN 6acf763; 22 activation tests passed. |
| CR03 | Deleting and recreating a constraint cannot resurrect an old optimistic version. | RED 5fb80d8 → GREEN 05dfbe9; durable BIGINT counter, old INTEGER epoch fenced, live versions retained, migration roundtrip passed. |
| CR04 | Separate-repository detail must report the same inherited base rule as constraint recalculation. | Search correction 2022ea9, independent recheck pending final freeze. |
| CR05 | A valid long raw key cannot break a cursor or a natural-identity database index. | Bounded v2 seek cursor 9cdb137; storage RED 2b25b57, generated SHA256 identity migration 0020. Valid 3840-character key activates losslessly; forced staging/canonical collisions roll back; exact UTF8 digests and migration roundtrip pass. |
| CR06 | Search query and stored-key Unicode case folding must agree beyond sharp-s. | PostgreSQL 18 casefold and migration 0019; dedicated real-DB regressions. |
| CR07 | Parser output and bounded API structure contracts agree without metadata amplification. | Structure contract 497b431 passed 220 tests; aggregate output budget correction in progress. |
| CR08 | A refresh discovers current members inside the confirmed layout rather than freezing preview filenames. | RED c22ea2c → GREEN 268d9c5; 65 authority/activation/worker tests passed. |
| CR09 | Bound confirmation digest need not equal the unbound preview request digest. | RED bcedbe3 → GREEN a691ab3; 67 component tests and actual browser differing-digest acceptance passed. |
| Cursor projection epoch | Constraint edits invalidate membership-bound search cursors atomically; retries/rollback do not. | RED df45ed0 → GREEN aaf6dfc; full constraints suite and independent cursor mutation probe passed. |

## Verified intermediate results (not final closeout)

- Whole backend: 1,357 tests passed in the diagnostic run; global branch coverage 94.86%, not 100%. The parser package alone is 100% including branches. Changed-line gaps are being addressed; no global coverage waiver is used to claim changed-line coverage.
- Built deployment-like smoke: commit ae274d7, four formats and four roles, real queued jobs/API/worker/built browser, redaction and cleanup passed in 60 seconds. Must rerun after the review corrections.
- Exact scope inventory: 27 plans, 20 requirements, 23 decisions, 52 unique edges, zero flagged assumptions, two prohibitions, 50 UI instances across eight categories and three axes. Named executable selectors are in tools/phase4_source_manifest.txt; this mapping is not a substitute for running those tests.
- Twelve selected semantic mutants were killed and restored byte-for-byte in an earlier diagnostic run; final gauntlet reruns them against final sources.
- Fresh frontend full suite passes; changed-line diagnostic is 791/844 executable lines (93%, 53 missing). Those gaps remain blocking; test-only remediation is in progress. No full frontend coverage claim is made.
- Exact regex approval was already recorded in 04-07-SUMMARY and its license in 04-14-SUMMARY. The post-install license policy now recognizes only regex 2026.9.3 with Apache-2.0 AND CNRI-Python, tested against wrong version/name/expression/UNKNOWN. Installed Python license inventory: 107 accepted packages.
- pip-audit reports no known external-package vulnerabilities; local VerboFlex is not a PyPI distribution and is reported as unauditable by that tool. npm high-severity gate passes with two pre-existing moderate qs/typed-rest-client findings still disclosed.

## Assurance boundary

Plan19 implements the pre-existing Phase04 plan in the shared branch as directed; no new dependency or version upgrade is authorized here. Isolated disposable service instances and owner-only temporary evidence avoid user runtime data. Intermediate logs and cumulative diagnostic coverage are not substituted for the required final fresh gauntlet.
