# Phase 2 Admin Configuration — Evidence

## Outcome

- Gauntlet-status: PASS
- Source-digest: `63711d77bb0ea42f7ca6a15fc3f52b72b46d99dc21b488a4294c9a8e1d5aed55`
- Review-status: CLOSED
- Open-critical-high: 0
- Live-provider-smoke: NOT RUN — BLOCKING HUMAN CHECKPOINT

Phase 2 delivers the approved administration slice: internal user administration,
versioned product configuration, repository registration, encrypted Bitbucket OAuth,
read-only repository discovery, deterministic four-format localization preview,
candidate mapping, and publication of the current explicitly confirmed candidate. No
Bitbucket provider write operation is part of this phase.

The approved Phase 2 SPEC, UI-SPEC, validation contract, and Plans 02-01 through 02-20
are the authority for this evidence. This automated execution does not claim a separate
human old-coder Tier review. The persisted OWASP ASVS 5.0 Level 1 code/security review
is source-bound and closed with no Critical or High blocker.

## Immutable source identity

- Repository: `/Users/smutti/Documents/personal/verboflex`
- Branch: `codex/phase-2-admin-configuration`
- Plan 02-20 base: `50664a2`
- Complete Phase 2 review base: `ce9fbeef86b00f594d1d06e15d3083d623c54095`
- Canonical source manifest: `tools/phase2_source_manifest.txt`
- Review artifact: `docs/reviews/phase-02-code-security.md`
- Review-mode digest: `eefa340a56806506dbc9024a380d6a59e24f109fe9daecd4d216184cd6ef9130`
- Candidate canonical digest before the review PASS annotation:
  `bdb1de56fdfab55cbd81c72f5b96ece3480bcfff12a4d66bca7e9f19f3628452`
- Final canonical digest after the source-bound review was closed:
  `63711d77bb0ea42f7ca6a15fc3f52b72b46d99dc21b488a4294c9a8e1d5aed55`

The manifest includes implementation, tests, migrations, deployment contracts,
lockfiles, verifier scripts, and the closed review. It excludes this evidence report
and generated runtime/test output. `tools/source_state.sh` rejects missing,
untracked, dirty, empty-category, or malformed manifest inputs and independently
checks the review digest and the digest captured at gauntlet entry.

## Automated gauntlet

- Candidate command: `bash tools/phase2_gauntlet.sh --candidate`
- Candidate result: exit 0, all 13 ordered layers complete, terminal
  `PHASE 2 GAUNTLET CANDIDATE: PASS (evidence not yet signed)`.
- Exact final command: `bash tools/phase2_gauntlet.sh`
- Exact final result: exit 0, all 14 ordered layers complete, terminal
  `PHASE 2 GAUNTLET: PASS`.
- Deterministic test seed: `220`

The exact ordered layers are source state, checker self-tests, backend tests and
coverage, frontend tests and coverage, type/lint/format/build, property suites,
changed-scope coverage, mutation, migrations/OpenAPI, supply-chain/secrets/licenses,
architecture/provider spy, Compose/browser smoke, final source state, and (for the
exact final command) evidence verification.

### Results

| Surface | Result |
| --- | --- |
| Backend randomized regression | 703 passed, 0 failures/errors/skips; 57.980 s |
| Frontend unit/component | 16 files, 183 passed, shuffled seed 220 |
| Backend type/static | mypy clean across 81 source files; Ruff and Ruff format clean |
| Frontend type/static/build | TypeScript, ESLint with zero warnings, Prettier, and Vite production build passed |
| Focused properties | 200 backend property cases and 3 frontend session properties passed |
| Plan 02-20 backend changed scope | 1/1 changed production line and branch covered, 100% |
| Plan 02-20 frontend changed scope | N/A: the only frontend change is a test; production-path classifier negative control passed |
| Backend mutation authority | 104/104 reviewed custom mutants killed across ten proof programs; every proof's negative control passed |
| Frontend polling mutation | 30/30 Stryker mutants killed in the critical delay and stale-authority ranges |
| Migration and schema | 3 migration tests passed; disposable PostgreSQL upgrade -> downgrade to base -> re-upgrade passed |
| OpenAPI/generated client | Canonical regeneration/drift check passed |
| Architecture/provider boundary | 28 architecture, provider-adapter, and OpenAPI tests passed |
| Mock provider deployment | 3 repositories, 2 mappings, all 4 formats; 48 GET reads and zero writes |
| Browser deployment journey | Playwright 4/4 at the 320, 768, 1024, and 1440 width contracts |

