# Phase 3 Bitbucket Import Integration — Evidence

## Outcome

- Gauntlet-status: PASS
- Source-digest: `ddb3e79ad5e00891f8d3bcaa6bd4d8b39ad738bb0e97f0ad16b0d05f25cb9310`

The canonical Phase 3 gauntlet completed on 2026-09-03. Its 14 ordered,
fail-closed layers passed against one unchanged manifest digest. This record contains
only bounded counts, durations, digests, commit identities, and pass/fail outcomes.

## Canonical pre-closeout gauntlet

| Measurement | Result |
| --- | --- |
| Ordered layers | 14/14 passed in 367 seconds |
| Backend suite | 950/950 passed; 95% combined branch-aware coverage |
| Frontend suite | 356/356 passed across 24 files; 83.5% statement coverage |
| Backend targeted mutation | 6/6 capability, state, provenance, ancestry, rewrite, and error mutants killed |
| Frontend targeted mutation | 25/25 polling, action, cursor, and reconciliation-dialog mutants killed |
| Responsive and accessibility browser checks | 2/2 passed |
| Migration and OpenAPI contracts | 14/14 migration checks passed; generated client unchanged |
| Architecture and provider audit | 116/116 passed |
| Supply-chain, license, secret, and schema gates | Passed |
| API capability matrix | 56 total; 17 integrated and 39 explicitly opted out |
| Mock deployment provider audit | 1 OAuth POST, 59 resource GETs, 0 resource mutations |
| Backend JUnit SHA-256 | `58aa8354cb7d085e0070698fbe319105384ea37afe14e4b4ce1f95f7b3e68962` |
| Frontend coverage SHA-256 | `cd5f677b9438f0ecc1dc1f659e73eff0f667cdb5222ac4334e06921f3fc6da58` |
| Cleanup | Passed; no disposable Phase 3 container, network, volume, image, or worker remained |

## Prior deployment evidence

This record contains only bounded, non-secret verification results. It does not
contain OAuth credentials, access tokens, provider response bodies, repository or
branch names, source paths, source content, or raw application logs.

## Mandatory deployment-like mock smoke

The isolated Phase 3 smoke completed on 2026-09-03 with seven distinct services:
PostgreSQL, Redis, API, worker, scheduler, frontend, and the deterministic provider.
It proved the direct and separate mapping import journey, equal and fast-forward
refreshes, bounded provider failures, same-UUID retry, watchdog recovery, and direct,
separate, and zero-delta rewrite confirmation.

| Measurement | Result |
| --- | --- |
| Migration cycle | `head -> 0011_active_revision_revalidations -> head`; 2/2 checks passed |
| Browser journey | 1/1 deployment-like import/recovery/reconciliation journey passed |
| OAuth token traffic | 1 POST to the isolated token endpoint |
| Provider resource traffic | 59 GET requests |
| Provider resource mutations | 0 POST/PUT/PATCH/DELETE requests |
| Redis and evidence scans | Passed; no credential or source-byte material found |
| Cleanup | Passed; no disposable container, volume, network, image, or runtime file remained |

The failing deployment tracer was committed as `3014031`; the corrected, fully
passing implementation was committed as `cdb0548`.

## Supplemental live-provider mode

`tools/phase3_smoke.sh --live-provider-read-only` is implemented as an explicitly
supplemental path. It creates a disposable local deployment, routes Bitbucket TLS
traffic through an owner-only method-audit boundary, and drives connection,
reconnection, preview, publication, one commit-bound direct import, and local revoke
through authenticated VerboFlex APIs. The audit boundary forwards only the OAuth
token POST and rejects every non-GET provider resource request before forwarding.

The credential-independent self-test passed. It verifies argument routing, generated
driver/proxy syntax, owner-only temporary files, trap cleanup, closed method
classification, rejection of a synthetic provider mutation, bounded result fields,
and redaction. The explicit four-variable-unset invocation returned:

`phase3 live provider: SKIP (supplemental variables are not configured)`

That skip exited successfully and does not replace or weaken the mandatory mock
smoke. No live provider result is claimed. When deliberately configured, only closed
readiness, OAuth/resource method counts, duration, result count, SHA-256 identities,
zero resource mutations, and successful local revoke may be emitted; the owner-only
runtime and credentials are removed on every exit.
