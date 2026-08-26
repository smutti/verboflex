# Phase 1 Platform Foundation — Evidence

This report was assembled outside the repository and outside the canonical
source set. It was not a verification input during the blind phase. Its draft
was disclosed only after the round-3 blind record was frozen and was then
compared append-only by the same fresh-context verifier.

## Outcome under test

Phase 1 provides the approved Docker-first foundation: separate FastAPI and
React/Vite applications; internal corporate-email/password authentication;
provider-independent internal roles; PostgreSQL/Alembic; Redis/Celery;
generated OpenAPI client; mandatory first-password replacement; rotating and
revocable refresh sessions; bounded service status; and the neutral responsive
authenticated shell. Microsoft Entra/OIDC remains deliberately deferred.

The approved refresh authority boundary is the hardened
`__Host-verboflex_refresh` cookie with `Secure`, `HttpOnly`, `SameSite=Lax`,
`Path=/`, and no `Domain`, including local development. The user explicitly
approved this description/SPEC revision after Tier 3 round 1.

## Immutable source identity

- Repository: `/Users/smutti/Documents/personal/verboflex`
- Branch: `codex/phase-1-platform-foundation`
- Verified commit: `3a0ea238cf1953fd9e086b2e2eda42a57509f10d`
- Source-digest: `ed816871a1e6ff21fecb9a7204d3f83db33ebd1772165013ba5abda170a470f9`
- Canonical source digest:
  `ed816871a1e6ff21fecb9a7204d3f83db33ebd1772165013ba5abda170a470f9`
- Review-mode digest:
  `3b398c710022e9b5dd85828e6c8f5f296fea9796e32e1185bd8d9c7a1de8084f`
- Source review: `docs/reviews/phase-01-code-security.md`, `CLOSED/PASS`,
  zero Critical, High, or Medium findings; one disclosed Low development-only
  dependency debt (VF-SEC-007).
- Relevant working tree before, during, and immediately after the official
  round: clean. The pre-existing untracked `.planning/milestone.lock` is not in
  the manifest and was neither modified nor staged.

`tools/source_manifest.txt` includes implementation, tests, configuration,
`backend/.python-version`, lockfiles, migrations, all verifier scripts, the
deployment runbook, and the closed review artifact. It excludes this evidence
report and generated runtime/build/test output. Manifest controls reject empty
rules, missing/untracked/dirty paths, missing categories, malformed directives,
unapproved exclusions, and omitted required source.

The digest recorded before the official gauntlet, by its first layer, in two
independent immediate post-run computations, and in the correctly source-bound
`--verify-final-before-report` call was byte-identical. HEAD was also
byte-identical before and after. No failed historical run contributes to this
claim.

## Official immutable gauntlet

- Entry point: `tools/gauntlet.sh`
- Deterministic test seed: `1401`
- Official raw log (private external record):
  `/tmp/verboflex-phase01-r3-official.3Ng2Xq/official.log`
- Layer record:
  `/tmp/verboflex-phase01-r3-official.3Ng2Xq/official.layers`
- Initial/entry digest record:
  `/tmp/verboflex-phase01-r3-official.3Ng2Xq/{initial.digest,official.digest}`
- Immediate post-run digest and HEAD records:
  `/tmp/verboflex-phase01-r3-official.3Ng2Xq/{post.1.digest,post.2.digest,head.before,head.after}`
- Exact result: exit 0, 13/13 layers, terminal
  `PHASE 1 GAUNTLET: PASS`.

The exact layer order was:

1. `source-state`
2. `checker-self-tests`
3. `backend-tests`
4. `frontend-tests-browser`
5. `types`
6. `lint-format-complexity`
7. `changed-line-coverage`
8. `mutation-properties`
9. `migration-rehearsal`
10. `openapi-drift`
11. `supply-chain-secrets`
12. `staging-adversarial-smoke`
13. `final-source-state`

### Environment and locked toolchain

- Host class: macOS arm64; Docker Engine 29.7.2 / Compose 5.3.1.
- Python execution: Python 3.14.7 through uv 0.11.12 and the locked backend
  environment. Notable resolved packages: FastAPI 0.141.1, SQLAlchemy 2.0.52,
  Alembic 1.19.1, Celery 5.6.3, Pydantic 2.13.4.
