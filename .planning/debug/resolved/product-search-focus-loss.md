---
status: resolved
trigger: "c'è un bug quando inserisco nella serach della pagina prodotti, quando finisco di scrivere la search perde il focus e c'è un refresh della pagina che visivamente è brutto"
created: 2026-09-08T13:22:00Z
updated: 2026-09-08T13:46:00Z
mode: find-and-fix
---

# Product search focus loss

## Symptoms

Expected: typing in the Products search keeps keyboard focus and updates only the result region without a disruptive page-like refresh.
Actual: when the 300 ms debounce completes, the search input loses focus and the page visibly switches to the full loading skeleton.
Error message: none.
Timeline: introduced with the searchable infinite Products catalogue on 2026-09-08.
Reproduction: open the administrator Products page, focus Search products, type a query, and wait for the debounce to complete.

## Current Focus

hypothesis: Confirmed and fixed: a non-append filtered request set the whole collection back to `loading`, unmounting the focused input.
test: Deferred filtered-request regression asserts the exact search input remains connected, focused, and visible while a results-only loading status is shown.
expecting: The same DOM input survives the complete filtered request and the existing table remains visible until replacement results arrive.
next_action: User can refresh Products and verify uninterrupted typing with the compact Updating products status.
tdd_checkpoint: RED failed on disconnected input; GREEN passes with retained focus.

## Evidence

- `ProductsPage.loadProducts()` previously called `setLoadState("loading")` for every non-append request, including debounced name-filter changes.
- The filter controls were rendered only inside the `loadState === "ready"` branch, so the full loading state removed the input from the DOM.
- RED regression: `keeps the search mounted and focused while filtered results refresh` failed because the original search DOM node reported `isConnected === false`.
- GREEN regression proves the same DOM node remains connected and focused, the table remains visible, and an `Updating products` live status is shown while the response is pending.
- Same-authority filter refreshes retain results; an access-token authority change still uses the closed full-loading state to avoid exposing a prior user's collection.
- The rebuilt local frontend container is healthy and serves the updated application shell.

## Eliminated

- hypothesis: Browser navigation or a document-level reload causes the focus loss.
  evidence: The query is triggered by local React state/effects and calls the generated API client without route navigation.
- hypothesis: The debounce itself moves focus.
  evidence: Focus is lost only because the debounced request switches the component into a render branch that unmounts the input.

## Resolution

root_cause: Filter refreshes reused the initial-page `loading` state. Because filter controls lived inside the ready branch, React unmounted and later recreated the search field after every debounced query.
fix: Preserve the ready collection for same-authority filter requests, add a dedicated `refreshing` state with a compact live indicator, retain current results during the request, and keep full loading only for initial or changed-authority requests. Filter-refresh failures now leave current results available with an inline retry.
verification: 63 focused frontend tests pass; ESLint, TypeScript, production build, formatting, Docker rebuild, HTTP shell smoke, and container health pass. The existing non-blocking Vite chunk-size warning remains.
files_changed: frontend/src/features/admin/products/ProductsPage.tsx, frontend/src/features/admin/products/ProductConfiguration.test.tsx
