# Angular JSON localization and web screenshots

VerboFlex supports nested JSON catalogs used by ngx-translate on a direct repository
mapping. A versioned localization profile selects the intended files and protects
interpolation parameters and explicitly declared rich text. Optional web capture
uses registered scenarios, exact JSON values, synthetic API responses and an isolated
Angular/Playwright runner. Existing mappings and Compose capture remain supported.

## Configure a candidate

In the mapping form, open **Angular localization (optional)** and enable the profile.
Paths in `files` are relative to the mapping's localization folder. Other paths are
repository-relative. This example uses `src/assets/i18n` as the localization folder:

```json
{
  "version": 1,
  "syntax": "ngx_translate",
  "files": {"en": "en.json", "it": "it.json"},
  "rich_text_paths": [["NOTICE", "BODY"]],
  "web_capture": {
    "application_root": null,
    "manifest_path": "capture.json",
    "source_roots": ["src/app"],
    "source_excludes": ["src/app/api"],
    "runner_profile": "reviewed-angular",
    "catalog_url_prefix": "/assets/i18n/",
    "marker": "_"
  }
}
```

Omit `web_capture` for import/edit/writeback without screenshots. Omit the whole
profile to retain generic JSON behavior. Preview, choose English as the base language,
confirm, publish the candidate and import. Editing the profile invalidates candidate
preview authority. An active revision cannot be edited in place.

Only the selected files are downloaded and parsed as localization catalogs. Preview
lists excluded paths. Missing selected files fail the operation rather than importing
a partial set. A file named `template.json` is excluded only by this explicit
selection; the valid locale `nav` and generic JSON detection are unchanged.

A JSON value keeps its leaf key and parent selector. `SITE.NAME` and `TENANT.NAME`
are separate values even though they share a translation group. Literal dots in
object members remain literal. Runtime address collisions disable capture, preserving
the imported translations for diagnosis. Code context reports missing literal usages,
unresolved dynamic usages, empty values and identical base/target text. Identical text
is informational, never an automatic review-state change.

## Edit and review messages

The matching imported base value defines the contract for each exact JSON selector.
`{{name}}` and `{{ name }}` identify the same parameter; dotted names such as
`{{ value.requiredLength }}` are supported. Parameters can move, but their names and
multiplicity must remain unchanged. Invalid delimiters, added/missing parameters and
ICU plural/select expressions are rejected. Changing a base message's parameters
requires a source change and a new import.

The editor shows required tokens using their original spelling, provides insertion
buttons and displays the source of rich-text messages as text. Save errors preserve
the local draft. The API validates saving, missing-value authoring, approval, reuse,
capture and final writeback. Rich-text paths preserve their allowed element structure
and attributes; added scripts, event handlers, URLs or markup are rejected. Repository
HTML is never inserted into the VerboFlex DOM.

## Add another language

Use the project [Add language workflow](adding-languages.md) to create a catalog
from the base language. Verified language receipts extend the exact catalog
selection for subsequent imports without rewriting active mapping configuration.
Existing bindings, interpolation guards and screenshot scenarios apply after
refresh. The operator's optional `catalog_overlays` policy renders newer catalogs
against the reviewed, pinned application, with both revisions in the receipt.
Changed application sources or manifests still require review.

## Register scenarios

The repository manifest is data, not a command runner. The complete three-scenario
example is [the synthetic manifest](../tools/fixtures/angular-web/capture.json).
Each scenario declares an ID, label, local route, unique readiness selector, actions,
exact runtime-key/DOM bindings, and HTTP fixtures. Use `attribute: "placeholder"`
for a search-input binding; capture requires the input to be empty so its placeholder
is actually visible. Supported actions are `click`,
`fill`, `blur`, `wait`, `assert_enabled` and `assert_disabled`. Fixture URLs are local
`/api/` paths with exact query strings and methods. A capture bootstrap can configure
API clients to use that prefix. No live credentials or service calls are needed.

The initial scenarios are:

| ID | Real browser state | Main evidence |
| --- | --- | --- |
| `sites.list` | Two synthetic sites and a simulated map | A header translated with `instant()` after locale initialization |
| `tenant.create.open` | The create dialog with valid synthetic values | Saved wording and an enabled form action |
| `tenant.create.validation` | A 98-character name against the actual 97-character validator | Saved wording, interpolated `97`, and a disabled form action |

The fixture uses Angular reactive forms; it does not insert validation errors into
the DOM. Both `en` and `it` run in light appearance at desktop 1440×900 and mobile
390×844. Map content is explicitly simulated. An application integration should use a
separate capture entry/configuration, preload its locale before `instant()` calls,
provide the correct route injector to dynamic dialogs, and bundle fonts locally.
Keep that bootstrap out of the production entry graph. Ordinary builds and backend
contracts must not acquire fixture-specific behavior.

The worker resolves the branch once. Catalogs, manifest and selected TypeScript/HTML
sources use that commit. TypeScript and Angular AST parsers inspect source as data;
they do not execute it. Generated roots can be excluded explicitly; generated/test
folders and `.spec.ts`/`.test.ts` files are also skipped. Broken selected source or an
exceeded budget fails the import rather than replacing a complete usage index with a
partial one. Catalog references retain their localization-root restrictions. Separate
application-file provenance, hashes, validated scenarios and usage evidence live in
`ImportExecution.web_context`, included in the activation digest.

