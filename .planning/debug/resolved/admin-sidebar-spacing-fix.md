---
status: resolved
trigger: "procedi con la correzione TDD della sidebar amministrativa dilatata"
created: 2026-08-28
updated: 2026-08-28
---

# Debug Session: Admin sidebar spacing fix

## Symptoms

- expected: Desktop Administration navigation remains a compact group immediately below Workspace overview at every supported viewport height.
- actual: The desktop flex sidebar stretches the nested grid rows across the available viewport height.
- errors: No runtime exception; visible layout regression.
- timeline: Diagnosed in `.planning/debug/resolved/admin-sidebar-spacing.md` after Plan 02-18 Task 1.
- reproduction: Open an authenticated admin route at desktop width with a tall viewport and compare the vertical bounds of Workspace overview, Administration, Products, Users, and Bitbucket.

## Current Focus

- hypothesis: Confirmed: explicit block-axis start alignment on the shared navigation grid prevents implicit row stretching without changing responsive structure or semantics.
- test: Run a real-browser regression at a tall desktop viewport that requires the Administration group to remain compact and near Workspace overview.
- expecting: RED fails against the original production stylesheet; adding `content-start` to `WorkspaceNavigation` makes it pass.
- next_action: none
- reasoning_checkpoint: User authorized the diagnosed minimal fix and TDD/browser regression.
- tdd_checkpoint: RED and GREEN observed; full frontend and local Docker gates passed

## Evidence

- 2026-08-28: Prior diagnosis measured current nav rows at 532 px and 616 px, with four Administration rows at 148.75 px each; an isolated `content-start` candidate compacted them.
- 2026-08-28: RED `tools/real_smoke.sh --browser-only` failed the new Playwright geometry assertion: the rendered gap from Workspace overview to Administration was 332.703125 px versus the compact maximum of 40 px.
- 2026-08-28: Applied the diagnosed one-class change, adding `content-start` to the shared `WorkspaceNavigation` grid.
- 2026-08-28: GREEN rerun passed the complete isolated browser smoke, including forced password change, refresh, desktop/mobile navigation and the new geometry check: 1/1, `real staging smoke: PASS`.
- 2026-08-28: Full frontend suite passed 149/149; focused AppShell suite passed 15/15; typecheck, lint, Prettier and production Vite build passed.
- 2026-08-28: Rebuilt and replaced the local Docker frontend at `http://localhost:8080`; frontend, backend, PostgreSQL, Redis, and worker remained healthy, and the backend health endpoint returned `{"status":"ok"}`.

## Eliminated

- hypothesis: Compacting the desktop grid breaks the shared mobile navigation.
  evidence: The isolated browser smoke exercises 768 px and 375 px Sheet navigation cycles after the same shared markup change and passed.
- hypothesis: The fix requires changes to the sidebar height, routes, or destination structure.
  evidence: One `content-start` utility on the existing shared nav was sufficient; all 149 frontend tests and the real browser smoke passed unchanged.

## Resolution

- root_cause: The tall desktop flex aside cross-axis stretched its direct grid nav; default CSS Grid `align-content: normal` then distributed free block-axis space into implicit navigation rows and again into the nested Administration rows.
- fix: Added Tailwind `content-start` to `WorkspaceNavigation`, keeping the shared grid full-height but packing its implicit rows at the top. Added a Playwright geometry regression that caps the group gap and control heights.
- verification: RED gap 332.703125 px; GREEN isolated browser smoke 1/1 PASS; frontend 149/149; AppShell 15/15; typecheck/lint/format/build PASS; local Docker stack healthy.
- files_changed: frontend/src/components/layout/AppShell.tsx, frontend/e2e/auth-shell.spec.ts
