# Phase 2: Admin Configuration - Research

**Researched:** 2026-08-26  
**Domain:** administrator control plane, transactional configuration publication, Bitbucket Cloud OAuth/read-only discovery, localization preview  
**Confidence:** HIGH for repository architecture and decision contracts; MEDIUM for current external-provider behavior

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Internal user lifecycle
- **D-01:** User creation and administrative password reset generate a temporary password in the backend, reveal it exactly once to the administrator, and require the affected user to change it at first login.
- **D-02:** A user's corporate email is immutable after account creation. Correcting an erroneous email requires a new account. — **Reversibility:** costly — changing this later alters the stable login identifier contract and every administrative/audit flow that refers to it.
- **D-03:** Administrators may update only the user's display name, assigned roles, lifecycle state, and password authority through the dedicated reset operation; password plaintext is never stored or recoverable.
- **D-04:** Roles are additive, any combination of the four fixed roles is allowed, and every user must retain at least one role.
- **D-05:** An administrator cannot remove their own `admin` role. Role changes and lifecycle mutations must transactionally preserve at least one active administrator.
- **D-06:** Deactivation is reversible. Deactivation immediately revokes all authority for the user; reactivation generates a new one-time temporary password and again requires a password change.

### Products and reusable repositories
- **D-07:** A Bitbucket repository is a global resource identified uniquely by normalized `workspace + repository_slug`, with an optional descriptive name. It may be reused by multiple products. — **Reversibility:** one-way — changing to product-owned repository rows after launch requires a data migration and rewrites repository and mapping API identities.
- **D-08:** Product-repository mappings hold product-specific branch and localization configuration; reuse of the global repository never forces products to share those settings.
- **D-09:** Only the product has an active/inactive operational state. Mappings do not have independent draft/enabled/disabled states.
- **D-10:** Activating or publishing a product requires every mapping in the candidate configuration to pass validation and preview. Deactivating a product suspends all of its mappings without deleting configuration.
- **D-11:** Every product-repository mapping stores exactly one source branch, one or more allowed pull-request target branches, and one designated default target branch. Different products may use different branches of the same repository.

### Localization mapping and live preview
- **D-12:** One mapping model supports two explicit topologies: `direct`, where keys and translations use one repository side, and `separate`, where key and translation repository sides are linked explicitly. — **Reversibility:** one-way — splitting this into unrelated schemas later requires migration of mapping identities and published API payloads.
- **D-13:** Repository localization layout is discovered automatically. Administrators do not maintain globs, per-file lists, or language extraction templates in v1.
- **D-14:** Phase 2 pulls forward the Bitbucket read access and minimal format-detection work previously assigned to Phases 3 and 4. Minimal parsers are read-only preview adapters, not the later canonical import or format-preserving writer implementations.
- **D-15:** Preview displays detected files, formats, languages, sample keys, and sample translations. Ambiguous or invalid detection blocks activation; an administrator must explicitly confirm a successful preview.
- **D-16:** Repository scanning and parsing must respect the existing background-job boundary when work is not safely bounded for an HTTP request.

### Pull-request behavior and admin UX
- **D-17:** Pull-request grouping is fixed per repository and target branch. Compatible changes for all languages and files in that repository/target pair belong to one PR; a change set must never span repositories or target branches.
- **D-18:** Administrators configure an allowed target-branch list plus a default target. A future submitter may choose another target only from the allowed list.
- **D-19:** New product setup uses a guided wizard. After creation, configuration is organized into focused overview, repository, mapping, and preview sections; user administration remains a global admin section in the same shell.
- **D-20:** Edits to an active product create a candidate configuration revision. The currently active revision remains effective until the candidate passes validation and preview and an administrator publishes it atomically. — **Reversibility:** one-way — removing revisioned publication later requires collapsing active/candidate records and changing concurrency and API semantics.

### Bitbucket authentication
- **D-21:** VerboFlex authenticates to Bitbucket Cloud with OAuth 2.0 rather than repository/workspace access tokens, API tokens, or deprecated app passwords. — **Reversibility:** costly — changing the provider credential model affects callback APIs, encrypted token persistence, refresh/rotation, capability checks, and repository bindings.
- **D-22:** Bitbucket access and refresh credentials remain backend-only, encrypted at rest, excluded from API responses and logs, and independent from VerboFlex's internal user authentication. Microsoft Entra ID/OIDC remains deferred and is not part of this decision.
- **D-23:** The Phase 2 SPEC/research must define the least-privilege Bitbucket OAuth scope matrix for preview now and later write/PR capabilities; implementation must not request an undocumented superset by default.

### the agent's Discretion
- Exact API resource names, pagination defaults, list sorting, validation copy, and wizard micro-interactions may follow established FastAPI, generated-client, and shadcn patterns.
- Exact automatic-detection confidence thresholds may be chosen during specification, provided ambiguity fails closed and requires explicit administrator confirmation.
- Exact temporary-password length and generation mechanism may reuse or strengthen the existing password-policy boundary without weakening Phase 1 guarantees.

### Deferred Ideas (OUT OF SCOPE)
- Microsoft Entra ID/OIDC for VerboFlex user authentication remains a future identity-provider integration.
- Full canonical import, durable source baselines, stable translation identity, and complete parser fixtures remain downstream work after the minimal read-only preview adapters.
- Format-preserving writes, change-set execution, commits, and pull-request creation remain in the later write-back and PR phases.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-02 | Admin can create, update, administratively reset passwords for, deactivate, and view internal users. | Reuse the database-authoritative principal and extract the CLI reset/deactivation transaction into one admin-user service; one-time credential and last-admin tests are specified below. |
| AUTH-03 | Admin can assign multiple roles to the same user. | Preserve the fixed four-role set, set semantics, nonempty roles, self-admin and last-active-admin invariants under one authority lock. |
| PROD-01 | Admin can create and edit a product record with name, description, and active/inactive status. | A-01 gives the exact globally unique normalized-name contract; active/candidate pointer publication prevents draft edits changing live state. |
| PROD-02 | Admin can configure one or more Bitbucket Cloud repositories for a product. | Global repository registry plus revision-owned mappings preserves reuse without cross-product coupling. |
| PROD-03 | Admin can configure the source branch the platform reads from for each repository mapping. | Exact provider branch strings are stored on the mapping and validated against a bounded live list. |
| PROD-04 | Admin can configure allowed target branches for translation pull requests. | Target branches have set semantics; default must be a member; all branches are validated live. |
| PROD-05 | Admin can configure product-specific pull request grouping behavior. | The only v1 grouping key is the ordered pair `(repository_id, target_branch)`; a pure contract test makes it falsifiable. |
| PROD-06 | Admin can configure whether translations live directly in the product repository or in a linked translation repository. | One mapping schema uses exact topology values `direct` and `separate`; topology validation rejects missing or extra sides. |
| PROD-07 | Admin can configure links between a repository containing translation keys and a separate Bitbucket project/repository containing translated values. | Separate topology holds explicit key and translation repository-side references inside the product revision. |
| PROD-08 | Admin can validate a repository mapping by previewing detected files, languages, sample keys, and sample translations before enabling imports. | A-02/A-03 define strict fixtures, asynchronous jobs, scan budgets, deterministic samples, confidence, confirmation digest, and stale-result protection. |
| PROD-09 | Admin can configure the localization file format used by each mapping. | Discovery returns one candidate per exact format/layout; confirmation selects exactly one and mixed/ambiguous layouts fail closed. |
| BITB-01 | Admin can connect, reconnect, revoke, and view bounded status for the single organization-wide Bitbucket Cloud OAuth 2.0 connection used for repository access. | Scope matrix, state handling, encrypted token generation, rotation serialization and local revocation are defined below. |
| BITB-03 | System can list configured repository branches from Bitbucket Cloud. | Follow opaque Bitbucket pagination with `pagelen=100`; expose an application cursor with default 50/max 100 and validate provider next URLs. |
| BITB-04 | System can read configured localization files from the configured Bitbucket Cloud source branch. | Commit-bound, read-only source browsing has explicit count/depth/byte/time caps and no provider write capability. |
| UI-03 | Admin configuration screens provide clear validation feedback for repository, branch, mapping, and credential setup. | Wizard state model, bounded background polling, accessible errors, secret reveal, generated-client drift and Playwright gates are included. |
</phase_requirements>

## Summary

Phase 2 should be planned as four cooperating authorities, not as a single CRUD feature: admin-user authority, immutable product configuration revisions, a backend-only Bitbucket connection, and commit-bound preview jobs. The existing Phase 1 authentication, PostgreSQL transaction, Celery, generated-client and app-shell seams already support this split. In particular, the repository currently defines roles verbatim as `"admin"`, `"product_manager_reviewer"`, `"translator"`, and `"viewer"`; `require_roles()` compares these against database-loaded principal roles. [VERIFIED: `backend/src/verboflex/models/role.py:18-23`; `backend/src/verboflex/auth/principal.py:128-142`]

