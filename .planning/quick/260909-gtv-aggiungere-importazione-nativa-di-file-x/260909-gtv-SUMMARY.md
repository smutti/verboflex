---
phase: quick
plan: 260909-gtv
subsystem: localization-import
tags: [xliff, bitbucket, fastapi, react, postgresql, tdd]
requires:
  - phase: 4
    provides: Canonical localization import, preview, duplicate quarantine, and Bitbucket worker pipeline
provides:
  - Strict native XLIFF 1.2, 2.0, and 2.1 parsing
  - Automatic `.xlf` and `.xliff` discovery and preview
  - XLIFF duplicate quarantine, persistence, API contracts, and UI labeling
affects: [phase-4, localization, imports, migrations, openapi]
actuals:
  tokens: 86213
  tasks: 3
  commits: 5
tech-stack:
  added: []
  patterns:
    - Namespace-and-version dispatch for XLIFF dialects
    - Preview detection reuses the canonical parser grammar
key-files:
  created:
    - backend/src/verboflex/localization/importing/xliff.py
    - backend/src/verboflex/localization/preview/xliff.py
    - backend/alembic/versions/0027_xliff_format.py
  modified:
    - backend/src/verboflex/localization/importing/core.py
    - backend/src/verboflex/localization/importing/registry.py
    - backend/src/verboflex/services/repository_discovery.py
    - backend/src/verboflex/schemas/previews.py
    - frontend/src/features/admin/previews/ProductPreviewPage.tsx
key-decisions:
  - XLIFF 1.2 and 2.x use exact OASIS namespaces and versions rather than filename inference.
  - Unknown extensions and unsupported inline semantics fail atomically instead of being discarded.
  - No dependency, GitHub provider path, or language-count ceiling was added.
patterns-established:
  - XLIFF preview and import share one strict canonical grammar.
  - Duplicate-preserving parsing is restricted to the bounded diagnostic boundary.
requirements-completed: []
coverage:
  - id: D1
    description: XLIFF 1.2, 2.0, and 2.1 parse into deterministic bounded canonical values.
    verification:
      - kind: unit
        ref: backend/tests/unit/localization/importing/test_xliff.py and test_conformance.py
        status: pass
    human_judgment: false
  - id: D2
    description: Bitbucket discovers and previews `.xlf` and `.xliff` sources.
    verification:
      - kind: integration
        ref: backend/tests/integration/test_bitbucket_discovery.py and backend/tests/unit/localization/preview/test_xliff.py
        status: pass
    human_judgment: false
  - id: D3
    description: XLIFF duplicate identities are diagnosed and quarantined while unique values activate.
    verification:
      - kind: integration
        ref: backend/tests/unit/localization/test_duplicate_diagnostics.py and backend/tests/integration/test_translation_import_activation.py
        status: pass
    human_judgment: false
  - id: D4
    description: A real configured Bitbucket XLIFF repository can be selected, imported, and inspected in the browser.
    verification: []
    human_judgment: true
    rationale: Phase 4 repository-backed human UAT remains pending and was not auto-approved by this quick task.
duration: 34min
completed: 2026-09-09
status: halted
---

# Quick Task 260909-gtv: Native XLIFF Import Summary

**Native XLIFF 1.2/2.0/2.1 discovery, strict parsing, duplicate quarantine, persistence, and UI projection are implemented; final clean-output gates await the separately owned migration predecessor and existing repository gate cleanup.**

## Performance

- **Duration:** 34 min
- **Started:** 2026-09-09T10:22:37Z
- **Completed:** 2026-09-09T10:56:45Z
- **Tasks:** 3 implemented; Task 3 final clean-output gate halted on external repository state
- **Task commits:** 5

## Accomplishments

- Added strict, bounded XLIFF 1.2, 2.0, and 2.1 canonical parsing with `defusedxml`, exact namespace/version dispatch, deterministic selectors, and ordered semantic structure.
- Added `.xlf`/`.xliff` Bitbucket discovery, exact preview candidates, locale templates, duplicate diagnostics/quarantine, persistence constraints, public `xliff` literals, generated-client coverage, and the `XLIFF` UI label.
- Preserved the existing file, aggregate, value, output, depth, and diagnostic budgets without adding a language-count limit, dependency, or GitHub surface.

## TDD Evidence

### RED

