# Phase 3 Code and Security Review

- Review-status: CLOSED
- Open-critical-high: 0
- Full-gauntlet-status: PASS
- Reviewed-source-digest: `e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c`
- Review-standard: OWASP ASVS 5.0 Level 1
- Review-scope: Every one of 331 manifest-selected paths plus 21 additional Phase 3 diff paths, 352 unique paths across `4c557f5147038c4b09dc6dcf26d7b26675884bb5..a6e17381b3d7001722259a3cd5ece582fc30f4f4`
- Review-date: 2026-09-03
- Structured-review: `.planning/phases/03-bitbucket-import-integration/03-REVIEW.md`

## Verdict

The final fresh independent deep review reports zero unresolved Critical or
project High-equivalent findings on the exact review-mode digest above. The
typed reviewer truthfully reports `status: issues_found` because eight Warning
findings remain open; at the configured High blocking threshold those warnings
do not replace or weaken the zero-blocker result.

The reviewer independently reproduced the digest, reconciled the complete
manifest/diff union, and traced the production implementation rather than
accepting gauntlet prose as proof. It confirmed the late-INSERT,
cross-execution-reparenting, and mixed-side-delta remediation paths. The final
post-remediation gauntlet passed all 14 layers on the same source: backend
952/952, frontend 356/356, backend mutation 6/6, frontend mutation 25/25,
browser 2/2, architecture/provider 116/116, and API coverage 56/56. The mock
deployment observed 59 provider resource GETs and zero resource mutations.

## Closed Blocking Findings

| Finding | Disposition | Current authority | Executable evidence |
| --- | --- | --- | --- |
| Late source-reference INSERT after execution finalization | CLOSED | Migration 0014 locks the execution and requires exact `running`; the service flushes provenance before terminalizing | PostgreSQL terminal-insert regression and full import/migration suites pass |
| Cross-execution UPDATE reparenting into terminal provenance | CLOSED | Migration 0014 rejects every `execution_id` change before ownership evaluation and retains the OLD execution row lock | Committed fail-first PostgreSQL reparent regression passes after the guard fix |
| Mixed descendant/diverged separate mapping omitted one file delta | CLOSED | Review-required classification requests and validates diffstat for every non-equal side | Mixed-side complete and incomplete-delta regressions pass |

## Current Warning Inventory

| Finding | Status | Scope |
| --- | --- | --- |
| WR-01 | **OPEN — WARNING** | OAuth `expires_in` accepts positive values without an explicit maximum before datetime arithmetic |
| WR-02 | **OPEN — WARNING** | A delayed start-import response can act on a newly selected product without live mutation identity validation |
| WR-03 | **OPEN — WARNING** | Rewrite confirmation compares values from the same render closure rather than a live identity/generation |
| WR-04 | **OPEN — WARNING** | The source manifest excludes an executable Phase 2 JSON edge registry consumed by a selected test |
| WR-05 | **OPEN — WARNING** | The frontend development/mutation dependency graph contains two moderate advisories |
| WR-06 | **OPEN — WARNING** | The retained Phase 2 Compose verifier targets the removed OAuth callback contract |
| WR-07 | **OPEN — WARNING** | `.env.example` omits required Bitbucket and Phase 3 timing/watchdog settings |
| WR-08 | **OPEN — WARNING** | Container inputs use mutable tags rather than immutable content digests |

## ASVS 5.0 Level 1 Disposition

| Security authority | Result | Reviewed boundary |
| --- | --- | --- |
| Authentication and authorization | PASS | Internal bearer authentication, current database role authority, and Admin-only import operations |
| OAuth and secret handling | PASS with WR-01 | Exact `pullrequest:write` capability, access-only encrypted storage, legacy reauthorization, and no credential projection |
| Provider request authority | PASS | Application resource adapter remains GET-only through Phase 8; OAuth token POST is separately bounded |
| Input and URL validation | PASS | Closed request schemas, workspace/slug/ref/path validation, redirect rejection, and bounded traversal |
| Durable provenance and concurrency | PASS | Running-only INSERT, immutable execution identity, row locking, exact commit/file references, CAS finalization, and watchdog recovery |
| Rewrite reconciliation | PASS | Mapping-scoped complete proposal, both separate sides confirmed atomically, stale identity rejection, and zero-delta support |
| Error handling and logging | PASS | D-15 allowlisted diagnostics and bounded public errors exclude tokens, bodies, source content, unsafe paths, and tracebacks |
| API and pagination | PASS | Five generated Admin import operations, opaque revision/filter-bound cursors, complete page accumulation, and no handwritten wire duplicates |
| UI authority | PASS with WR-02/03 | All 26 UI considerations are represented by state, focus, responsive, polling, reconciliation, and stale-response tests |
| Deployment and cleanup | PASS | Migration cycle, isolated backend/worker/scheduler/frontend/provider smoke, redaction checks, and disposable-resource cleanup |
| Supply chain and reproducibility | WARNING | WR-04 through WR-08 remain visible and nonblocking at the configured threshold |

## Fresh Verification Performed

- Final source digest independently reproduced as `e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c`.
- Review scope reconciled exactly: 331 manifest paths plus 21 diff-only paths, 352 unique paths.
- Full Phase 3 implementation diff reviewed from exact base `4c557f5147038c4b09dc6dcf26d7b26675884bb5`.
- OAuth scope closure, provider methods, log dataflow, PostgreSQL trigger/lock ordering, API/client types, cursor authority, UI identities, smoke redaction, cleanup, and dependency state were traced directly.
- Final 14-layer gauntlet and API pre-seal passed without digest drift or provider resource writes.

## Review Limits

- The optional live-provider mode remains supplemental and was not used as
  closure authority; no live-provider result is fabricated.
- WR-01 through WR-08 remain open at Warning severity and are not represented
  as fixed.
- `Reviewed-source-digest` deliberately excludes this canonical review and the
  structured review artifact to avoid self-reference.
