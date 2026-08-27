# Phase 02 Deferred Items

## Open

- **Plan 02-04 — randomized admin-user role-order isolation:** the default full backend run on 2026-08-27 produced 2 failures in `tests/unit/services/test_admin_users.py::test_every_non_empty_role_combination_round_trips_on_the_same_user_uuid` because persisted `target.roles` order differed from `FIXED_ROLE_ORDER` for two randomized parameter cases. The unchanged test passes 15/15 in isolation and the full suite passes 343/343 with `--randomly-dont-reorganize`. This test and `services/admin_users.py` predate Plan 02-04 and are outside the OAuth task boundary. A later maintenance plan should make role ordering or the assertion deterministic under `pytest-randomly`.
