---
quick_id: 260909-gtv
type: quick
status: planned
description: Aggiungere importazione nativa di file XLIFF 1.2 e 2.x con discovery, preview, parser canonico e diagnostica duplicati
autonomous: true
tdd: true
estimate:
  tokens: 45000
  raw_tokens: 45000
  tasks: 3
  confidence: low
files_modified:
  - backend/src/verboflex/localization/importing/core.py
  - backend/src/verboflex/localization/importing/registry.py
  - backend/src/verboflex/localization/importing/xliff.py
  - backend/src/verboflex/localization/preview/core.py
  - backend/src/verboflex/localization/preview/registry.py
  - backend/src/verboflex/localization/preview/xliff.py
  - backend/src/verboflex/services/repository_discovery.py
  - backend/src/verboflex/services/import_jobs.py
  - backend/src/verboflex/services/translation_search.py
  - backend/src/verboflex/models/translation.py
  - backend/src/verboflex/schemas/previews.py
  - backend/src/verboflex/schemas/translations.py
  - backend/alembic/versions/0027_xliff_format.py
  - backend/tests/fixtures/localization/xliff/manifest.json
  - backend/tests/fixtures/localization/xliff/valid_12.xlf
  - backend/tests/fixtures/localization/xliff/valid_12.expected.json
  - backend/tests/fixtures/localization/xliff/valid_20.xliff
  - backend/tests/fixtures/localization/xliff/valid_20.expected.json
  - backend/tests/fixtures/localization/xliff/valid_21.xliff
  - backend/tests/fixtures/localization/xliff/valid_21.expected.json
  - backend/tests/fixtures/localization/xliff/invalid_cases.json
  - backend/tests/fixtures/localization/conformance/manifest.json
  - backend/tests/unit/localization/importing/test_xliff.py
  - backend/tests/unit/localization/importing/test_conformance.py
  - backend/tests/unit/localization/importing/test_contracts.py
  - backend/tests/unit/localization/preview/test_xliff.py
  - backend/tests/unit/localization/test_duplicate_diagnostics.py
  - backend/tests/unit/test_phase4_parser_input_authority.py
  - backend/tests/integration/test_bitbucket_discovery.py
  - backend/tests/integration/test_translation_import_activation.py
  - backend/tests/integration/test_migrations.py
  - backend/tests/api/test_openapi_contract.py
  - backend/tests/api/test_translation_structure_roundtrip.py
  - frontend/openapi.json
  - frontend/src/api/client/index.ts
  - frontend/src/api/client/sdk.gen.ts
  - frontend/src/api/client/types.gen.ts
  - frontend/src/api/admin-client-contract.test.ts
  - frontend/src/features/admin/previews/ProductPreviewPage.tsx
  - frontend/src/features/admin/previews/ProductPreviewPage.test.tsx
must_haves:
  truths:
    - Bitbucket discovery includes bounded `.xlf` and `.xliff` files and automatically exposes valid XLIFF 1.2, 2.0, and 2.1 bilingual layouts in preview.
    - A confirmed XLIFF layout imports one canonical target-language value per translation unit or segment, retaining source text, target text, stable unit identity, and ordered inline/metadata semantics.
    - Duplicate XLIFF identities are reported and quarantined by the existing diagnostic workflow; unique values continue through activation.
    - XLIFF uses the existing file, aggregate-byte, value, output, depth, and diagnostic budgets without introducing a dedicated language-count ceiling.
    - Public preview and translation projections identify the format as `xliff`, and the administrator UI labels it as XLIFF.
    - No GitHub connection, API, credential, or provider path is introduced.
  artifacts:
    - path: backend/src/verboflex/localization/importing/xliff.py
      provides: Strict canonical XLIFF 1.2/2.x parser and duplicate-preserving inspector
    - path: backend/src/verboflex/localization/preview/xliff.py
      provides: Exact XLIFF layout detection and bounded preview samples
    - path: backend/tests/fixtures/localization/xliff/manifest.json
      provides: Executable supported/rejected syntax and safety-boundary ledger
    - path: backend/alembic/versions/0027_xliff_format.py
      provides: Fail-safe database format-constraint expansion
  key_links:
    - from: backend/src/verboflex/services/repository_discovery.py
      to: backend/src/verboflex/localization/preview/registry.py
      via: `.xlf`/`.xliff` source files enter the existing Bitbucket snapshot and XLIFF detector
    - from: backend/src/verboflex/localization/preview/xliff.py
      to: backend/src/verboflex/localization/importing/xliff.py
      via: preview reuses the canonical grammar and publishes only exact confirmable layouts
    - from: backend/src/verboflex/localization/importing/registry.py
      to: backend/src/verboflex/services/translation_imports.py
      via: `xliff` canonical values flow through the unchanged staged-manifest and activation boundary
    - from: backend/src/verboflex/schemas/previews.py
      to: frontend/src/features/admin/previews/ProductPreviewPage.tsx
      via: canonical OpenAPI regeneration adds the closed `xliff` literal consumed by the UI label map
