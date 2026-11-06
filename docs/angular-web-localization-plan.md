# Angular localization and web screenshot implementation plan

Status: implemented and locally verified through P6. Updated 6 November 2026.

See [delivered behavior and verification](angular-web-verification.md) and the
[configuration guide](angular-web-localization.md).

Support an Angular application using ngx-translate in one Bitbucket repository:
import the intended JSON catalogs, preserve interpolation and embedded markup during
editing, and render saved translations in three reproducible web scenarios. Deliver
working import, review, writeback and browser capture while preserving existing
Android Compose behavior.

The pilot has 296 string leaves in each of two nested JSON catalogs, 18 interpolated
messages per language and one message containing HTML. The two catalogs currently
contain identical text, predominantly in English. Parsing produced 592 values without issues; 103
existing JSON preview, import and writer tests passed. These results establish the
format baseline, not a completed browser integration. Build and render feasibility
is the first implementation gate.

Private application sources, translations, credentials and render receipts stay
outside this public repository. Commit only synthetic fixtures. Pilot paths and
scenario bindings are configured during onboarding rather than hardcoded in VerboFlex.

## Delivery scope

| Capability | Existing foundation | Required delivery |
| --- | --- | --- |
| Nested JSON | Recursive parsing and edits to original string tokens | Explicit catalog selection and actionable import diagnostics |
| Interpolation | Conservative placeholder handling for reuse; no ngx-translate edit contract | One versioned ngx-translate validator shared by editing, review, reuse and writeback |
| Source context | Kotlin/Java extraction for separate mappings | Optional Angular/TypeScript usage index on a direct mapping |
| Screenshots | Durable jobs, authenticated images, expiry and Compose runner | Web capture configuration, immutable bundles and an isolated browser runner |
| Reviewer interface | Scenario selection, saved proposals and stale-image handling | Web scenarios and exact nested-value selection |
| Application integration | Production Angular components and routes | Capture-only state, API fixtures, readiness and three scenario adapters |

The first release supports English and Italian, the standard application variant,
light appearance, and desktop/mobile viewport profiles. TWC and dark appearance are
future profiles, not implied coverage. Automatic exploration of arbitrary screens,
production login, live backend data, ICU messages, custom interpolation delimiters
and automatic translation of the Italian catalog are outside this delivery.

## Catalog selection and identity

Keep the pilot as a `direct` mapping, with `main` as its configured source branch,
English as the base language and `src/assets/i18n` as its localization root. Each
import resolves the branch once to an immutable commit. Code, scenario manifest and
catalogs for that execution must come from that same commit.

Add an optional, versioned localization profile to the mapping. It declares the
message syntax and an exact locale-to-file allowlist relative to the localization
root. For the pilot, select `en.json` and `it.json`. Reject duplicate locales,
duplicate paths, traversal and incompatible file/locale declarations. Adding a
language requires a candidate configuration, preview and publication. Existing
mappings without a profile retain their behavior.

Apply selection before layout detection and use it consistently during preview,
import, refresh, source provenance and writeback. Show excluded files and the reason
in preview. `template.json` must not produce a catalog in this profile. Do not
globally blacklist the filename, the namespace `NAV`, or the valid locale `nav`:
the observed false positive is a layout ambiguity, not an invalid language code.

Preserve the current canonical identity: scope, raw leaf key and `json_path` parent
selector. A runtime key such as `SECTION.NAME` is an additional address, not a new
database key. Build an explicit mapping from runtime key to canonical selector;
detect literal-dot versus nested-path collisions and require resolution before
enabling capture. Never split a dotted key and guess its original JSON structure.

Report empty values, missing locale counterparts, duplicate members and source
references absent from the catalogs. Identical source/target text is a nonblocking
diagnostic, never proof of an incorrect translation. Preserve existing approval
state. The initial text scan identified four apparently missing references. Implementation
verification with the Angular AST found that all four occur inside HTML comments;
they are correctly excluded from active usage evidence. For any genuinely missing
active reference, report its location and obtain wording through the review process;
do not invent translations or silently remove usages.

## Placeholder and markup contract

Introduce a mapping-selected `ngx_translate` syntax profile, leaving generic JSON,
Qt, Android, Apple strings and HTML email behavior unchanged. Tokenize the default
`{{ name }}` interpolation grammar, including dotted paths such as
`{{ data.item.name }}` and `{{ value.requiredLength }}`. Treat surrounding whitespace
as insignificant to token identity, preserve case and path segments, and retain
the original token spelling when the editor inserts a protected token.

Allow token reordering in translated prose but require the same token multiset.
Missing, additional, renamed or duplicated parameters and malformed delimiters
produce a field-level error. Unsupported syntax is diagnosed explicitly. This
profile does not reinterpret ICU plural/select messages as ordinary interpolation.

