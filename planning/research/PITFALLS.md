# Pitfalls Research

**Domain:** Bitbucket-backed localization review and approval portal
**Researched:** 2026-05-04
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Losing File Semantics During Write-Back

**What goes wrong:**
The platform parses localization files and writes them back with changed ordering, dropped comments, altered escaping, changed encoding, or malformed platform-specific structures.

**Why it happens:**
Developers normalize everything into generic key/value objects and serialize from scratch.

**How to avoid:**
Use format-specific adapters with golden before/after fixtures. Prefer minimal text edits where possible. Add fixtures for comments, escaping, arrays/plurals, Qt numerus variants, `.strings` comments, and nested JSON.

**Warning signs:**
Simple edits produce large diffs; comments disappear; Android apostrophes or format placeholders change; `.strings` files lose comments; Qt translation types are removed.

**Phase to address:**
Parser/writer foundation before Bitbucket PR write-back.

---

### Pitfall 2: Treating Repository Mapping as Discoverable

**What goes wrong:**
The app guesses relationships between product repositories, key repositories, and translation repositories, then imports or writes to the wrong place.

**Why it happens:**
Cross-repo localization structures are product-specific and often undocumented in code.

**How to avoid:**
Make mapping explicit in admin UI. Include a validation preview showing keys, languages, files, sample translations, source branch, and target write location before enabling imports.

**Warning signs:**
Admin setup has implicit defaults; products with separate key/translation repos need code changes; imported strings have missing source text or wrong language.

**Phase to address:**
Product and repository configuration phase.

---

### Pitfall 3: Stale Branch and Conflict Blindness

**What goes wrong:**
The portal writes changes based on an old import while the target branch has moved, causing conflicts, overwritten translations, or PRs with unexpected diffs.

**Why it happens:**
The platform stores translation values but not the source commit/file snapshot used during review.

**How to avoid:**
Store import commit hashes and raw file snapshots. Before writing, compare current branch head/file hash against the imported baseline. Require refresh or conflict resolution if stale.

**Warning signs:**
PR diffs include unrelated changes; reviewers see changes they did not make; PR creation succeeds but CI fails due malformed or outdated files.

**Phase to address:**
Change-set and PR phase.

---

### Pitfall 4: Under-Scoped Bitbucket Permissions

**What goes wrong:**
Imports work but commits or PRs fail in production because tokens have read access but not repository write or pull request write permissions.

**Why it happens:**
Bitbucket Cloud separates repository write permissions from pull request write permissions.

**How to avoid:**
Validate token scopes during setup. Surface capability checks in admin UI: read files, create branch, commit to branch, open PR. Store failures with actionable messages.

**Warning signs:**
Setup only tests repository listing; PR creation fails after translations are already reviewed; errors are generic 401/403 messages.

**Phase to address:**
Bitbucket integration phase.

---

### Pitfall 5: Review Comments Detached From Translation History

**What goes wrong:**
Comments are stored only in PRs or raw files, so reviewers lose context across imports, branches, and future edits.

**Why it happens:**
The PR is mistaken for the primary review workspace.

**How to avoid:**
Store comments in the application against canonical translation IDs plus product/language/key/file context. Optionally include a change-set summary in the PR description.

**Warning signs:**
Users cannot see prior discussion before PR creation; comments disappear after a new import; rejected translations have no durable rationale.

**Phase to address:**
Review and comments phase.

---

### Pitfall 6: Search That Mirrors Repository Structure

**What goes wrong:**
The UI exposes files and directories instead of the product manager's mental model.

**Why it happens:**
The implementation starts from Bitbucket tree navigation instead of canonical translation search.

**How to avoid:**
Index product, language, key, source text, translated text, state, and constraint violation status. Repository path should be visible as context, not the primary navigation.

**Warning signs:**
Users must know file paths; language filtering is slow; finding a string requires opening several repositories.