Repository-wide global coverage is reported for visibility (backend 97%; frontend
71.61% statements and 59.82% branches) but is not substituted for the plan gate.
The completion rule is 100% changed-production statement/branch coverage. Prior Phase
2 plans retain their own 100% changed-production proofs; Plan 02-20's only production
change is the bounded provider lease error mapping proven above.

## Security, dependency, and secret evidence

- `uv lock --check`, `pip-audit`, and the Python license inventory passed.
- `npm audit --audit-level=high` passed. The only reported advisory is the already
  documented Moderate development-only `qs` path under Stryker tooling.
- `npm audit --omit=dev --audit-level=moderate` passed with no production advisory.
- The complete npm dependency tree and direct-package provenance/license inventory
  were generated from the lockfile-resolved installation.
- The Phase 2 secret scan found exactly five reviewed test/code false positives and
  zero unreviewed finding. Browser storage guards passed, and Compose logs contained
  no disposable password, OAuth credential, bearer, refresh token, or secret value.
- The TLS mock provider audit observed 48 bounded GET reads and zero POST, PUT, PATCH,
  or DELETE requests. API and worker ran as distinct processes, and smoke teardown
  removed the scoped Compose resources.

The fresh review covers the complete Phase 2 diff against OWASP ASVS 5.0 Level 1 and
records explicit dispositions for authorization, OAuth, secrets, parsing, stale
authority, migrations, provider writes, idempotency, API drift, and responsive access.
Its final disposition is CLOSED with zero open Critical or High finding.

## Fail-closed checker and failure history

No failed or partial run is counted as a passing result. During finalization the
following checker defects were exposed and corrected before the recorded candidate:

- layer functions now execute under `set -e`, so an early command failure cannot be
  masked by a later successful command;
- the coverage gate applies the plan's 100% changed-production rule rather than an
  unrelated repository-global threshold and rejects zero-line backend reports;
- frontend changed-scope classification excludes test/spec/story files and has a
  negative control, allowing N/A only when no production path changed;
- custom mutation checkers were realigned with the final lease and preview-result
  authority boundaries, and focused polling mutation added the exact 29-second edge;
- a non-contractual complexity gate was removed after it flagged previously approved
  Phase 2 code despite green coverage, mutation, types, and static quality gates.

The mocked deployment smoke also exposed a real High-severity defect before closure:
lease acquisition after a local Bitbucket disconnect escaped bounded adapter error
mapping. A regression test was added and the acquisition now remains inside the
reviewed exception boundary. The final mock smoke receives the approved bounded
response and still observes zero provider writes.

## Deliberate live-provider checkpoint

No live Bitbucket OAuth navigation, metadata read, file read, provider mutation, or
provider credential use was performed while producing this evidence. Task 3 remains a
blocking-human gate. Before it can run, the user must personally verify all of the
following:

1. The organizational test consumer callback exactly matches `BITBUCKET_CALLBACK_URL`.
2. Permission is exactly `repository`; no write or admin scope is enabled.
3. Consumer credentials are disposable.
4. One representative disposable test repository is authorized for bounded read-only
   metadata, branch pagination, commit resolution, tree pagination, and raw reads.
5. File contents and token values will not be captured, and no fixed A-03 limit will be
   changed without a separately reviewed contract.

Only after that personal verification and authorization may the agent run
`bash tools/phase2_smoke.sh --live-provider-read-only`. Local generation revoke is the
guarantee; no provider-side revoke is claimed. The exact resume signal is
`consumer verified`.

## Known limit

The Moderate development-only `@stryker-mutator/core -> typed-rest-client -> qs`
advisory remains open in `.planning/phases/02-admin-configuration/deferred-items.md`.
It has no production dependency path, the production audit is clean, and no unreviewed
lockfile override was introduced.
