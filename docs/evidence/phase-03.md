# Phase 3 Bitbucket Import Integration — Evidence

## Outcome

- Gauntlet-status: PASS
- Source-digest: `64bdc9a3e5c4085036c78732b4285609dd3a00c6c307b7c33f40149b5fb0684b`

The final canonical Phase 3 gauntlet completed on 2026-09-04. Its 14 ordered,
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

## Final pre-review reconfirmation

The complete gauntlet was rerun from committed source on 2026-09-03 before the
independent review. All 14 ordered layers passed in 384 seconds, the API pre-seal
reconfirmed exactly 56 capabilities (17 integrated and 39 explicitly opted out),
and the manifest remained unchanged at the canonical source digest recorded
above. The supplemental live-mode implementation is included by the manifest's
`tools/**` verifier-script rule; no live credentials or invocation were required
for this mandatory closeout run.

| Measurement | Result |
| --- | --- |
| Source commit | `616e3fcec361ae7dc3634193f21aafbf7510179d` |
| Ordered layers | 14/14 passed in 384 seconds |
| Backend JUnit SHA-256 | `f6564550eb9705470aaa17e61e46a82eefcc744d443dbd1fd013d83518f00ae3` |
| Frontend coverage SHA-256 | `e51ce70ee556179e8a21b55ea96196b8916aa4bfb1aae359428aa1394fd3ec0f` |
| API capability matrix | 56 total; 17 integrated and 39 explicitly opted out |
| Provider resource mutations | 0 |
| Final source-state | Passed; manifest digest unchanged |

## First post-review-remediation gauntlet

The first independent closeout review found two source-integrity blockers. The
remediation was driven by committed failing tests, added a follow-on migration
that serializes provenance insertion with execution finalization, and required
complete file deltas for every changed side of a mapping. The complete gauntlet
then passed again from committed source on 2026-09-03. Its intermediate digest
was superseded after the next fresh review found the remaining
execution-identity reparenting path described below.

| Measurement | Result |
| --- | --- |
| Source commit | `9088147c52559c813dd4ffe8169df03d41f591a3` |
| Ordered layers | 14/14 passed in 368 seconds |
| Backend suite | 952/952 passed; 95% combined branch-aware coverage |
| Frontend suite | 356/356 passed across 24 files; 83.5% statement coverage |
| Backend targeted mutation | 6/6 mutants killed |
| Frontend targeted mutation | 25/25 mutants killed |
| Responsive and accessibility browser checks | 2/2 passed |
| Migration and OpenAPI contracts | 14/14 migration checks passed; generated client unchanged |
| Architecture and provider audit | 116/116 passed |
| API capability matrix | 56 total; 17 integrated and 39 explicitly opted out |
| Mock deployment provider audit | 1 OAuth POST, 59 resource GETs, 0 resource mutations |
| Backend JUnit SHA-256 | `87e4968b425d34c303db6881e7332913a6f8b7636cbad47f70837d8c2f370e27` |
| Frontend coverage SHA-256 | `e1cda1bf439ddc9730e23ed939916e959d70c8bef53a4be08b8b803680c469e1` |
| Cleanup | Passed; no disposable Phase 3 container, network, volume, image, or worker remained |
| Final source-state | Passed; digest unchanged at `3072eb3d43244067c8e2aebd37b636c1d4418978507ac305656b751fd0fc1098` |

## Final provenance-remediation gauntlet

The next fresh independent review found that an `UPDATE` could reparent a
source reference from a running execution to a compatible terminal execution.
A committed PostgreSQL regression reproduced the bypass, and the follow-on
migration now makes the source-reference execution identity immutable while
retaining the row lock that serializes allowed running-state updates with
finalization. The complete gauntlet passed again from committed source on
2026-09-03 and established the canonical digest recorded in Outcome.

| Measurement | Result |
| --- | --- |
| Source commit | `ccb276b8b12d3ca459a5d171eb8637aef6b45122` |
| Ordered layers | 14/14 passed in 367 seconds |
| Backend suite | 952/952 passed; 95% combined branch-aware coverage |
| Frontend suite | 356/356 passed across 24 files; 83.5% statement coverage |
| Backend targeted mutation | 6/6 mutants killed |
| Frontend targeted mutation | 25/25 mutants killed |
| Responsive and accessibility browser checks | 2/2 passed |
| Migration and OpenAPI contracts | 14/14 migration checks passed; generated client unchanged |
| Architecture and provider audit | 116/116 passed |
| API capability matrix | 56 total; 17 integrated and 39 explicitly opted out |
| Mock deployment provider audit | 1 OAuth POST, 59 resource GETs, 0 resource mutations |
| Backend JUnit SHA-256 | `c332e60d1b712e1fccb779381cc83106681ef892aa321854dec430b28cf33cd8` |
| Frontend coverage SHA-256 | `dbdf58045bf511f56631cdc197f89b55e48fc11cef83dddd0c292064f12d9d00` |
| Cleanup | Passed; no disposable Phase 3 container, network, volume, image, or worker remained |
| Final source-state | Passed; digest unchanged at `e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c` |