Derive each contract from the matching base-language value and selector. A base
text edit must preserve the contract of its imported revision; changing parameter
names is a developer change followed by reimport and translation reconciliation.
Missing base text or an incompatible imported target produces a diagnostic and
blocks approval/capture of that value until repaired, without dropping its catalog.

Allow an explicit set of rich-text JSON paths. For those values, parse the fragment
and preserve its element structure, attributes and interpolation tokens while
allowing text-node translation. Disallow added executable elements, attributes or
URLs. Show markup as protected content in the editor; never render repository HTML
directly in the VerboFlex page. The Angular fixture remains responsible for the
application's actual rendering. Plain JSON values cannot acquire HTML through editing.

Use the same backend validator for proposal saving, missing-value authoring,
approval, reuse suggestions, screenshot input creation and final writeback. Recheck
the current source/profile before submission so old proposals cannot bypass a new
contract. Reject invalid saves with useful errors and preserve the user's local
draft. Frontend token controls improve editing but are not the authority.

## Web context and capture contracts

Add capture configuration independently of `code_source.compose`, so a direct JSON
mapping can register a web application without fabricating separate Keys and
Translations repositories. Store application roots, manifest path, runner profile
and syntax rules on the candidate revision. Every relevant configuration change
invalidates preview confirmation and requires reimport of derived context.

Use TypeScript AST and Angular template parsing in a bounded extraction process.
Recognize literal `translate` pipe arguments, literal `TranslateService.instant`
and `get` calls, and the configured extraction marker. Ignore comments, ordinary
strings, generated clients and tests. Record unresolved dynamic references; they
do not become guessed keys. The JSON catalog remains authoritative for this direct
mapping, and an incomplete source scan must never delete imported translations.
Malformed selected sources or exceeded budgets cannot replace a previously complete
usage index with partial results.

The scenario manifest declares stable IDs, reviewer labels, fixture IDs, viewport
profiles and exact key-to-element bindings. It is read as data; build commands and
runner configuration belong to an operator-owned profile. Source extraction helps
find usages, while explicit scenario bindings determine what can be captured.
Keep declared, statically referenced and visibly observed evidence distinct.

Store the usage index, validated manifest and their provenance on the import
execution, include them in the staging digest and activate them atomically. Record
an application source reference even though the localization root is narrower than
the application root. Refreshing either context or catalogs invalidates captures
according to the existing source-authority rules.

Introduce a versioned capture bundle with an engine discriminator and separate web
and Compose payloads. The web request selects a registered `scenario_id`, a
`target_value_id` and a viewport profile; the server derives language, canonical
selector, commits and runner settings. A group can contain several `NAME` values,
so a raw leaf key or group ID alone is insufficient to select a web target.

Preserve legacy `preview_function` requests as Compose requests and retain the
version 1 Compose bundle and runner entry points. Additive Alembic migrations and
generated OpenAPI/MCP contracts must support reading existing capture receipts.
Deploy schema/read compatibility before enabling new web mappings; rollback disables
web capture without removing existing Compose configuration or data.

## Rendering a saved translation

1. The API checks membership, current import authority, scenario/target eligibility,
   proposal version and quotas. It stores an immutable request and dispatches its ID
   to Celery after commit. A screenshot never approves or commits a translation.
2. Celery resolves authorized source references and invokes the trusted isolation
   adapter. Repository downloads and builds never run in the API process. Supply
   fetched sources without provider credentials to the application build/browser.
3. The runner obtains a build keyed by application commit, lockfile, build profile,
   toolchain and fixture version. Determine the pilot-compatible Node/Angular versions
   in the first gate and pin the resulting image; do not assume the application's
   Angular version can use VerboFlex's Node 24 toolchain.
4. Serve the exact imported locale catalogs with the selected saved proposal applied
   by canonical path. Leave unrelated drafts out. Capture-only startup preloads the
   selected locale before components call `instant()` and fixes browser locale and
   local storage. Preserve the application's configured fallback policy explicitly.
   This pilot's HTTP-loaded JSON permits translation changes without rebuilding JS.
5. Start a fresh browser context, install synthetic authentication/API fixtures and
   open the selected route. Set time, animations, fonts, viewport and device scale
   deterministically. Complete the scenario's registered actions and wait for an
   explicit readiness signal and the target element.
6. Render a fresh PNG and bounded receipt containing the engine, commits, import and
   proposal versions, scenario/fixture/profile digests, locale and viewport. Validate
   the image, then recheck authority before storing and serving it. Reuse build
   artifacts, never substitute an old image for a requested new render.

