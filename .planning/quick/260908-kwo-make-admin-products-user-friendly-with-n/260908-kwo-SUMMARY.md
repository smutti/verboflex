---
quick_id: 260908-kwo
title: Make admin products user friendly
status: complete
completed: 2026-09-08
code_commit: 73c70f9
---

# Summary

The administrator Products catalogue now uses a fixed 50-item cursor page and loads subsequent pages automatically near the end of the list. The page includes a debounced product-name search, accessible status chips, stable row identity, an inline loading-more indicator, and centered icon-led empty states for both an empty catalogue and unmatched filters.

The admin collection API gained the optional `name` parameter. Search input is NFKC-normalized and case-folded, SQL wildcard characters remain literal, and filtered cursors are bound to the canonical name/status context. Unfiltered version-1 cursors remain valid.

## TDD evidence

- RED backend: name-filter contract initially returned `Product 000..002` instead of `Product 010..012`.
- GREEN backend: focused name/cursor test passes; full admin product API suite passes.
- RED frontend: initial request omitted the required `name` query field and the legacy selects/load-more control remained.
- GREEN frontend: complete Product configuration tracer passes with status chips, name debounce, automatic intersection loading, and centered empty state.

## Verification

- `uv run ruff check ...` and `uv run ruff format --check ...` — pass.
- `uv run pytest tests/api/test_admin_products.py tests/api/test_openapi_contract.py -q` — 41 passed.
- `uv run pytest tests/api/test_admin_product_search.py -q` — 1 passed.
- `npm run build` — pass; existing non-blocking Vite chunk-size warning remains.
- `npm test -- --run src/features/admin/products/ProductConfiguration.test.tsx src/api/admin-client-contract.test.ts` — 62 passed.
- Docker backend/frontend rebuilt and backend, worker, and frontend containers are healthy.
- Live `/api/v1/health` returns `{"status":"ok"}` and the served OpenAPI exposes optional `name` on `/api/v1/admin/products`.

## API gates

Boring ✓ · Compatibility ✓ · Authentication ✓ · Authorization ✓ · Idempotency N/A (read) · Blast radius ✓ (bounded pages) · Pagination ✓ (opaque cursor) · Expensive fields N/A · No implementation leakage ✓