- JavaScript execution: Node 24.15.0, npm 11.16.0. Notable exact packages:
  React 19.2.8, Vite 8.2.2, TypeScript 6.0.3, Vitest 4.1.11,
  Playwright 1.62.1, Stryker 10.0.0, shadcn 4.19.0.
- Dependency reconstruction is lockfile-owned (`uv.lock` and
  `package-lock.json`); Docker builds use the pinned major/runtime boundaries
  in the tracked Dockerfiles.

### Actual numbers

| Surface | Official result |
| --- | --- |
| Backend regression | 268 passed; seed 1401 |
| Frontend unit/component | 10 files, 75 passed; shuffled seed 1401 |
| Production frontend build | 1,948 modules; JS 398.24 kB (128.96 kB gzip); CSS 49.40 kB (9.18 kB gzip) |
| Browser smoke in frontend layer | Playwright 1/1 passed in 12.6 s |
| Backend type gate | mypy clean across 36 source files |
| Frontend type gate | `tsc --noEmit` passed |
| Static quality | Ruff, Ruff format, ESLint 0 warnings, Prettier, complexity gate passed |
| Backend changed-line branch coverage | 1,007/1,007 lines, 100%, zero missing |
| Frontend changed-line branch coverage | 157/157 lines, 100%, zero missing; Cobertura branch-aware |
| Backend full mutation | 893 total; 891 killed; exactly 2 documented equivalent joins; zero other verdicts |
| Backend equivalent proof | Three production-equivalent join spellings compile to identical PostgreSQL SQL; divergent join negative control rejected |
| Backend property-only mutation | 199/199 killed |
| Frontend full mutation | 153/153 killed, 100.00% |
| Frontend property-only mutation | 37/37 killed, 100.00% |
| Migration rehearsal | 3 passed; upgrade -> downgrade -> upgrade on PostgreSQL |
| OpenAPI | drift negative control caught; checked-in schema/client clean |
| Staging/adversarial | Playwright 1/1 in 12.6 s; `adversarial auth: PASS`; `real staging smoke: PASS` |

Frontend global coverage was 37.41% statements, 21.76% branches, 53.79%
functions, and 37.78% lines because generated OpenAPI internals and source-owned
shadcn primitives are not subject to a global 100% policy. The completion gate
is exact 100% changed-line branch coverage over all handwritten production
lines. Exclusions are restricted to the SPEC-approved explicit map for
OpenAPI-generated internals, shadcn-owned code, and entrypoint-only wiring; the
gate rejects any handwritten production exclusion, empty mapping, unresolved
path, zero total, or partial branch.

### Checker reach and negative controls

The single official entry point runs its packaged checker self-tests before the
product suites. Known-bad controls establish that these gates can fail:

- source manifest/parser, required-category, missing/untracked/dirty source,
  candidate/closure state, digest drift, and caller-owned layer record;
- incomplete or duplicated layer sequences and later-layer failure cleanup;
- backend mutation missing/zero/stale statistics, unexpected survivor,
  broadened equivalent-mutant map, changed SQL proof, and property attribution;
- frontend partial Cobertura branch, noncanonical path, vacuous total, forbidden
  handwritten exclusion, and real diff-cover parser path;
- OpenAPI mutation, unreviewed secret tuple, planted true secret, staging
  placeholder secret/insecure cookie/compose leakage, adversarial wrong status
  and wrong JSON body;
- real backend-infrastructure startup followed by controlled frontend failure,
  proving zero tracked/unique Celery worker and zero PostgreSQL/Redis container.

The official run independently finished with zero scoped container and zero
Celery worker residue. No credential, token, signing secret, disposable password,
or raw secret value appears in this report.

## Product and security evidence

- JWTs enforce purpose, expiry, token version, active user, and session binding.
  The adversarial smoke exercises expired, wrong-purpose, stale-version, and
  byte-level signature-tampered JWT denial. The harness decodes the signature,
  flips a deterministic byte, re-encodes base64url, and fails closed unless the
  original and tampered signature byte strings differ.
