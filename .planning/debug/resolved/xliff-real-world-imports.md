---
status: resolved
trigger: "Correggi tutti"
created: 2026-09-09
updated: 2026-09-09T14:31:47+02:00
---

# Debug Session: XLIFF real-world imports

## Symptoms

- **Expected behavior:** Valid XLIFF 1.2, 2.0, and 2.1 files from real open-source repositories import through preview and canonical parsing; invalid XLIFF 2.x inline/group structures are rejected; XLIFF files participate in post-rebase reconciliation; Docker services run the current implementation.
- **Actual behavior:** Valid XLIFF files using standard namespaced attributes or a 2.1 skeleton are rejected; six invalid Microsoft XLIFF 2.x fixtures are accepted; rewrite candidate filtering omits `.xlf` and `.xliff`; the running backend container exposes the pre-XLIFF format enum.
- **Errors:** `No supported localization layout was found in this source branch`; false-positive imports for invalid sc/ec/order/reordering and group xml:lang fixtures.
- **Timeline:** Observed on 2026-09-09 after adding native XLIFF support and testing it against public repositories.
- **Reproduction:** Run preview-to-canonical import probes against locize/xliff, symfony/translation, and microsoft/XLIFF2-Object-Model at the recorded commits; inspect the running backend container's CanonicalFormat enum.

## Current Focus

- hypothesis: Confirmed — four independent deterministic omissions cause the observed failures: blanket namespace rejection, absent core 2.1 skeleton handling, absent group/order/inline semantic validation, and a stale reconciliation suffix allowlist.
- test: Self-verification and fix-acceptance guardrail are complete.
- expecting: A real product import now discovers and imports supported XLIFF files without accepting invalid core documents, and rebase reconciliation retains `.xlf`/`.xliff` deltas.
- next_action: Archive the confirmed session and register its recurrence guard in the debug knowledge base.
- bug_class: Bohrbug (deterministic, input-dependent parser and suffix filtering failures)
- reasoning_checkpoint:
    hypothesis: The parser's blanket namespace rejection plus absent core-element and semantic validators cause valid XLIFF rejection and invalid XLIFF acceptance; the reconciliation suffix tuple independently rejects XLIFF deltas.
    confirming_evidence:
      - _require_attrs_unqualified rejects every attribute containing `}`, including XSI schemaLocation and XML namespace attributes present in valid public fixtures.
      - _walk_2x accepts group nodes without calling any attribute validator and rejects every file child other than group/unit, including the valid Symfony skeleton.
      - _content_nodes only checks inline tag names; it never matches sc/ec copyOf/startRef or compares canReorder sequences, and _unit_2x never enforces target order uniqueness.
      - The public-fixture probe rejects locize example12 and Symfony resources-2.1, accepts all six recorded Microsoft invalid fixtures, and import_jobs.py filters only xml/ts/json/strings rewrite paths.
    falsification_test: If the focused behavioral tests do not reproduce this exact valid-rejected/invalid-accepted/XLIFF-delta-rejected pattern, the mechanism is incomplete and implementation must not begin.
    fix_rationale: Explicit namespace/element allowlists and bounded semantic validators address the parser contract at the decision points that misclassify documents; extending the rewrite suffix tuple restores the missing format path.
    blind_spots: The parser intentionally supports a strict core bilingual subset, not every XLIFF module or source-only document; Docker image freshness is deployment state and must be verified after code acceptance.
    candidate_causes:
      - code: missing parser rules and stale rewrite suffix allowlist
      - environment: running Docker images predate the committed XLIFF implementation
      - data: public fixtures exercise legal namespace metadata and invalid semantic relationships absent from the original fixture set
    and_gate: yes — parser classification defects require specific real-world document shapes, and live-container failure additionally requires a stale image; the suffix defect is independent.
- tdd_checkpoint:
    test_file: backend/tests/unit/localization/importing/test_xliff.py; backend/tests/integration/test_import_jobs.py
    test_name: valid real-world XLIFF metadata/skeleton, six invalid Microsoft semantics, and XLIFF rewrite delta suffixes
    status: green
    failure_output: Initial RED was 8 parser failures plus 2 rewrite-path failures; the expanded held-out corpus exposed 5 additional RED semantic cases. All now pass.