**Phase to address:**
Search/review UI phase.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store only current translation text | Faster data model | Cannot detect stale imports or audit changes. | Never for PR write-back. |
| One table for all config JSON blobs | Fast admin setup | Hard to validate mappings and query impact. | Only for format-specific advanced options. |
| One parser for XML-like formats | Less code | Android and Qt semantics diverge. | Only for shared low-level XML parsing, not adapter logic. |
| No Celery/background jobs | Simpler app | Long requests, retries impossible, poor PR status UX. | Local prototype only. |
| No golden fixtures | Faster parser work | Format regressions undetected. | Never for supported formats. |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Bitbucket Cloud auth | Using a token that can read repos but cannot create PRs. | Check repository read/write and pull request write capabilities separately. |
| Bitbucket branches | Creating commits directly on target branch. | Create/update a source branch, then open PR to target branch. |
| Bitbucket source API | Assuming raw file reads include encoding metadata. | Store content bytes/text carefully; do not assume Bitbucket recodes files. |
| Android XML | Ignoring arrays, plurals, formatting placeholders, and escaping. | Support v1 scope explicitly and preserve unsupported nodes safely. |
| Qt TS | Dropping `type`, `numerus`, location, comments, or variants. | Preserve message metadata even if v1 edits only simple translations. |
| iOS `.strings` | Parsing as naive `"key" = "value"` lines. | Preserve comments, escaping, UTF-8, duplicate-key handling, and table names. |
| JSON | Ignoring duplicate keys/order/formatting. | Use location-aware edits; decide policy for duplicate keys during import. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full repo scan on every search | Slow searches and API rate pressure. | Import to Postgres and search local canonical data. | As soon as products have multiple repos/languages. |
| Re-import everything on every run | Long import jobs and noisy updates. | Track branch head, file hashes, and incremental import status. | Dozens of products or large localization files. |
| Client-side filtering of all strings | Browser memory and slow UI. | Server-side indexed filters and pagination. | Tens of thousands of strings. |
| Synchronous PR creation request | Timeouts and duplicate submissions. | Background job with idempotency key and status UI. | Slow Bitbucket API response or multiple changed files. |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Plaintext Bitbucket tokens | Repository write compromise. | Encrypt secrets at rest and restrict access to backend services. |
| Missing server-side role checks | Users can edit/approve/submit by calling APIs directly. | Enforce permissions on every mutation. |
| OAuth2 tokens without proper expiry/refresh policy | Stolen or stale tokens remain useful too long. | Use short-lived access tokens, explicit refresh/session policy, and server-side role checks. |
| Over-broad tokens | A compromise affects all workspaces/projects. | Prefer least-privilege project/repository/workspace tokens based on deployment model. |
| Logging tokens or raw API errors | Secret leakage. | Redact credentials and sensitive headers. |
| Blind PR branch names | Branch collisions or injection-like names. | Generate sanitized branch names and enforce uniqueness/idempotency. |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| File-tree first navigation | Product managers need repository knowledge. | Product/language/state/violation first search. |
| No context for constraint violations | Reviewers see errors but not why. | Show max length, actual length, and product constraint source. |
| Comments hidden behind separate screens | Review discussion is missed. | Show comment count in table and thread in detail panel. |
| Approval state changes without audit | Teams cannot explain why text was rejected or approved. | Store state history with actor, timestamp, optional comment. |
| PR submission lacks preview | Users do not trust generated changes. | Show changed strings and affected files before submit. |

## "Looks Done But Isn't" Checklist

- [ ] **Android XML support:** Verify escaped apostrophes, quotes, formatted strings, arrays, and plurals.
- [ ] **Qt `.ts` support:** Verify contexts, message ids, translation `type`, `numerus`, translator comments, and variants are preserved.
- [ ] **iOS `.strings` support:** Verify comments, escaped quotes, duplicate policy, UTF-8 handling, and table names.
- [ ] **JSON support:** Verify nested keys, arrays, duplicate key policy, and minimal formatting changes.
- [ ] **Bitbucket write-back:** Verify branch creation, commit creation, PR creation, permission errors, and stale source detection.
- [ ] **Review comments:** Verify comments survive imports, edits, state changes, and PR submission.
- [ ] **Constraints:** Verify length violations recalculate after import and edit.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Bad serializer diff | HIGH | Stop submissions, restore from Bitbucket, add failing fixture, patch adapter, recreate PR. |
| Wrong repo mapping | HIGH | Disable product import, correct mapping, re-import from source, invalidate wrong records. |
| Stale branch PR | MEDIUM | Refresh branch/file baseline, replay pending changes, regenerate PR. |
| Token scope failure | LOW | Show setup error, update token/scopes, retry idempotent job. |
| Lost comments | HIGH | Restore from DB backup/audit logs if available; otherwise add durable comment tests before relaunch. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Losing file semantics | Parser/writer foundation | Golden fixtures for every supported format. |
| Bad repository mapping | Product config | Admin preview validates sample files and language mappings. |
| Stale branch conflicts | Change-set/PR workflow | Tests simulate moved branch head before submission. |
| Bitbucket permission failures | Bitbucket integration | Setup capability checks for read/write/PR scopes. |
| Detached comments | Review/comments | Comments persist across imports and are visible in translation detail. |
| Repository-shaped UX | Search/review UI | Product manager can find a string without file path knowledge. |

## Sources

- [Bitbucket Cloud REST API intro](https://developer.atlassian.com/cloud/bitbucket/rest/intro/) - auth/token behavior and scopes.
- [API token permissions](https://support.atlassian.com/bitbucket-cloud/docs/api-token-permissions/) - separate repository and pull request permission boundaries.
- [Bitbucket Cloud source API](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-source/) - source browse/write behavior.
- [Android string resources](https://developer.android.com/guide/topics/resources/string-resource) - Android escaping and string resource types.
- [Qt TS file format](https://doc.qt.io/qt-6/linguist-ts-file-format.html) - TS message/translation metadata.
- [Apple String Resources](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/LoadingResources/Strings/Strings.html) - `.strings` format, comments, unique keys, UTF-8 note.
- [RFC 8259 JSON](https://www.rfc-editor.org/rfc/rfc8259.html) - JSON value/object/string interoperability issues.

---
*Pitfalls research for: VerboFlex*
*Researched: 2026-05-04*
