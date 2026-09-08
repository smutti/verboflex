---
quick_id: 260908-rfq
title: Apply semantic product status badge colors
status: complete
completed: 2026-09-08
code_commit: 351c47e
---

# Summary

Product lifecycle states now use a consistent semantic visual language in the administrator catalogue and product overview. Active and published states are green; inactive, draft, and not-configured states are yellow; existing destructive and error treatments remain red.

The shared Badge component now owns reusable success and warning variants, so future status surfaces can apply the same accessible color treatment without duplicating styling.

## TDD evidence

- RED: the product configuration tracer reported two failures because Active and Published still rendered as neutral outline badges.
- GREEN: the same tracer passes with explicit success and warning variants for lifecycle and revision states.

## Verification

- npm test -- --run src/features/admin/products/ProductConfiguration.test.tsx — 45 passed.
- npm test -- --run — 631 passed across 34 files.
- Targeted ESLint and Prettier checks — pass.
- npm run build — pass; the existing non-blocking Vite chunk-size warning remains.
- Docker frontend rebuilt and restarted; http://localhost:8080/ returns HTTP 200.
