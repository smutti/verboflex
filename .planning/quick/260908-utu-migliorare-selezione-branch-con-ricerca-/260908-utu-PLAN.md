---
quick_id: 260908-utu
status: complete
date: 2026-09-08
---

# Searchable branch selection and single-step target choice

## Goal

Make branch selection usable with large Bitbucket repositories: users can search loaded branches while remaining provider pages are fetched automatically, and choosing the first allowed target also makes it the default without a second control.

## Tasks

1. Add failing frontend tests for searchable source/target branch lists, automatic cursor pagination during search, preserved input focus, and automatic first-target default selection.
2. Implement accessible branch search, progressive loading feedback, filtered empty states, and inline default-target management without the redundant dropdown.
3. Run targeted tests, frontend typecheck/lint/format checks, and update the local frontend container for manual verification.

## Constraints

- Preserve multi-target mappings and the existing exact configured-branch recovery behavior.
- Keep Bitbucket branch names opaque and case-preserving; filtering is case-insensitive only in the UI.
- Do not modify unrelated dirty files.
