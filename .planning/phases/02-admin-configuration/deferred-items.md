# Phase 02 Deferred Items

## Open

None.

## Resolved

- **Plan 02-04 — randomized admin-user role-order isolation:** resolved on 2026-08-27 by commit `be0a543`, which declares deterministic `User.roles` ORM ordering and adds a mapper-contract regression. Verification passed with the stable seed, adjacent admin tests 35/35, and the full randomized backend suite 344/344. Full investigation: `.planning/debug/resolved/randomized-admin-role-order.md`.
