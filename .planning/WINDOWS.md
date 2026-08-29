---
schema_version: 1
open_count: 0
waived_count: 0
fixed_count: 29
total_count: 29
last_updated: 2026-08-29T15:48:31.840Z
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
| 15 | 02 | deviation | backend/tests/unit/services/test_mappings.py |  | Preserved complete reusable repository fixture identity | fixed |  | 2026-08-27T12:46:58.050Z | 2026-08-27T12:47:24.532Z |
| 16 | 02 | deviation | frontend/openapi.json |  | Synchronized canonical OpenAPI and generated TypeScript client | fixed |  | 2026-08-27T12:46:58.120Z | 2026-08-27T12:47:24.591Z |
| 17 | 02 | deviation | backend/tests/api/test_admin_products.py |  | Admitted approved mapping subresources in product surface assertion | fixed |  | 2026-08-27T12:46:58.186Z | 2026-08-27T12:47:24.651Z |
| 18 | 02 | deviation | tools/verify_mapping_api_mutants.py |  | Closed candidate cursor dependency and corruption evidence gaps | fixed |  | 2026-08-27T12:46:58.248Z | 2026-08-27T12:47:24.709Z |
| 19 | 02 | deviation | backend/tests/unit/localization/preview/test_android_xml.py |  | Added mutation and branch-coverage evidence for every fail-closed boundary | fixed |  | 2026-08-27T19:10:58.316Z | 2026-08-27T19:11:19.519Z |
| 20 | 02 | deviation | backend/src/verboflex/localization/preview/android_xml.py |  | Reduced changed detector and core complexity below grade C | fixed |  | 2026-08-27T19:10:58.394Z | 2026-08-27T19:11:19.579Z |
| 21 | 02 | deviation | frontend/openapi.json |  | Synchronized the expanded browser-facing preview contract | fixed |  | 2026-08-27T19:10:58.457Z | 2026-08-27T19:11:19.640Z |
| 22 | 02 | deviation | backend/tests/integration/test_preview_jobs.py |  | Applied repository formatting to the tracer integration file | fixed |  | 2026-08-27T19:10:58.518Z | 2026-08-27T19:11:19.702Z |
| 23 | 02 | deviation | tools/verify_ios_preview_mutants.py |  | Added a drift-checked iOS parser and registry mutation proof after the planned gauntlet lacked format-specific mutation evidence. | fixed |  | 2026-08-27T19:53:44.141Z | 2026-08-27T19:53:48.678Z |
| 24 | 02 | deviation | backend/tests/unit/localization/preview/test_ios_strings.py |  | Closed detector and worker branch-coverage gaps and removed unreachable guards after the first changed-line gate reported 87 percent. | fixed |  | 2026-08-27T19:53:44.204Z | 2026-08-27T19:53:48.740Z |
| 25 | 02 | unmet-truth | docker/frontend.Dockerfile |  | Frontend container smoke cannot typecheck the Plan 02-15 admin client contract because frontend/openapi.json is not copied into the image build context. | fixed |  | 2026-08-28T07:58:44.977Z | 2026-08-28T15:52:44Z |
| 26 | 02 | deviation | tools/phase2_gauntlet.sh |  | Bound the exact dummy live credential fixture and replaced the obsolete live checkpoint assertion. | fixed |  | 2026-08-29T09:55:47.879Z | 2026-08-29T09:57:06.774Z |
| 27 | 02 | deviation | tools/phase2_smoke.sh |  | Added a bounded exact-address-in-use Compose retry after a transient host-port race. | fixed |  | 2026-08-29T09:57:06.841Z | 2026-08-29T09:57:06.951Z |
| 28 | 02 | deviation | frontend/src/api/admin-client-contract.test.ts |  | Scoped the generated credential-surface assertion to Bitbucket aliases after the initial full-client scan produced unrelated false positives. | fixed |  | 2026-08-29T15:48:27.121Z | 2026-08-29T15:48:31.780Z |
| 29 | 02 | deviation | frontend/src/api/client/index.ts |  | Included the canonical generator-owned client barrel omitted from the plan file list. | fixed |  | 2026-08-29T15:48:27.185Z | 2026-08-29T15:48:31.840Z |

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
  },
  {
    "id": 15,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/tests/unit/services/test_mappings.py",
    "line": null,
    "description": "Preserved complete reusable repository fixture identity",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T12:46:58.050Z",
    "resolved_at": "2026-08-27T12:47:24.532Z"
  },
  {
    "id": 16,
    "kind": "deviation",
    "phase": "02",
    "file": "frontend/openapi.json",
    "line": null,
    "description": "Synchronized canonical OpenAPI and generated TypeScript client",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T12:46:58.120Z",
    "resolved_at": "2026-08-27T12:47:24.591Z"
  },
  {
    "id": 17,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/tests/api/test_admin_products.py",
    "line": null,
    "description": "Admitted approved mapping subresources in product surface assertion",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T12:46:58.186Z",
    "resolved_at": "2026-08-27T12:47:24.651Z"
  },
  {
    "id": 18,
    "kind": "deviation",
    "phase": "02",
    "file": "tools/verify_mapping_api_mutants.py",
    "line": null,
    "description": "Closed candidate cursor dependency and corruption evidence gaps",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T12:46:58.248Z",
    "resolved_at": "2026-08-27T12:47:24.709Z"
  },
  {
    "id": 19,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/tests/unit/localization/preview/test_android_xml.py",
    "line": null,
    "description": "Added mutation and branch-coverage evidence for every fail-closed boundary",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T19:10:58.316Z",
    "resolved_at": "2026-08-27T19:11:19.519Z"
  },
  {
    "id": 20,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/src/verboflex/localization/preview/android_xml.py",
    "line": null,
    "description": "Reduced changed detector and core complexity below grade C",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T19:10:58.394Z",
    "resolved_at": "2026-08-27T19:11:19.579Z"
  },
  {
    "id": 21,
    "kind": "deviation",
    "phase": "02",
    "file": "frontend/openapi.json",
    "line": null,
    "description": "Synchronized the expanded browser-facing preview contract",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T19:10:58.457Z",
    "resolved_at": "2026-08-27T19:11:19.640Z"
  },
  {
    "id": 22,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/tests/integration/test_preview_jobs.py",
    "line": null,
    "description": "Applied repository formatting to the tracer integration file",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T19:10:58.518Z",
    "resolved_at": "2026-08-27T19:11:19.702Z"
  },
  {
    "id": 23,
    "kind": "deviation",
    "phase": "02",
    "file": "tools/verify_ios_preview_mutants.py",
    "line": null,
    "description": "Added a drift-checked iOS parser and registry mutation proof after the planned gauntlet lacked format-specific mutation evidence.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T19:53:44.141Z",
    "resolved_at": "2026-08-27T19:53:48.678Z"
  },
  {
    "id": 24,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/tests/unit/localization/preview/test_ios_strings.py",
    "line": null,
    "description": "Closed detector and worker branch-coverage gaps and removed unreachable guards after the first changed-line gate reported 87 percent.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T19:53:44.204Z",
    "resolved_at": "2026-08-27T19:53:48.740Z"
  },
  {
    "id": 25,
    "kind": "unmet-truth",
    "phase": "02",
    "file": "docker/frontend.Dockerfile",
    "line": null,
    "description": "Frontend container smoke cannot typecheck the Plan 02-15 admin client contract because frontend/openapi.json is not copied into the image build context.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T07:58:44.977Z",
    "resolved_at": "2026-08-28T15:52:44Z"
  },
  {
    "id": 26,
    "kind": "deviation",
    "phase": "02",
    "file": "tools/phase2_gauntlet.sh",
    "line": null,
    "description": "Bound the exact dummy live credential fixture and replaced the obsolete live checkpoint assertion.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-29T09:55:47.879Z",
    "resolved_at": "2026-08-29T09:57:06.774Z"
  },
  {
    "id": 27,
    "kind": "deviation",
    "phase": "02",
    "file": "tools/phase2_smoke.sh",
    "line": null,
    "description": "Added a bounded exact-address-in-use Compose retry after a transient host-port race.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-29T09:57:06.841Z",
    "resolved_at": "2026-08-29T09:57:06.951Z"
  },
  {
    "id": 28,
    "kind": "deviation",
    "phase": "02",
    "file": "frontend/src/api/admin-client-contract.test.ts",
    "line": null,
    "description": "Scoped the generated credential-surface assertion to Bitbucket aliases after the initial full-client scan produced unrelated false positives.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-29T15:48:27.121Z",
    "resolved_at": "2026-08-29T15:48:31.780Z"
  },
  {
    "id": 29,
    "kind": "deviation",
    "phase": "02",
    "file": "frontend/src/api/client/index.ts",
    "line": null,
    "description": "Included the canonical generator-owned client barrel omitted from the plan file list.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-29T15:48:27.185Z",
    "resolved_at": "2026-08-29T15:48:31.840Z"
  }
]
````