## Final Nyquist-remediation gauntlet

The retrospective Nyquist audit added strict boundary regressions for OAuth
expiry, digest completeness, asynchronous UI authority, committed confirmation
state, and responsive focus. Independent follow-up review then required durable
browser selection, semantic mutation ownership, and exact cleanup authority for
both response handling and asynchronous `finally` blocks. Each issue was first
reproduced by a failing test and then closed without weakening the original
Phase 3 behavior.

The final complete gauntlet passed from committed source on 2026-09-04 and
established the digest recorded in Outcome.

| Measurement | Result |
| --- | --- |
| Source commit containing final production fix | `6e8e858` |
| Ordered layers | 14/14 passed in 781 seconds |
| Backend suite | 958/958 passed; 95% aggregate coverage |
| Frontend suite | 368/368 passed |
| Backend targeted mutation | 6/6 mutants killed |
| Frontend exact-owned mutation | 52/52 mutants killed at only the declared locations |
| Responsive and accessibility browser checks | 3/3 passed, including browser-only `PW3-C27` |
| Architecture and provider audit | 119/119 passed |
| API capability matrix | 56 total; 17 integrated and 39 explicitly opted out |
| Provider resource mutations | 0 |
| Independent review | 0 Critical/High; four historical nonblocking warnings; Nyquist closeout ready |
| Independent verifier | 60/60 must-haves; 10/10 Nyquist/review regressions closed; 0 gaps; 0 human items |
| Final source-state | Passed; digest unchanged at `64bdc9a3e5c4085036c78732b4285609dd3a00c6c307b7c33f40149b5fb0684b` |

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

## Final independent review authority

The final fresh typed `gsd-code-reviewer` independently reproduced source digest
`64bdc9a3e5c4085036c78732b4285609dd3a00c6c307b7c33f40149b5fb0684b`.
The historical deep scope remains 352 unique paths, and every subsequent
Nyquist remediation delta received an independent standard review. The final
review applied OWASP ASVS 5.0 Level 1 at the configured High blocking threshold
and closed with zero unresolved Critical/High-equivalent findings. Four
historical nonblocking Warning findings remain explicit; WR-01 through WR-04
and WR-09 through WR-14 are resolved with executable evidence.

| Measurement | Result |
| --- | --- |
| Reviewer | Fresh typed `gsd-code-reviewer` (`phase3_nyquist_fix_review`) |
| Structured status | `issues_found` because Warning findings remain; `closeout_blocked: false` |
| OWASP standard | ASVS 5.0 Level 1 |
| Reviewed paths | Historical 352-path deep review plus independently reviewed Nyquist deltas |
| Critical/High-equivalent findings | 0 open |
| Warning findings | 4 open and visible: WR-05 through WR-08 |
| Canonical review | `Review-status: CLOSED`; `Open-critical-high: 0` |
| Nyquist closeout | `nyquist_closeout_ready: true`; WR-01..04 and WR-09..14 resolved |
| Reviewed source digest | `64bdc9a3e5c4085036c78732b4285609dd3a00c6c307b7c33f40149b5fb0684b` |
| Provider resource mutations | 0 |
| Review source-state | Passed; digest unchanged |

## Final independent verifier authority

The fresh typed `gsd-verifier` independently verified the Phase 3 roadmap goal,
BITB-02/05/06, D-01 through D-18, the six cross-artifact edges, the two
prohibitions, UI3-C01 through UI3-C26, and browser-only `PW3-C27` against
implementation, tests, and digest-bound runtime evidence. It recorded exactly
`status: passed` with 60/60 original must-haves verified, all ten
Nyquist/review regressions closed, zero gaps, and zero human-verification items.

The verifier independently reproduced the reviewed source digest and confirmed
the exact API capability split, the five generated import operations, D-15
positive and negative logging evidence, provenance/retry/watchdog/rewrite
authority, the mandatory mock smoke, all quality gates, and the Phase 4-8
provider-write fences. No source-manifest file changed after the accepted final
gauntlet, and provider resource writes remained zero.

| Measurement | Result |
| --- | --- |
| Verifier | Fresh typed `gsd-verifier` (`phase3_post_nyquist_final_verifier`) |
| Verifier status | `passed` |
| Goal-backward score | 60/60 must-haves verified |
| Requirements | BITB-02, BITB-05, and BITB-06 verified |
| Decisions and UI | D-01..D-18, UI3-C01..UI3-C26, and `PW3-C27` verified |
| Nyquist regression closure | 10/10: WR-01..04 and WR-09..14 |
| API capability matrix | 56 total; 17 integrated and 39 explicitly opted out |
| Gaps / human verification | 0 / 0 |
| Verified source digest | `64bdc9a3e5c4085036c78732b4285609dd3a00c6c307b7c33f40149b5fb0684b` |
| Provider resource mutations | 0 |
| Final source-state | Passed; review, verifier, evidence, and manifest digest are identical |
