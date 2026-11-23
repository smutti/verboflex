# Update a project's sources

Open **Update catalog** in the product workspace to bring new and changed strings
into VerboFlex. Each source shows the latest attempt and the date of the catalog
available to translators. A timeout offers **Retry update**. **Open translation
catalog** opens the last successful import, including after a failed attempt.
It appears once a catalog is available. **Source details** contains the configured
branches, commit IDs and diagnostics. A separate code/translation mapping refreshes
both sources together.

To send approved translations to Bitbucket for review, open **Publish translations**.
Administrators can choose different source branches by editing and publishing the
product mapping. A rewritten source history requires review before activation.

The API retains its administrator-only authorization. Product ownership alone
does not grant import permission. The workspace entry and direct page route use
the same role boundary. Repository reads and catalog activation run in Celery;
leaving the page does not cancel an accepted job. Reopening the page retrieves
its server-owned status. Concurrent starts remain protected by the existing API.
After completion, return to **Strings** to load the updated catalog. Navigating
away from an unsaved translation uses the existing dirty-form navigation guard.

The source page loads repository names from the active published revision, even
when a different candidate configuration exists. Opening it only reads status;
it does not start an import. Failures retain the last successful baseline and the
existing retry/review actions. UI copy is available in all six interface languages.

## Verification

Synthetic frontend tests cover project navigation, direct-route authorization,
published versus candidate source selection, repository loading and retry, and
explicit refresh dispatch. Existing import tests cover polling, duplicate starts,
provider failures and baseline review. Run:

```sh
npm --prefix frontend test -- --run src/features/products src/features/admin/imports src/router.test.tsx src/i18n
npm --prefix frontend run lint
npm --prefix frontend run build
PLAYWRIGHT_BASE_URL=http://127.0.0.1:4179 npm --prefix frontend run e2e -- source-updates.spec.ts ui-language.spec.ts
```

Serve the built frontend on the selected port before the browser checks. They
use synthetic HTTP responses, exercise 320- and 1440-pixel layouts, verify that
reload resumes status polling without submitting a duplicate job, and deny a
viewer access before source configuration is fetched.

The PostgreSQL regression
`backend/tests/integration/test_import_jobs.py::test_import_authorization_fails_before_mapping_or_dispatch_work`
verifies that unauthorized list, start, status and rewrite requests cannot dispatch
repository work. See [application checks](application-ci.md) for test database setup.

## Confirmation renewal and catalog navigation

An automatic Bitbucket token renewal keeps completed preview confirmations valid
only within the same verified client-credentials lineage. Explicit reconnects,
changed configured credentials, revocation and incompatible scopes still invalidate
authority. Provider leases continue to require the exact current token generation.
Existing credentials without proven lineage require one fresh connection and
preview confirmation; the migration does not infer trust from old timestamps.
Enabled Qt source policies advance their version during migration so saved search
cursors and configuration forms cannot retain the former base-only semantics.
A stale confirmation is reported as **Mapping confirmation required**, independently
of malformed files or parser limits. Failed imports retain the last successful catalog.
This state remains readable in both import details and the published-mapping list,
including an initial import with no catalog yet. After confirming the preview,
the administrator can retry from the same mapping.

In the workspace, **Review translations with changed source text** opens the
project’s unresolved source-change queue. The administrative mapping view retains
its **Open current catalog** and **Review source changes** actions.

Saving an inline translation retains the loaded list while refreshing its cursor
chain. Previously loaded pages are replaced together. A filtered-out saved row
remains at its former position while the user finishes their work. Refresh failures
keep the visible results and expose retry without using the stale continuation.
The synthetic `translation-save-scroll.spec.ts` browser check saves beyond the first
page in complete and filtered queues and retains before/after screenshots.
