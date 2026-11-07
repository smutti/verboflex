# Add a project language

Open **Change sets → Approved changes**, select the translation source when the
project has several mappings, and use **New language → Add language**. Enter a
canonical locale such as `fr`, `pt-BR`, `sr-Latn-RS` or `es-419`.

An administrator first configures approval branches. Import from that working
branch, with a different PR destination. Administrators and project reviewers can
add languages; translators and viewers cannot. Repository access and membership
are checked again by the worker immediately before sending a commit.

The new catalog starts with copied source wording. This is an initialization aid,
not automatic translation or approval. Review the copied text. When branch history
shows **Saved to branch**, refresh the source to import the new language into
Strings. Translate, save, review and explicitly open a PR through the existing
workflow. No language request writes directly to the destination branch or opens
a PR automatically. Imported coverage follows the existing format semantics:
nonempty copied values can count as present; presence is not translation quality.

## Formats and preservation

| Source | Initialization |
| --- | --- |
| Android XML | Create the destination `values-*` directory, retaining filenames, strings, arrays, comments and attributes. Keep existing quantities and add missing destination plural categories from `other`. Script/numeric-region locales use Android's `b+` convention. |
| MOKO XML | Copy `moko-resources/base/strings.xml` to the locale directory. Separate code repositories stay read-only; unrelated shared resources, including duplicate occurrences, remain intact. |
| Qt TS | Follow the confirmed filename/directory template, set `language`, retain context, IDs, source text and metadata, mark active translations unfinished, and initialize the destination's positional plural count. |
| JSON / Angular | Copy a per-locale catalog byte-for-byte, including nesting, empty objects, literal-dot keys, interpolation and rich text. For locale-rooted JSON, append a copied base-language object without rewriting existing members. |
| iOS `.strings` | Copy the confirmed `.lproj` catalog, preserving comments, escapes, BOM and original encoding, including UTF-16. |
| XLIFF 1.2 / 2.0 / 2.1 | Create the locale peer, initialize targets from embedded sources including inline codes, retain unit/group/file IDs and metadata, update the target locale and reset translation state. Existing XLIFF translation writeback restrictions still apply. |
| HTML / email | Copy every base-language template, preserving directories, filename separator, extension, markup and variables. The existing HTML API for supplied reviewed fragment translations remains available. |

Android locale paths follow the [Android resource qualifier documentation](https://developer.android.com/topic/architecture/views/resources/providing-resources-views).
Locale grammar and structural parser bounds remain deliberately limited; an
ambiguous filename without a confirmed locale template is rejected. There is no
arbitrary output-path field. GitHub source projects retain their existing
import/local-review capability; language commits require a writable Bitbucket
mapping, as do the existing approval branches.

A request applies to the selected mapping. It creates all its base-language
catalog peers atomically, up to 100 destination files and the existing bounded
file/batch sizes. Existing languages or destination files are never overwritten.
A moved branch or changed import requires a fresh import. An unsent failed request
can be discarded; uncertain sends must first be reconciled. Retrying a verified
job never sends another commit.

## Screenshots

After refresh, the new language uses the project's existing screenshot bindings.
Save a translation, choose a configured scenario and viewport, and generate the
image. Angular validates the same exact JSON selector and placeholder contract
in the new catalog. The three synthetic scenarios (site list, tenant creation,
tenant validation) work at desktop and mobile sizes. Compose uses the new locale
resource overlays and its existing reviewed application runner. HTML retains its
normal browser preview. Projects without a renderer/scenario integration do not
gain one merely by adding a language.

For Angular mappings with an explicit catalog allowlist, a verified language
commit registers only its generated locale/path pair. Import and preview combine
these receipts with the unchanged mapping profile. Unsent, failed or foreign
project jobs cannot extend the allowlist. Changing the profile invalidates those
registrations; include any desired created catalogs explicitly in the new profile.
The active revision itself is never edited by the language job.

The web runner supports an explicit operator option for reusing a reviewed
application with newer frozen catalogs:

```json
{
  "catalog_overlays": true,
  "source_digest": "<SHA-256 of the reviewed import's complete source and manifest set>"
}
```

Add these fields to the existing private runner profile alongside its repository,
immutable application commit, mirror and image digest. The adapter checks the
complete imported source set against that reviewed digest, and the isolated
container hashes every archived source before building. Changed code or scenarios
require operator review. The archive always comes from the pinned application
commit; no new source revision is executed implicitly. This mode intentionally
renders the reviewed application version, including its pinned styles/assets and
build configuration, with the selected catalog. The receipt and screenshot
options distinguish **Reviewed application revision** from **Language catalog
revision**. Without this option the existing exact-commit policy remains in force.

## API and verification

`POST /api/v1/products/{product_id}/languages` accepts `workflow_id` and `language`
and returns a durable job ID with HTTP 202. It performs no repository I/O.
`DELETE /api/v1/products/{product_id}/languages/{job_id}` discards an unsent blocked
request. Existing branch-history, retry and scheduler recovery endpoints apply.
Migration `0056_project_languages` extends the job/audit constraints and refuses
downgrade while language history exists.

- `tests/unit/localization/test_languages.py`: parser-backed byte/identity,
  encoding, plural, locale and unsupported-input tests across formats.
- `tests/api/test_project_languages.py`: import → HTTP request → durable commit →
  refresh, repeat creation, permission revocation and uncertain-send recovery.
- `frontend/e2e/add-language.spec.ts`: retry, preserved input, reload, viewer
  controls and 320/1440-pixel layouts against synthetic HTTP fixtures.
- `PHASE8_HTTP_SETUP=1 bash tools/phase7_smoke.sh`: real built UI/API/PostgreSQL,
  Redis, Celery and TLS provider fixture; browser language creation, commit,
  refresh and explicit PR publication.
- `backend/.venv/bin/python tools/web_capture_smoke.py --artifacts /tmp/web-evidence`:
  the original twelve real Angular captures plus six captures in a newly created
  French catalog, including saved text and actual maxlength interpolation.
