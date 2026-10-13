# Code keys and Compose capture: implementation evidence

Validation date: 12 October 2026. Implementation scope was authorized by “procedi con
implementazione”; the user then selected 1953 and Babel. The detailed executable
contract was written during the autonomous implementation; separate approval of that
file was not obtained. No remote writes, commits, live-database migrations or deployment
were performed. The branch is `codex/code-keys-compose-preview`.

The subsequent [review and end-to-end report](code-keys-compose-review.md) records
the additional fixes and current verification. Counts below describe the original
implementation-stage runs, not the later review state.

## Outcome and acceptance mapping

| Contract | Implementation and executable evidence |
| --- | --- |
| Kotlin/Java keys only | `test_code_keys.py`: configured constants, enum entries, resource references, aliases, calls, conservative overload evidence, malformed/dynamic inputs and comment/string exclusion property. `test_compose_capture.py` exercises the actual parser subprocess and crash/timeout paths. |
| Independent translations, exact join | `test_code_key_join.py`: actual base text, exact matching, missing/orphan keys, no invented base text, real translations-side provenance and parser failure. |
| Durable configuration and import | `test_admin_mappings.py::test_code_source_configuration_is_versioned_and_invalidates_preview`; `test_confirmed_layout_refresh.py::test_code_only_keys_preview_import_and_first_translation_authority` runs discovery, preview, confirmation, publication, import and activation through the existing worker with synthetic provider data. It also verifies writeback authority and rejects code-side destinations and unknown new identifiers. |
| Bounded source discovery | `test_bitbucket_discovery.py::test_code_source_traverses_android_package_directories_beyond_locale_budget` covers a 55-package tree while retaining file/byte/depth bounds. |
| Durable screenshot and permission boundaries | `test_code_screenshots.py`: immutable inputs, idempotency, current membership, revocation/regrant during rendering, foreign access, authenticated PNG delivery, queue recovery, interrupted workers, quotas, expiry, cancellation, failed output, changed inputs/source and saved-version validation. |
| Real Compose output | Actual 1953 Home preview, with Babel base/Italian values and a synthetic title override, rendered through `tools/compose_capture.py`; PNG visually inspected. Android compilation and five existing localization UI unit tests pass in the disposable copy. |
| User interface | `TranslationScreenshots.test.tsx`: saved version, dirty edit block, authenticated image, retry identity and navigation recovery. `CodeKeyCatalog.test.tsx`: lazy catalog, missing keys, cursor pagination and access failure. `CodeSourceFields.test.tsx` verifies typing multiple functions/previews. Full frontend suite passes. |
| Existing behavior | Existing mapping/import/publication/schema/maintenance and API inventories were updated for the additive fields, new model and eight new operations. Default localization-file mappings retain their behavior. |

Initial extraction stubs produced nine failing tests before implementation; the
initial join produced three failures. Overload/import and enum regressions were
observed failing before their fixes. Full-suite failures uncovered SQL JSON `null`
versus SQL `NULL` during mapping cloning, stale schema/API inventories, and test doubles
missing the new field. Those were repaired and rechecked. Added coverage-oriented tests
were not all written before implementation; mutation testing supplies additional,
limited negative evidence rather than a claim of strict TDD throughout.

## Checks

| Check | Result |
| --- | --- |
| Complete backend suite, disposable PostgreSQL 18/Redis/Celery | **3,442 passed** in 827.95 seconds; `/tmp/verboflex-code-final-backend`. Later additive tests are covered by the focused runs below. |
| Focused feature suite after the latest additions | **56 passed**. |
| Real synthetic Git runner checks | **2 passed**: commit-bound checkout ignores worktree changes; unsafe archive symlinks fail closed. |
| Backend API/schema boundary contract recheck | **55 passed**. |
| Complete frontend suite | **1,041 passed**, 62 files. |
| Frontend API/capture/catalog recheck | **24 passed**. |
| MCP connector suite | **40 passed**; regenerated MCP contract matches OpenAPI. |
| Ruff / mypy | Pass; mypy checks 211 source files. |
| ESLint / TypeScript / production build | Pass. The pre-existing large bundle warning remains. |
| API generation | Repeated generation produces byte-identical OpenAPI and client files. The ordinary `api:check` Git-diff check necessarily sees the intended, uncommitted API changes. |
| Docker Compose configuration | Base/production merge validates with synthetic configuration. No deployment. |
| Dependency audit | `pip-audit` reports no known vulnerabilities in the backend environment. 128 distributions audited. The three added tree-sitter distributions declare MIT licenses. |
| Secrets scan | Changed/new files scanned with detect-secrets; five candidates are synthetic test literals or pre-existing test data. No credentials were added. |
| Complexity review | Parser extraction has cyclomatic complexity 33, preview discovery 29, declarations 26 and capture snapshot 29. No numeric complexity threshold was established; this is maintainability debt, not a passing complexity gate. |