## Evidence

- timestamp: 2026-09-09T12:01:00+02:00
  checked: Current XLIFF parser and real locize/Symfony fixtures.
  found: `_require_attrs_unqualified` rejects all namespaced attributes, and `_walk_2x` rejects `<skeleton>` at file scope.
  implication: Valid XSI schemaLocation/XML metadata and the core XLIFF 2.1 skeleton cannot pass the current parser.
- timestamp: 2026-09-09T12:02:00+02:00
  checked: Microsoft invalid fixtures and the 2.x parsing path.
  found: All six invalid fixtures produce canonical values with no issues; group attributes are not checked, target order is not validated across sibling segments, and inline tags receive vocabulary-only validation.
  implication: The false positives are direct consequences of missing semantic validation rather than preview-only behavior.
- timestamp: 2026-09-09T12:03:00+02:00
  checked: `_validated_rewrite_candidate` and the running backend container.
  found: Rewrite paths allow only `.xml`, `.ts`, `.json`, and `.strings`; Docker exposes CanonicalFormat without `xliff`.
  implication: XLIFF changes fail reconciliation after rebase, and the local runtime is stale even though source code contains XLIFF support.
- timestamp: 2026-09-09T12:04:00+02:00
  checked: Focused TDD regressions before implementation.
  found: Unit selection fails 8/8 exactly as predicted; integration selection fails 2/2 because both `.xlf` and `.xliff` deltas terminalize as import_failed.
  implication: The regression tests reproduce every reported code defect and provide an executable acceptance oracle.
- timestamp: 2026-09-09T12:05:00+02:00
  checked: Full public-corpus probe after the first GREEN implementation.
  found: The original 10 regressions pass, but five other files in Microsoft's core/invalid directory are accepted: mismatched xml:space, empty inline skeleton, non-empty external skeleton, wrong source xml:lang, and wrong target xml:lang.
  implication: Namespace acceptance must include value/inheritance semantics and skeleton href/content exclusivity, not just an attribute namespace allowlist.
- timestamp: 2026-09-09T12:06:00+02:00
  checked: Added focused regressions for the five newly exposed Microsoft invalid files.
  found: All five fail RED because the parser currently produces canonical values.
  implication: The remaining false positives are reproducible independently and can be fixed without broadening the provider scope.
- timestamp: 2026-09-09T12:07:00+02:00
  checked: GREEN regressions, adjacent suites, static checks, and complete public corpus.
  found: 152 focused/adjacent tests pass; Ruff and strict mypy pass. Public preview probe accepts locize 29/48 and Symfony 11/28 supported bilingual-core files, accepts three Microsoft core/valid subset files, and accepts zero of 122 Microsoft core/invalid files.
  implication: The parser now distinguishes supported valid documents from every invalid core fixture in the held-out corpus while retaining its explicit no-modules/source-only scope.
- timestamp: 2026-09-09T12:08:00+02:00
  checked: Full backend suite.
  found: 1728 tests pass; only the two known live-worker tests fail because no Redis worker is listening at their dedicated test endpoint 127.0.0.1:56379.
  implication: No code regression is observed outside the external worker-smoke fixture; deployment verification remains outstanding.
- timestamp: 2026-09-09T12:09:00+02:00
  checked: Rebuilt Docker backend and worker, live database migration, health probes, and an in-container locize import.
  found: Backend and worker are healthy, Celery ping succeeds, Alembic is at 0027_xliff_format, runtime CanonicalFormat includes xliff, and locize example12 imports 5 values with no issues inside the rebuilt container.
  implication: The running local application now contains and exercises the corrected XLIFF implementation.
- timestamp: 2026-09-09T12:10:00+02:00
  checked: Migration-chain source control state.
  found: 0027_xliff_format correctly follows 0026_duplicate_quarantine_layout and fresh database upgrades pass in the working tree, but 0026 remains untracked while 0027 is already committed.
  implication: The final commit must include 0026 so a clean checkout can resolve the migration chain.
