---
status: resolved
trigger: "Run the complete local application inside Docker and make web login reach the backend"
created: 2026-08-28
updated: 2026-08-28
---

# Debug Session: Dockerized frontend login

## Symptoms

- expected: All five Compose services are healthy and the frontend container serves a login page whose generated client reaches the backend on port 8000.
- actual: A manually launched Vite server serves port 8080 without an API base URL; the Compose frontend image cannot currently build because `frontend/openapi.json` is absent from its build stage.
- errors: Frontend same-origin token request returns 404; Docker frontend typecheck cannot resolve the OpenAPI JSON imported by the contract test.
- timeline: The container defect was recorded during Plan 02-16 and became user-visible while testing login after Plan 02-18 Task 1.
- reproduction: Build the frontend Compose image, or launch Vite without `VITE_API_BASE_URL` and submit valid credentials.

## Current Focus

- hypothesis: Copying the canonical OpenAPI schema into the frontend build stage will restore the container build; the existing Compose build arg will then point the generated client to port 8000.
- test: Observe the failing frontend image build, apply the minimal Dockerfile change with a regression contract, rebuild, stop the manual Vite process, start the Compose frontend, and verify health plus token routing.
- expecting: RED fails on missing `openapi.json`; GREEN builds and all five Compose services become healthy without resetting volumes.
- next_action: none
- reasoning_checkpoint:
- tdd_checkpoint: RED and GREEN observed; regression and isolated browser smoke passed

## Evidence

- 2026-08-28: RED `docker compose build --no-cache frontend` failed with TS2307 because `/app/openapi.json` was absent during `tsc --noEmit`.
- 2026-08-28: Adding the canonical schema copy before `frontend/src` made the Compose frontend image build pass, including typecheck and Vite production build.
- 2026-08-28: All five primary Compose services became healthy after replacing the manual Vite process with the Nginx frontend container; PostgreSQL and Redis volumes were preserved.
- 2026-08-28: The built frontend asset contains `http://localhost:8000`, `/login` returns 200, and the backend CORS preflight from `http://localhost:8080` returns 200.
- 2026-08-28: Generated admin client contract passed 6/6 and `api:check` produced no schema or generated-client drift; package manifests and lockfile remained unchanged.
- 2026-08-28: Isolated `tools/real_smoke.sh --browser-only` completed image builds, migration upgrade/downgrade/upgrade, worker readiness and the Playwright auth shell: 1/1 passed, final result PASS.
- 2026-08-28: The primary local administrator remained active after the switch; no application data volume was reset.

## Eliminated

- hypothesis: The production frontend build cannot consume the configured backend URL.
  evidence: The built asset contains `http://localhost:8000` and CORS preflight passes.
- hypothesis: Dockerizing the frontend requires resetting the primary database.
  evidence: All services became healthy with existing volumes and the admin persisted.

## Eliminated

## Resolution

- root_cause: The Docker frontend builder copied source files but omitted the canonical `frontend/openapi.json` imported by the generated-client contract test, so typecheck failed before Vite could build the configured production asset.
- fix: Copy `frontend/openapi.json` to `/app/openapi.json` in the builder before copying `frontend/src` and running the existing build command.
- verification: RED/GREEN image builds, 6/6 client contract, deterministic API drift check, five healthy primary Compose services, CORS/asset checks and isolated browser smoke PASS.
- files_changed: docker/frontend.Dockerfile