Coverage was run with a **100% failure threshold**, rather than a reporting-only
command. All 56 functional tests pass, but that coverage gate **fails**: 92.63% statement
coverage over the eight new backend modules (787 statements, 58 missed). It does not
cover every changed line in existing modules or the deployment scripts. Remaining
paths include defensive configuration/parser boundaries, some snapshot errors,
subprocess entry-point instrumentation and cancellation/list branches. No claim of
100% changed-line or branch coverage is made.

The repository's mutation tool, mutmut 3.7.0, ran in an independent temporary source
copy against the join and capture serializers. It generated and executed 290 mutants:
**239 killed, 51 survived**, no timeout/error/skipped mutants. Stronger escaping and
provenance tests improved the initial result of 222 killed / 68 survived. Survivors
include equivalent internal labels and exception-message changes, but not all have
been proven equivalent: this is **partial mutation assurance**, not a passing mutation
gate. The parser, database services and UI were not included in this mutation run.

The test runner uses pytest-randomly. Focused reruns and the complete suite use
independent randomized ordering. The final complete backend run passes all 3,442 tests. An isolated recheck without the gate's Redis setup
returned 503 in an existing revoked-password test; the fully provisioned gate verifies
that path. No assertion or timeout was relaxed to hide it. A final UI regression also demonstrated that typing separators lost multiple function names; the field now preserves editing text while updating the structured configuration.

## Real Android pilot

- Repositories: 1953 application and Babel translations, read locally.
- AST scan: 200 source files, 219 distinct keys, 343 occurrences, 17 previews.
- Base/Italian join for the pilot: 431 values, two missing keys and 4,071 translation
  keys outside the app catalog. These counts describe those two languages only.
- Toolchain: existing AGP 8.12.3 / Kotlin 2.3.0 / Gradle 8.13 / JDK 21;
  Compose screenshot plugin pinned to 0.0.1-alpha16.
- The Home fixture now uses its successful screen state and is internal/callable.
- First screenshot build: 96 seconds. Fresh subsequent capture: 18 seconds,
  nine tasks executed and 65 up-to-date. Rendering uses a new nonce and fresh output.
- Verified PNG: 1280 × 800; a synthetic translated title is visibly present.
- `compileDebugKotlin`, `compileDebugAndroidTestKotlin`, and the five
  `LocalizedUiStringsSmokeTest` tests pass (48-second combined Gradle run).
- Artifacts: `/tmp/verboflex-pilot-overlay.log`, `/tmp/verboflex-pilot-regression.log`;
  the preview image was copied into this chat's visualization directory.

Private application source and translations are not test fixtures in VerboFlex. The
pilot ran in a disposable copy, with the intended integration changes overlaid. The
current application HEAD does not yet contain these uncommitted changes. Production
capture must import a commit containing the plugin setup and fixture. Existing 1953
submodule changes and unrelated documents, and Babel's existing untracked files, were
preserved. Babel was not modified.

## Security review and deployment boundary

This was a self-review, not independent verification. Repository work stays in Celery;
HTTP only freezes authorized data. Requests carry a server-validated registered fixture
and immutable source identifiers, never shell commands or arbitrary repository URLs.
Acceptance is serialized per user/product, with two active requests per user, four per
product and twenty per user/hour. Retrying an ID does not start another build. Image
reads check current product access and the original actor's membership generation.
The runner subprocess receives only PATH/TMPDIR from the worker environment; a real
synthetic subprocess test verifies service secrets are not inherited.

The supplied production adapter launches an unprivileged, network-disabled container
with read-only root and source mirror, dropped capabilities and CPU/memory/process/time
bounds. This configuration was inspected, but an application-specific Linux image was
**not built or validated**. It needs JDK/SDK, credential-free prewarmed private
artifacts, a reviewed repository/profile mapping and initialized pinned submodules.
The normal API/import containers must not receive Docker access. The local pilot uses
an explicit development-workspace option and does not prove container isolation.

Static usage is evidence of possible execution, not proof that a key is visible in
all screen states. Property indirection, parameterized/multi-preview fixtures and
arbitrary service/view-model setup require adapters. Capture currently overlays Android
resource text/selectors; it does not recreate rich-text spans or custom translation
backends. The pinned Kotlin grammar can reject valid one-line class members; this
fails closed rather than silently producing a partial catalog. Build cancellation
prevents publication immediately but a running build can continue until its deadline.

The implementation and local pilot are reviewable; deployment and the strict
coverage/mutation gates are **not certified complete**. See
[the integration guide](code-keys-compose.md) for setup and operational limits.
