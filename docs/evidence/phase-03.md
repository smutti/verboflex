# Phase 3 Bitbucket Import Integration — Evidence

## Outcome

- Gauntlet-status: PENDING
- Source-digest: `pending`

The canonical Phase 3 gauntlet has been assembled and remains pending until its
immutable source set is committed and all fail-closed layers complete. Only bounded
counts, durations, digests, commit identities, and pass/fail outcomes will be added
to this record.

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