---

# Quick task 260909-gtv — native XLIFF import

## Goal

Allow a user to select and import XLIFF files already stored in a configured Bitbucket repository. VerboFlex must discover and preview XLIFF 1.2, 2.0, and 2.1 bilingual documents automatically, persist their canonical values through the existing worker pipeline, and expose duplicate-key warnings without adding GitHub as a provider.

## Locked scope and assumptions

- Support the namespace-qualified OASIS XLIFF 1.2 document model (`file` languages and `trans-unit` source/target) and XLIFF 2.0/2.1 core model (root `srcLang`/`trgLang`, `unit`/`segment` source/target).
- Treat one XLIFF file as one bilingual source/target pair. XLIFF 1.2 documents with multiple `file` nodes are accepted only when every node declares the same normalized pair; mixed pairs fail atomically.
- Emit one canonical value per 1.2 `trans-unit` and per 2.x `segment`. Its `language` is the normalized target language, `source_text` is the visible source content, `translated_text` and `display_text` are the visible target content, including a valid empty target.
- Keep `CanonicalSelector(kind="scalar")`. For 1.2 use `resname` as `logical_key` when present, otherwise the required `trans-unit` id; for 2.x use `unit` name when present, otherwise the required unit id. Selector fields retain the dialect, semantic file identity, original unit id, and segment id or deterministic segment index so sibling segments remain individually addressable without using paths as identity.
- Preserve the accepted document hierarchy, namespace URI, version, ordered attributes, notes, source/target boundaries, original-data references, inline elements, text, and tails as bounded `xliff:*` structure nodes. The accepted core inline vocabulary is explicit: 1.2 `g`, `x`, `ph`, `bx`, `ex`, `bpt`, `ept`, `it`, and `mrk`; 2.x `cp`, `ph`, `pc`, `sc`, `ec`, `mrk`, `sm`, and `em`, together with core `originalData`/`data` where referenced. Unknown core elements, extension namespaces, invalid inline nesting/reference shapes, and ambiguous identities fail closed rather than being discarded.
- Use existing `defusedxml`; reject DTDs, entities, external references, processing instructions, invalid UTF-8/declarations, forbidden control characters, unsafe paths, missing languages, missing source/target pairs, and unsupported versions. Add no dependency.
- Retain the existing limits: 1 MiB per file, 20 MiB aggregate input, 500 files, 5,000 values per file, 50,000 values per mapping, 128 MiB mapping output, depth 12, bounded structure fields/nodes, and five safe issues. Add no language-count limit.
- Preserve all dirty worktree changes. Before each edit, inspect the current diff of the listed file and integrate with it; never restore, overwrite, stage, or commit unrelated changes.

## Tasks

