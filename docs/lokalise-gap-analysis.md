# VerboFlex and Lokalise: gap analysis

Reviewed **8 October 2026** against VerboFlex source
`a6fcfe89983110d3483c4a69ddd78a095b37ccd8`, the running local UI, and current official
Lokalise documentation. This comparison concerns **Lokalise Expert for software
localization**, rather than combining Expert, Vantage and Messages into one
imaginary feature set. Availability varies by plan; this is not a pricing comparison.

VerboFlex already supports a useful repository-based review workflow. Its largest
functional gaps are creating missing translations, reusing previous translations,
terminology, linguistic QA, and organizing work across people. Rebuilding the
multilingual screen would not close those gaps.

## What was verified locally

Docker Desktop and the existing local Compose stack were started without building
new application images. Compose readiness completed successfully; login,
`/api/v1/users/me`, translation options and system status returned HTTP 200.
The browser displayed five products and the Flameshot bilingual editor with
50 loaded keys, language selection, filters, comments, history and review actions.
No translation was edited and no repository import or remote write was triggered.

The running database is at **0036_mcp_oauth**, while the reviewed source contains
0037 and 0038. In particular, the newer audit ledger is implemented in source but
must not be advertised as deployed locally. Restarting Docker did not perform a
release or schema upgrade.

Status definitions: **Present** means implemented for the stated scope, not full
Lokalise parity. **Partial** means a narrower workflow exists. **Missing** means
no supporting domain model, API and product UI were found in the reviewed source.
**Unverified** means release evidence is still outstanding.

Priorities: **P0** before a production claim at the intended scale; **P1** for an
effective daily translation workflow; **P2** for broader adoption; **P3** when a
specific customer need justifies the work. These are recommendations, not approved
changes to the v1 scope.

Follow-up implementation: new keys, missing-language entries, Android/Qt plural
creation, current-content exact/fuzzy suggestions and a project glossary are now
implemented. Local Docker was migrated to 0041 and rebuilt. The table below retains
the original comparison baseline; see [Translation authoring and reuse](translation-authoring-and-reuse.md)
for the delivered behavior, limits and verification. Assignment, broader linguistic
QA, ICU/Apple plural adapters and cross-project reuse remain open.

## Capability comparison

