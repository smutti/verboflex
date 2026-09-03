---
phase: 03
slug: bitbucket-import-integration
status: verified
threats_open: 0
asvs_level: 1
blocking_threshold: high
register_authored_at_plan_time: true
source_digest: e5d23977e946a9ec98ad57d1fd9893c2cec7a1d364f73c54862ef68ba668c51c
created: 2026-09-03
verified: 2026-09-03
---

# Phase 03 — Security

> ASVS L1 verification of the Phase 3 plan-time STRIDE register. Every registered threat was checked against the final implementation and tests; no risk was accepted or transferred.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Browser → FastAPI | Untrusted identifiers, cursors, proposal identities, and administrator actions request import authority. | Bearer authority and browser-safe import metadata |
| FastAPI/services → PostgreSQL | Concurrent requests and workers contend for logical import, execution, proposal, and baseline authority. | Durable state, immutable provenance, and lock-fenced transitions |
| PostgreSQL → Redis → Celery | Replayable background dispatch carries only one logical import UUID. | Non-sensitive job identity |
| Worker → Bitbucket Cloud | OAuth credentials authorize bounded provider reads and provider-controlled responses enter parsing. | Encrypted credentials, commit metadata, paths, and source bytes |
| Provider → diagnostics | Untrusted failures become operator-visible events only after durable terminalization. | Allowlisted category, operation, status, timing, and UUIDs |
| OpenAPI → generated client → DOM | Canonical server contracts become executable browser requests and rendered state. | Closed generated schemas and text-only metadata |
| Source tree → gauntlet/review/verifier | Final code and tests become digest-bound closeout evidence. | File manifest, hashes, counts, and sanitized reports |
| Test secrets → smoke boundary | Optional live credentials may enter ephemeral test processes. | Owner-only temporary values and redacted evidence |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation evidence | Status |
|-----------|----------|-----------|----------|-------------|---------------------|--------|
| T-03-01 | Elevation of privilege | Import routes | high | mitigate | Admin dependency and active graph ownership in `admin_mappings.py` and `import_jobs.py`; authorization tests. | closed |
| T-03-02 | Tampering | Concurrent starts/completion | high | mitigate | Stable locking and logical/execution conditional writes in `import_jobs.py`; concurrency tests. | closed |
| T-03-03 | Information disclosure | Provider/source projection | high | mitigate | Closed metadata-only models in `schemas/imports.py`; recursive contract assertions. | closed |
| T-03-04 | Tampering | Provider method surface | high | mitigate | GET-only resource adapter in `client.py`; provider-boundary verb audits. | closed |
| T-03-05 | Tampering | Import provenance | high | mitigate | Composite constraints and immutable provenance triggers in migrations `0012` and `0014`; migration tests. | closed |
| T-03-06 | Elevation of privilege | Import lookup/start | high | mitigate | Admin and active product/revision/mapping authorization before side effects; API and service tests. | closed |
| T-03-07 | Information disclosure | Schemas/OpenAPI | high | mitigate | Closed Pydantic schemas and recursive forbidden-key OpenAPI tests. | closed |
| T-03-08 | Elevation of privilege | OAuth authority | high | mitigate | Exact requested capability and documented implication closure in `bitbucket_oauth.py`; reject-extra tests. | closed |
| T-03-09 | Spoofing | Legacy/stale generation | high | mitigate | Legacy generations require reauthorization and cannot issue import leases; OAuth tests. | closed |
| T-03-10 | Information disclosure | Admin status | high | mitigate | Closed capability projection in `schemas/admin_bitbucket.py`; sensitive-field tests. | closed |
| T-03-11 | Spoofing | Client capability inference | high | mitigate | UI consumes closed generated readiness literals and never parses raw scopes. | closed |
| T-03-12 | Information disclosure | DOM/generated types | high | mitigate | Recursive forbidden-key and rendered-state tests in frontend contracts. | closed |
| T-03-13 | Elevation of privilege | Future write readiness | high | mitigate | Readiness is descriptive only; provider-write operations and controls are structurally absent. | closed |
| T-03-14 | SSRF/Tampering | URL/continuation | high | mitigate | Scheme, host, path, credential, fragment, and operation validation in `urls.py`; negative tests. | closed |
| T-03-15 | Elevation of privilege | Provider operation | high | mitigate | Closed operation vocabulary, read-only adapter, and AST/runtime verb checks. | closed |
| T-03-16 | Denial of service | Provider failures | medium | mitigate | Single transport attempt, explicit budgets, and no hidden retries in `client.py`. | closed |
| T-03-17 | Spoofing | Stale generation | high | mitigate | Credential generation checked before and after every provider response. | closed |
| T-03-18 | Information disclosure | Structured diagnostics | high | mitigate | Allowlisted typed event payload in `diagnostics.py`; canary leakage tests. | closed |
| T-03-19 | Repudiation | Failure correlation | medium | mitigate | Stable event identity and bounded operation/category/status/timing fields. | closed |
| T-03-20 | Denial of service | Logging handler | medium | mitigate | Diagnostic logging failure is contained and cannot undo durable terminalization. | closed |
| T-03-21 | Tampering | Concurrent state | high | mitigate | Stable lock order and execution/revision/mapping/generation CAS in `import_jobs.py`. | closed |
| T-03-22 | Tampering | Separate baseline | high | mitigate | Both sides stage before one atomic active-pointer transition. | closed |
| T-03-23 | Denial of service | Worker loss | medium | mitigate | Bounded watchdog terminalizes abandoned execution without redispatch. | closed |
| T-03-24 | Information disclosure | Queue/public projection | high | mitigate | Celery carries UUID-only JSON; public status uses a closed current-only schema. | closed |
| T-03-25 | Tampering | Ancestry result | high | mitigate | Exact commits, bounded reachability, generation checks, and exhaustive ancestry tests. | closed |
| T-03-26 | Information disclosure | Diffstat | high | mitigate | Metadata-only rows exclude patches, bodies, headers, URLs, and credentials. | closed |
| T-03-27 | Denial of service | Pagination/budgets | medium | mitigate | Page, row, path, and byte ceilings plus repeated-cursor rejection. | closed |
| T-03-28 | Tampering | Proposal identity | high | mitigate | Full digest and identity constraints with lock-time revalidation in `import_jobs.py` and migration `0013`. | closed |
| T-03-29 | Tampering | Separate confirmation | high | mitigate | One mapping transaction advances Keys and Translations together. | closed |
| T-03-30 | Information disclosure | Comparison API | high | mitigate | Closed metadata-only rewrite proposal schema. | closed |
| T-03-31 | Repudiation | Baseline replacement | medium | mitigate | Immutable executions, reconstructible proposal digest, and confirmation timestamp. | closed |
| T-03-32 | Elevation of privilege | Import endpoints | high | mitigate | Full 401/403 coverage and active ownership checks on all five operations. | closed |
| T-03-33 | Tampering | Cursor/proposal | high | mitigate | Identity-bound cursors and currentness revalidation before mutation. | closed |
| T-03-34 | Information disclosure | Public schema | high | mitigate | Strict response models and recursive forbidden-field tests. | closed |
| T-03-35 | Denial of service | Collection/aggregate | medium | mitigate | Bounded pagination and indexed set-based affected-mapping aggregate. | closed |
| T-03-36 | Tampering | Generated contract | high | mitigate | Frozen operation/schema tests and pinned zero-diff regeneration gate. | closed |
| T-03-37 | Information disclosure | Generated types | high | mitigate | Generated-client forbidden-field and runtime same-origin request audits. | closed |
| T-03-38 | Elevation of privilege | Generated operations | high | mitigate | Exact five-operation allowlist; no provider mutation operation generated. | closed |
| T-03-39 | Tampering | Stale pages/polls | high | mitigate | Request-generation guard, bounded cursor set, and deterministic deduplication. | closed |
| T-03-40 | Elevation of privilege | Row action | high | mitigate | UI renders only the generated server action; backend reauthorizes every request. | closed |
| T-03-41 | Information disclosure | DOM/live region | high | mitigate | Closed fields, fixed error text, text rendering, and no automatic full-hash announcement. | closed |
| T-03-42 | Denial of service | Pagination/polling | medium | mitigate | Bounded pages, repeated-cursor failure, and exact polling deadline. | closed |
| T-03-43 | Tampering | Stale/duplicate confirmation | high | mitigate | Full proposal identity guard, synchronous ref, server revalidation, and no optimistic pointer update. | closed |
| T-03-44 | Information disclosure | Dialog/DOM/clipboard | high | mitigate | Text-only bounded metadata, explicit copy, and storage/DOM/request audits. | closed |
| T-03-45 | Spoofing | Client ancestry/count | high | mitigate | Client renders generated `confirmable` and count fields only. | closed |
| T-03-46 | Denial of service | Long delta/reflow | medium | mitigate | Bounded dialog scroll region and responsive viewport/zoom tests. | closed |
| T-03-47 | Information disclosure | Smoke/log/evidence | high | mitigate | Redaction canaries, bounded evidence allowlist, owner-only temporary files, and trap cleanup. | closed |
| T-03-48 | Elevation of privilege | Method audit | high | mitigate | OAuth token POST is separated from GET-only provider resource traffic. | closed |
| T-03-49 | Denial of service | Compose resources | medium | mitigate | Bounded readiness/timeouts and cleanup on both success and failure. | closed |
| T-03-50 | Tampering | Scope coverage | high | mitigate | Exact-set/count architecture guards with removal, duplicate, extra, and comment-only negative controls. | closed |
| T-03-51 | Tampering | Source digest | high | mitigate | Canonical manifest and repeated digest checks in `phase3_gauntlet.sh`. | closed |
| T-03-52 | Information disclosure | Logs/evidence | high | mitigate | Secret canary scans and bounded evidence projection. | closed |
| T-03-53 | Elevation of privilege | Assembled provider surface | high | mitigate | Provider method/endpoint/coverage equality and runtime mock audit prove zero resource writes. | closed |
| T-03-54 | Tampering | Digest binding | high | mitigate | Digest `e5d23977…c51c` independently matches manifest, review, verifier, and evidence. | closed |
| T-03-55 | Repudiation | Closeout authority | high | mitigate | Fresh typed review and independent `status: passed` verification are retained. | closed |
| T-03-56 | Information disclosure | Review/evidence | high | mitigate | Reports contain bounded sanitized hashes/counts and pass leakage scans. | closed |
| T-03-57 | Elevation of privilege | Stale/false closure | high | mitigate | Closeout fails on a blocking finding, non-passed verification, or digest mismatch. | closed |
| T-03-SC | Tampering | Supply chain | high | mitigate | No Phase 3 dependency installation or lockfile change; pin, audit, license, and generated-drift gates pass. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit 2026-09-03

| Metric | Count |
|--------|------:|
| Unique registered threats | 58 |
| Closed | 58 |
| Open | 0 |
| Blocking High threats | 0 |

Fresh verification performed by `gsd-security-auditor`:

- 95 backend boundary, OAuth, diagnostics, and OpenAPI tests passed.
- 90 frontend generated-contract, connection, import, polling, and reconciliation tests passed.
- 10 targeted administrator capability, authorization, and aggregate tests passed.
- Canonical source/review digest reproduced exactly.
- The `persistence-authorization` summary flag maps to T-03-05, T-03-28, T-03-29, and T-03-31; no unregistered flag remains.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|--------------:|-------:|-----:|--------|
| 2026-09-03 | 58 | 58 | 0 | `gsd-security-auditor` |

---

## Sign-Off

- [x] All threats have a disposition.
- [x] No accepted risk is required.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.

**Approval:** verified 2026-09-03