<task type="tracer" tdd="true">
  <name>Task 1: RED then GREEN the XLIFF canonical parser and exact preview detector</name>
  <files>backend/src/verboflex/localization/importing/core.py, backend/src/verboflex/localization/importing/registry.py, backend/src/verboflex/localization/importing/xliff.py, backend/src/verboflex/localization/preview/core.py, backend/src/verboflex/localization/preview/registry.py, backend/src/verboflex/localization/preview/xliff.py, backend/tests/fixtures/localization/xliff/manifest.json, backend/tests/fixtures/localization/xliff/valid_12.xlf, backend/tests/fixtures/localization/xliff/valid_12.expected.json, backend/tests/fixtures/localization/xliff/valid_20.xliff, backend/tests/fixtures/localization/xliff/valid_20.expected.json, backend/tests/fixtures/localization/xliff/valid_21.xliff, backend/tests/fixtures/localization/xliff/valid_21.expected.json, backend/tests/fixtures/localization/xliff/invalid_cases.json, backend/tests/fixtures/localization/conformance/manifest.json, backend/tests/unit/localization/importing/test_xliff.py, backend/tests/unit/localization/importing/test_conformance.py, backend/tests/unit/localization/importing/test_contracts.py, backend/tests/unit/localization/preview/test_xliff.py</files>
  <behavior>
    - RED: golden fixtures for XLIFF 1.2, 2.0, and 2.1 assert exact keys, normalized target languages, source/target visible text, selectors, locators, and ordered semantic structure; the tests must initially fail because `xliff` is absent from the closed format registries.
    - RED: preview tests assert `.xlf` and `.xliff` candidate detection, target-locale path templating when the exact target locale occurs in a directory or filename, standalone per-path candidates otherwise, deterministic file/candidate order, all detected languages beyond the former 32-language boundary, and existing sample truncation without language truncation.
    - RED: hostile and ambiguous fixtures assert atomic safe failures for XXE/DTD/entity/PI input, wrong namespace/version, mixed 1.2 language pairs, missing or duplicate unit identities, invalid locale tags, malformed UTF-8, unsupported extensions, inline mismatches/references, over-depth trees, excessive attributes/nodes/values, file/aggregate/output boundaries, and concurrent same-input determinism.
    - GREEN: strict parsing returns no partial values when any file or structure fails; duplicate-preserving inspection returns every occurrence only to the diagnostic boundary while ordinary parsing emits `duplicate_key`.
  </behavior>
  <action>Write the fixtures and failing tests first and run them to record the intended RED caused by missing XLIFF support, not by syntax/import mistakes. Then add `xliff` to `CanonicalFormat`, `PreviewFormat`, their closed registries, and the explicit `xliff:*` structure vocabulary. Implement the adapter with the current immutable dataclasses, `CanonicalValueBuffer`, canonical ordering, fixed safe issue messages, locale normalization, and `defusedxml` protections. Build preview candidates from the same accepted grammar so preview cannot confirm a document the canonical parser rejects. Use namespace URI plus exact version to select the 1.2 or 2.x grammar; do not infer dialect from the filename. Commit RED and GREEN separately using the quick-task id.</action>
  <verify>
    <automated>cd backend &amp;&amp; uv run pytest tests/unit/localization/importing/test_xliff.py tests/unit/localization/preview/test_xliff.py tests/unit/localization/importing/test_contracts.py tests/unit/localization/importing/test_conformance.py -x</automated>
  </verify>
  <done>XLIFF 1.2/2.0/2.1 fixtures parse into deterministic, bounded canonical values; exact preview candidates are confirmable; hostile, ambiguous, duplicate, and over-budget inputs fail atomically with the closed diagnostic vocabulary.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: RED then GREEN XLIFF through Bitbucket discovery, duplicate quarantine, persistence, API, and UI</name>
  <files>backend/src/verboflex/services/repository_discovery.py, backend/src/verboflex/services/import_jobs.py, backend/src/verboflex/services/translation_search.py, backend/src/verboflex/models/translation.py, backend/src/verboflex/schemas/previews.py, backend/src/verboflex/schemas/translations.py, backend/alembic/versions/0027_xliff_format.py, backend/tests/unit/localization/test_duplicate_diagnostics.py, backend/tests/unit/test_phase4_parser_input_authority.py, backend/tests/integration/test_bitbucket_discovery.py, backend/tests/integration/test_translation_import_activation.py, backend/tests/integration/test_migrations.py, backend/tests/api/test_openapi_contract.py, backend/tests/api/test_translation_structure_roundtrip.py, frontend/openapi.json, frontend/src/api/client/index.ts, frontend/src/api/client/sdk.gen.ts, frontend/src/api/client/types.gen.ts, frontend/src/api/admin-client-contract.test.ts, frontend/src/features/admin/previews/ProductPreviewPage.tsx, frontend/src/features/admin/previews/ProductPreviewPage.test.tsx</files>
  <behavior>
    - RED: the Bitbucket source snapshot includes lowercase `.xlf` and `.xliff` files under the unchanged source budgets, while unrelated suffixes remain excluded and repository bytes never enter public responses.
    - RED: confirmed `xliff:` path identities select the current snapshot from immutable layout authority, including exact standalone paths and `{locale}` templates; moved matching files are accepted and files outside the template are rejected.
    - RED: duplicate units/segments appear in complete duplicate reports with safe path/position data, all their occurrences are quarantined, and remaining unique XLIFF values activate normally.
    - RED: migration upgrade permits `xliff` in both staged-value and active-locator format constraints; downgrade restores the prior vocabulary only when no XLIFF row exists and aborts without deleting data otherwise.
    - RED: preview and translation OpenAPI schemas expose the closed `xliff` literal, generated TypeScript matches canonical OpenAPI, activated structure survives authenticated detail projection, and the preview card renders the human label `XLIFF`.
  </behavior>
  <action>Add the failing discovery, parser-input-authority, duplicate, activation, migration, API-contract, structure-roundtrip, generated-client, and UI label tests before production changes. Extend only the existing Bitbucket source-discovery suffix list and confirmed-layout matcher; add no provider abstraction or GitHub surface. Register the XLIFF inspector in duplicate diagnostics. Expand the two database check constraints with a new Alembic revision chained after the current `0026_duplicate_quarantine_layout` head, using constraint names discovered from metadata; make downgrade fail before mutation when persisted XLIFF data would violate the old constraint. Extend backend literals, regenerate OpenAPI and the client via `npm run api:generate`, and add the exhaustive XLIFF label. Keep source bytes, XML fragments, exception text, and provider details outside every public response. Commit the GREEN integration separately.</action>
  <verify>
    <automated>cd backend &amp;&amp; uv run pytest tests/unit/localization/test_duplicate_diagnostics.py tests/unit/test_phase4_parser_input_authority.py tests/integration/test_bitbucket_discovery.py tests/integration/test_translation_import_activation.py tests/integration/test_migrations.py tests/api/test_openapi_contract.py tests/api/test_translation_structure_roundtrip.py -x &amp;&amp; cd ../frontend &amp;&amp; npm test -- --run src/api/admin-client-contract.test.ts src/features/admin/previews/ProductPreviewPage.test.tsx</automated>
  </verify>
  <done>A `.xlf` or `.xliff` file discovered from Bitbucket can be previewed, confirmed, parsed by the worker, duplicate-quarantined, persisted, searched, and displayed as XLIFF using generated closed contracts; no GitHub code or configuration exists in the change.</done>
