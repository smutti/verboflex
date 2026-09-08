---
quick_id: 260908-sa7
status: complete
source_commit: de2342e
completed_at: "2026-09-08T20:38:00Z"
---

# Mapping-driven product repositories

The standalone product Repositories page now resolves its content exclusively from the current editable revision's saved mappings. It no longer presents every organization-wide registered repository as if it belonged to the product. Direct and split mappings contribute their referenced repositories, duplicates are removed, and cursor pagination is followed within explicit safety bounds.

The embedded repository step remains the organization-wide catalogue used to prepare a mapping. Its copy now explains that selecting or registering a repository does not persist a product association; that happens only when the mapping is saved.

The product-focused view adds a clear mapping-derived heading, semantic connection badges, responsive repository cards, loading and focused error states, an icon-led empty state, and direct actions to configure or manage mappings. The registration form now exposes required fields to assistive technology, links inline errors with `aria-describedby`, focuses the first invalid control, and announces pending submission text.

## TDD evidence

- RED: the standalone route showed unrelated globally registered repositories, required repository fields did not expose inline validation, and the browser retained focus on the submit button.
- GREEN: focused repository and product-configuration suites pass with mapping-only resolution, bounded multi-page lookup, accessible empty/error states, and focused inline validation.
- Regression: all 34 frontend test files pass, 638 tests total.
- Static/build gates: TypeScript, ESLint, Prettier, and the Vite production build pass.
- Local deployment: the frontend image was rebuilt and recreated; `http://localhost:8080/` returns HTTP 200 and the container is healthy.

## Residual note

Vite still reports the pre-existing advisory that the main JavaScript bundle is larger than 500 kB. This change adds no dependency.
