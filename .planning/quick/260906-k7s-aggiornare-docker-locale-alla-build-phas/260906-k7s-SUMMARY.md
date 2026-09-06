---
task: 260906-k7s
status: complete
completed: 2026-09-06T12:36:50Z
---

# Local Phase 4 application upgraded for UAT

Executed inline under the Codex quick fallback on codex/merge-phases-4-5.
No application source, dependency, provider configuration or roadmap changes.

## Delivery

- Source digest unchanged: sha256:2df3766ead7f1aea3597a8ad8b99205f14508a4189109996149265a163017b3a.
- Built backend/frontend using existing Dockerfiles and locked dependencies.
- Applied migrations 0012_import_jobs through 0021_retained_constraint_epoch successfully.
- Recreated only backend, worker and frontend; original PostgreSQL/Redis containers and volumes retained. No scheduler added and no provider jobs initiated.
- Original backend/worker environment preserved exactly, including authentication and Bitbucket secret material; no secrets printed or committed.
- No queued/running import or preview records existed before the update.

## Checks

- Compose build, migrations and up --wait passed; three application containers healthy.
- API /api/v1/health returned HTTP 200 and status ok.
- Frontend HTML and new index-HrB9VbNJ.js / index-C2waBoxL.css assets returned HTTP 200.
- Celery worker inspect ping returned pong.
- Users (1), products (1), Bitbucket connections (1) preserved byte-for-byte at row-JSON fingerprint level; zero mappings existed before deployment.
- pg_trgm already present; no new database extension installed.
- UAT remains 0/4 pending: deployment checks are not human Bitbucket/accessibility acceptance.

## Recovery

Private temporary recovery directory: /tmp/verboflex-local-upgrade-GNqKTo (owner-only).
Custom PostgreSQL dump pre-upgrade.dump: 65,709 bytes, mode 0600; pg_restore --list validated its archive structure (a full restore was not performed).
Backend original image retained as verboflex-backend:pre-phase4-260906-k7s.
The old frontend image referenced missing Docker content, so tagging/committing it failed before any database migration. Original served assets and nginx configuration were copied as frontend-before/ and nginx-before.conf instead.
Runtime environment snapshot is private runtime.json, mode 0600, outside git. Do not display it. Recovery files are temporary, not a permanent backup policy; do not automatically restore them over live data.

## User handoff

Reload localhost:8080. First prepare/publish a mapping using a disposable repository branch, exact layout and base language, run import and find its values in Translations. Then change one target externally and refresh; compare provenance and preserved context. No remote writes were made by this task.