</task>

<task type="auto">
  <name>Task 3: Run focused regression, static, contract-drift, and migration safety gates</name>
  <files>/Users/smutti/Documents/personal/verboflex/.planning/quick/260909-gtv-aggiungere-importazione-nativa-di-file-x/260909-gtv-SUMMARY.md</files>
  <action>Run the full XLIFF slice and the existing all-format conformance, mapping-capacity, output-budget, structure-bound, duplicate, import-activation, migration, and public-boundary regressions. Run Ruff, formatting, strict mypy, deterministic OpenAPI generation/client drift, frontend typecheck/lint/build, and inspect the final diff for unrelated files. Confirm the RED commit precedes GREEN commits. Record exact commands, counts, commit hashes, and residual limitations in the quick-task summary; do not mark the pending Phase 4 human UAT checks as passed.</action>
  <verify>
    <automated>cd backend &amp;&amp; uv run pytest tests/unit/localization tests/unit/test_phase4_parser_input_authority.py tests/integration/test_bitbucket_discovery.py tests/integration/test_translation_import_activation.py tests/integration/test_migrations.py tests/api/test_openapi_contract.py tests/api/test_translation_structure_roundtrip.py tests/unit/test_phase4_public_error_boundaries.py -x &amp;&amp; uv run ruff check src tests alembic &amp;&amp; uv run ruff format --check src tests alembic &amp;&amp; uv run mypy &amp;&amp; cd ../frontend &amp;&amp; npm run api:check &amp;&amp; npm run typecheck &amp;&amp; npm run lint &amp;&amp; npm run build</automated>
  </verify>
  <done>All targeted regressions and static/build/contract gates pass from committed outputs; the summary proves the RED-to-GREEN sequence and records that Phase 4 human UAT remains independent.</done>
