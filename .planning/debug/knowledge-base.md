# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## randomized-admin-role-order — ORM role collections sometimes reload outside the fixed domain order
- **Date:** 2026-08-27
- **Error patterns:** pytest-randomly role-order assertion failures, persisted `target.roles` differs from `FIXED_ROLE_ORDER`, passes in isolation, randomized full-suite failure
- **Root cause(s):** `User.roles` declared a many-to-many collection without SQLAlchemy `order_by`; PostgreSQL association query order was unspecified, so persisted reloads could differ from `FIXED_ROLE_ORDER` even though the service response projection was sorted.
- **Fix:** Added `order_by="Role.name"` to the `User.roles` SQLAlchemy relationship.
- **Files changed:** backend/src/verboflex/models/user.py, backend/tests/unit/services/test_admin_users.py
- **Why not caught:** No deterministic gate existed for ORM collection ordering; the behavioral combination test depended on incidental PostgreSQL ordering, while lint and type checks cannot infer the relationship's runtime order contract.
- **Recurrence guard:** Regression test `backend/tests/unit/services/test_admin_users.py::test_user_roles_relationship_declares_fixed_role_order` requires `User.roles` to declare `Role.name` ordering.
---
