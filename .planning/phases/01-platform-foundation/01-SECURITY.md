---
phase: 01-platform-foundation
slug: platform-foundation
status: verified
# Count of OPEN threats at or above workflow.security_block_on (high).
threats_open: 0
asvs_level: 1
created: 2026-08-26
---

# Phase 01 — Security

> Retroactive security verification of the plan-time STRIDE registers against
> the source-bound Phase 1 review, official gauntlet, and independent verifier.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Package registries and shadcn registry → lockfiles/source | Third-party identities, packages, generated component source, and transitive dependency graphs enter the trusted build. | Executable build inputs and supply-chain metadata |
| Environment/deployment → API and worker processes | Typed settings, signing material, cookie policy, database/Redis endpoints, and process commands define runtime authority. | Secrets and security-critical configuration |
| CLI/browser/API callers → authentication services | Corporate email, passwords, bearer tokens, refresh cookies, Origin, and request identity request or mutate authority. | Credentials, session authority, and personal identity |
| FastAPI/Celery → PostgreSQL/Redis | Durable identity and session state, rate-limit state, queued work, and operational probes cross process boundaries. | Security state and serialized task data |
| FastAPI OpenAPI → generated TypeScript → React | Backend contracts and authenticated responses drive browser session state and route presentation. | API schemas, identity, roles, and status data |
| Source tree → verification tools → evidence | Custom checkers, reviews, digests, and reports establish the Phase 1 assurance claim. | Source, test results, logs, and security evidence |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation / Evidence | Status |
|-----------|----------|-----------|----------|-------------|-----------------------|--------|
| P01/T-01-SC | Tampering | PyPI/npm dependency selection | high | mitigate | Exact direct-dependency allowlists, audited identities, compatibility checks, and committed lockfiles; supply-chain layer passed. | closed |
| P01/T-01-SQ | Spoofing | Package publisher/source identity | high | mitigate | Human dependency audit recorded canonical sources and publishers before installation. | closed |
| P01/T-01-ST | Tampering | Unexpected shadcn/transitive additions | medium | mitigate | Approved project-owned shadcn source boundary and exact lockfile-diff checks passed. | closed |
| P02/T-02-01 | Information Disclosure | Health response | medium | mitigate | Constant health projection and no-detail regression checks passed. | closed |
| P02/T-02-02 | Tampering | Backend dependency graph | high | mitigate | Approved exact lock and Python compatibility gates passed. | closed |
| P02/T-02-03 | Elevation of Privilege | Premature endpoint behavior | high | mitigate | All Phase 1 endpoint seams were replaced by implemented, authenticated, tested behavior. | closed |
| P03/T-03-01 | Tampering | Generated API drift | high | mitigate | Canonical OpenAPI export, deterministic generation, negative control, and fail-on-diff gate passed. | closed |
| P03/T-03-02 | Information Disclosure | Error UI | medium | mitigate | Stable sanitized client errors and generic UI copy are regression tested. | closed |
| P03/T-03-SC | Tampering | Frontend npm graph | high | mitigate | Approved direct dependency set, exact pins, lockfile, and runtime audit passed. | closed |
| P04/T-04-01 | Spoofing | Signing/cookie configuration | high | mitigate | Typed startup settings reject weak signing material and require Secure refresh cookies in every environment. | closed |
| P04/T-04-02 | Information Disclosure | Environment/build context | high | mitigate | Real environment files are ignored and examples contain invalid non-secret placeholders. | closed |
| P04/T-04-03 | Denial of Service | Process lifecycle | medium | mitigate | API, worker, database, Redis, and frontend have separate bounded commands and health checks. | closed |
| P05/T-03-01 | Elevation of Privilege | First-admin bootstrap | high | mitigate | PostgreSQL advisory locking, only-if-empty transaction, unique constraints, and concurrency tests leave exactly one admin. | closed |
| P05/T-03-02 | Information Disclosure | Bootstrap/reset password input | high | mitigate | Secrets enter only through `getpass` or stdin; argv/default/log/plaintext guards and secret scans passed. | closed |
| P05/T-03-03 | Tampering | Alembic authentication migration | high | mitigate | Real PostgreSQL upgrade → downgrade → upgrade rehearsal and schema assertions passed. | closed |
| P05/T-03-04 | Spoofing | Normalized corporate email | medium | mitigate | One ASCII-trim/lowercase/validate seam, database uniqueness, property tests, and duplicate tests passed. | closed |
| P05/T-03-05 | Repudiation | CLI reset outcome | medium | accept | Non-secret outcome plus durable token-version/session mutation is sufficient for Phase 1; full mutation audit records remain assigned to Phase 9. | closed |
| P06/T-04-01 | Spoofing | JWT verification | high | mitigate | Explicit HS256/claim/purpose/expiry verification plus active user, token-version, and session reconciliation passed adversarial tests. | closed |
| P06/T-04-02 | Information Disclosure | Login errors | high | mitigate | Identical 401 response and dummy-hash path prevent user enumeration. | closed |
| P06/T-04-03 | Denial of Service | Password verification | high | mitigate | Redis-authoritative limits execute before Argon2 and fail closed on Redis outage. | closed |
| P06/T-04-04 | Elevation of Privilege | Roles and token purpose | high | mitigate | Roles come from PostgreSQL and purpose-aware dependencies reject password-change authority from ordinary resources. | closed |
| P06/T-04-05 | Tampering | Refresh-session creation | high | mitigate | Only SHA-256 refresh-token digests persist; database session and host-only cookie issuance are transactionally bounded. | closed |
| P07/T-05-01 | Spoofing | Refresh replay | high | mitigate | Locked single-use rotation, one successor, replay detection, and family revocation passed concurrency and mutation tests. | closed |
| P07/T-05-02 | Spoofing | Cookie-authenticated CSRF | high | mitigate | `__Host-` Secure/HttpOnly/SameSite cookie plus exact Origin enforcement before state mutation. | closed |
| P07/T-05-03 | Elevation of Privilege | Password-change token purpose | high | mitigate | Password-change authority is accepted only by the dedicated endpoint. | closed |
| P07/T-05-04 | Tampering | Password/session transaction | high | mitigate | Password replacement, token-version advance, global session revocation, and cookie clearing occur atomically. | closed |
| P07/T-05-05 | Denial of Service | Rotation/password hashing | medium | mitigate | Per-session/user Redis limits precede expensive work and sensitive endpoints fail closed. | closed |
| P08/T-06-01 | Denial of Service | Rate limits | high | mitigate | Exact per-actor policies, server-observed identity, boundary/over-limit tests, and manual mutant proof passed. | closed |
| P08/T-06-02 | Information Disclosure | System status | medium | mitigate | Only approved enums are returned; raw addresses, exceptions, task identifiers, and probe details are suppressed. | closed |
| P08/T-06-03 | Denial of Service | Service probes | medium | mitigate | Database, Redis, and worker probes have independent strict timeouts; health remains independent. | closed |
| P08/T-06-04 | Tampering | Celery task input/execution | medium | mitigate | Named JSON-only non-eager task crosses Redis and executes in a separate worker process. | closed |
| P08/T-06-05 | Repudiation | Smoke task | low | accept | Deterministic non-mutating sample task is sufficient for Phase 1; durable audit belongs to later real workflows. | closed |
| P09/T-07-01 | Tampering | Stale generated client | high | mitigate | Checked-in schema/client, deterministic generation, and controlled drift negative control passed. | closed |
| P09/T-07-02 | Information Disclosure | Browser credential storage | high | mitigate | Access authority is memory-only; storage AST guards, negative controls, and real-browser inspection passed. | closed |
| P09/T-07-03 | Elevation of Privilege | Session-state transitions | high | mitigate | Discriminated versioned state transitions, `/users/me` confirmation, and property-based sequence tests passed. | closed |
| P09/T-07-04 | Spoofing | Client-authoritative roles | high | mitigate | Browser identity and roles come only from authenticated generated `/users/me`; no browser token-claim parsing. | closed |
| P10/T-10-SC | Tampering | shadcn registry | high | mitigate | Official modern CLI/source, explicit 13-component allowlist, exact pins, and inspected lock diff. | closed |
| P10/T-10-01 | Elevation of Privilege | Component code | medium | mitigate | Project-owned source passed type, lint, accessibility, and production-build checks before use. | closed |
| P11/T-11-01 | Tampering | Visual/accessibility tokens | medium | mitigate | Static visual/accessibility contract and negative control passed. | closed |
| P11/T-11-02 | Information Disclosure | Remote font | low | mitigate | System-only font assertion prevents remote font requests. | closed |
| P12/T-12-01 | Elevation of Privilege | Route guards | high | mitigate | Route presentation is a pure projection of server-backed session state; API authorization remains authoritative. | closed |
| P12/T-12-02 | Information Disclosure | Authentication errors/input | high | mitigate | Generic error copy and no browser storage/logging are enforced by tests and static guards. | closed |
| P12/T-12-03 | Denial of Service | Duplicate submit | medium | mitigate | Authentication actions permit one in-flight request and expose disabled loading state. | closed |
| P13/T-13-01 | Spoofing | Identity/status UI | medium | mitigate | Identity and service state render only from authenticated generated server responses. | closed |
| P13/T-13-02 | Information Disclosure | Browser storage | high | mitigate | Memory-only session and real E2E storage inspection passed. | closed |
| P13/T-13-03 | Elevation of Privilege | Role presentation | high | mitigate | UI roles are non-authoritative and backend dependencies enforce permissions. | closed |
| P14/T-14-01 | Tampering | Custom gauntlet checks | high | mitigate | Fail-closed checkers, target validation, positive/negative controls, and exact source fingerprints passed. | closed |
| P14/T-14-02 | Repudiation | Code/security review | high | mitigate | Scope, digests, findings, fixes, controls, and post-fix verification are persisted in the closed review artifact. | closed |
| P14/T-14-03 | Information Disclosure | Smoke secrets/logs | high | mitigate | Per-run non-echoed secrets, private temporary files, scoped cleanup, redaction, and detect-secrets controls passed. | closed |
| P14/T-14-04 | Elevation of Privilege | Unresolved ASVS finding | critical | mitigate | Critical/high findings block closure; final review reports zero Critical, High, or Medium open findings. | closed |
| P14/T-14-SC | Tampering | Dependency graph | high | mitigate | Backend and runtime frontend audits, inventories, approved locks, and direct-dependency allowlists passed. | closed |
| P15/T-15-01 | Tampering | Final source/evidence | high | mitigate | Immutable manifest/digest checks ran before, during, and after the official gauntlet and before report publication. | closed |
| P15/T-15-02 | Repudiation | Evidence claims | high | mitigate | Evidence records exact commands, versions, seeds, thresholds, logs, exclusions, review identity, and verifier hashes. | closed |
| P15/T-15-03 | Spoofing | Independent sign-off | high | mitigate | Three fresh-context rounds preserved blind records; the explicitly authorized final Round 3 verdict is `passed`. | closed |
| P15/T-15-04 | Information Disclosure | Raw logs | high | mitigate | Logs stayed outside the canonical source set; secret scan/redaction passed and published evidence contains no credentials. | closed |
| VF-SEC-007 | Tampering | Development-only `typed-rest-client → qs` dependency chain | low | mitigate | No production dependency path; runtime audits are clean. Upgrade or time-bound acceptance remains required before release. | open — below high threshold (non-blocking) |