- timestamp: 2026-09-09T14:31:47+02:00
  checked: Human verification checkpoint plus independent runtime verification.
  found: The user confirmed the original workflow fixed; independent checks confirm CanonicalFormat includes xliff, Alembic is at 0027 head, worker ping succeeds, and 26 selected XLIFF/rewrite tests pass.
  implication: The original issue is resolved end-to-end and the session can be archived.
- timestamp: 2026-09-09T14:31:47+02:00
  checked: Semantic knowledge-base indexing availability.
  found: No MemPalace CLI or configured wing is available in this workspace.
  implication: Semantic indexing was skipped explicitly; `.planning/debug/knowledge-base.md` remains the durable fallback.

## Eliminated

## Resolution

- root_cause: The strict XLIFF adapter implemented a namespace-free structural subset and tag-vocabulary checks but omitted explicitly allowed XML/XSI attributes, the core 2.1 skeleton, group/target-order/inline relationship validation, and the import rewrite suffix tuple was not extended when XLIFF was registered.
- fix: Added explicit bounded XML/XSI namespace rules, correct skeleton href/content alternatives, inherited xml:space and language validation, target-order uniqueness, sc/ec pairing and copy semantics, canReorder sequence/hierarchy checks, and `.xlf`/`.xliff` at every rewrite validation boundary; rebuilt the backend/worker images and upgraded the local database.
- oracle_type: specified — OASIS core semantics plus the Microsoft valid/invalid fixture classification and the application's explicit rebase reconciliation contract.
- verification:
    target_test: {result: pass}
    mutation_check: {result: skipped, reason_if_skipped: mutmut is configured only for authentication modules and has no XLIFF/import_jobs mutation target}
    no_op_deletion: {result: pass, deletion_justified_by_rca: false}
    adjacent_tests: {result: pass, suites_run: [152 focused parser/preview/conformance/API/import-job tests, Ruff, strict mypy, full public corpus, Docker runtime smoke]}
    revert_and_reconfirm: {result: pass, bug_returned_on_revert: true, fixed_on_reapply: true, evidence: exact agent-authored tests failed before implementation and passed unchanged after implementation}
    guardrail_verdict: accepted
    full_suite_note: 1728 passed; two environment-only worker smoke tests require the separate Redis endpoint 127.0.0.1:56379, which was not running
    human_verification: {result: pass, evidence: user confirmed fixed; runtime enum, Alembic head, worker ping, and 26 selected XLIFF/rewrite tests independently verified}
- files_changed: backend/src/verboflex/localization/importing/xliff.py; backend/src/verboflex/services/import_jobs.py; backend/tests/unit/localization/importing/test_xliff.py; backend/tests/integration/test_import_jobs.py; backend/alembic/versions/0026_duplicate_quarantine_layout.py must be included to make the already-committed 0027 dependency portable

## Prevention

- **Blameless 5-Whys — code/data branch:** The initial adapter was deliberately strict, but its structural allowlist treated every namespaced attribute as unsupported and its tests used only simplified fixtures. Real repositories introduced legal XML/XSI metadata, skeleton variants, and inline relationships that the fixture set did not represent. Because validation stopped at tag vocabulary, invalid relationship semantics could also pass. The actionable condition is that format adapters need valid and invalid conformance-corpus coverage at the same boundary as canonical import.
- **Blameless 5-Whys — configuration/environment branch:** XLIFF was registered in the canonical format enum without extending every reconciliation suffix boundary, while the local Docker runtime still used an older image. The feature therefore required both source-level registry consistency and image/database refresh checks. The actionable condition is to verify format registration across import, reconciliation, migration, and deployed-runtime boundaries together.
- **Why not caught:** Earlier parser tests did not exercise public XLIFF 1.2/2.x metadata and semantic-invalid fixtures, and no registry contract required `.xlf`/`.xliff` at every rewrite-validation boundary. Local source tests also could not detect a stale Docker image.
- **Recurrence guard:** `backend/tests/unit/localization/importing/test_xliff.py` now covers real-world schema metadata, skeleton alternatives, language/space inheritance, target ordering, and invalid inline relationships; `backend/tests/integration/test_import_jobs.py` covers both `.xlf` and `.xliff` reconciliation deltas. The public-corpus probe accepted zero of 122 Microsoft core-invalid documents, while the Docker smoke confirms the runtime enum and migration head.
