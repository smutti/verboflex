---
schema_version: 1
open_count: 0
waived_count: 0
fixed_count: 14
total_count: 14
last_updated: 2026-08-27T11:26:35.292Z
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
| 6 | 01 | stub | backend/src/verboflex/api/v1/routes/system.py | 22 | GET /system/status remains an intentional callable 501 seam until Plan 01-08 | fixed |  | 2026-08-24T14:07:24.648Z | 2026-08-26T08:13:30.100Z |
| 7 | 01 | stub | docker-compose.yml | 76 | Compose worker command and healthcheck target the Celery app intentionally deferred to Plan 01-08 | fixed |  | 2026-08-24T15:36:10.327Z | 2026-08-26T08:13:30.166Z |
| 8 | 02 | deviation | backend/tests/api/test_admin_repositories.py |  | Closed repository validation branches and added reproducible mutation proof after the first coverage gate reported 93.36%. | fixed |  | 2026-08-27T06:02:12.251Z | 2026-08-27T06:03:19.868Z |
| 9 | 02 | deviation | backend/tests/api/test_openapi_contract.py |  | Added exact repository operations and regenerated canonical OpenAPI after full regression exposed contract drift. | fixed |  | 2026-08-27T06:02:12.311Z | 2026-08-27T06:03:19.935Z |
| 10 | 02 | deviation | backend/tests/unit/services/test_admin_users.py | 159 | Randomized parameter order can expose nondeterministic persisted role ordering; isolated and deterministic full runs pass. | fixed |  | 2026-08-27T07:45:12.335Z | 2026-08-27T11:26:11.588Z |
| 11 | 02 | deviation | backend/tests/api/test_openapi_contract.py |  | Corrected a RED assertion whose generic content token collided with required OpenAPI media metadata. | fixed |  | 2026-08-27T11:26:24.789Z | 2026-08-27T11:26:35.111Z |
| 12 | 02 | deviation | frontend/src/api/client/index.ts |  | Regenerated the checked-in TypeScript client after canonical discovery operations changed. | fixed |  | 2026-08-27T11:26:24.852Z | 2026-08-27T11:26:35.171Z |
| 13 | 02 | deviation | tools/verify_bitbucket_http_adapter_mutants.py |  | Realigned the prior HTTP mutation subject with the new streamed response implementation. | fixed |  | 2026-08-27T11:26:24.911Z | 2026-08-27T11:26:35.233Z |
| 14 | 02 | deviation | backend/tests/api/test_admin_repositories.py |  | Expanded the repository surface regression after full randomized tests exposed the approved read-only subresources. | fixed |  | 2026-08-27T11:26:24.970Z | 2026-08-27T11:26:35.292Z |

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
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-24T14:07:24.648Z",
    "resolved_at": "2026-08-26T08:13:30.100Z"
  },
  {
    "id": 7,
    "kind": "stub",
    "phase": "01",
    "file": "docker-compose.yml",
    "line": 76,
    "description": "Compose worker command and healthcheck target the Celery app intentionally deferred to Plan 01-08",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-24T15:36:10.327Z",
    "resolved_at": "2026-08-26T08:13:30.166Z"
  },
  {
    "id": 8,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/tests/api/test_admin_repositories.py",
    "line": null,
    "description": "Closed repository validation branches and added reproducible mutation proof after the first coverage gate reported 93.36%.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T06:02:12.251Z",
    "resolved_at": "2026-08-27T06:03:19.868Z"
  },
  {
    "id": 9,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/tests/api/test_openapi_contract.py",
    "line": null,
    "description": "Added exact repository operations and regenerated canonical OpenAPI after full regression exposed contract drift.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T06:02:12.311Z",
    "resolved_at": "2026-08-27T06:03:19.935Z"
  },
  {
    "id": 10,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/tests/unit/services/test_admin_users.py",
    "line": 159,
    "description": "Randomized parameter order can expose nondeterministic persisted role ordering; isolated and deterministic full runs pass.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T07:45:12.335Z",
    "resolved_at": "2026-08-27T11:26:11.588Z"
  },
  {
    "id": 11,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/tests/api/test_openapi_contract.py",
    "line": null,
    "description": "Corrected a RED assertion whose generic content token collided with required OpenAPI media metadata.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T11:26:24.789Z",
    "resolved_at": "2026-08-27T11:26:35.111Z"
  },
  {
    "id": 12,
    "kind": "deviation",
    "phase": "02",
    "file": "frontend/src/api/client/index.ts",
    "line": null,
    "description": "Regenerated the checked-in TypeScript client after canonical discovery operations changed.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T11:26:24.852Z",
    "resolved_at": "2026-08-27T11:26:35.171Z"
  },
  {
    "id": 13,
    "kind": "deviation",
    "phase": "02",
    "file": "tools/verify_bitbucket_http_adapter_mutants.py",
    "line": null,
    "description": "Realigned the prior HTTP mutation subject with the new streamed response implementation.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T11:26:24.911Z",
    "resolved_at": "2026-08-27T11:26:35.233Z"
  },
  {
    "id": 14,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/tests/api/test_admin_repositories.py",
    "line": null,
    "description": "Expanded the repository surface regression after full randomized tests exposed the approved read-only subresources.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T11:26:24.970Z",
    "resolved_at": "2026-08-27T11:26:35.292Z"
  }
]
````