## Summary Threat Flags

| Flag | Implementation Evidence | Verification |
|------|-------------------------|--------------|
| Authentication authority | `backend/src/verboflex/api/v1/routes/auth.py` deactivation and logout transitions | Exhaustive state, peer-isolation, adversarial, and mutation tests passed. |
| Rate-limit identity | `backend/src/verboflex/auth/refresh_sessions.py` distinguishes live user authority from stale/anonymous credentials | Boundary, over-limit, stale credential, and exact manual-mutant proofs passed. |
| Cookie configuration | `backend/src/verboflex/core/config.py` requires Secure refresh cookies in every environment | Configuration negative controls and real staging/adversarial smoke passed. |

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | P05/T-03-05 | Phase 1 provides a non-secret CLI diagnostic and durable authority mutation; full mutation audit records are explicitly assigned to Phase 9. | Approved Phase 1 plan | 2026-08-26 |
| AR-02 | P08/T-06-05 | The sample task is deterministic and non-mutating; durable job audit belongs to later real import/PR workflows. | Approved Phase 1 plan | 2026-08-26 |

`VF-SEC-007` is deliberately not recorded as accepted risk. It remains visible
as an open Low development-only dependency item for upgrade or explicit,
time-bounded acceptance before release.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-26 | 56 | 55 | 1 below blocking threshold | Codex / GSD secure-phase, reconciled with closed source-bound review and Tier 3 verification |

