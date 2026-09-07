---
quick_id: 260907-r2f
status: complete
code_commit: ac93493
completed_at: 2026-09-07T19:47:00+02:00
---

# Focused product workspace summary

## Delivered

- Added a user-facing **Product workspace** destination for every authenticated role, distinct from administrator-only **Product configuration**.
- Added an authorized product chooser with responsive visual cards and direct routes to `/products/:productId/strings`.
- Added a deterministic product identity palette derived from the immutable product id. The same color is applied to the product card, focus banner, initials badge, and active sidebar destination.
- Reused the existing translation search and detail components in a product-locked mode: the product selector is removed, clearing filters retains the product, detail links stay inside the product workspace, and Back returns to the focused search.
- Kept `/translations` as **All translations** for cross-product searches.
- Rebuilt the local Docker frontend; `verboflex-frontend-1` reached healthy state.

## TDD evidence

- Red: the first focused tests failed because the identity helper, product route, focused banner, and locked filter behavior did not exist.
- Green: the completed frontend suite passes with 623 tests, including focused routing for all four roles, stable color identity, locked product filters, colored sidebar state, and product-scoped detail return.

## Verification

- `npm test -- --run` — 34 files, 623 tests passed after the final test addition (one asynchronous router assertion was hardened and then passed three consecutive targeted runs).
- `npm run lint` — passed.
- `npm run build` — passed; the existing bundle-size advisory remains non-blocking.
- Docker frontend rebuild and health check — passed.

## Residual assumptions

- The existing translation-options endpoint remains the authority for active products visible to the signed-in user; this task adds no second product-access model.
- Product colors are intentionally automatic and not stored in PostgreSQL. They remain stable across renames as long as the product id is unchanged.
- This focused workspace exposes Strings now. Import diagnostics and duplicate warnings remain in administration until a later user-workspace information architecture explicitly promotes them.
- Authenticated browser visual inspection was not performed because the isolated inspection tab had no signed-in session; no credentials were entered. Component, routing, accessibility, build, and Docker checks cover the delivered behavior.