The residual assumptions can be closed without user input. A-01 is a global, case-insensitive product-name key based on NFKC, whitespace collapse and `casefold()`. A-02 is a deliberately narrow encoding/shape matrix with duplicate-aware strict JSON and format-specific unsupported fixtures. A-03 uses an always-asynchronous, 60-second preview contract with explicit repository, file, byte, language and sample ceilings. These are product contracts, not claims about third-party defaults. [RECOMMENDED: falsifiable Phase 2 contracts; confidence HIGH]

Bitbucket OAuth scopes are static on the OAuth consumer rather than selectively narrowed on each grant. Therefore Phase 2 must configure the consumer with only `repository`, validate the granted/live scopes, and treat later write/PR scope changes as a new consumer permission profile plus explicit reauthorization. [CITED: https://support.atlassian.com/bitbucket-cloud/docs/use-oauth-on-bitbucket-cloud/] [CITED: https://developer.atlassian.com/cloud/bitbucket/bitbucket-cloud-rest-api-scopes/]

**Primary recommendation:** plan RED→GREEN vertical slices around transactional service invariants first, then OAuth/provider access, one detector at a time, job confirmation/publication, generated client, and finally the guided UI; never let route handlers, workers, or the SPA become the authority for concurrency or publication.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Admin authentication/authorization | API / Backend | Database / Storage | FastAPI dependencies deny unauthenticated/non-admin calls; current roles and session authority are loaded from PostgreSQL. |
| User lifecycle and last-admin invariant | API / Backend | Database / Storage | One domain service defines the mutation; PostgreSQL serializes competing authority changes. |
| Product/repository/revision persistence | Database / Storage | API / Backend | Constraints, foreign keys, immutable published revisions and pointer swaps are durable invariants. |
| Bitbucket OAuth redirect/token exchange | API / Backend | Database / Storage + Redis | The backend owns state consumption, encrypted credentials and token generation; the browser sees status only. |
| Branch/source discovery | API / Backend | Bitbucket Cloud | A provider adapter enforces URL, pagination, timeout and content budgets. |
| Localization detection/preview | Celery worker | Database / Storage | Jobs perform bounded provider reads and parsing; durable job/result rows are the public source of truth. |
| Candidate confirmation/publication | API / Backend | Database / Storage | Confirmation and active-pointer swap are transactional, commit/digest/revision-bound operations. |
| Guided admin UX | Browser / Client | API / Backend | React owns wizard/form/polling presentation; generated API contracts and backend checks remain authoritative. |

## Project Constraints (from AGENTS.md)

- Keep frontend and backend separate; React + Vite + TypeScript and project-owned shadcn/ui are locked for the SPA, while Python + FastAPI owns the API. [VERIFIED: `AGENTS.md:6-28`]
- PostgreSQL + SQLAlchemy + Alembic own persistence/migrations; Celery + Redis own repository imports, parsing, commits and PR work that must not run in HTTP requests. [VERIFIED: `AGENTS.md:16-22`]
- Authentication remains OAuth2 bearer tokens over internal users with multiple roles; Microsoft enterprise authentication is deferred. [VERIFIED: `AGENTS.md:20-28`]
- Bitbucket Cloud is the only v1 provider and the first supported formats are Android XML, Qt `.ts`, JSON and iOS `.strings`. [VERIFIED: `AGENTS.md:12-25`]
- Every phase closes with targeted tests, code review, and build/deploy smoke verification; this project additionally has TDD and Nyquist validation enabled. [VERIFIED: `AGENTS.md:22-23`; `.planning/config.json:1-36`]
- Follow existing patterns because conventions/architecture are not yet separately established, and use a GSD workflow for writes. [VERIFIED: `AGENTS.md:113-137`]

## Decisions Closing Residual Assumptions

### A-01 — Exact product-name contract

Use this algorithm, in this order, for both create and rename: [RECOMMENDED: exact Phase 2 contract; confidence HIGH]

1. Require a string input.
2. Apply `unicodedata.normalize("NFKC", raw_name)`.
3. Replace every maximal run of characters for which `str.isspace()` is true with one ASCII space, then remove an outer ASCII space.
4. Reject an empty result, more than 120 Unicode code points, NUL, or any remaining character for which `str.isprintable()` is false.
5. Persist the result as `display_name` and persist `name_key = display_name.casefold()`.
6. Enforce one global database `UNIQUE(name_key)`; product identity remains its UUID. Equality and conflicts use `name_key`, while responses show the normalized `display_name`.

Python documents NFKC as compatibility decomposition followed by canonical composition and `casefold()` as the aggressive case-insensitive comparison transform. [CITED: https://docs.python.org/3.15/library/unicodedata.html] [CITED: https://docs.python.org/3/howto/unicode.html]

The exact examples that must become tests are: [RECOMMENDED: acceptance fixtures; confidence HIGH]

| Inputs | Result |
|--------|--------|
| `"  VerboFlex\tMobile  "` | display `"VerboFlex Mobile"`, key `"verboflex mobile"` |
| `"VerboFlex"` vs `"verboflex"` | conflict |
| `"Cafe\u0301"` vs `"Café"` | conflict |
| `"Ａpp"` vs `"App"` | conflict |
| `"Café"` vs `"Cafe"` | distinct |
| `"Product-A"` vs `"Product A"` | distinct |
| whitespace-only, NUL/control-containing, or 121-code-point input | reject |

Do not strip accents, transliterate, delete punctuation, use a database-locale collation as the identity rule, or mutate already-published product UUIDs. [RECOMMENDED: prevents environment-dependent identity; confidence HIGH]

### A-02 — Exact preview encoding and JSON shape contract

All decoders are strict: decoding errors, embedded NUL, duplicate semantic identities and unsupported constructs are blocking outcomes; never insert replacement characters. Measure the raw byte ceiling before decoding. [RECOMMENDED: fail-closed preview boundary; confidence HIGH]

| Format | Accepted encodings | Rejected encodings/conditions |
|--------|--------------------|------------------------------|
| JSON | UTF-8; optional UTF-8 BOM is stripped | UTF-16/32, legacy encodings, malformed UTF-8, duplicate object names, `NaN`/`Infinity` |
| Android XML | UTF-8; optional UTF-8 BOM; declaration absent or encoding label equal to UTF-8 case-insensitively | UTF-16/32, declared non-UTF-8, DTD/entity declarations, malformed XML |
| Qt `.ts` | UTF-8; optional UTF-8 BOM; declaration absent or encoding label equal to UTF-8 case-insensitively | UTF-16/32, declared non-UTF-8, DTD/entity declarations, malformed XML |
| iOS `.strings` | UTF-8 with optional BOM, or UTF-16LE/UTF-16BE only when the matching BOM is present | BOM-less UTF-16, UTF-32, legacy encodings, malformed sequences |

RFC 8259 requires UTF-8 for exchanged JSON, notes that parsers may ignore a UTF-8 BOM, and warns that duplicate object names produce unpredictable behavior. [CITED: https://www.rfc-editor.org/rfc/rfc8259] Apple documents `.strings` as semicolon-terminated key/value pairs with C-style comments and recommends UTF-8 source; its text-loading guidance recognizes UTF-16 with a BOM. [CITED: https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/LoadingResources/Strings/Strings.html] [CITED: https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/Strings/Articles/readingFiles.html]

Only these two minimal JSON localization shapes are supported: [RECOMMENDED: Phase 2 detector contract; confidence HIGH]

```json
{"welcome.title": "Welcome", "button.ok": "OK"}
```

- **Flat-per-locale:** a nonempty top-level object whose keys are nonempty strings and whose values are strings. The locale must be unambiguous from either a filename stem such as `it-IT.json` or one locale directory component such as `it-IT/messages.json`, but not contradictory sources.

```json
{"en": {"welcome.title": "Welcome"}, "it": {"welcome.title": "Benvenuto"}}
```

- **Locale-rooted:** a nonempty top-level object where every first-level key is a locale and every value is a nonempty flat object of nonempty string keys to string values.

The supported locale subset is exactly language (2–3 ASCII letters), optional script (4 ASCII letters), and optional region (2 ASCII letters or 3 digits), separated by `-` or `_`. Canonicalize separators to `-`, language lower-case, script title-case and region upper-case. Reject variants/extensions in Phase 2 instead of guessing. [RECOMMENDED: deterministic locale extraction; confidence HIGH]

Use `json.loads` with `object_pairs_hook` to reject duplicates and `parse_constant` to reject non-finite values. Reject top-level arrays/scalars, empty objects, nested values beyond the locale-rooted level, mixed root shapes, booleans/numbers/null, blank keys, duplicate canonical locales, and ambiguous path locale. Sort paths, languages and keys by Unicode code-point order before sampling. [RECOMMENDED: strict deterministic detector; confidence HIGH]

Format fixture boundary: [RECOMMENDED: supported/unsupported detector matrix; confidence HIGH]

| Format | Supported fixture | Unsupported/blocking fixture |
|--------|-------------------|------------------------------|
| Android XML | `<resources>` containing plain-text `<string name="…">…</string>` values | `plurals`, `string-array`, child markup/spans, duplicate names, entity/DTD, content outside the minimal root |
| Qt `.ts` | `TS/context/message/source/translation`, non-`numerus`, one plain translation | numerus messages, translation variants, unfinished/obsolete entries, child byte/markup nodes, duplicate message identity |
| JSON | either exact minimal shape above | nested namespaces, mixed locales/strings, arrays, scalar/null/non-finite values, duplicates, ambiguous locale |
| iOS `.strings` | quoted key, `=`, quoted value, `;`, whitespace and C-style comments, documented escapes | missing semicolon, duplicate decoded key, invalid escape/unicode, preprocessor constructs, plural dictionaries |

Android documents `<resources>/<string name>` and treats arrays/plurals as different resource constructs; Qt's TS schema includes numerus, translation state and variants beyond this phase's minimal adapter. [CITED: https://developer.android.com/guide/topics/resources/string-resource] [CITED: https://doc.qt.io/qt-6/linguist-ts-file-format.html] Use `defusedxml` for both XML preview adapters because Python's XML security guidance recommends hardened parsing for untrusted data. [CITED: https://docs.python.org/3/library/xml.html]

The iOS detector should be a small state-machine lexer with source spans, not a regex and not a writer. Every unsupported construct is reported and blocks confirmation. Phase 4 is still responsible for canonical identities and complete format fixtures. [RECOMMENDED: phase boundary; confidence HIGH]

### A-03 — Exact operational bounds

All previews are asynchronous. `POST` creates or reuses a durable job and returns `202`; the public state values are exactly `"queued"`, `"running"`, `"succeeded"`, `"failed"`, and `"timed_out"`. A retry for identical `(repository, branch, commit, candidate_revision, layout_detector_version)` reuses the same digest/result; retry after a terminal failure creates a new attempt attached to that digest. [RECOMMENDED: one predictable API contract; confidence HIGH]

| Bound | Exact value | Failure behavior |
|-------|-------------|------------------|
| Bitbucket provider page size | `pagelen=100` | follow only provider `next`; never synthesize page numbers |
| Source tree pagination | 50 pages and 5,000 entries total | terminal blocking `limit_exceeded` |
| Directory depth | 12 path components below repository root | terminal blocking `limit_exceeded` |
| Candidate localization files | 500 | terminal blocking `limit_exceeded` |
| One raw file | 1,048,576 bytes (1 MiB) | file and layout are unsupported; confirmation blocked |
| All downloaded raw files | 20,971,520 bytes (20 MiB) | terminal blocking `limit_exceeded` |
| Detected languages | 32 | terminal blocking `limit_exceeded` rather than truncating validity |
| Preview samples | at most 10 per language and 100 total | deterministic truncation; response says `samples_are_partial=true` |
| Confidence | exactly `1.0` required | anything lower, multiple interpretations, malformed/unsupported/empty content blocks confirmation |
| Provider HTTP timeouts | connect 3 s, read 10 s, write 10 s, pool 3 s | fail current attempt; no hidden automatic HTTP retry in Phase 2 |
| Worker budget | soft limit 60 s, hard limit 75 s | durable `timed_out`; no confirmation |
| Frontend polling | every 2 s through 30 s, then 5 s through 90 s | stop automatic polling at 90 s; show manual Refresh/Retry |
| Admin list pagination | default 50, maximum 100 | opaque stable cursor; reject invalid cursor |

Bitbucket pagination guarantees `values` and `next`; clients must treat `next` as opaque, and `pagelen` is bounded from 10 through 100. [CITED: https://developer.atlassian.com/cloud/bitbucket/rest/intro/] The source API exposes directory pagination and a `max_depth` parameter, but VerboFlex must still enforce its own entry/depth/byte limits. [CITED: https://developer.atlassian.com/cloud/bitbucket/rest/api-group-source/] HTTPX exposes separate connect/read/write/pool timeouts; set all explicitly. [CITED: https://www.python-httpx.org/advanced/timeouts/]

Send `Accept-Encoding: identity`, stream responses, count bytes while reading, reject redirects, and permit only `https://api.bitbucket.org` after parsing every initial and pagination URL. Treat `next` as provider data, not as a trusted URL. [RECOMMENDED: SSRF/decompression-bomb boundary; confidence HIGH]

Preview identity must include the selected provider commit hash, candidate revision UUID/version, repository side(s), detector version and layout identity. Persist deterministic output and a digest of all validity-relevant fields. Confirmation stores `(preview_job_id, preview_digest, confirmed_by, confirmed_at)`; candidate mutation, reconnect generation change, branch/commit change or detector version change invalidates it. [RECOMMENDED: stale-result prevention; confidence HIGH]

## Standard Stack

### Existing core — do not replace

The exact backend runtime dependencies currently include `"fastapi==0.141.1"`, `"celery[redis]==5.6.3"`, `"sqlalchemy==2.0.52"`, `"alembic==1.19.1"`, `"psycopg[binary]==3.3.4"`, `"redis==6.4.0"`, `"pwdlib[argon2]==0.3.1"`, and `"PyJWT==2.13.0"`. [VERIFIED: `backend/pyproject.toml:9-23`] The existing test stack quotes `"pytest==9.1.1"`, `"hypothesis==6.165.10"`, `"httpx==0.28.1"`, `"mutmut==3.7.0"`, and `"diff-cover==10.5.1"`. [VERIFIED: `backend/pyproject.toml:29-43`]

| Library | Version | Phase 2 purpose | Direction |
|---------|---------|-----------------|-----------|
| FastAPI | 0.141.1 | typed admin/OAuth/job API and dependency authorization | reuse existing |
| SQLAlchemy | 2.0.52 | row locks, revision models, transactions | reuse existing |
| Alembic | 1.19.1 | reversible Phase 2 schema | reuse existing |
| PostgreSQL | containerized project service | constraints, advisory/row locks, atomic publication | reuse existing |
| Celery + Redis | 5.6.3 + 6.4.0 client | bounded preview execution and OAuth-state TTL storage | reuse existing |
| pwdlib/Argon2 | 0.3.1 | generated temporary-password hashing | reuse existing |
| Pydantic | transitive/current FastAPI line | strict API and detector result schemas | reuse existing |
| React/Vite/TypeScript/shadcn | current project pins | admin wizard, status polling, accessible state UI | reuse existing |

FastAPI documents hierarchical dependencies and response models as the boundary for shared authorization and output filtering. [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/] [CITED: https://fastapi.tiangolo.com/tutorial/response-model/] SQLAlchemy documents `with_for_update()` and mapper version counters; PostgreSQL documents row locks and serializable failures. [CITED: https://docs.sqlalchemy.org/en/20/core/selectable.html] [CITED: https://docs.sqlalchemy.org/en/20/orm/versioning.html] [CITED: https://www.postgresql.org/docs/current/explicit-locking.html]

### Required runtime dependency changes

| Package | Version | Purpose | Change |
|---------|---------|---------|--------|
| `httpx` [WARNING: legitimacy seam flagged suspicious — verify before promotion.] | 0.28.1 | pooled Bitbucket OAuth/REST client with explicit streaming/timeouts | promote existing dev dependency to direct runtime dependency |
| `defusedxml` [WARNING: legitimacy seam flagged suspicious — verify before installation.] | 0.7.1 | hostile XML rejection for Android/Qt preview | add direct runtime dependency |
| `cryptography` [WARNING: legitimacy seam flagged suspicious — verify before installation.] | 50.0.1 | MultiFernet authenticated encryption and key rotation for provider tokens | add direct runtime dependency |

HTTPX's official documentation covers the timeout and client APIs, defusedxml is referenced by Python's XML security documentation, and cryptography documents MultiFernet rotation. [CITED: https://www.python-httpx.org/] [CITED: https://docs.python.org/3/library/xml.html] [CITED: https://cryptography.io/en/latest/fernet/]

Do not add an OAuth wrapper, JSONPath package, locale package, XML writer, iOS writer or new frontend state library in Phase 2. The provider exchange is a narrow HTTP adapter; strict JSON uses the standard library; locale support is an intentionally bounded recognizer; preview never writes source. [RECOMMENDED: dependency minimization consistent with locked boundary; confidence HIGH]

### Package Legitimacy Audit

The required PyPI registry checks observed versions `httpx 0.28.1`, `defusedxml 0.7.1`, and `cryptography 50.0.1`; the project legitimacy seam returned `SUS` for each because registry download/source signals were incomplete, not because any package was `SLOP`. Registry existence does not earn verified package provenance, so all three retain the warning and human checkpoint below. [CITED: https://pypi.org/project/httpx/] [CITED: https://pypi.org/project/defusedxml/] [CITED: https://pypi.org/project/cryptography/]

| Package | Registry | Latest publish signal | Downloads | Source repo signal | Verdict | Disposition |
|---------|----------|-----------------------|-----------|--------------------|---------|-------------|
| httpx | PyPI | 2024-12-06 | unknown to seam | `github.com/encode/httpx` | SUS | planner adds human verification before runtime promotion |
| defusedxml | PyPI | 2021-03-08 | unknown to seam | `github.com/tiran/defusedxml` | SUS | planner adds human verification before install |
| cryptography | PyPI | 2026-08-25 | unknown to seam | unavailable to seam | SUS | planner adds human verification before install |

**Packages removed due to SLOP verdict:** none.  
**Packages flagged as suspicious:** `httpx`, `defusedxml`, `cryptography`; the plan must insert `checkpoint:human-verify` before each direct runtime dependency change. [RECOMMENDED: mandatory legitimacy-gate disposition]

## Architecture Patterns

### System Architecture Diagram

```text
Authenticated admin SPA
        |
        | generated HTTP client + bearer token
        v
FastAPI /api/v1/admin ---------------------> PostgreSQL
  | require_roles(admin)                       | users/sessions/roles
  |                                            | products -> active/candidate revision
  | OAuth start/callback                       | repository registry/mappings
  |                                            | encrypted Bitbucket generation
  | enqueue preview                            | durable preview jobs/results/confirmations
  v                                            ^
Redis -------------------------------- Celery worker
  | single-use OAuth state                      |
  | broker                                      | bounded provider adapter
  +---------------------------------------------+
                                                |
                                                v
                                      Bitbucket Cloud REST
                                      branches -> commit -> tree/files
                                                |
                                                v
                                   detector registry decision
                                  / valid candidate -> samples
                                  \ ambiguous/invalid -> block

Publish request -> lock Product -> verify every mapping's current confirmed digest
                -> atomic active_revision pointer swap OR complete rollback
```

### Recommended Project Structure

```text
backend/src/verboflex/
├── api/v1/routes/admin/         # thin user/product/repository/preview/status routes
├── services/                    # transactional admin_users, revisions, OAuth, publication
├── bitbucket/                   # OAuth exchange + bounded REST adapter
├── localization/preview/        # detector protocol + four read-only adapters
├── models/                      # product/revision/repository/mapping/connection/job rows
├── schemas/                     # request/response projections with no provider secrets
└── worker/                      # preview task orchestration
frontend/src/features/admin/
├── users/                       # lifecycle table and one-time secret dialog
├── products/                    # wizard and revision forms
├── repositories/               # registry and branch selectors
├── mappings/                    # topology/layout configuration
└── previews/                    # polling, candidates, confirmation and blocking feedback
```

These are recommended new ownership boundaries, not pre-existing paths. Existing integration points are the versioned router, current app router, responsive shell and memory-only session provider. [VERIFIED: `backend/src/verboflex/api/v1/router.py:1-11`; `frontend/src/router.tsx:17-62`; `frontend/src/components/layout/AppShell.tsx:22-159`; `frontend/src/features/auth/session.tsx:19-171`]

### Pattern 1: One transactional authority service for user lifecycle

The current password constants are verbatim `MIN_PASSWORD_CHARACTERS = 12`, `MAX_PASSWORD_CHARACTERS = 128`, and `PASSWORD_HASHER = PasswordHash.recommended()`. [VERIFIED: `backend/src/verboflex/auth/passwords.py:6-8`] Generate 24 random bytes with `secrets.token_urlsafe(24)` (32 URL-safe ASCII characters), hash immediately, retain plaintext only in the successful response object, set forced password change, advance token version, and revoke sessions inside the same database transaction. [RECOMMENDED: password-policy-compatible one-time secret; confidence HIGH]

Extract the CLI's existing lock/reset/deactivate semantics rather than copying them into routes. The repository already uses `FIRST_ADMIN_LOCK_KEY = 0x564552424F464C58`, `SELECT pg_advisory_xact_lock(:lock_key)`, a target `with_for_update()`, `user.token_version += 1`, and bulk session revocation. [VERIFIED: `backend/src/verboflex/cli.py:24`; `backend/src/verboflex/cli.py:55-91`; `backend/src/verboflex/cli.py:94-148`]

Acquire one transaction-scoped admin-authority advisory lock for every create/role/deactivate/reactivate mutation, then lock the target user. Re-read the actor and roles under the transaction; reject an empty role set, self-admin removal, and any prospective state with zero active admins. Only after validation mutate password/lifecycle/roles and revoke sessions. [RECOMMENDED: serialization point for the global last-admin invariant; confidence HIGH]

### Pattern 2: Immutable published revision plus optimistic candidate

Model a stable Product with `active_revision_id`, `candidate_revision_id`, `is_active`, `name_key` and ordinary metadata. A ProductRevision owns description and all mapping configuration. Once a revision is published, reject every mutation to it; edit only the candidate. [RECOMMENDED: direct implementation of D-20; confidence HIGH]

Give the candidate an integer version counter. Every mutation includes the expected version; use SQLAlchemy `version_id_col` or an explicit `UPDATE … WHERE id=:id AND version=:expected`, returning `409` when zero rows match. SQLAlchemy documents mapper version counters as stale-update detection. [CITED: https://docs.sqlalchemy.org/en/20/orm/versioning.html]

Publication receives candidate revision/version and confirmed preview digest set. Within one transaction, lock Product `FOR UPDATE`; if the same revision is already active return the current representation as an idempotent no-op. Otherwise verify the candidate pointer/version and quantify **every** mapping in SQL: nonempty set, live OAuth generation, successful current preview, exact commit/revision/layout digest and admin confirmation. Swap the active pointer and clear the candidate pointer only if every predicate holds. [RECOMMENDED: single linearization point; confidence HIGH]

Two publishers therefore have one winner. An identical retry observes the already-active revision and succeeds without another revision; a different/stale candidate receives `409`; every validation or database error rolls back and leaves the former active pointer untouched. [RECOMMENDED: concurrency acceptance contract; confidence HIGH]

### Pattern 3: Backend-only OAuth generation

Persist exactly one Bitbucket connection row with an integer `generation`, encrypted access/refresh blobs, provider expiry, connection/revocation timestamps and a scope profile. Put client ID/client secret and a comma-separated MultiFernet key ring in deployment secrets; encrypt with the first key and allow older keys only for decrypt/rotation. MultiFernet documents this primary-key encryption/fallback-decryption behavior. [CITED: https://cryptography.io/en/latest/fernet/]

OAuth start requires admin, generates 32 random bytes, stores only a digest in Redis for 10 minutes with initiating admin/session/generation and fixed post-callback location, and sends that state to Bitbucket. Callback atomically consumes the state, requires exact redirect URI, exchanges the code in the backend, validates scope, stores a new encrypted generation and redirects only to the fixed SPA status page. RFC 9700 requires CSRF protection by one-time state bound to the user-agent when PKCE is not the verified mechanism. [CITED: https://www.rfc-editor.org/rfc/rfc9700] Bitbucket's current documentation does not document PKCE, so Phase 2 must not claim or depend on it. [CITED: https://developer.atlassian.com/cloud/bitbucket/rest/]

Serialize refresh/rotation/revoke on the singleton row and generation. A bounded refresh reads the current generation under lock, calls the provider, then atomically replaces both rotated tokens; any stale generation is discarded and `invalid_grant` becomes `reauthorization_required`. A revoked generation is rejected before any repository call. [RECOMMENDED: rotation/revoke race contract; confidence HIGH]

### Pattern 4: Durable job resource, not raw Celery result

Celery documents task states, retry identity and soft/hard time limits, but provider calls still require explicit I/O timeouts. [CITED: https://docs.celeryq.dev/en/stable/userguide/tasks.html] Store public status, input digest, attempt, timestamps, bounded error code, output and confirmation authority in PostgreSQL. Celery carries only the job UUID and updates the durable row conditionally; a stale worker may not overwrite a newer candidate/generation. [RECOMMENDED: stable API and retry-safe worker authority; confidence HIGH]

### Pattern 5: Detector registry returns candidates, never a guess

Each adapter exposes a pure `probe(path, prefix_bytes)` and bounded `detect(files)` result. The registry partitions files by an exact layout identity: format plus repository side plus language/path convention. A candidate is confirmable only when confidence is exactly 1.0 and it has at least one sample, an unambiguous locale, valid encoding/grammar and zero unsupported/limit diagnostics. Multiple candidates remain separate; overlapping claims for one file or two valid interpretations of a layout are blocking ambiguity. [RECOMMENDED: exact fail-closed algorithm; confidence HIGH]

### Anti-Patterns to Avoid

- **Route-level business transactions:** they fork CLI/worker behavior. Routes should validate transport, call one service and map domain conflicts.
- **Counting admins without a global serialization lock:** two target-row locks can each observe another admin and both commit removal.
- **Mutable active revision rows:** candidate preview failure can leak into live configuration.
- **OAuth scopes supplied only on the authorization URL:** Bitbucket consumer permissions are static and an individual grant request does not provide optional scope narrowing. [CITED: https://support.atlassian.com/bitbucket-cloud/docs/use-oauth-on-bitbucket-cloud/]
- **Trusting provider `next`:** validate scheme/host/path and never expose the full provider URL as the application's cursor.
- **Blind recursive download:** source browse must stop on every A-03 budget.
- **Regex-only `.strings` or XML parsing:** escaping, comments, entities and malformed input defeat regex recognizers.
- **Treating samples as imports:** preview output is partial, immutable and noncanonical.
- **Holding plaintext secrets for idempotent replay:** a timed-out reset should be repeated to generate a fresh secret; never persist plaintext to replay the earlier response.

## Bitbucket OAuth Capability and Reauthorization Matrix

Bitbucket describes `repository` as repository/source read authority; `repository:write` implies `repository`; `pullrequest` implies `repository`; and `pullrequest:write` implies both `pullrequest` and `repository:write`. [CITED: https://developer.atlassian.com/cloud/bitbucket/bitbucket-cloud-rest-api-scopes/]

| Capability/profile | Consumer scopes configured | Phase | Boundary |
|--------------------|----------------------------|-------|----------|
| Connect, metadata, branches, source preview | exactly `{repository}` | 2 | allowed now; reject any token whose effective live scope set differs |
| Import-grade reads/baselines | exactly `{repository}` | 3 | same read profile; no new authorization solely for these reads |
| Source branch/file/commit writes | exactly `{repository:write}` | 7 | explicit consumer permission change and fresh authorization; implied read need not be separately requested |
| Pull-request read/create/update | exactly `{pullrequest:write}` | 8 | explicit consumer permission change and fresh authorization; implied PR read/repository write/read need not be separately requested |

Never request `account`, `email`, `project`, `admin`, `webhook`, `issue`, `wiki`, both an implied scope and its parent, or any future scope during Phase 2. [RECOMMENDED: least-privilege profile derived from official implications; confidence HIGH]

Validate the token response `scope` when present and a harmless live response's `x-oauth-scopes` header; the support documentation shows the latter as the effective-scope inspection point. [CITED: https://support.atlassian.com/bitbucket-cloud/kb/how-to-fetch-the-scope-of-a-token-via-command-line/] Do not hardcode an access-token lifetime: current Atlassian pages disagree, while OAuth token responses carry `expires_in`; persist the received value and refresh early using a bounded skew. [CITED: https://developer.atlassian.com/cloud/bitbucket/rest/] [CITED: https://support.atlassian.com/bitbucket-cloud/docs/use-oauth-on-bitbucket-cloud/]

Later scope expansion cannot silently upgrade the existing read token because the consumer permission set is static and old credentials were granted under the former profile. Deployment must deliberately change the consumer, mark the connection `reauthorization_required`, and complete a fresh authorization before enabling new capability. [RECOMMENDED: explicit costly boundary; confidence HIGH]

Research did not establish an official Bitbucket Cloud provider token-revocation endpoint. [ASSUMED] Therefore Phase 2's guaranteed revoke contract is local and immediate: under the connection lock, advance generation, delete encrypted credential blobs, mark revoked, and make all provider adapters reject the old generation. Do not claim provider-side revocation until an official endpoint is verified. [RECOMMENDED: fail-closed local revocation; confidence MEDIUM]

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | custom KDF/salt format | existing pwdlib `PasswordHash.recommended()` | preserves Phase 1 authentication compatibility |
| Token encryption/key rotation | custom cipher or bare AES | cryptography MultiFernet | authenticated encryption and ordered key rotation are provided |
| Hostile XML | raw external entity-capable parser | defusedxml | Python's own guidance points to hardened parsing |
| Provider HTTP | raw sockets/custom pool/retry | HTTPX Client with explicit four-way timeouts and streaming | centralizes bounded I/O and redaction |
| Concurrency | process mutex or check-then-write | PostgreSQL constraints, advisory/row locks and version counters | works across API/worker processes |
| JSON grammar | regex or permissive JS assumptions | Python `json` with duplicate/non-finite hooks | exact fail-closed shape checks |
| Job API | expose Celery `AsyncResult` | durable PostgreSQL job/result rows | preserves stable public state across broker/result expiry |
| Pagination | construct `page=N` URLs | follow validated opaque `next` and issue an app cursor | matches provider guarantees |

**Key insight:** the only purposely custom parser is a bounded read-only `.strings` lexer because the phase needs a detector, not a serializer. It must be driven by supported/unsupported golden preview fixtures and may not be reused as the later write-back implementation. [RECOMMENDED: narrow exception; confidence HIGH]

## API and Transaction Contract

Use additive resources below the existing `"/api/v1"` prefix. That prefix is an exact current setting. [VERIFIED: `backend/src/verboflex/config.py:18-42`] Exact path spelling remains planner discretion, but plan one resource family for users, products/revisions, repositories/mappings, the singleton Bitbucket connection, branches, preview jobs and confirmation/publication. [RECOMMENDED: resource-oriented API; confidence HIGH]

Transport rules: [RECOMMENDED: testable API contract; confidence HIGH]

- Return `401` for absent/invalid internal bearer authority and `403` for an authenticated non-admin; reuse the current bounded details `"Invalid access token"` and `"Insufficient permissions"` rather than inventing resource-specific leaks. [VERIFIED: `backend/src/verboflex/auth/principal.py:25-31`; `backend/src/verboflex/auth/principal.py:104-142`]
- Return `201` for resource creation, `202` for preview enqueue, `204` only when there is intentionally no response body, `409` for normalized uniqueness/stale version/publication conflicts, and FastAPI/Pydantic `422` for malformed request shape. FastAPI exposes response status and response-model filtering in OpenAPI. [CITED: https://fastapi.tiangolo.com/tutorial/response-status-code/] [CITED: https://fastapi.tiangolo.com/tutorial/response-model/]
- Lists use default 50/max 100 and opaque cursors over a stable sort key plus UUID. Users sort normalized email then UUID; products sort `name_key` then UUID; repositories sort optional descriptive key fallback then workspace/slug/UUID; preview output uses path/language/key code-point order. [RECOMMENDED: deterministic pagination; confidence HIGH]
- Create/reset/reactivate responses containing a temporary password set `Cache-Control: no-store`; list/detail/OpenAPI examples never have a temporary-password field. A repeat reset/reactivation intentionally generates a fresh secret and invalidates the former one; do not persist plaintext for retry replay. [RECOMMENDED: one-time secret boundary; confidence HIGH]
- Candidate edits are versioned `PUT`/`PATCH` operations; publish is intrinsically idempotent by candidate UUID/version; preview is idempotent by input digest; OAuth callback is single-use by state; revoke is a state-setting action. [RECOMMENDED: operation-specific idempotency; confidence HIGH]
- Branch names are opaque provider values and must not be case-folded. Repository `workspace` and `repository_slug` are ASCII-trimmed/lowercased and must have a composite database unique constraint, as locked in the SPEC. [LOCKED: `02-SPEC.md:106-116`]

### Concurrency decision table

| Race | Serialization / compare condition | Required observable result |
|------|-----------------------------------|----------------------------|
| Two removals/deactivations of the final admins | global admin-authority advisory xact lock, then target row lock and prospective active-admin count | at most one succeeds; the other gets `409`; at least one active admin remains |
| Two mutations of one user's authority/password | same global lock + target `FOR UPDATE` | commits serialize; only final committed hash/lifecycle/token version is valid; all earlier sessions revoked |
| Two equal repository creations | composite unique constraint on normalized workspace/slug | one `201`, one bounded `409`, one row |
| Two candidate edits | revision version compare | one version advances; stale writer gets `409` with recoverable client form |
| Two publishes | Product `FOR UPDATE` + candidate UUID/version/digest compare | one pointer swap; equal retry is a no-op; different stale candidate gets `409` |
| Preview completes after candidate edit | conditional result update on candidate UUID/version/input digest | stale job remains inspectable but cannot confirm or replace current status |
| Refresh versus reconnect/revoke | singleton connection lock + generation compare | one generation wins; old decrypted/refreshed material is discarded and unusable |

If serializable transactions are later chosen for a multi-row operation, PostgreSQL may abort with serialization failure `SQLSTATE 40001`; retry the **whole** transaction with a bounded attempt count, never a fragment. [CITED: https://www.postgresql.org/docs/current/transaction-iso.html] The planned operations above need explicit locks/version predicates and do not require making the whole application serializable. [RECOMMENDED: narrower locking scope; confidence HIGH]

## Common Pitfalls and Risk Register

### Pitfall 1: The last-admin check races
**What goes wrong:** two admins each deactivate the other after both count two active admins.  
**Why:** locking only each target row does not serialize a global invariant.  
**Avoid:** one transaction advisory lock for every authority-set mutation, then target locks and a prospective count; add a two-thread PostgreSQL test. [RECOMMENDED: concurrency control; confidence HIGH]

### Pitfall 2: Candidate relations mutate live configuration
**What goes wrong:** mappings are shared between active/candidate revisions or an ORM cascade edits the published row.  
**Avoid:** revision-owned mappings with immutable published rows; publication changes one pointer only; negative tests snapshot the active graph before every candidate failure. [RECOMMENDED: data model invariant; confidence HIGH]

### Pitfall 3: OAuth scope or token behavior is assumed
**What goes wrong:** a statically over-scoped consumer makes every Phase 2 token over-privileged, or a hardcoded lifetime conflicts with provider response.  
**Avoid:** exact consumer scope profile, live header validation, `expires_in`, explicit reauthorization and tests for extra/missing scope. [CITED: https://support.atlassian.com/bitbucket-cloud/docs/use-oauth-on-bitbucket-cloud/] [CITED: https://support.atlassian.com/bitbucket-cloud/kb/how-to-fetch-the-scope-of-a-token-via-command-line/]

### Pitfall 4: Refresh-token rotation loses the usable token
**What goes wrong:** concurrent refreshes both use one rotating refresh token and the losing commit overwrites the winner.  
**Avoid:** serialize the singleton generation, replace access and refresh together, reject stale generation, and make revoke win immediately. Current Bitbucket documentation states refresh tokens rotate. [CITED: https://developer.atlassian.com/cloud/bitbucket/rest/]

### Pitfall 5: Pagination becomes an SSRF or unbounded scan
**What goes wrong:** application follows an attacker/provider-controlled `next`, redirect or enormous tree.  
**Avoid:** exact host/scheme allowlist, zero redirects, opaque `next`, streaming byte count and every A-03 ceiling. [RECOMMENDED: provider trust boundary; confidence HIGH]

### Pitfall 6: Detector confidence disguises unsupported content
**What goes wrong:** a numeric heuristic above a loose threshold accepts mixed JSON, plural XML or ambiguous locale layout.  
**Avoid:** confidence 1.0 is a proof predicate, not a probability; any unsupported feature or competing interpretation makes the result non-confirmable. [RECOMMENDED: fail-closed semantics; confidence HIGH]

### Pitfall 7: Secret leaks through schemas, logs, exceptions or client generation
**What goes wrong:** adding token fields to a SQLAlchemy/Pydantic projection puts them into OpenAPI and browser types; HTTP client debug logging captures headers/bodies.  
**Avoid:** separate encrypted persistence model from bounded status response, explicit redaction, no token-bearing exception text, `Cache-Control: no-store`, captured-log tests and OpenAPI/browser/persistence negative scans. [RECOMMENDED: secret boundary; confidence HIGH]

### Pitfall 8: Phase 2 adapters become canonical parsers
**What goes wrong:** preview locators/results are treated as stable translation identities or serializers, making Phase 4/7 depend on incomplete grammar.  
**Avoid:** package preview modules separately, expose bounded samples only, prohibit canonical/import/write models in their dependency graph, and add a provider write spy. [LOCKED: `02-SPEC.md:79-104`]

### Dependency and implementation risks

| Risk | Likelihood / impact | Planning mitigation |
|------|---------------------|---------------------|
| New runtime packages fail the legitimacy gate | medium / high | required human checkpoints before `httpx`, `defusedxml`, `cryptography` changes |
| Python 3.14 compatibility of parser/crypto wheels | low-medium / high | install in locked uv environment and run Linux container smoke before implementation slice |
| Bitbucket docs/lifetime behavior changes | medium / medium | persist token response fields, mock exact contracts, manual local OAuth smoke, no lifetime constant |
| Huge/hostile repositories | high / high | A-03 caps are validation behavior, not tuning knobs; property/boundary tests |
| Migration downgrade/cascade error | medium / high | RED schema introspection tests, upgrade/downgrade/upgrade against disposable Postgres |
| Frontend/backend client drift | medium / medium | canonical OpenAPI export + generated client check in every stable API wave |

## Code Examples

These are implementation sketches for the planner; proposed new names/values are the recommended contracts above, not existing repository definitions.

### Product-name canonicalization

```python
# Sources: Python unicodedata and Unicode HOWTO
import unicodedata

def normalize_product_name(raw: str) -> tuple[str, str]:
    compatibility = unicodedata.normalize("NFKC", raw)
    display = " ".join(compatibility.split())
    if not 1 <= len(display) <= 120:
        raise ValueError("product name must contain 1 to 120 characters")
    if "\x00" in display or not display.isprintable():
        raise ValueError("product name contains unsupported characters")
    return display, display.casefold()
```

`str.split()` without an explicit separator applies Unicode whitespace runs, which implements the chosen contract. [CITED: https://docs.python.org/3/library/stdtypes.html] Test the algorithm with the exact A-01 table; do not rely on the database collation to reproduce it. [RECOMMENDED: application-generated unique key; confidence HIGH]

### Last-active-admin serialization

```python
# Source pattern: existing backend/src/verboflex/cli.py:69-90
with session.begin():
    session.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})
    target = session.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one()
    actor = session.execute(select(User).where(User.id == actor_id).with_for_update()).scalar_one()
    validate_self_admin_rule(actor, target, requested_roles)
    validate_nonempty_roles(requested_roles)
    validate_prospective_active_admin_count(session, target, requested_roles, requested_active)
    apply_authority_change_and_revoke_sessions(session, target)
```

The existing repository has the exact advisory lock and `with_for_update()` transaction pattern quoted earlier. PostgreSQL transaction advisory locks release automatically at transaction end. [CITED: https://www.postgresql.org/docs/current/explicit-locking.html]

### Strict duplicate-aware JSON

```python
import json

def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object name")
        result[key] = value
    return result

value = json.loads(
    decoded_utf8,
    object_pairs_hook=unique_object,
    parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"unsupported {token}")),
)
```

Python documents `object_pairs_hook` and `parse_constant`; the shape validator still must reject all values outside the A-02 matrix. [CITED: https://docs.python.org/3/library/json.html]

### Atomic publish predicate

```python
with session.begin():
    product = session.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    ).scalar_one()
    if product.active_revision_id == candidate_id:
        return product
    candidate = require_current_candidate(product, candidate_id, expected_version)
    require_all_mappings_current_confirmed(session, candidate, expected_preview_digests)
    product.active_revision_id = candidate.id
    product.candidate_revision_id = None
```

All validation occurs after the Product lock and before pointer mutation. The service must not catch an exception and commit partial state. [RECOMMENDED: atomic publication; confidence HIGH]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest `9.1.1`, Hypothesis `6.165.10`, pytest-cov, mutmut; exact pins are in `backend/pyproject.toml` [VERIFIED: `backend/pyproject.toml:29-43`] |
| Frontend framework | Vitest `4.1.11`, Testing Library, fast-check `4.9.0`, Playwright `1.62.1`, Stryker `10.0.0` [VERIFIED: `frontend/package.json:35-62`] |
| Backend quick command | `cd backend && uv run pytest -q <focused-node-id> -x` |
| Backend full command | `cd backend && uv run pytest -q` |
| Frontend quick command | `cd frontend && npm test -- --run <focused-test-file>` |
| Frontend full command | `cd frontend && npm test -- --run && npm run typecheck && npm run build` |
| E2E | `cd frontend && npm run e2e`; existing configuration uses one worker, a 60-second timeout and base URL `http://localhost:8080` [VERIFIED: `frontend/playwright.config.ts:3-17`] |

### Required RED→GREEN slices

Every numbered API behavior starts with one focused failing test, records the RED command/output, adds minimum implementation, records the same GREEN command, then refactors while green. Do not bundle all schema/models/routes before the first observable API behavior. [LOCKED: `02-SPEC.md:106-118`]

1. **Migration skeleton and A-01:** failing product-name examples/unique race and schema introspection, then models/migration/normalizer.
2. **Admin guard and user list/create:** first `401/403/no mutation`, then deterministic list, duplicate email, generated one-time credential.
3. **User authority mutations:** roles/nonempty/self-admin, then two-thread last-admin race, reset/deactivate/reactivate and rollback/log/persistence negatives.
4. **Repository + candidate revision:** registry uniqueness/reuse isolation, topology/branch/target constraints, version conflict, fixed grouping property.
5. **Atomic publication core:** empty/unconfirmed/stale failure snapshots, one-winner concurrency and idempotent equal retry before provider work.
6. **OAuth boundary:** state replay/binding/TTL, exact scope, encrypted persistence/schema/log negatives, reconnect/revoke/refresh-generation races.
7. **Provider adapter:** branch pagination/opaque-next/host redirect denial and every count/byte/time boundary.
8. **Detectors:** for each format, supported fixture RED→GREEN, then malformed/unsupported/ambiguous/encoding boundary; JSON properties and XML/iOS adversarial fixtures.
9. **Preview job + confirmation:** stable identity, stale completion, deterministic bounded sampling, timeout/polling, digest confirmation and publication integration.
10. **Generated client and UI:** admin navigation/guards, wizard states, password reveal, polling/retry, accessible validation/stale form preservation, then Playwright smoke.

### Phase Requirements → Test Map

| Req ID(s) | Behavior | Test type / focused target | File exists? |
|-----------|----------|----------------------------|--------------|
| AUTH-02, AUTH-03 | admin guard, lifecycle, roles, one-time secret, last-admin race | unit + API + PostgreSQL concurrency `tests/unit/services/test_admin_users.py`, `tests/api/test_admin_users.py`, `tests/integration/test_admin_user_concurrency.py` | Wave 0 |
| PROD-01 | A-01, candidate isolation/version/publication/deactivation | unit + migration + integration `tests/unit/test_product_names.py`, `tests/integration/test_product_publication.py` | Wave 0 |
| PROD-02–07, PROD-09 | repository uniqueness/reuse, mapping topology/format/branches/grouping | schema/service/property/integration `tests/unit/services/test_mappings.py`, `tests/integration/test_repository_registry.py` | Wave 0 |
| BITB-01 | OAuth state/scope/encryption/rotation/revoke/redaction | unit + provider-mock + integration `tests/integration/test_bitbucket_oauth.py` | Wave 0 |
| BITB-03, BITB-04 | paginated branches and bounded read-only source | provider-mock/boundary `tests/integration/test_bitbucket_client.py` | Wave 0 |
| PROD-08, PROD-09 | four detector matrices and A-02/A-03 | golden preview fixtures + unit/property `tests/unit/localization/preview/` | Wave 0 |
| PROD-08 | durable jobs, deterministic samples, stale completion/confirmation | worker integration `tests/integration/test_preview_jobs.py` | Wave 0 |
| UI-03 | wizard, status/error/conflict, responsive nav, password reveal/polling | Vitest + Playwright `frontend/src/features/admin/**/*.test.tsx`, `frontend/e2e/admin-configuration.spec.ts` | Wave 0 |

All paths in the final column are recommended new test locations; Wave 0 must create them. The current migration suite already expects disposable PostgreSQL and exercises upgrade/downgrade behavior, so extend that harness rather than replacing it. [VERIFIED: `backend/tests/integration/test_migrations.py:18-180`]

### Property, mutation and negative controls

- Hypothesis: product normalization is idempotent; JSON output order is stable; grouping depends only on exact repository/target; source scan never crosses any ceiling; arbitrary invalid bytes never yield confirmable results. [RECOMMENDED: property coverage; confidence HIGH]
- PostgreSQL concurrency: use two independent sessions/threads, matching the existing exact `ThreadPoolExecutor(max_workers=2)` pattern. [VERIFIED: `backend/tests/integration/test_refresh_concurrency.py:29-51`]
- Extend mutmut beyond the current auth-only scope to admin-user invariants, name normalization, publication predicates, scope validation, bounds and detectors. The current mutation scope is explicitly auth-focused. [VERIFIED: `backend/pyproject.toml:73-101`]
- Extend Stryker beyond the current auth-session mutation target to admin polling/error/state reducers. [VERIFIED: `frontend/stryker.config.mjs:4-23`]
- Negative scans: API schema/response/browser/log/persistence contain no temporary password beyond the successful mutation response and no provider tokens ever; provider spy records zero write/branch/commit/PR calls; active-revision snapshots are identical after every failed candidate operation. [RECOMMENDED: prohibition evidence; confidence HIGH]

### Sampling and smoke gates

- **Per task commit:** focused backend or frontend test that supplied RED→GREEN evidence.
- **Per wave merge:** full relevant suite, coverage and generated-client drift check.
- **Phase gate:** full backend/frontend suites; 100% configured backend coverage; targeted mutations; Ruff/mypy/lint/typecheck/build; Alembic upgrade→downgrade→upgrade against disposable PostgreSQL; Docker Compose API/Postgres/Redis/Celery worker health; enqueue/complete one preview against an HTTP mock; canonical OpenAPI export/client generation/check; Playwright desktop/mobile admin smoke; secret scan, dependency audit, code review and deploy smoke. The backend currently configures coverage failure at 100 and strict mypy. [VERIFIED: `backend/pyproject.toml:45-68`]
- A real Bitbucket organization credential is not required in CI. Provider mocks are the automated gate; one human local OAuth connect/preview/revoke smoke is release evidence when disposable credentials are available. [RECOMMENDED: safe external-service gate; confidence HIGH]

### Wave 0 gaps

- [ ] Add the recommended backend test modules/fixtures and provider HTTP mock.
- [ ] Add supported/unsupported/ambiguous/encoding fixtures for each of four formats.
- [ ] Add generated OpenAPI/client schema cases for every admin resource and secret-negative assertion.
- [ ] Expand mutmut/Stryker targets only as implementation modules land.
- [ ] Insert package-legitimacy human checkpoints before direct dependency changes.

## Security Domain

The project uses ASVS 5.0.0 as the current stable baseline. Its current chapters place validation/business logic in V2, file handling in V5, authentication in V6, session management in V7, authorization in V8, OAuth in V10, cryptography in V11, and logging/error handling in V16. [CITED: https://owasp.org/www-project-application-security-verification-standard/]

| ASVS 5 category | Applies | Phase 2 control |
|-----------------|---------|-----------------|
| V2 Validation and Business Logic | yes | Pydantic plus domain invariants, exact A-01/A-02/A-03 rejection, atomic publication |
| V5 File Handling | yes | read-only streaming caps, strict decoders, hardened XML, no archive/decompression |
| V6 Authentication | yes | reuse Phase 1 bearer/password authority; generated password is policy-compliant and one-time |
| V7 Session Management | yes | token-version advance and session revocation in the authority transaction |
| V8 Authorization | yes | `require_roles(admin)` on every admin route; callback authority comes only from consumed bound state |
| V10 OAuth | yes | exact redirect/state, backend-only exchange, least privilege, rotation generation and explicit reauthorization |
| V11 Cryptography | yes | MultiFernet keys in deployment secrets; no custom cipher; key rotation smoke |
| V16 Logging and Error Handling | yes | bounded errors, no secrets/URLs with credentials, captured-log assertions |

| Threat pattern | STRIDE | Mitigation |
|----------------|--------|------------|
| Non-admin invokes hidden admin API | Elevation of privilege | database-loaded admin dependency on router/resource and no frontend authority |
| Concurrent removal of final admins | Tampering/DoS | global authority transaction lock + prospective invariant |
| OAuth login CSRF/replay | Spoofing | 32-byte state, digest-only Redis record, admin/session/generation binding, 10-minute TTL, atomic consume |
| Provider token disclosure | Information disclosure | authenticated encryption, response-schema separation, log/OpenAPI/browser negative scans |
| Malicious pagination/redirect/path | SSRF/tampering | exact scheme/host allowlist, no redirects, bounded normalized provider paths |
| XML entity expansion / oversized source | DoS/information disclosure | defusedxml, reject DTD/entities, byte/count/depth/time ceilings |
| Stale preview publishes wrong source | Tampering | commit/revision/layout/generation digest and atomic all-mapping compare-and-publish |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| uv | locked Python environment/tests | yes | 0.11.12 | none needed |
| project Python via `uv run` | backend | yes | 3.14.7 | containerized project runtime |
| system Python | incidental only | yes, not suitable | 3.9.6 | use `uv run`, never system Python |
| Node.js / npm | frontend | yes | 24.15.0 / 11.16.0 | project container |
| Docker / Compose / daemon | Postgres, Redis, worker smoke | yes | 29.7.2 / 5.3.1 / 29.7.2 | none needed |
| PostgreSQL CLI (`psql`) | manual database inspection | no | — | disposable Docker Postgres and Python migration harness |
| Redis CLI | manual broker inspection | no | — | Docker health checks / Python Redis client |
| gitleaks | optional local secret scan | no | — | existing detect-secrets; CI may install gitleaks |

These values were probed locally on 2026-08-26. [VERIFIED: `command -v`, version commands, `uv run python`, and Docker daemon probe] Missing host CLIs do not block implementation because the project runs stateful services through Docker. [RECOMMENDED: environment disposition; confidence HIGH]

## What Stays Out of Phase 2

- Canonical translation rows, stable translation identity, durable import/source baselines and actionable import resilience remain Phases 3–4. [LOCKED: `02-SPEC.md:79-104`]
- Full plural/array/markup/variant grammar, canonical locators and format-preserving serialization remain Phase 4/7; Phase 2 reports such constructs as unsupported. [LOCKED: `02-CONTEXT.md:47-55`; `02-CONTEXT.md:151-156`]
- Provider writes, branches, commits, PR creation/update and PR-job idempotency remain Phases 7–8. [LOCKED: `02-SPEC.md:93-101`]
- Translation search/edit/review/comments/constraints are Phases 5–6; audit history PLAT-07 remains Phase 9. [LOCKED: `02-SPEC.md:95-102`]
- Multiple Bitbucket connections, Bitbucket Server/Data Center, Microsoft Entra ID/OIDC, Figma and advanced localization suite features remain deferred. [LOCKED: `02-SPEC.md:79-104`]

## State of the Art

| Old/unsafe approach | Current Phase 2 approach | Impact |
|---------------------|--------------------------|--------|
| Phase 1 CLI-only authority code copied into routes | extracted transactional service reused by CLI and API | one invariant implementation and test surface |
| mutable product configuration | immutable active + optimistic candidate + atomic pointer publication | preview/save failure cannot alter live behavior |
| future scopes requested early | exact read-only consumer profile and explicit reauthorization | least privilege and auditable capability boundary |
| synchronous recursive preview | durable bounded Celery job and polling | predictable HTTP latency and stale-result control |
| heuristic parser acceptance | strict encoding/shape matrices and confidence exactly 1.0 | ambiguity and unsupported content fail closed |
| raw Celery/backend provider status in SPA | bounded PostgreSQL job/connection projections | stable API without provider secrets |

Bitbucket's REST introduction now directs Bearer calls to `https://api.bitbucket.org`; access token duration should be derived from the response because current Atlassian pages are inconsistent. [CITED: https://developer.atlassian.com/cloud/bitbucket/rest/] This is a temporal integration point and should be rechecked when execution begins. [RECOMMENDED: seven-day freshness for provider docs; confidence MEDIUM]

## Assumptions Log

All residual SPEC assumptions A-01, A-02 and A-03 are resolved above as explicit recommended contracts. No unresolved product decision remains. The following implementation assumptions are intentionally visible:

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | [ASSUMED] Deployment can supply at least two Fernet-compatible keys during a rotation window. | OAuth architecture | without an old+new overlap, existing encrypted tokens require reconnect rather than online rotation |
| A2 | [ASSUMED] The product accepts the deliberately narrow locale subset and does not require BCP 47 variants/extensions in preview. | A-02 | valid repositories using variants such as extension tags will fail closed until contract expansion |
| A3 | [ASSUMED] A 20 MiB/500-file/60-second preview budget covers normal configured repositories. | A-03 | larger repositories block activation and require a later explicit limit change, not silent truncation |
| A4 | [ASSUMED] Local credential invalidation satisfies v1's independently revocable connection even though provider-side OAuth token revocation was not verified. | OAuth matrix | a revoked credential might remain usable outside VerboFlex until provider expiry/revocation |

These assumptions do not block planning because each fails closed and has an explicit test/operational outcome. A1 and A3 should be confirmed during deployment smoke; A2 should be revisited only with a concrete repository fixture; A4 must be stated in admin/release documentation. [RECOMMENDED: planning disposition; confidence HIGH]

## Open Questions (RESOLVED)

1. **Does the production Bitbucket OAuth consumer already exist with exactly `repository` permission and the exact callback URI?**
   - **Disposition: RESOLVED** — the final quality/live-smoke plan contains a blocking human checkpoint for the production consumer, exact callback URI, and exact `repository` scope; provider mocks remain the automated gate.
   - Known: the required Phase 2 profile is exact and static. [CITED: https://support.atlassian.com/bitbucket-cloud/docs/use-oauth-on-bitbucket-cloud/]
   - Recommendation: planner adds a human configuration checkpoint before live OAuth smoke; automated implementation continues with provider mocks.
2. **What measured repositories establish whether A-03 budgets need later adjustment?**
   - **Disposition: RESOLVED** — the fixed A-03 safe defaults ship now; representative-repository evidence is a manual observation, and any limit change requires an explicit reviewed contract update.
   - Known: no Phase 2 repository corpus was supplied.
   - Recommendation: ship exact safe defaults; log only bounded counts/durations (never file contents/tokens), then change limits through an explicit reviewed contract if real fixtures fail.
3. **Provider-side OAuth revocation endpoint?**
   - **Disposition: RESOLVED** — Phase 2 guarantees immediate local generation revoke; provider-side revoke remains an explicit `COVERAGE.md` opt-out until an official endpoint is verified.
   - Known: no official endpoint was verified.
   - Recommendation: guarantee local generation revoke now and open a Phase 3 provider-capability follow-up only if an authoritative endpoint is found.

## Sources

### Repository evidence (HIGH confidence)
- `AGENTS.md` — locked project stack, architecture, formats, security/testing boundaries.
- `backend/pyproject.toml` and `frontend/package.json` — exact dependency and quality-tool values.
- `backend/src/verboflex/auth/principal.py`, `auth/passwords.py`, `cli.py`, and user/role/session models — existing authority, role, password and transaction patterns.
- `backend/tests/integration/test_migrations.py` and `test_refresh_concurrency.py` — disposable Postgres and two-session race harnesses.
- `frontend/src/router.tsx`, `components/layout/AppShell.tsx`, `features/auth/session.tsx`, Playwright/Vitest/Stryker configs — frontend integration and validation patterns.

### Official primary documentation (MEDIUM confidence, current external behavior)
- https://developer.atlassian.com/cloud/bitbucket/rest/ — OAuth/token and REST endpoint behavior.
- https://developer.atlassian.com/cloud/bitbucket/bitbucket-cloud-rest-api-scopes/ — scope implications.
- https://developer.atlassian.com/cloud/bitbucket/rest/intro/ — pagination contract.
- https://developer.atlassian.com/cloud/bitbucket/rest/api-group-refs/ — branch reads.
- https://developer.atlassian.com/cloud/bitbucket/rest/api-group-source/ — source browse/read.
- https://support.atlassian.com/bitbucket-cloud/docs/use-oauth-on-bitbucket-cloud/ — static OAuth consumer permissions.
- https://www.rfc-editor.org/rfc/rfc9700 and https://www.rfc-editor.org/rfc/rfc6749 — OAuth security/protocol.
- https://fastapi.tiangolo.com/tutorial/dependencies/ and `/response-model/` — API authorization/schema patterns.
- https://docs.sqlalchemy.org/en/20/orm/versioning.html and PostgreSQL locking/isolation docs — concurrency mechanisms.
- https://docs.celeryq.dev/en/stable/userguide/tasks.html — task state/retry/limits.
- https://developer.android.com/guide/topics/resources/string-resource — Android resource shapes.
- https://doc.qt.io/qt-6/linguist-ts-file-format.html — Qt TS schema.
- Apple String Resources and String Programming Guide — `.strings` grammar/encoding.
- https://www.rfc-editor.org/rfc/rfc8259 — JSON encoding/interoperability.
- Python Unicode, JSON and XML security docs; HTTPX timeout docs; cryptography Fernet docs; OWASP ASVS 5 project page.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH for existing pins; MEDIUM for three new/promoted packages pending required legitimacy checkpoints.
- Architecture: HIGH because it follows locked Phase 2 decisions and opened repository authority/concurrency patterns.
- A-01/A-02/A-03: HIGH as falsifiable recommended contracts; A-03 production fit remains an explicit assumption.
- Bitbucket behavior: MEDIUM because claims use current official pages but provider behavior is temporally unstable and current token-lifetime pages conflict.
- Pitfalls/security: HIGH for transactional and repository boundaries; MEDIUM for provider-side revocation absence.

**Research date:** 2026-08-26  
**Valid until:** 2026-09-02 for Bitbucket OAuth/API claims; 2026-09-25 for stable framework/repository patterns.
