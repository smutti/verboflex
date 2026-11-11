# Update a project's sources

Administrators can open **Update from branches** in a project's workspace.
The page shows each published mapping, its configured source branches, the last
successful commit IDs, import status and warnings. Select **Update from branches**
on a mapping to import the latest commits. A separate code/translation mapping
refreshes both sources in the same import execution.

This operation updates VerboFlex's imported catalog. It does not merge, reset,
push or change the configured repository branches. To choose different source
branches, edit, validate and publish the project's mapping in administration.
Saved proposals remain subject to the existing import and conflict rules; a
rewritten Git history requires the existing baseline review before activation.

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
