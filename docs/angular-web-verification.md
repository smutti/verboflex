# Angular web localization verification

Local implementation validation, 6 November 2026. All committed fixtures are synthetic.
Private application sources, capture overlays and images are held outside this repository.

## Delivered behavior

- Candidate-owned exact JSON catalog selection, including preview exclusions and a direct-mapping database constraint.
- ngx-translate parameter and rich-text validation during saving, authoring, approval, reuse, capture and writeback.
- Angular/TypeScript AST usage evidence, exact nested-value identity, immutable import context and collision diagnostics.
- Three registered web scenarios with API fixtures, real Angular reactive-form validation, desktop/mobile profiles and saved-proposal overlays.
- Celery dispatch into a rootless container with networking disabled, offline application builds, bounded receipts and fresh Chromium captures.
- Reviewer target/scenario/viewport controls, stale-image handling, editor token controls and all six interface catalogs.
- Legacy Compose input compatibility, generated API/MCP contracts, migration 0055 and English onboarding/CI guides.

## Completed checks

| Check | Result |
| --- | --- |
| Backend complete suite | 3,762 passed, one skipped in 32m 15s; the skipped real web integration test passed in the separate isolated capture gate below |
| Final web unit regressions | 40 passed across context, profile, message and receipt contracts; the final 13 added cases also passed in focused unit/integration runs after full-suite collection |
| Actual API → Redis → Celery → offline Angular build → Chromium → authenticated image | 12 successful captures: three scenarios × English/Italian × desktop/mobile; distinct render IDs and matching PNG/input digests |
| Isolated Chromium negative contracts | 12 passed, including external requests, WebSockets, unexpected API requests, ambiguity, clipping, fixed dialog portals and placeholder visibility |
| Receipt authority | 10 passed; altered image/input/source/manifest digests, commit, scenario, language and viewport are rejected |
| Profile preview → worker import → HTTP save/approval → JSON writer → worker refresh | Passed; malformed excluded template is not fetched, invalid saved/retained parameters are rejected, all unrelated bytes are preserved |
| Candidate profile API | Passed; round trip and preview invalidation without mutating the active revision |
| VerboFlex review browser | 10 passed, including Compose/HTML compatibility, exact web targets and stale captures at narrow/desktop widths |
| Built application smoke | Passed functional, recovery, approval-branch, shared MOKO, Compose capture and redaction checks; final cleanup recorded by the harness |
| Frontend complete suite | 1,187 passed across 72 files |
| Frontend static checks | ESLint, TypeScript and production build passed |
| MCP connector | 40 passed; Ruff, mypy and generated contract drift passed |
| Backend static checks | Ruff and mypy passed |
| Public guide | Build, artifact allowlist and local links passed; no private images included |

## Private pilot

The pinned Angular 17.3 application builds using Node 20.20.0. The capture-only entry
uses its actual sites-list and create-tenant components and its existing 97-character
validator. Locale catalogs load before `instant()` calls. Dialog services are provided
in the route injector so API fixture paths retain the synthetic site ID.

All twelve main combinations passed. Sixteen additional captures verify the page
title, visible search placeholder, save and cancel controls. The map is explicitly
simulated; required fonts are local. The normal application build succeeds and a
bundle/asset check confirms that the capture bootstrap and capture assets are excluded.
The list readiness check waits for the second synthetic site row before capture.
All 296 base messages pass parameter/markup validation. AST extraction examines
110 selected source files, yielding 514 occurrences and seven dynamic references.
The four apparent missing keys from the initial text scan are inside HTML comments;
there are no missing active static references in this scan. Identical source/target
catalogs remain an informational diagnostic.

The pilot overlay is a local integration artifact. Enabling a deployed project still
requires a reviewed application commit containing its capture entry/manifest, a
prepared digest-pinned dependency image, the exact mirror commit and runner settings.
No application repository push or running deployment change was performed.
The private component renders and the synthetic API/queue end-to-end checks are
separate evidence: the private application was not connected to a deployed VerboFlex
instance during this validation.

## Compatibility adjustments

The legacy preview and mapping response shapes remain unchanged when the optional
web data is absent. Contract and migration assertions now cover the additive fields
and revision 0055. Provider architecture checks distinguish the existing local
`SourceFileCache.put` call from an HTTP PUT; network mutation checks remain active.
The native-zoom browser fixes its locale to English, matching its selectors. The
browser-Back regression awaits destination rendering after the router state changes.
An isolated branch-workflow rerun and the final integrated smoke both passed after
an earlier target-verification timeout under concurrent test/build load.