- Ordinary refresh sessions store only SHA-256 token hashes, rotate exactly
  once, reject replay/concurrent reuse, and revoke the whole family on logout.
- Password change, administrative reset, and administrative deactivation
  increment token version and revoke live refresh authority. Deactivation
  preserves existing revocation timestamps and cannot mutate peer users.
- Logout is idempotent and clears the exact host-only cookie. Live active-user
  sessions share the authenticated-user rate budget; stale/invalid authority is
  anonymous and peer-bounded so it cannot drain the user's global budget.
- Continuous rate-limit denial is proved at the exact boundary and beyond it.
  The packaged checker also applies the approved manual mutant
  `attempts <= limit` -> `attempts != limit + 1` at all three production
  comparisons and fails closed unless the boundary/over-limit tests kill it.
- Credential failures are non-enumerating; bounds are applied before expensive
  verification; Redis outages fail closed on login/refresh/password change.
- Browser access authority remains in React memory. Refresh authority remains
  in the HttpOnly cookie flow. The real browser test proves localStorage and
  sessionStorage remain empty.
- Credentialed CORS permits one exact configured origin, never wildcard, and
  cookie-authenticated hostile Origin requests are rejected.
- API handlers do not execute background jobs inline. Celery is exercised
  through Redis transport, and status probes remain bounded.
- Every environment, including local development and tests, rejects
  `refresh_cookie_secure=false`; the host-only refresh cookie is always Secure.
  Staging/production additionally reject missing, placeholder, or short secrets
  and insecure deployment configurations. Public TLS termination remains an explicit
  later release/deployment proof, not a Phase 1 local-compose claim.

## UI and human visual gate

The Phase 1 authenticated shell was inspected at 1440x900, 768x900, and
375x812. The approved quiet hierarchy, visible focus, identity/role labels,
bounded service states, desktop sidebar, tablet/mobile Sheet, no horizontal
overflow, no clipped text, and required password-change flow passed. The user
personally performed the final disposable `Set new password` action. Later
source-bound E2E strengthening exercises four focused Escape/teardown cycles at
768px and four at 375px, real dialog DOM teardown, focus restoration, and the
absence of a competing Tooltip dismissable layer while the Sheet is open.

## Dependency and review disposition

Backend and frontend runtime audit gates pass. The one remaining Low finding,
VF-SEC-007, is a moderate advisory in the development-only transitive
`typed-rest-client -> qs` chain. It has no production dependency path. It stays
open for explicit upgrade or time-bounded acceptance at ship time; Phase 1
closure does not silently waive it.

The fresh-context source/security review is persisted naturally in the
repository, bound to the review digest, and closed only after the complete
candidate run was reconciled. It reports 0 Critical, 0 High, 0 Medium, 1 Low.

## Tier 3 independent verification history

### Round 1 — performed against historical state

- Verifier: `COMPUTER001228.local`, OpenAI Codex / GPT-5 family; genuinely fresh
  task context. Context correlation was broken; model-family correlation was
  not. No canary was used.
- Historical state: commit
  `67ef10b9af5fea5c516b606b9eb2d57c6be59bfb`, digest
  `3552de3da32987f16dbb2c0b1a4681a103e3a9d533c273ec2c96c36dac4c8584`.
- Exactly four blind inputs were supplied: complete human-approved contract;
  approved SPEC; repo at that exact state/digest; `tools/gauntlet.sh`.
  Builder conversation, draft EVIDENCE, raw logs/case study, and a separate
  review-artifact handoff were withheld.
- The verifier read the full verifier protocol, attacked run freshness, SPEC
  versus contract, tests with divergent mutants, every custom checker with
  known-bad inputs, and scenario/Must-NOT/failure mapping in both directions.
  Its blind record was frozen append-only before human grading.
- Round-1 frozen-record SHA-256 before append:
  `fe8e075d9156fb37aef093a563f3e1d72d2aa5087feb8a09cdbb996d3ff21073`.
