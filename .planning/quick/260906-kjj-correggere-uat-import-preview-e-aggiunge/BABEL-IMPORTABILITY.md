# Babel — live read-only importability check

Date: 2026-09-06. User explicitly requested this check alongside approval of SPEC v1.

## Result

Provider access and bounded localization-subtree reads succeed. Current preview/import workflow cannot import the observed layout: the production preview registry returns zero candidates. This is not a successful canonical import or a passed UAT.

- Repository: comelit/babel.
- Source branch: master, as configured by the user. Default PR target was not substituted.
- Resolved commit: 6102ff5a2ba6a50bbf1d24f75f6e2a7fb3e7c625.
- Localization root: babel/src/commonMain/moko-resources.
- Scoped directory pages: 20.
- XML files: 19; total 3,570,592 bytes; largest 420,878 bytes.
- Language directories: base, bg, cs, de, el, es, fi, fr, hr, it, ja, nb, nl, pl, pt, ru, sl, tr, vi.
- All files parse as safe XML with root resources and string children. Base file has 4,321 string elements. This count is not a unique-key count or a successfully imported canonical count.
- Some files contain translatable attributes and nested child elements; flattening/skipping those to make preview pass is not acceptable.
- Actual production detect_preview_layouts(..., repository_side='direct'): zero candidates.

## Method and limits

Ran a separate read-only diagnostic Python process in the existing backend container, using the existing Bitbucket adapter/credential service and source-discovery budgets. A diagnostic adapter redirected only the initial directory listing to the observed localization root; every listed/read path was checked to remain within it. It did not change production source, persistent mapping root, worker jobs or data.

Called the real detector against every downloaded file in memory. Output contained paths, sizes and XML structure counts only, not translation bodies or credentials. No file, branch, PR, publication, mapping or canonical value was created/changed. Normal OAuth lease handling may maintain existing credential state.

Diagnostic command: docker exec -i verboflex-backend-1 python - < /tmp/verboflex-local-upgrade-GNqKTo/babel_probe.py. The temporary script is diagnostic evidence only, not the committed gauntlet or a durable integration test. Add a parameterized durable live probe if the extension proceeds.

## Why SPEC v1 is insufficient for Babel

The approved optional source-root feature solves the irrelevant-directory scan. It does not add layout recognition. The current Android preview detector only accepts paths shaped as res/values[-language]/*.xml, and its plain-string preview rejects translatable attributes and nested XML children. Babel's observed moko-resources/base/strings.xml and moko-resources/<language>/strings.xml do not satisfy that contract.

Supporting Babel requires a separately explicit MOKO-layout/preview contract and regression fixtures, including nested content and metadata preservation through canonical import/refresh. Existing Android layouts must retain their behavior; do not move or rewrite Babel's source files or pretend they are res/values files.

SPEC v1 remains approved. No implementation work has been claimed complete. New MOKO support is pending user direction, rather than silently added to v1.
