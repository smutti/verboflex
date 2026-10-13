# Code key import and Compose rendering acceptance contract

Implementation authorized by the user's “procedi con implementazione” after the
Compose-first plan. Pilot repositories: local `1953` and `babel`. Existing unrelated
changes in those repositories are preserved. VerboFlex work uses branch
`codex/code-keys-compose-preview`; no publishing or remote writes are part of validation.

The pilot uses `Res.strings.key` references in app code and MOKO XML definitions in
Babel. Extraction therefore includes configured resource references, in addition to
explicit constant declarations. Test fixtures remain synthetic and contain no private
application source or translations.

## Executable acceptance criteria

1. Parse Kotlin/Java syntax and extract only configured resource roots, declarations
   and localization calls. Preserve source locations and preview function identities.
   Ignore comments, ordinary text literals and `untranslated(...)`. Reject malformed,
   ambiguous or dynamic selected definitions without partially replacing an index.
2. Join exact code keys to separate localization values, including base text from the
   translations repository. Report missing keys and orphan translations. Preserve
   native selectors, real file provenance and existing import/writeback behavior.
3. Persist code-source configuration and imported provenance with revision authority;
   reads enforce current product membership. Source code is never a writeback target.
4. A screenshot request resolves an available preview for the selected translation,
   freezes its locale and content, and returns a durable job ID. HTTP retries are
   idempotent; a new request triggers a new render. Invalid/foreign inputs are denied.
5. Celery orchestrates rendering. Jobs survive browser navigation, have bounded attempts,
   cancellation and stale recovery, and recheck membership before publishing. Users
   without product access cannot obtain status, content or artifacts.
6. The Compose runner renders an actual preview with supplied translations, using a
   supported pinned toolchain. No emulator is required. Successful output has verifiable
   input provenance and a newly generated valid image. Build failure is never replaced
   by an old image. Execution isolation is explicit in the deployment instructions.
7. The translation context UI lists usages and previews, requests screenshots, displays
   progress/errors and an authenticated image, and restores an existing job after navigation.
8. Run relevant backend/API/migration, frontend and contract checks, plus actual Compose
   rendering on the pilot where possible. Record exact results and unresolved limits
   in `docs/code-keys-compose-evidence.md`; mocks alone do not establish rendering.

## Setup and dependency rationale

- `tree-sitter==0.26.0`: bounded syntax parsing without executing repository code.
- `tree-sitter-java==0.23.5`: Java syntax grammar.
- `tree-sitter-kotlin==1.1.0`: Kotlin syntax grammar.
- Compose screenshot Gradle tooling: pin a version compatible with the pilot's AGP
  8.12.3 and Kotlin 2.3.0 after the executable spike. Keep it in the capture integration.
- Existing pytest/Hypothesis, Ruff/mypy, Vitest/TypeScript and Docker test infrastructure
  supply validation. New tests live beside the corresponding backend and frontend areas.

## Failure model

Incomplete extraction must not delete keys; language imports activate atomically.
Cross-product IDs, revoked memberships and stale mapping revisions must fail closed.
Repeated deliveries cannot execute an accepted attempt twice or publish a stale result.
Repository code runs outside normal API/import processes without service credentials.
Source/translation revisions, build inputs and image identity must remain bound together.
Tests cover hostile paths, excessive inputs and subprocess failures as well as happy paths.
Independent fresh-agent verification is not claimed unless actually performed.

## Dependency correction (implementation evidence)

Pin `tree-sitter==0.25.2` instead of 0.26.0. On this Python 3.14 / macOS ARM
environment, 0.26.0 crashed during the complete pilot scan. With 0.25.2 the same
200 source files complete: 219 keys, 343 occurrences and 17 previews. Extraction
runs in a bounded child process so a native parser crash cannot kill an import worker.

## Review verification extension (12 October 2026)

The user requested a review and end-to-end verification after implementation. The
following regression criteria extend the existing contract without changing it:

- A configured Java call `demo.i18n.Translator.text` extracts the literal passed to
  imported `Translator.text`, and does not accept `Other.text` by method name alone.
- Reconnect retries a failed authenticated image GET for the same completed job;
  it does not create another capture job.
- Direct translation URLs expose the same lazy screenshot controls as the search
  context panel, including the dirty-edit guard and current saved proposal version.
- With worker umask 077, the container's unprivileged UID can read its input while
  other host users cannot traverse the private temporary exchange parent.
- Untrusted build output is discarded by the worker and Docker logging driver;
  a noisy build cannot fill host disks through either log spool.
- Repository code receives no writable host mount. PNG output is streamed with an
  8 MiB limit and a deadline; excessive output or a silent stalled process fails closed.
- The disposable built stack configures a synthetic Kotlin/Java-only repository and
  separate translations via HTTP, confirms/imports them through Celery, exposes missing
  keys in the browser, saves a proposal and captures it only when requested. The real
  scheduler/worker, idempotency and image authorization are exercised. Only external
  repository data and the Android renderer are fixtures; this does not replace the
  separate real Android rendering check.

No new dependencies or remote writes are required. The existing smoke lifecycle owns
all disposable services. New checks live in `tools/code_capture_smoke.py`,
`tools/code_capture_smoke_browser.mjs`, `tools/fixtures/code_capture_renderer.py` and
the existing parser, runner and screenshot component test files.
