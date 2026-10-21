# Public-content evidence

Compose screenshot claims checked against main commit `6ca943d` on 2026-10-21; other claims checked on 2026-10-11. This file is for maintainers and is not copied to the public artifact. Recheck affected claims when the application changes.

| Public claim                                                                   | Source                                                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Internal roles and read/propose/comment/review permissions                     | [`RoleName`](../backend/src/verboflex/schemas/users.py), [`translation_access.py`](../backend/src/verboflex/auth/translation_access.py)                                                                                                                                |
| Multilingual and bilingual search, filtering, language selection, inline edits | [`translations/`](../frontend/src/features/translations/), [`translation_search.py`](../backend/src/verboflex/services/translation_search.py)                                                                                                                          |
| Grapheme counting, draft saving and visible over-limit state                   | [`TranslationEditor.tsx`](../frontend/src/features/translations/TranslationEditor.tsx)                                                                                                                                                                                 |
| Over-limit or stale proposals cannot be approved                               | [`translation_reviews.py`](../backend/src/verboflex/services/translation_reviews.py), especially the review eligibility checks                                                                                                                                         |
| Comments, mentions and in-app notifications                                    | [`MentionComposer.tsx`](../frontend/src/features/translations/MentionComposer.tsx), [`notifications/`](../frontend/src/features/notifications/)                                                                                                                        |
| Dashboard: three activity items and three project updates                                   | [`PersonalDashboard.tsx`](../frontend/src/features/workspace/PersonalDashboard.tsx)                                                                                                                                                                                    |
| Product coverage; availability does not mean approval                          | [`ProductOverviewPage.tsx`](../frontend/src/features/admin/products/ProductOverviewPage.tsx)                                                                                                                                                                           |
| Repository/source setup, preview and publication                               | [`ProductWizardPage.tsx`](../frontend/src/features/admin/products/ProductWizardPage.tsx), [`repositories/`](../frontend/src/features/admin/repositories/)                                                                                                              |
| Public GitHub import/local review only                                         | [`github-imports.md`](../docs/github-imports.md), [`integrations/github/`](../backend/src/verboflex/integrations/github/)                                                                                                                                              |
| Five import formats; four write-back formats; XLIFF is read-only               | [`importing/registry.py`](../backend/src/verboflex/localization/importing/registry.py), [`writing/registry.py`](../backend/src/verboflex/localization/writing/registry.py), [`writableTranslationDetail`](../frontend/src/features/translations/TranslationEditor.tsx) |
| Bitbucket preparation, explicit submission and result presentation             | [`change-sets/`](../frontend/src/features/change-sets/)                                                                                                                                                                                                                |
| Refresh, stale proposals, failed import isolation and source deletion          | [`translation_imports.py`](../backend/src/verboflex/services/translation_imports.py), [`translation_reviews.py`](../backend/src/verboflex/services/translation_reviews.py), [`translation_search.py`](../backend/src/verboflex/services/translation_search.py)         |
| HTTP MCP, OAuth scopes, CLI commands, consent and revocation                   | [`mcp-server/README.md`](../mcp-server/README.md), [`mcp_http.py`](../backend/src/verboflex/mcp_http.py)                                                                                                                                                               |
| Background workers and self-hosted services                                    | [`docker-compose.yml`](../docker-compose.yml), [`docker-compose.prod.yml`](../docker-compose.prod.yml)                                                                                                                                                                 |
| Optional daily backup, 14 verified copies, keyring and restore procedure       | [`backup-restore.md`](../docs/backup-restore.md), [`docker-compose.backup.yml`](../docker-compose.backup.yml)                                                                                                                                                          |

## Intentional limits on claims

- Do not claim private GitHub access, GitHub write-back, automatic translation, XLIFF editing, guaranteed compatibility with every format variant, public self-service signup or benchmarked support for millions of strings.
- Remote Claude web connectivity still requires a reachable HTTPS installation and end-to-end verification there. Local Codex CLI and MCP SDK checks are not proof of Claude web deployment compatibility.
- Sample coverage: 1,200 source keys × three target languages = 3,600 possible translations. Present: 2,940; missing: 660. German: 840/1,200; Italian: 960/1,200; French: 1,140/1,200. These are invented data and independent from the one-row editing demonstration.
- The demo models draft → approval only. It does not simulate a real pull request or claim any external action occurred.

| Added claim | Source |
| --- | --- |
| Product search, languages and coverage cards | `frontend/src/features/products/ProductWorkspaceIndex.tsx`, `backend/src/verboflex/services/product_workspace.py` |
| Missing translations, new keys, native plurals, reuse and glossary | [Authoring reference](../docs/translation-authoring-and-reuse.md) |
| Apache 2.0 source license | [LICENSE](../LICENSE), [NOTICE](../NOTICE) |
| Live demo deployment prerequisites and limits | [Demo deployment](../docs/demo-deployment.md) |

## Current application screenshots

Seven captures from the running local portal on 2026-10-11 show synthetic
Northstar products. The gallery distinguishes real screenshots from the separate
in-memory demonstration. See [SCREENSHOTS.md](SCREENSHOTS.md) for capture scope,
file hashes and the update checklist. Product counters are repository coverage;
match percentages are source similarity, not quality or approval scores.

- Filter shortcuts and same-language matching: `frontend/src/features/translations/TranslationFilters.tsx`.
- Empty values and missing entries are distinct; new entries require mapped files: `docs/translation-authoring-and-reuse.md`.
- Pending state filtering and selection before submission: `frontend/src/features/change-sets/ChangeSetReviewPage.tsx`.

## Compose screenshots

The landing page’s code-to-screen illustration is HTML with synthetic Northstar
checkout content, not a capture or a running renderer. The existing seven gallery
images remain real application captures. The website never calls a capture service.

| Public claim | Source |
| --- | --- |
| Generate screenshots from registered, zero-argument Android Compose previews | [Capture integration](../docs/code-keys-compose.md), [runner](../tools/compose_capture.py) |
| Apply the selected saved proposal; freeze code and translation revisions | [Screenshot service](../backend/src/verboflex/services/screenshots.py) |
| Review text on the left, screenshots on the right; mobile stacking; technical disclosure | [TranslationDetailPage](../frontend/src/features/translations/TranslationDetailPage.tsx) |
| Explicit generation, dirty-edit guard, stale version warning, authenticated images, light/dark selection and full-size image | [TranslationScreenshots](../frontend/src/features/translations/TranslationScreenshots.tsx) |
| Prepared runner and fixture state required; no arbitrary live app/device capture | [Integration limitations](../docs/code-keys-compose.md), [Linux setup](../docs/compose-linux-runner.md) |

Do not describe this as live rendering, automatic capture after every edit, instant
rendering, support for every Compose target, or a guarantee that a registered key
appears in every fixture. Screenshot generation does not approve or submit changes.
