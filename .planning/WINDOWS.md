---
schema_version: 1
open_count: 2
waived_count: 0
fixed_count: 5
total_count: 7
last_updated: 2026-08-24T17:27:29.176Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 01 | stub | backend/src/verboflex/api/v1/routes/auth.py | 33 | POST /auth/token remains an intentional callable 501 seam until Plan 01-06 | fixed |  | 2026-08-24T14:07:24.354Z | 2026-08-24T16:53:04.067Z |
| 2 | 01 | stub | backend/src/verboflex/api/v1/routes/auth.py | 52 | POST /auth/refresh remains an intentional callable 501 seam until Plan 01-07 | fixed |  | 2026-08-24T14:07:24.418Z | 2026-08-24T17:27:29.059Z |
| 3 | 01 | stub | backend/src/verboflex/api/v1/routes/auth.py | 69 | POST /auth/logout remains an intentional callable 501 seam until Plan 01-07 | fixed |  | 2026-08-24T14:07:24.475Z | 2026-08-24T17:27:29.119Z |
| 4 | 01 | stub | backend/src/verboflex/api/v1/routes/auth.py | 89 | POST /auth/change-password remains an intentional callable 501 seam until Plan 01-07 | fixed |  | 2026-08-24T14:07:24.532Z | 2026-08-24T17:27:29.176Z |
| 5 | 01 | stub | backend/src/verboflex/api/v1/routes/users.py | 23 | GET /users/me remains an intentional callable 501 seam until Plan 01-06 | fixed |  | 2026-08-24T14:07:24.591Z | 2026-08-24T16:53:04.133Z |
| 6 | 01 | stub | backend/src/verboflex/api/v1/routes/system.py | 22 | GET /system/status remains an intentional callable 501 seam until Plan 01-08 | open |  | 2026-08-24T14:07:24.648Z |  |
| 7 | 01 | stub | docker-compose.yml | 76 | Compose worker command and healthcheck target the Celery app intentionally deferred to Plan 01-08 | open |  | 2026-08-24T15:36:10.327Z |  |

````json
[
  {
    "id": 1,
    "kind": "stub",
    "phase": "01",
    "file": "backend/src/verboflex/api/v1/routes/auth.py",
    "line": 33,
    "description": "POST /auth/token remains an intentional callable 501 seam until Plan 01-06",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-24T14:07:24.354Z",
    "resolved_at": "2026-08-24T16:53:04.067Z"
  },
  {
    "id": 2,
    "kind": "stub",
    "phase": "01",
    "file": "backend/src/verboflex/api/v1/routes/auth.py",
    "line": 52,
    "description": "POST /auth/refresh remains an intentional callable 501 seam until Plan 01-07",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-24T14:07:24.418Z",
    "resolved_at": "2026-08-24T17:27:29.059Z"
  },
  {
    "id": 3,
    "kind": "stub",
    "phase": "01",
    "file": "backend/src/verboflex/api/v1/routes/auth.py",
    "line": 69,
    "description": "POST /auth/logout remains an intentional callable 501 seam until Plan 01-07",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-24T14:07:24.475Z",
    "resolved_at": "2026-08-24T17:27:29.119Z"
  },
  {
    "id": 4,
    "kind": "stub",
    "phase": "01",
    "file": "backend/src/verboflex/api/v1/routes/auth.py",
    "line": 89,
    "description": "POST /auth/change-password remains an intentional callable 501 seam until Plan 01-07",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-24T14:07:24.532Z",
    "resolved_at": "2026-08-24T17:27:29.176Z"
  },
  {
    "id": 5,
    "kind": "stub",
    "phase": "01",
    "file": "backend/src/verboflex/api/v1/routes/users.py",
    "line": 23,
    "description": "GET /users/me remains an intentional callable 501 seam until Plan 01-06",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-24T14:07:24.591Z",
    "resolved_at": "2026-08-24T16:53:04.133Z"
  },
  {
    "id": 6,
    "kind": "stub",
    "phase": "01",
    "file": "backend/src/verboflex/api/v1/routes/system.py",
    "line": 22,
    "description": "GET /system/status remains an intentional callable 501 seam until Plan 01-08",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-24T14:07:24.648Z",
    "resolved_at": null
  },
  {
    "id": 7,
    "kind": "stub",
    "phase": "01",
    "file": "docker-compose.yml",
    "line": 76,
    "description": "Compose worker command and healthcheck target the Celery app intentionally deferred to Plan 01-08",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-24T15:36:10.327Z",
    "resolved_at": null
  }
]
````