- Eight material findings were human-graded. F-01 was a description/SPEC
  revision preserving the hardened `__Host-` cookie. F-02 through F-08 were
  behavioural: bind `.python-version`; make frontend diff coverage non-vacuous;
  recompute mutation fresh; prove property-only attribution; run packaged
  self-tests in the entry point; revoke authority on deactivation; and enforce
  logout limits per authenticated user.
- Because behavioural fixes changed the state, round 1 does not verify the final
  state. Its failed/obsolete evidence claims are retained only as history.

### Human-graded post-round source-review findings

All behavioural findings below used separate RED -> GREEN commits and invalidated
the prior candidate/digest. Failed candidates were discarded and made no PASS
claim. Fresh source review/rebind occurred after source changes.

- Caller-owned layer-record corruption by nested checker self-tests: behavioural
  checker defect; fixed with private nested layer records and negative control.
- Stale refresh credentials consuming a live user's logout budget: behavioural;
  used/revoked/expired/inactive/malformed/unknown credentials now use the
  anonymous peer sentinel; live sessions alone use user-global authority.
- Frontend coverage exclusions and partial-branch LCOV weakness: behavioural;
  exact approved exclusions plus branch-aware Cobertura, normalization,
  non-vacuous and real diff-cover controls.
- Temporary Cobertura suffix/parser and whitespace total handling: behavioural;
  fixed with private fixed-name XML and robust real-output parsing. A claimed
  cleanup/unbound defect could not be reproduced with production identity and
  was human-graded a reviewer false positive; no fix was made without RED.
- Exact detect-secrets policy line drift: behavioural checker data drift; only
  nine line numbers changed, with all 23 paths/plugins/fingerprints unchanged.
- TS2345 in deferred status test values: behavioural QA/type-safety; fixed with
  the exact generated SDK default type and no broad cast or production change.
- Responsive Sheet Escape/teardown/Tooltip competition: behavioural; repeated
  real browser REDs led to controlled Sheet/Tooltip authority and actual dialog
  teardown, with no retry, arbitrary wait, skip, weakened assertion, or timeout
  inflation.
- Five logout mutation survivors: three substantive behaviours received tests;
  two `join(User)` spellings were human-approved equivalent only after concrete
  identical PostgreSQL SQL proof. The checker accepts exactly those two and
  rejects any broadened mapping or divergent proof.
- Orphan Celery child after a later-layer failure: behavioural checker cleanup;
  direct owned process execution, unique hostname, fail-closed PID check, and a
  real lifecycle failure negative control prove cleanup.
- Text-only final-character JWT tampering could preserve decoded signature bytes:
  behavioural adversarial-harness defect; RED `112af30`, GREEN `c1fb597` now
  mutates decoded bytes deterministically. No production auth source changed.

### Round 2 — historical failed verifier state

- Historical state: commit
  `5657f91d04d37042a1fed0a23dac47dc64890727`, digest
  `c5a3ed72cdebb636086dcccf4c9e208cc13b6d559ff6b4ecc92ea21658cffd2e`.
- The genuinely fresh verifier received exactly the four permitted inputs and
  froze its blind prefix before seeing the draft. Frozen-prefix SHA-256:
  `b8199c74eecf6467db7064ed32997de454c665b57add50dad159534f0f83aa84`.
- Its source-specific verdict was `failed`: F-R2-01 found that the continuous
  post-limit rate behaviour had no mutation proof; F-R2-02 found incomplete
  bidirectional decision/remediation mapping; F-R2-03 found obsolete local
  `refresh_cookie_secure=false` description/configuration. The human graded
  F-R2-01 behavioural and F-R2-02/F-R2-03 description/mapping.
- Human grades and the explicit authorization for one exceptional third round
  were appended without changing the frozen prefix. The complete round-2
  append-only record SHA-256 is
  `18fffe7ad47b6eff4517d4b46eae653a2e824cfb2a7488251063f308ca30332b`.

### Post-round-2 remediation

- RED `2c285c1` exposed the exact post-limit mutant; RED `64ef070` required a
  fail-closed executable proof; GREEN `acdb3ba` added the exact three-site
  mutant proof and negative controls. Baseline was 8/8; the mutant produced
  exactly three failures and five passes.