## Install an isolated runner

The backend image includes the bounded Angular source parser. A local worker needs:

```sh
npm ci --prefix tools/web-runtime --ignore-scripts
export VERBOFLEX_WEB_EXTRACTOR_COMMAND='["node","--max-old-space-size=256","/absolute/path/tools/web-runtime/extract.mjs"]'
```

A reviewed application runner image contains its dependencies, Node toolchain,
Playwright/Chromium, the trusted runtime and `/opt/web-profile.json`. The reference
[Dockerfile](../docker/web-capture.Dockerfile) prepares Angular 17.3 with Node 20.20.0
and Playwright 1.62.1. Application code is built offline per capture; dependencies
are reused, while images are always rendered fresh. A prepared dependency image
must match the repository lockfile hash. The image's operator-owned profile contains
`name`, `lockfile_sha256`, `build_args` and `dist`. The browser output directory must
contain `index.html` and local assets. Repository manifests cannot supply commands.

On the trusted worker host, register a bare mirror and a digest-pinned image:

```json
{
  "reviewed-angular": {
    "repository_id": "00000000-0000-0000-0000-000000000001",
    "commit": "0123456789012345678901234567890123456789",
    "mirror": "/srv/capture/mirrors/application.git",
    "image": "sha256:REPLACE_WITH_THE_PREPARED_IMAGE_DIGEST"
  }
}
```

Set `VERBOFLEX_WEB_SCREENSHOT_RUNNER_COMMAND` in the API and screenshot worker to a
JSON argv array invoking `python /absolute/path/tools/web_capture_container.py
--profiles /srv/capture/profiles.json`. The API uses the setting only to expose
availability; repository operations and rendering run through Celery. Continue to
use `VERBOFLEX_SCREENSHOT_RUNNER_COMMAND` for Compose. Workers must consume the
`screenshots` queue. On a provisioned capture host with the backend environment,
Docker CLI and application database/broker settings, start
`celery -A verboflex.worker.celery_app worker -Q screenshots --concurrency=1`.
The ordinary backend image includes the extractor; executing this Docker adapter
requires the separately provisioned capture host. Configure the API availability
setting through `.env` and recreate its service after enabling it. An operator updates the mirror and reviewed profile for each
supported application revision; an unprepared commit fails closed.

The adapter exports a bounded archive from the exact commit. The application receives
that archive, immutable input and prepared dependencies, never the mirror's `.git`
configuration, provider tokens or service environment. Docker runs as an unprivileged
user with no network, a read-only root, no added capabilities, CPU/memory/process
limits and temporary output. Build/browser output is bounded and application logs
are not exposed by the API. A production deployment can place this adapter on a
dedicated capture host; do not run repository builds directly in the API process.

Chromium gets a fresh context, fixed locale/time, disabled service workers and
reviewed fixture responses. External traffic, WebSockets, unexpected API requests,
console/page errors, unresolved tokens and invisible/ambiguous/clipped targets fail
the capture. The target's real scroll container is scrolled before measuring it.
Only the selected saved value is overlaid; unrelated drafts stay out. The worker
validates input/image digests, commit/scenario/viewport provenance and DOM regions,
then rechecks current import and access authority before storing the image.

## Reviewer workflow and compatibility

Open a translation, choose its exact JSON path, scenario and viewport, save the draft,
and generate a screenshot. Unsaved edits block generation. Changing the proposal,
target, viewport or scenario marks an older image as stale. The existing reconnect,
retry, cancellation, quotas, expiry and authenticated image retrieval remain in use.
A receipt records a unique render ID, timestamp, commit, manifest/source digests,
language, viewport and observed text. Capture does not approve or submit translations.

Web requests use `engine: "web"`, `scenario_id`, `target_value_id`, `viewport` and an
optional saved `proposal_version`. The server derives source and language authority.
Legacy `preview_function` requests remain Compose requests with the version 1 runner
bundle. Web bundles are version 2. Migration `0055_web_localization` adds nullable
profile/context/receipt fields. Disable new web configuration before rollback;
downgrade refuses to discard existing web configuration or evidence.

## Verification

All committed fixtures and receipts generated by these commands use synthetic data:

```sh
node --test tools/web-runtime/renderer.test.mjs
backend/.venv/bin/python tools/web_capture_smoke.py --artifacts /tmp/verboflex-web-evidence
```

The smoke owns and removes its PostgreSQL, Redis, Celery processes, temporary mirror
and containers. It tests saved text through the actual API and queue, builds offline
inside Docker, captures all twelve combinations, checks authenticated PNGs and
verifies distinct render receipts. It requires Docker, the backend environment and
`npm ci --prefix tools/web-runtime --ignore-scripts`. Its source extractor and
catalog parser run on synthetic repository data; ordinary backend regressions also
exercise exact selectors, invalid messages and revoked access. The renderer negative
suite requires `npx --prefix tools/web-runtime playwright install chromium`.

The frontend `translation-detail-review.spec.ts` covers exact target/scenario requests,
viewport selection and stale images at narrow and desktop widths, alongside the
existing Compose, unsaved-edit and HTML-preview checks. Run it against the built
frontend as described in [application checks](application-ci.md). Private pilot
sources, dependency images and render evidence remain outside this repository.