Use Playwright's [request mocking](https://playwright.dev/docs/mock) and
[screenshot API](https://playwright.dev/docs/screenshots). Run both build and browser
inside the isolation boundary with resource/time limits, no host home or application
secrets, and no production network access. Dependency preparation is a separate,
controlled step. During rendering only the local fixture server is reachable;
unregistered requests fail the scenario. App-controlled scripts must not choose
arbitrary host commands or destinations.

Retain current cancellation, retry, idempotency, expiry, revoked-access and scheduler
recovery behavior. Reuse the existing screenshot queue with engine-aware trusted
dispatch; route web jobs to a dedicated pool if deployment needs separate capacity.
Keep existing input/image budgets. For highlighting, use reviewed DOM bindings and
verify visibility; return unavailable or ambiguous when a binding cannot establish
the target. Reused words alone are insufficient evidence, and key lookup is not
proof of visible text.

## Three initial scenarios

All fixture identities and contact values are synthetic. Register the standard
application variant, English/Italian, light appearance, desktop 1440 × 900 and
mobile 390 × 844. Scenario navigation uses stable element IDs or capture-only test
attributes so translated labels do not break navigation.

| Scenario | State and actions | Translation evidence | Acceptance |
| --- | --- | --- | --- |
| `sites.list` | Open the sites list with two synthetic sites and deterministic table data | Page title, search placeholder and a table header populated through `instant()` | Imported text and a saved replacement appear after startup; map/network dependencies cannot stall rendering |
| `tenant.create.open` | Open the tenant list for a synthetic site, then its real create-tenant dialog; populate valid synthetic contact and building/unit data | Dialog title, field labels and action buttons | The production dialog renders in both locales; no create operation reaches a real backend |
| `tenant.create.validation` | Reuse the dialog, enter a 98-character first name against its current 97-character limit, then blur it | The real control-errors component resolves `VALIDATE.MAX_LENGTH` and `{{ value.requiredLength }}` | The error visibly includes 97, the edited wording appears, no raw braces remain, and the invalid form cannot submit |

The validation scenario uses the actual Angular validator and component. Do not
insert an error message directly into the DOM or add a validator only for the image.
If a later application commit changes the constraint, its fixture contract must be
updated and reviewed rather than silently producing different evidence.

Provide synthetic profile, permission, sites, tenants, buildings and apartments API
responses required by these routes. Add a capture-only local map stand-in preserving
the map container dimensions; label it as simulated in scenario metadata. The sites
image verifies surrounding layout and translations, not live Google Maps fidelity.
Bundle required fonts/assets locally. Capture integration must be excluded from
production builds, with a build check proving that exclusion.

Do not promise every catalog key a screenshot: only keys explicitly bound to these
states are supported initially. For a long dialog, scroll its actual scroll container
to the selected target and capture the resulting viewport. Confirm the target is
visible before producing location metadata; a page-level full-height screenshot
alone does not expose content clipped inside a dialog.

## Implementation sequence

| Work package | Dependencies | Changes and principal files | Exit criterion |
| --- | --- | --- | --- |
| P0 Browser feasibility | None | Add a synthetic Angular fixture and prototype the three adapters; prepare the private pilot's isolated build profile | Pinned build starts with mocked auth/APIs; all three states show the intended target and one replacement string. Record toolchain, build/render timing and required app hooks |
| P1 Import profile | P0 | `models/product_mapping.py`, `schemas/admin_mappings.py`, `services/mappings.py`, `services/preview_jobs.py`, `services/repository_discovery.py`, preview/import tasks, admin mapping UI and an additive migration | Only configured locale files reach the selected layout; template exclusion, candidate invalidation, refresh and exact JSON writeback pass |
| P2 Message validation | P1 | `localization/placeholders.py`, a dedicated ngx-translate tokenizer/markup validator, review/authoring/reuse services, writeback and translation editor | Invalid parameters/markup are rejected at every mutation boundary; valid reorderings and repairs survive a round trip |
| P3 Angular context and capture schema | P1 | Bounded Angular extractor, import execution context/digest, `schemas/screenshots.py`, `services/screenshots.py`, mapping configuration and capture UI contracts | Direct mappings expose exact selector-bound scenarios; dynamic/missing usages are diagnostic; legacy Compose requests and receipts remain readable |
| P4 Web runner | P0, P2, P3 | New web bundle/JSON overlay module, trusted `tools/web_capture*` adapters, runner image/profile, `worker/screenshot_tasks.py` and the pilot capture-only harness | All three real browser scenarios produce fresh PNGs from pinned inputs through Celery; unexpected network calls, stale inputs and timeouts fail safely |
| P5 Reviewer workflow | P2, P3, P4 | `TranslationScreenshots.tsx`, `ScreenshotImage.tsx`, `TranslationDetailPage.tsx`, admin mappings, generated client/MCP contracts and all six UI catalogs | Select a nested value and scenario, save, capture, inspect, edit and regenerate; dirty drafts, stale images, failures and revoked access behave correctly |
| P6 Integration and release | P1–P5 | Synthetic provider/build smoke, API/worker/browser regressions, application CI and English guides | Full application checks pass; local private pilot validates the three scenarios; Compose smoke remains green; documentation matches delivered behavior |

P2 and P3 can be implemented independently after P1. Build caching follows a correct
uncached render, so it cannot hide an integration defect. Keep each work package
reviewable; do not merge all schema, UI and runner changes as one undifferentiated patch.

Existing implementation anchors:

- [JSON detection](../backend/src/verboflex/localization/preview/json.py),
  [canonical import](../backend/src/verboflex/localization/importing/json.py) and
  [writer](../backend/src/verboflex/localization/writing/json.py).
- [Mapping contracts](../backend/src/verboflex/schemas/admin_mappings.py),
  [import activation](../backend/src/verboflex/services/translation_imports.py) and
  [review validation](../backend/src/verboflex/services/translation_reviews.py).
- [Capture authority](../backend/src/verboflex/services/screenshots.py),
  [worker lifecycle](../backend/src/verboflex/worker/screenshot_tasks.py),
  [Compose bundle](../backend/src/verboflex/localization/code_keys/capture.py) and
  [reviewer controls](../frontend/src/features/translations/TranslationScreenshots.tsx).

## Verification and completion criteria

Use synthetic equivalents of the pilot's structure and states, with distinct English
and Italian content. A same-text target is a separate diagnostic fixture. Keep
private integration receipts outside tracked directories and ordinary CI.

| Layer | Required evidence |
| --- | --- |
| Import and serialization | Exact file selection; legitimate `nav` remains supported; excluded templates do not invalidate peers; duplicate/malformed/oversized input fails atomically; nested repeated leaf names and literal-dot ambiguity; missing/empty values; refresh and preservation of every unedited byte |
| Message semantics | Dotted/whitespace parameters, repeated tokens, valid reordering, missing/extra/renamed tokens, malformed/unsupported syntax, escaped braces, HTML tags/attributes and injection attempts; per-selector base matching; base edit and stale-profile reconciliation |
| API and persistence | Unauthorized capture/save/approval; direct mapping provenance; candidate invalidation; exact target/scenario membership; version 1 Compose compatibility; migrations; stale proposal and concurrent refresh; invalid placeholder submission through HTTP and MCP |
| Worker and isolation | Post-commit dispatch and rollback; broker recovery and duplicate delivery; cancellation/revocation during render; image/input bounds; unavailable runner; denied network/host access; rejected symlinks/output; cache isolation and fresh capture after changed text |
| Real browser | Three scenarios × two locales × two viewport profiles; a saved replacement visible in each; real maxlength interpolation; reliable `instant()` startup; target visibility inside dialog scrolling; simulated maps and no production calls |
| Product workflow | Import → edit → save → capture → approve → synthetic Bitbucket writeback → refresh; permissions and read-only views; expired/stale images; retry/reload; all six VerboFlex UI languages; controls usable at 320 px and 200% zoom |
| Compatibility | Existing JSON, HTML email, Kotlin/Java and Compose unit/API/browser smoke checks remain green |

The ordinary application smoke may use a synthetic renderer to verify transport,
authority and lifecycle, but that result does not satisfy the browser-rendering gate.
Add a real, pinned Chromium job that builds only the small synthetic Angular fixture.
Run the private application as a separate local integration check using the same
runner contract and three scenario definitions.

Follow [application checks](application-ci.md) for backend lint/type/tests, isolated
PostgreSQL/Redis/Celery checks, frontend lint/build/tests, OpenAPI/MCP drift and built
smoke. Generate clients before frontend tests. Run affected gates per work package
and the complete application gate at integration; do not rerun unrelated suites for
documentation-only changes.

Update `docs/code-keys-compose.md` for the shared capture boundary, add an English
web onboarding/runner guide, and update README, application CI and the public guide
only when each capability is implemented. Keep all six UI catalogs aligned and
leave repository keys, scenario labels and translation values unchanged by UI
localization. Publish no private application screenshots with the product website.

Completion requires importing the intended catalogs, preserving valid messages in
review and writeback, rendering the three actual application states from saved
translations, recording their exact provenance, and passing the compatibility gates.
P0 established Angular 17.3, Node 20.20.0, route-scoped dialog injection and locale
preloading. The private pilot passed the three-state matrix and additional target
bindings. Deployment remains an operator action using a reviewed application commit
and prepared runner profile.
