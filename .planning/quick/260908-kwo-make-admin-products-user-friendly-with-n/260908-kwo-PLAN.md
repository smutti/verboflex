---
quick_id: 260908-kwo
title: Make admin products user friendly
status: complete
date: 2026-09-08
---

# Quick plan

## Goal

Make the administrative product catalogue easier to scan and filter: fixed 50-item cursor pages loaded automatically, name search, status chips, and a centered visual empty state.

## Tasks

1. Add a backward-compatible optional `name` filter to the existing admin product-list API, bind it to cursor pagination, and prove matching and cursor isolation with failing backend tests before implementation.
2. Replace the page-size/status selects with a debounced name search, status chips, and automatic infinite scrolling at 50 items; add a centered icon-led empty/no-results state and prove the behavior with failing frontend tests before implementation.
3. Synchronize the generated client type, run focused backend/frontend tests and builds, then smoke-check the Docker application and record evidence.

## API constraints

- Internal, existing HTTP/JSON surface; the new query parameter is optional and preserves default behavior.
- Existing bearer authentication and admin authorization remain unchanged.
- Cursor pagination remains server-owned and bounded to 50 items per UI request.
- The cursor must not be reusable across different status or name-filter contexts.
- This is a read operation, so idempotency does not apply; no new expensive response fields are introduced.
