---
schema_version: 1
open_count: 4
waived_count: 0
fixed_count: 51
total_count: 55
last_updated: 2026-09-05T10:14:35.637Z
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
| 30 | 02 | deviation | tools/verify_mapping_api_mutants.py |  | Realigned mapping mutation subjects with the shared owned-revision paginator. | fixed |  | 2026-08-29T17:49:48.066Z | 2026-08-29T17:49:54.400Z |
| 31 | 02 | deviation | backend/tests/integration/test_bitbucket_http_adapter.py |  | Updated the stale credential fixture to the expiry-safe lease contract required by the acceptance gate. | fixed |  | 2026-08-29T17:49:48.147Z | 2026-08-29T17:49:54.461Z |
| 32 | 02 | deviation | frontend/src/features/admin/products/ProductConfiguration.test.tsx |  | Aligned existing frontend revision fixtures with the canonical required revision name. | fixed |  | 2026-08-29T17:49:48.220Z | 2026-08-29T17:49:54.522Z |
| 33 | 02 | deviation | frontend/src/features/admin/mappings/ProductMappingsPage.tsx |  | Prevented a successful mapping save from invalidating its own current-candidate collection | fixed |  | 2026-08-29T20:13:15.806Z | 2026-08-29T20:13:35.915Z |
| 34 | 02 | deviation | frontend/src/features/admin/useCursorCollection.ts |  | Preserved generated wire-shape authority for the generic cursor slice | fixed |  | 2026-08-29T20:13:15.871Z | 2026-08-29T20:13:35.980Z |
| 35 | 02 | deviation | frontend/e2e/admin-configuration.spec.ts |  | Verified current-source browser journeys after detecting a stale default nginx asset | fixed |  | 2026-08-29T20:13:15.939Z | 2026-08-29T20:13:36.042Z |
| 36 | 02 | deviation | tools/phase2_smoke.sh |  | Generated owner-only deployment secrets were required for real staging/production smoke and are fully scanned and cleaned | fixed |  | 2026-08-31T11:11:45.316Z | 2026-08-31T11:12:09.484Z |
| 37 | 02 | deviation | tools/phase2_gauntlet.sh |  | Mechanical Ruff formatting shifted three exact reviewed secret-fixture line numbers; policy entries were realigned | fixed |  | 2026-08-31T11:11:45.381Z | 2026-08-31T11:12:09.549Z |
| 38 | 03 | deviation | backend/tests/api/test_openapi_contract.py |  | Exact generated export assertions required identifier-boundary matching | fixed |  | 2026-09-03T10:30:58.460Z | 2026-09-03T10:31:32.155Z |
| 39 | 03 | deviation | frontend/src/features/admin/products/ProductConfiguration.test.tsx |  | Typed product fixtures required canonical affected_mapping_count alignment | fixed |  | 2026-09-03T10:30:58.526Z | 2026-09-03T10:31:32.223Z |
| 40 | 04 | stub | backend/src/verboflex/localization/importing/registry.py | 36 | Qt canonical dispatch intentionally returns a closed unsupported-structure result until Plan 04-03 supplies the adapter | fixed |  | 2026-09-04T20:50:55.925Z | 2026-09-05T07:29:46.875Z |
| 41 | 04 | stub | backend/src/verboflex/localization/importing/registry.py | 37 | JSON canonical dispatch intentionally returns a closed unsupported-structure result until Plan 04-04 supplies the adapter | fixed |  | 2026-09-04T20:50:55.994Z | 2026-09-05T07:29:46.939Z |
| 42 | 04 | stub | backend/src/verboflex/localization/importing/registry.py | 38 | iOS strings canonical dispatch intentionally returns a closed unsupported-structure result until Plan 04-05 supplies the adapter | fixed |  | 2026-09-04T20:50:56.071Z | 2026-09-05T07:29:47.002Z |
| 43 | 04 | deviation | backend/tests/unit/localization/importing/test_ios_strings.py | 196 | Corrected the Task 1 span-adjacency test to compare intentionally unequal adjacent-pair iterables with strict=False. | fixed |  | 2026-09-04T22:07:04.874Z | 2026-09-04T22:07:24.801Z |
| 44 | 04 | deviation | backend/src/verboflex/localization/importing/android_xml.py |  | Closed Android adapter calls with forged non-byte input. | fixed |  | 2026-09-05T07:29:19.950Z | 2026-09-05T07:29:47.064Z |
| 45 | 04 | deviation | backend/tests/unit/localization/importing/test_ios_strings.py |  | Replaced a collision-prone iOS redaction oracle. | fixed |  | 2026-09-05T07:29:20.013Z | 2026-09-05T07:29:47.126Z |
| 46 | 04 | deviation | backend/tests/fixtures/localization/android/valid_structured.expected.json |  | Updated the Android golden for the mandated global order. | fixed |  | 2026-09-05T07:29:20.076Z | 2026-09-05T07:29:47.187Z |
| 47 | 04 | deviation | backend/tests/unit/localization/importing/test_conformance.py |  | Closed defensive parser branches required by the next blocking checkpoint. | fixed |  | 2026-09-05T07:29:20.142Z | 2026-09-05T07:29:47.251Z |
| 48 | 04 | deviation | tools/phase4_parser_checkpoint.sh |  | Replaced a transitive-import persistence assertion with fail-closed SQLAlchemy method guards. | fixed |  | 2026-09-05T09:10:53.182Z | 2026-09-05T09:11:04.876Z |
| 49 | 04 | deviation | tools/phase4_parser_checkpoint.sh |  | Preserved actionable container failures and idempotent cleanup. | fixed |  | 2026-09-05T09:11:04.695Z | 2026-09-05T09:11:04.936Z |
| 50 | 04 | deviation | docs/evidence/phase-04-parser.md |  | Removed a self-triggering evidence sanitization phrase. | fixed |  | 2026-09-05T09:11:04.756Z | 2026-09-05T09:11:04.995Z |
| 51 | 04 | deviation | tools/phase4_parser_checkpoint.sh |  | Confined coverage data to the owner-only runtime directory. | fixed |  | 2026-09-05T09:11:04.816Z | 2026-09-05T09:11:05.058Z |
| 52 | 04 | lint-warning | backend/src/verboflex/localization/importing |  | Full backend mypy reports 12 pre-existing parser-module errors; Plan 04-08 focused model mypy passes. | open |  | 2026-09-05T09:29:10.936Z |  |
| 53 | 04 | deviation | backend/tests/unit/localization |  | Default backend pytest collection collides on duplicate importing/preview test basenames; Plan 04-08 verified the complete corpus in split runs. | open |  | 2026-09-05T09:29:11.095Z |  |
| 54 | 04 | deviation | backend/tests/architecture/test_phase2_scope.py |  | Phase 2 architecture guards still reject the Phase 4 canonical translation model modules | open |  | 2026-09-05T10:14:35.482Z |  |
| 55 | 04 | unrun-verify | backend/tests/worker/test_smoke_task.py |  | Broad worker smoke requires Redis and a Celery worker at 127.0.0.1:56379 | open |  | 2026-09-05T10:14:35.637Z |  |

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
  },
  {
    "id": 30,
    "kind": "deviation",
    "phase": "02",
    "file": "tools/verify_mapping_api_mutants.py",
    "line": null,
    "description": "Realigned mapping mutation subjects with the shared owned-revision paginator.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-29T17:49:48.066Z",
    "resolved_at": "2026-08-29T17:49:54.400Z"
  },
  {
    "id": 31,
    "kind": "deviation",
    "phase": "02",
    "file": "backend/tests/integration/test_bitbucket_http_adapter.py",
    "line": null,
    "description": "Updated the stale credential fixture to the expiry-safe lease contract required by the acceptance gate.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-29T17:49:48.147Z",
    "resolved_at": "2026-08-29T17:49:54.461Z"
  },
  {
    "id": 32,
    "kind": "deviation",
    "phase": "02",
    "file": "frontend/src/features/admin/products/ProductConfiguration.test.tsx",
    "line": null,
    "description": "Aligned existing frontend revision fixtures with the canonical required revision name.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-29T17:49:48.220Z",
    "resolved_at": "2026-08-29T17:49:54.522Z"
  },
  {
    "id": 33,
    "kind": "deviation",
    "phase": "02",
    "file": "frontend/src/features/admin/mappings/ProductMappingsPage.tsx",
    "line": null,
    "description": "Prevented a successful mapping save from invalidating its own current-candidate collection",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-29T20:13:15.806Z",
    "resolved_at": "2026-08-29T20:13:35.915Z"
  },
  {
    "id": 34,
    "kind": "deviation",
    "phase": "02",
    "file": "frontend/src/features/admin/useCursorCollection.ts",
    "line": null,
    "description": "Preserved generated wire-shape authority for the generic cursor slice",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-29T20:13:15.871Z",
    "resolved_at": "2026-08-29T20:13:35.980Z"
  },
  {
    "id": 35,
    "kind": "deviation",
    "phase": "02",
    "file": "frontend/e2e/admin-configuration.spec.ts",
    "line": null,
    "description": "Verified current-source browser journeys after detecting a stale default nginx asset",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-29T20:13:15.939Z",
    "resolved_at": "2026-08-29T20:13:36.042Z"
  },
  {
    "id": 36,
    "kind": "deviation",
    "phase": "02",
    "file": "tools/phase2_smoke.sh",
    "line": null,
    "description": "Generated owner-only deployment secrets were required for real staging/production smoke and are fully scanned and cleaned",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-31T11:11:45.316Z",
    "resolved_at": "2026-08-31T11:12:09.484Z"
  },
  {
    "id": 37,
    "kind": "deviation",
    "phase": "02",
    "file": "tools/phase2_gauntlet.sh",
    "line": null,
    "description": "Mechanical Ruff formatting shifted three exact reviewed secret-fixture line numbers; policy entries were realigned",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-31T11:11:45.381Z",
    "resolved_at": "2026-08-31T11:12:09.549Z"
  },
  {
    "id": 38,
    "kind": "deviation",
    "phase": "03",
    "file": "backend/tests/api/test_openapi_contract.py",
    "line": null,
    "description": "Exact generated export assertions required identifier-boundary matching",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-03T10:30:58.460Z",
    "resolved_at": "2026-09-03T10:31:32.155Z"
  },
  {
    "id": 39,
    "kind": "deviation",
    "phase": "03",
    "file": "frontend/src/features/admin/products/ProductConfiguration.test.tsx",
    "line": null,
    "description": "Typed product fixtures required canonical affected_mapping_count alignment",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-03T10:30:58.526Z",
    "resolved_at": "2026-09-03T10:31:32.223Z"
  },
  {
    "id": 40,
    "kind": "stub",
    "phase": "04",
    "file": "backend/src/verboflex/localization/importing/registry.py",
    "line": 36,
    "description": "Qt canonical dispatch intentionally returns a closed unsupported-structure result until Plan 04-03 supplies the adapter",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-04T20:50:55.925Z",
    "resolved_at": "2026-09-05T07:29:46.875Z"
  },
  {
    "id": 41,
    "kind": "stub",
    "phase": "04",
    "file": "backend/src/verboflex/localization/importing/registry.py",
    "line": 37,
    "description": "JSON canonical dispatch intentionally returns a closed unsupported-structure result until Plan 04-04 supplies the adapter",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-04T20:50:55.994Z",
    "resolved_at": "2026-09-05T07:29:46.939Z"
  },
  {
    "id": 42,
    "kind": "stub",
    "phase": "04",
    "file": "backend/src/verboflex/localization/importing/registry.py",
    "line": 38,
    "description": "iOS strings canonical dispatch intentionally returns a closed unsupported-structure result until Plan 04-05 supplies the adapter",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-04T20:50:56.071Z",
    "resolved_at": "2026-09-05T07:29:47.002Z"
  },
  {
    "id": 43,
    "kind": "deviation",
    "phase": "04",
    "file": "backend/tests/unit/localization/importing/test_ios_strings.py",
    "line": 196,
    "description": "Corrected the Task 1 span-adjacency test to compare intentionally unequal adjacent-pair iterables with strict=False.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-04T22:07:04.874Z",
    "resolved_at": "2026-09-04T22:07:24.801Z"
  },
  {
    "id": 44,
    "kind": "deviation",
    "phase": "04",
    "file": "backend/src/verboflex/localization/importing/android_xml.py",
    "line": null,
    "description": "Closed Android adapter calls with forged non-byte input.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-05T07:29:19.950Z",
    "resolved_at": "2026-09-05T07:29:47.064Z"
  },
  {
    "id": 45,
    "kind": "deviation",
    "phase": "04",
    "file": "backend/tests/unit/localization/importing/test_ios_strings.py",
    "line": null,
    "description": "Replaced a collision-prone iOS redaction oracle.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-05T07:29:20.013Z",
    "resolved_at": "2026-09-05T07:29:47.126Z"
  },
  {
    "id": 46,
    "kind": "deviation",
    "phase": "04",
    "file": "backend/tests/fixtures/localization/android/valid_structured.expected.json",
    "line": null,
    "description": "Updated the Android golden for the mandated global order.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-05T07:29:20.076Z",
    "resolved_at": "2026-09-05T07:29:47.187Z"
  },
  {
    "id": 47,
    "kind": "deviation",
    "phase": "04",
    "file": "backend/tests/unit/localization/importing/test_conformance.py",
    "line": null,
    "description": "Closed defensive parser branches required by the next blocking checkpoint.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-05T07:29:20.142Z",
    "resolved_at": "2026-09-05T07:29:47.251Z"
  },
  {
    "id": 48,
    "kind": "deviation",
    "phase": "04",
    "file": "tools/phase4_parser_checkpoint.sh",
    "line": null,
    "description": "Replaced a transitive-import persistence assertion with fail-closed SQLAlchemy method guards.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-05T09:10:53.182Z",
    "resolved_at": "2026-09-05T09:11:04.876Z"
  },
  {
    "id": 49,
    "kind": "deviation",
    "phase": "04",
    "file": "tools/phase4_parser_checkpoint.sh",
    "line": null,
    "description": "Preserved actionable container failures and idempotent cleanup.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-05T09:11:04.695Z",
    "resolved_at": "2026-09-05T09:11:04.936Z"
  },
  {
    "id": 50,
    "kind": "deviation",
    "phase": "04",
    "file": "docs/evidence/phase-04-parser.md",
    "line": null,
    "description": "Removed a self-triggering evidence sanitization phrase.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-05T09:11:04.756Z",
    "resolved_at": "2026-09-05T09:11:04.995Z"
  },
  {
    "id": 51,
    "kind": "deviation",
    "phase": "04",
    "file": "tools/phase4_parser_checkpoint.sh",
    "line": null,
    "description": "Confined coverage data to the owner-only runtime directory.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-05T09:11:04.816Z",
    "resolved_at": "2026-09-05T09:11:05.058Z"
  },
  {
    "id": 52,
    "kind": "lint-warning",
    "phase": "04",
    "file": "backend/src/verboflex/localization/importing",
    "line": null,
    "description": "Full backend mypy reports 12 pre-existing parser-module errors; Plan 04-08 focused model mypy passes.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-05T09:29:10.936Z",
    "resolved_at": null
  },
  {
    "id": 53,
    "kind": "deviation",
    "phase": "04",
    "file": "backend/tests/unit/localization",
    "line": null,
    "description": "Default backend pytest collection collides on duplicate importing/preview test basenames; Plan 04-08 verified the complete corpus in split runs.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-05T09:29:11.095Z",
    "resolved_at": null
  },
  {
    "id": 54,
    "kind": "deviation",
    "phase": "04",
    "file": "backend/tests/architecture/test_phase2_scope.py",
    "line": null,
    "description": "Phase 2 architecture guards still reject the Phase 4 canonical translation model modules",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-05T10:14:35.482Z",
    "resolved_at": null
  },
  {
    "id": 55,
    "kind": "unrun-verify",
    "phase": "04",
    "file": "backend/tests/worker/test_smoke_task.py",
    "line": null,
    "description": "Broad worker smoke requires Redis and a Celery worker at 127.0.0.1:56379",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-05T10:14:35.637Z",
    "resolved_at": null
  }
]
````
