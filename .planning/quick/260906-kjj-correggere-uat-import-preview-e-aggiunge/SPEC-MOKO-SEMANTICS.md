# SPEC addendum — MOKO escape and inter-element source preservation

Status: proposed from the user's 2026-09-06 direction: "Sì procedi approvo". Under the old-coder approval rule, that message approves the direction but precedes this exact executable contract; implementation awaits explicit approval of this file.
Tier: 3 — localization parsing, lossless source preservation and future Bitbucket write safety.

This addendum extends only the approved MOKO layout contract. `SPEC.md`, `SPEC-MOKO-ADDENDUM.md` and `SPEC-IMPORT-CAPACITY-DUPLICATES.md` remain approved. Existing Android XML semantics do not change. Duplicate identities remain blocking for the whole mapping.

## User-visible behavior

- A MOKO `strings.xml` value containing a backslash sequence not recognized by the existing Android-compatible decoder is imported with that sequence preserved literally. For example, source characters `\\z` remain the two characters backslash and `z`; VerboFlex does not discard the slash, invent an escape meaning or rewrite Bitbucket.
- Known supported escapes keep their current decoded display meaning and retain source provenance. The parser must distinguish known and unknown sequences without accepting malformed Unicode escapes as valid text.
- Non-whitespace character data directly below `<resources>` and outside a supported resource element is retained as opaque source layout. It creates no translation key, is not shown as a translatable value and cannot shift or fabricate resource positions.
- Preview and import may accept those two MOKO-specific shapes only when every actual resource element remains structurally valid. Malformed XML, declarations/entities, unknown resource elements, invalid attributes, invalid Unicode escapes and unsupported nested markup continue to fail closed.
- Duplicate diagnostics scan all bounded MOKO scalar keys even when these preserved source shapes are present. A complete scan reports Babel's duplicate groups as complete; publication/import remains blocked by the duplicates. No clean subset is activated.
- A later VerboFlex edit and generated PR must apply a minimal locator-bound edit to the selected resource value while leaving unknown escape spelling and opaque inter-element text outside that value byte-for-byte unchanged. This task proves the serializer primitive locally; it does not create or send a Bitbucket PR.

## Executable scenarios

### M1 — Literal unknown escapes

Given a MOKO scalar string containing ordinary text and an unknown escape such as `\\z`, parsing succeeds and the canonical display text contains the exact literal `\\z`. Known escapes in the same value retain current behavior. The same input under the generic Android XML layout retains its existing rejection behavior.

### M2 — Unicode and terminal backslash safety

Malformed or incomplete `\\u` sequences and a terminal unpaired backslash remain rejected with the existing bounded `unsupported_structure` diagnostic. No replacement character, silent truncation or exception detail enters the public error.

### M3 — Opaque inter-element text

Given valid MOKO resources separated by non-whitespace direct text under `<resources>`, both resources retain their real zero-based positions and canonical values. The direct text produces no canonical identity. A source-preserving edit of either value leaves the direct text and all bytes outside the selected value unchanged.

### M4 — Structural boundaries

Unknown direct child elements, entity/DOCTYPE input, unsupported nested tags, invalid metadata and collection/scalar ambiguity still reject the complete MOKO mapping. The MOKO relaxation cannot be reached through a forged layout identity or ordinary Android path.

### M5 — Duplicate diagnostics and Babel evidence

Representative fixtures combining duplicates, unknown escapes and inter-element text produce a complete report with exact duplicate group and repeated-occurrence counts. The bounded read-only Babel probe at commit `6102ff5a2ba6a50bbf1d24f75f6e2a7fb3e7c625` must report all 145 known groups as a complete diagnostic scan if that commit is still authoritative, while canonical import remains `blocked_by_duplicates`. If the branch commit changes, report the new commit and counts rather than comparing unlike snapshots.

### M6 — Lossless property and capacity

Property tests generate bounded combinations of literal backslashes, known escapes, XML entities, Unicode text and opaque direct text. Parse/edit verification proves unchanged regions are byte-identical and resource positions stable. The existing 5,000-per-file, 50,000-per-mapping, 1 MiB file, 20 MiB discovery and 128 MiB canonical-output limits remain unchanged.

## Failure model

- Data corruption: byte-region comparison around minimal edits and golden fixtures.
- Semantic drift between MOKO and Android: paired tests with the same content and different exact layout authority.
- Hidden malformed Unicode: adversarial incomplete/oversized escape tests and property cases.
- False import success: duplicate-report and activation tests retain whole-mapping blocking and prior baseline.
- Parser bypass: forged layout/path tests, registry boundary tests and existing architecture guards.
- Proprietary data leakage: live probe emits only commit, counts, paths already approved for diagnostic output and fixed issue codes; no values, keys, raw XML or credentials.

## Setup and verification plan

- Continue quick task `260906-kjj` sequentially on `codex/merge-phases-4-5`; checkpoint commits remain authorized by the parent SPEC. No new branch, dependency, plugin or tool installation.
- Add sanitized fixtures under `backend/tests/fixtures/localization/moko_xml/` and extend the existing MOKO parser/preview/diagnostic tests. Add a small source-preservation module only if the current locator representation cannot prove M3 without coupling import parsing to a future PR implementation.
- RED first for M1–M5; GREEN with a MOKO-authority-specific policy. Do not loosen generic Android XML parsing.
- Run targeted tests, full randomized backend/frontend suites, mypy, Ruff/ESLint/TypeScript/build, 100% changed-line coverage, parser property tests and meaningful mutation controls. Update durable `EVIDENCE.md` with exact commands/results.
- Re-run the read-only Babel probe only; no provider writes and no automatic product configuration changes. Docker deployment waits for all remaining approved task slices and release gates.

## Must NOT

- No automatic correction, normalization or deletion of source text.
- No first/last-wins duplicate handling, partial activation or fabricated successful Babel import.
- No general relaxation of Android XML, XML entities, unsupported elements or nested markup.
- No raw source values/keys in logs, diagnostics, committed fixtures or evidence.
- No Bitbucket commit/PR/write, product mutation, push or merge in this slice.

## Residual assumptions

- Direct non-whitespace text under `<resources>` is layout-preserved but not a localization resource because it has no key or supported resource element.
- Unknown non-Unicode escape sequences are literal source text in MOKO; malformed Unicode escapes and a trailing backslash are errors because interpreting them would be ambiguous.
- This addendum proves the lossless edit primitive needed by a future PR flow but does not itself expose translation editing or create a remote PR.

## Revisions

- 2026-09-06 proposal: translates the user's approved direction into exact MOKO-only parsing and preservation rules. Awaiting explicit approval before RED tests and implementation.