| Area | Lokalise reference | VerboFlex today | Gap and recommended priority |
| --- | --- | --- | --- |
| Bilingual / multilingual editing | Both views and inline editing. [Editor](https://docs.lokalise.com/en/articles/6854191-translation-editor) | **Present.** Both views, editable imported values, language rows, draft conflict handling; up to 20 visible languages. | Improve density and feedback incrementally. Do not rebuild the basic view. **P2** |
| Fill a missing language value | Key-centric editing of language values. [Editor](https://docs.lokalise.com/en/articles/6854191-translation-editor) | **Partial.** Empty imported values can be edited; an absent language slot is read-only. | Create a target entry in the correct configured file, with valid provenance and serialization. Distinguish an empty value from a missing repository entry. **P1** |
| Filters and work queues | Predefined filters, AND/OR conditions, named filters shared across contributors. [Filters](https://docs.lokalise.com/en/articles/1400616-filter) | **Partial.** Searchable selectors, source-changed / needs-review / needs-translation and length/state filters; local view/language preferences. | Named personal/shared views, richer conditions and tags. Persisted view preferences are not shared saved filters. **P1** |
| Bulk work | Actions on selected keys. [Bulk actions](https://docs.lokalise.com/en/articles/2074190-bulk-actions) | **Partial.** Approved proposals can be selected for a change set; editor operations are predominantly per group. | Bounded bulk review and metadata actions, with a preview and explicit selection semantics across pages. **P1** |
| Translation memory | Cross-project exact/fuzzy suggestions, provenance and pretranslation. [TM](https://docs.lokalise.com/en/articles/1409589-translation-memory) | **Missing.** Revision history and global string search exist, but no reusable suggestion store or matching workflow. | Suggest approved translations with matching score and source context; accept explicitly. Respect physical-deletion policy. **P1** |
| Glossary | Term definitions, translations and usage guidance in the editor. [Glossary](https://docs.lokalise.com/en/articles/1400629-glossary) | **Missing.** Comments are available, but no structured terminology management. | Project terminology, preferred/forbidden terms and terms that must remain unchanged. **P1** |
| Translation QA | Placeholder, HTML, number, whitespace, URL and other checks with configurable severity. Expert currently excludes plural keys from its QA checks. [QA](https://docs.lokalise.com/en/articles/2564656-qa-checks) | **Partial.** Grapheme-based length limits, source/version checks and format/structure validation. These are not linguistic QA. | Start with format-aware placeholders, tags, whitespace and number consistency. Show issues before saving and in non-focused rows. **P1** |
| Visual context | Key-linked screenshots, regions and optional automatic matching. [Screenshots](https://docs.lokalise.com/en/articles/2045882-screenshots) | **Partial.** Source text/context, file provenance, history and discussion exist; no screenshot attachment workflow. | Add key-linked screenshots and descriptions before attempting OCR or design-tool integration. **P1** |
| Assignments and deadlines | Per-language assignees, due dates, task templates and chained review tasks. [Tasks](https://docs.lokalise.com/en/articles/1457259-tasks) | **Partial.** Draft/approved/rejected proposals, comments, mentions and notifications; no translation task domain. | Assign a bounded set of keys/languages, show “My work”, owner, progress and deadline. Celery jobs are not user assignments. **P1** |
| Dashboard and analytics | Usage, task activity, translation quality and review-effort reporting. [Analytics](https://docs.lokalise.com/en/articles/9204943-lokalise-analytics) | **Partial.** Personal activity/notifications and product coverage by language. Coverage excludes pending edits and review status. | Show imported coverage separately from draft/approved/ready-to-submit progress; then add aging queues and trends. **P1** |
| AI / machine translation | Suggestions and automated translation are integrated into the translation workflow. [Editor](https://docs.lokalise.com/en/articles/6854191-translation-editor), [Automations](https://docs.lokalise.com/en/articles/4529101-automations) | **Partial integration path.** External assistants can use MCP; no native provider-backed suggestion/translation workflow was found. | Add optional suggestions with glossary/context, cost limits, provenance and human acceptance. MCP alone does not supply a managed translation engine. **P2** |
| Repository integration | GitHub can pull files and create PRs; automatic pulls are supported. [GitHub](https://docs.lokalise.com/en/articles/1684090-github) | **Partial breadth.** Bitbucket has import/refresh/branch/commit/PR; GitHub supports public import/refresh and local review only. | Private GitHub and GitHub PR submission; provider events and configurable refresh scheduling. **P2**, or P1 for GitHub-first teams |
| Automation rules | Event-driven translation rules and task-oriented workflows. [Automations](https://docs.lokalise.com/en/articles/4529101-automations), [Workflows](https://docs.lokalise.com/en/articles/9582608-workflows) | **Partial.** Asynchronous jobs, retry/recovery, maintenance and backup schedules; no user-configured localization rule builder. | Start with a few bounded triggers: source updated → flag review / assign work / refresh. **P2** |
| Branches and conflicts | Translation-project branching and merge conflict resolution. [Branching](https://docs.lokalise.com/en/articles/3391861-project-branching) | **Different model.** Configured repository branches, immutable baselines, rewritten-source confirmation and proposal reconciliation. | Do not equate safe handling of a Git rebase with translation-project branch/merge parity. Parallel release workspaces require separate design. **P2/P3** |
| File formats and plural forms | Broad platform/document format support. [Formats](https://docs.lokalise.com/en/collections/2909121-keys-and-files) | **Partial breadth.** Eligible Android XML, Qt TS, JSON and Apple strings edits; Android/Qt variants supported. XLIFF is import/read only. | Prioritize actual repository demand, e.g. PO, ARB/ICU, XCStrings or YAML; require read/edit/write round-trip fixtures. **P2** |
| Permissions | Project contributors and language-specific access. [Contributors](https://docs.lokalise.com/en/articles/1400623-contributors) | **Partial.** Installation-wide admin/reviewer/translator/viewer roles; no product or language membership boundary. | Product and language permissions before onboarding outside translators or separate organizations. **P0 for that audience; P2 for the current internal-team scope** |
| Enterprise sign-in | SAML SSO is documented for Enterprise. [SSO](https://docs.lokalise.com/en/articles/3339495-saml-based-single-sign-on-sso) | **Partial.** Internal accounts, token/session controls and OAuth for MCP. MCP OAuth is not enterprise user SSO. | External identity provider and lifecycle integration when enterprise deployment requires it. **P2** |
| APIs and MCP | REST API and an MCP server are publicly documented. [Developer platform](https://lokalise.com/product/for-developers/) | **Present.** HTTP API, MCP over HTTP/OAuth and local stdio, using existing role checks. | Keep interoperability tests current. MCP is useful parity, not an exclusive differentiator. **P2 maintenance** |
| Delivery ecosystem | CLI, SDK/OTA and cloud export options. [Developer platform](https://lokalise.com/product/for-developers/) | **Narrower by design.** Delivery through reviewed Bitbucket PRs. | Do not add OTA, CMS integrations or document translation merely to match a feature list. **P3** |
| Production operations / scale | Vendor feature documentation cannot establish comparative performance for our workload. | **Unverified.** Local backups/restore tooling and health checks exist; production hosting, off-host recovery, alert delivery and scale certification remain open. | Complete rollout and capacity evidence; no unsupported “faster than Lokalise” claim. **P0** |

## Recommended delivery sequence

Effort below is relative, not an estimate in days.

| Step | Deliverable | Acceptance criterion | Relative effort |
| --- | --- | --- | --- |
| 0 | Production baseline and fast filtered queries | Align release image/schema after backup and rehearsal. Repeat the declared workload with retained evidence: p95 ≤ 2 seconds at five readers, no unexpected errors, correct cursors. Include import contention. | L |
| 1 | Complete a missing translation | An absent target entry can be created in an explicitly mapped existing target file, reviewed and serialized into a Bitbucket PR without changing unrelated content. File creation is a separate explicit scope. | L |
| 2 | QA panel and error feedback | Missing/changed placeholders and malformed supported tags are visible in and out of focus. Configured blocking rules apply through UI, API and MCP. Login distinguishes unavailable services from wrong credentials. | M |
| 3 | Saved views and bounded bulk review | Save/share “Italian needing review”; restore across devices; preview exact scope and item-level failures before applying a bulk action. Keep existing optimistic concurrency checks. | M |
| 4 | Glossary and translation reuse | Show terminology and approved exact matches first, then fuzzy suggestions with provenance; accept manually. Deleting source content also removes derived reusable content according to the agreed deletion policy. | L |
| 5 | Visual context and assigned work | Attach context to keys; assign language-specific tasks and expose personal queues, deadlines and pending-review counts. Add membership restrictions before external contributors. | L |
| 6 | GitHub completion and optional AI | Add private GitHub/PR support with the same recovery safeguards, then a managed suggestion workflow when requested. | L |

A practical first product increment is **missing translations + structural QA +
saved work queues**. It lets a translator finish work, protects runtime strings
and reduces repeated navigation. Translation memory, glossary and assignment
features then improve throughput across projects.

## Choices to retain

- Keep the user's requested concise UI and **Save / Cancel** interaction; do not
  reintroduce “Save and next” just because another editor offers related actions.
- Keep deleted repository strings physically removed. A future TM must not become
  an accidental archive of content that the user explicitly requested to delete.
- Keep source provenance, safe serialization, reviewed PRs and rebase/reconciliation
  protections. They are core strengths of this repository-oriented product.
- Keep GitHub public-only/no-write limits explicit until actually implemented.
- Keep the product positioning focused: an internally hosted localization review
  workspace connected to engineering repositories. Feature-for-feature TMS parity
  would be a larger product decision.

## VerboFlex evidence

The existing Graphify index provided historical orientation but not sufficient
coverage of current features. Conclusions above were checked against live source:

| Claim | Evidence |
| --- | --- |
| Editor, read-only absent slots and supported edit shapes | [TranslationResultList](../frontend/src/features/translations/TranslationResultList.tsx), [TranslationEditor](../frontend/src/features/translations/TranslationEditor.tsx) |
| Fixed filters, view/language preferences | [TranslationFilters](../frontend/src/features/translations/TranslationFilters.tsx), [preferences](../frontend/src/features/translations/translationPreferences.ts) |
| Comments, proposals, notifications; no task/TM/glossary models | [Review models](../backend/src/verboflex/models/review.py), [model directory](../backend/src/verboflex/models), [API routes](../backend/src/verboflex/api/v1/routes) |
| Coverage excludes pending/review; activity is separate | [ProductOverviewPage](../frontend/src/features/admin/products/ProductOverviewPage.tsx), [product summary service](../backend/src/verboflex/services/product_summary.py), [PersonalDashboard](../frontend/src/features/workspace/PersonalDashboard.tsx) |
| Approved proposal selection is a submission workflow | [ChangeSetsPage](../frontend/src/features/change-sets/ChangeSetsPage.tsx), [submission models](../backend/src/verboflex/models/submission.py) |
| Source rewrite and optimistic conflict handling | [RewrittenBaselineDialog](../frontend/src/features/admin/imports/RewrittenBaselineDialog.tsx), [TranslationConflictDialog](../frontend/src/features/translations/TranslationConflictDialog.tsx) |
| Format dispatch and import bounds | [Parser registry](../backend/src/verboflex/localization/importing/registry.py), [parser contracts](../backend/src/verboflex/localization/importing/core.py) |
| Internal roles, audit and MCP boundaries | [Authorization and audit](authorization-and-audit.md), [MCP guide](../mcp-server/README.md) |
| Login uses the same failure message for all errors | [LoginPage](../frontend/src/features/auth/LoginPage.tsx) |
| GitHub limits | [GitHub imports](github-imports.md), [README support matrix](../README.md) |
| Deployment, backups and outstanding release evidence | [Production readiness](production-readiness.md), [backup/restore](backup-restore.md), [local Docker](local-docker.md) |

No paid Lokalise account was exercised in this review, and no comparative
performance test was run against its service. Earlier local load-test findings
remain provisional: the interrupted capacity task is not closed and its temporary
raw outputs were no longer available during this review. No 10-million-value
certification or numerical feature-parity percentage is claimed.