### Evidence

- `docs/reviews/phase-01-code-security.md`: `CLOSED/PASS`, zero open Critical, High, or Medium findings.
- `docs/evidence/phase-01.md`: official immutable 13/13 gauntlet PASS on canonical digest `ed816871a1e6ff21fecb9a7204d3f83db33ebd1772165013ba5abda170a470f9`.
- `01-VERIFICATION.md`: Phase 1 `passed`, 6/6 observable truths, 9/9 requirements, no outstanding human verification.
- Backend: 268 tests; 891/891 non-equivalent mutants killed plus two exact SQL-proved equivalents; property-only 199/199 killed.
- Frontend: 75 tests; 153/153 mutants and property-only 37/37 killed; Playwright and adversarial staging smoke passed.
- Changed-line branch coverage: 100% for backend and frontend handwritten production changes.

## Sign-Off

- [x] All threats have a disposition (`mitigate` or `accept`).
- [x] Accepted risks from approved plans are documented.
- [x] Blocking `threats_open: 0` confirmed for threshold `high`.
- [x] `status: verified` set in frontmatter.
- [x] Low development-only dependency debt remains explicitly visible and is not silently waived.

**Approval:** verified 2026-08-26 for Phase 1 ship gate; release disposition of `VF-SEC-007` remains outstanding.