</task>

## Threat model

| Threat | Severity | Disposition | Required mitigation |
|---|---|---|---|
| Repository-controlled XML expands entities or reaches external resources | high | mitigate | Parse only through `defusedxml`; reject DTD, entities, external references, and processing instructions with regression fixtures. |
| Deep/wide XLIFF or metadata expansion exhausts worker memory/CPU | high | mitigate | Enforce existing file/aggregate/value/output/depth/node budgets before publishing canonical values, plus explicit per-element attribute/reference bounds. |
| Namespace/version spoofing selects the wrong grammar | medium | mitigate | Dispatch only on the exact OASIS namespace URI and allowed version pair; reject filename-based inference and namespace extensions. |
| Unsupported inline or metadata content is silently dropped and later rewritten incorrectly | high | mitigate | Preserve every accepted semantic node/attribute/text/tail in ordered structure and reject any unrepresented construct atomically. |
| Duplicate units overwrite one another | high | mitigate | Keep strict canonical uniqueness; route duplicate-preserving parsing only to bounded reports and quarantine every duplicate occurrence. |
| Parser or provider detail leaks through diagnostics | medium | mitigate | Reuse the five fixed public issue categories/messages and prohibit source fragments, exception text, credentials, or provider payloads in schemas. |
| Downgrade makes persisted XLIFF rows invalid or deletes them | high | mitigate | Abort downgrade before constraint replacement when XLIFF rows exist; never delete or rewrite canonical data during migration. |

## Source coverage audit

| Source | Item | Task | Status |
|---|---|---:|---|
| GOAL | Native XLIFF import from configured Bitbucket repositories | 1-2 | COVERED |
| REQ | Quick task has no separate ROADMAP requirement id; it extends the active Phase 4 import capability | 1-3 | COVERED |
| RESEARCH | OASIS 1.2 `file` languages plus `trans-unit` source/target | 1 | COVERED |
| RESEARCH | OASIS 2.0/2.1 root languages plus `unit`/`segment` source/target | 1 | COVERED |
| CONTEXT | Preserve inline text and metadata semantics for safe round-trip authority | 1, 3 | COVERED |
| CONTEXT | No GitHub connection or provider work | 2 | COVERED |
| CONTEXT | No dedicated maximum-language cap | 1, 3 | COVERED |
| CONTEXT | Preserve file/byte/value safety budgets | 1, 3 | COVERED |
| CONTEXT | Duplicate diagnostics remain visible and quarantined | 1-2 | COVERED |
| CONTEXT | TDD RED then GREEN | 1-3 | COVERED |

## Success criteria

- A valid XLIFF 1.2, 2.0, or 2.1 bilingual file reaches a deterministic preview and canonical import using the existing Bitbucket/Celery pipeline.
- Inline codes and accepted metadata are represented in bounded ordered structure; unsupported semantics fail closed.
- Duplicate XLIFF identities are visible in the existing warning flow and excluded without first/last-wins behavior.
- Database, backend schemas, OpenAPI, generated TypeScript, and UI agree on the exact `xliff` format literal.
- Existing formats, budgets, security boundaries, and the absence of a dedicated language cap remain regression-protected.
- Only files owned by this quick task are committed; unrelated dirty worktree changes remain untouched.

## Output

Create `.planning/quick/260909-gtv-aggiungere-importazione-nativa-di-file-x/260909-gtv-SUMMARY.md` after implementation with RED/GREEN evidence, verification commands, commits, and residual limitations.