- `58c4080`: parser/preview contract failed because XLIFF was absent from the closed registries; the preview assertion received no candidates.
- `9e697eb`: pipeline integration contract failed because discovery still ended with the prior JSON/iOS suffix vocabulary and did not admit `.xlf`/`.xliff`.

### GREEN

- Task 1 focused parser/preview/conformance suite passed after `c5abdeb`.
- Task 2 focused backend suite passed: **35 tests**.
- Task 2 frontend contract/UI suite passed: **96 tests across 2 files**.
- Shared-worktree full targeted backend regression passed: **627 tests** in 35.12 seconds.
- Cross-format conformance passed: **47 tests**.

## Task Commits

1. **Task 1 RED:** `58c4080` — define native XLIFF import contract
2. **Task 1 GREEN:** `c5abdeb` — add strict XLIFF parser and preview
3. **Task 2 RED:** `9e697eb` — define XLIFF pipeline integration contract
4. **Task 2 GREEN:** `faa270b` — integrate XLIFF import end to end
5. **Task 3 regression closure:** `eae8acc` — close XLIFF conformance gates

## Verification Results

### Passed

- Full targeted backend regression in the shared worktree: `627 passed`.
- `uv run ruff check src tests alembic`: passed.
- Focused formatting for XLIFF-owned parser, preview, and test files: passed (`6 files already formatted`).
- Focused strict typing for eight changed backend source files: passed (`Success: no issues found`).
- Frontend typecheck: passed.
- Frontend lint: passed with zero warnings.
- Frontend production build: passed; only the existing bundle-size advisory remained.
- Frontend focused generated-client/UI tests: `96 passed`.

### Final clean-output gate blockers

The planned exact aggregate command is not fully green from `HEAD` alone, so this summary is intentionally `status: halted` rather than `complete`.

1. `backend/alembic/versions/0027_xliff_format.py` correctly chains from `0026_duplicate_quarantine_layout`, but `backend/alembic/versions/0026_duplicate_quarantine_layout.py` is pre-existing untracked work owned outside this quick task. A clean detached worktree therefore stops Alembic with `KeyError: '0026_duplicate_quarantine_layout'`. The shared worktree, where 0026 exists, passes all 627 targeted tests. The unrelated 0026 file was not absorbed into these commits.
2. Full `ruff format --check src tests alembic` reports pre-existing formatting drift outside XLIFF-owned hunks. In clean committed state the remaining example is `repository_discovery.py:264`, blamed to prior commit `ac7f56dd`; in the shared dirty checkout additional unrelated files are also reported.
3. The exact bare `uv run mypy` command fails before source analysis because the package lacks a `py.typed` marker. Explicit strict checking of all changed XLIFF backend source files passes.
4. `npm run api:check` exposes pre-existing generated-contract drift from other concurrent features (product name filtering and durable latest-job endpoints). Regeneration changes unrelated generated hunks, which this task deliberately did not stage. Typecheck, lint, build, and focused XLIFF client tests pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Regression] Registered XLIFF in the shared conformance inventory**

- **Found during:** Task 3
- **Issue:** The all-format conformance suite required every closed canonical format to declare exact categories, constructs, and shared budgets.
- **Fix:** Added XLIFF category/construct inventories, fixture limits, adapter dispatch coverage, and the closed OpenAPI provenance literal.
- **Verification:** `47 passed` conformance tests and `627 passed` targeted backend tests.
- **Committed in:** `eae8acc`

**2. [Rule 1 - Regression] Aligned the migration-head assertion**

- **Found during:** Task 3
- **Issue:** The existing migration regression still expected the prior head after introducing revision 0027.
- **Fix:** Updated the exact expected revision to `0027_xliff_format` without weakening downgrade assertions.
- **Verification:** Full migration-containing suite passed in the shared worktree.
- **Committed in:** `eae8acc`

## Residual Limitations

- Import support intentionally covers the locked OASIS core subset. Extension namespaces, unknown inline elements, processing instructions, DTD/entities, mixed language pairs, and ambiguous/malformed identities fail atomically.
- This quick task imports and projects XLIFF; it does not add XLIFF write-back/serialization or GitHub integration.
- Phase 4 human UAT against a real repository remains independent and pending.

## User Setup Required

None for code or schema generation. The existing configured Bitbucket connection is used.

## Next Step

Commit the separately owned migration `0026_duplicate_quarantine_layout.py` and reconcile the existing formatting, mypy invocation, and generated OpenAPI drift. Then rerun the exact Task 3 aggregate gate and change this summary to `status: complete` only after it passes from committed output.
