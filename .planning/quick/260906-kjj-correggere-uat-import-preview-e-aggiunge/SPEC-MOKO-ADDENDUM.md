# Proposed addendum — Babel's observed MOKO XML layout

Status: proposed, not approved. SPEC.md v1 remains approved unchanged.

## Purpose

Make the observed Babel localization layout eligible for the same bounded preview, canonical import, search and refresh workflow. This adds layout/preview support, not Bitbucket write-back, a serializer, a new identity policy or automatic translation editing.

## Acceptance scenarios

1. A synthetic fixture at moko-resources/base/strings.xml and moko-resources/it/strings.xml produces one exact layout candidate with both paths, with repository-relative provenance unchanged. The root's base marker is explicit; do not infer that base means English from its text. Require the existing explicit base-language authority before publication/import.
2. Plain and nested string content and translatable metadata are represented without dropping elements or silently flattening semantics; leverage the existing canonical Android XML structure where compatible. Preview must not accept a shape the canonical importer cannot preserve. Unsupported shapes produce an actionable failure, not a misleading partial success.
3. Duplicate keys, malformed XML, DTD/entities, unsafe paths and all existing size/page/structure budgets remain fail-closed. No new dependencies proposed.
4. Existing Android res/values layouts and the other three supported formats retain their current behavior; a mapping remains exactly one format/layout. Any proposed new wire enum must first be checked against exhaustive consumers and documented as a versioned/additive extension, not silently changed.
5. A real read-only Babel probe at the configured source branch verifies discovery, exact candidate membership and canonical parsing of all 19 current files, followed by isolated local import/search verification. Report excluded/nontranslatable structures and actual counts; do not compare different source commits as one result.
6. No remote writes or changes to the user's existing product/mapping are automatic. Use an isolated local test product/database for import proof; preserve exact branch and commit. The user still performs final UAT confirmation.

## Setup and evidence

Extend the approved TDD/gauntlet setup. Add synthetic, non-proprietary fixtures under backend/tests/fixtures/localization/moko_xml/ and focused detector/import tests under backend/tests/unit/localization/. Persist a parameterized read-only probe at tools/check_repository_importability.py; do not commit repository contents or credentials. Report source-specific results in this quick task's EVIDENCE.md and retain BABEL-IMPORTABILITY.md as pre-fix history.

If semantic inspection reveals further unsupported features, surface them as additional contract gaps before implementation rather than dropping data.
