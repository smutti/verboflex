---
status: resolved
trigger: "perchè il worker non è available?"
created: 2026-09-08T12:50:00Z
updated: 2026-09-08T12:54:00Z
mode: find-and-fix
---

# Worker health false negative

## Symptoms

Expected: the Home service-status panel reports the running and responsive Celery worker as online.
Actual: API, PostgreSQL, and Redis are online, while the worker is reported unavailable.
Error message: the UI shows `Worker unavailable` without an infrastructure error detail.
Timeline: observed on 2026-09-08 in the current local Docker deployment.
Reproduction: sign in as an administrator, open `/`, and wait for the service-status request.

## Current Focus

hypothesis: Confirmed and fixed: the inner Celery inspect timeout consumed the full outer service deadline, leaving no allowance for protocol overhead.
test: Route wiring regression plus repeated probes against the rebuilt local backend and worker.
expecting: A healthy worker is reported online without weakening the public bounded-time contract.
next_action: User can refresh Home and verify the green worker card and project statistics.

## Evidence

- Docker reports `verboflex-worker-1` healthy and its Celery process has been running for more than seven hours.
- Worker logs show a successful Redis connection and `celery@72bb23c31dbc ready`.
- A direct Celery control ping from the backend returns `pong`.
- Eight live worker probes configured with a two-second Celery timeout each take about 2.08 seconds, exceeding the surrounding two-second service deadline.
- RED: the route-wiring regression expected an inner timeout of 0.125 seconds for a 0.25-second public deadline and initially received 0.25 seconds.
- GREEN: all eight system-status API tests pass after reserving half the deadline for Celery protocol overhead.
- Five consecutive probes through the rebuilt local service return `online`; frontend, backend, worker, Redis, and PostgreSQL containers are healthy.

## Eliminated

- hypothesis: The worker container is stopped or unhealthy.
  evidence: Docker health and the Celery process are both healthy.
- hypothesis: The worker cannot reach Redis.
  evidence: Worker startup logs show a successful Redis connection and direct control ping succeeds.

## Resolution

root_cause: The Celery inspect call and its outer asynchronous guard shared the exact same timeout. Celery waits through its collection window and adds a small protocol cleanup cost, so the outer guard cancelled a healthy response and projected `unavailable`.
fix: Give the inner Celery inspect operation half of the configured public probe deadline, preserving the strict external bound while leaving deterministic room for protocol overhead.
verification: 8 backend system-status tests, Ruff, MyPy, 92 focused frontend tests, frontend typecheck, lint, format, production build, five live worker probes, container health, and HTTP smoke checks pass.
files_changed: backend/src/verboflex/api/v1/routes/system.py, backend/tests/api/test_system_status.py, frontend/src/components/layout/AppShell.tsx, frontend/src/features/workspace/WorkspaceOverviewPage.tsx, frontend/src/App.test.tsx, frontend/src/router.test.tsx, frontend/src/components/layout/AppShell.test.tsx, frontend/src/features/workspace/WorkspaceOverviewPage.test.tsx
