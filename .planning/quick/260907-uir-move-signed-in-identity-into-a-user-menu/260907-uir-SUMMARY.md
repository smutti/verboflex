---
quick_id: 260907-uir
status: complete
source_commit: 155774c
completed_at: "2026-09-07T20:11:43Z"
---

# Header user menu and profile password management

The repeated signed-in identity card has been removed from Workspace. The authenticated shell now places an accessible user menu immediately beside logout: its trigger shows the user icon and display name, while the menu exposes display name, email, assigned roles, and a Profile destination.

Every authenticated role can open `/profile`. The page presents account details and reuses the established password-change validation and generated API client. A successful change returns the user to sign-in because the backend revokes existing sessions when credentials change. The forced temporary-password flow remains unchanged.

## TDD evidence

- RED: nine focused tests failed before implementation across the shell, Workspace, routing, and session authority boundaries.
- GREEN: the five focused test files passed with 121 tests.
- Regression: all 34 frontend test files passed, 630 tests total.
- Static/build gates: TypeScript, ESLint, Prettier, and the Vite production build passed.
- Local deployment: rebuilt and recreated only the frontend container; `http://localhost:8080/` responds, the built asset contains the Profile page, and frontend/backend/worker/Redis/PostgreSQL are healthy.

## Residual note

Vite still reports the pre-existing advisory that the main JavaScript bundle is larger than 500 kB. This task adds no dependency and does not alter the existing bundle-splitting boundary.
