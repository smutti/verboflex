---
status: resolved
trigger: "Login web locale rifiutato dopo bootstrap del primo amministratore"
created: 2026-08-28
updated: 2026-08-28
diagnose_only: true
---

# Debug Session: Web login rejected

## Symptoms

- expected: Login at `http://localhost:8080/login` accepts the newly bootstrapped corporate email and disposable password, then redirects to the required password-change page.
- actual: Submitting the credentials from the web page does not authenticate the user.
- errors: No exact browser error supplied yet; inspect the rendered error and network/API response.
- timeline: Started immediately after creating the first local administrator.
- reproduction: Open the local login page, enter the bootstrapped email and supplied disposable password, and submit.

## Current Focus

- hypothesis: The Vite development server was started without the backend API base URL, so the generated client posts to port 8080 instead of port 8000.
- test: Compare the same-origin token path, backend token path, stored password verification, and a direct authenticated backend request.
- expecting: Password verification and direct backend login succeed while the Vite same-origin path returns 404.
- next_action: restart the Vite development server with `VITE_API_BASE_URL=http://localhost:8000` after user authorization
- reasoning_checkpoint:
- tdd_checkpoint:

## Evidence

- 2026-08-28: Database contains the active administrator `simone.mutti@comelit.it` with `must_change_password=true` and an Argon2id password hash.
- 2026-08-28: Non-echoed password verification against the stored hash returned `password_matches=True`.
- 2026-08-28: Direct POST to backend `/api/v1/auth/token` returned HTTP 200, `must_change_password=true`, and an access token.
- 2026-08-28: POST to `http://127.0.0.1:8080/api/v1/auth/token` returned HTTP 404, while the endpoint exists on port 8000.
- 2026-08-28: The running Vite process has no `VITE_API_BASE_URL`; `frontend/src/api/config.ts` therefore selects `/`, and `vite.config.ts` defines no API proxy.
- 2026-08-28: Browser renders the generic invalid-login alert and no JavaScript exception.

## Eliminated

- hypothesis: The supplied password differs from the stored password.
  evidence: Direct Argon2 verification succeeded.
- hypothesis: The backend rejects the valid account or password.
  evidence: Direct backend token request returned HTTP 200 and a valid password-change authority.
- hypothesis: The account is inactive or missing.
  evidence: The database row exists and is active.

## Resolution

- root_cause: The local Vite server was launched without `VITE_API_BASE_URL=http://localhost:8000`. The generated client falls back to `/`, so login is posted to the frontend server on port 8080 and receives 404.
- fix: Operational restart only: launch Vite with the explicit backend base URL. A durable development proxy or environment contract may be considered separately.
- verification: Stored password and direct backend authentication both pass; wrong frontend target independently reproduces the failure.
- files_changed: none; diagnosis artifact only