- RED `be96733` proved that local insecure configuration was still accepted;
  GREEN `f4a56e0` made `Secure=true` mandatory in every environment without a
  production auth change.
- `4d4b171` completed the SPEC's bidirectional mapping for the approved round-1,
  source-review, checker, and round-2 decisions. A fresh source/security review
  found no new material finding, bound the exact review digest, and closed
  `CLOSED/PASS` in `3a0ea23` after a complete candidate gauntlet.
- The candidate and official gauntlets both ran from zero after remediation.
  The official state is the exact commit/digest named above; all 13 layers
  passed and immediate double digest plus final-before-report checks matched.

### Round 3 — explicitly authorized final verifier

- This is the single human-authorized exception to the default two-round cap.
  No fourth round is authorized.
- Exact final state: commit/digest named above.
- The fresh-context verifier received exactly four inputs: the complete
  human-approved contract, the updated approved SPEC, this exact repository
  commit/digest, and `tools/gauntlet.sh`. Builder conversation, this draft, raw
  logs/case study, and a separate review-artifact handoff were withheld.
- Verifier host: `COMPUTER001228.local`, macOS 26.5.2 arm64. Model family:
  OpenAI Codex / GPT-5. The verifier was genuinely fresh-context; context
  correlation was broken while model-family correlation was not.
- The exact gauntlet rerun passed all 13 layers. The blind attacks also covered
  SPEC-versus-contract, test gaming and six concrete divergent semantic
  mutants, packaged checker known-bad/fail-closed reach, and bidirectional
  mapping of 31 scenarios, 22 Must-NOT rules, and 21 failure rows. Every mutant
  was already killed and no mapped obligation was orphaned.
- Blind record: `/tmp/verboflex-phase1-round3-blind-record.md`. The frozen
  prefix was 13,985 bytes / 116 lines with SHA-256
  `ae149268e6134923ca53f7f32e7db5fc80f4b1554ffe9ee51ecf1c901301897d`.
  The verifier confirmed those first 13,985 bytes remained byte-identical after
  comparison.
- This draft was 18,799 bytes / 334 lines when revealed, SHA-256
  `f49d40135cb1c7e4081a8c02fb2dcf04505e19fd93cb15ce90d1eb9b325ed90e`.
  The append-only complete verifier record became 17,968 bytes / 158 lines,
  SHA-256
  `606a8da020cff35cdb0f640055211b34495e3ff014cfeb78185bf603795d2d6a`.
  After the required machine-readable `Source-digest` label passed the report
  gate, the same verifier appended the nonmaterial finalization note without a
  new round or probe. The frozen prefix remained identical; the final record is
  19,459 bytes / 174 lines with SHA-256
  `546ae8393bf4ec1b2b36211510684a4f2832ad6efa7d9b6e524de3dbf96e96de`.
- Material findings, surviving mutants, misleading claims, and evidence/SPEC
  discrepancies: none. The sole nonblocking note was historical `stub/501`
  wording in four descriptions; runtime, API, SPEC, tests, and gates implement
  the behaviour and no speculative fix was made without RED.
- Canary: `not-run/not-applicable`; no independent canary was supplied, and a
  verifier-planted repository change would neither be blind nor permitted.
- Source-specific final verdict: **`passed`**, exclusively for the exact
  branch/HEAD/tree/digest recorded above. Finalization permission: **granted**.
- Fixed after the last independently verified state: **none**.
- Round 4: not authorized and not performed.

This report is finalized only for the round-3 source-specific `passed` verdict.
A `failed` or `blocked` verdict would have forbidden finalization; a
`not performed` downgrade would have required explicit human acceptance and
full disclosure.

## Reproduction boundary

The public reproducible entry point is `tools/gauntlet.sh`; it generates its
own disposable test/staging credentials and scoped infrastructure. The raw
official files above are supporting records, not source and not required to
trust a different source state. Evidence generation is excluded from the
canonical manifest by design. After final report creation,
`tools/source_state.sh --verify-report-digest` must still match the official
digest.
